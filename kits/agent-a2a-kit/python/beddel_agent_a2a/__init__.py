"""Beddel A2A Protocol agent adapter kit (client only).

Outbound A2A protocol client:
- Client: A2AAgentAdapter — calls external A2A agents via IAgentAdapter
- Discovery: discover_agent — fetches Agent Card from remote endpoints

Server components (BeddelA2AExecutor, build_agent_card) have been moved
to the companion kit: serve-a2a-kit (beddel_serve_a2a).
"""

from beddel_agent_a2a.adapter import A2AAgentAdapter
from beddel_agent_a2a.discovery import discover_agent

__all__ = [
    "A2AAgentAdapter",
    "discover_agent",
]
