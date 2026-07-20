"""Unit tests for KimiAgentAdapter — agent-kimi-kit.

All tests mock the kimi-agent-sdk to avoid live API calls.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from beddel.domain.errors import AgentError
from beddel.domain.models import AgentResult
from beddel_agent_kimi.adapter import (
    KIMI_AUTH_MISSING,
    KIMI_EXECUTION_FAILED,
    KIMI_INVALID_MODEL,
    KIMI_SESSION_TIMEOUT,
    KimiAgentAdapter,
)
from beddel_agent_kimi.session import MODEL_TIER_MAP, resolve_model, resolve_sandbox


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set MOONSHOT_API_KEY for adapter instantiation."""
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key-abc123")


@pytest.fixture()
def adapter(mock_env: None) -> KimiAgentAdapter:
    """Create a KimiAgentAdapter with test API key."""
    return KimiAgentAdapter(timeout=10)


# ---------------------------------------------------------------------------
# Session mock helper
# ---------------------------------------------------------------------------


def _make_mock_session(
    response: str = "Hello from Kimi",
    usage: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock Session that returns a canned response."""
    mock_session = MagicMock()
    mock_session.send.return_value = response
    mock_session.usage = usage or {"prompt_tokens": 10, "completion_tokens": 5}
    return mock_session


# ---------------------------------------------------------------------------
# Test: Auth Validation (AC6)
# ---------------------------------------------------------------------------


class TestAuthValidation:
    """Test auth fail-fast behavior."""

    def test_missing_api_key_raises_agent_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """BEDDEL-AGENT-800 raised when MOONSHOT_API_KEY is not set."""
        monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
        with pytest.raises(AgentError) as exc_info:
            KimiAgentAdapter()
        assert exc_info.value.code == KIMI_AUTH_MISSING

    def test_empty_api_key_raises_agent_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """BEDDEL-AGENT-800 raised when MOONSHOT_API_KEY is empty."""
        monkeypatch.setenv("MOONSHOT_API_KEY", "   ")
        with pytest.raises(AgentError) as exc_info:
            KimiAgentAdapter()
        assert exc_info.value.code == KIMI_AUTH_MISSING

    def test_explicit_api_key_bypasses_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
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
    """Test model tier → Kimi model mapping."""

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
# Test: Execute Happy Path (AC2)
# ---------------------------------------------------------------------------


class TestExecuteHappyPath:
    """Test execute() with mocked SDK."""

    @pytest.mark.asyncio
    async def test_execute_returns_agent_result(self, adapter: KimiAgentAdapter) -> None:
        """execute() returns AgentResult with correct fields."""
        mock_session = _make_mock_session("Code analysis complete")
        mock_session_cls = MagicMock(return_value=mock_session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": MagicMock(Session=mock_session_cls)}):
            result = await adapter.execute("Analyze codebase", model="powerful")

        assert isinstance(result, AgentResult)
        assert result.exit_code == 0
        assert result.output == "Code analysis complete"
        assert result.agent_id == "kimi"

    @pytest.mark.asyncio
    async def test_execute_creates_session_with_correct_model(
        self, adapter: KimiAgentAdapter
    ) -> None:
        """execute() passes resolved model to Session constructor."""
        mock_session = _make_mock_session()
        mock_session_cls = MagicMock(return_value=mock_session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": MagicMock(Session=mock_session_cls)}):
            await adapter.execute("task", model="fast")

        mock_session_cls.assert_called_once()
        call_kwargs = mock_session_cls.call_args[1]
        assert call_kwargs["model"] == "kimi-k2.6"

    @pytest.mark.asyncio
    async def test_execute_passes_sandbox_mode(self, adapter: KimiAgentAdapter) -> None:
        """execute() maps sandbox to KAOS mode for Session."""
        mock_session = _make_mock_session()
        mock_session_cls = MagicMock(return_value=mock_session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": MagicMock(Session=mock_session_cls)}):
            await adapter.execute("task", sandbox="workspace-write")

        call_kwargs = mock_session_cls.call_args[1]
        assert call_kwargs["sandbox_mode"] == "workspace"

    @pytest.mark.asyncio
    async def test_execute_invalid_sandbox_raises_error(
        self, adapter: KimiAgentAdapter
    ) -> None:
        """execute() with invalid sandbox raises BEDDEL-AGENT-801."""
        with pytest.raises(AgentError) as exc_info:
            await adapter.execute("task", sandbox="invalid-sandbox")
        assert exc_info.value.code == KIMI_SESSION_TIMEOUT

    @pytest.mark.asyncio
    async def test_execute_invalid_model_raises_error(
        self, adapter: KimiAgentAdapter
    ) -> None:
        """execute() with invalid model tier raises BEDDEL-AGENT-821."""
        with pytest.raises(AgentError) as exc_info:
            await adapter.execute("task", model="nonexistent-tier")
        assert exc_info.value.code == KIMI_INVALID_MODEL


# ---------------------------------------------------------------------------
# Test: Stream Happy Path (AC3)
# ---------------------------------------------------------------------------


class TestStreamHappyPath:
    """Test stream() with mocked SDK."""

    @pytest.mark.asyncio
    async def test_stream_yields_complete_event(self, adapter: KimiAgentAdapter) -> None:
        """stream() yields a single 'complete' event."""
        mock_session = _make_mock_session("Streamed output")
        mock_session_cls = MagicMock(return_value=mock_session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": MagicMock(Session=mock_session_cls)}):
            events = []
            async for event in adapter.stream("task", model="balanced"):
                events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == "complete"
        assert events[0]["output"] == "Streamed output"
        assert events[0]["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_stream_uses_correct_model(self, adapter: KimiAgentAdapter) -> None:
        """stream() resolves model tier correctly."""
        mock_session = _make_mock_session()
        mock_session_cls = MagicMock(return_value=mock_session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": MagicMock(Session=mock_session_cls)}):
            async for _ in adapter.stream("task", model="code"):
                pass

        call_kwargs = mock_session_cls.call_args[1]
        assert call_kwargs["model"] == "kimi-k2.7-code"


# ---------------------------------------------------------------------------
# Test: Timeout Handling (AC5)
# ---------------------------------------------------------------------------


class TestTimeoutHandling:
    """Test session timeout behavior."""

    @pytest.mark.asyncio
    async def test_execute_timeout_raises_agent_error(
        self, adapter: KimiAgentAdapter
    ) -> None:
        """execute() raises BEDDEL-AGENT-801 on timeout."""
        mock_session = MagicMock()
        # Simulate a blocking call that exceeds timeout
        mock_session.send.side_effect = lambda _: asyncio.get_event_loop().run_until_complete(
            asyncio.sleep(999)
        )
        mock_session_cls = MagicMock(return_value=mock_session)

        # Use a very short timeout adapter
        short_adapter = KimiAgentAdapter(api_key="test-key", timeout=0)

        with patch.dict("sys.modules", {"kimi_agent_sdk": MagicMock(Session=mock_session_cls)}):
            with pytest.raises(AgentError) as exc_info:
                await short_adapter.execute("task")
            assert exc_info.value.code == KIMI_SESSION_TIMEOUT

    @pytest.mark.asyncio
    async def test_stream_timeout_raises_stream_interrupted(
        self, adapter: KimiAgentAdapter
    ) -> None:
        """stream() raises BEDDEL-AGENT-703 on timeout (re-wrapped)."""
        mock_session = MagicMock()
        mock_session.send.side_effect = lambda _: asyncio.get_event_loop().run_until_complete(
            asyncio.sleep(999)
        )
        mock_session_cls = MagicMock(return_value=mock_session)

        short_adapter = KimiAgentAdapter(api_key="test-key", timeout=0)

        with patch.dict("sys.modules", {"kimi_agent_sdk": MagicMock(Session=mock_session_cls)}):
            from beddel.error_codes import AGENT_STREAM_INTERRUPTED

            with pytest.raises(AgentError) as exc_info:
                async for _ in short_adapter.stream("task"):
                    pass
            assert exc_info.value.code == AGENT_STREAM_INTERRUPTED


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
        mock_session = MagicMock()
        mock_session.send.side_effect = RuntimeError("SDK internal error")
        mock_session_cls = MagicMock(return_value=mock_session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": MagicMock(Session=mock_session_cls)}):
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("task")
            assert exc_info.value.code == KIMI_EXECUTION_FAILED
            assert "SDK internal error" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_import_error_wrapped(self, adapter: KimiAgentAdapter) -> None:
        """Missing kimi-agent-sdk raises BEDDEL-AGENT-803."""
        # Remove the mock module to simulate import failure
        with patch.dict("sys.modules", {"kimi_agent_sdk": None}):
            with pytest.raises((AgentError, ModuleNotFoundError)):
                await adapter.execute("task")
