"""Antigravity SDK tool implementations.

Seven tools callable from Beddel's ``tool`` primitive:

1. ``antigravity_tool_exec`` — execute a registered Antigravity custom tool
2. ``antigravity_mcp_call`` — call MCP tool via ADK's connected servers
3. ``antigravity_subagent`` — delegate task to an Antigravity sub-agent
4. ``antigravity_session_save`` — persist conversation state
5. ``antigravity_session_load`` — load previous conversation
6. ``antigravity_usage`` — retrieve token/cost metrics
7. ``antigravity_safety_check`` — evaluate tool invocation against safety policies

All tools receive a ``ToolContext`` as first argument and return
``dict[str, Any]`` with a ``status`` key ("ok" or "error").
"""

from __future__ import annotations

import logging
from typing import Any

from beddel.domain.errors import AgentError

from beddel_antigravity_sdk.session import (
    ANTIGRAVITY_MCP_FAILED,
    ANTIGRAVITY_SESSION_NOT_FOUND,
    AntigravitySession,
    AntigravityStateSync,
    ToolContext,
)

__all__ = [
    "antigravity_tool_exec",
    "antigravity_mcp_call",
    "antigravity_subagent",
    "antigravity_session_save",
    "antigravity_session_load",
    "antigravity_usage",
    "antigravity_safety_check",
]

logger = logging.getLogger(__name__)

# Error code constants (architecture §35.10)
ANTIGRAVITY_EXECUTION_FAILED: str = "BEDDEL-AGENT-751"
ANTIGRAVITY_SAFETY_DENIED: str = "BEDDEL-AGENT-753"

# Safety policy rules
_SAFETY_POLICIES: dict[str, set[str]] = {
    "deny_all": set(),  # No tools allowed
    "workspace_only": {"read_file", "write_file", "edit_file", "list_dir", "search"},
    "allow": None,  # type: ignore[dict-item]  # All tools allowed (None = no restriction)
}


# ---------------------------------------------------------------------------
# Tool 1: antigravity_tool_exec
# ---------------------------------------------------------------------------


async def antigravity_tool_exec(
    ctx: ToolContext,
    tool_name: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a registered Antigravity custom tool by name.

    Enforces the "Antigravity safety_policy (inner)" half of the
    defense-in-depth safety model (architecture §35.6): before looking up
    or invoking the target tool, the call is checked against the adapter's
    current safety policy via :func:`antigravity_safety_check`. If denied,
    the tool is never invoked. This makes the previously-advisory
    ``antigravity_safety_check`` tool enforcing for real invocations that
    go through this entry point.

    Looks up the tool in the adapter's registered tool list and invokes it.

    Args:
        ctx: Tool context with session and adapter reference.
        tool_name: Name of the registered tool to execute.
        args: Arguments to pass to the tool.

    Returns:
        Dict with ``status`` "ok" and ``result``, "error" with details if
        the tool is not found or fails, or "error" with
        ``code=ANTIGRAVITY_SAFETY_DENIED`` if the safety policy denies
        the call.
    """
    args = args or {}

    # Defense in depth (inner): check the safety policy before invoking.
    check = await antigravity_safety_check(ctx, tool_name, args)

    pre_tool_call_decide = ctx.adapter._lifecycle_hooks.get("pre_tool_call_decide")
    if pre_tool_call_decide is not None:
        await ctx.adapter._fire_hook(
            "pre_tool_call_decide", tool_name, args, check["allowed"]
        )

    if not check["allowed"]:
        return {
            "status": "error",
            "code": ANTIGRAVITY_SAFETY_DENIED,
            "message": (
                f"Tool {tool_name!r} denied by safety policy: {check['reason']}"
            ),
            "policy": check["policy"],
        }

    # Find tool in adapter's tool registry
    registered_tools = ctx.adapter._tools
    target_tool = None
    for tool in registered_tools:
        # Tools can be callables with a __name__ or objects with a .name attribute
        name = getattr(tool, "__name__", None) or getattr(tool, "name", None)
        if name == tool_name:
            target_tool = tool
            break

    if target_tool is None:
        return {
            "status": "error",
            "code": ANTIGRAVITY_EXECUTION_FAILED,
            "message": f"Tool not found in adapter registry: {tool_name!r}",
            "available_tools": [
                getattr(t, "__name__", None) or getattr(t, "name", "unknown")
                for t in registered_tools
            ],
        }

    try:
        # Invoke the tool — handle both sync and async callables
        import asyncio
        import inspect

        if inspect.iscoroutinefunction(target_tool):
            result = await target_tool(**args)
        elif callable(target_tool):
            result = await asyncio.to_thread(target_tool, **args)
        else:
            return {
                "status": "error",
                "code": ANTIGRAVITY_EXECUTION_FAILED,
                "message": f"Tool {tool_name!r} is not callable",
            }
    except Exception as exc:
        return {
            "status": "error",
            "code": ANTIGRAVITY_EXECUTION_FAILED,
            "message": f"Tool execution failed: {exc}",
        }

    return {"status": "ok", "result": result}


# ---------------------------------------------------------------------------
# Tool 2: antigravity_mcp_call
# ---------------------------------------------------------------------------


async def antigravity_mcp_call(
    ctx: ToolContext,
    server_name: str,
    tool_name: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call an MCP tool via Antigravity's connected MCP servers.

    Delegates to ADK's MCP infrastructure. Requires that the adapter
    was configured with ``mcp_servers`` containing the target server.

    Args:
        ctx: Tool context with session and adapter reference.
        server_name: Name/identifier of the MCP server to call.
        tool_name: Name of the tool on the MCP server.
        args: Arguments to pass to the MCP tool.

    Returns:
        Dict with ``status`` "ok" and ``result``, or "error" with details.
    """
    args = args or {}
    mcp_servers = ctx.adapter._mcp_servers

    if not mcp_servers:
        return {
            "status": "error",
            "code": ANTIGRAVITY_MCP_FAILED,
            "message": "No MCP servers configured on adapter",
        }

    # Find the target server configuration
    target_server = None
    for server_config in mcp_servers:
        name = (
            server_config.get("name", "")
            if isinstance(server_config, dict)
            else getattr(server_config, "name", "")
        )
        if name == server_name:
            target_server = server_config
            break

    if target_server is None:
        available = [
            s.get("name", "unknown")
            if isinstance(s, dict)
            else getattr(s, "name", "unknown")
            for s in mcp_servers
        ]
        return {
            "status": "error",
            "code": ANTIGRAVITY_MCP_FAILED,
            "message": f"MCP server not found: {server_name!r}",
            "available_servers": available,
        }

    # Store call in session state for traceability
    mcp_calls = ctx.session.state.setdefault("_mcp_calls", [])
    mcp_calls.append(
        {
            "server": server_name,
            "tool": tool_name,
            "args": args,
        }
    )

    # Build MCP server object and invoke tool via ADK
    try:
        from google.adk.tools.mcp import McpStdioServer, McpSseServer  # type: ignore[import-not-found]
    except ImportError:
        return {
            "status": "error",
            "code": ANTIGRAVITY_MCP_FAILED,
            "message": "google-adk is not installed",
        }

    transport = (
        target_server.get("transport", "") if isinstance(target_server, dict) else ""
    )

    try:
        if transport == "stdio":
            server = McpStdioServer(
                command=target_server.get("command", ""),
                args=target_server.get("args", []),
                env=target_server.get("env", {}),
            )
        elif transport == "sse":
            server = McpSseServer(
                url=target_server.get("url", ""),
                headers=target_server.get("headers", {}),
            )
        else:
            return {
                "status": "error",
                "code": ANTIGRAVITY_MCP_FAILED,
                "message": (
                    f"Unsupported MCP transport {transport!r} "
                    f"for server {server_name!r}"
                ),
            }

        # Invoke the tool on the MCP server
        result = await server.call_tool(tool_name, args)
    except Exception as exc:
        return {
            "status": "error",
            "code": ANTIGRAVITY_MCP_FAILED,
            "message": f"MCP call failed: {exc}",
        }

    return {"status": "ok", "result": result}


# ---------------------------------------------------------------------------
# Tool 3: antigravity_subagent
# ---------------------------------------------------------------------------


async def _run_named_sub_agent(child_agent: Any, prompt: str) -> dict[str, Any]:
    """Run a named sub-agent via a standalone ADK Runner session.

    Creates an ``InMemorySessionService`` and ``Runner`` scoped to the
    given child ``Agent``, sends the prompt as the user message, and
    collects text output + events.

    Args:
        child_agent: A pre-built ADK ``Agent`` instance.
        prompt: The user message to send to the child agent.

    Returns:
        Dict with ``output``, ``events``, and ``usage`` keys.
        Usage is best-effort ``{}`` for this standalone path.
    """
    try:
        from google.adk.runners import Runner  # type: ignore[import-not-found]
        from google.adk.sessions import InMemorySessionService  # type: ignore[import-not-found]
        from google.genai.types import Content, Part  # type: ignore[import-not-found]
    except ImportError:
        return {"output": "", "events": [], "usage": {}}

    session_service = InMemorySessionService()
    runner = Runner(
        agent=child_agent,
        app_name="beddel-antigravity-subagent",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="beddel-antigravity-subagent",
        user_id="beddel",
    )
    content = Content(parts=[Part(text=prompt)])

    text_parts: list[str] = []
    events: list[dict[str, Any]] = []

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

    return {"output": "\n".join(text_parts), "events": events, "usage": {}}


async def antigravity_subagent(
    ctx: ToolContext,
    agent_name: str,
    prompt: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Delegate a task to an Antigravity sub-agent.

    When ``agent_name`` matches a configured sub-agent in the adapter's
    ``_sub_agents`` list, builds that specific child agent and runs the
    prompt through a standalone ADK session. Otherwise, falls back to
    the adapter's top-level ``execute()`` method (existing behavior).

    Requires that the adapter was configured with ``enable_subagents=True``.

    Args:
        ctx: Tool context with session and adapter reference.
        agent_name: Name for the sub-agent (matched against configured
            sub-agent names).
        prompt: Task/instruction to delegate.
        model: Optional model override for the sub-agent.

    Returns:
        Dict with ``status`` "ok", ``output``, ``events``, and
        ``agent_name``.
    """
    if not ctx.adapter._enable_subagents:
        return {
            "status": "error",
            "code": ANTIGRAVITY_EXECUTION_FAILED,
            "message": "Sub-agent delegation disabled (enable_subagents=False)",
        }

    child_agent = ctx.adapter._build_sub_agent(agent_name)

    if child_agent is not None:
        result = await _run_named_sub_agent(child_agent, prompt)
    else:
        # Fallback: existing K5.2-era behavior — delegate to adapter.execute()
        try:
            exec_result = await ctx.adapter.execute(
                prompt=prompt,
                model=model or ctx.adapter._model,
                sandbox="workspace-write",
            )
        except AgentError as exc:
            return {
                "status": "error",
                "code": exc.code,
                "message": str(exc.message),
            }
        result = {
            "output": exec_result.output,
            "events": exec_result.events,
            "usage": exec_result.usage,
        }

    # Record in session state
    subagent_calls = ctx.session.state.setdefault("_subagent_calls", [])
    subagent_calls.append(
        {
            "agent_name": agent_name,
            "prompt": prompt,
            "output_length": len(result["output"]),
        }
    )

    # Accumulate usage metrics from sub-agent execution
    usage = result.get("usage") or {}
    ctx.session.usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
    ctx.session.usage["completion_tokens"] += usage.get("completion_tokens", 0)
    ctx.session.usage["total_tokens"] += usage.get("total_tokens", 0)

    return {
        "status": "ok",
        "output": result["output"],
        "events": result["events"],
        "agent_name": agent_name,
    }


# ---------------------------------------------------------------------------
# Tool 4: antigravity_session_save
# ---------------------------------------------------------------------------


async def antigravity_session_save(ctx: ToolContext) -> dict[str, Any]:
    """Persist conversation state to a state store or save_dir.

    When the adapter has a configured ``_state_store`` (non-None), uses
    ``AntigravityStateSync`` to persist via Beddel's ``IStateStore`` port.
    Otherwise falls back to file-based JSON serialization at ``save_dir``.

    Args:
        ctx: Tool context with session and adapter reference.

    Returns:
        Dict with ``status`` "ok", ``conversation_id``, and ``path``
        (``path`` is ``None`` when using the state-store-backed path).
    """
    state_store = getattr(ctx.adapter, "_state_store", None)
    if state_store is not None:
        key = ctx.session.conversation_id or "default"
        ctx.session.conversation_id = key
        sync = AntigravityStateSync(state_store)
        await sync.save_from_session(ctx.session, key)
        return {"status": "ok", "conversation_id": key, "path": None}

    try:
        path = ctx.session.save()
    except ValueError as exc:
        return {
            "status": "error",
            "code": ANTIGRAVITY_SESSION_NOT_FOUND,
            "message": str(exc),
        }

    return {
        "status": "ok",
        "conversation_id": ctx.session.conversation_id,
        "path": str(path),
    }


# ---------------------------------------------------------------------------
# Tool 5: antigravity_session_load
# ---------------------------------------------------------------------------


async def antigravity_session_load(
    ctx: ToolContext,
    conversation_id: str,
) -> dict[str, Any]:
    """Load a previous conversation by conversation_id.

    When the adapter has a configured ``_state_store`` (non-None), uses
    ``AntigravityStateSync`` to load via Beddel's ``IStateStore`` port.
    Otherwise falls back to file-based JSON deserialization from ``save_dir``.

    Args:
        ctx: Tool context with session and adapter reference.
        conversation_id: The conversation identifier to load.

    Returns:
        Dict with ``status`` "ok", ``state``, and ``conversation_id``.

    Raises:
        AgentError: BEDDEL-AGENT-755 if conversation not found (file-based path).
    """
    state_store = getattr(ctx.adapter, "_state_store", None)
    if state_store is not None:
        sync = AntigravityStateSync(state_store)
        await sync.load_into_session(ctx.session, conversation_id)
        ctx.session.conversation_id = conversation_id
        return {
            "status": "ok",
            "state": ctx.session.state,
            "conversation_id": conversation_id,
        }

    save_dir = ctx.session.save_dir
    if not save_dir:
        return {
            "status": "error",
            "code": ANTIGRAVITY_SESSION_NOT_FOUND,
            "message": "Cannot load session: save_dir is not configured",
        }

    try:
        loaded = AntigravitySession.load(conversation_id, save_dir)
    except AgentError as exc:
        return {
            "status": "error",
            "code": exc.code,
            "message": exc.message,
        }

    # Update current session with loaded state
    ctx.session.state = loaded.state
    ctx.session.conversation_id = loaded.conversation_id
    ctx.session.usage = loaded.usage

    return {
        "status": "ok",
        "state": loaded.state,
        "conversation_id": loaded.conversation_id,
    }


# ---------------------------------------------------------------------------
# Tool 6: antigravity_usage
# ---------------------------------------------------------------------------


async def antigravity_usage(ctx: ToolContext) -> dict[str, Any]:
    """Retrieve token usage and cost metrics from the session.

    Args:
        ctx: Tool context with session reference.

    Returns:
        Dict with ``status`` "ok" and ``usage`` metrics.
    """
    return {
        "status": "ok",
        "usage": ctx.session.usage,
    }


# ---------------------------------------------------------------------------
# Tool 7: antigravity_safety_check
# ---------------------------------------------------------------------------


async def antigravity_safety_check(
    ctx: ToolContext,
    tool_name: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a tool invocation against Antigravity safety policies.

    Checks whether the given tool is allowed under the adapter's current
    safety policy. Uses the defense-in-depth model where both Beddel's
    sandbox and Antigravity's safety_policy must allow the call.

    Args:
        ctx: Tool context with adapter reference.
        tool_name: Name of the tool to check.
        args: Arguments that would be passed (for context, not evaluated).

    Returns:
        Dict with ``status`` "ok", ``allowed`` bool, ``policy`` name,
        and optional ``reason`` if denied.
    """
    policy_name = ctx.adapter._safety_policy
    allowed_tools = _SAFETY_POLICIES.get(policy_name)

    # Unknown policy → fail-closed (deny all)
    if policy_name not in _SAFETY_POLICIES:
        return {
            "status": "ok",
            "allowed": False,
            "policy": policy_name,
            "reason": f"Unknown safety policy '{policy_name}' — denying by default",
        }

    # None means "allow all" (no restriction)
    if allowed_tools is None:
        return {
            "status": "ok",
            "allowed": True,
            "policy": policy_name,
            "reason": None,
        }

    # Empty set means "deny all"
    if not allowed_tools:
        return {
            "status": "ok",
            "allowed": False,
            "policy": policy_name,
            "reason": f"Policy '{policy_name}' denies all tool execution",
        }

    # Check if tool is in the allowed set
    if tool_name in allowed_tools:
        return {
            "status": "ok",
            "allowed": True,
            "policy": policy_name,
            "reason": None,
        }

    return {
        "status": "ok",
        "allowed": False,
        "policy": policy_name,
        "reason": f"Tool '{tool_name}' not in allowed set for policy '{policy_name}'",
    }
