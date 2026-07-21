"""Kimi K3 Agent Adapter — IAgentAdapter implementation.

Bridges the Beddel domain core to Moonshot's Kimi agent platform via
the ``kimi-agent-sdk`` Python package (Session API).  Implements the
:class:`~beddel.domain.ports.IAgentAdapter` protocol via structural
subtyping (no explicit inheritance).

Auth: ``MOONSHOT_API_KEY`` environment variable (required, fail-fast).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from beddel.domain.errors import AgentError
from beddel.domain.models import AgentResult

from beddel_agent_kimi.approval import KimiApprovalBridge
from beddel_agent_kimi.errors import (
    KIMI_AUTH_MISSING,
    KIMI_EXECUTION_FAILED,
    KIMI_INVALID_MODEL,
    KIMI_RATE_LIMITED,
    KIMI_SESSION_TIMEOUT,
)
from beddel_agent_kimi.session import (
    DEFAULT_TIMEOUT,
    build_kimi_config,
    get_api_key,
    resolve_model,
    resolve_sandbox,
)
from kaos.path import KaosPath

__all__ = ["KimiAgentAdapter"]

logger = logging.getLogger(__name__)

_SUPPORTED_SANDBOXES = ("read-only", "workspace-write", "danger-full-access")

# Rate-limit retry configuration
_MAX_RETRIES = 3
_BASE_BACKOFF_S = 2.0


class KimiAgentAdapter:
    """Kimi K3 agent adapter implementing IAgentAdapter structurally.

    Wraps the ``kimi-agent-sdk`` Session API to provide autonomous code
    agent execution with model tier routing and KAOS sandbox passthrough.

    Uses the real kimi-agent-sdk lifecycle:
      Session.create(work_dir=...) -> session.prompt(task) -> collect -> cleanup

    Args:
        timeout: Maximum session execution time in seconds. Default 300.
        api_key: Optional explicit API key. If None, reads from
            ``MOONSHOT_API_KEY`` environment variable.
        work_dir: Working directory for agent file operations. Defaults to cwd.

    Raises:
        AgentError: ``BEDDEL-AGENT-800`` if API key is not available.
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        api_key: str | None = None,
        work_dir: str | Path | None = None,
        approval_gate: Any | None = None,
        approval_mode: str = "manual",
        approval_timeout: float = 60.0,
        agent_file: Path | None = None,
    ) -> None:
        try:
            self._api_key = api_key if api_key else get_api_key()
        except ValueError as exc:
            raise AgentError(
                code=KIMI_AUTH_MISSING,
                message=str(exc),
                details={"env_var": "MOONSHOT_API_KEY"},
            ) from exc
        self._timeout = timeout
        self._work_dir = Path(work_dir) if work_dir else Path.cwd()
        self._approval_bridge = KimiApprovalBridge(
            gate=approval_gate,
            mode=approval_mode,
            timeout=approval_timeout,
        )
        self._agent_file = agent_file

    # ------------------------------------------------------------------
    # IAgentAdapter.execute
    # ------------------------------------------------------------------

    async def execute(
        self,
        prompt: str,
        *,
        model: str | None = None,
        sandbox: str = "read-only",
        tools: list[str] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Execute a prompt via the Kimi agent SDK Session API.

        Creates a new Session via Session.create(work_dir=...), submits the
        prompt via session.prompt(), collects streaming messages, and cleans
        up via the async context manager.

        Args:
            prompt: The instruction or task to send to the agent.
            model: Beddel model tier or raw Kimi model name.
            sandbox: Sandbox access level for the agent execution.
            tools: Optional tool names (currently passthrough).
            output_schema: Optional JSON Schema (currently unused).

        Returns:
            An :class:`AgentResult` with the agent's response.

        Raises:
            AgentError: On auth failure, timeout, invalid model/sandbox,
                rate limit, or SDK execution error.
        """
        # Validate sandbox
        if sandbox not in _SUPPORTED_SANDBOXES:
            raise AgentError(
                code=KIMI_EXECUTION_FAILED,
                message=f"Unsupported sandbox value: {sandbox!r}",
                details={
                    "sandbox": sandbox,
                    "supported": list(_SUPPORTED_SANDBOXES),
                },
            )

        # Resolve model tier
        try:
            kimi_model = resolve_model(model)
        except ValueError as exc:
            raise AgentError(
                code=KIMI_INVALID_MODEL,
                message=str(exc),
                details={"model": model},
            ) from exc

        # Resolve sandbox to KAOS mode (validates input; mode no longer passed to Session.create)
        try:
            resolve_sandbox(sandbox)
        except ValueError as exc:
            raise AgentError(
                code=KIMI_EXECUTION_FAILED,
                message=str(exc),
                details={"sandbox": sandbox},
            ) from exc

        # Execute via kimi-agent-sdk with retry on rate limit
        return await self._execute_with_retry(prompt, kimi_model)

    async def _execute_with_retry(
        self,
        prompt: str,
        kimi_model: str,
    ) -> AgentResult:
        """Execute session with exponential backoff on 429 rate limits."""
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                return await self._run_session(prompt, kimi_model)
            except AgentError as exc:
                if exc.code == KIMI_RATE_LIMITED and attempt < _MAX_RETRIES:
                    last_exc = exc
                    backoff = _BASE_BACKOFF_S * (2**attempt)
                    logger.warning(
                        "Kimi rate limited (attempt %d/%d), retrying in %.1fs",
                        attempt + 1,
                        _MAX_RETRIES,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise

        # Should not reach here, but satisfy type checker
        raise last_exc  # type: ignore[misc]

    async def _run_session(
        self,
        prompt: str,
        kimi_model: str,
    ) -> AgentResult:
        """Run a single session attempt with proper lifecycle."""
        try:
            from kimi_agent_sdk import (  # type: ignore[import-not-found]
                Config,
                Session,
            )
        except ImportError as exc:
            raise AgentError(
                code=KIMI_EXECUTION_FAILED,
                message=(
                    "kimi-agent-sdk is not installed. "
                    "Install with: pip install kimi-agent-sdk"
                ),
                details={"import_error": str(exc)},
            ) from exc

        try:
            config = Config(**build_kimi_config(self._api_key, kimi_model))

            # Real kimi-agent-sdk lifecycle:
            # Session.create() -> session.prompt() -> collect -> cleanup
            output_parts: list[str] = []

            create_kwargs: dict[str, Any] = {
                "work_dir": KaosPath(str(self._work_dir)),
                "config": config,
                "yolo": self._approval_bridge.should_use_yolo(),
            }
            if self._agent_file is not None:
                create_kwargs["agent_file"] = self._agent_file

            async with await Session.create(**create_kwargs) as session:
                try:
                    await asyncio.wait_for(
                        self._collect_messages(session, prompt, output_parts),
                        timeout=self._timeout,
                    )
                except asyncio.TimeoutError:
                    raise AgentError(
                        code=KIMI_SESSION_TIMEOUT,
                        message=f"Kimi session timed out after {self._timeout}s",
                        details={
                            "timeout": self._timeout,
                            "model": kimi_model,
                            "partial_output": "".join(output_parts),
                        },
                    )

        except AgentError:
            raise
        except Exception as exc:
            exc_str = str(exc)
            # Detect rate limit errors (HTTP 429)
            if "429" in exc_str or "rate" in exc_str.lower():
                raise AgentError(
                    code=KIMI_RATE_LIMITED,
                    message=f"Kimi rate limited: {exc}",
                    details={"error": exc_str, "model": kimi_model},
                ) from exc
            raise AgentError(
                code=KIMI_EXECUTION_FAILED,
                message=f"Kimi session execution failed: {exc}",
                details={"error": exc_str, "model": kimi_model},
            ) from exc

        return AgentResult(
            exit_code=0,
            output="".join(output_parts),
            events=[],
            files_changed=[],
            usage={},
            agent_id="kimi",
        )

    async def _collect_messages(
        self,
        session: Any,
        prompt: str,
        output_parts: list[str],
    ) -> None:
        """Collect messages from session.prompt() into output_parts."""
        async for wire_msg in session.prompt(prompt):
            # ApprovalRequest — agent needs permission
            if hasattr(wire_msg, "resolve"):
                await self._approval_bridge.handle_approval(wire_msg)
                continue
            # TextPart is the primary output message type
            if hasattr(wire_msg, "text"):
                output_parts.append(wire_msg.text)
            elif hasattr(wire_msg, "extract_text"):
                text = wire_msg.extract_text()
                if text:
                    output_parts.append(text)

    # ------------------------------------------------------------------
    # IAgentAdapter.stream
    # ------------------------------------------------------------------

    async def stream(
        self,
        prompt: str,
        *,
        model: str | None = None,
        sandbox: str = "read-only",
        tools: list[str] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream events from a Kimi agent session.

        Iterates over session.prompt() wire messages and yields structured
        event dicts for each message type (text, tool_call, approval, etc.).

        Args:
            prompt: The instruction or task to send to the agent.
            model: Beddel model tier or raw Kimi model name.
            sandbox: Sandbox access level for the agent execution.
            tools: Optional tool names.

        Yields:
            Event dicts with ``"type"`` key. Types include:
            - ``"text"``: incremental text output
            - ``"tool_call"``: agent invoked a tool
            - ``"approval_request"``: agent needs permission
            - ``"complete"``: final aggregated output

        Raises:
            AgentError: On timeout, auth, or SDK execution error.
        """
        # Validate inputs
        if sandbox not in _SUPPORTED_SANDBOXES:
            raise AgentError(
                code=KIMI_EXECUTION_FAILED,
                message=f"Unsupported sandbox value: {sandbox!r}",
                details={"sandbox": sandbox},
            )

        try:
            kimi_model = resolve_model(model)
        except ValueError as exc:
            raise AgentError(
                code=KIMI_INVALID_MODEL,
                message=str(exc),
                details={"model": model},
            ) from exc

        try:
            resolve_sandbox(sandbox)
        except ValueError as exc:
            raise AgentError(
                code=KIMI_EXECUTION_FAILED,
                message=str(exc),
                details={"sandbox": sandbox},
            ) from exc

        try:
            from kimi_agent_sdk import (  # type: ignore[import-not-found]
                Config,
                Session,
            )
        except ImportError as exc:
            raise AgentError(
                code=KIMI_EXECUTION_FAILED,
                message=(
                    "kimi-agent-sdk is not installed. "
                    "Install with: pip install kimi-agent-sdk"
                ),
                details={"import_error": str(exc)},
            ) from exc

        config = Config(**build_kimi_config(self._api_key, kimi_model))

        output_parts: list[str] = []

        try:
            create_kwargs: dict[str, Any] = {
                "work_dir": KaosPath(str(self._work_dir)),
                "config": config,
                "yolo": self._approval_bridge.should_use_yolo(),
            }
            if self._agent_file is not None:
                create_kwargs["agent_file"] = self._agent_file

            async with await Session.create(**create_kwargs) as session:
                async for wire_msg in session.prompt(prompt):
                    # ApprovalRequest — handle via bridge
                    if hasattr(wire_msg, "resolve"):
                        approved = await self._approval_bridge.handle_approval(wire_msg)
                        yield {
                            "type": "approval_request",
                            "message": getattr(wire_msg, "message", str(wire_msg)),
                            "approved": approved,
                        }
                        continue
                    event = self._wire_msg_to_event(wire_msg, output_parts)
                    if event:
                        yield event

        except AgentError:
            raise
        except Exception as exc:
            exc_str = str(exc)
            if "429" in exc_str or "rate" in exc_str.lower():
                raise AgentError(
                    code=KIMI_RATE_LIMITED,
                    message=f"Kimi rate limited: {exc}",
                    details={"error": exc_str},
                ) from exc
            raise AgentError(
                code=KIMI_EXECUTION_FAILED,
                message=f"Kimi stream failed: {exc}",
                details={"error": exc_str},
            ) from exc

        # Yield final complete event
        yield {
            "type": "complete",
            "output": "".join(output_parts),
            "exit_code": 0,
        }

    @staticmethod
    def _wire_msg_to_event(
        wire_msg: Any, output_parts: list[str]
    ) -> dict[str, Any] | None:
        """Convert a kimi-agent-sdk wire message to a Beddel event dict."""
        # TextPart — incremental text output
        if hasattr(wire_msg, "text"):
            output_parts.append(wire_msg.text)
            return {"type": "text", "content": wire_msg.text}

        # ApprovalRequest — agent needs permission
        if hasattr(wire_msg, "resolve"):
            return {
                "type": "approval_request",
                "message": str(wire_msg),
            }

        # Generic extract_text fallback
        if hasattr(wire_msg, "extract_text"):
            text = wire_msg.extract_text()
            if text:
                output_parts.append(text)
                return {"type": "text", "content": text}

        return None
