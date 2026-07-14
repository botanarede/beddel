"""Integration tests for bundled workflow YAML files.

Validates that all workflow YAML files in the kit are:
1. Parseable as valid YAML with required top-level keys
2. Reference tool names that exist in kit.yaml
3. Declare inputs with name and type fields
4. Only use {{ inputs.* }} references that resolve to declared inputs
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

_KIT_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOWS_DIR = _KIT_ROOT / "workflows"
_KIT_YAML = _KIT_ROOT / "kit.yaml"

# Required top-level keys for a valid Beddel workflow
_REQUIRED_KEYS = {"id", "version", "inputs", "steps"}

# Pattern to match {{ inputs.param_name }} references
_INPUT_REF_PATTERN = re.compile(r"\{\{\s*inputs\.(\w+)\s*\}\}")


@pytest.fixture()
def kit_manifest() -> dict[str, Any]:
    """Load kit.yaml manifest."""
    return yaml.safe_load(_KIT_YAML.read_text(encoding="utf-8"))


@pytest.fixture()
def kit_tool_names(kit_manifest: dict[str, Any]) -> set[str]:
    """Extract all declared tool names from kit.yaml."""
    tools = kit_manifest.get("tools", [])
    return {t["name"] for t in tools}


def _load_workflow(filename: str) -> dict[str, Any]:
    """Load and parse a workflow YAML file."""
    path = _WORKFLOWS_DIR / filename
    assert path.exists(), f"Workflow file not found: {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _get_workflow_files() -> list[str]:
    """List all YAML files in the workflows directory."""
    if not _WORKFLOWS_DIR.exists():
        return []
    return [f.name for f in _WORKFLOWS_DIR.iterdir() if f.suffix in {".yaml", ".yml"}]


# --- Parameterized tests across all workflows ---


@pytest.fixture(params=_get_workflow_files())
def workflow(request: pytest.FixtureRequest) -> dict[str, Any]:
    """Load each workflow YAML for parameterized testing."""
    return _load_workflow(request.param)


@pytest.fixture(params=_get_workflow_files())
def workflow_name(request: pytest.FixtureRequest) -> str:
    """Workflow filename for parameterized testing."""
    return request.param


class TestWorkflowStructure:
    """Test that workflow YAML files have valid structure."""

    def test_workflows_directory_exists(self) -> None:
        """Workflows directory must exist."""
        assert _WORKFLOWS_DIR.exists(), f"Missing: {_WORKFLOWS_DIR}"

    def test_three_workflows_present(self) -> None:
        """Exactly 3 bundled workflows must be present."""
        files = _get_workflow_files()
        assert len(files) == 3, f"Expected 3 workflows, found {len(files)}: {files}"

    def test_workflow_is_valid_yaml(self, workflow_name: str) -> None:
        """Each workflow file must be valid YAML."""
        path = _WORKFLOWS_DIR / workflow_name
        content = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), f"{workflow_name} did not parse as dict"

    def test_workflow_has_required_keys(self, workflow_name: str) -> None:
        """Each workflow must have id, version, inputs, steps."""
        wf = _load_workflow(workflow_name)
        missing = _REQUIRED_KEYS - set(wf.keys())
        assert not missing, f"{workflow_name} missing keys: {missing}"

    def test_workflow_version_is_string(self, workflow_name: str) -> None:
        """Version must be a string."""
        wf = _load_workflow(workflow_name)
        assert isinstance(wf["version"], str), f"{workflow_name}: version must be str"

    def test_workflow_has_description(self, workflow_name: str) -> None:
        """Each workflow should have a description."""
        wf = _load_workflow(workflow_name)
        assert "description" in wf, f"{workflow_name} missing description"
        assert len(wf["description"]) > 10


class TestWorkflowInputs:
    """Test that workflow inputs are properly declared."""

    def test_inputs_is_list(self, workflow_name: str) -> None:
        """Inputs must be a list."""
        wf = _load_workflow(workflow_name)
        assert isinstance(wf["inputs"], list), f"{workflow_name}: inputs not a list"

    def test_inputs_have_name_and_type(self, workflow_name: str) -> None:
        """Each input must have name and type fields."""
        wf = _load_workflow(workflow_name)
        for i, inp in enumerate(wf["inputs"]):
            assert "name" in inp, f"{workflow_name} input[{i}] missing 'name'"
            assert "type" in inp, f"{workflow_name} input[{i}] missing 'type'"

    def test_inputs_not_empty(self, workflow_name: str) -> None:
        """Each workflow must declare at least one input."""
        wf = _load_workflow(workflow_name)
        assert len(wf["inputs"]) > 0, f"{workflow_name} has no inputs"


class TestWorkflowSteps:
    """Test that workflow steps reference valid tools."""

    def test_steps_is_list(self, workflow_name: str) -> None:
        """Steps must be a list."""
        wf = _load_workflow(workflow_name)
        assert isinstance(wf["steps"], list), f"{workflow_name}: steps not a list"

    def test_steps_have_id_and_primitive(self, workflow_name: str) -> None:
        """Each step must have id and primitive fields."""
        wf = _load_workflow(workflow_name)
        for i, step in enumerate(wf["steps"]):
            assert "id" in step, f"{workflow_name} step[{i}] missing 'id'"
            assert "primitive" in step, f"{workflow_name} step[{i}] missing 'primitive'"

    def test_tool_steps_reference_valid_tools(
        self, workflow_name: str, kit_tool_names: set[str]
    ) -> None:
        """Tool steps must reference tool names declared in kit.yaml."""
        wf = _load_workflow(workflow_name)
        for step in wf["steps"]:
            if step.get("primitive") == "tool":
                config = step.get("config", {})
                tool_name = config.get("tool")
                assert tool_name is not None, (
                    f"{workflow_name} step '{step['id']}': "
                    f"primitive=tool but no config.tool"
                )
                assert tool_name in kit_tool_names, (
                    f"{workflow_name} step '{step['id']}': "
                    f"tool '{tool_name}' not in kit.yaml. "
                    f"Available: {sorted(kit_tool_names)}"
                )

    def test_input_references_resolve(self, workflow_name: str) -> None:
        """All {{ inputs.X }} references must resolve to declared inputs."""
        wf = _load_workflow(workflow_name)
        declared_inputs = {inp["name"] for inp in wf["inputs"]}

        # Serialize all step configs to find input references
        steps_yaml = yaml.dump(wf["steps"])
        referenced_inputs = set(_INPUT_REF_PATTERN.findall(steps_yaml))

        unresolved = referenced_inputs - declared_inputs
        assert not unresolved, (
            f"{workflow_name}: unresolved input refs: {unresolved}. "
            f"Declared: {sorted(declared_inputs)}"
        )


class TestSpecificWorkflows:
    """Test specific workflow expectations from the architecture doc."""

    def test_onboarding_has_6_steps(self) -> None:
        """onboarding-novo-cliente must have exactly 6 steps."""
        wf = _load_workflow("onboarding-novo-cliente.yaml")
        assert len(wf["steps"]) == 6

    def test_onboarding_has_llm_step(self) -> None:
        """onboarding-novo-cliente must use llm primitive for generation."""
        wf = _load_workflow("onboarding-novo-cliente.yaml")
        llm_steps = [s for s in wf["steps"] if s["primitive"] == "llm"]
        assert len(llm_steps) == 1, "Expected exactly 1 llm step"
        assert llm_steps[0]["id"] == "generate-tenant"

    def test_onboarding_has_3_inputs(self) -> None:
        """onboarding-novo-cliente must have 3 inputs."""
        wf = _load_workflow("onboarding-novo-cliente.yaml")
        input_names = {inp["name"] for inp in wf["inputs"]}
        assert input_names == {"briefing", "project_id", "tenant_id"}

    def test_deploy_has_4_steps(self) -> None:
        """deploy-tenant must have exactly 4 steps."""
        wf = _load_workflow("deploy-tenant.yaml")
        assert len(wf["steps"]) == 4

    def test_deploy_is_pure_tool(self) -> None:
        """deploy-tenant must use only tool primitives (no LLM)."""
        wf = _load_workflow("deploy-tenant.yaml")
        for step in wf["steps"]:
            assert step["primitive"] == "tool", (
                f"deploy-tenant step '{step['id']}' uses "
                f"'{step['primitive']}', expected 'tool'"
            )

    def test_deploy_has_2_inputs(self) -> None:
        """deploy-tenant must have 2 inputs."""
        wf = _load_workflow("deploy-tenant.yaml")
        input_names = {inp["name"] for inp in wf["inputs"]}
        assert input_names == {"tenant_id", "project_id"}

    def test_update_has_5_steps(self) -> None:
        """update-tenant must have exactly 5 steps."""
        wf = _load_workflow("update-tenant.yaml")
        assert len(wf["steps"]) == 5

    def test_update_is_pure_tool(self) -> None:
        """update-tenant must use only tool primitives (no LLM)."""
        wf = _load_workflow("update-tenant.yaml")
        for step in wf["steps"]:
            assert step["primitive"] == "tool", (
                f"update-tenant step '{step['id']}' uses "
                f"'{step['primitive']}', expected 'tool'"
            )

    def test_update_has_3_inputs(self) -> None:
        """update-tenant must have 3 inputs with changes as dict."""
        wf = _load_workflow("update-tenant.yaml")
        input_names = {inp["name"] for inp in wf["inputs"]}
        assert input_names == {"tenant_id", "project_id", "changes"}
        # Verify changes is dict type
        changes_input = next(i for i in wf["inputs"] if i["name"] == "changes")
        assert changes_input["type"] == "dict"


class TestKitYamlWorkflows:
    """Test that kit.yaml correctly references workflow files."""

    def test_kit_yaml_has_workflows_section(self, kit_manifest: dict[str, Any]) -> None:
        """kit.yaml must have a workflows section."""
        assert "workflows" in kit_manifest

    def test_kit_yaml_references_3_workflows(
        self, kit_manifest: dict[str, Any]
    ) -> None:
        """kit.yaml workflows section must reference exactly 3 files."""
        workflows = kit_manifest["workflows"]
        assert len(workflows) == 3

    def test_kit_yaml_workflow_files_exist(self, kit_manifest: dict[str, Any]) -> None:
        """All workflow files referenced in kit.yaml must exist on disk."""
        for wf in kit_manifest["workflows"]:
            file_path = _KIT_ROOT / wf["file"]
            assert file_path.exists(), f"Referenced file not found: {wf['file']}"

    def test_kit_yaml_workflow_entries_have_required_fields(
        self, kit_manifest: dict[str, Any]
    ) -> None:
        """Each workflow entry must have name, file, and description."""
        for wf in kit_manifest["workflows"]:
            assert "name" in wf, f"Workflow entry missing 'name': {wf}"
            assert "file" in wf, f"Workflow entry missing 'file': {wf}"
            assert "description" in wf, f"Workflow entry missing 'description': {wf}"
