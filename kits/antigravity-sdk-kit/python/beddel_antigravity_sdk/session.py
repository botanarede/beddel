"""Antigravity session state management.

Provides ``AntigravitySession`` — a scoped state container for ToolContext
within one agent-exec step — and ``ToolContext`` — a wrapper passed to all
tool functions containing the session and adapter reference.

Cross-step persistence uses file-based JSON storage at
``{save_dir}/{conversation_id}.json``.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from beddel.domain.errors import AgentError

if TYPE_CHECKING:
    from beddel_antigravity_sdk.adapter import AntigravityAgentAdapter

__all__ = ["AntigravitySession", "AntigravityStateSync", "ToolContext"]

logger = logging.getLogger(__name__)

# Error code constants (architecture §35.10)
ANTIGRAVITY_SESSION_NOT_FOUND: str = "BEDDEL-AGENT-755"
ANTIGRAVITY_MCP_FAILED: str = "BEDDEL-AGENT-754"

# Characters forbidden in conversation_id (path traversal prevention)
_FORBIDDEN_ID_CHARS = frozenset("/\\..")


def _validate_conversation_id(conversation_id: str) -> None:
    """Validate conversation_id does not contain path traversal sequences.

    Raises:
        ValueError: If the ID contains ``..``, ``/``, ``\\``, or is empty.
    """
    if not conversation_id:
        raise ValueError("conversation_id must not be empty")
    if ".." in conversation_id or "/" in conversation_id or "\\" in conversation_id:
        raise ValueError(
            f"Invalid conversation_id: {conversation_id!r} "
            "(must not contain '..', '/', or '\\\\')"
        )


@dataclass
class AntigravitySession:
    """Scoped state container for ToolContext within one agent-exec step.

    Attributes:
        state: Mutable dict shared across tool calls within a step.
        conversation_id: Identifier for cross-step persistence.
            Auto-generated if not provided.
        save_dir: Directory for file-based persistence.
        usage: Token/cost metrics accumulated during execution.
    """

    state: dict[str, Any] = field(default_factory=dict)
    conversation_id: str | None = None
    save_dir: str | None = None
    usage: dict[str, int] = field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
    )

    def save(self) -> Path:
        """Persist session state to ``{save_dir}/{conversation_id}.json``.

        Returns:
            Path to the saved JSON file.

        Raises:
            ValueError: If ``save_dir`` or ``conversation_id`` is not set,
                or if ``conversation_id`` contains path traversal characters.
        """
        if not self.save_dir:
            raise ValueError("Cannot save session: save_dir is not configured")
        if not self.conversation_id:
            self.conversation_id = str(uuid.uuid4())

        # Security: prevent path traversal via conversation_id
        _validate_conversation_id(self.conversation_id)

        save_path = Path(self.save_dir)
        save_path.mkdir(parents=True, exist_ok=True)

        file_path = save_path / f"{self.conversation_id}.json"
        payload = {
            "conversation_id": self.conversation_id,
            "state": self.state,
            "usage": self.usage,
        }
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.debug("Session saved to %s", file_path)
        return file_path

    @classmethod
    def load(cls, conversation_id: str, save_dir: str) -> AntigravitySession:
        """Load a previously saved session from disk.

        Args:
            conversation_id: The conversation identifier to load.
            save_dir: Directory where sessions are persisted.

        Returns:
            A new ``AntigravitySession`` populated from the saved data.

        Raises:
            AgentError: ``BEDDEL-AGENT-755`` if the conversation file
                does not exist.
            ValueError: If ``conversation_id`` contains path traversal
                characters.
        """
        # Security: prevent path traversal via conversation_id
        _validate_conversation_id(conversation_id)

        file_path = Path(save_dir) / f"{conversation_id}.json"
        if not file_path.exists():
            raise AgentError(
                code=ANTIGRAVITY_SESSION_NOT_FOUND,
                message=f"Session not found: {conversation_id}",
                details={
                    "conversation_id": conversation_id,
                    "save_dir": save_dir,
                    "path": str(file_path),
                },
            )

        data = json.loads(file_path.read_text(encoding="utf-8"))
        return cls(
            state=data.get("state", {}),
            conversation_id=data.get("conversation_id", conversation_id),
            save_dir=save_dir,
            usage=data.get(
                "usage",
                {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            ),
        )


class AntigravityStateSync:
    """Bidirectional sync between AntigravitySession.state and Beddel IStateStore.

    Provides async methods to load state from an ``IStateStore``-compatible
    object into a session, and to save session state back to the store.

    The ``state_store`` parameter is duck-typed (``Any``) — it must conform
    to the ``IStateStore`` protocol (i.e., expose async ``save(key, state)``
    and ``load(key)`` methods) but no hard import is required.

    Exceptions raised by the underlying state store propagate unchanged
    to the caller.  This is deliberate — silent data loss on save/load
    is a correctness bug, not an observability nicety.

    Args:
        state_store: An object implementing the ``IStateStore`` protocol
            (``save``, ``load`` async methods).
    """

    def __init__(self, state_store: Any) -> None:
        self._state_store = state_store

    async def load_into_session(self, session: AntigravitySession, key: str) -> None:
        """Load persisted state into the given session.

        Calls ``state_store.load(key)``.  If the result is not ``None``,
        replaces ``session.state`` with the loaded dict.  If ``None``
        (no checkpoint exists), ``session.state`` is left unchanged.

        Args:
            session: The session whose state may be replaced.
            key: The state-store key to load from (maps to
                ``IStateStore.load(workflow_id)``).
        """
        loaded = await self._state_store.load(key)
        if loaded is not None:
            session.state = loaded

    async def save_from_session(self, session: AntigravitySession, key: str) -> None:
        """Persist the session's current state to the store.

        Calls ``state_store.save(key, session.state)``.

        Args:
            session: The session whose state will be persisted.
            key: The state-store key to save under (maps to
                ``IStateStore.save(workflow_id, state)``).
        """
        await self._state_store.save(key, session.state)


@dataclass
class ToolContext:
    """Context passed to all antigravity tool functions.

    Wraps an ``AntigravitySession`` and an adapter reference so tools
    can access session state, adapter configuration, and execute
    sub-operations against the Antigravity SDK.

    Attributes:
        session: The current session state container.
        adapter: Reference to the parent adapter instance.
    """

    session: AntigravitySession
    adapter: AntigravityAgentAdapter
