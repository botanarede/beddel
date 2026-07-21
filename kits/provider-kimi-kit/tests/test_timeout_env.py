"""Tests for MOONSHOT_TIMEOUT env var fallback in KimiLLMProvider."""

from __future__ import annotations

import pytest

from beddel.domain.errors import AdapterError
from beddel_provider_kimi.adapter import KimiLLMProvider
from beddel_provider_kimi.errors import ADAPT_KIMI_PARAM_REJECTED


class TestMoonshotTimeoutEnv:
    """MOONSHOT_TIMEOUT env var configuration tests."""

    def test_moonshot_timeout_env_sets_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC1: MOONSHOT_TIMEOUT env var is used when no explicit timeout is passed."""
        monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
        monkeypatch.setenv("MOONSHOT_TIMEOUT", "300")

        provider = KimiLLMProvider()

        assert provider._timeout == 300.0

    def test_explicit_timeout_overrides_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC2: Explicit constructor timeout takes priority over env var."""
        monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
        monkeypatch.setenv("MOONSHOT_TIMEOUT", "300")

        provider = KimiLLMProvider(timeout=60)

        assert provider._timeout == 60

    def test_missing_env_preserves_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC3: Without env var or explicit timeout, default (120) is used."""
        monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
        monkeypatch.delenv("MOONSHOT_TIMEOUT", raising=False)

        provider = KimiLLMProvider()

        assert provider._timeout == 120

    def test_invalid_non_numeric_env_raises_adapter_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC4: Non-numeric MOONSHOT_TIMEOUT raises AdapterError."""
        monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
        monkeypatch.setenv("MOONSHOT_TIMEOUT", "not-a-number")

        with pytest.raises(AdapterError) as exc_info:
            KimiLLMProvider()

        assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED
        assert "MOONSHOT_TIMEOUT" in str(exc_info.value)

    def test_negative_env_raises_adapter_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC4: Negative MOONSHOT_TIMEOUT raises AdapterError."""
        monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
        monkeypatch.setenv("MOONSHOT_TIMEOUT", "-5")

        with pytest.raises(AdapterError) as exc_info:
            KimiLLMProvider()

        assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED

    def test_zero_env_raises_adapter_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC4: Zero MOONSHOT_TIMEOUT raises AdapterError."""
        monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
        monkeypatch.setenv("MOONSHOT_TIMEOUT", "0")

        with pytest.raises(AdapterError) as exc_info:
            KimiLLMProvider()

        assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED

    def test_explicit_zero_timeout_raises_adapter_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit timeout=0 in constructor raises AdapterError."""
        monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
        monkeypatch.delenv("MOONSHOT_TIMEOUT", raising=False)

        with pytest.raises(AdapterError) as exc_info:
            KimiLLMProvider(timeout=0)

        assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED
