"""Kimi AgentSwarm coordination strategy — ICoordinationStrategy implementation.

Bridges Beddel's multi-agent coordination port to Kimi's native AgentSwarm tool.
Creates a single parent Session, instructs the model to invoke AgentSwarm with
the coordination task's subtasks, and collects SubagentEvent/ToolResult messages.

Auth: Reuses ``session.py`` helpers (MOONSHOT_API_KEY, model resolution).
Concurrency: Maps ``swarm_concurrency`` to env var
``KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY`` (process-global, async-lock protected).

[Source: docs/architecture/40-agent-kimi-kit.md §40.7]
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from beddel.domain.errors import AgentError
from beddel.domain.models import (
    AgentResult,
    CoordinationResult,
    CoordinationTask,
    ExecutionContext,
)
from beddel.domain.ports import IAgentAdapter

from beddel_agent_kimi.session import (
    DEFAULT_TIMEOUT,
    get_api_key,
    resolve_model,
)

__all__ = ["KimiSwarmStrategy"]

logger = logging.getLogger(__name__)

# Error codes (from architecture §40.6)
KIMI_AUTH_MISSING: str = "BEDDEL-AGENT-800"
KIMI_SESSION_TIMEOUT: str = "BEDDEL-AGENT-801"
KIMI_SWARM_ALL_FAILED: str = "BEDDEL-AGENT-804"
KIMI_SWARM_NONCOMPLIANT: str = "BEDDEL-AGENT-804"

# Concurrency defaults
_DEFAULT_CONCURRENCY: int = 8
_MIN_CONCURRENCY: int = 1
_MAX_CONCURRENCY: int = 128
_MIN_SUBTASKS: int = 2

# Module-level lock for process-global env var mutation
_concurrency_lock = asyncio.Lock()


class KimiSwarmStrategy:
    """Kimi AgentSwarm coordination strategy implementing ICoordinationStrategy.

    Orchestrates multi-agent work by creating a parent Kimi Session and
    prompting it to invoke the native AgentSwarm tool with discrete subtask
    items. Collects SubagentEvent messages grouped by parent_tool_call_id
    and returns a CoordinationResult.

    Args:
        swarm_concurrency: Max concurrent sub-agents (1–128). Default 8.
        model: Beddel model tier for the parent session. Default None (balanced).
        timeout: Session timeout in seconds. Default 300.
        api_key: Explicit API key. If None, reads MOONSHOT_API_KEY from env.

    Raises:
        AgentError: BEDDEL-AGENT-800 if API key is unavailable.
        ValueError: If swarm_concurrency is outside valid range.
    """

    def __init__(
        self,
        swarm_concurrency: int = _DEFAULT_CONCURRENCY,
        model: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        api_key: str | None = None,
    ) -> None:
        # Validate concurrency range
        if not (_MIN_CONCURRENCY <= swarm_concurrency <= _MAX_CONCURRENCY):
            raise ValueError(
                f"swarm_concurrency must be {_MIN_CONCURRENCY}–{_MAX_CONCURRENCY}, "
                f"got {swarm_concurrency}"
            )

        try:
            self._api_key = api_key if api_key else get_api_key()
        except ValueError as exc:
            raise AgentError(
                code=KIMI_AUTH_MISSING,
                message=str(exc),
                details={"env_var": "MOONSHOT_API_KEY"},
            ) from exc

        self._concurrency = swarm_concurrency
        self._model = model
        self._timeout = timeout

    # ------------------------------------------------------------------
    # ICoordinationStrategy.coordinate
    # ------------------------------------------------------------------

    async def coordinate(
        self,
        agents: dict[str, IAgentAdapter],
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> CoordinationResult:
        """Coordinate work via Kimi AgentSwarm tool invocation.

        Creates a parent Session, sets concurrency env var, and prompts
        the model to invoke AgentSwarm with task.subtasks as items.

        Args:
            agents: Named agent adapters (available but not used directly —
                swarm uses Kimi's native sub-agent spawning).
            task: Coordination task with prompt and subtasks.
            context: Current workflow execution context.

        Returns:
            CoordinationResult with aggregate output and per-child results.

        Raises:
            AgentError: On validation failure, noncompliance, timeout, or
                total swarm failure.
        """
        # Validate minimum subtasks (SDK requires >= 2 when not resuming)
        if len(task.subtasks) < _MIN_SUBTASKS:
            raise AgentError(
                code=KIMI_SWARM_ALL_FAILED,
                message=(
                    f"AgentSwarm requires at least {_MIN_SUBTASKS} subtasks, "
                    f"got {len(task.subtasks)}"
                ),
                details={"subtask_count": len(task.subtasks)},
            )

        # Resolve model
        kimi_model = resolve_model(self._model)

        # Determine effective timeout
        timeout = task.timeout if task.timeout is not None else self._timeout

        # Set concurrency env var (process-global, lock-protected)
        async with _concurrency_lock:
            prev_val = os.environ.get("KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY")
            if prev_val is not None and prev_val != str(self._concurrency):
                raise AgentError(
                    code=KIMI_SWARM_ALL_FAILED,
                    message=(
                        "Conflicting KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY: "
                        f"env has {prev_val!r}, this instance wants {self._concurrency}"
                    ),
                    details={
                        "existing": prev_val,
                        "requested": self._concurrency,
                    },
                )
            os.environ["KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY"] = str(self._concurrency)

        try:
            return await self._run_swarm(task, kimi_model, timeout)
        finally:
            # Restore env var under lock
            async with _concurrency_lock:
                if prev_val is None:
                    os.environ.pop("KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY", None)
                else:
                    os.environ["KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY"] = prev_val

    # ------------------------------------------------------------------
    # Internal: session execution
    # ------------------------------------------------------------------

    async def _run_swarm(
        self,
        task: CoordinationTask,
        kimi_model: str,
        timeout: float,
    ) -> CoordinationResult:
        """Execute the swarm session with timeout wrapper."""
        try:
            from kimi_agent_sdk import (  # type: ignore[import-not-found]
                Config,
                Session,
            )
        except ImportError as exc:
            raise AgentError(
                code=KIMI_SWARM_ALL_FAILED,
                message=(
                    "kimi-agent-sdk is not installed. "
                    "Install with: pip install kimi-agent-sdk"
                ),
                details={"import_error": str(exc)},
            ) from exc

        config = Config(
            default_model=kimi_model,
            providers={
                "kimi": {
                    "type": "kimi",
                    "base_url": "https://api.moonshot.ai/v1",
                    "api_key": self._api_key,
                }
            },
            models={
                kimi_model: {
                    "provider": "kimi",
                    "model": kimi_model,
                }
            },
        )

        # Build the swarm instruction prompt
        swarm_prompt = self._build_swarm_prompt(task)

        try:
            async with await Session.create(
                work_dir=str(task.context_data.get("work_dir", ".")),
                config=config,
            ) as session:
                try:
                    result = await asyncio.wait_for(
                        self._collect_swarm_messages(session, swarm_prompt, task),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    raise AgentError(
                        code=KIMI_SESSION_TIMEOUT,
                        message=f"Kimi swarm session timed out after {timeout}s",
                        details={
                            "timeout": timeout,
                            "model": kimi_model,
                            "subtask_count": len(task.subtasks),
                        },
                    )

        except AgentError:
            raise
        except Exception as exc:
            raise AgentError(
                code=KIMI_SWARM_ALL_FAILED,
                message=f"Kimi swarm session failed: {exc}",
                details={"error": str(exc), "model": kimi_model},
            ) from exc

        return result

    # ------------------------------------------------------------------
    # Internal: message collection
    # ------------------------------------------------------------------

    async def _collect_swarm_messages(
        self,
        session: Any,
        prompt: str,
        task: CoordinationTask,
    ) -> CoordinationResult:
        """Collect messages from session.prompt() and build CoordinationResult.

        Verifies that the model actually invoked the AgentSwarm tool (ToolCall),
        collects SubagentEvent messages grouped by parent_tool_call_id, and
        extracts the aggregate report from ToolResult.
        """
        tool_call_seen = False
        aggregate_text: str = ""
        subagent_events: dict[str, list[Any]] = {}  # parent_tool_call_id -> events
        failed_agents: list[str] = []
        agent_results: dict[str, AgentResult] = {}
        parent_text_parts: list[str] = []

        async for msg in session.prompt(prompt):
            msg_type = type(msg).__name__

            if msg_type == "ToolCall":
                # Verify it's the AgentSwarm tool
                tool_name = getattr(msg, "name", None) or getattr(
                    msg, "tool_name", None
                )
                if tool_name == "AgentSwarm":
                    tool_call_seen = True
                    logger.debug(
                        "AgentSwarm ToolCall detected: id=%s",
                        getattr(msg, "id", "unknown"),
                    )

            elif msg_type == "SubagentEvent":
                parent_id = getattr(msg, "parent_tool_call_id", "unknown")
                event_data = getattr(msg, "event", msg)
                subagent_events.setdefault(parent_id, []).append(event_data)

                # Track individual child failures from event data
                child_id = getattr(event_data, "agent_id", None) or str(
                    len(subagent_events.get(parent_id, []))
                )
                status = getattr(event_data, "status", None)
                if status == "failed":
                    failed_agents.append(child_id)
                    logger.warning(
                        "Swarm child %s failed (parent_tool_call_id=%s)",
                        child_id,
                        parent_id,
                    )
                elif status == "completed":
                    # Build AgentResult from structured child event
                    child_output = getattr(event_data, "output", "") or ""
                    agent_results[child_id] = AgentResult(
                        exit_code=0,
                        output=child_output,
                        events=[],
                        files_changed=[],
                        usage={},
                        agent_id=child_id,
                    )

            elif msg_type == "ToolResult":
                # Aggregate report from AgentSwarm
                result_text = getattr(msg, "text", None) or getattr(
                    msg, "content", None
                )
                if result_text:
                    aggregate_text = str(result_text)

            elif hasattr(msg, "text"):
                # Parent text messages
                parent_text_parts.append(msg.text)

        # Verify model compliance — AgentSwarm MUST have been invoked
        if not tool_call_seen:
            raise AgentError(
                code=KIMI_SWARM_NONCOMPLIANT,
                message=(
                    "Model did not invoke AgentSwarm tool — "
                    "noncompliance with swarm instruction"
                ),
                details={
                    "parent_text": "".join(parent_text_parts),
                    "subtask_count": len(task.subtasks),
                },
            )

        # If ALL children failed, raise error
        total_children = sum(len(events) for events in subagent_events.values())
        if total_children > 0 and len(failed_agents) >= total_children:
            raise AgentError(
                code=KIMI_SWARM_ALL_FAILED,
                message="All swarm sub-agents failed",
                details={
                    "failed_agents": failed_agents,
                    "total_children": total_children,
                },
            )

        # Use aggregate text as canonical output; fall back to parent text
        output = aggregate_text if aggregate_text else "".join(parent_text_parts)

        return CoordinationResult(
            output=output,
            agent_results=agent_results,
            strategy_name="kimi-agent-swarm",
            metadata={
                "item_count": len(task.subtasks),
                "child_count": total_children,
                "succeeded": len(agent_results),
                "failed": len(failed_agents),
                "failed_agents": failed_agents,
                "concurrency": self._concurrency,
                "model": resolve_model(self._model),
                "timeout": self._timeout,
            },
        )

    # ------------------------------------------------------------------
    # Internal: prompt construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_swarm_prompt(task: CoordinationTask) -> str:
        """Build the instruction prompt that forces AgentSwarm invocation.

        The prompt explicitly instructs the model to use the AgentSwarm tool
        with task.subtasks as items and task.prompt as the prompt_template.
        """
        items_list = "\n".join(f"  - {item}" for item in task.subtasks)
        return (
            "You MUST invoke the AgentSwarm tool with the following parameters. "
            "Do NOT respond with text — ONLY invoke the tool.\n\n"
            f"prompt_template: {task.prompt}\n\n"
            f"items:\n{items_list}\n\n"
            "subagent_type: coder\n\n"
            "This is a mandatory tool invocation. Respond ONLY with the "
            "AgentSwarm tool call, nothing else."
        )
