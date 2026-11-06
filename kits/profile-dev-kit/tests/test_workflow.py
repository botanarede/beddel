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
READ_REPORT_PATH = WORKFLOWS_DIR / "read-report.yaml"
APPROVE_PATH = WORKFLOWS_DIR / "approve-change.yaml"
RECORD_DECISION_PATH = WORKFLOWS_DIR / "record-approval-decision.yaml"
READ_APPROVAL_PATH = WORKFLOWS_DIR / "read-approval.yaml"


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


def test_preflight_change_bind_impact_gate_review_evidence_report_and_each_step_fails_closed() -> (
    None
):
    wf = _load()
    steps = wf.steps
    assert [s.id for s in steps] == [
        "preflight",
        "change",
        "bind_inventory",
        "impact",
        "attempt",
        "gate",
        "review",
        "evidence",
        "report",
    ]
    assert [s.config["tool"] for s in steps] == [
        "profile_preflight",
        "profile_record_change",
        "profile_bind_inventory",
        "profile_derive_impact",
        "profile_open_attempt",
        "profile_run_gate",
        "profile_run_review",
        "profile_capture_evidence",
        "profile_record_report",
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
        "profile_open_attempt",
        "profile_run_gate",
        "profile_run_review",
        "profile_capture_evidence",
        "profile_record_report",
    ]
    assert len(list(WORKFLOWS_DIR.glob("*.yaml"))) == 7


def test_review_step_outlives_the_largest_accepted_review_budget() -> None:
    """The core bounds an async tool at 60 s by default; the Review needs more."""
    from beddel_profile_dev import config as cfg
    from beddel_profile_dev.tools import review as review_module

    review = next(s for s in _load().steps if s.id == "review")
    ceiling = cfg._MAX_REVIEW_TIMEOUT_SECONDS + review_module._GUARD_SECONDS
    assert cfg.REVIEW_TIMEOUT_SECONDS <= cfg._MAX_REVIEW_TIMEOUT_SECONDS
    assert review.config["timeout"] >= ceiling


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


def test_read_report_workflow_is_one_allowlisted_step() -> None:
    wf = WorkflowParser.parse(READ_REPORT_PATH.read_text())
    assert wf.id == "read-report"
    assert wf.requires_kits == ["profile-dev-kit"]
    assert _raw_inputs(READ_REPORT_PATH) == ["repo_path", "change_id"]
    assert wf.allowed_tools == ["profile_read_report"]
    assert [s.id for s in wf.steps] == ["read"]
    assert wf.steps[0].config["tool"] == "profile_read_report"
    assert wf.steps[0].execution_strategy.type is StrategyType.FAIL


def test_no_workflow_declares_mcp_servers_or_mcp_server_steps() -> None:
    def walk(value: object) -> Iterator[dict[object, object]]:
        if isinstance(value, dict):
            yield value
            for nested in value.values():
                yield from walk(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from walk(nested)

    for path in sorted(WORKFLOWS_DIR.glob("*.yaml")):
        document = yaml.safe_load(path.read_text())
        assert isinstance(document, dict)
        assert "mcp_servers" not in document
        assert all(
            item.get("primitive") != "mcp_server"
            for item in walk(document)
            if isinstance(item, dict)
        ), path.name


def test_approve_workflow_is_one_allowlisted_step() -> None:
    wf = WorkflowParser.parse(APPROVE_PATH.read_text())
    assert wf.id == "approve-change"
    assert wf.requires_kits == ["profile-dev-kit"]
    assert _raw_inputs(APPROVE_PATH) == [
        "repo_path",
        "change_id",
        "revision",
        "actor",
        "decision_commit",
    ]
    assert wf.allowed_tools == ["profile_approve_change"]
    assert [s.id for s in wf.steps] == ["approve"]
    assert wf.steps[0].config["tool"] == "profile_approve_change"
    assert "timeout" not in wf.steps[0].config
    assert wf.steps[0].execution_strategy.type is StrategyType.FAIL


def test_record_approval_decision_workflow_is_one_allowlisted_step() -> None:
    wf = WorkflowParser.parse(RECORD_DECISION_PATH.read_text())
    assert wf.id == "record-approval-decision"
    assert wf.requires_kits == ["profile-dev-kit"]
    assert _raw_inputs(RECORD_DECISION_PATH) == [
        "repo_path",
        "change_id",
        "revision",
        "actor",
    ]
    assert wf.allowed_tools == ["profile_record_approval_decision"]
    assert [s.id for s in wf.steps] == ["record"]
    assert _tool_names(wf.steps) == {"profile_record_approval_decision"}
    assert "timeout" not in wf.steps[0].config
    assert wf.steps[0].execution_strategy.type is StrategyType.FAIL


def test_read_approval_workflow_is_one_allowlisted_step() -> None:
    wf = WorkflowParser.parse(READ_APPROVAL_PATH.read_text())
    assert wf.id == "read-approval"
    assert wf.requires_kits == ["profile-dev-kit"]
    assert _raw_inputs(READ_APPROVAL_PATH) == ["repo_path", "change_id"]
    assert wf.allowed_tools == ["profile_read_approval"]
    assert [s.id for s in wf.steps] == ["read"]
    assert _tool_names(wf.steps) == {"profile_read_approval"}
    assert "timeout" not in wf.steps[0].config
    assert wf.steps[0].execution_strategy.type is StrategyType.FAIL
