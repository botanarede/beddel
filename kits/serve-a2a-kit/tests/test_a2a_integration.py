"""In-process ASGI conformance tests for serve-a2a-kit (Story K1A.5).

These tests exercise the real a2a-sdk 1.1.2 wiring end-to-end over an
in-process ASGI transport (no real sockets, no mocking of SDK internals):

    FastAPI app
      + create_agent_card_routes()  -> GET /.well-known/agent-card.json
      + create_jsonrpc_routes()     -> POST /a2a (JSON-RPC)
    mounted via add_a2a_routes_to_fastapi()
    backed by a real DefaultRequestHandler(
        agent_executor=BeddelA2AExecutor(registry),
        task_store=InMemoryTaskStore(),
        agent_card=<real AgentCard from build_agent_card()>,
    )

Coverage (see story-k1a-5.md AC1, AC3, AC4):
    - Card discovery: GET /.well-known/agent-card.json round-trips through
      ProtoJSON parsing (A2ACardResolver against the real ASGI transport).
    - Non-streaming completion via handler.on_message_send(): terminal
      result IS a Task snapshot with TASK_STATE_COMPLETED.
    - Streaming via handler.on_message_send_stream(): first event is a
      Task(SUBMITTED); artifact events share one stable artifact_id with
      correct append/last_chunk flags; the LAST event is a
      TaskStatusUpdateEvent(COMPLETED) — NOT a Task. Streaming and
      non-streaming have different terminal event types in a2a-sdk 1.1.2.
    - Unknown workflow_id reaches terminal FAILED.
    - Text-only Part (no workflow_id) reaches terminal FAILED without
      raising out of the handler.

The workflow executor stub used here (``_StubWorkflowExecutor``) is a thin,
real class implementing the same ``execute_stream`` shape as
``beddel.domain.executor.WorkflowExecutor`` — it is not a mock of any
a2a-sdk component. Only the *workflow-side* streaming is stubbed, per the
existing ``test_server.py`` precedent (``_mock_execute_stream``); every
a2a-sdk object (``FastAPI``, ``DefaultRequestHandler``, ``InMemoryTaskStore``,
``AgentCard``, routes, ``httpx.ASGITransport``) is the real SDK component.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from a2a.client import A2ACardResolver
from a2a.server.agent_execution.context import ServerCallContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    Message,
    Part,
    Role,
    SendMessageConfiguration,
    SendMessageRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)
from fastapi import FastAPI
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value

from beddel.domain.models import (
    BeddelEvent,
    EventType,
    ExecutionStrategy,
    Step,
    StrategyType,
    Workflow,
)
from beddel_serve_a2a.server import (
    BeddelA2AExecutor,
    WorkflowRegistry,
    build_agent_card,
)

# ---------------------------------------------------------------------------
# Workflow / step builders (mirrors test_server.py helpers)
# ---------------------------------------------------------------------------


def _make_step(step_id: str = "step-1", primitive: str = "llm") -> Step:
    """Create a minimal Step for testing."""
    return Step(
        id=step_id,
        primitive=primitive,
        config={},
        execution_strategy=ExecutionStrategy(type=StrategyType.FAIL),
    )


def _make_workflow(
    wf_id: str = "wf-integration",
    name: str = "Integration Test Workflow",
    description: str = "A workflow used for ASGI conformance testing",
    steps: list[Step] | None = None,
) -> Workflow:
    """Create a minimal Workflow for testing."""
    return Workflow(
        id=wf_id,
        name=name,
        description=description,
        steps=steps or [_make_step()],
    )


async def _mock_execute_stream(
    events: list[BeddelEvent],
) -> AsyncGenerator[BeddelEvent, None]:
    """Yield a pre-built list of BeddelEvents as an async generator."""
    for event in events:
        yield event


class _StubWorkflowExecutor:
    """Minimal workflow-side executor stub with an ``execute_stream`` method.

    This stands in for ``beddel.domain.executor.WorkflowExecutor`` — it is
    not part of the a2a-sdk and is not a mock of SDK internals. It exists
    purely to control which ``BeddelEvent`` sequence the real
    ``BeddelA2AExecutor`` sees, so that streaming/non-streaming/failure
    paths through the REAL SDK request handler can be exercised
    deterministically.
    """

    def __init__(self, events: list[BeddelEvent]) -> None:
        self._events = events

    def execute_stream(
        self, workflow: Workflow, inputs: dict[str, Any] | None
    ) -> AsyncGenerator[BeddelEvent, None]:
        return _mock_execute_stream(self._events)


def _build_send_request(
    workflow_id: str | None = None, *, text_only: bool = False
) -> SendMessageRequest:
    """Build a real SendMessageRequest carrying a DataPart or a text Part."""
    if text_only:
        return SendMessageRequest(
            message=Message(
                role=Role.ROLE_USER,
                parts=[Part(text="hello, no workflow_id here")],
                message_id=str(uuid.uuid4()),
            ),
            configuration=SendMessageConfiguration(),
        )

    data_value = Value()
    json_format.ParseDict({"workflow_id": workflow_id}, data_value)

    return SendMessageRequest(
        message=Message(
            role=Role.ROLE_USER,
            parts=[Part(data=data_value)],
            message_id=str(uuid.uuid4()),
        ),
        configuration=SendMessageConfiguration(),
    )


# ---------------------------------------------------------------------------
# Fixtures — real FastAPI app + real DefaultRequestHandler over ASGI
# ---------------------------------------------------------------------------


class _A2AHarness:
    """Bundle of real a2a-sdk components wired for in-process testing.

    Attributes:
        app: The FastAPI app with real A2A routes mounted.
        handler: The real ``DefaultRequestHandler`` backing the routes.
        client: An ``httpx.AsyncClient`` dispatching over ``ASGITransport``
            (zero real sockets).
        registry: The workflow registry backing the executor.
    """

    def __init__(
        self,
        app: FastAPI,
        handler: DefaultRequestHandler,
        client: httpx.AsyncClient,
        registry: WorkflowRegistry,
    ) -> None:
        self.app = app
        self.handler = handler
        self.client = client
        self.registry = registry


def _build_harness(
    events_by_workflow: dict[str, list[BeddelEvent]],
) -> _A2AHarness:
    """Construct a real FastAPI + DefaultRequestHandler harness.

    Args:
        events_by_workflow: Maps workflow_id to the BeddelEvent sequence
            that the stub workflow executor should stream for it.

    Returns:
        A fully wired ``_A2AHarness`` ready for ASGI dispatch.
    """
    registry: WorkflowRegistry = {}
    for wf_id, events in events_by_workflow.items():
        wf = _make_workflow(wf_id=wf_id)
        registry[wf_id] = (wf, _StubWorkflowExecutor(events))  # type: ignore[assignment]

    agent_card = build_agent_card(
        workflows=registry,
        public_base_url="http://test",
    )
    executor = BeddelA2AExecutor(registry)
    task_store = InMemoryTaskStore()
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store,
        agent_card=agent_card,
    )

    app = FastAPI()
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card),
        jsonrpc_routes=create_jsonrpc_routes(handler, rpc_url="/a2a"),
    )

    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")

    return _A2AHarness(app=app, handler=handler, client=client, registry=registry)


@pytest_asyncio.fixture
async def a2a_harness() -> AsyncGenerator[_A2AHarness, None]:
    """Pytest fixture yielding an ``_A2AHarness`` with two known workflows.

    ``wf-complete``: streams WORKFLOW_START -> TEXT_CHUNK x2 -> WORKFLOW_END
        (reaches TASK_STATE_COMPLETED).
    ``wf-fail``: streams WORKFLOW_START -> ERROR only, stream exhausts
        without a terminal event (reaches TASK_STATE_FAILED via the
        executor's fallback-to-failed behavior).

    The underlying ``httpx.AsyncClient`` is closed on teardown.
    """
    events_by_workflow = {
        "wf-complete": [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "Hello "},
            ),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "World"},
            ),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
        ],
        "wf-fail": [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.ERROR,
                step_id="step-1",
                data={"error": "fatal for this test"},
            ),
        ],
    }
    harness = _build_harness(events_by_workflow)
    try:
        yield harness
    finally:
        await harness.client.aclose()


# ---------------------------------------------------------------------------
# AC3: Card discovery at /.well-known/agent-card.json
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_card_discovery_round_trips_via_card_resolver(
    a2a_harness: _A2AHarness,
) -> None:
    """GET /.well-known/agent-card.json returns a card A2ACardResolver can parse.

    Uses the real ``A2ACardResolver`` against the real ASGI-backed
    ``httpx.AsyncClient`` — the fetched JSON round-trips back into a real
    ``AgentCard`` (ProtoJSON parse), proving the served representation is
    spec-conformant, not just "some JSON".
    """
    resolver = A2ACardResolver(
        httpx_client=a2a_harness.client,
        base_url="http://test",
    )

    card = await resolver.get_agent_card()

    assert card.name == "Beddel Agent"
    skill_ids = {skill.id for skill in card.skills}
    assert skill_ids == {"wf-complete", "wf-fail"}
    assert card.capabilities.streaming is True


@pytest.mark.asyncio
async def test_agent_card_get_direct_returns_200(a2a_harness: _A2AHarness) -> None:
    """Direct GET to the well-known card path returns HTTP 200 with JSON body."""
    response = await a2a_harness.client.get("/.well-known/agent-card.json")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Beddel Agent"


# ---------------------------------------------------------------------------
# AC1/AC4: Non-streaming completion via handler.on_message_send()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_streaming_send_returns_task_snapshot_completed(
    a2a_harness: _A2AHarness,
) -> None:
    """on_message_send() (non-streaming) returns a Task snapshot when COMPLETED.

    This is the ONE case where a Task snapshot as the terminal result is
    correct: the non-streaming path replaces status updates with Task
    snapshots before returning.
    """
    request = _build_send_request(workflow_id="wf-complete")
    call_context = ServerCallContext()

    result = await a2a_harness.handler.on_message_send(request, call_context)

    assert isinstance(result, Task)
    assert result.status.state == TaskState.TASK_STATE_COMPLETED


# ---------------------------------------------------------------------------
# AC1/AC4: Streaming via handler.on_message_send_stream()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_send_emits_ordered_events_with_stable_artifact_id(
    a2a_harness: _A2AHarness,
) -> None:
    """on_message_send_stream() yields Task(SUBMITTED) first and a
    TaskStatusUpdateEvent(COMPLETED) last — NOT a Task snapshot.

    Streaming and non-streaming have DIFFERENT terminal event types in
    a2a-sdk 1.1.2: on_message_send_stream() forwards status updates
    unchanged, only on_message_send() (non-streaming) replaces them with
    Task snapshots.
    """
    request = _build_send_request(workflow_id="wf-complete")
    call_context = ServerCallContext()

    events: list[Any] = []
    async for event in a2a_harness.handler.on_message_send_stream(
        request, call_context
    ):
        events.append(event)

    # First event: Task snapshot in SUBMITTED state.
    assert isinstance(events[0], Task)
    assert events[0].status.state == TaskState.TASK_STATE_SUBMITTED

    # Last event: TaskStatusUpdateEvent(COMPLETED) — NOT a Task.
    last_event = events[-1]
    assert isinstance(last_event, TaskStatusUpdateEvent)
    assert not isinstance(last_event, Task)
    assert last_event.status.state == TaskState.TASK_STATE_COMPLETED

    # Artifact events: two TEXT_CHUNKs + one WORKFLOW_END last_chunk marker.
    artifact_events = [ev for ev in events if isinstance(ev, TaskArtifactUpdateEvent)]
    assert len(artifact_events) == 3

    artifact_ids = {ev.artifact.artifact_id for ev in artifact_events}
    assert len(artifact_ids) == 1, (
        f"Expected one stable artifact_id across all chunks, got {artifact_ids}"
    )

    # First chunk creates the artifact (append=False); the second chunk
    # appends (append=True); the final WORKFLOW_END marker appends with
    # last_chunk=True.
    assert artifact_events[0].append is False
    assert artifact_events[0].last_chunk is False
    assert artifact_events[1].append is True
    assert artifact_events[1].last_chunk is False
    assert artifact_events[2].append is True
    assert artifact_events[2].last_chunk is True


# ---------------------------------------------------------------------------
# AC1: Unknown workflow_id reaches terminal FAILED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_workflow_id_reaches_failed_non_streaming(
    a2a_harness: _A2AHarness,
) -> None:
    """A workflow_id absent from the registry reaches TASK_STATE_FAILED
    via the non-streaming handler path.
    """
    request = _build_send_request(workflow_id="does-not-exist")
    call_context = ServerCallContext()

    result = await a2a_harness.handler.on_message_send(request, call_context)

    assert isinstance(result, Task)
    assert result.status.state == TaskState.TASK_STATE_FAILED


@pytest.mark.asyncio
async def test_unknown_workflow_id_reaches_failed_streaming(
    a2a_harness: _A2AHarness,
) -> None:
    """A workflow_id absent from the registry reaches a terminal
    TaskStatusUpdateEvent(FAILED) via the streaming handler path.
    """
    request = _build_send_request(workflow_id="does-not-exist")
    call_context = ServerCallContext()

    events: list[Any] = []
    async for event in a2a_harness.handler.on_message_send_stream(
        request, call_context
    ):
        events.append(event)

    last_event = events[-1]
    assert isinstance(last_event, TaskStatusUpdateEvent)
    assert last_event.status.state == TaskState.TASK_STATE_FAILED


# ---------------------------------------------------------------------------
# AC1: Text-only Part (missing workflow_id) reaches terminal FAILED cleanly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_only_message_missing_workflow_id_fails_cleanly(
    a2a_harness: _A2AHarness,
) -> None:
    """A Message with only a text Part (no DataPart, no workflow_id) does
    not crash the handler — it reaches TASK_STATE_FAILED with an
    informative message about the missing workflow_id.
    """
    request = _build_send_request(text_only=True)
    call_context = ServerCallContext()

    result = await a2a_harness.handler.on_message_send(request, call_context)

    assert isinstance(result, Task)
    assert result.status.state == TaskState.TASK_STATE_FAILED

    # The failure message should mention the missing workflow_id, not be
    # empty or generic — informative per the acceptance criteria.
    history_texts = [
        part.text
        for msg in result.history
        for part in msg.parts
        if part.HasField("text")
    ]
    assert any("workflow_id" in text for text in history_texts), (
        f"Expected an informative message mentioning 'workflow_id', "
        f"got history texts: {history_texts}"
    )
