"""Integration tests for antigravity-sdk-kit example workflows.

Validates that the three bundled example workflow YAML files
(``workflows/hello-world.yaml``, ``workflows/mcp-pipeline.yaml``,
``workflows/vds-orchestrator.yaml``) are valid Beddel workflow definitions:

- Parse successfully via the real ``beddel.domain.parser.WorkflowParser``
  (YAML syntax + Pydantic schema + variable-reference validation — the same
  pipeline the SDK uses at runtime).
- Reference only tools/adapters that are actually declared in ``kit.yaml``.
- Have the expected step structure described in the story (agent-exec step
  for hello-world; tool + MCP + schedule trigger pattern for mcp-pipeline;
  multi-agent sub-agent delegation for vds-orchestrator).
- Are correctly declared in ``kit.yaml``'s ``workflows:`` section.

These tests do not execute the workflows (no ADK runtime involved) — they
validate structure only, consistent with the "integration test" scope
defined in Story K5.6 (parse correctly, correct step structure, reference
existing tools/adapter).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from beddel.domain.parser import WorkflowParser

_KIT_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOWS_DIR = _KIT_ROOT / "workflows"
_KIT_YAML_PATH = _KIT_ROOT / "kit.yaml"

WORKFLOW_FILES = [
    "hello-world.yaml",
    "mcp-pipeline.yaml",
    "vds-orchestrator.yaml",
]


@pytest.fixture(scope="module")
def kit_manifest() -> dict[str, Any]:
    """Load and parse ``kit.yaml`` once for the module."""
    return yaml.safe_load(_KIT_YAML_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def declared_tool_names(kit_manifest: dict[str, Any]) -> set[str]:
    """Set of tool names declared in ``kit.yaml``'s top-level ``tools:`` list."""
    return {entry["name"] for entry in kit_manifest.get("tools", [])}


@pytest.fixture(scope="module")
def declared_adapter_names(kit_manifest: dict[str, Any]) -> set[str]:
    """Set of adapter names declared in ``kit.yaml``'s top-level ``adapters:`` list."""
    return {entry["name"] for entry in kit_manifest.get("adapters", [])}


def _load_workflow_text(filename: str) -> str:
    path = _WORKFLOWS_DIR / filename
    assert path.exists(), f"Workflow file not found: {path}"
    return path.read_text(encoding="utf-8")


def _tool_names_used(workflow_dict: dict[str, Any]) -> set[str]:
    """Collect every ``config.tool`` value referenced by ``primitive: tool`` steps."""
    names: set[str] = set()
    for step in workflow_dict.get("steps", []):
        if step.get("primitive") == "tool":
            tool_name = step.get("config", {}).get("tool")
            if tool_name:
                names.add(tool_name)
    return names


def _adapter_names_used(workflow_dict: dict[str, Any]) -> set[str]:
    """Collect every ``config.adapter`` value referenced by ``primitive: agent-exec`` steps."""
    names: set[str] = set()
    for step in workflow_dict.get("steps", []):
        if step.get("primitive") == "agent-exec":
            adapter_name = step.get("config", {}).get("adapter")
            if adapter_name:
                names.add(adapter_name)
    return names


# ---------------------------------------------------------------------------
# Generic checks — parametrized across all 3 workflow files
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filename", WORKFLOW_FILES)
def test_workflow_file_exists(filename: str) -> None:
    """Each of the 3 expected workflow files exists under workflows/."""
    path = _WORKFLOWS_DIR / filename
    assert path.is_file()


@pytest.mark.parametrize("filename", WORKFLOW_FILES)
def test_workflow_is_valid_yaml(filename: str) -> None:
    """Each workflow file is syntactically valid YAML (safe_load succeeds)."""
    raw = _load_workflow_text(filename)
    data = yaml.safe_load(raw)
    assert isinstance(data, dict)


@pytest.mark.parametrize("filename", WORKFLOW_FILES)
def test_workflow_parses_via_beddel_parser(filename: str) -> None:
    """Each workflow parses successfully via the real WorkflowParser.

    Exercises the full 3-phase pipeline: YAML deserialization, Pydantic
    schema validation, and variable-reference syntax validation.
    """
    raw = _load_workflow_text(filename)
    workflow = WorkflowParser.parse(raw)

    assert workflow.id
    assert workflow.name
    assert len(workflow.steps) >= 1


@pytest.mark.parametrize("filename", WORKFLOW_FILES)
def test_workflow_step_ids_are_unique(filename: str) -> None:
    """Step IDs within a workflow must be unique (sanity check on structure)."""
    raw = _load_workflow_text(filename)
    workflow = WorkflowParser.parse(raw)

    step_ids = [step.id for step in workflow.steps]
    assert len(step_ids) == len(set(step_ids)), f"Duplicate step IDs in {filename}"


@pytest.mark.parametrize("filename", WORKFLOW_FILES)
def test_workflow_tools_are_declared_in_kit_yaml(
    filename: str, declared_tool_names: set[str]
) -> None:
    """Every tool referenced by a ``primitive: tool`` step exists in kit.yaml."""
    raw = _load_workflow_text(filename)
    data = yaml.safe_load(raw)

    used = _tool_names_used(data)
    unknown = used - declared_tool_names
    assert not unknown, (
        f"{filename} references tool(s) not declared in kit.yaml: {unknown}"
    )


@pytest.mark.parametrize("filename", WORKFLOW_FILES)
def test_workflow_adapters_are_declared_in_kit_yaml(
    filename: str, declared_adapter_names: set[str]
) -> None:
    """Every adapter referenced by an ``agent-exec`` step exists in kit.yaml."""
    raw = _load_workflow_text(filename)
    data = yaml.safe_load(raw)

    used = _adapter_names_used(data)
    unknown = used - declared_adapter_names
    assert not unknown, (
        f"{filename} references adapter(s) not declared in kit.yaml: {unknown}"
    )


# ---------------------------------------------------------------------------
# hello-world.yaml — minimal agent-exec example
# ---------------------------------------------------------------------------


class TestHelloWorld:
    """Structure checks specific to hello-world.yaml."""

    @pytest.fixture(scope="class")
    @classmethod
    def workflow(cls):
        raw = _load_workflow_text("hello-world.yaml")
        return WorkflowParser.parse(raw)

    def test_has_input_schema_with_topic(self, workflow) -> None:
        assert workflow.input_schema is not None
        assert "topic" in workflow.input_schema.get("properties", {})

    def test_has_agent_exec_step_using_antigravity_adapter(self, workflow) -> None:
        agent_exec_steps = [s for s in workflow.steps if s.primitive == "agent-exec"]
        assert len(agent_exec_steps) == 1
        assert agent_exec_steps[0].config["adapter"] == "antigravity"

    def test_minimal_step_count(self, workflow) -> None:
        # Minimal example: agent-exec + a step to surface the result.
        assert len(workflow.steps) == 2


# ---------------------------------------------------------------------------
# mcp-pipeline.yaml — tool + MCP + schedule trigger pattern
# ---------------------------------------------------------------------------


class TestMcpPipeline:
    """Structure checks specific to mcp-pipeline.yaml."""

    @pytest.fixture(scope="class")
    @classmethod
    def workflow(cls):
        raw = _load_workflow_text("mcp-pipeline.yaml")
        return WorkflowParser.parse(raw)

    def test_has_schedule_trigger(self, workflow) -> None:
        trigger = workflow.metadata.get("trigger")
        assert trigger is not None
        assert trigger.get("type") == "schedule"
        assert "cron" in trigger.get("config", {})

    def test_has_standalone_antigravity_tool_exec_step(self, workflow) -> None:
        tool_steps = [s for s in workflow.steps if s.primitive == "tool"]
        tool_names = {s.config.get("tool") for s in tool_steps}
        assert "antigravity_tool_exec" in tool_names

    def test_has_mcp_call_step(self, workflow) -> None:
        tool_steps = [s for s in workflow.steps if s.primitive == "tool"]
        mcp_steps = [
            s for s in tool_steps if s.config.get("tool") == "antigravity_mcp_call"
        ]
        assert len(mcp_steps) == 1
        assert "server_name" in mcp_steps[0].config
        assert "tool_name" in mcp_steps[0].config

    def test_has_synthesizing_agent_exec_step(self, workflow) -> None:
        agent_exec_steps = [s for s in workflow.steps if s.primitive == "agent-exec"]
        assert len(agent_exec_steps) == 1
        assert agent_exec_steps[0].config["adapter"] == "antigravity"

    def test_multi_step_pipeline_structure(self, workflow) -> None:
        # tool + MCP + agent-exec + report, at minimum.
        assert len(workflow.steps) >= 4


# ---------------------------------------------------------------------------
# vds-orchestrator.yaml — simplified Viver de Samba multi-agent automation
# ---------------------------------------------------------------------------


class TestVdsOrchestrator:
    """Structure checks specific to vds-orchestrator.yaml."""

    @pytest.fixture(scope="class")
    @classmethod
    def workflow(cls):
        raw = _load_workflow_text("vds-orchestrator.yaml")
        return WorkflowParser.parse(raw)

    def test_has_input_schema_with_event_topic(self, workflow) -> None:
        assert workflow.input_schema is not None
        assert "event_topic" in workflow.input_schema.get("properties", {})

    def test_has_two_distinct_subagent_delegations(self, workflow) -> None:
        subagent_steps = [
            s
            for s in workflow.steps
            if s.primitive == "tool" and s.config.get("tool") == "antigravity_subagent"
        ]
        agent_names = {s.config.get("agent_name") for s in subagent_steps}
        assert agent_names == {"researcher", "writer"}

    def test_has_session_persistence_step(self, workflow) -> None:
        tool_steps = [s for s in workflow.steps if s.primitive == "tool"]
        save_steps = [
            s for s in tool_steps if s.config.get("tool") == "antigravity_session_save"
        ]
        assert len(save_steps) == 1

    def test_multi_agent_pipeline_structure(self, workflow) -> None:
        # research + draft + persist + publish, at minimum.
        assert len(workflow.steps) >= 4


# ---------------------------------------------------------------------------
# kit.yaml workflows section cross-reference
# ---------------------------------------------------------------------------


class TestKitYamlWorkflowsSection:
    """Validates kit.yaml's workflows: section references the 3 example files."""

    def test_workflows_section_exists(self, kit_manifest: dict[str, Any]) -> None:
        assert "workflows" in kit_manifest
        assert isinstance(kit_manifest["workflows"], list)
        assert len(kit_manifest["workflows"]) == 3

    @pytest.mark.parametrize("filename", WORKFLOW_FILES)
    def test_each_workflow_file_referenced(
        self, kit_manifest: dict[str, Any], filename: str
    ) -> None:
        declared_paths = {entry["path"] for entry in kit_manifest["workflows"]}
        expected_path = f"workflows/{filename}"
        assert expected_path in declared_paths

    def test_each_declared_workflow_path_resolves_to_a_real_file(
        self, kit_manifest: dict[str, Any]
    ) -> None:
        for entry in kit_manifest["workflows"]:
            resolved = _KIT_ROOT / entry["path"]
            assert resolved.is_file(), (
                f"kit.yaml references missing file: {entry['path']}"
            )

    def test_each_declared_workflow_has_name_and_description(
        self, kit_manifest: dict[str, Any]
    ) -> None:
        for entry in kit_manifest["workflows"]:
            assert entry.get("name")
            assert entry.get("description")
