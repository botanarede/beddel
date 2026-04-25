"""Beddel bridge-adk-kit — ADK Bridge for Beddel workflows.

Re-exports the public API from the kit's modules:

- :class:`BeddelADKTool` — Wraps a Beddel YAML workflow as an ADK FunctionTool
- :func:`create_adk_agent` — Factory for creating ADK agents with Beddel workflow tools
"""

from __future__ import annotations

__all__ = ["BeddelADKTool", "create_adk_agent"]


def __getattr__(name: str) -> object:
    """Lazy-load kit symbols to avoid import-time side effects."""
    if name == "BeddelADKTool":
        from beddel_bridge_adk.tool import BeddelADKTool

        return BeddelADKTool
    if name == "create_adk_agent":
        from beddel_bridge_adk.agent import create_adk_agent

        return create_adk_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
