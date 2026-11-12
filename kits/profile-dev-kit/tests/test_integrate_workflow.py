"""Shape and safety checks for the integration entry workflow."""

from __future__ import annotations

from pathlib import Path

import yaml
from beddel.domain.models import StrategyType
from beddel.domain.parser import WorkflowParser

PATH = Path(__file__).resolve().parents[1] / "workflows" / "integrate-story.yaml"


def test_integrate_workflow_shape() -> None:
    document = yaml.safe_load(PATH.read_text())
    assert document["id"] == "integrate-story"
    assert document["requires_kits"] == [
        "profile-dev-kit",
        "tools-git-kit",
        "tools-github-kit",
    ]
    assert document["allowed_tools"] == [
        "profile_integrate_prepare",
        "profile_integrate_reconcile",
        "profile_integrate_settle",
        "profile_record_stage_outcome",
        "git_fetch",
        "git_push",
        "github_pr_create_or_reuse",
        "github_pr_checks_wait",
        "github_pr_merge",
    ]
    assert document["inputs"] == [
        "repo_path",
        "story_key",
        "spec_path",
        "branch",
        "base_branch",
        "remote",
        "change_id",
        "parent_path",
        "parent_branch",
        "status_path",
    ]
    assert [step["id"] for step in document["steps"]] == [
        "prepare",
        "fetch",
        "land",
        "push",
        "pull_request",
        "checks",
        "merge",
        "refetch",
        "confirm",
        "confirm_reuse",
        "record_repo",
        "pointer",
        "fetch_parent",
        "finish",
        "record_parent",
    ]
    assert (
        sum(step["config"].get("tool") == "git_push" for step in document["steps"]) == 1
    )
    push = next(step for step in document["steps"] if step["id"] == "push")
    assert "force" not in push["config"]["arguments"]
    assert "set_upstream" not in push["config"]["arguments"]
    request = next(step for step in document["steps"] if step["id"] == "pull_request")
    assert set(request["config"]["arguments"]) == {
        "cwd",
        "branch",
        "base",
        "story_key",
        "spec_path",
        "change_id",
        "revision",
    }
    assert (
        next(step for step in document["steps"] if step["id"] == "merge")["config"][
            "arguments"
        ]["merge_method"]
        == "merge"
    )
    assert {step.get("output_key") for step in document["steps"]} >= {"confirmed"}


def test_integrate_workflow_parses_and_conditions_pair() -> None:
    workflow = WorkflowParser.parse(PATH.read_text())
    steps = {step.id: step for step in workflow.steps}
    assert steps["confirm"].if_condition == "$stepResult.land.result.pr == true"
    assert steps["confirm_reuse"].if_condition == "$stepResult.land.result.pr != true"
    assert (
        steps["confirm"].config["timeout"] == 2000
        if "timeout" in steps["confirm"].config
        else True
    )
    assert steps["confirm"].execution_strategy.type is StrategyType.FAIL
    assert steps["confirm_reuse"].execution_strategy.type is StrategyType.FAIL
    assert steps["confirm"].config["tool"] == "profile_integrate_reconcile"
