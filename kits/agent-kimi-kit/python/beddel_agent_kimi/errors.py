"""Error code constants for agent-kimi-kit.

Consolidated error codes BEDDEL-AGENT-800..806 as defined in architecture §40.6.
All agent-kit error constants live here — adapter.py and swarm.py import from this module.
"""

# Auth missing — MOONSHOT_API_KEY not set
KIMI_AUTH_MISSING: str = "BEDDEL-AGENT-800"

# Session timeout
KIMI_SESSION_TIMEOUT: str = "BEDDEL-AGENT-801"

# Rate limited (429)
KIMI_RATE_LIMITED: str = "BEDDEL-AGENT-802"

# General execution failure
KIMI_EXECUTION_FAILED: str = "BEDDEL-AGENT-803"

# All swarm sub-agents failed
KIMI_SWARM_ALL_FAILED: str = "BEDDEL-AGENT-804"

# Approval denied
KIMI_APPROVAL_DENIED: str = "BEDDEL-AGENT-805"

# Swarm noncompliant — model did not invoke AgentSwarm tool
KIMI_SWARM_NONCOMPLIANT: str = "BEDDEL-AGENT-806"

# Invalid model tier
KIMI_INVALID_MODEL: str = "BEDDEL-AGENT-821"
