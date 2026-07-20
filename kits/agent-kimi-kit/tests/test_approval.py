"""Unit tests for KimiApprovalBridge — agent-kimi-kit.

Tests cover risk classification, auto/manual mode behavior,
timeout handling, yolo detection, validation, gate exception safety,
and adapter integration.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from beddel.domain.errors import AgentError
from beddel.domain.models import ApprovalResult, ApprovalStatus, RiskLevel
from beddel_agent_kimi.adapter import KimiAgentAdapter
from beddel_agent_kimi.approval import KIMI_APPROVAL_DENIED, KimiApprovalBridge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeApprovalRequest:
    """Mimics kimi_agent_sdk.ApprovalRequest for testing."""

    def __init__(self, message: str = "Allow action?") -> None:
        self.message = message
        self.resolved_decision: str | None = None

    def resolve(self, decision: str) -> None:
        self.resolved_decision = decision

    def __str__(self) -> str:
        return self.message


class FakeGate:
    """Fake IApprovalGate that returns a configured result."""

    def __init__(
        self,
        status: ApprovalStatus = ApprovalStatus.APPROVED,
        delay: float = 0.0,
    ) -> None:
        self._status = status
        self._delay = delay
        self.last_action: str | None = None
        self.last_risk_level: RiskLevel | None = None

    async def request_approval(
        self, action: str, risk_level: RiskLevel
    ) -> ApprovalResult:
        self.last_action = action
        self.last_risk_level = risk_level
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        return ApprovalResult(
            request_id="req-001",
            status=self._status,
            approver="test-user",
            timestamp=1700000000.0,
        )

    async def check_status(self, request_id: str) -> ApprovalStatus:
        return self._status


class ExplodingGate:
    """Fake IApprovalGate that raises an exception."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def request_approval(
        self, action: str, risk_level: RiskLevel
    ) -> ApprovalResult:
        raise self._exc

    async def check_status(self, request_id: str) -> ApprovalStatus:
        return ApprovalStatus.DENIED


class CancellingGate:
    """Fake IApprovalGate that raises CancelledError."""

    async def request_approval(
        self, action: str, risk_level: RiskLevel
    ) -> ApprovalResult:
        raise asyncio.CancelledError()

    async def check_status(self, request_id: str) -> ApprovalStatus:
        return ApprovalStatus.DENIED


# ---------------------------------------------------------------------------
# Test: Risk Classification
# ---------------------------------------------------------------------------


class TestRiskClassification:
    """Test classify_risk() pattern matching."""

    def setup_method(self) -> None:
        self.bridge = KimiApprovalBridge(gate=None, mode="auto")

    def test_file_creation_is_low(self) -> None:
        """File creation patterns classify as LOW risk."""
        assert self.bridge.classify_risk("write new file") == RiskLevel.LOW
        assert self.bridge.classify_risk("create file output.txt") == RiskLevel.LOW
        assert self.bridge.classify_risk("Write New Document") == RiskLevel.LOW

    def test_file_edit_is_medium(self) -> None:
        """File edit patterns classify as MEDIUM risk."""
        assert self.bridge.classify_risk("edit file config.py") == RiskLevel.MEDIUM
        assert self.bridge.classify_risk("modify existing code") == RiskLevel.MEDIUM
        assert self.bridge.classify_risk("update file settings") == RiskLevel.MEDIUM
        assert self.bridge.classify_risk("change file content") == RiskLevel.MEDIUM

    def test_shell_command_is_high(self) -> None:
        """Shell/command patterns classify as HIGH risk."""
        assert self.bridge.classify_risk("run command ls -la") == RiskLevel.HIGH
        assert self.bridge.classify_risk("execute shell script") == RiskLevel.HIGH
        assert self.bridge.classify_risk("bash -c 'rm -rf /'") == RiskLevel.HIGH
        assert self.bridge.classify_risk("open terminal session") == RiskLevel.HIGH

    def test_unknown_defaults_to_medium(self) -> None:
        """Unknown messages default to MEDIUM (conservative)."""
        assert self.bridge.classify_risk("do something") == RiskLevel.MEDIUM
        assert self.bridge.classify_risk("") == RiskLevel.MEDIUM
        assert self.bridge.classify_risk("perform analysis") == RiskLevel.MEDIUM


# ---------------------------------------------------------------------------
# Test: Validation
# ---------------------------------------------------------------------------


class TestValidation:
    """Test constructor validation for mode and timeout."""

    def test_invalid_mode_raises(self) -> None:
        """Invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid approval mode"):
            KimiApprovalBridge(gate=None, mode="turbo")

    def test_zero_timeout_raises(self) -> None:
        """Zero timeout raises ValueError."""
        with pytest.raises(ValueError, match="must be > 0"):
            KimiApprovalBridge(gate=None, mode="auto", timeout=0)

    def test_negative_timeout_raises(self) -> None:
        """Negative timeout raises ValueError."""
        with pytest.raises(ValueError, match="must be > 0"):
            KimiApprovalBridge(gate=None, mode="auto", timeout=-5.0)


# ---------------------------------------------------------------------------
# Test: Auto Mode (gate=None)
# ---------------------------------------------------------------------------


class TestAutoMode:
    """Test auto mode: risk-based policy decisions (never delegates to gate)."""

    def setup_method(self) -> None:
        self.bridge = KimiApprovalBridge(gate=None, mode="auto")

    @pytest.mark.asyncio
    async def test_low_risk_approved(self) -> None:
        """LOW risk is auto-approved in auto mode."""
        req = FakeApprovalRequest("create file test.txt")
        result = await self.bridge.handle_approval(req)
        assert result is True
        assert req.resolved_decision == "approve"

    @pytest.mark.asyncio
    async def test_medium_risk_approved(self) -> None:
        """Recognized MEDIUM risk (file edit) is auto-approved in auto mode."""
        req = FakeApprovalRequest("edit file config.py")
        result = await self.bridge.handle_approval(req)
        assert result is True
        assert req.resolved_decision == "approve"

    @pytest.mark.asyncio
    async def test_recognized_medium_approved(self) -> None:
        """Recognized MEDIUM risk patterns (file edit) are approved."""
        req = FakeApprovalRequest("modify existing module")
        result = await self.bridge.handle_approval(req)
        assert result is True
        assert req.resolved_decision == "approve"

    @pytest.mark.asyncio
    async def test_high_risk_denied(self) -> None:
        """HIGH risk is denied in auto mode."""
        req = FakeApprovalRequest("execute shell command rm -rf")
        result = await self.bridge.handle_approval(req)
        assert result is False
        assert req.resolved_decision == "deny"

    @pytest.mark.asyncio
    async def test_unknown_risk_denied(self) -> None:
        """Unknown/unrecognized actions (unrecognized MEDIUM) are denied in auto mode."""
        req = FakeApprovalRequest("some unknown action")
        result = await self.bridge.handle_approval(req)
        assert result is False
        assert req.resolved_decision == "deny"

    @pytest.mark.asyncio
    async def test_unrecognized_medium_denied(self) -> None:
        """Unrecognized MEDIUM risk is explicitly denied (not approved)."""
        req = FakeApprovalRequest("perform analysis on data")
        result = await self.bridge.handle_approval(req)
        assert result is False
        assert req.resolved_decision == "deny"


# ---------------------------------------------------------------------------
# Test: Manual Mode (gate provided)
# ---------------------------------------------------------------------------


class TestManualMode:
    """Test manual mode: delegates all decisions to gate."""

    @pytest.mark.asyncio
    async def test_gate_approved(self) -> None:
        """Gate returning APPROVED -> approve."""
        gate = FakeGate(status=ApprovalStatus.APPROVED)
        bridge = KimiApprovalBridge(gate=gate, mode="manual")
        req = FakeApprovalRequest("create file output.txt")

        result = await bridge.handle_approval(req)

        assert result is True
        assert req.resolved_decision == "approve"
        assert gate.last_action == "create file output.txt"
        assert gate.last_risk_level == RiskLevel.LOW

    @pytest.mark.asyncio
    async def test_gate_denied(self) -> None:
        """Gate returning DENIED -> deny."""
        gate = FakeGate(status=ApprovalStatus.DENIED)
        bridge = KimiApprovalBridge(gate=gate, mode="manual")
        req = FakeApprovalRequest("run command deploy")

        result = await bridge.handle_approval(req)

        assert result is False
        assert req.resolved_decision == "deny"

    @pytest.mark.asyncio
    async def test_gate_timeout_status_denies(self) -> None:
        """Gate returning TIMEOUT status -> deny."""
        gate = FakeGate(status=ApprovalStatus.TIMEOUT)
        bridge = KimiApprovalBridge(gate=gate, mode="manual")
        req = FakeApprovalRequest("edit file main.py")

        result = await bridge.handle_approval(req)

        assert result is False
        assert req.resolved_decision == "deny"

    @pytest.mark.asyncio
    async def test_gate_escalated_denies(self) -> None:
        """Gate returning ESCALATED status -> deny."""
        gate = FakeGate(status=ApprovalStatus.ESCALATED)
        bridge = KimiApprovalBridge(gate=gate, mode="manual")
        req = FakeApprovalRequest("edit file main.py")

        result = await bridge.handle_approval(req)

        assert result is False
        assert req.resolved_decision == "deny"

    @pytest.mark.asyncio
    async def test_auto_mode_with_gate_applies_auto_policy(self) -> None:
        """Auto mode with gate still applies deterministic policy (HIGH -> deny)."""
        gate = FakeGate(status=ApprovalStatus.APPROVED)
        bridge = KimiApprovalBridge(gate=gate, mode="auto")
        req = FakeApprovalRequest("execute bash script")

        result = await bridge.handle_approval(req)

        # Auto mode ALWAYS applies deterministic policy, never delegates
        assert result is False
        assert req.resolved_decision == "deny"
        # Gate should NOT have been called
        assert gate.last_risk_level is None

    @pytest.mark.asyncio
    async def test_manual_mode_no_gate_denies(self) -> None:
        """Manual mode without gate denies by default."""
        bridge = KimiApprovalBridge(gate=None, mode="manual")
        req = FakeApprovalRequest("create file test.txt")

        result = await bridge.handle_approval(req)

        assert result is False
        assert req.resolved_decision == "deny"


# ---------------------------------------------------------------------------
# Test: Yolo Mode
# ---------------------------------------------------------------------------


class TestYoloMode:
    """Test yolo mode: approve everything."""

    @pytest.mark.asyncio
    async def test_yolo_approves_everything(self) -> None:
        """Yolo mode auto-approves any request regardless of risk."""
        bridge = KimiApprovalBridge(gate=None, mode="yolo")

        # High risk
        req = FakeApprovalRequest("execute bash rm -rf /")
        result = await bridge.handle_approval(req)
        assert result is True
        assert req.resolved_decision == "approve"

        # Unknown
        req2 = FakeApprovalRequest("something unknown and scary")
        result2 = await bridge.handle_approval(req2)
        assert result2 is True
        assert req2.resolved_decision == "approve"


# ---------------------------------------------------------------------------
# Test: Timeout Handling
# ---------------------------------------------------------------------------


class TestTimeout:
    """Test timeout behavior when gate hangs."""

    @pytest.mark.asyncio
    async def test_gate_timeout_raises_agent_error(self) -> None:
        """Gate exceeding timeout raises BEDDEL-AGENT-805 after deny."""
        gate = FakeGate(status=ApprovalStatus.APPROVED, delay=5.0)
        bridge = KimiApprovalBridge(gate=gate, mode="manual", timeout=0.01)
        req = FakeApprovalRequest("run command slow-op")

        with pytest.raises(AgentError) as exc_info:
            await bridge.handle_approval(req)

        assert exc_info.value.code == KIMI_APPROVAL_DENIED
        assert "timed out" in exc_info.value.message
        assert req.resolved_decision == "deny"

    @pytest.mark.asyncio
    async def test_timeout_details_contain_context(self) -> None:
        """Timeout error includes action, risk_level, and timeout in details."""
        gate = FakeGate(status=ApprovalStatus.APPROVED, delay=5.0)
        bridge = KimiApprovalBridge(gate=gate, mode="manual", timeout=0.01)
        req = FakeApprovalRequest("execute terminal command")

        with pytest.raises(AgentError) as exc_info:
            await bridge.handle_approval(req)

        details = exc_info.value.details
        assert details["action"] == "execute terminal command"
        assert details["risk_level"] == "high"
        assert details["timeout"] == 0.01


# ---------------------------------------------------------------------------
# Test: Gate Exception Safety
# ---------------------------------------------------------------------------


class TestGateExceptionSafety:
    """Test _delegate_to_gate exception safety paths."""

    @pytest.mark.asyncio
    async def test_gate_exception_resolves_deny(self) -> None:
        """Gate raising RuntimeError -> resolve deny + raise BEDDEL-AGENT-805."""
        gate = ExplodingGate(RuntimeError("connection lost"))
        bridge = KimiApprovalBridge(gate=gate, mode="manual")
        req = FakeApprovalRequest("edit file main.py")

        with pytest.raises(AgentError) as exc_info:
            await bridge.handle_approval(req)

        assert exc_info.value.code == KIMI_APPROVAL_DENIED
        assert "connection lost" in exc_info.value.message
        assert req.resolved_decision == "deny"

    @pytest.mark.asyncio
    async def test_gate_cancellation_resolves_deny(self) -> None:
        """Gate raising CancelledError -> resolve deny + re-raise CancelledError."""
        gate = CancellingGate()
        bridge = KimiApprovalBridge(gate=gate, mode="manual")
        req = FakeApprovalRequest("create file output.txt")

        with pytest.raises(asyncio.CancelledError):
            await bridge.handle_approval(req)

        assert req.resolved_decision == "deny"


# ---------------------------------------------------------------------------
# Test: Yolo Detection
# ---------------------------------------------------------------------------


class TestYoloDetection:
    """Test should_use_yolo() logic."""

    def test_no_gate_auto_mode_not_yolo(self) -> None:
        """gate=None + mode='auto' -> yolo=False (auto mode is not yolo)."""
        bridge = KimiApprovalBridge(gate=None, mode="auto")
        assert bridge.should_use_yolo() is False

    def test_yolo_mode_is_yolo(self) -> None:
        """mode='yolo' -> yolo=True."""
        bridge = KimiApprovalBridge(gate=None, mode="yolo")
        assert bridge.should_use_yolo() is True

    def test_gate_provided_auto_not_yolo(self) -> None:
        """gate provided + auto mode -> yolo=False."""
        gate = FakeGate()
        bridge = KimiApprovalBridge(gate=gate, mode="auto")
        assert bridge.should_use_yolo() is False

    def test_manual_mode_not_yolo(self) -> None:
        """mode='manual' -> yolo=False even without gate."""
        bridge = KimiApprovalBridge(gate=None, mode="manual")
        assert bridge.should_use_yolo() is False

    def test_gate_manual_not_yolo(self) -> None:
        """gate + manual -> yolo=False."""
        gate = FakeGate()
        bridge = KimiApprovalBridge(gate=gate, mode="manual")
        assert bridge.should_use_yolo() is False


# ---------------------------------------------------------------------------
# Test: Adapter Integration
# ---------------------------------------------------------------------------


class FakeTextPart:
    """Mimics kimi_agent_sdk.TextPart."""

    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


def _make_fake_session(
    responses: list[Any] | None = None,
) -> MagicMock:
    """Create a mock session for adapter integration tests."""
    if responses is None:
        responses = [FakeTextPart("Done")]

    session = MagicMock()

    async def _fake_prompt(text: str):  # noqa: ANN202
        for msg in responses:
            yield msg

    session.prompt = _fake_prompt
    return session


def _make_sdk_mock(session: MagicMock) -> MagicMock:
    """Create a mock kimi_agent_sdk module."""
    sdk_mock = MagicMock()

    @asynccontextmanager
    async def _fake_create(**kwargs: Any):  # noqa: ANN202
        session._create_kwargs = kwargs
        yield session

    async def _awaitable_create(**kwargs: Any):  # noqa: ANN202
        return _fake_create(**kwargs)

    sdk_mock.Session = MagicMock()
    sdk_mock.Session.create = _awaitable_create
    sdk_mock.Config = MagicMock(side_effect=lambda **kwargs: kwargs)

    return sdk_mock


class TestAdapterIntegration:
    """Test KimiAgentAdapter passes yolo correctly to Session.create()."""

    @pytest.fixture()
    def mock_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MOONSHOT_API_KEY", "test-key-abc123")

    @pytest.mark.asyncio
    async def test_default_adapter_passes_yolo_false(self, mock_env: None) -> None:
        """Default adapter (no gate, auto mode) passes yolo=False."""
        adapter = KimiAgentAdapter(
            api_key="test-key",
            timeout=10,
            work_dir="/tmp/test",
        )
        session = _make_fake_session()
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            await adapter.execute("task")

        assert session._create_kwargs["yolo"] is False

    @pytest.mark.asyncio
    async def test_adapter_yolo_mode_passes_yolo_true(self, mock_env: None) -> None:
        """Adapter with mode='yolo' passes yolo=True to Session.create()."""
        adapter = KimiAgentAdapter(
            api_key="test-key",
            timeout=10,
            work_dir="/tmp/test",
            approval_mode="yolo",
        )
        session = _make_fake_session()
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            await adapter.execute("task")

        assert session._create_kwargs["yolo"] is True

    @pytest.mark.asyncio
    async def test_adapter_with_gate_passes_yolo_false(self, mock_env: None) -> None:
        """Adapter with approval_gate passes yolo=False."""
        gate = FakeGate()
        adapter = KimiAgentAdapter(
            api_key="test-key",
            timeout=10,
            work_dir="/tmp/test",
            approval_gate=gate,
        )
        session = _make_fake_session()
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            await adapter.execute("task")

        assert session._create_kwargs["yolo"] is False

    @pytest.mark.asyncio
    async def test_adapter_manual_mode_passes_yolo_false(self, mock_env: None) -> None:
        """Adapter with manual mode passes yolo=False."""
        adapter = KimiAgentAdapter(
            api_key="test-key",
            timeout=10,
            work_dir="/tmp/test",
            approval_mode="manual",
        )
        session = _make_fake_session()
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            await adapter.execute("task")

        assert session._create_kwargs["yolo"] is False

    @pytest.mark.asyncio
    async def test_adapter_handles_approval_in_collect(self, mock_env: None) -> None:
        """Adapter handles ApprovalRequest during message collection."""
        gate = FakeGate(status=ApprovalStatus.APPROVED)
        adapter = KimiAgentAdapter(
            api_key="test-key",
            timeout=10,
            work_dir="/tmp/test",
            approval_gate=gate,
            approval_mode="manual",
        )
        approval_req = FakeApprovalRequest("create file output.txt")
        session = _make_fake_session(
            [FakeTextPart("Start"), approval_req, FakeTextPart(" End")]
        )
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            result = await adapter.execute("task")

        assert result.output == "Start End"
        assert approval_req.resolved_decision == "approve"

    @pytest.mark.asyncio
    async def test_adapter_stream_handles_approval(self, mock_env: None) -> None:
        """Adapter stream() yields approval events with decision."""
        gate = FakeGate(status=ApprovalStatus.DENIED)
        adapter = KimiAgentAdapter(
            api_key="test-key",
            timeout=10,
            work_dir="/tmp/test",
            approval_gate=gate,
            approval_mode="manual",
        )
        approval_req = FakeApprovalRequest("execute bash deploy")
        session = _make_fake_session(
            [FakeTextPart("Hi"), approval_req, FakeTextPart(" Bye")]
        )
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            events = [e async for e in adapter.stream("task")]

        # text, approval_request, text, complete
        assert events[0] == {"type": "text", "content": "Hi"}
        assert events[1]["type"] == "approval_request"
        assert events[1]["approved"] is False
        assert events[2] == {"type": "text", "content": " Bye"}
        assert events[3]["type"] == "complete"
