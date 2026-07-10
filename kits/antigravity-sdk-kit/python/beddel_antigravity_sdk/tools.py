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

    Looks up the tool in the adapter's registered tool list and invokes it.

    Args:
        ctx: Tool context with session and adapter reference.
        tool_name: Name of the registered tool to execute.
        args: Arguments to pass to the tool.

    Returns:
        Dict with ``status`` "ok" and ``result``, or "error" with details.
    """
    args = args or {}

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


async def antigravity_subagent(
    ctx: ToolContext,
    agent_name: str,
    prompt: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Delegate a task to an Antigravity sub-agent.

    Creates a sub-agent execution via the ADK Runner. Requires that
    the adapter was configured with ``enable_subagents=True``.

    Args:
        ctx: Tool context with session and adapter reference.
        agent_name: Name for the sub-agent.
        prompt: Task/instruction to delegate.
        model: Optional model override for the sub-agent.

    Returns:
        Dict with ``status`` "ok", ``output``, and ``events``.
    """
    if not ctx.adapter._enable_subagents:
        return {
            "status": "error",
            "code": ANTIGRAVITY_EXECUTION_FAILED,
            "message": "Sub-agent delegation disabled (enable_subagents=False)",
        }

    # Execute via adapter (re-uses the same execution path)
    try:
        result = await ctx.adapter.execute(
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

    # Record in session state
    subagent_calls = ctx.session.state.setdefault("_subagent_calls", [])
    subagent_calls.append(
        {
            "agent_name": agent_name,
            "prompt": prompt,
            "output_length": len(result.output),
        }
    )

    # Accumulate usage metrics from sub-agent execution
    if result.usage:
        ctx.session.usage["prompt_tokens"] += result.usage.get("prompt_tokens", 0)
        ctx.session.usage["completion_tokens"] += result.usage.get(
            "completion_tokens", 0
        )
        ctx.session.usage["total_tokens"] += result.usage.get("total_tokens", 0)

    return {
        "status": "ok",
        "output": result.output,
        "events": result.events,
        "agent_name": agent_name,
    }


# ---------------------------------------------------------------------------
# Tool 4: antigravity_session_save
# ---------------------------------------------------------------------------


async def antigravity_session_save(ctx: ToolContext) -> dict[str, Any]:
    """Persist conversation state to save_dir.

    Serializes the current session state (including all accumulated
    tool call history) to a JSON file.

    Args:
        ctx: Tool context with session reference.

    Returns:
        Dict with ``status`` "ok", ``conversation_id``, and ``path``.
    """
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

    Deserializes session state from the save_dir and updates the
    current context session.

    Args:
        ctx: Tool context with session reference.
        conversation_id: The conversation identifier to load.

    Returns:
        Dict with ``status`` "ok", ``state``, and ``conversation_id``.

    Raises:
        AgentError: BEDDEL-AGENT-755 if conversation not found.
    """
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
