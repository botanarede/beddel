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

__all__ = ["AntigravitySession", "ToolContext"]

logger = logging.getLogger(__name__)

# Error code constants (architecture §35.10)
ANTIGRAVITY_SESSION_NOT_FOUND: str = "BEDDEL-AGENT-755"


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
            ValueError: If ``save_dir`` or ``conversation_id`` is not set.
        """
        if not self.save_dir:
            raise ValueError("Cannot save session: save_dir is not configured")
        if not self.conversation_id:
            self.conversation_id = str(uuid.uuid4())

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
        """
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
