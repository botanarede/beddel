"""Unit tests for AntigravitySession and ToolContext.

Tests cover: session creation, save/load lifecycle, error paths
(missing save_dir, missing file), and ToolContext construction.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from beddel.domain.errors import AgentError

from beddel_antigravity_sdk.session import (
    ANTIGRAVITY_SESSION_NOT_FOUND,
    AntigravitySession,
    ToolContext,
)


# ---------------------------------------------------------------------------
# Test: session creation with defaults
# ---------------------------------------------------------------------------


def test_session_creation_defaults():
    """AntigravitySession initializes with empty state and None IDs."""
    session = AntigravitySession()

    assert session.state == {}
    assert session.conversation_id is None
    assert session.save_dir is None
    assert session.usage == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


# ---------------------------------------------------------------------------
# Test: session creation with custom values
# ---------------------------------------------------------------------------


def test_session_creation_custom():
    """AntigravitySession respects provided values."""
    session = AntigravitySession(
        state={"key": "value"},
        conversation_id="conv-123",
        save_dir="/tmp/sessions",
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    )

    assert session.state == {"key": "value"}
    assert session.conversation_id == "conv-123"
    assert session.save_dir == "/tmp/sessions"
    assert session.usage["total_tokens"] == 150


# ---------------------------------------------------------------------------
# Test: session save writes correct JSON
# ---------------------------------------------------------------------------


def test_session_save_writes_json(tmp_path: Path):
    """save() persists state to {save_dir}/{conversation_id}.json."""
    session = AntigravitySession(
        state={"step": 1, "result": "ok"},
        conversation_id="test-conv-001",
        save_dir=str(tmp_path),
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )

    result_path = session.save()

    assert result_path == tmp_path / "test-conv-001.json"
    assert result_path.exists()

    data = json.loads(result_path.read_text())
    assert data["conversation_id"] == "test-conv-001"
    assert data["state"] == {"step": 1, "result": "ok"}
    assert data["usage"]["total_tokens"] == 15


# ---------------------------------------------------------------------------
# Test: session save auto-generates conversation_id
# ---------------------------------------------------------------------------


def test_session_save_autogenerates_id(tmp_path: Path):
    """save() generates a UUID conversation_id if not set."""
    session = AntigravitySession(
        state={"data": True},
        save_dir=str(tmp_path),
    )

    result_path = session.save()

    assert session.conversation_id is not None
    assert len(session.conversation_id) == 36  # UUID format
    assert result_path.exists()


# ---------------------------------------------------------------------------
# Test: session load reads correct JSON
# ---------------------------------------------------------------------------


def test_session_load_reads_json(tmp_path: Path):
    """load() deserializes a previously saved session."""
    # First save a session
    payload = {
        "conversation_id": "load-test-001",
        "state": {"loaded": True, "count": 42},
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
    }
    file_path = tmp_path / "load-test-001.json"
    file_path.write_text(json.dumps(payload))

    # Load it
    session = AntigravitySession.load("load-test-001", str(tmp_path))

    assert session.conversation_id == "load-test-001"
    assert session.state == {"loaded": True, "count": 42}
    assert session.save_dir == str(tmp_path)
    assert session.usage["total_tokens"] == 30


# ---------------------------------------------------------------------------
# Test: session load with missing file raises AgentError
# ---------------------------------------------------------------------------


def test_session_load_not_found(tmp_path: Path):
    """load() raises AgentError(BEDDEL-AGENT-755) for missing conversation."""
    with pytest.raises(AgentError) as exc_info:
        AntigravitySession.load("nonexistent-conv", str(tmp_path))

    assert exc_info.value.code == ANTIGRAVITY_SESSION_NOT_FOUND
    assert "nonexistent-conv" in exc_info.value.message
    assert exc_info.value.details["conversation_id"] == "nonexistent-conv"


# ---------------------------------------------------------------------------
# Test: session save without save_dir raises ValueError
# ---------------------------------------------------------------------------


def test_session_save_without_save_dir():
    """save() raises ValueError when save_dir is None."""
    session = AntigravitySession(state={"x": 1})

    with pytest.raises(ValueError, match="save_dir"):
        session.save()


# ---------------------------------------------------------------------------
# Test: ToolContext construction
# ---------------------------------------------------------------------------


def test_tool_context_construction():
    """ToolContext wraps session and adapter."""
    session = AntigravitySession(state={"ctx": True})
    mock_adapter = MagicMock()

    ctx = ToolContext(session=session, adapter=mock_adapter)

    assert ctx.session is session
    assert ctx.adapter is mock_adapter
    assert ctx.session.state["ctx"] is True
