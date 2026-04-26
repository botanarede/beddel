"""Shared fixtures for provider-gemini-kit tests.

When ``google-genai`` is installed, tests run against the REAL genai classes.
When absent, mock modules are injected into ``sys.modules`` so the
``try/except ImportError`` guard in ``adapter.py`` resolves to lightweight
stand-ins.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Path setup — add kit src/ so ``import beddel_provider_gemini`` resolves.
# ``beddel`` itself must be installed (pip install beddel).
# ---------------------------------------------------------------------------

_KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_KIT_ROOT / "src"))


# ---------------------------------------------------------------------------
# Detect whether real google-genai is available
# ---------------------------------------------------------------------------

try:
    from google.genai import types as _real_types  # noqa: F401

    HAS_REAL_GENAI = True
except ImportError:
    HAS_REAL_GENAI = False


# ---------------------------------------------------------------------------
# Mock genai classes (used only when real SDK is absent)
# ---------------------------------------------------------------------------


class MockGenerateContentConfig:
    """Stand-in for ``google.genai.types.GenerateContentConfig``."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockClient:
    """Stand-in for ``google.genai.Client``."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.aio = MagicMock()



if not HAS_REAL_GENAI:
    # Build mock module hierarchy for google.genai
    _mock_google = MagicMock()
    _mock_genai = MagicMock()
    _mock_types = MagicMock()

    _mock_genai.Client = MockClient
    _mock_types.GenerateContentConfig = MockGenerateContentConfig

    _mock_google.genai = _mock_genai

    sys.modules.setdefault("google", _mock_google)
    sys.modules["google.genai"] = _mock_genai
    sys.modules["google.genai.types"] = _mock_types

    # Force-reload beddel_provider_gemini modules so they pick up mocks.
    for _mod_name in list(sys.modules):
        if _mod_name.startswith("beddel_provider_gemini"):
            del sys.modules[_mod_name]

    # Re-import so adapter sees the mocked genai
    importlib.import_module("beddel_provider_gemini")
