"""Unit tests for AntigravitySession, AntigravityStateSync, and ToolContext.

Tests cover: session creation, save/load lifecycle, error paths
(missing save_dir, missing file), ToolContext construction, and
AntigravityStateSync load/save with IStateStore duck-typing.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from beddel.domain.errors import AgentError

from beddel_antigravity_sdk.session import (
    ANTIGRAVITY_SESSION_NOT_FOUND,
    AntigravitySession,
    AntigravityStateSync,
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


# ---------------------------------------------------------------------------
# Test: path traversal in conversation_id rejected (C2 fix)
# ---------------------------------------------------------------------------


def test_session_save_rejects_path_traversal(tmp_path: Path):
    """save() rejects conversation_id with path traversal characters."""
    session = AntigravitySession(
        state={"x": 1},
        conversation_id="../../../etc/passwd",
        save_dir=str(tmp_path),
    )

    with pytest.raises(ValueError, match="must not contain"):
        session.save()


def test_session_load_rejects_path_traversal(tmp_path: Path):
    """load() rejects conversation_id with path traversal characters."""
    with pytest.raises(ValueError, match="must not contain"):
        AntigravitySession.load("../../etc/shadow", str(tmp_path))


def test_session_save_rejects_slash(tmp_path: Path):
    """save() rejects conversation_id containing forward slash."""
    session = AntigravitySession(
        state={},
        conversation_id="sub/dir",
        save_dir=str(tmp_path),
    )

    with pytest.raises(ValueError, match="must not contain"):
        session.save()


# ---------------------------------------------------------------------------
# K5.5: AntigravityStateSync — IStateStore bridge tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_state_sync_load_replaces_session_state():
    """load_into_session replaces session.state when store returns data."""
    mock_store = AsyncMock()
    mock_store.load = AsyncMock(return_value={"restored": True, "count": 42})

    session = AntigravitySession(state={"original": "data"})
    sync = AntigravityStateSync(mock_store)

    await sync.load_into_session(session, "my-key")

    assert session.state == {"restored": True, "count": 42}
    mock_store.load.assert_awaited_once_with("my-key")


@pytest.mark.asyncio()
async def test_state_sync_load_noop_when_store_returns_none():
    """load_into_session is a no-op when store.load() returns None."""
    mock_store = AsyncMock()
    mock_store.load = AsyncMock(return_value=None)

    original_state = {"keep": "this"}
    session = AntigravitySession(state=original_state)
    sync = AntigravityStateSync(mock_store)

    await sync.load_into_session(session, "absent-key")

    assert session.state is original_state
    assert session.state == {"keep": "this"}
    mock_store.load.assert_awaited_once_with("absent-key")


@pytest.mark.asyncio()
async def test_state_sync_save_calls_store_with_correct_args():
    """save_from_session calls state_store.save(key, session.state)."""
    mock_store = AsyncMock()
    mock_store.save = AsyncMock(return_value=None)

    session = AntigravitySession(state={"data": "to_persist", "n": 7})
    sync = AntigravityStateSync(mock_store)

    await sync.save_from_session(session, "save-key-1")

    mock_store.save.assert_awaited_once_with(
        "save-key-1", {"data": "to_persist", "n": 7}
    )


@pytest.mark.asyncio()
async def test_state_sync_load_propagates_store_exception():
    """Exceptions from state_store.load() propagate unchanged."""
    mock_store = AsyncMock()
    mock_store.load = AsyncMock(side_effect=RuntimeError("connection lost"))

    session = AntigravitySession(state={"untouched": True})
    sync = AntigravityStateSync(mock_store)

    with pytest.raises(RuntimeError, match="connection lost"):
        await sync.load_into_session(session, "any-key")

    # Session state must be unchanged
    assert session.state == {"untouched": True}


@pytest.mark.asyncio()
async def test_state_sync_save_propagates_store_exception():
    """Exceptions from state_store.save() propagate unchanged."""
    mock_store = AsyncMock()
    mock_store.save = AsyncMock(side_effect=IOError("disk full"))

    session = AntigravitySession(state={"important": "data"})
    sync = AntigravityStateSync(mock_store)

    with pytest.raises(IOError, match="disk full"):
        await sync.save_from_session(session, "save-key")

    mock_store.save.assert_awaited_once()
