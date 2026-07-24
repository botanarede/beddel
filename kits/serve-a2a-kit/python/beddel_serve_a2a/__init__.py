"""Beddel A2A Protocol server kit.

Serve-tier integration that exposes Beddel workflows as A2A-compliant agents:
- BeddelA2AExecutor: Maps Beddel workflow execution to A2A task lifecycle events
- build_agent_card: Generates an A2A Agent Card from discovered workflows
"""

from beddel_serve_a2a.server import BeddelA2AExecutor, build_agent_card

__all__ = [
    "BeddelA2AExecutor",
    "build_agent_card",
]
