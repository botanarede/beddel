"""Antigravity Agent SDK adapter — in-process agent execution via ``google-adk``.

This adapter bridges the Beddel domain core to the Google Antigravity SDK
(``google-adk``), enabling agent-style interactions through Google's ADK
``Runner.run_async()`` async generator.  It implements the
:class:`~beddel.domain.ports.IAgentAdapter` protocol via structural
subtyping (no explicit inheritance).

Unlike the Claude adapter which spawns a subprocess, the Antigravity SDK
runs in-process as a native async Python library.
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
    AGENT_NOT_CONFIGURED,
    AGENT_STREAM_INTERRUPTED,
    AGENT_TIMEOUT,
)

from beddel_antigravity_sdk.session import ANTIGRAVITY_MCP_FAILED

__all__ = ["AntigravityAgentAdapter"]

logger = logging.getLogger(__name__)

_SANDBOX_MAP: dict[str, str] = {
    "read-only": "deny_all",
    "workspace-write": "workspace_only",
    "danger-full-access": "allow",
}


class AntigravityAgentAdapter:
    """Antigravity SDK adapter using ``Runner.run_async()`` for in-process execution.

    Implements the ``IAgentAdapter`` protocol structurally by exposing
    :meth:`execute` and :meth:`stream` with matching signatures.  All
    interaction with the Google ADK happens through ``Runner.run_async()``,
    which is a native async generator yielding events in-process.

    Note: The ``sandbox`` parameter in :meth:`execute` and :meth:`stream`
    **overrides** the ``safety_policy`` set at construction time. This
    matches the behavior of the Claude adapter where ``sandbox`` is the
    caller's explicit intent for a specific invocation.

    Args:
        model: Default model identifier for Antigravity SDK invocations.
        timeout: Maximum execution time in seconds before the session
            is aborted.
        safety_policy: Default safety policy (used when sandbox is None).
        mcp_servers: Optional list of MCP server configurations.
        tools: Optional list of tool objects to pass to the Agent.
        enable_subagents: Whether to enable sub-agent spawning.
        save_dir: Optional directory for agent session persistence.
            (Wired in Story K5.5 — currently stored but not passed to Runner.)
        skills_paths: Optional list of skill file paths to load.
            (Wired in Story K5.5 — currently stored but not passed to Agent.)
        lifecycle_hooks: Optional lifecycle hook callbacks. Recognized keys:
            ``on_session_start``, ``on_session_end``, ``pre_tool_call_decide``,
            ``post_tool_call``, ``on_tool_error``. Each value is a callable
            (sync or async) invoked defensively by :meth:`_fire_hook` —
            exceptions are logged and never propagate into agent execution.
        tracer: Optional ``ITracer``-shaped instance (duck-typed, not
            imported at module level) used to emit ``"antigravity.execute"``
            / ``"antigravity.stream"`` spans around each run. Tracing
            failures are logged and never propagate (mirrors the domain
            executor's defensive tracing pattern).
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        timeout: int = 300,
        safety_policy: str = "deny_all",
        mcp_servers: list[Any] | None = None,
        tools: list[Any] | None = None,
        enable_subagents: bool = False,
        save_dir: str | None = None,
        skills_paths: list[str] | None = None,
        lifecycle_hooks: dict[str, Any] | None = None,
        tracer: Any | None = None,
    ) -> None:
        self._model = model
        self._timeout = timeout
        self._safety_policy = safety_policy
        self._mcp_servers = mcp_servers
        self._tools = tools or []
        self._enable_subagents = enable_subagents
        self._save_dir = save_dir
        self._skills_paths = skills_paths or []
        self._lifecycle_hooks = lifecycle_hooks or {}
        self._tracer = tracer

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_config(
        self,
        *,
        sandbox: str | None = None,
        tools: list[Any] | None = None,
        model: str | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build configuration dict for the Agent and Runner setup.

        Maps the ``sandbox`` parameter to a safety policy and assembles
        configuration for agent creation.  When ``sandbox`` is provided,
        it overrides the adapter's default ``safety_policy`` — this is
        the caller's explicit intent for this specific invocation.

        Args:
            sandbox: Sandbox access level mapped to a safety policy.
                Overrides constructor ``safety_policy`` when set.
            tools: Optional list of tool overrides.
            model: Optional model override.
            output_schema: Optional JSON Schema dict for structured output.
                Note: ADK requires a Pydantic model, not raw JSON Schema.
                This field is stored for future conversion (Story K5.5).

        Returns:
            A dict with keys: ``model``, ``safety_policy``, ``tools``,
            and optionally ``output_schema``.

        Raises:
            AgentError: ``BEDDEL-AGENT-701`` if ``sandbox`` is not a
                recognized value.
        """
        safety_policy = self._safety_policy
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
            safety_policy = _SANDBOX_MAP[sandbox]
            if sandbox == "danger-full-access":
                logger.warning(
                    "antigravity-sdk: sandbox='danger-full-access' grants unrestricted "
                    "tool execution. Ensure this is intentional."
                )

        config: dict[str, Any] = {
            "model": model or self._model,
            "safety_policy": safety_policy,
            "tools": tools if tools is not None else self._tools,
        }

        if output_schema is not None:
            config["output_schema"] = output_schema

        return config

    def _build_mcp_servers(self) -> list[Any]:
        """Build MCP server objects from adapter's ``_mcp_servers`` config list.

        Lazily imports ``McpStdioServer`` and ``McpSseServer`` from
        ``google.adk.tools.mcp`` and converts each config dict into a real
        server object based on the ``"transport"`` key.

        Returns:
            A list of ``McpStdioServer`` / ``McpSseServer`` instances ready
            to be passed to the ADK ``Agent(tools=[...])``.  Returns an
            empty list if there are no MCP server configs or if the
            ``google.adk.tools.mcp`` import fails.

        Raises:
            AgentError: ``BEDDEL-AGENT-754`` if a config entry has an
                unrecognized ``"transport"`` value.
        """
        if not self._mcp_servers:
            return []

        try:
            from google.adk.tools.mcp import McpSseServer, McpStdioServer  # type: ignore[import-not-found]
        except ImportError:
            logger.warning(
                "google.adk.tools.mcp is not available — "
                "MCP server configuration will be skipped for this run"
            )
            return []

        servers: list[Any] = []
        for server_config in self._mcp_servers:
            transport = server_config.get("transport", "")
            name = server_config.get("name", "<unnamed>")

            if transport == "stdio":
                servers.append(
                    McpStdioServer(
                        command=server_config.get("command", ""),
                        args=server_config.get("args", []),
                        env=server_config.get("env", {}),
                    )
                )
            elif transport == "sse":
                servers.append(
                    McpSseServer(
                        url=server_config.get("url", ""),
                        headers=server_config.get("headers", {}),
                    )
                )
            else:
                raise AgentError(
                    code=ANTIGRAVITY_MCP_FAILED,
                    message=f"Unrecognized MCP transport: {transport!r}",
                    details={
                        "transport": transport,
                        "server_name": name,
                        "supported": ["stdio", "sse"],
                    },
                )

        return servers

    def _get_mcp_server_config(self, name: str) -> dict[str, Any] | None:
        """Look up an MCP server config dict by its ``"name"`` key.

        Args:
            name: The server name to look up.

        Returns:
            The config dict if found, or ``None`` if not found.
        """
        if not self._mcp_servers:
            return None
        for server_config in self._mcp_servers:
            if isinstance(server_config, dict) and server_config.get("name") == name:
                return server_config
        return None

    def _start_span(
        self, name: str, attributes: dict[str, Any] | None = None
    ) -> Any | None:
        """Start a trace span defensively.

        Mirrors the domain executor's defensive tracing pattern
        (``src/beddel-py/src/beddel/domain/executor.py``): tracing is
        best-effort observability and must never break agent execution.

        Args:
            name: Span name (e.g. ``"antigravity.execute"``).
            attributes: Optional key-value attributes to attach to the span.

        Returns:
            The opaque span handle returned by the tracer, or ``None`` if
            no tracer is configured or starting the span failed.
        """
        if self._tracer is None:
            return None
        try:
            return self._tracer.start_span(name, attributes)
        except Exception:
            logger.warning("Tracing start_span failed (ignored)", exc_info=True)
            return None

    def _end_span(
        self, span: Any | None, attributes: dict[str, Any] | None = None
    ) -> None:
        """End a trace span defensively.

        No-op if no tracer is configured or ``span`` is ``None`` (e.g.
        because :meth:`_start_span` failed or returned early).

        Args:
            span: The opaque span handle returned by :meth:`_start_span`.
            attributes: Optional key-value attributes to attach before closing.
        """
        if self._tracer is None or span is None:
            return
        try:
            self._tracer.end_span(span, attributes)
        except Exception:
            logger.warning("Tracing end_span failed (ignored)", exc_info=True)

    def _extract_usage(self, agent: Any) -> dict[str, int]:
        """Defensively extract token usage from ``agent.conversation.total_usage``.

        The Google ADK's ``Agent``/conversation object model may not expose
        this shape in all versions — attribute access is fully defensive
        (``getattr`` chains) and never raises.

        Args:
            agent: The ADK ``Agent`` instance used for this run.

        Returns:
            A dict with ``prompt_tokens``, ``completion_tokens``, and
            ``total_tokens`` keys, or an empty dict if the usage data is
            unavailable or malformed.
        """
        conversation = getattr(agent, "conversation", None)
        total_usage = (
            getattr(conversation, "total_usage", None)
            if conversation is not None
            else None
        )
        if total_usage is None:
            return {}
        return {
            "prompt_tokens": getattr(total_usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(total_usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(total_usage, "total_tokens", 0) or 0,
        }

    async def _fire_hook(self, name: str, *args: Any, **kwargs: Any) -> None:
        """Fire a lifecycle hook callback by name, defensively.

        Looks up ``self._lifecycle_hooks.get(name)``. If configured, calls
        it — awaiting directly if it is a coroutine function, otherwise
        running it in a thread (mirrors the sync/async dispatch pattern
        used for tool callables in ``tools.py::antigravity_tool_exec``).
        Exceptions are logged and swallowed: lifecycle hooks must never
        break agent execution.

        Args:
            name: The hook key to look up (e.g. ``"on_session_start"``).
            *args: Positional arguments forwarded to the hook callable.
            **kwargs: Keyword arguments forwarded to the hook callable.
        """
        hook = self._lifecycle_hooks.get(name)
        if hook is None:
            return
        try:
            import inspect

            if inspect.iscoroutinefunction(hook):
                await hook(*args, **kwargs)
            elif callable(hook):
                await asyncio.to_thread(hook, *args, **kwargs)
        except Exception:
            logger.warning("Lifecycle hook %r failed (ignored)", name, exc_info=True)

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
        """Execute a prompt via the Antigravity SDK ``Runner.run_async()``.

        Imports ``google.adk`` at runtime, creates an Agent and Runner,
        iterates the async generator to collect text output, tool usage,
        and events, then returns a structured :class:`AgentResult`.

        The ``prompt`` is sent as the user message to the agent. The Agent
        is created with a generic instruction; the prompt drives behavior
        via the user message channel (correct ADK semantics).

        Args:
            prompt: The instruction or task to send to the agent.
            model: Optional model override.  Falls back to the adapter's
                configured model when ``None``.
            sandbox: Sandbox access level mapped to a safety policy.
            tools: Optional list of tool names the agent is allowed to use.
            output_schema: Optional JSON Schema dict for structured output.
                Note: Currently stored but not converted to Pydantic model.
                Full output_schema support is planned for Story K5.5.

        Returns:
            An :class:`AgentResult` with the agent's text output, changed
            files, usage metrics, and event log.

        Raises:
            AgentError: ``BEDDEL-AGENT-700`` if ``google-adk`` is not
                installed, ``BEDDEL-AGENT-701`` on execution errors,
                ``BEDDEL-AGENT-702`` on timeout.
        """
        try:
            from google.adk.agents import Agent  # type: ignore[import-not-found]
            from google.adk.runners import Runner  # type: ignore[import-not-found]
            from google.adk.sessions import InMemorySessionService  # type: ignore[import-not-found]
            from google.genai.types import Content, Part  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AgentError(
                code=AGENT_NOT_CONFIGURED,
                message="google-adk is not installed",
                details={"package": "google-adk"},
            ) from exc

        config = self._build_config(
            sandbox=sandbox,
            tools=tools,
            model=model,
            output_schema=output_schema,
        )

        # Build agent — prompt is the USER MESSAGE, not the instruction.
        # ADK semantics: instruction = system prompt, new_message = user input.
        agent_kwargs: dict[str, Any] = {
            "name": "beddel-antigravity",
            "model": config["model"],
            "instruction": "You are a helpful assistant executing tasks for the Beddel workflow engine.",
        }
        if config["tools"]:
            agent_kwargs["tools"] = config["tools"]

        # Append MCP server objects (ADK manages their lifecycle)
        mcp_servers = self._build_mcp_servers()
        if mcp_servers:
            agent_kwargs.setdefault("tools", [])
            if not isinstance(agent_kwargs["tools"], list):
                agent_kwargs["tools"] = list(agent_kwargs["tools"])
            agent_kwargs["tools"].extend(mcp_servers)

        agent = Agent(**agent_kwargs)
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="beddel-antigravity",
            session_service=session_service,
        )

        text_parts: list[str] = []
        events: list[dict[str, Any]] = []
        files_changed: list[str] = []
        exit_code = 0
        session: Any = None
        span = self._start_span(
            "antigravity.execute",
            {"model": config["model"], "sandbox": sandbox},
        )

        try:
            session = await session_service.create_session(
                app_name="beddel-antigravity",
                user_id="beddel",
            )
            await self._fire_hook("on_session_start", session_id=session.id)
            content = Content(parts=[Part(text=prompt)])

            async with asyncio.timeout(self._timeout):
                async for event in runner.run_async(
                    user_id="beddel",
                    session_id=session.id,
                    new_message=content,
                ):
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                text_parts.append(part.text)
                                events.append(
                                    {
                                        "type": "text",
                                        "text": part.text,
                                        "author": getattr(event, "author", ""),
                                    }
                                )
                            elif hasattr(part, "function_call") and part.function_call:
                                fc = part.function_call
                                tool_name = getattr(fc, "name", "")
                                tool_args = getattr(fc, "args", {})
                                events.append(
                                    {
                                        "type": "tool_use",
                                        "name": tool_name,
                                        "input": tool_args,
                                    }
                                )
                                await self._fire_hook(
                                    "post_tool_call",
                                    tool_name=tool_name,
                                    input=tool_args,
                                )
                                # Track file changes from tool calls
                                if tool_name in (
                                    "write_file",
                                    "edit_file",
                                    "create_file",
                                ):
                                    file_path = tool_args.get(
                                        "file_path", ""
                                    ) or tool_args.get("path", "")
                                    if file_path:
                                        files_changed.append(file_path)

        except TimeoutError as exc:
            raise AgentError(
                code=AGENT_TIMEOUT,
                message=f"Antigravity SDK timed out after {self._timeout}s",
                details={"timeout": self._timeout},
            ) from exc
        except AgentError:
            raise
        except Exception as exc:
            await self._fire_hook("on_tool_error", error=str(exc))
            raise AgentError(
                code=AGENT_EXECUTION_FAILED,
                message="Antigravity SDK execution error",
                details={"error": str(exc)},
            ) from exc
        finally:
            usage = self._extract_usage(agent)
            self._end_span(span, {"usage": usage, "exit_code": exit_code})
            await self._fire_hook(
                "on_session_end",
                session_id=getattr(session, "id", None),
                usage=usage,
            )

        return AgentResult(
            exit_code=exit_code,
            output="\n".join(text_parts),
            events=events,
            files_changed=files_changed,
            usage=self._extract_usage(agent),
            agent_id="antigravity-sdk",
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
        """Stream events from the Antigravity SDK.

        Imports ``google.adk`` at runtime, creates an Agent and Runner,
        calls ``run_async()``, and yields structured event dicts as
        events arrive from the in-process agent execution.

        Event types:
            - ``"text"``: Text content from an agent response part.
            - ``"tool_use"``: Tool invocation from a function_call part.
            - ``"complete"``: Final event signaling execution is done.

        Args:
            prompt: The instruction or task to send to the agent.
            model: Optional model override.  Falls back to the adapter's
                configured model when ``None``.
            sandbox: Sandbox access level mapped to a safety policy.
            tools: Optional list of tool names the agent is allowed to use.

        Yields:
            Structured event dicts from the agent execution stream.

        Raises:
            AgentError: ``BEDDEL-AGENT-700`` if ``google-adk`` is not
                installed, ``BEDDEL-AGENT-703`` on stream interruption.
        """
        try:
            from google.adk.agents import Agent  # type: ignore[import-not-found]
            from google.adk.runners import Runner  # type: ignore[import-not-found]
            from google.adk.sessions import InMemorySessionService  # type: ignore[import-not-found]
            from google.genai.types import Content, Part  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AgentError(
                code=AGENT_NOT_CONFIGURED,
                message="google-adk is not installed",
                details={"package": "google-adk"},
            ) from exc

        config = self._build_config(
            sandbox=sandbox,
            tools=tools,
            model=model,
        )

        # Build agent — prompt is user message, not instruction
        agent_kwargs: dict[str, Any] = {
            "name": "beddel-antigravity",
            "model": config["model"],
            "instruction": "You are a helpful assistant executing tasks for the Beddel workflow engine.",
        }
        if config["tools"]:
            agent_kwargs["tools"] = config["tools"]

        # Append MCP server objects (ADK manages their lifecycle)
        mcp_servers = self._build_mcp_servers()
        if mcp_servers:
            agent_kwargs.setdefault("tools", [])
            if not isinstance(agent_kwargs["tools"], list):
                agent_kwargs["tools"] = list(agent_kwargs["tools"])
            agent_kwargs["tools"].extend(mcp_servers)

        agent = Agent(**agent_kwargs)
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="beddel-antigravity",
            session_service=session_service,
        )

        text_parts: list[str] = []
        session: Any = None
        span = self._start_span(
            "antigravity.stream",
            {"model": config["model"], "sandbox": sandbox},
        )

        try:
            session = await session_service.create_session(
                app_name="beddel-antigravity",
                user_id="beddel",
            )
            await self._fire_hook("on_session_start", session_id=session.id)
            content = Content(parts=[Part(text=prompt)])

            async with asyncio.timeout(self._timeout):
                async for event in runner.run_async(
                    user_id="beddel",
                    session_id=session.id,
                    new_message=content,
                ):
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                text_parts.append(part.text)
                                yield {"type": "text", "text": part.text}
                            elif hasattr(part, "function_call") and part.function_call:
                                fc = part.function_call
                                tool_name = getattr(fc, "name", "")
                                tool_args = getattr(fc, "args", {})
                                yield {
                                    "type": "tool_use",
                                    "name": tool_name,
                                    "input": tool_args,
                                }
                                await self._fire_hook(
                                    "post_tool_call",
                                    tool_name=tool_name,
                                    input=tool_args,
                                )

        except TimeoutError as exc:
            raise AgentError(
                code=AGENT_STREAM_INTERRUPTED,
                message=f"Antigravity SDK stream interrupted after {self._timeout}s",
                details={"timeout": self._timeout},
            ) from exc
        except AgentError:
            raise
        except Exception as exc:
            await self._fire_hook("on_tool_error", error=str(exc))
            raise AgentError(
                code=AGENT_STREAM_INTERRUPTED,
                message="Antigravity SDK stream interrupted",
                details={"error": str(exc)},
            ) from exc
        finally:
            usage = self._extract_usage(agent)
            self._end_span(span, {"usage": usage})
            await self._fire_hook(
                "on_session_end",
                session_id=getattr(session, "id", None),
                usage=usage,
            )

        # Emit final completion event
        yield {
            "type": "complete",
            "output": "\n".join(text_parts),
            "exit_code": 0,
            "usage": self._extract_usage(agent),
        }
