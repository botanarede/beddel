"""Beddel Kiro CLI agent adapter kit."""

from __future__ import annotations

from typing import Any

__all__ = ["KiroCLIAgentAdapter"]


def __getattr__(name: str) -> Any:
    """Load the SDK-dependent adapter without burdening the stdlib hook."""
    if name == "KiroCLIAgentAdapter":
        from beddel_agent_kiro.adapter import KiroCLIAgentAdapter

        return KiroCLIAgentAdapter
    raise AttributeError(name)
