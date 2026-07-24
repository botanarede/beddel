"""A2A protocol server adapter for Beddel workflows.

Part of serve-a2a-kit — the A2A protocol server kit.
Migrated from core adapters/ per ADR-0012 (Kit Boundary Rule).

Exposes Beddel workflows as A2A-compliant agents with Agent Card discovery
and task lifecycle management via the a2a-sdk.

Public API:
    - :class:`BeddelA2AExecutor` — maps Beddel workflow execution to A2A
      task lifecycle events.
    - :func:`build_agent_card` — generates an A2A Agent Card from
      discovered workflows.
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    HTTPAuthSecurityScheme,
    Message,
    Part,
    Role,
    SecurityRequirement,
    SecurityScheme,
    StringList,
    Task,
    TaskState,
    TaskStatus,
)

from beddel.domain.executor import WorkflowExecutor
from beddel.domain.models import BeddelEvent, EventType, Workflow

logger = logging.getLogger(__name__)

__all__ = [
    "BeddelA2AExecutor",
    "build_agent_card",
]


def _agent_message(text: str) -> Message:
    """Create an A2A :class:`Message` with a single text :class:`Part`."""
    return Message(
        role=Role.ROLE_AGENT,
        parts=[Part(text=text)],
        message_id=str(uuid.uuid4()),
    )


# Type alias for the workflow registry used by the executor.
# Maps workflow_id → (Workflow definition, WorkflowExecutor instance).
WorkflowRegistry = dict[str, tuple[Workflow, WorkflowExecutor]]


def _extract_workflow_params(
    context: RequestContext,
) -> tuple[str | None, dict[str, Any] | None]:
    """Extract ``workflow_id`` and ``inputs`` from A2A message parts.

    Scans the message's parts for structured data containing keys
    ``workflow_id`` and ``inputs``.  In a2a-sdk 1.x, parts use a proto
    oneof with ``text``, ``data``, ``raw``, or ``url`` fields.

    Returns:
        A ``(workflow_id, inputs)`` tuple.  Either value may be ``None``
        when the corresponding key is absent from all parts.
    """
    workflow_id: str | None = None
    inputs: dict[str, Any] | None = None

    if context.message is None:
        return workflow_id, inputs

    for part in context.message.parts:
        # In proto-based a2a-sdk 1.x, Part has a `data` field (google.protobuf.Value)
        if not part.HasField("data"):
            continue
        # Convert proto Value to Python dict
        from google.protobuf.json_format import MessageToDict

        data = MessageToDict(part.data)
        if "workflow_id" in data and workflow_id is None:
            workflow_id = str(data["workflow_id"])
        if "inputs" in data and inputs is None:
            raw = data["inputs"]
            inputs = dict(raw) if isinstance(raw, dict) else None

    return workflow_id, inputs


def _create_initial_task(
    task_id: str,
    context_id: str,
    message: Message | None = None,
) -> Task:
    """Create an initial A2A :class:`Task` with SUBMITTED status.

    Per the A2A v1.0 spec and a2a-sdk ``AgentExecutor`` contract, the
    first event enqueued for task-mode execution MUST be a ``Task`` object.
    ``TaskStatusUpdateEvent`` events may only follow after the initial Task
    is established in the store.

    Args:
        task_id: The task identifier.
        context_id: The context identifier.
        message: Optional initial message to include in task history.

    Returns:
        A :class:`Task` proto with SUBMITTED state.
    """
    task = Task(
        id=task_id,
        context_id=context_id,
        status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
    )
    if message is not None:
        task.history.append(message)
    return task


class BeddelA2AExecutor(AgentExecutor):
    """Executes Beddel workflows via the A2A task lifecycle.

    The executor bridges the Beddel streaming execution model to the A2A
    protocol by consuming :class:`~beddel.domain.models.BeddelEvent`
    instances from :meth:`WorkflowExecutor.execute_stream` and translating
    them into task lifecycle events.

    Conforms to the A2A v1.0 task-event state machine:
    - Every new execution begins by enqueuing a ``Task`` object (SUBMITTED)
    - Subsequent updates use ``TaskUpdater`` for status/artifact events
    - Streaming uses a stable artifact ID with ``append`` / ``last_chunk``
    - Every path reaches a terminal state (COMPLETED, FAILED, CANCELED)

    Args:
        registry: Mapping of workflow IDs to ``(Workflow, WorkflowExecutor)``
            tuples.  Typically built by the CLI ``connect`` command from
            discovered workflow files.
    """

    def __init__(self, registry: WorkflowRegistry) -> None:
        self._registry = registry

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute a Beddel workflow mapped to an A2A task.

        Extracts ``workflow_id`` and ``inputs`` from the incoming A2A
        message, looks up the workflow in the registry, streams execution
        events, and maps each :class:`BeddelEvent` to the appropriate
        task lifecycle call.

        Per the A2A v1.0 spec and SDK contract, the first event enqueued
        is always a ``Task`` object.  Subsequent updates use
        ``TaskUpdater`` methods.
        """
        task_id = context.task_id or ""
        context_id = context.context_id or ""

        # A2A v1.0 spec: first event MUST be a Task object (not TaskStatusUpdateEvent).
        # The SDK's ActiveTask/EventConsumer rejects TaskStatusUpdateEvent if no Task
        # exists yet (raises InvalidAgentResponseError).
        initial_task = _create_initial_task(
            task_id, context_id, message=context.message
        )
        await event_queue.enqueue_event(initial_task)

        # After the initial Task is enqueued, use TaskUpdater for subsequent events.
        updater = TaskUpdater(event_queue, task_id, context_id)

        workflow_id, inputs = _extract_workflow_params(context)

        if workflow_id is None:
            await updater.failed(
                message=_agent_message("Missing 'workflow_id' in message DataPart."),
            )
            return

        entry = self._registry.get(workflow_id)
        if entry is None:
            await updater.failed(
                message=_agent_message(
                    f"Workflow '{workflow_id}' not found in registry."
                ),
            )
            return

        workflow, executor = entry

        # Mutable state for stable artifact ID tracking across streaming chunks
        artifact_state: dict[str, str | None] = {"id": None}
        terminal_reached = False

        try:
            async with contextlib.aclosing(
                executor.execute_stream(workflow, inputs)
            ) as stream:
                async for event in stream:
                    terminal = await self._handle_event(updater, event, artifact_state)
                    if terminal:
                        terminal_reached = True
                        break
        except Exception as exc:  # noqa: BLE001
            logger.exception("Workflow %s failed unexpectedly", workflow_id)
            if not terminal_reached:
                await updater.failed(message=_agent_message(str(exc)))
                terminal_reached = True

        # Fallback: if stream exhausted without terminal event, fail the task
        if not terminal_reached:
            await updater.failed(
                message=_agent_message(
                    "Workflow stream ended without a terminal event."
                ),
            )

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Cancel a running A2A task.

        Per the A2A v1.0 spec, cancellation emits a CANCELED status update
        for the existing task.  The task already exists (created during the
        original ``execute()`` call), so no initial Task enqueue is needed.
        """
        task_id = context.task_id or ""
        context_id = context.context_id or ""
        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.cancel()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _handle_event(
        updater: TaskUpdater,
        event: BeddelEvent,
        artifact_state: dict[str, str | None],
    ) -> bool:
        """Map a single :class:`BeddelEvent` to a :class:`TaskUpdater` call.

        Args:
            updater: The task updater for emitting A2A events.
            event: The Beddel domain event to translate.
            artifact_state: Mutable dict tracking the current streaming
                artifact ID (``{"id": str | None}``).  Shared across
                all calls within one execution to maintain a stable ID.

        Returns:
            ``True`` if a terminal state was reached (COMPLETED, FAILED,
            CANCELED) and the event loop should stop.  ``False`` otherwise.
        """
        et = event.event_type

        if et == EventType.WORKFLOW_START:
            await updater.start_work()

        elif et == EventType.STEP_START:
            step_name = event.step_id or "unknown"
            await updater.update_status(
                TaskState.TASK_STATE_WORKING,
                message=_agent_message(f"Running step: {step_name}"),
            )

        elif et == EventType.TEXT_CHUNK:
            chunk = str(event.data.get("text", ""))
            if artifact_state["id"] is None:
                # First chunk: create artifact with new stable ID
                artifact_id = str(uuid.uuid4())
                artifact_state["id"] = artifact_id
                await updater.add_artifact(
                    parts=[Part(text=chunk)],
                    artifact_id=artifact_id,
                    append=False,
                )
            else:
                # Subsequent chunks: append to same artifact
                await updater.add_artifact(
                    parts=[Part(text=chunk)],
                    artifact_id=artifact_state["id"],
                    append=True,
                )

        elif et == EventType.STEP_END:
            # Step results are separate artifacts (not streaming chunks)
            result_data = event.data.get("result", "")
            step_artifact_id = str(uuid.uuid4())
            await updater.add_artifact(
                parts=[Part(text=str(result_data))],
                artifact_id=step_artifact_id,
                name=event.step_id,
                append=False,
            )

        elif et == EventType.WORKFLOW_END:
            # If streaming was active, emit final chunk marker
            if artifact_state["id"] is not None:
                await updater.add_artifact(
                    parts=[Part(text="")],
                    artifact_id=artifact_state["id"],
                    append=True,
                    last_chunk=True,
                )
            await updater.complete()
            return True  # Terminal state reached

        elif et == EventType.ERROR:
            # ERROR events are informational (recoverable SKIP/RETRY attempts
            # emit ERROR before continuing).  Only WORKFLOW_END is a normal
            # terminal event; fatal failures propagate as exceptions caught by
            # the outer try/except in execute().
            error_msg = str(event.data.get("error", "Unknown error"))
            await updater.update_status(
                TaskState.TASK_STATE_WORKING,
                message=_agent_message(f"Error (recoverable): {error_msg}"),
            )

        return False  # Non-terminal, continue processing


def build_agent_card(
    workflows: dict[str, tuple[Workflow, Any]],
    public_base_url: str = "http://127.0.0.1:8000",
    *,
    include_security: bool = False,
) -> AgentCard:
    """Build an A2A Agent Card from discovered workflows.

    Each workflow in the registry is mapped to an :class:`AgentSkill` with
    its ``id``, ``name``, ``description``, and ``tags`` derived from the
    workflow definition.

    Args:
        workflows: Mapping of workflow IDs to ``(Workflow, executor)``
            tuples.  Only the :class:`Workflow` is used; the executor
            value is ignored.
        public_base_url: The public-facing base URL for the agent
            (e.g. ``http://myhost:9000``).  The A2A endpoint URL is
            derived as ``{public_base_url}/a2a``.
        include_security: When True, include bearer auth security scheme
            in the Agent Card.

    Returns:
        A fully populated :class:`AgentCard` ready to be served at
        ``/.well-known/agent-card.json``.
    """
    # Defensive: never expose 0.0.0.0 in Agent Card
    if "0.0.0.0" in public_base_url:
        public_base_url = public_base_url.replace("0.0.0.0", "127.0.0.1")

    skills: list[AgentSkill] = []

    for wf_id, (workflow, _executor) in workflows.items():
        # Validate required fields — a2a-sdk rejects empty skill ID/name
        skill_id = wf_id.strip()
        skill_name = workflow.name.strip()
        if not skill_id:
            raise ValueError(
                f"Cannot build Agent Card: workflow ID is empty "
                f"(name={workflow.name!r})"
            )
        if not skill_name:
            raise ValueError(
                f"Cannot build Agent Card: workflow name is empty (id={wf_id!r})"
            )

        tags = ["workflow"]
        if workflow.steps:
            tags.append(workflow.steps[0].primitive)

        description = workflow.description.strip() or f"Execute workflow: {skill_name}"
        skills.append(
            AgentSkill(
                id=skill_id,
                name=skill_name,
                description=description,
                tags=tags,
            ),
        )

    # Build security schemes if requested
    security_schemes: dict[str, SecurityScheme] = {}
    security_requirements: list[SecurityRequirement] = []

    if include_security:
        bearer_scheme = SecurityScheme(
            http_auth_security_scheme=HTTPAuthSecurityScheme(
                description="Bearer token for A2A authentication",
                scheme="bearer",
                bearer_format="opaque",
            )
        )
        security_schemes["bearer"] = bearer_scheme
        req = SecurityRequirement()
        req.schemes["bearer"].CopyFrom(StringList())
        security_requirements.append(req)

    return AgentCard(
        name="Beddel Agent",
        description="A2A-compliant agent powered by Beddel workflows.",
        version="1.0.0",
        supported_interfaces=[
            AgentInterface(
                url=f"{public_base_url.rstrip('/')}/a2a",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            ),
        ],
        provider=AgentProvider(
            organization="Beddel",
            url="https://github.com/botanarede/beddel",
        ),
        skills=skills,
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        security_schemes=security_schemes,
        security_requirements=security_requirements,
    )
