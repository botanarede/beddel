"""Unit tests for beddel_agentrq_approval adapter kit.

Covers all AC 11 scenarios: auto-approve by policy, task creation via MCP mock,
status polling with all mapped statuses + unknown fallback, client-side timeout
derivation, connection lifecycle, and MCP error handling.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, patch

import pytest

from beddel.domain.models import ApprovalPolicy, ApprovalResult, ApprovalStatus, RiskLevel
from beddel_agentrq_approval.adapter import AdapterError, AgentRQApprovalGate


# ---------------------------------------------------------------------------
# MCP Mock Helpers
# ---------------------------------------------------------------------------


@dataclass
class MockContent:
    """Simulates MCP result content item with a text attribute."""

    text: str


@dataclass
class MockResult:
    """Simulates MCP tool call result with content list."""

    content: list[MockContent] = field(default_factory=list)


def make_mock_session(
    call_tool_side_effects: list[MockResult] | None = None,
) -> AsyncMock:
    """Create a mock MCP ClientSession with configurable call_tool responses."""
    if call_tool_side_effects is None:
        call_tool_side_effects = [
            MockResult(content=[MockContent(text="task-abc-123")]),  # createTask
            MockResult(content=[MockContent(text="ok")]),  # reply
        ]

    session = AsyncMock()
    session.call_tool = AsyncMock(side_effect=call_tool_side_effects)
    return session


# ===================================================================
# Auto-Approve by Policy (AC 4, 10)
# ===================================================================


class TestAutoApproveByPolicy:
    """Tests for risk-based auto-approval without MCP traffic."""

    async def test_auto_approve_by_policy(self) -> None:
        """AC 4: risk_level in auto_approve_levels returns APPROVED without MCP call."""
        policy = ApprovalPolicy(auto_approve_levels=[RiskLevel.LOW])
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
            policy=policy,
        )

        result = await gate.request_approval("read_config", RiskLevel.LOW)

        assert result.status == ApprovalStatus.APPROVED
        assert result.approver == "policy"
        assert result.metadata["action"] == "read_config"
        assert result.metadata["risk_level"] == "low"
        # No MCP session created — gate._session should remain None
        assert gate._session is None

    async def test_auto_approve_generates_synthetic_uuid(self) -> None:
        """AC 10: request_id is a hex UUID, no MCP traffic."""
        policy = ApprovalPolicy(auto_approve_levels=[RiskLevel.LOW, RiskLevel.MEDIUM])
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
            policy=policy,
        )

        result = await gate.request_approval("update_settings", RiskLevel.MEDIUM)

        # UUID4 hex is 32 hex chars (no dashes)
        assert len(result.request_id) == 32
        assert all(c in "0123456789abcdef" for c in result.request_id)
        # No MCP session created
        assert gate._session is None


# ===================================================================
# Task Creation via MCP Mock (AC 3, 8)
# ===================================================================


class TestTaskCreation:
    """Tests for MCP-based task creation and context enrichment."""

    async def test_request_approval_creates_task(self, gate_with_mock: AgentRQApprovalGate, mock_session: AsyncMock) -> None:
        """AC 3: calls createTask with correct title/description via MCP mock."""
        result = await gate_with_mock.request_approval("delete_db", RiskLevel.HIGH)

        # First call should be createTask
        create_call = mock_session.call_tool.call_args_list[0]
        assert create_call.args[0] == "createTask"
        assert create_call.args[1]["title"] == "[Beddel Approval] delete_db"
        assert "Risk: high" in create_call.args[1]["description"]
        assert "Action: delete_db" in create_call.args[1]["description"]
        assert result.request_id == "task-abc-123"

    async def test_request_approval_posts_context_via_reply(self, gate_with_mock: AgentRQApprovalGate, mock_session: AsyncMock) -> None:
        """AC 8: calls reply tool after task creation for context enrichment."""
        await gate_with_mock.request_approval("deploy_prod", RiskLevel.HIGH)

        # Second call should be reply
        reply_call = mock_session.call_tool.call_args_list[1]
        assert reply_call.args[0] == "reply"
        assert reply_call.args[1]["taskId"] == "task-abc-123"
        assert "deploy_prod" in reply_call.args[1]["message"]
        assert "high" in reply_call.args[1]["message"]

    async def test_request_approval_returns_pending(self, gate_with_mock: AgentRQApprovalGate) -> None:
        """AC 3: result.status == PENDING, request_id matches task_id."""
        result = await gate_with_mock.request_approval("write_data", RiskLevel.HIGH)

        assert result.status == ApprovalStatus.PENDING
        assert result.request_id == "task-abc-123"
        assert isinstance(result, ApprovalResult)


# ===================================================================
# Status Polling with Mapped Statuses (AC 5)
# ===================================================================


class TestCheckStatus:
    """Tests for check_status with all AgentRQ status mappings."""

    async def test_check_status_completed(self) -> None:
        """AgentRQ 'completed' maps to APPROVED."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-1"] = time.time()

        response_json = json.dumps({"status": "completed"})
        session = make_mock_session([MockResult(content=[MockContent(text=response_json)])])
        gate._session = session

        status = await gate.check_status("task-1")
        assert status == ApprovalStatus.APPROVED

    async def test_check_status_rejected(self) -> None:
        """AgentRQ 'rejected' maps to DENIED."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-2"] = time.time()

        response_json = json.dumps({"status": "rejected"})
        session = make_mock_session([MockResult(content=[MockContent(text=response_json)])])
        gate._session = session

        status = await gate.check_status("task-2")
        assert status == ApprovalStatus.DENIED

    async def test_check_status_blocked(self) -> None:
        """AgentRQ 'blocked' maps to ESCALATED."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-3"] = time.time()

        response_json = json.dumps({"status": "blocked"})
        session = make_mock_session([MockResult(content=[MockContent(text=response_json)])])
        gate._session = session

        status = await gate.check_status("task-3")
        assert status == ApprovalStatus.ESCALATED

    async def test_check_status_notstarted(self) -> None:
        """AgentRQ 'notstarted' maps to PENDING."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-4"] = time.time()

        response_json = json.dumps({"status": "notstarted"})
        session = make_mock_session([MockResult(content=[MockContent(text=response_json)])])
        gate._session = session

        status = await gate.check_status("task-4")
        assert status == ApprovalStatus.PENDING

    async def test_check_status_ongoing(self) -> None:
        """AgentRQ 'ongoing' maps to PENDING."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-5"] = time.time()

        response_json = json.dumps({"status": "ongoing"})
        session = make_mock_session([MockResult(content=[MockContent(text=response_json)])])
        gate._session = session

        status = await gate.check_status("task-5")
        assert status == ApprovalStatus.PENDING

    async def test_check_status_unknown_status(self, caplog: pytest.LogCaptureFixture) -> None:
        """Unknown status maps to PENDING + warning log."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-6"] = time.time()

        response_json = json.dumps({"status": "some_new_status"})
        session = make_mock_session([MockResult(content=[MockContent(text=response_json)])])
        gate._session = session

        with caplog.at_level(logging.WARNING, logger="beddel_agentrq_approval.adapter"):
            status = await gate.check_status("task-6")

        assert status == ApprovalStatus.PENDING
        assert "Unknown AgentRQ task status" in caplog.text
        assert "some_new_status" in caplog.text


# ===================================================================
# Client-Side Timeout Derivation (AC 5)
# ===================================================================


class TestTimeoutDerivation:
    """Tests for client-side timeout computed from created_at + timeout_seconds."""

    async def test_check_status_timeout(self) -> None:
        """When elapsed > timeout_seconds, returns TIMEOUT."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
            timeout_seconds=60,
        )
        # Simulate a request created 120 seconds ago (exceeds 60s timeout)
        gate._pending_requests["task-timeout"] = time.time() - 120

        status = await gate.check_status("task-timeout")
        assert status == ApprovalStatus.TIMEOUT

    async def test_check_status_not_timed_out(self) -> None:
        """When elapsed < timeout_seconds, status is fetched from MCP."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
            timeout_seconds=300,
        )
        gate._pending_requests["task-active"] = time.time()

        response_json = json.dumps({"status": "ongoing"})
        session = make_mock_session([MockResult(content=[MockContent(text=response_json)])])
        gate._session = session

        status = await gate.check_status("task-active")
        assert status == ApprovalStatus.PENDING


# ===================================================================
# Unknown Request ID (AC 9)
# ===================================================================


class TestUnknownRequestId:
    """Tests for check_status with unknown request_id."""

    async def test_check_status_unknown_request_id(self) -> None:
        """Unknown request_id returns PENDING (consistent with reference adapter)."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        # Do NOT add anything to _pending_requests

        status = await gate.check_status("nonexistent-task-id")
        assert status == ApprovalStatus.PENDING


# ===================================================================
# MCP Error Handling (AC 9)
# ===================================================================


class TestMCPErrorHandling:
    """Tests for MCP transport error wrapping in AdapterError."""

    async def test_check_status_mcp_error(self) -> None:
        """MCP exception raises AdapterError with BEDDEL-ADAPT-003."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-err"] = time.time()

        session = AsyncMock()
        session.call_tool = AsyncMock(side_effect=ConnectionError("Connection refused"))
        gate._session = session

        with pytest.raises(AdapterError) as exc_info:
            await gate.check_status("task-err")

        assert exc_info.value.code == "BEDDEL-ADAPT-003"
        assert "Connection refused" in str(exc_info.value)
        assert exc_info.value.details["request_id"] == "task-err"


# ===================================================================
# CIBA Path (AC 6)
# ===================================================================


class TestRequestApprovalAsync:
    """Tests for request_approval_async (CIBA pattern)."""

    async def test_request_approval_async_returns_request_id(self) -> None:
        """CIBA path returns string task_id."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        session = make_mock_session()
        gate._session = session

        request_id = await gate.request_approval_async("deploy_staging", RiskLevel.HIGH)

        assert request_id == "task-abc-123"
        assert isinstance(request_id, str)

    async def test_request_approval_async_auto_approve_returns_uuid(self) -> None:
        """CIBA path with auto-approved level returns synthetic UUID."""
        policy = ApprovalPolicy(auto_approve_levels=[RiskLevel.LOW])
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
            policy=policy,
        )

        request_id = await gate.request_approval_async("read_logs", RiskLevel.LOW)

        assert len(request_id) == 32
        assert all(c in "0123456789abcdef" for c in request_id)


# ===================================================================
# Connection Lifecycle (AC 7)
# ===================================================================


class TestConnectionLifecycle:
    """Tests for lazy connection, close, and async context manager."""

    async def test_connection_lifecycle_close(self) -> None:
        """close() sets session to None."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._session = AsyncMock()
        gate._exit_stack = AsyncMock()

        await gate.close()

        assert gate._session is None
        assert gate._exit_stack is None

    async def test_context_manager_closes_on_exit(self) -> None:
        """__aexit__ calls close()."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._session = AsyncMock()
        gate._exit_stack = AsyncMock()

        async with gate:
            assert gate._session is not None

        # After exiting context manager, session should be cleaned up
        assert gate._session is None

    async def test_lazy_connection(self) -> None:
        """No MCP traffic until first approval call."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )

        # Session is None on construction (lazy)
        assert gate._session is None

        # Even entering context manager does NOT connect
        async with gate:
            assert gate._session is None

    async def test_ensure_connected_creates_session(self) -> None:
        """_ensure_connected creates session on first call."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        mock_session = AsyncMock()

        with patch.object(gate, "_create_session", return_value=mock_session):
            session = await gate._ensure_connected()

        assert session is mock_session
        assert gate._session is mock_session

    async def test_ensure_connected_reuses_session(self) -> None:
        """_ensure_connected reuses existing session on subsequent calls."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        existing_session = AsyncMock()
        gate._session = existing_session

        session = await gate._ensure_connected()

        assert session is existing_session
