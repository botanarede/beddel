"""Beddel A2A Protocol agent adapter kit.

Bidirectional A2A protocol kit:
- Client (outbound): A2AAgentAdapter — calls external A2A agents via IAgentAdapter
- Server (inbound): BeddelA2AExecutor — exposes Beddel workflows as A2A agents
- Discovery: discover_agent — fetches Agent Card from remote endpoints
"""

from beddel_agent_a2a.adapter import A2AAgentAdapter
from beddel_agent_a2a.discovery import discover_agent
from beddel_agent_a2a.server import BeddelA2AExecutor, build_agent_card

__all__ = [
    "A2AAgentAdapter",
    "BeddelA2AExecutor",
    "build_agent_card",
    "discover_agent",
]
