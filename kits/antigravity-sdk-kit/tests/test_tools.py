"""Unit tests for antigravity tool implementations.

Tests cover all 7 tools: session_save, session_load, usage,
tool_exec, mcp_call, subagent, safety_check — both happy paths
and error paths. All tests use mocked adapter/session.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from beddel.domain.models import AgentResult

from beddel_antigravity_sdk.session import AntigravitySession, ToolContext
from beddel_antigravity_sdk.tools import (
    ANTIGRAVITY_EXECUTION_FAILED,
    ANTIGRAVITY_MCP_FAILED,
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
    adapter._safety_policy = "deny_all"
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
# Test: antigravity_mcp_call happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_mcp_call_happy_path(ctx: ToolContext):
    """mcp_call returns result when server is configured."""
    ctx.adapter._mcp_servers = [{"name": "my-server", "url": "http://localhost:3000"}]

    result = await antigravity_mcp_call(
        ctx, "my-server", "read_resource", {"uri": "/data"}
    )

    assert result["status"] == "ok"
    assert result["result"]["server"] == "my-server"
    assert result["result"]["tool"] == "read_resource"
    # Verify session state was updated
    assert len(ctx.session.state["_mcp_calls"]) == 1


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
        {"name": "other-server", "url": "http://localhost:4000"}
    ]

    result = await antigravity_mcp_call(ctx, "missing-server", "tool", {})

    assert result["status"] == "error"
    assert result["code"] == ANTIGRAVITY_MCP_FAILED
    assert "missing-server" in result["message"]


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
