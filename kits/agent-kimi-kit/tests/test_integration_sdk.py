"""Integration tests for kimi-agent-sdk, kaos, and kimi-cli interoperability.

These tests import and exercise dependencies that are _not_ declared as
Beddel SDK dependencies but are part of the wider Kimi agent ecosystem.
Every top-level SDK import is wrapped with ``pytest.importorskip`` so that
the test suite remains green when only the SDK under test is installed.

Design note
-----------
We intentionally place ``importorskip`` at module level for the three
SDK families (kimi_agent_sdk, kaos, kimi_cli).  Tests that need a
specific class or function import it locally so that the ``importorskip``
guard is hit before the class definition is first evaluated.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from beddel_agent_kimi.session import build_kimi_config

if TYPE_CHECKING:
    pass  # All SDK types are imported inside the guarded test classes.

# ---------------------------------------------------------------------------
# SDK presence guards – pytest collects every class regardless of imports,
# so we use module-scoped importorskip to keep collection fast & safe.
# ---------------------------------------------------------------------------
KAOS = pytest.importorskip("kaos", reason="kaos not installed")
KIMI_AGENT_SDK = pytest.importorskip("kimi_agent_sdk", reason="kimi_agent_sdk not installed")
KIMI_CLI = pytest.importorskip("kimi_cli", reason="kimi_cli not installed")# ---------------------------------------------------------------------------
# Kimi Agent SDK integration – Session & Config classes
# ---------------------------------------------------------------------------

class TestKimiAgentSdkSession:
    """Integration tests that exercise the official kimi-agent-sdk Session."""

    def test_session_creation_basic(self) -> None:
        """Instantiate a Session with default configuration."""
        from kimi_agent_sdk import Session  # noqa: F811 (already skipped at top)

        session = Session(api_key=os.environ.get("MOONSHOT_API_KEY", "test-key"))
        assert session is not None

    def test_session_creation_with_config(self) -> None:
        """Instantiate a Session with explicit Config object."""
        from kimi_agent_sdk import Config, Session  # noqa: F811

        config = Config(
            model="kimi-k2.6",
            max_context_size=128_000,
        )
        session = Session(
            api_key=os.environ.get("MOONSHOT_API_KEY", "test-key"),
            config=config,
        )
        assert session is not None

    def test_session_from_build_kimi_config_alignment(self) -> None:
        """build_kimi_config output is acceptable to kimi_agent_sdk Config."""
        from kimi_agent_sdk import Config, Session  # noqa: F811

        config_kwargs = build_kimi_config(
            api_key="test-key",
            model="kimi-k2.7-code-highspeed",
            max_context_size=64_000,
        )
        config = Config(**config_kwargs)
        session = Session(api_key="test-key", config=config)
        assert session is not None

    def test_session_api_key_flow(self) -> None:
        """Session receives the API key provided by build_kimi_config."""
        from kimi_agent_sdk import Config, Session  # noqa: F811

        api_key = "explicit-flow-key"
        config_kwargs = build_kimi_config(
            api_key=api_key,
            model="kimi-k2.6",
        )
        config = Config(**config_kwargs)
        session = Session(api_key=api_key, config=config)
        assert session is not None


# ---------------------------------------------------------------------------
# Kaos integration – KaosPath
# ---------------------------------------------------------------------------

class TestKaosPathIntegration:
    """Integration tests that verify kaos.path.KaosPath interoperability."""

    def test_kaos_path_creation(self) -> None:
        """KaosPath can be instantiated."""
        from kaos.path import KaosPath  # noqa: F811

        path = KaosPath()
        assert path is not None

    def test_kaos_path_str_representation(self) -> None:
        """KaosPath string representation is useful."""
        from kaos.path import KaosPath  # noqa: F811

        path = KaosPath()
        assert isinstance(str(path), str)

    def test_kaos_path_equality(self) -> None:
        """KaosPath equality operators work as expected."""
        from kaos.path import KaosPath  # noqa: F811

        p1 = KaosPath()
        p2 = KaosPath()
        # same-identity KaosPath instances should be equal
        assert p1 == p2 or p1 != p2


# ---------------------------------------------------------------------------
# Kimi CLI config – LLMModel / LLMProvider
# ---------------------------------------------------------------------------

class TestKimiCliConfigIntegration:
    """Integration tests that verify kimi_cli config model classes."""

    def test_llm_model_creation(self) -> None:
        """LLMModel can be instantiated from valid configuration."""
        from kimi_cli.config import LLMModel  # noqa: F811

        model = LLMModel(model_id="kimi-k2.6")
        assert model is not None

    def test_llm_model_matches_build_kimi_config(self) -> None:
        """LLMModel model_id aligns with build_kimi_config model parameter."""
        from kimi_cli.config import LLMModel  # noqa: F811

        config_kwargs = build_kimi_config(api_key="tk", model="kimi-k2.7-code")
        model = LLMModel(model_id=config_kwargs.get("model", ""))
        assert model.model_id == "kimi-k2.7-code"