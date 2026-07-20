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
from typing import Any

from beddel.domain.errors import AgentError
from beddel.domain.models import AgentResult
from beddel.error_codes import (
    AGENT_EXECUTION_FAILED,
    AGENT_STREAM_INTERRUPTED,
    AGENT_TIMEOUT,
)

from beddel_agent_kimi.session import (
    DEFAULT_TIMEOUT,
    get_api_key,
    resolve_model,
    resolve_sandbox,
)

__all__ = ["KimiAgentAdapter"]

logger = logging.getLogger(__name__)

# Custom error codes for Kimi adapter (from architecture §40.6)
KIMI_AUTH_MISSING: str = "BEDDEL-AGENT-800"
KIMI_SESSION_TIMEOUT: str = "BEDDEL-AGENT-801"
KIMI_EXECUTION_FAILED: str = "BEDDEL-AGENT-803"
KIMI_INVALID_MODEL: str = "BEDDEL-AGENT-821"

_SUPPORTED_SANDBOXES = ("read-only", "workspace-write", "danger-full-access")


class KimiAgentAdapter:
    """Kimi K3 agent adapter implementing IAgentAdapter structurally.

    Wraps the ``kimi-agent-sdk`` Session API to provide autonomous code
    agent execution with model tier routing and KAOS sandbox passthrough.

    Args:
        timeout: Maximum session execution time in seconds. Default 300.
        api_key: Optional explicit API key. If None, reads from
            ``MOONSHOT_API_KEY`` environment variable.

    Raises:
        AgentError: ``BEDDEL-AGENT-800`` if API key is not available.
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        api_key: str | None = None,
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

        Creates a new Session, submits the prompt, and collects the
        final result. Each call is session-isolated (stateless between
        calls).

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
                or SDK execution error.
        """
        # Validate sandbox
        if sandbox not in _SUPPORTED_SANDBOXES:
            raise AgentError(
                code=KIMI_SESSION_TIMEOUT,
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

        # Resolve sandbox to KAOS mode
        try:
            kaos_mode = resolve_sandbox(sandbox)
        except ValueError as exc:
            raise AgentError(
                code=KIMI_SESSION_TIMEOUT,
                message=str(exc),
                details={"sandbox": sandbox},
            ) from exc

        # Execute via kimi-agent-sdk
        try:
            from kimi_agent_sdk import Session  # type: ignore[import-untyped]

            session = Session(
                api_key=self._api_key,
                model=kimi_model,
                sandbox_mode=kaos_mode,
            )
            # Run session in executor to handle sync SDK
            result_text = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, session.send, prompt
                ),
                timeout=self._timeout,
            )

        except asyncio.TimeoutError:
            raise AgentError(
                code=KIMI_SESSION_TIMEOUT,
                message=f"Kimi session timed out after {self._timeout}s",
                details={"timeout": self._timeout, "model": kimi_model},
            )
        except ImportError as exc:
            raise AgentError(
                code=KIMI_EXECUTION_FAILED,
                message="kimi-agent-sdk is not installed. Install with: pip install kimi-agent-sdk",
                details={"import_error": str(exc)},
            ) from exc
        except Exception as exc:
            raise AgentError(
                code=KIMI_EXECUTION_FAILED,
                message=f"Kimi session execution failed: {exc}",
                details={"error": str(exc), "model": kimi_model},
            ) from exc

        # Extract usage if available
        usage: dict[str, Any] = {}
        if hasattr(session, "usage") and session.usage:
            usage = dict(session.usage) if hasattr(session.usage, "__iter__") else {}

        return AgentResult(
            exit_code=0,
            output=result_text if isinstance(result_text, str) else str(result_text),
            events=[],
            files_changed=[],
            usage=usage,
            agent_id="kimi",
        )

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

        Since the kimi-agent-sdk Session API does not support incremental
        streaming in v1, this method calls :meth:`execute` internally and
        yields a single ``"complete"`` event with the full output.

        Args:
            prompt: The instruction or task to send to the agent.
            model: Beddel model tier or raw Kimi model name.
            sandbox: Sandbox access level for the agent execution.
            tools: Optional tool names.

        Yields:
            Event dicts with ``"type"`` key. Final event is ``"complete"``.

        Raises:
            AgentError: ``BEDDEL-AGENT-703`` if execution times out.
        """
        try:
            result = await self.execute(
                prompt,
                model=model,
                sandbox=sandbox,
                tools=tools,
            )
        except AgentError as exc:
            if exc.code == KIMI_SESSION_TIMEOUT:
                raise AgentError(
                    code=AGENT_STREAM_INTERRUPTED,
                    message="Kimi stream interrupted due to session timeout",
                    details=exc.details,
                ) from exc
            raise

        yield {
            "type": "complete",
            "output": result.output,
            "exit_code": result.exit_code,
        }
