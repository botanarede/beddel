"""Antigravity SDK Kit — Bridge kit for Google ADK agent runtime.

Exposes AntigravityAgentAdapter (IAgentAdapter implementation) that bridges
Google Antigravity SDK's LocalAgentConfig-based agent runtime into Beddel's
agent-exec primitive, plus AntigravitySession for state management and
ToolContext for tool function invocation.
"""

from __future__ import annotations

__all__ = ["AntigravityAgentAdapter", "AntigravitySession", "ToolContext"]


def __getattr__(name: str) -> object:
    if name == "AntigravityAgentAdapter":
        from beddel_antigravity_sdk.adapter import AntigravityAgentAdapter

        return AntigravityAgentAdapter
    if name == "AntigravitySession":
        from beddel_antigravity_sdk.session import AntigravitySession

        return AntigravitySession
    if name == "ToolContext":
        from beddel_antigravity_sdk.session import ToolContext

        return ToolContext
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
