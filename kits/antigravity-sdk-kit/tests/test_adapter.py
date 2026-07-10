"""Unit tests for AntigravityAgentAdapter.

Tests cover: happy paths (execute/stream), sandbox mapping, error handling
(invalid sandbox, import error, timeout), and output_schema forwarding.
All tests use mocked google.adk — no real Gemini API calls.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from beddel.domain.errors import AgentError
from beddel.error_codes import (
    AGENT_EXECUTION_FAILED,
    AGENT_NOT_CONFIGURED,
    AGENT_TIMEOUT,
)

from .conftest import MockContent, MockEvent, MockPart, MockSession


# ---------------------------------------------------------------------------
# Test 1: execute happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_execute_happy_path(adapter, mock_runner_with_text_events):
    """Runner yields text events → AgentResult has correct output."""
    mock_runner_with_text_events(["Hello", " world"])

    result = await adapter.execute("Say hello")

    assert result.exit_code == 0
    assert result.output == "Hello\n world"
    assert result.agent_id == "antigravity-sdk"
    assert len(result.events) == 2
    assert result.events[0] == {"type": "text", "text": "Hello", "author": "agent"}
    assert result.events[1] == {"type": "text", "text": " world", "author": "agent"}


# ---------------------------------------------------------------------------
# Test 2: stream happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_stream_happy_path(adapter, mock_runner_with_mixed_events):
    """Runner yields text + tool_use events → stream yields correct dicts."""
    mock_runner_with_mixed_events(
        [
            {"type": "text", "text": "Analyzing..."},
            {"type": "tool_use", "name": "read_file", "args": {"path": "/tmp/x.py"}},
            {"type": "text", "text": "Done."},
        ]
    )

    events: list[dict[str, Any]] = []
    async for event in adapter.stream("Analyze code"):
        events.append(event)

    assert events[0] == {"type": "text", "text": "Analyzing..."}
    assert events[1] == {
        "type": "tool_use",
        "name": "read_file",
        "input": {"path": "/tmp/x.py"},
    }
    assert events[2] == {"type": "text", "text": "Done."}
    # Last event is always "complete"
    assert events[3]["type"] == "complete"
    assert events[3]["output"] == "Analyzing...\nDone."
    assert events[3]["exit_code"] == 0


# ---------------------------------------------------------------------------
# Test 3: sandbox "read-only" → safety_policy "deny_all"
# ---------------------------------------------------------------------------


def test_sandbox_read_only(adapter):
    """sandbox='read-only' maps to safety_policy='deny_all'."""
    config = adapter._build_config(sandbox="read-only")
    assert config["safety_policy"] == "deny_all"


# ---------------------------------------------------------------------------
# Test 4: sandbox "workspace-write" → safety_policy "workspace_only"
# ---------------------------------------------------------------------------


def test_sandbox_workspace_write(adapter):
    """sandbox='workspace-write' maps to safety_policy='workspace_only'."""
    config = adapter._build_config(sandbox="workspace-write")
    assert config["safety_policy"] == "workspace_only"


# ---------------------------------------------------------------------------
# Test 5: sandbox "danger-full-access" → safety_policy "allow"
# ---------------------------------------------------------------------------


def test_sandbox_full_access(adapter):
    """sandbox='danger-full-access' maps to safety_policy='allow'."""
    config = adapter._build_config(sandbox="danger-full-access")
    assert config["safety_policy"] == "allow"


# ---------------------------------------------------------------------------
# Test 6: invalid sandbox raises AgentError
# ---------------------------------------------------------------------------


def test_invalid_sandbox_raises_error(adapter):
    """Unrecognized sandbox value raises AgentError(AGENT_EXECUTION_FAILED)."""
    with pytest.raises(AgentError) as exc_info:
        adapter._build_config(sandbox="unknown")

    assert exc_info.value.code == AGENT_EXECUTION_FAILED
    assert "unknown" in exc_info.value.message
    assert exc_info.value.details["sandbox"] == "unknown"


# ---------------------------------------------------------------------------
# Test 7: google-adk not installed raises AgentError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_import_error_raises_not_configured():
    """When google.adk is not importable, execute raises AGENT_NOT_CONFIGURED."""
    # Remove all mock google modules to simulate missing package
    modules_to_remove = [
        "google",
        "google.adk",
        "google.adk.agents",
        "google.adk.runners",
        "google.adk.sessions",
        "google.genai",
        "google.genai.types",
    ]

    with patch.dict(sys.modules, {k: None for k in modules_to_remove}):
        # We need a fresh adapter because the class itself doesn't cache imports
        from beddel_antigravity_sdk.adapter import AntigravityAgentAdapter

        adapter = AntigravityAgentAdapter(model="gemini-2.5-flash", timeout=5)

        with pytest.raises(AgentError) as exc_info:
            await adapter.execute("Hello")

        assert exc_info.value.code == AGENT_NOT_CONFIGURED
        assert "google-adk" in exc_info.value.message


# ---------------------------------------------------------------------------
# Test 8: timeout raises AgentError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_timeout_raises_agent_error(adapter):
    """Execution exceeding timeout raises AgentError(AGENT_TIMEOUT)."""

    # Create a slow async generator that sleeps longer than the adapter timeout
    async def _slow_gen(*args: Any, **kwargs: Any):
        await asyncio.sleep(60)  # Way longer than the 30s timeout
        yield MockEvent(content=MockContent(parts=[MockPart(text="late")]))

    # Patch Runner and session service
    mock_runner_instance = MagicMock()
    mock_runner_instance.run_async = _slow_gen

    # Access the runners mock via sys.modules
    runners_mod = sys.modules["google.adk.runners"]
    runners_mod.Runner.return_value = mock_runner_instance

    sessions_mod = sys.modules["google.adk.sessions"]
    mock_session_service = AsyncMock()
    mock_session_service.create_session = AsyncMock(
        return_value=MockSession(id="timeout-session")
    )
    sessions_mod.InMemorySessionService.return_value = mock_session_service

    # Use a very short timeout adapter
    from beddel_antigravity_sdk.adapter import AntigravityAgentAdapter

    short_adapter = AntigravityAgentAdapter(model="gemini-2.5-flash", timeout=1)

    with pytest.raises(AgentError) as exc_info:
        await short_adapter.execute("Do something slow")

    assert exc_info.value.code == AGENT_TIMEOUT
    assert "timed out" in exc_info.value.message


# ---------------------------------------------------------------------------
# Test 9: output_schema maps to config
# ---------------------------------------------------------------------------


def test_output_schema_passed_to_config(adapter):
    """output_schema dict is forwarded in the built config."""
    schema = {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"],
    }
    config = adapter._build_config(output_schema=schema)
    assert config["output_schema"] == schema


def test_output_schema_not_set_when_none(adapter):
    """When output_schema is None, config does not contain the key."""
    config = adapter._build_config()
    assert "output_schema" not in config
