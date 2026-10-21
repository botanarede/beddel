"""AC2/AC3: entry workflow parses, requires the kit and allowlists every tool."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import yaml
from beddel.domain.models import Step, StrategyType, Workflow
from beddel.domain.parser import WorkflowParser

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / "workflows"
WORKFLOW_PATH = WORKFLOWS_DIR / "verify-change.yaml"
RATIFY_PATH = WORKFLOWS_DIR / "ratify-inventory.yaml"


def _load() -> Workflow:
    return WorkflowParser.parse(WORKFLOW_PATH.read_text())


def _raw_inputs(path: Path) -> list[str]:
    return list(yaml.safe_load(path.read_text())["inputs"])


def _load_ratify() -> Workflow:
    return WorkflowParser.parse(RATIFY_PATH.read_text())


def _walk(steps: list[Step] | None) -> Iterator[Step]:
    for step in steps or []:
        yield step
        yield from _walk(step.then_steps)
        yield from _walk(step.else_steps)
        fallback = step.execution_strategy.fallback_step
        if fallback is not None:
            yield from _walk([fallback])


def _tool_names(steps: list[Step]) -> set[str]:
    return {
        str(s.config["tool"])
        for s in _walk(steps)
        if s.primitive == "tool" and "tool" in s.config
    }


def test_parses_and_requires_kit() -> None:
    wf = _load()
    assert wf.id == "verify-change"
    assert wf.requires_kits == ["profile-dev-kit"]


def test_preflight_change_bind_impact_and_each_step_fails_closed() -> None:
    wf = _load()
    steps = wf.steps
    assert [s.id for s in steps] == ["preflight", "change", "bind_inventory", "impact"]
    assert [s.config["tool"] for s in steps] == [
        "profile_preflight",
        "profile_record_change",
        "profile_bind_inventory",
        "profile_derive_impact",
    ]
    assert _raw_inputs(WORKFLOW_PATH) == [
        "repo_path",
        "change_id",
        "base",
        "revision",
        "inventory_version",
    ]
    # A failing step must stop the run: no retry, no fallback, no skip.
    assert all(s.primitive == "tool" for s in steps)
    assert all(s.execution_strategy.type is StrategyType.FAIL for s in steps)


def test_allowlist_equals_the_tools_the_steps_name() -> None:
    for path in sorted(WORKFLOWS_DIR.glob("*.yaml")):
        wf = WorkflowParser.parse(path.read_text())
        assert set(wf.allowed_tools or []) == _tool_names(wf.steps), path.name
    assert _load().allowed_tools == [
        "profile_preflight",
        "profile_record_change",
        "profile_bind_inventory",
        "profile_derive_impact",
    ]
    assert len(list(WORKFLOWS_DIR.glob("*.yaml"))) == 3


def test_declare_workflow_is_one_allowlisted_step() -> None:
    path = WORKFLOWS_DIR / "declare-non-applicability.yaml"
    wf = WorkflowParser.parse(path.read_text())
    assert wf.id == "declare-non-applicability"
    assert wf.requires_kits == ["profile-dev-kit"]
    assert _raw_inputs(path) == [
        "repo_path",
        "revision",
        "class_id",
        "affected_point_id",
        "criterion_id",
        "actor",
    ]
    assert wf.allowed_tools == ["profile_declare_non_applicability"]
    assert [s.id for s in wf.steps] == ["declare"]
    assert wf.steps[0].execution_strategy.type is StrategyType.FAIL


def test_ratify_workflow_is_one_allowlisted_step() -> None:
    wf = _load_ratify()
    assert wf.id == "ratify-inventory"
    assert wf.requires_kits == ["profile-dev-kit"]
    assert _raw_inputs(RATIFY_PATH) == ["repo_path", "inventory_version", "actor"]
    assert [s.id for s in wf.steps] == ["ratify"]
    assert wf.allowed_tools == ["profile_ratify_inventory"]
    assert _tool_names(wf.steps) == {"profile_ratify_inventory"}
    assert wf.steps[0].execution_strategy.type is StrategyType.FAIL


def test_walk_catches_a_tool_hidden_in_a_nested_branch() -> None:
    wf = WorkflowParser.parse(
        """
id: nested
name: Nested
version: "1.0"
allowed_tools: [a]
steps:
  - id: s1
    primitive: tool
    config: {tool: a}
  - id: s2
    primitive: tool
    if: "true"
    config: {tool: a}
    then:
      - id: s3
        primitive: tool
        config: {tool: sneaky}
"""
    )
    assert _tool_names(wf.steps) - set(wf.allowed_tools or []) == {"sneaky"}
