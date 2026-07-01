"""Claude Agent SDK adapter — subprocess-based agent execution via ``claude-agent-sdk``.

This adapter bridges the Beddel domain core to the Claude Agent SDK,
enabling agent-style interactions through the ``claude-agent-sdk`` Python
package's ``query()`` function.  It implements the
:class:`~beddel.domain.ports.IAgentAdapter` protocol via structural
subtyping (no explicit inheritance).

The Claude Agent SDK wraps the Claude Code CLI as a subprocess.  Each
call to ``query()`` creates a new session.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from typing import Any

from beddel.domain.errors import AgentError
from beddel.domain.models import AgentResult
from beddel.error_codes import (
    AGENT_EXECUTION_FAILED,
    AGENT_NOT_CONFIGURED,
    AGENT_STREAM_INTERRUPTED,
    AGENT_TIMEOUT,
)

__all__ = ["ClaudeAgentAdapter"]

_SANDBOX_MAP: dict[str, str] = {
    "read-only": "plan",
    "workspace-write": "acceptEdits",
    "danger-full-access": "bypassPermissions",
}


class ClaudeAgentAdapter:
    """Claude Agent SDK adapter using ``query()`` for subprocess execution.

    Implements the ``IAgentAdapter`` protocol structurally by exposing
    :meth:`execute` and :meth:`stream` with matching signatures.  All
    interaction with the Claude Agent SDK happens through the ``query()``
    async generator, which spawns the Claude Code CLI as a subprocess.

    Args:
        model: Default model identifier for Claude Agent SDK invocations.
        max_turns: Maximum number of agentic turns per session.
        timeout: Maximum execution time in seconds before the session
            is aborted.
        permission_mode: Default permission mode for the CLI subprocess.
        cwd: Optional working directory for the CLI subprocess.
        vertex_project: Optional Google Cloud project ID for Vertex AI.
        vertex_region: Optional Google Cloud region for Vertex AI.
        system_prompt: Optional system prompt passed in agent options.
        thinking: Optional thinking mode (``adaptive``, ``enabled``,
            or ``disabled``).
        effort: Optional effort level (``low``, ``medium``, or ``high``).
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4",
        max_turns: int = 25,
        timeout: int = 300,
        permission_mode: str = "bypassPermissions",
        cwd: str | None = None,
        vertex_project: str | None = None,
        vertex_region: str | None = None,
        system_prompt: str | None = None,
        thinking: str | None = None,
        effort: str | None = None,
    ) -> None:
        self._model = model
        self._max_turns = max_turns
        self._timeout = timeout
        self._permission_mode = permission_mode
        self._cwd = cwd
        self._vertex_project = vertex_project
        self._vertex_region = vertex_region
        self._system_prompt = system_prompt
        self._thinking = thinking
        self._effort = effort

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_options(
        self,
        prompt: str,
        *,
        sandbox: str | None = None,
        tools: list[str] | None = None,
        output_schema: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Build kwargs dict for ``ClaudeAgentOptions``.

        The dict is returned instead of the actual ``ClaudeAgentOptions``
        object because the SDK is an optional dependency and cannot be
        imported at module level.

        Args:
            prompt: The prompt text (unused in options, passed to ``query()``).
            sandbox: Sandbox access level mapped to a permission mode.
            tools: Optional list of allowed tool names.
            output_schema: Optional JSON Schema dict for structured output.
            model: Optional model override.

        Returns:
            A dict of keyword arguments for ``ClaudeAgentOptions()``.

        Raises:
            AgentError: ``BEDDEL-AGENT-701`` if ``sandbox`` is not a
                recognized value.
        """
        permission_mode = self._permission_mode
        if sandbox is not None:
            if sandbox not in _SANDBOX_MAP:
                raise AgentError(
                    code=AGENT_EXECUTION_FAILED,
                    message=f"Unsupported sandbox value: {sandbox!r}",
                    details={
                        "sandbox": sandbox,
                        "supported": list(_SANDBOX_MAP.keys()),
                    },
                )
            permission_mode = _SANDBOX_MAP[sandbox]

        opts: dict[str, Any] = {
            "model": model or self._model,
            "max_turns": self._max_turns,
            "permission_mode": permission_mode,
        }
        if self._cwd is not None:
            opts["cwd"] = self._cwd
        if tools is not None:
            opts["allowed_tools"] = tools
        if output_schema is not None:
            opts["output_format"] = {"type": "json_schema", "schema": output_schema}
        if self._system_prompt is not None:
            opts["system_prompt"] = self._system_prompt
        if self._thinking is not None:
            from claude_agent_sdk import ThinkingConfig  # type: ignore[import-not-found]

            _thinking_map = {
                "adaptive": ThinkingConfig.ADAPTIVE,
                "enabled": ThinkingConfig.ENABLED,
                "disabled": ThinkingConfig.DISABLED,
            }
            opts["thinking"] = _thinking_map[self._thinking]
        if self._effort is not None:
            from claude_agent_sdk import EffortLevel  # type: ignore[import-not-found]

            _effort_map = {
                "low": EffortLevel.LOW,
                "medium": EffortLevel.MEDIUM,
                "high": EffortLevel.HIGH,
            }
            opts["effort"] = _effort_map[self._effort]

        # Propagate Vertex AI environment variables to the subprocess.
        vertex_project = self._vertex_project or os.environ.get(
            "ANTHROPIC_VERTEX_PROJECT_ID"
        )
        if vertex_project:
            vertex_region = self._vertex_region or os.environ.get(
                "CLOUD_ML_REGION", "us-east5"
            )
            opts["env"] = {
                "CLAUDE_CODE_USE_VERTEX": "1",
                "ANTHROPIC_VERTEX_PROJECT_ID": vertex_project,
                "CLOUD_ML_REGION": vertex_region,
            }

        return opts

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
        """Execute a prompt via the Claude Agent SDK ``query()`` function.

        Imports ``claude_agent_sdk`` at runtime, builds options, iterates
        the async generator to collect text output, file changes, and
        usage/cost metadata, then returns a structured :class:`AgentResult`.

        Args:
            prompt: The instruction or task to send to the agent.
            model: Optional model override.  Falls back to the adapter's
                configured model when ``None``.
            sandbox: Sandbox access level mapped to a Claude permission mode.
            tools: Optional list of tool names the agent is allowed to use.
            output_schema: Optional JSON Schema dict for structured output.

        Returns:
            An :class:`AgentResult` with the agent's text output, changed
            files, usage metrics, and cost information.

        Raises:
            AgentError: ``BEDDEL-AGENT-700`` if ``claude-agent-sdk`` is not
                installed or the CLI is not found, ``BEDDEL-AGENT-701`` on
                process errors, ``BEDDEL-AGENT-702`` on timeout.
        """
        try:
            import claude_agent_sdk  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AgentError(
                code=AGENT_NOT_CONFIGURED,
                message="claude-agent-sdk is not installed",
                details={"package": "claude-agent-sdk"},
            ) from exc

        opts_dict = self._build_options(
            prompt,
            sandbox=sandbox,
            tools=tools,
            output_schema=output_schema,
            model=model,
        )
        options: Any = claude_agent_sdk.ClaudeAgentOptions(**opts_dict)

        text_parts: list[str] = []
        files_changed: list[str] = []
        usage: dict[str, Any] = {}
        cost_usd: float | None = None
        exit_code = 0

        try:
            async with asyncio.timeout(self._timeout):
                async for message in claude_agent_sdk.query(prompt=prompt, options=options):
                    msg_type = type(message).__name__

                    if msg_type == "AssistantMessage":
                        for block in message.content:
                            block_type = type(block).__name__
                            if block_type == "TextBlock":
                                text_parts.append(block.text)
                            elif block_type == "ToolUseBlock" and block.name in (
                                "Write",
                                "Edit",
                            ):
                                file_path = block.input.get("file_path", "")
                                if file_path:
                                    files_changed.append(file_path)

                    elif msg_type == "ResultMessage":
                        usage = getattr(message, "usage", {}) or {}
                        cost_usd = getattr(message, "cost_usd", None)
                        exit_code = getattr(message, "exit_code", 0) or 0

        except TimeoutError as exc:
            raise AgentError(
                code=AGENT_TIMEOUT,
                message=f"Claude Agent SDK timed out after {self._timeout}s",
                details={"timeout": self._timeout},
            ) from exc
        except claude_agent_sdk.CLINotFoundError as exc:
            raise AgentError(
                code=AGENT_NOT_CONFIGURED,
                message="Claude Code CLI not found",
                details={"error": str(exc)},
            ) from exc
        except claude_agent_sdk.ProcessError as exc:
            # The Claude Code CLI exits non-zero after is_error=True results
            # (e.g. read-only mode "success" exit). If we already collected
            # output text, treat it as a successful execution with the content
            # we gathered — the ProcessError is just a CLI exit-code artifact.
            if text_parts:
                logger.info(
                    "ProcessError after collecting %d text parts — treating as success",
                    len(text_parts),
                )
            else:
                stderr = getattr(exc, "stderr", str(exc))
                raise AgentError(
                    code=AGENT_EXECUTION_FAILED,
                    message="Claude Agent SDK process error",
                    details={"stderr": stderr},
                ) from exc

        usage_out: dict[str, Any] = dict(usage) if isinstance(usage, dict) else {}
        if cost_usd is not None:
            usage_out["cost_usd"] = cost_usd

        return AgentResult(
            exit_code=exit_code,
            output="\n".join(text_parts),
            events=[],
            files_changed=files_changed,
            usage=usage_out,
            agent_id="claude-agent-sdk",
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
        """Stream events from the Claude Agent SDK.

        Imports ``claude_agent_sdk`` at runtime, builds options, calls
        ``query()``, and yields structured event dicts as messages arrive.

        Event types:
            - ``"text"``: Text content from an ``AssistantMessage``.
            - ``"tool_use"``: Tool invocation from an ``AssistantMessage``.
            - ``"complete"``: Final result from a ``ResultMessage``.

        Args:
            prompt: The instruction or task to send to the agent.
            model: Optional model override.  Falls back to the adapter's
                configured model when ``None``.
            sandbox: Sandbox access level mapped to a Claude permission mode.
            tools: Optional list of tool names the agent is allowed to use.

        Yields:
            Structured event dicts from the agent execution stream.

        Raises:
            AgentError: ``BEDDEL-AGENT-700`` if ``claude-agent-sdk`` is not
                installed or the CLI is not found, ``BEDDEL-AGENT-703`` on
                timeout.
        """
        try:
            import claude_agent_sdk  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AgentError(
                code=AGENT_NOT_CONFIGURED,
                message="claude-agent-sdk is not installed",
                details={"package": "claude-agent-sdk"},
            ) from exc

        opts_dict = self._build_options(
            prompt,
            sandbox=sandbox,
            tools=tools,
            model=model,
        )
        options: Any = claude_agent_sdk.ClaudeAgentOptions(**opts_dict)

        try:
            async for message in claude_agent_sdk.query(prompt=prompt, options=options):
                msg_type = type(message).__name__

                if msg_type == "AssistantMessage":
                    for block in message.content:
                        block_type = type(block).__name__
                        if block_type == "TextBlock":
                            yield {"type": "text", "text": block.text}
                        elif block_type == "ToolUseBlock":
                            yield {
                                "type": "tool_use",
                                "name": block.name,
                                "input": block.input,
                                "id": block.id,
                            }

                elif msg_type == "ResultMessage":
                    yield {
                        "type": "complete",
                        "output": getattr(message, "text", ""),
                        "exit_code": getattr(message, "exit_code", 0) or 0,
                        "usage": getattr(message, "usage", {}) or {},
                        "cost_usd": getattr(message, "cost_usd", None),
                    }

        except claude_agent_sdk.CLINotFoundError as exc:
            raise AgentError(
                code=AGENT_NOT_CONFIGURED,
                message="Claude Code CLI not found",
                details={"error": str(exc)},
            ) from exc
        except TimeoutError as exc:
            raise AgentError(
                code=AGENT_STREAM_INTERRUPTED,
                message="Claude Agent SDK stream interrupted due to timeout",
                details={"timeout": self._timeout},
            ) from exc
