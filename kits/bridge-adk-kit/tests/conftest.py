"""Shared fixtures for bridge-adk-kit tests.

Injects mock ``google.adk`` modules into ``sys.modules`` BEFORE any test
imports ``beddel_bridge_adk``, so the ``try/except ImportError`` guard in
``tool.py`` and ``agent.py`` resolves to the mocked classes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path setup for standalone kit test execution
# ---------------------------------------------------------------------------

_KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_KIT_ROOT / "src"))

_PROJECT_ROOT = _KIT_ROOT.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src" / "beddel-py" / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "src" / "beddel-py" / "tests"))

# ---------------------------------------------------------------------------
# Mock ADK modules — injected before any beddel_bridge_adk import
# ---------------------------------------------------------------------------

_mock_google = MagicMock()
_mock_google_adk = MagicMock()
_mock_google_adk_tools = MagicMock()
_mock_google_adk_agents = MagicMock()


class MockFunctionTool:
    """Stand-in for ``google.adk.tools.FunctionTool``."""

    def __init__(self, func: Any = None, **kwargs: Any) -> None:
        self.func = func


class MockToolContext:
    """Stand-in for ``google.adk.tools.ToolContext``."""

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self.state: dict[str, Any] = state or {}


class MockAgent:
    """Stand-in for ``google.adk.agents.Agent``."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        for k, v in kwargs.items():
            setattr(self, k, v)


_mock_google_adk_tools.FunctionTool = MockFunctionTool
_mock_google_adk_tools.ToolContext = MockToolContext
_mock_google_adk_agents.Agent = MockAgent

# Wire the mock hierarchy so attribute access works:
_mock_google.adk = _mock_google_adk
_mock_google_adk.tools = _mock_google_adk_tools
_mock_google_adk.agents = _mock_google_adk_agents

# Patch sys.modules BEFORE any test file imports beddel_bridge_adk.
sys.modules.setdefault("google", _mock_google)
sys.modules.setdefault("google.adk", _mock_google_adk)
sys.modules.setdefault("google.adk.tools", _mock_google_adk_tools)
sys.modules.setdefault("google.adk.agents", _mock_google_adk_agents)

# Force-reload beddel_bridge_adk modules so they pick up the mocked ADK.
for _mod_name in list(sys.modules):
    if _mod_name.startswith("beddel_bridge_adk"):
        del sys.modules[_mod_name]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_VALID_WORKFLOW_YAML = """\
id: test-workflow
name: Test Workflow
description: A test workflow for unit tests
version: "1.0"
steps:
  - id: step-1
    primitive: llm
    config:
      model: gpt-4o-mini
      prompt: "Hello"
"""

_INVALID_WORKFLOW_YAML = """\
id: test-workflow
name: Test Workflow
steps:
  - id: step-1
    primitive: llm
    config:
      model: gpt-4o-mini
      prompt: "$badref"
"""


@pytest.fixture()
def valid_workflow_yaml(tmp_path: Any) -> str:
    """Write a valid workflow YAML to a temp file and return its path."""
    p = tmp_path / "valid.yaml"
    p.write_text(_VALID_WORKFLOW_YAML, encoding="utf-8")
    return str(p)


@pytest.fixture()
def invalid_workflow_yaml(tmp_path: Any) -> str:
    """Write an invalid workflow YAML to a temp file and return its path."""
    p = tmp_path / "invalid.yaml"
    p.write_text(_INVALID_WORKFLOW_YAML, encoding="utf-8")
    return str(p)
