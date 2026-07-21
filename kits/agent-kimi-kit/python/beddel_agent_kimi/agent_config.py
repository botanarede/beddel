"""Production agent configuration for agent-kimi-kit.

Provides a bundled production-safe agent YAML configuration that disables
dangerous tools (Shell, ReadMediaFile, FetchURL, SearchWeb) while keeping
safe file operations gated by the approval bridge.

Usage:
    from beddel_agent_kimi.agent_config import get_production_agent_file

    adapter = KimiAgentAdapter(agent_file=get_production_agent_file())
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["PRODUCTION_AGENT_FILE", "get_production_agent_file"]

#: Path to the bundled production agent YAML configuration.
#: Disables Shell, ReadMediaFile, FetchURL, SearchWeb.
PRODUCTION_AGENT_FILE: Path = Path(__file__).parent / "production-agent.yaml"


def get_production_agent_file() -> Path:
    """Return the path to the bundled production agent config.

    The production config disables unsafe tools that can escape
    the working directory or access the network:
    - Shell (arbitrary command execution)
    - ReadMediaFile (Pillow CVE-2026-25990)
    - FetchURL (network exfiltration)
    - SearchWeb (network access)

    Returns:
        Path to production-agent.yaml bundled with agent-kimi-kit.

    Raises:
        FileNotFoundError: If the bundled YAML is missing (broken install).
    """
    if not PRODUCTION_AGENT_FILE.exists():
        msg = (
            f"Production agent config not found: {PRODUCTION_AGENT_FILE}. "
            "This indicates a broken agent-kimi-kit installation."
        )
        raise FileNotFoundError(msg)
    return PRODUCTION_AGENT_FILE
