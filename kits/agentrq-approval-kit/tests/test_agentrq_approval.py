"""Unit tests for beddel_agentrq_approval adapter kit.

Covers all AC scenarios plus code-review fixes: auto-approve queryability (C1),
empty response handling (C3), credential redaction (H1), connect lock (H3),
memory eviction (H4), close-after-close (M2/M3).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, patch

import pytest

from beddel.domain.models import (
    ApprovalPolicy,
    ApprovalResult,
    ApprovalStatus,
    RiskLevel,
)
from beddel_agentrq_approval.adapter import (
    AdapterError,
    AgentRQApprovalGate,
    _redact_url,
)


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
# URL Redaction (H1 fix)
# ===================================================================


class TestURLRedaction:
    """Tests for _redact_url helper."""

    def test_redacts_query_params(self) -> None:
        """Token in query params is redacted."""
        url = "https://app.agentrq.com/mcp/ws1?token=secret123"
        assert "secret123" not in _redact_url(url)
        assert "***" in _redact_url(url)

    def test_preserves_host_and_path(self) -> None:
        """Host and path remain visible."""
        url = "https://app.agentrq.com/mcp/ws1?token=secret"
        redacted = _redact_url(url)
        assert "app.agentrq.com" in redacted
        assert "/mcp/ws1" in redacted


# ===================================================================
# Auto-Approve by Policy (AC 4, 10, C1 fix)
# ===================================================================


class TestAutoApproveByPolicy:
    """Tests for risk-based auto-approval without MCP traffic."""

    async def test_auto_approve_by_policy(self) -> None:
        """AC 4: risk_level in auto_approve_levels returns APPROVED."""
        policy = ApprovalPolicy(auto_approve_levels=[RiskLevel.LOW])
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
            policy=policy,
        )

        result = await gate.request_approval("read_config", RiskLevel.LOW)

        assert result.status == ApprovalStatus.APPROVED
        assert result.approver == "policy"
        assert result.metadata["action"] == "read_config"
        assert gate._session is None

    async def test_auto_approve_generates_synthetic_uuid(self) -> None:
        """AC 10: request_id is a hex UUID."""
        policy = ApprovalPolicy(auto_approve_levels=[RiskLevel.LOW, RiskLevel.MEDIUM])
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
            policy=policy,
        )

        result = await gate.request_approval("update_settings", RiskLevel.MEDIUM)

        assert len(result.request_id) == 32
        assert all(c in "0123456789abcdef" for c in result.request_id)

    async def test_auto_approve_queryable_via_check_status(self) -> None:
        """C1 FIX: check_status returns APPROVED for auto-approved requests."""
        policy = ApprovalPolicy(auto_approve_levels=[RiskLevel.LOW])
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
            policy=policy,
        )

        result = await gate.request_approval("read_config", RiskLevel.LOW)
        status = await gate.check_status(result.request_id)

        assert status == ApprovalStatus.APPROVED


# ===================================================================
# Task Creation via MCP Mock (AC 3, 8)
# ===================================================================


class TestTaskCreation:
    """Tests for MCP-based task creation and context enrichment."""

    async def test_request_approval_creates_task(self) -> None:
        """AC 3: calls createTask with correct title/description."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        mock_session = make_mock_session()
        gate._session = mock_session

        result = await gate.request_approval("delete_db", RiskLevel.HIGH)

        create_call = mock_session.call_tool.call_args_list[0]
        assert create_call.args[0] == "createTask"
        args = create_call.kwargs["arguments"]
        assert args["title"] == "[Beddel Approval] delete_db"
        assert "Risk: high" in args["description"]
        assert result.request_id == "task-abc-123"

    async def test_request_approval_posts_context_via_reply(self) -> None:
        """AC 8: calls reply tool after task creation."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        mock_session = make_mock_session()
        gate._session = mock_session

        await gate.request_approval("deploy_prod", RiskLevel.HIGH)

        reply_call = mock_session.call_tool.call_args_list[1]
        assert reply_call.args[0] == "reply"
        args = reply_call.kwargs["arguments"]
        assert args["taskId"] == "task-abc-123"
        assert "deploy_prod" in args["message"]

    async def test_request_approval_returns_pending(self) -> None:
        """AC 3: result.status == PENDING, request_id matches task_id."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._session = make_mock_session()

        result = await gate.request_approval("write_data", RiskLevel.HIGH)

        assert result.status == ApprovalStatus.PENDING
        assert result.request_id == "task-abc-123"
        assert isinstance(result, ApprovalResult)

    async def test_request_approval_empty_response_raises(self) -> None:
        """C3 FIX: Empty createTask response raises AdapterError."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=MockResult(content=[])  # Empty content
        )
        gate._session = mock_session

        with pytest.raises(AdapterError) as exc_info:
            await gate.request_approval("delete_all", RiskLevel.CRITICAL)

        assert exc_info.value.code == "BEDDEL-ADAPT-003"
        assert "empty" in str(exc_info.value).lower()

    async def test_request_approval_empty_task_id_raises(self) -> None:
        """C3 FIX: Empty task_id text raises AdapterError."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=MockResult(content=[MockContent(text="")])
        )
        gate._session = mock_session

        with pytest.raises(AdapterError) as exc_info:
            await gate.request_approval("delete_all", RiskLevel.CRITICAL)

        assert "empty task_id" in str(exc_info.value).lower()

    async def test_reply_failure_is_non_fatal(self) -> None:
        """L2 FIX: reply failure doesn't crash request_approval."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            side_effect=[
                MockResult(content=[MockContent(text="task-xyz")]),  # createTask OK
                ConnectionError("reply failed"),  # reply fails
            ]
        )
        gate._session = mock_session

        result = await gate.request_approval("action", RiskLevel.HIGH)

        # Task was created successfully despite reply failure
        assert result.request_id == "task-xyz"
        assert result.status == ApprovalStatus.PENDING


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
        gate._pending_requests["task-1"] = time.monotonic()

        response_json = json.dumps({"status": "completed"})
        gate._session = make_mock_session(
            [MockResult(content=[MockContent(text=response_json)])]
        )

        status = await gate.check_status("task-1")
        assert status == ApprovalStatus.APPROVED

    async def test_check_status_rejected(self) -> None:
        """AgentRQ 'rejected' maps to DENIED."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-2"] = time.monotonic()

        response_json = json.dumps({"status": "rejected"})
        gate._session = make_mock_session(
            [MockResult(content=[MockContent(text=response_json)])]
        )

        status = await gate.check_status("task-2")
        assert status == ApprovalStatus.DENIED

    async def test_check_status_blocked(self) -> None:
        """AgentRQ 'blocked' maps to ESCALATED."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-3"] = time.monotonic()

        response_json = json.dumps({"status": "blocked"})
        gate._session = make_mock_session(
            [MockResult(content=[MockContent(text=response_json)])]
        )

        status = await gate.check_status("task-3")
        assert status == ApprovalStatus.ESCALATED

    async def test_check_status_notstarted(self) -> None:
        """AgentRQ 'notstarted' maps to PENDING."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-4"] = time.monotonic()

        response_json = json.dumps({"status": "notstarted"})
        gate._session = make_mock_session(
            [MockResult(content=[MockContent(text=response_json)])]
        )

        status = await gate.check_status("task-4")
        assert status == ApprovalStatus.PENDING

    async def test_check_status_ongoing(self) -> None:
        """AgentRQ 'ongoing' maps to PENDING."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-5"] = time.monotonic()

        response_json = json.dumps({"status": "ongoing"})
        gate._session = make_mock_session(
            [MockResult(content=[MockContent(text=response_json)])]
        )

        status = await gate.check_status("task-5")
        assert status == ApprovalStatus.PENDING

    async def test_check_status_unknown_status(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Unknown status maps to PENDING + warning log."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-6"] = time.monotonic()

        response_json = json.dumps({"status": "some_new_status"})
        gate._session = make_mock_session(
            [MockResult(content=[MockContent(text=response_json)])]
        )

        with caplog.at_level(
            logging.WARNING, logger="beddel_agentrq_approval.adapter"
        ):
            status = await gate.check_status("task-6")

        assert status == ApprovalStatus.PENDING
        assert "Unknown AgentRQ task status" in caplog.text

    async def test_check_status_evicts_on_terminal(self) -> None:
        """H4 FIX: Terminal states evict from _pending_requests."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-evict"] = time.monotonic()

        response_json = json.dumps({"status": "completed"})
        gate._session = make_mock_session(
            [MockResult(content=[MockContent(text=response_json)])]
        )

        await gate.check_status("task-evict")
        assert "task-evict" not in gate._pending_requests

    async def test_check_status_taskstatus_field(self) -> None:
        """C2 FIX: Reads taskStatus field (AgentRQ metadata)."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-meta"] = time.monotonic()

        response_json = json.dumps({"taskStatus": "completed", "messages": []})
        gate._session = make_mock_session(
            [MockResult(content=[MockContent(text=response_json)])]
        )

        status = await gate.check_status("task-meta")
        assert status == ApprovalStatus.APPROVED


# ===================================================================
# Client-Side Timeout Derivation (AC 5)
# ===================================================================


class TestTimeoutDerivation:
    """Tests for client-side timeout computed from monotonic clock."""

    async def test_check_status_timeout(self) -> None:
        """When elapsed > timeout_seconds, returns TIMEOUT."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
            timeout_seconds=60,
        )
        # Simulate a request created 120 seconds ago
        gate._pending_requests["task-timeout"] = time.monotonic() - 120

        status = await gate.check_status("task-timeout")
        assert status == ApprovalStatus.TIMEOUT

    async def test_timeout_evicts_from_pending(self) -> None:
        """H4 FIX: TIMEOUT also evicts from _pending_requests."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
            timeout_seconds=60,
        )
        gate._pending_requests["task-timeout"] = time.monotonic() - 120

        await gate.check_status("task-timeout")
        assert "task-timeout" not in gate._pending_requests

    async def test_check_status_not_timed_out(self) -> None:
        """When elapsed < timeout_seconds, status is fetched from MCP."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
            timeout_seconds=300,
        )
        gate._pending_requests["task-active"] = time.monotonic()

        response_json = json.dumps({"status": "ongoing"})
        gate._session = make_mock_session(
            [MockResult(content=[MockContent(text=response_json)])]
        )

        status = await gate.check_status("task-active")
        assert status == ApprovalStatus.PENDING


# ===================================================================
# Unknown Request ID (AC 9)
# ===================================================================


class TestUnknownRequestId:
    """Tests for check_status with unknown request_id."""

    async def test_check_status_unknown_request_id(self) -> None:
        """Unknown request_id returns PENDING."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        status = await gate.check_status("nonexistent-task-id")
        assert status == ApprovalStatus.PENDING


# ===================================================================
# MCP Error Handling (AC 9)
# ===================================================================


class TestMCPErrorHandling:
    """Tests for MCP transport error wrapping."""

    async def test_check_status_mcp_error(self) -> None:
        """MCP exception raises AdapterError with BEDDEL-ADAPT-003."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._pending_requests["task-err"] = time.monotonic()

        session = AsyncMock()
        session.call_tool = AsyncMock(
            side_effect=ConnectionError("Connection refused")
        )
        gate._session = session

        with pytest.raises(AdapterError) as exc_info:
            await gate.check_status("task-err")

        assert exc_info.value.code == "BEDDEL-ADAPT-003"
        assert exc_info.value.details["request_id"] == "task-err"
        # H1 FIX: No URL/token in error details
        assert "token" not in str(exc_info.value.details)


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
        gate._session = make_mock_session()

        request_id = await gate.request_approval_async(
            "deploy_staging", RiskLevel.HIGH
        )

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
# Connection Lifecycle (AC 7, H3, M2, M3 fixes)
# ===================================================================


class TestConnectionLifecycle:
    """Tests for lazy connection, close, lock, and closed flag."""

    async def test_connection_lifecycle_close(self) -> None:
        """close() sets session to None and marks closed."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._session = AsyncMock()
        gate._exit_stack = AsyncMock()

        await gate.close()

        assert gate._session is None
        assert gate._exit_stack is None
        assert gate._closed is True

    async def test_context_manager_closes_on_exit(self) -> None:
        """__aexit__ calls close()."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._session = AsyncMock()
        gate._exit_stack = AsyncMock()

        async with gate:
            assert gate._session is not None

        assert gate._session is None
        assert gate._closed is True

    async def test_lazy_connection(self) -> None:
        """No MCP traffic until first approval call."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        assert gate._session is None

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
        """_ensure_connected reuses existing session."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        existing_session = AsyncMock()
        gate._session = existing_session

        session = await gate._ensure_connected()
        assert session is existing_session

    async def test_ensure_connected_raises_after_close(self) -> None:
        """M3 FIX: _ensure_connected raises RuntimeError after close."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        await gate.close()

        with pytest.raises(RuntimeError, match="has been closed"):
            await gate._ensure_connected()

    async def test_close_idempotent(self) -> None:
        """close() is safe to call multiple times."""
        gate = AgentRQApprovalGate(
            workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        )
        gate._session = AsyncMock()
        gate._exit_stack = AsyncMock()

        await gate.close()
        await gate.close()  # Should not raise

        assert gate._closed is True
