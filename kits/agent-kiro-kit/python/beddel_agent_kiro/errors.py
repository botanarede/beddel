"""Error codes owned by the agent-kiro kit."""

from __future__ import annotations

KIRO_AGENT_INVALID = "KIRO_AGENT_INVALID"
"""The configured Delivery agent is not installed or cannot be loaded."""

KIRO_CLI_MISSING = "KIRO_CLI_MISSING"
"""The kiro-cli executable is not installed or discoverable."""

__all__ = ["KIRO_AGENT_INVALID", "KIRO_CLI_MISSING"]
