"""Kimi AgentSwarm coordination strategy — ICoordinationStrategy implementation.

Bridges Beddel's multi-agent coordination port to Kimi's native AgentSwarm tool.
Creates a single parent Session, instructs the model to invoke AgentSwarm with
the coordination task's subtasks, and collects SubagentEvent/ToolResult messages.

Auth: Reuses ``session.py`` helpers (MOONSHOT_API_KEY, model resolution).
Concurrency: Maps ``swarm_concurrency`` to env var
``KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY`` (process-global, ref-counted).

[Source: docs/architecture/40-agent-kimi-kit.md §40.7]
"""

from __future__ import annotations

import asyncio
import json
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

from beddel_agent_kimi.errors import (
    KIMI_AUTH_MISSING,
    KIMI_INVALID_MODEL,
    KIMI_RATE_LIMITED,
    KIMI_SESSION_TIMEOUT,
    KIMI_SWARM_ALL_FAILED,
    KIMI_SWARM_NONCOMPLIANT,
)
from beddel_agent_kimi.session import (
    DEFAULT_TIMEOUT,
    build_kimi_config,
    get_api_key,
    resolve_model,
)
from kaos.path import KaosPath

__all__ = ["KimiSwarmStrategy"]

logger = logging.getLogger(__name__)

# Concurrency defaults
_DEFAULT_CONCURRENCY: int = 8
_MIN_CONCURRENCY: int = 1
_MAX_CONCURRENCY: int = 128
_MIN_SUBTASKS: int = 2

# Rate-limit retry configuration (mirrors adapter.py)
_MAX_RETRIES: int = 3
_BASE_BACKOFF_S: float = 2.0

# Module-level lock for process-global env var mutation
_concurrency_lock = asyncio.Lock()

# Reference counter for concurrent same-value env var usage (HIGH-1)
_concurrency_ref_counts: dict[str, int] = {}
_concurrency_original: str | None = None


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

        # Resolve model (MEDIUM-10: wrap in try/except)
        try:
            kimi_model = resolve_model(self._model)
        except ValueError as exc:
            raise AgentError(
                code=KIMI_INVALID_MODEL,
                message=str(exc),
                details={"model": self._model},
            ) from exc

        # Determine effective timeout
        effective_timeout = task.timeout if task.timeout is not None else self._timeout

        # Validate context_data serializability (MEDIUM-9)
        try:
            json.dumps(task.context_data)
        except (TypeError, ValueError, OverflowError) as exc:
            raise AgentError(
                code=KIMI_SWARM_ALL_FAILED,
                message=(f"task.context_data is not JSON-serializable: {exc}"),
                details={"error": str(exc)},
            ) from exc

        # Acquire env var with reference counting (HIGH-1)
        await self._acquire_concurrency_env()
        try:
            return await self._execute_with_retry(task, kimi_model, effective_timeout)
        finally:
            await self._release_concurrency_env()

    # ------------------------------------------------------------------
    # Internal: env var ref-counting (HIGH-1)
    # ------------------------------------------------------------------

    async def _acquire_concurrency_env(self) -> None:
        """Acquire reference-counted access to the concurrency env var."""
        global _concurrency_original  # noqa: PLW0603
        value = str(self._concurrency)

        async with _concurrency_lock:
            current = os.environ.get("KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY")

            # First caller: store the original value
            if not _concurrency_ref_counts:
                _concurrency_original = current

            # Check for conflicting values from a different instance
            if (
                current is not None
                and current != value
                and value not in _concurrency_ref_counts
            ):
                # Another caller set a different value — conflict
                if _concurrency_ref_counts.get(current, 0) > 0:
                    raise AgentError(
                        code=KIMI_SWARM_ALL_FAILED,
                        message=(
                            "Conflicting KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY: "
                            f"active sessions use {current!r}, "
                            f"this instance wants {value}"
                        ),
                        details={
                            "existing": current,
                            "requested": self._concurrency,
                        },
                    )

            # Increment ref count for this value
            _concurrency_ref_counts[value] = _concurrency_ref_counts.get(value, 0) + 1
            os.environ["KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY"] = value

    async def _release_concurrency_env(self) -> None:
        """Release reference-counted access to the concurrency env var."""
        global _concurrency_original  # noqa: PLW0603
        value = str(self._concurrency)

        async with _concurrency_lock:
            count = _concurrency_ref_counts.get(value, 0)
            if count <= 1:
                _concurrency_ref_counts.pop(value, None)
            else:
                _concurrency_ref_counts[value] = count - 1

            # Restore original only when ALL refs are released
            if not _concurrency_ref_counts:
                if _concurrency_original is None:
                    os.environ.pop("KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY", None)
                else:
                    os.environ["KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY"] = (
                        _concurrency_original
                    )
                _concurrency_original = None

    # ------------------------------------------------------------------
    # Internal: retry loop (HIGH-6)
    # ------------------------------------------------------------------

    async def _execute_with_retry(
        self,
        task: CoordinationTask,
        kimi_model: str,
        timeout: float,
    ) -> CoordinationResult:
        """Execute swarm with exponential backoff on 429 rate limits."""
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                return await self._run_swarm(task, kimi_model, timeout)
            except AgentError as exc:
                if exc.code == KIMI_RATE_LIMITED and attempt < _MAX_RETRIES:
                    last_exc = exc
                    backoff = _BASE_BACKOFF_S * (2**attempt)
                    logger.warning(
                        "Kimi swarm rate limited (attempt %d/%d), retrying in %.1fs",
                        attempt + 1,
                        _MAX_RETRIES,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise

        # Should not reach here, but satisfy type checker
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Internal: session execution (HIGH-5: full lifecycle under timeout)
    # ------------------------------------------------------------------

    async def _run_swarm(
        self,
        task: CoordinationTask,
        kimi_model: str,
        timeout: float,
    ) -> CoordinationResult:
        """Execute the swarm session with timeout covering full lifecycle."""
        try:
            from kimi_agent_sdk import Session  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AgentError(
                code=KIMI_SWARM_ALL_FAILED,
                message=(
                    "kimi-agent-sdk is not installed. "
                    "Install with: pip install kimi-agent-sdk"
                ),
                details={"import_error": str(exc)},
            ) from exc

        # Use shared config builder (returns validated Config object)
        # Build the swarm instruction prompt
        swarm_prompt = self._build_swarm_prompt(task)

        # State for partial output access in timeout handler (HIGH-5)
        collection_state = _SwarmCollectionState()

        try:
            config = build_kimi_config(self._api_key, kimi_model)
            # Wrap ENTIRE lifecycle in timeout (HIGH-5)
            await asyncio.wait_for(
                self._run_session_lifecycle(
                    Session, config, task, swarm_prompt, collection_state
                ),
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
                    "partial_output": collection_state.get_partial_output(),
                    "child_states": dict(collection_state.child_terminal_states),
                    "failed_ids": list(collection_state.failed_ids),
                },
            )
        except AgentError:
            raise
        except Exception as exc:
            exc_str = str(exc)
            # Detect rate limit errors (HTTP 429) — HIGH-6
            if "429" in exc_str or "rate" in exc_str.lower():
                raise AgentError(
                    code=KIMI_RATE_LIMITED,
                    message=f"Kimi swarm rate limited: {exc}",
                    details={"error": exc_str, "model": kimi_model},
                ) from exc
            raise AgentError(
                code=KIMI_SWARM_ALL_FAILED,
                message=f"Kimi swarm session failed: {exc}",
                details={"error": exc_str, "model": kimi_model},
            ) from exc

        return collection_state.build_result(
            task=task,
            kimi_model=kimi_model,
            concurrency=self._concurrency,
            effective_timeout=timeout,
        )

    async def _run_session_lifecycle(
        self,
        session_cls: Any,
        config: Any,
        task: CoordinationTask,
        swarm_prompt: str,
        state: "_SwarmCollectionState",
    ) -> None:
        """Full session lifecycle: create + prompt + collect (HIGH-5)."""
        async with await session_cls.create(
            work_dir=KaosPath(str(task.context_data.get("work_dir", "."))),
            config=config,
        ) as session:
            await self._collect_swarm_messages(session, swarm_prompt, task, state)

    # ------------------------------------------------------------------
    # Internal: message collection (HIGH-3, HIGH-4)
    # ------------------------------------------------------------------

    async def _collect_swarm_messages(
        self,
        session: Any,
        prompt: str,
        task: CoordinationTask,
        state: "_SwarmCollectionState",
    ) -> None:
        """Collect messages from session.prompt() and populate state.

        Verifies that the model actually invoked the AgentSwarm tool (ToolCall),
        collects SubagentEvent messages correlated by parent_tool_call_id,
        and extracts the aggregate report from ToolResult.
        """
        async for msg in session.prompt(prompt):
            # Wire-message dispatch based on class-name strings.
            # Rationale: kimi-agent-sdk is not installed locally so we
            # cannot import concrete types for isinstance() checks.
            # The SDK guarantees stable class names for its wire protocol.
            msg_type = type(msg).__name__

            if msg_type == "ToolCall":
                # Verify it's the AgentSwarm tool
                tool_name = getattr(msg, "name", None) or getattr(
                    msg, "tool_name", None
                )
                if tool_name == "AgentSwarm":
                    # HIGH-4: Record the ToolCall ID for correlation
                    call_id = getattr(msg, "id", None)
                    if call_id:
                        state.agent_swarm_call_id = call_id
                    state.tool_call_seen = True
                    logger.debug("AgentSwarm ToolCall detected: id=%s", call_id)

            elif msg_type == "SubagentEvent":
                parent_id = getattr(msg, "parent_tool_call_id", None)

                # HIGH-4: Only accept events correlated to our AgentSwarm call
                if state.agent_swarm_call_id and parent_id != state.agent_swarm_call_id:
                    continue

                event_data = getattr(msg, "event", msg)

                # HIGH-3: Track children by unique child_id
                child_id = getattr(event_data, "agent_id", None) or getattr(
                    event_data, "child_id", None
                )
                if not child_id:
                    child_id = f"child-{len(state.child_terminal_states) + 1}"

                status = getattr(event_data, "status", None)

                # Only record terminal states (HIGH-3)
                if status == "failed":
                    state.child_terminal_states[child_id] = "failed"
                    state.failed_ids.add(child_id)
                    logger.warning(
                        "Swarm child %s failed (parent_tool_call_id=%s)",
                        child_id,
                        parent_id,
                    )
                elif status == "completed":
                    state.child_terminal_states[child_id] = "completed"
                    # Build AgentResult from terminal completed event
                    child_output = getattr(event_data, "output", "") or ""
                    state.agent_results[child_id] = AgentResult(
                        exit_code=0,
                        output=child_output,
                        events=[],
                        files_changed=[],
                        usage={},
                        agent_id=child_id,
                    )

            elif msg_type == "ToolResult":
                parent_id = getattr(msg, "parent_tool_call_id", None) or getattr(
                    msg, "tool_call_id", None
                )

                # HIGH-4: Only accept ToolResult correlated to our call
                if state.agent_swarm_call_id and parent_id != state.agent_swarm_call_id:
                    continue

                result_text = getattr(msg, "text", None) or getattr(
                    msg, "content", None
                )
                if result_text:
                    state.aggregate_text = str(result_text)
                state.tool_result_seen = True

            elif hasattr(msg, "text"):
                # Parent text messages
                state.parent_text_parts.append(msg.text)

        # Verify model compliance — AgentSwarm MUST have been invoked
        if not state.tool_call_seen:
            raise AgentError(
                code=KIMI_SWARM_NONCOMPLIANT,
                message=(
                    "Model did not invoke AgentSwarm tool — "
                    "noncompliance with swarm instruction"
                ),
                details={
                    "parent_text": "".join(state.parent_text_parts),
                    "subtask_count": len(task.subtasks),
                },
            )

        # HIGH-4: If AgentSwarm was called but no matching ToolResult arrived
        if state.tool_call_seen and not state.tool_result_seen:
            raise AgentError(
                code=KIMI_SWARM_ALL_FAILED,
                message=(
                    "AgentSwarm ToolCall was issued but no matching "
                    "ToolResult was received — stream ended prematurely"
                ),
                details={
                    "agent_swarm_call_id": state.agent_swarm_call_id,
                    "child_states": dict(state.child_terminal_states),
                },
            )

        # If ALL children failed, raise error (HIGH-3: use unique children)
        total_children = len(state.child_terminal_states)
        if total_children > 0 and len(state.failed_ids) >= total_children:
            raise AgentError(
                code=KIMI_SWARM_ALL_FAILED,
                message="All swarm sub-agents failed",
                details={
                    "failed_agents": list(state.failed_ids),
                    "total_children": total_children,
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


# ---------------------------------------------------------------------------
# Internal state container for message collection (HIGH-5)
# ---------------------------------------------------------------------------


class _SwarmCollectionState:
    """Mutable state container for swarm message collection.

    Stored as an instance so partial state is accessible from the timeout
    handler (HIGH-5).
    """

    __slots__ = (
        "tool_call_seen",
        "tool_result_seen",
        "agent_swarm_call_id",
        "aggregate_text",
        "parent_text_parts",
        "child_terminal_states",
        "failed_ids",
        "agent_results",
    )

    def __init__(self) -> None:
        self.tool_call_seen: bool = False
        self.tool_result_seen: bool = False
        self.agent_swarm_call_id: str | None = None
        self.aggregate_text: str = ""
        self.parent_text_parts: list[str] = []
        # HIGH-3: Track unique children by child_id -> terminal status
        self.child_terminal_states: dict[str, str] = {}
        self.failed_ids: set[str] = set()
        self.agent_results: dict[str, AgentResult] = {}

    def get_partial_output(self) -> str:
        """Return best available output for timeout error details."""
        if self.aggregate_text:
            return self.aggregate_text
        return "".join(self.parent_text_parts)

    def build_result(
        self,
        task: CoordinationTask,
        kimi_model: str,
        concurrency: int,
        effective_timeout: float,
    ) -> CoordinationResult:
        """Build final CoordinationResult from collected state."""
        # Use aggregate text as canonical output; fall back to parent text
        output = (
            self.aggregate_text
            if self.aggregate_text
            else "".join(self.parent_text_parts)
        )

        total_children = len(self.child_terminal_states)

        return CoordinationResult(
            output=output,
            agent_results=self.agent_results,
            strategy_name="kimi-agent-swarm",
            metadata={
                "item_count": len(task.subtasks),
                "child_count": total_children,
                "succeeded": len(self.agent_results),
                "failed": len(self.failed_ids),
                "failed_agents": list(self.failed_ids),
                "concurrency": concurrency,
                "model": kimi_model,
                # MEDIUM-8: Report effective timeout, not self._timeout
                "timeout": effective_timeout,
            },
        )
