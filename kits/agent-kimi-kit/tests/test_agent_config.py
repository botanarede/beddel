"""Tests for agent_config module — production agent YAML configuration."""

from __future__ import annotations

from pathlib import Path

import yaml

from beddel_agent_kimi.agent_config import (
    PRODUCTION_AGENT_FILE,
    get_production_agent_file,
)

# Tools that MUST be disabled in production config
_UNSAFE_TOOLS = {
    "kimi_cli.tools.shell:Shell",
    "kimi_cli.tools.file:ReadMediaFile",
    "kimi_cli.tools.web:FetchURL",
    "kimi_cli.tools.web:SearchWeb",
}

# Tools that MUST be present in production config
_SAFE_TOOLS = {
    "kimi_cli.tools.file:ReadFile",
    "kimi_cli.tools.file:Glob",
    "kimi_cli.tools.file:Grep",
    "kimi_cli.tools.file:WriteFile",
    "kimi_cli.tools.file:StrReplaceFile",
}


class TestProductionAgentFile:
    """Test production agent config YAML."""

    def test_production_agent_file_exists(self) -> None:
        """Bundled production-agent.yaml exists on disk."""
        assert PRODUCTION_AGENT_FILE.exists()
        assert PRODUCTION_AGENT_FILE.is_file()

    def test_get_production_agent_file_returns_path(self) -> None:
        """get_production_agent_file() returns a valid Path."""
        path = get_production_agent_file()
        assert isinstance(path, Path)
        assert path.exists()

    def test_yaml_is_valid(self) -> None:
        """production-agent.yaml is valid YAML."""
        with open(PRODUCTION_AGENT_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)
        assert "version" in data
        assert data["version"] == 1

    def test_has_agent_section(self) -> None:
        """YAML has an 'agent' section with 'tools' list."""
        with open(PRODUCTION_AGENT_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "agent" in data
        assert "tools" in data["agent"]
        assert isinstance(data["agent"]["tools"], list)

    def test_unsafe_tools_not_present(self) -> None:
        """Shell, ReadMediaFile, FetchURL, SearchWeb are NOT in tools."""
        with open(PRODUCTION_AGENT_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        tools = set(data["agent"]["tools"])
        for unsafe in _UNSAFE_TOOLS:
            assert unsafe not in tools, (
                f"Unsafe tool {unsafe} found in production config"
            )

    def test_safe_tools_present(self) -> None:
        """ReadFile, Glob, Grep, WriteFile, StrReplaceFile ARE in tools."""
        with open(PRODUCTION_AGENT_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        tools = set(data["agent"]["tools"])
        for safe in _SAFE_TOOLS:
            assert safe in tools, f"Safe tool {safe} missing from production config"

    def test_extends_default(self) -> None:
        """Production config extends 'default' for system prompt inheritance."""
        with open(PRODUCTION_AGENT_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["agent"].get("extend") == "default"

    def test_agent_name_is_beddel_production(self) -> None:
        """Agent name is set to 'beddel-production'."""
        with open(PRODUCTION_AGENT_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["agent"]["name"] == "beddel-production"
