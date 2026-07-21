"""Integration tests against the real installed kimi-agent-sdk==0.0.5.

These tests import the actual SDK classes (NOT mocks) to verify
API compatibility. No sessions are created, no API keys are needed.
"""

from __future__ import annotations

import inspect


class TestSessionCreateSignature:
    """Verify Session.create() signature matches what adapter expects."""

    def test_session_create_does_not_accept_sandbox_mode(self) -> None:
        """Session.create() must NOT have a sandbox_mode parameter."""
        from kimi_agent_sdk import Session

        sig = inspect.signature(Session.create)
        params = list(sig.parameters.keys())
        assert "sandbox_mode" not in params, (
            f"Session.create() should NOT accept sandbox_mode. "
            f"Found parameters: {params}"
        )

    def test_session_create_accepts_work_dir(self) -> None:
        """Session.create() must accept work_dir parameter."""
        from kimi_agent_sdk import Session

        sig = inspect.signature(Session.create)
        params = list(sig.parameters.keys())
        assert "work_dir" in params, (
            f"Session.create() should accept work_dir. Found parameters: {params}"
        )

    def test_session_create_accepts_config(self) -> None:
        """Session.create() must accept config parameter."""
        from kimi_agent_sdk import Session

        sig = inspect.signature(Session.create)
        params = list(sig.parameters.keys())
        assert "config" in params, (
            f"Session.create() should accept config. Found parameters: {params}"
        )

    def test_session_create_accepts_yolo(self) -> None:
        """Session.create() must accept yolo parameter."""
        from kimi_agent_sdk import Session

        sig = inspect.signature(Session.create)
        params = list(sig.parameters.keys())
        assert "yolo" in params, (
            f"Session.create() should accept yolo. Found parameters: {params}"
        )


class TestKaosPath:
    """Verify KaosPath is importable and constructable from string."""

    def test_kaos_path_importable(self) -> None:
        """KaosPath must be importable from kaos.path."""
        from kaos.path import KaosPath

        assert KaosPath is not None

    def test_kaos_path_from_string(self) -> None:
        """KaosPath can be constructed from a string path."""
        from kaos.path import KaosPath

        path = KaosPath(".")
        assert path is not None

    def test_kaos_path_from_absolute_string(self) -> None:
        """KaosPath can be constructed from an absolute path string."""
        from kaos.path import KaosPath

        path = KaosPath("/tmp/test-workspace")
        assert path is not None
        assert str(path) == "/tmp/test-workspace"


class TestBuildKimiConfigContract:
    """Verify build_kimi_config() returns valid Config against real SDK."""

    def test_returns_config_instance(self) -> None:
        """build_kimi_config() must return a kimi_agent_sdk.Config instance."""
        from kimi_agent_sdk import Config

        from beddel_agent_kimi.session import build_kimi_config

        result = build_kimi_config(api_key="test-key", model="kimi-k3")
        assert isinstance(result, Config), (
            f"Expected Config instance, got {type(result).__name__}"
        )

    def test_default_model_set_correctly(self) -> None:
        """Returned config has default_model matching the passed model."""
        from beddel_agent_kimi.session import build_kimi_config

        result = build_kimi_config(api_key="test-key", model="kimi-k2.7-code")
        assert result.default_model == "kimi-k2.7-code"

    def test_max_context_size_default(self) -> None:
        """Returned config models entry has max_context_size == 100_000."""
        from beddel_agent_kimi.session import build_kimi_config

        result = build_kimi_config(api_key="test-key", model="kimi-k3")
        model_entry = result.models["kimi-k3"]
        assert model_entry.max_context_size == 100_000

    def test_max_context_size_override(self) -> None:
        """max_context_size can be overridden via kwarg."""
        from beddel_agent_kimi.session import build_kimi_config

        result = build_kimi_config(
            api_key="test-key", model="kimi-k3", max_context_size=200_000
        )
        model_entry = result.models["kimi-k3"]
        assert model_entry.max_context_size == 200_000

    def test_invalid_max_context_size_raises(self) -> None:
        """max_context_size <= 0 raises ValueError."""
        import pytest

        from beddel_agent_kimi.session import build_kimi_config

        with pytest.raises(ValueError, match="max_context_size must be > 0"):
            build_kimi_config(api_key="test-key", model="kimi-k3", max_context_size=0)

        with pytest.raises(ValueError, match="max_context_size must be > 0"):
            build_kimi_config(api_key="test-key", model="kimi-k3", max_context_size=-1)


class TestLLMModelFieldSnapshot:
    """Snapshot required fields of SDK Config nested models.

    These tests serve as an early-warning system: if kimi-agent-sdk adds
    new required fields, these tests will fail before runtime does.
    """

    def test_llm_model_required_fields(self) -> None:
        """LLMModel required fields == {provider, model, max_context_size}."""
        from kimi_cli.config import LLMModel

        required = {
            name for name, field in LLMModel.model_fields.items() if field.is_required()
        }
        assert required == {"provider", "model", "max_context_size"}, (
            f"LLMModel required fields changed! Expected "
            f"{{provider, model, max_context_size}}, got {required}"
        )

    def test_llm_provider_required_fields(self) -> None:
        """LLMProvider required fields == {type, base_url, api_key}."""
        from kimi_cli.config import LLMProvider

        required = {
            name
            for name, field in LLMProvider.model_fields.items()
            if field.is_required()
        }
        assert required == {"type", "base_url", "api_key"}, (
            f"LLMProvider required fields changed! Expected "
            f"{{type, base_url, api_key}}, got {required}"
        )
