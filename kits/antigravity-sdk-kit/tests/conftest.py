"""Shared fixtures for antigravity-sdk-kit tests.

Mocks `google.adk` and `google.genai` modules so tests never call real
Gemini API. The adapter is tested in complete isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path setup — add kit src/ so ``import beddel_antigravity_sdk`` resolves.
# ---------------------------------------------------------------------------

_KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_KIT_ROOT / "python"))


# ---------------------------------------------------------------------------
# Mock ADK objects
# ---------------------------------------------------------------------------


class MockPart:
    """Stand-in for google.genai.types.Part."""

    def __init__(self, text: str | None = None, function_call: Any = None) -> None:
        self.text = text
        self.function_call = function_call


class MockFunctionCall:
    """Stand-in for a function_call attribute."""

    def __init__(self, name: str, args: dict[str, Any] | None = None) -> None:
        self.name = name
        self.args = args or {}


class MockContent:
    """Stand-in for google.genai.types.Content."""

    def __init__(self, parts: list[Any] | None = None, **kwargs: Any) -> None:
        self.parts = parts or []


class MockEvent:
    """Stand-in for Runner event."""

    def __init__(self, content: Any = None, author: str = "agent") -> None:
        self.content = content
        self.author = author


class MockSession:
    """Stand-in for session returned by InMemorySessionService."""

    def __init__(self, id: str = "test-session") -> None:
        self.id = id


# ---------------------------------------------------------------------------
# Inject mock google.adk / google.genai into sys.modules
# ---------------------------------------------------------------------------


def _inject_mock_adk() -> dict[str, MagicMock]:
    """Inject mock google.adk modules and return the mock objects."""
    mock_google = MagicMock()
    mock_adk = MagicMock()
    mock_agents = MagicMock()
    mock_runners = MagicMock()
    mock_sessions = MagicMock()
    mock_tools = MagicMock()
    mock_tools_mcp = MagicMock()
    mock_genai = MagicMock()
    mock_genai_types = MagicMock()

    # Wire up Content/Part constructors to our mocks
    mock_genai_types.Content = MockContent
    mock_genai_types.Part = MockPart

    # Wire module hierarchy
    mock_google.adk = mock_adk
    mock_google.genai = mock_genai
    mock_adk.agents = mock_agents
    mock_adk.runners = mock_runners
    mock_adk.sessions = mock_sessions
    mock_adk.tools = mock_tools
    mock_tools.mcp = mock_tools_mcp
    mock_genai.types = mock_genai_types

    modules = {
        "google": mock_google,
        "google.adk": mock_adk,
        "google.adk.agents": mock_agents,
        "google.adk.runners": mock_runners,
        "google.adk.sessions": mock_sessions,
        "google.adk.tools": mock_tools,
        "google.adk.tools.mcp": mock_tools_mcp,
        "google.genai": mock_genai,
        "google.genai.types": mock_genai_types,
    }
    sys.modules.update(modules)

    return {
        "google": mock_google,
        "adk": mock_adk,
        "agents": mock_agents,
        "runners": mock_runners,
        "sessions": mock_sessions,
        "tools": mock_tools,
        "tools_mcp": mock_tools_mcp,
        "genai": mock_genai,
        "genai_types": mock_genai_types,
    }


# Inject before any adapter import
_mocks = _inject_mock_adk()

# Force-reload beddel_antigravity_sdk modules so they pick up mocked ADK
for _mod_name in list(sys.modules):
    if _mod_name.startswith("beddel_antigravity_sdk"):
        del sys.modules[_mod_name]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def adapter():
    """Create an AntigravityAgentAdapter with default settings."""
    from beddel_antigravity_sdk.adapter import AntigravityAgentAdapter

    return AntigravityAgentAdapter(
        model="gemini-2.5-flash",
        timeout=30,
    )


@pytest.fixture()
def mock_runner_with_text_events():
    """Configure mock Runner to yield text events.

    Returns a function that sets up the Runner mock to yield the given texts.
    """

    def _configure(texts: list[str]) -> None:
        events = []
        for text in texts:
            part = MockPart(text=text)
            content = MockContent(parts=[part])
            event = MockEvent(content=content, author="agent")
            events.append(event)

        async def _async_gen(*args: Any, **kwargs: Any):
            for ev in events:
                yield ev

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = _async_gen

        _mocks["runners"].Runner.return_value = mock_runner_instance

        mock_session = MockSession(id="test-session-123")
        mock_session_service = AsyncMock()
        mock_session_service.create_session = AsyncMock(return_value=mock_session)
        _mocks["sessions"].InMemorySessionService.return_value = mock_session_service

    return _configure


@pytest.fixture()
def mock_runner_with_mixed_events():
    """Configure mock Runner to yield text + tool_use events."""

    def _configure(
        events_data: list[dict[str, Any]],
    ) -> None:
        events = []
        for data in events_data:
            if data["type"] == "text":
                part = MockPart(text=data["text"])
            else:
                fc = MockFunctionCall(
                    name=data["name"],
                    args=data.get("args", {}),
                )
                part = MockPart(function_call=fc)
            content = MockContent(parts=[part])
            event = MockEvent(content=content, author=data.get("author", "agent"))
            events.append(event)

        async def _async_gen(*args: Any, **kwargs: Any):
            for ev in events:
                yield ev

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = _async_gen

        _mocks["runners"].Runner.return_value = mock_runner_instance

        mock_session = MockSession(id="test-session-456")
        mock_session_service = AsyncMock()
        mock_session_service.create_session = AsyncMock(return_value=mock_session)
        _mocks["sessions"].InMemorySessionService.return_value = mock_session_service

    return _configure
