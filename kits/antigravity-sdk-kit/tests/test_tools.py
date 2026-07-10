"""Unit tests for antigravity tool implementations.

Tests cover all 7 tools: session_save, session_load, usage,
tool_exec, mcp_call, subagent, safety_check — both happy paths
and error paths. All tests use mocked adapter/session.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from beddel.domain.models import AgentResult

from beddel_antigravity_sdk.session import AntigravitySession, ToolContext
from beddel_antigravity_sdk.tools import (
    ANTIGRAVITY_EXECUTION_FAILED,
    ANTIGRAVITY_MCP_FAILED,
    ANTIGRAVITY_SAFETY_DENIED,
    antigravity_mcp_call,
    antigravity_safety_check,
    antigravity_session_load,
    antigravity_session_save,
    antigravity_subagent,
    antigravity_tool_exec,
    antigravity_usage,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_adapter() -> MagicMock:
    """Create a mock adapter with default configuration."""
    adapter = MagicMock()
    adapter._tools = []
    adapter._mcp_servers = None
    adapter._enable_subagents = False
    adapter._model = "gemini-2.5-flash"
    adapter._safety_policy = "allow"
    adapter._lifecycle_hooks = {}
    adapter._fire_hook = AsyncMock()
    return adapter


@pytest.fixture()
def ctx(mock_adapter: MagicMock, tmp_path: Path) -> ToolContext:
    """Create a ToolContext with a session backed by tmp_path."""
    session = AntigravitySession(
        state={},
        conversation_id="test-session",
        save_dir=str(tmp_path),
    )
    return ToolContext(session=session, adapter=mock_adapter)


# ---------------------------------------------------------------------------
# Test: antigravity_session_save happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_session_save_happy_path(ctx: ToolContext):
    """session_save persists state and returns path."""
    ctx.session.state = {"hello": "world"}

    result = await antigravity_session_save(ctx)

    assert result["status"] == "ok"
    assert result["conversation_id"] == "test-session"
    assert Path(result["path"]).exists()

    # Verify file content
    data = json.loads(Path(result["path"]).read_text())
    assert data["state"] == {"hello": "world"}


# ---------------------------------------------------------------------------
# Test: antigravity_session_load happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_session_load_happy_path(ctx: ToolContext, tmp_path: Path):
    """session_load reads saved state and updates context."""
    # Pre-create a session file
    payload = {
        "conversation_id": "existing-conv",
        "state": {"loaded": True},
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }
    (tmp_path / "existing-conv.json").write_text(json.dumps(payload))

    result = await antigravity_session_load(ctx, "existing-conv")

    assert result["status"] == "ok"
    assert result["state"] == {"loaded": True}
    assert result["conversation_id"] == "existing-conv"
    # Verify ctx.session was updated
    assert ctx.session.state == {"loaded": True}
    assert ctx.session.conversation_id == "existing-conv"


# ---------------------------------------------------------------------------
# Test: antigravity_session_load not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_session_load_not_found(ctx: ToolContext):
    """session_load returns error when conversation not found."""
    result = await antigravity_session_load(ctx, "missing-conv")

    assert result["status"] == "error"
    assert "missing-conv" in result["message"]


# ---------------------------------------------------------------------------
# Test: antigravity_usage returns metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_usage_returns_metrics(ctx: ToolContext):
    """usage returns current session token metrics."""
    ctx.session.usage = {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
    }

    result = await antigravity_usage(ctx)

    assert result["status"] == "ok"
    assert result["usage"]["prompt_tokens"] == 100
    assert result["usage"]["completion_tokens"] == 50
    assert result["usage"]["total_tokens"] == 150


# ---------------------------------------------------------------------------
# Test: antigravity_tool_exec happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_tool_exec_happy_path(ctx: ToolContext):
    """tool_exec invokes registered tool and returns result."""

    def my_tool(x: int = 0) -> str:
        return f"result_{x}"

    ctx.adapter._tools = [my_tool]

    result = await antigravity_tool_exec(ctx, "my_tool", {"x": 42})

    assert result["status"] == "ok"
    assert result["result"] == "result_42"


# ---------------------------------------------------------------------------
# Test: antigravity_tool_exec async tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_tool_exec_async_tool(ctx: ToolContext):
    """tool_exec handles async callables."""

    async def async_tool(msg: str = "") -> str:
        return f"async_{msg}"

    ctx.adapter._tools = [async_tool]

    result = await antigravity_tool_exec(ctx, "async_tool", {"msg": "hello"})

    assert result["status"] == "ok"
    assert result["result"] == "async_hello"


# ---------------------------------------------------------------------------
# Test: antigravity_tool_exec tool not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_tool_exec_not_found(ctx: ToolContext):
    """tool_exec returns error when tool not in registry."""
    ctx.adapter._tools = []

    result = await antigravity_tool_exec(ctx, "missing_tool", {})

    assert result["status"] == "error"
    assert result["code"] == ANTIGRAVITY_EXECUTION_FAILED
    assert "missing_tool" in result["message"]


# ---------------------------------------------------------------------------
# K5.4: antigravity_tool_exec safety enforcement (defense in depth — inner)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_tool_exec_denied_by_safety_policy(ctx: ToolContext):
    """tool_exec is blocked by deny_all policy — target tool never invoked."""
    target = MagicMock(return_value="should-not-run")
    target.__name__ = "risky_tool"
    ctx.adapter._tools = [target]
    ctx.adapter._safety_policy = "deny_all"

    result = await antigravity_tool_exec(ctx, "risky_tool", {})

    assert result["status"] == "error"
    assert result["code"] == ANTIGRAVITY_SAFETY_DENIED
    assert result["policy"] == "deny_all"
    target.assert_not_called()


@pytest.mark.asyncio()
async def test_tool_exec_allowed_by_safety_policy_proceeds(ctx: ToolContext):
    """tool_exec proceeds to normal invocation when safety policy allows."""

    def my_tool(x: int = 0) -> str:
        return f"result_{x}"

    ctx.adapter._tools = [my_tool]
    ctx.adapter._safety_policy = "allow"

    result = await antigravity_tool_exec(ctx, "my_tool", {"x": 7})

    assert result["status"] == "ok"
    assert result["result"] == "result_7"


@pytest.mark.asyncio()
async def test_tool_exec_workspace_only_denies_non_workspace_tool(ctx: ToolContext):
    """tool_exec denies a tool not in the workspace_only allowed set."""
    target = MagicMock(return_value="nope")
    target.__name__ = "exec_command"
    ctx.adapter._tools = [target]
    ctx.adapter._safety_policy = "workspace_only"

    result = await antigravity_tool_exec(ctx, "exec_command", {})

    assert result["status"] == "error"
    assert result["code"] == ANTIGRAVITY_SAFETY_DENIED
    target.assert_not_called()


@pytest.mark.asyncio()
async def test_tool_exec_fires_pre_tool_call_decide_hook(ctx: ToolContext):
    """tool_exec fires pre_tool_call_decide via adapter._fire_hook when configured."""

    def my_tool() -> str:
        return "ok"

    ctx.adapter._tools = [my_tool]
    ctx.adapter._safety_policy = "allow"
    ctx.adapter._lifecycle_hooks = {"pre_tool_call_decide": MagicMock()}

    await antigravity_tool_exec(ctx, "my_tool", {"a": 1})

    ctx.adapter._fire_hook.assert_called_once()
    call_args = ctx.adapter._fire_hook.call_args
    assert call_args[0][0] == "pre_tool_call_decide"
    assert call_args[0][1] == "my_tool"
    assert call_args[0][2] == {"a": 1}
    assert call_args[0][3] is True


@pytest.mark.asyncio()
async def test_tool_exec_no_hook_fired_when_not_configured(ctx: ToolContext):
    """tool_exec does not call _fire_hook when pre_tool_call_decide is unset."""

    def my_tool() -> str:
        return "ok"

    ctx.adapter._tools = [my_tool]
    ctx.adapter._safety_policy = "allow"
    ctx.adapter._lifecycle_hooks = {}

    await antigravity_tool_exec(ctx, "my_tool", {})

    ctx.adapter._fire_hook.assert_not_called()


# ---------------------------------------------------------------------------
# Test: antigravity_mcp_call — stdio happy path (K5.3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_mcp_call_stdio_happy_path(ctx: ToolContext):
    """mcp_call with stdio server builds McpStdioServer, calls tool, returns ok."""
    ctx.adapter._mcp_servers = [
        {
            "name": "fs-server",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-fs"],
            "env": {"HOME": "/tmp"},
        }
    ]

    # Mock google.adk.tools.mcp so McpStdioServer returns a mock server
    mock_server_instance = AsyncMock()
    mock_server_instance.call_tool = AsyncMock(
        return_value={"files": ["a.txt", "b.txt"]}
    )

    mock_mcp_mod = sys.modules["google.adk.tools.mcp"]
    mock_mcp_mod.McpStdioServer = MagicMock(return_value=mock_server_instance)
    mock_mcp_mod.McpSseServer = MagicMock()

    result = await antigravity_mcp_call(ctx, "fs-server", "list_files", {"dir": "/tmp"})

    assert result["status"] == "ok"
    assert result["result"] == {"files": ["a.txt", "b.txt"]}
    # Verify call_tool was invoked with correct args
    mock_server_instance.call_tool.assert_awaited_once_with(
        "list_files", {"dir": "/tmp"}
    )
    # Verify McpStdioServer was constructed with right kwargs
    mock_mcp_mod.McpStdioServer.assert_called_once_with(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-fs"],
        env={"HOME": "/tmp"},
    )
    # Verify session state was updated for traceability
    assert len(ctx.session.state["_mcp_calls"]) == 1
    assert ctx.session.state["_mcp_calls"][0]["server"] == "fs-server"
    assert ctx.session.state["_mcp_calls"][0]["tool"] == "list_files"


# ---------------------------------------------------------------------------
# Test: antigravity_mcp_call — sse happy path (K5.3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_mcp_call_sse_happy_path(ctx: ToolContext):
    """mcp_call with sse server builds McpSseServer, calls tool, returns ok."""
    ctx.adapter._mcp_servers = [
        {
            "name": "remote-search",
            "transport": "sse",
            "url": "http://localhost:8080/mcp",
            "headers": {"X-Api-Key": "secret"},
        }
    ]

    mock_server_instance = AsyncMock()
    mock_server_instance.call_tool = AsyncMock(
        return_value={"results": ["doc1", "doc2"]}
    )

    mock_mcp_mod = sys.modules["google.adk.tools.mcp"]
    mock_mcp_mod.McpStdioServer = MagicMock()
    mock_mcp_mod.McpSseServer = MagicMock(return_value=mock_server_instance)

    result = await antigravity_mcp_call(
        ctx, "remote-search", "search", {"query": "test"}
    )

    assert result["status"] == "ok"
    assert result["result"] == {"results": ["doc1", "doc2"]}
    mock_server_instance.call_tool.assert_awaited_once_with("search", {"query": "test"})
    mock_mcp_mod.McpSseServer.assert_called_once_with(
        url="http://localhost:8080/mcp",
        headers={"X-Api-Key": "secret"},
    )


# ---------------------------------------------------------------------------
# Test: antigravity_mcp_call — exception during ADK call (K5.3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_mcp_call_exception_returns_error(ctx: ToolContext):
    """mcp_call wraps exceptions into error dict, never raises."""
    ctx.adapter._mcp_servers = [
        {
            "name": "broken-server",
            "transport": "stdio",
            "command": "bad-cmd",
            "args": [],
            "env": {},
        }
    ]

    mock_server_instance = AsyncMock()
    mock_server_instance.call_tool = AsyncMock(
        side_effect=RuntimeError("Connection reset")
    )

    mock_mcp_mod = sys.modules["google.adk.tools.mcp"]
    mock_mcp_mod.McpStdioServer = MagicMock(return_value=mock_server_instance)

    result = await antigravity_mcp_call(ctx, "broken-server", "any_tool", {"x": 1})

    assert result["status"] == "error"
    assert result["code"] == ANTIGRAVITY_MCP_FAILED
    assert "Connection reset" in result["message"]
    # Verify traceability still recorded the attempt
    assert len(ctx.session.state["_mcp_calls"]) == 1


# ---------------------------------------------------------------------------
# Test: antigravity_mcp_call — google.adk.tools.mcp import fails (K5.3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_mcp_call_import_failure(ctx: ToolContext):
    """mcp_call returns error when google.adk.tools.mcp cannot be imported."""
    ctx.adapter._mcp_servers = [
        {
            "name": "fs-server",
            "transport": "stdio",
            "command": "npx",
            "args": [],
            "env": {},
        }
    ]

    # Simulate import failure by patching sys.modules
    with patch.dict(sys.modules, {"google.adk.tools.mcp": None}):
        result = await antigravity_mcp_call(
            ctx, "fs-server", "read_file", {"path": "/x"}
        )

    assert result["status"] == "error"
    assert result["code"] == ANTIGRAVITY_MCP_FAILED
    assert "google-adk is not installed" in result["message"]


# ---------------------------------------------------------------------------
# Test: antigravity_mcp_call server not configured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_mcp_call_no_servers(ctx: ToolContext):
    """mcp_call returns error when no MCP servers configured."""
    ctx.adapter._mcp_servers = None

    result = await antigravity_mcp_call(ctx, "any-server", "any-tool", {})

    assert result["status"] == "error"
    assert result["code"] == ANTIGRAVITY_MCP_FAILED
    assert "No MCP servers" in result["message"]


# ---------------------------------------------------------------------------
# Test: antigravity_mcp_call server not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_mcp_call_server_not_found(ctx: ToolContext):
    """mcp_call returns error when target server not in config."""
    ctx.adapter._mcp_servers = [
        {
            "name": "other-server",
            "transport": "sse",
            "url": "http://localhost:4000",
            "headers": {},
        }
    ]

    result = await antigravity_mcp_call(ctx, "missing-server", "tool", {})

    assert result["status"] == "error"
    assert result["code"] == ANTIGRAVITY_MCP_FAILED
    assert "missing-server" in result["message"]
    assert "available_servers" in result
    assert "other-server" in result["available_servers"]


# ---------------------------------------------------------------------------
# Test: antigravity_subagent happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_subagent_happy_path(ctx: ToolContext):
    """subagent delegates via adapter.execute() and returns output."""
    ctx.adapter._enable_subagents = True
    ctx.adapter.execute = AsyncMock(
        return_value=AgentResult(
            exit_code=0,
            output="Sub-agent completed task",
            events=[{"type": "text", "text": "Sub-agent completed task"}],
            files_changed=[],
            usage={},
            agent_id="antigravity-sdk",
        )
    )

    result = await antigravity_subagent(ctx, "helper-agent", "Do this task")

    assert result["status"] == "ok"
    assert result["output"] == "Sub-agent completed task"
    assert result["agent_name"] == "helper-agent"
    assert len(result["events"]) == 1
    # Verify session state records the call
    assert len(ctx.session.state["_subagent_calls"]) == 1


# ---------------------------------------------------------------------------
# Test: antigravity_subagent disabled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_subagent_disabled(ctx: ToolContext):
    """subagent returns error when enable_subagents is False."""
    ctx.adapter._enable_subagents = False

    result = await antigravity_subagent(ctx, "agent", "task")

    assert result["status"] == "error"
    assert "disabled" in result["message"]


# ---------------------------------------------------------------------------
# Test: antigravity_safety_check allow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_safety_check_allow_policy(ctx: ToolContext):
    """safety_check returns allowed=True when policy is 'allow'."""
    ctx.adapter._safety_policy = "allow"

    result = await antigravity_safety_check(ctx, "dangerous_tool", {"arg": "val"})

    assert result["status"] == "ok"
    assert result["allowed"] is True
    assert result["policy"] == "allow"
    assert result["reason"] is None


# ---------------------------------------------------------------------------
# Test: antigravity_safety_check deny_all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_safety_check_deny_all(ctx: ToolContext):
    """safety_check returns allowed=False when policy is 'deny_all'."""
    ctx.adapter._safety_policy = "deny_all"

    result = await antigravity_safety_check(ctx, "any_tool", {})

    assert result["status"] == "ok"
    assert result["allowed"] is False
    assert result["policy"] == "deny_all"
    assert "denies all" in result["reason"]


# ---------------------------------------------------------------------------
# Test: antigravity_safety_check workspace_only allows workspace tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_safety_check_workspace_allows(ctx: ToolContext):
    """safety_check allows workspace tools under workspace_only policy."""
    ctx.adapter._safety_policy = "workspace_only"

    result = await antigravity_safety_check(ctx, "read_file", {})

    assert result["status"] == "ok"
    assert result["allowed"] is True
    assert result["policy"] == "workspace_only"


# ---------------------------------------------------------------------------
# Test: antigravity_safety_check workspace_only denies non-workspace tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_safety_check_workspace_denies(ctx: ToolContext):
    """safety_check denies tools not in workspace set."""
    ctx.adapter._safety_policy = "workspace_only"

    result = await antigravity_safety_check(ctx, "exec_command", {})

    assert result["status"] == "ok"
    assert result["allowed"] is False
    assert "exec_command" in result["reason"]


# ---------------------------------------------------------------------------
# Test: unknown safety policy fails closed (H1 fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_safety_check_unknown_policy_fails_closed(ctx: ToolContext):
    """Unknown policy name denies by default (fail-closed)."""
    ctx.adapter._safety_policy = "nonexistent_policy"

    result = await antigravity_safety_check(ctx, "any_tool", {})

    assert result["status"] == "ok"
    assert result["allowed"] is False
    assert "Unknown" in result["reason"]


# ---------------------------------------------------------------------------
# Test: subagent accumulates usage (M2 fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_subagent_accumulates_usage(ctx: ToolContext):
    """subagent merges result.usage into session usage counters."""
    ctx.adapter._enable_subagents = True
    ctx.adapter.execute = AsyncMock(
        return_value=AgentResult(
            exit_code=0,
            output="Done",
            events=[],
            files_changed=[],
            usage={"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
            agent_id="antigravity-sdk",
        )
    )

    # Initial usage is zero
    assert ctx.session.usage["total_tokens"] == 0

    await antigravity_subagent(ctx, "helper", "task")

    # Usage should be accumulated
    assert ctx.session.usage["prompt_tokens"] == 50
    assert ctx.session.usage["completion_tokens"] == 25
    assert ctx.session.usage["total_tokens"] == 75
