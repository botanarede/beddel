"""Configure sys.path and shared fixtures for agentrq-approval-kit tests.

Adds the kit's ``python/`` to sys.path so ``import beddel_agentrq_approval``
resolves.  The ``beddel`` SDK itself must be installed (``pip install beddel``).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

_KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_KIT_ROOT / "python"))


# ---------------------------------------------------------------------------
# MCP Mock Infrastructure (shared with test files)
# ---------------------------------------------------------------------------


@dataclass
class MockContent:
    """Simulates MCP result content item with a text attribute."""

    text: str


@dataclass
class MockResult:
    """Simulates MCP tool call result with content list."""

    content: list[MockContent] = field(default_factory=list)


def make_mock_session(
    call_tool_side_effects: list[MockResult] | None = None,
) -> AsyncMock:
    """Create a mock MCP ClientSession with configurable call_tool responses.

    Args:
        call_tool_side_effects: Ordered list of MockResult to return on
            successive ``call_tool`` invocations.  Defaults to a standard
            createTask + reply pair.

    Returns:
        An AsyncMock simulating a ``ClientSession`` instance.
    """
    if call_tool_side_effects is None:
        call_tool_side_effects = [
            MockResult(content=[MockContent(text="task-abc-123")]),  # createTask
            MockResult(content=[MockContent(text="ok")]),  # reply
        ]

    session = AsyncMock()
    session.call_tool = AsyncMock(side_effect=call_tool_side_effects)
    return session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_session() -> AsyncMock:
    """Provide a default mock MCP session (createTask + reply responses)."""
    return make_mock_session()


@pytest.fixture()
def gate_with_mock(mock_session: AsyncMock):
    """Provide an AgentRQApprovalGate with an injected mock session.

    The gate is pre-connected (session injected directly) so no MCP traffic
    occurs on ``_ensure_connected``.
    """
    from beddel_agentrq_approval.adapter import AgentRQApprovalGate

    gate = AgentRQApprovalGate(
        workspace_url="https://mock.agentrq.dev/mcp/ws1?token=test",
        timeout_seconds=300,
    )
    gate._session = mock_session
    return gate
