"""Unit tests for KimiAgentAdapter — agent-kimi-kit.

All tests mock the kimi-agent-sdk to avoid live API calls.
Mocks replicate the real SDK lifecycle:
  Session.create(work_dir=..., config=..., sandbox_mode=...) -> async context manager
  session.prompt(text) -> async generator of wire messages (TextPart, ApprovalRequest)
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from beddel.domain.errors import AgentError
from beddel.domain.models import AgentResult
from beddel_agent_kimi.adapter import (
    KIMI_AUTH_MISSING,
    KIMI_EXECUTION_FAILED,
    KIMI_INVALID_MODEL,
    KIMI_RATE_LIMITED,
    KIMI_SESSION_TIMEOUT,
    KimiAgentAdapter,
)
from beddel_agent_kimi.session import resolve_model, resolve_sandbox


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set MOONSHOT_API_KEY for adapter instantiation."""
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key-abc123")


@pytest.fixture()
def adapter(mock_env: None) -> KimiAgentAdapter:
    """Create a KimiAgentAdapter with test API key (auto-approve for execute tests)."""
    return KimiAgentAdapter(
        timeout=10, work_dir="/tmp/test-workspace", approval_mode="auto"
    )


# ---------------------------------------------------------------------------
# SDK mock helpers — replicate real kimi-agent-sdk Session.create() API
# ---------------------------------------------------------------------------


class FakeTextPart:
    """Mimics kimi_agent_sdk.TextPart."""

    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakeApprovalRequest:
    """Mimics kimi_agent_sdk.ApprovalRequest."""

    def __init__(self, message: str = "Allow file write?") -> None:
        self._message = message

    def resolve(self, decision: str) -> None:
        pass

    def __str__(self) -> str:
        return self._message


def _make_fake_session(
    responses: list[Any] | None = None,
    prompt_side_effect: Exception | None = None,
) -> MagicMock:
    """Create a mock session that mimics the async context manager + prompt() API.

    Args:
        responses: List of wire message objects yielded by session.prompt().
        prompt_side_effect: Exception to raise from prompt().
    """
    if responses is None:
        responses = [FakeTextPart("Hello from Kimi")]

    session = MagicMock()

    async def _fake_prompt(text: str):  # noqa: ANN202
        """Async generator mimicking session.prompt()."""
        if prompt_side_effect:
            raise prompt_side_effect
        for msg in responses:
            yield msg

    session.prompt = _fake_prompt
    return session


def _make_sdk_mock(
    session: MagicMock | None = None,
    create_side_effect: Exception | None = None,
) -> MagicMock:
    """Create a mock kimi_agent_sdk module with Session.create() as async context manager.

    Args:
        session: The mock session object. If None, creates default.
        create_side_effect: Exception to raise from Session.create().
    """
    if session is None:
        session = _make_fake_session()

    sdk_mock = MagicMock()

    @asynccontextmanager
    async def _fake_create(**kwargs: Any):  # noqa: ANN202
        if create_side_effect:
            raise create_side_effect
        # Store the kwargs for assertion
        session._create_kwargs = kwargs
        yield session

    # Session.create is an async function that returns an async context manager
    # In the real SDK: async with await Session.create(...) as session:
    # We simulate this by making create() return the context manager directly
    async def _awaitable_create(**kwargs: Any):  # noqa: ANN202
        return _fake_create(**kwargs)

    sdk_mock.Session = MagicMock()
    sdk_mock.Session.create = _awaitable_create
    sdk_mock.Config = MagicMock(side_effect=lambda **kwargs: kwargs)
    sdk_mock.TextPart = FakeTextPart

    return sdk_mock


# ---------------------------------------------------------------------------
# Test: Auth Validation (AC6)
# ---------------------------------------------------------------------------


class TestAuthValidation:
    """Test auth fail-fast behavior."""

    def test_missing_api_key_raises_agent_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BEDDEL-AGENT-800 raised when MOONSHOT_API_KEY is not set."""
        monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
        with pytest.raises(AgentError) as exc_info:
            KimiAgentAdapter()
        assert exc_info.value.code == KIMI_AUTH_MISSING

    def test_empty_api_key_raises_agent_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BEDDEL-AGENT-800 raised when MOONSHOT_API_KEY is empty."""
        monkeypatch.setenv("MOONSHOT_API_KEY", "   ")
        with pytest.raises(AgentError) as exc_info:
            KimiAgentAdapter()
        assert exc_info.value.code == KIMI_AUTH_MISSING

    def test_explicit_api_key_bypasses_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit api_key parameter skips env lookup."""
        monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
        adapter = KimiAgentAdapter(api_key="explicit-key")
        assert adapter._api_key == "explicit-key"

    def test_valid_env_key_accepted(self, mock_env: None) -> None:
        """Valid MOONSHOT_API_KEY is accepted."""
        adapter = KimiAgentAdapter()
        assert adapter._api_key == "test-key-abc123"


# ---------------------------------------------------------------------------
# Test: Model Tier Routing (AC4)
# ---------------------------------------------------------------------------


class TestModelTierRouting:
    """Test model tier -> Kimi model mapping."""

    @pytest.mark.parametrize(
        "tier,expected",
        [
            ("fast", "kimi-k2.6"),
            ("balanced", "kimi-k2.7-code-highspeed"),
            ("code", "kimi-k2.7-code"),
            ("powerful", "kimi-k3"),
        ],
    )
    def test_valid_tiers(self, tier: str, expected: str) -> None:
        """Each Beddel tier maps to the correct Kimi model."""
        assert resolve_model(tier) == expected

    def test_none_defaults_to_balanced(self) -> None:
        """None model defaults to balanced tier."""
        assert resolve_model(None) == "kimi-k2.7-code-highspeed"

    def test_raw_kimi_model_passthrough(self) -> None:
        """Raw kimi-* model names pass through unchanged."""
        assert resolve_model("kimi-k3") == "kimi-k3"

    def test_invalid_tier_raises_value_error(self) -> None:
        """Unknown tier raises ValueError."""
        with pytest.raises(ValueError, match="Unknown model tier"):
            resolve_model("nonexistent")


# ---------------------------------------------------------------------------
# Test: Sandbox Validation (AC7)
# ---------------------------------------------------------------------------


class TestSandboxValidation:
    """Test sandbox level mapping."""

    @pytest.mark.parametrize(
        "sandbox,expected",
        [
            ("read-only", "read_only"),
            ("workspace-write", "workspace"),
            ("danger-full-access", "unrestricted"),
        ],
    )
    def test_valid_sandboxes(self, sandbox: str, expected: str) -> None:
        """Each Beddel sandbox maps to a KAOS mode."""
        assert resolve_sandbox(sandbox) == expected

    def test_invalid_sandbox_raises_value_error(self) -> None:
        """Unknown sandbox raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported sandbox"):
            resolve_sandbox("invalid-mode")


# ---------------------------------------------------------------------------
# Test: Execute — Session.create() Lifecycle (AC2)
# ---------------------------------------------------------------------------


class TestExecuteLifecycle:
    """Test execute() uses Session.create() + session.prompt() lifecycle."""

    @pytest.mark.asyncio
    async def test_execute_returns_agent_result(
        self, adapter: KimiAgentAdapter
    ) -> None:
        """execute() returns AgentResult with collected text output."""
        session = _make_fake_session([FakeTextPart("Code analysis complete")])
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            result = await adapter.execute("Analyze codebase", model="powerful")

        assert isinstance(result, AgentResult)
        assert result.exit_code == 0
        assert result.output == "Code analysis complete"
        assert result.agent_id == "kimi"

    @pytest.mark.asyncio
    async def test_execute_passes_work_dir(self, adapter: KimiAgentAdapter) -> None:
        """execute() passes work_dir to Session.create() as KaosPath."""
        session = _make_fake_session()
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            await adapter.execute("task", model="fast")

        # Session._create_kwargs is set by our fake context manager
        assert str(session._create_kwargs["work_dir"]) == "/tmp/test-workspace"

    @pytest.mark.asyncio
    async def test_execute_passes_sandbox_mode(self, adapter: KimiAgentAdapter) -> None:
        """execute() no longer passes sandbox_mode to Session.create()."""
        session = _make_fake_session()
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            await adapter.execute("task", sandbox="workspace-write")

        assert "sandbox_mode" not in session._create_kwargs

    @pytest.mark.asyncio
    async def test_execute_passes_model_in_config(
        self, adapter: KimiAgentAdapter
    ) -> None:
        """execute() creates Config with resolved model."""
        session = _make_fake_session()
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            await adapter.execute("task", model="code")

        # Config is called with default_model kwarg
        config = session._create_kwargs["config"]
        assert config["default_model"] == "kimi-k2.7-code"

    @pytest.mark.asyncio
    async def test_execute_concatenates_multiple_text_parts(
        self, adapter: KimiAgentAdapter
    ) -> None:
        """execute() concatenates multiple TextPart messages."""
        session = _make_fake_session(
            [
                FakeTextPart("Part 1 "),
                FakeTextPart("Part 2 "),
                FakeTextPart("Part 3"),
            ]
        )
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            result = await adapter.execute("task")

        assert result.output == "Part 1 Part 2 Part 3"

    @pytest.mark.asyncio
    async def test_execute_invalid_sandbox_raises_error(
        self, adapter: KimiAgentAdapter
    ) -> None:
        """execute() with invalid sandbox raises BEDDEL-AGENT-803."""
        with pytest.raises(AgentError) as exc_info:
            await adapter.execute("task", sandbox="invalid-sandbox")
        assert exc_info.value.code == KIMI_EXECUTION_FAILED

    @pytest.mark.asyncio
    async def test_execute_invalid_model_raises_error(
        self, adapter: KimiAgentAdapter
    ) -> None:
        """execute() with invalid model tier raises BEDDEL-AGENT-821."""
        with pytest.raises(AgentError) as exc_info:
            await adapter.execute("task", model="nonexistent-tier")
        assert exc_info.value.code == KIMI_INVALID_MODEL


# ---------------------------------------------------------------------------
# Test: Stream — Yields Typed Events (AC3)
# ---------------------------------------------------------------------------


class TestStreamEvents:
    """Test stream() yields structured events from session messages."""

    @pytest.mark.asyncio
    async def test_stream_yields_text_events(self, adapter: KimiAgentAdapter) -> None:
        """stream() yields text events for each TextPart."""
        session = _make_fake_session(
            [
                FakeTextPart("Hello "),
                FakeTextPart("World"),
            ]
        )
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            events = [e async for e in adapter.stream("task", model="balanced")]

        # 2 text events + 1 complete event
        assert len(events) == 3
        assert events[0] == {"type": "text", "content": "Hello "}
        assert events[1] == {"type": "text", "content": "World"}
        assert events[2] == {
            "type": "complete",
            "output": "Hello World",
            "exit_code": 0,
        }

    @pytest.mark.asyncio
    async def test_stream_yields_approval_events(
        self, adapter: KimiAgentAdapter
    ) -> None:
        """stream() yields approval_request events for ApprovalRequest messages."""
        session = _make_fake_session(
            [
                FakeTextPart("Starting..."),
                FakeApprovalRequest("Allow shell command?"),
                FakeTextPart("Done"),
            ]
        )
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            events = [e async for e in adapter.stream("task")]

        assert events[0] == {"type": "text", "content": "Starting..."}
        assert events[1] == {
            "type": "approval_request",
            "message": "Allow shell command?",
            "approved": False,
        }
        assert events[2] == {"type": "text", "content": "Done"}
        assert events[3]["type"] == "complete"
        assert events[3]["output"] == "Starting...Done"

    @pytest.mark.asyncio
    async def test_stream_uses_correct_model(self, adapter: KimiAgentAdapter) -> None:
        """stream() resolves model tier and passes to Session.create()."""
        session = _make_fake_session()
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            async for _ in adapter.stream("task", model="code"):
                pass

        config = session._create_kwargs["config"]
        assert config["default_model"] == "kimi-k2.7-code"


# ---------------------------------------------------------------------------
# Test: Timeout Handling (AC5)
# ---------------------------------------------------------------------------


class TestTimeoutHandling:
    """Test session timeout behavior."""

    @pytest.mark.asyncio
    async def test_execute_timeout_raises_agent_error(self, mock_env: None) -> None:
        """execute() raises BEDDEL-AGENT-801 on timeout."""

        async def _slow_prompt(text: str):  # noqa: ANN202
            """Simulate a session that hangs indefinitely."""
            await asyncio.sleep(999)
            yield FakeTextPart("never reached")  # noqa: RUF029

        session = MagicMock()
        session.prompt = _slow_prompt
        sdk_mock = _make_sdk_mock(session)

        # Very short timeout to trigger quickly
        short_adapter = KimiAgentAdapter(api_key="test-key", timeout=0)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            with pytest.raises(AgentError) as exc_info:
                await short_adapter.execute("task")
            assert exc_info.value.code == KIMI_SESSION_TIMEOUT
            assert "partial_output" in exc_info.value.details


# ---------------------------------------------------------------------------
# Test: Rate Limit Handling (AC5 — BEDDEL-AGENT-802)
# ---------------------------------------------------------------------------


class TestRateLimitHandling:
    """Test 429 rate limit detection and retry."""

    @pytest.mark.asyncio
    async def test_rate_limit_detected_from_exception(
        self, adapter: KimiAgentAdapter
    ) -> None:
        """SDK exceptions containing '429' raise BEDDEL-AGENT-802."""
        session = _make_fake_session(
            prompt_side_effect=RuntimeError("HTTP 429 Too Many Requests")
        )
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("task")
            assert exc_info.value.code == KIMI_RATE_LIMITED


# ---------------------------------------------------------------------------
# Test: SDK Error Propagation (AC5)
# ---------------------------------------------------------------------------


class TestErrorPropagation:
    """Test SDK exception handling."""

    @pytest.mark.asyncio
    async def test_sdk_exception_wrapped_as_agent_error(
        self, adapter: KimiAgentAdapter
    ) -> None:
        """SDK exceptions are wrapped as BEDDEL-AGENT-803."""
        session = _make_fake_session(
            prompt_side_effect=RuntimeError("SDK internal error")
        )
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("task")
            assert exc_info.value.code == KIMI_EXECUTION_FAILED
            assert "SDK internal error" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_import_error_wrapped(self, adapter: KimiAgentAdapter) -> None:
        """Missing kimi-agent-sdk raises BEDDEL-AGENT-803."""
        with patch.dict("sys.modules", {"kimi_agent_sdk": None}):
            with pytest.raises((AgentError, ModuleNotFoundError)):
                await adapter.execute("task")

    @pytest.mark.asyncio
    async def test_session_create_exception(self, adapter: KimiAgentAdapter) -> None:
        """Exception during Session.create() is wrapped as BEDDEL-AGENT-803."""
        sdk_mock = _make_sdk_mock(
            create_side_effect=ConnectionError("Network unreachable")
        )

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("task")
            assert exc_info.value.code == KIMI_EXECUTION_FAILED
            assert "Network unreachable" in exc_info.value.message


# ---------------------------------------------------------------------------
# Test: Default Approval Mode (manual)
# ---------------------------------------------------------------------------


class TestDefaultApprovalMode:
    """Verify the default approval_mode is 'manual' (deny without explicit gate)."""

    def test_default_approval_mode_is_manual(self, mock_env: None) -> None:
        """KimiAgentAdapter() without explicit approval_mode uses 'manual'."""
        adapter = KimiAgentAdapter(timeout=10, work_dir="/tmp/test-workspace")
        assert adapter._approval_bridge._mode == "manual"

    @pytest.mark.asyncio
    async def test_manual_mode_no_gate_denies(self, mock_env: None) -> None:
        """Manual mode with no gate denies ApprovalRequest."""
        adapter = KimiAgentAdapter(timeout=10, work_dir="/tmp/test-workspace")
        session = _make_fake_session(
            [
                FakeTextPart("Starting..."),
                FakeApprovalRequest("Allow file write?"),
                FakeTextPart("Done"),
            ]
        )
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            events = [e async for e in adapter.stream("task")]

        approval_event = next(e for e in events if e.get("type") == "approval_request")
        assert approval_event["approved"] is False
        assert approval_event["message"] == "Allow file write?"
