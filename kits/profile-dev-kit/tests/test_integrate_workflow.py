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
    assert steps["checks"].config["timeout"] == 2000
    assert steps["push"].config["timeout"] == 330
    assert steps["pull_request"].config["timeout"] == 400
    assert steps["confirm"].execution_strategy.type is StrategyType.FAIL
    assert steps["confirm_reuse"].execution_strategy.type is StrategyType.FAIL
    assert steps["confirm"].config["tool"] == "profile_integrate_reconcile"


import asyncio
import json
import sys
from typing import Any

from beddel.domain.executor import WorkflowExecutor
from beddel.domain.kit import parse_kit_manifest
from beddel.domain.models import DefaultDependencies
from beddel.domain.registry import PrimitiveRegistry
from beddel.primitives import register_builtins
from beddel.tools.kits import load_kit

from ._helpers import commit_all, git, init_repo

KIT_ROOT = PATH.parents[1]
KITS_ROOT = KIT_ROOT.parent
sys.path.insert(0, str(KITS_ROOT / "tools-git-kit" / "python"))
sys.path.insert(0, str(KITS_ROOT / "tools-github-kit" / "python"))
STORY = "7-6-integrate-workflow-completes-only-after-approval"
BRANCH = "feat/work"


def _fixture(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "case"
    root.mkdir()
    sub_bare = root / "sub.git"
    parent_bare = root / "parent.git"
    git(root, "init", "-q", "--bare", "-b", "main", str(sub_bare))
    git(root, "init", "-q", "--bare", "-b", "main", str(parent_bare))
    parent = init_repo(root / "parent")
    sub = init_repo(parent / "sub")
    for repo in (parent, sub):
        git(repo, "config", "user.name", "Fixture")
        git(repo, "config", "user.email", "fixture@example.invalid")
    (sub / "base.txt").write_text("base\n")
    base = commit_all(sub, "base")
    git(sub, "remote", "add", "origin", str(sub_bare))
    git(sub, "push", "-q", "origin", "HEAD:refs/heads/main")
    (parent / "status.yaml").write_text(f"x: 1\n  {STORY}: review  # keep\n")
    git(parent, "update-index", "--add", "--cacheinfo", f"160000,{base},sub")
    commit_all(parent, "parent")
    git(parent, "remote", "add", "origin", str(parent_bare))
    git(parent, "push", "-q", "origin", "HEAD:refs/heads/main")
    git(parent, "switch", "-C", "main")
    git(sub, "switch", "-q", "-c", BRANCH)
    (sub / "change.txt").write_text("change\n")
    tip = commit_all(sub, "change")
    return {
        "root": root,
        "parent": parent,
        "sub": sub,
        "base": base,
        "tip": tip,
        "sub_bare": sub_bare,
    }


class _Host:
    def __init__(self, env: dict[str, Any]) -> None:
        self.env = env
        self.calls: list[str] = []
        self.fail_checks = False

    async def create(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append("pr")
        return {"number": 7, "created": True}

    async def checks(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append("checks")
        if self.fail_checks:
            raise RuntimeError("checks failed")
        return {"status": "passed"}

    async def merge(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append("merge")
        if self.fail_checks:
            raise RuntimeError("merge blocked after checks failure")
        clone = self.env["root"] / f"clone-{len(self.calls)}"
        git(self.env["root"], "clone", "-q", str(self.env["sub_bare"]), str(clone))
        git(clone, "fetch", "-q", "origin", f"refs/heads/{BRANCH}")
        git(clone, "merge", "-q", "--no-ff", "-m", "Merge", kwargs["expected_head_sha"])
        git(clone, "push", "-q", "origin", "main")
        return {"merged": True, "merge_sha": git(clone, "rev-parse", "HEAD")}


def _run(
    env: dict[str, Any],
    host: _Host,
    approval: dict[str, Any] | None,
    report: dict[str, Any] | None,
    monkeypatch: Any,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from beddel_profile_dev.tools import integrate as module

    monkeypatch.setattr(
        module, "profile_read_approval", lambda repo, change: {"approval": approval}
    )
    monkeypatch.setattr(
        module, "profile_read_report", lambda repo, change: {"report": report}
    )
    registry: dict[str, Any] = {}
    for name in ("profile-dev-kit", "tools-git-kit", "tools-github-kit"):
        registry.update(load_kit(parse_kit_manifest(KITS_ROOT / name / "kit.yaml")))
    registry.update(
        {
            "github_pr_create_or_reuse": host.create,
            "github_pr_checks_wait": host.checks,
            "github_pr_merge": host.merge,
        }
    )
    registry.update(overrides or {})
    primitive = PrimitiveRegistry()
    register_builtins(primitive)
    executor = WorkflowExecutor(
        primitive, deps=DefaultDependencies(tool_registry=registry)
    )
    inputs = {
        "repo_path": str(env["sub"]),
        "story_key": STORY,
        "spec_path": "spec.md",
        "branch": BRANCH,
        "base_branch": "main",
        "remote": "origin",
        "change_id": "c1",
        "parent_path": str(env["parent"]),
        "parent_branch": "main",
        "status_path": "status.yaml",
    }
    return asyncio.run(executor.execute(WorkflowParser.parse(PATH.read_text()), inputs))


def _approval(env: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {
            "revision": env["tip"],
            "proof": {"commit": env["tip"]},
            "report": "changes/c1/report/1.json",
        },
        {"revision": env["tip"], "verdict": "consistent"},
    )


def _records(home: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text())
        for path in sorted(home.rglob("stage-outcomes/*.json"))
    ]


def test_workflow_happy_path_owner_push_and_complete_rerun(
    tmp_path: Path, monkeypatch: Any
) -> None:
    env = _fixture(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)
    host = _Host(env)
    approval, report = _approval(env)
    first = _run(env, host, approval, report, monkeypatch)
    records = _records(tmp_path / "home")
    assert [record["reason"] for record in records] == [
        "merge.confirmed",
        "pointer.unpublished",
    ]
    assert first["step_results"]["pointer"]["result"]["pointer"]
    git(env["parent"], "push", "-q", "origin", "main")
    second = _run(env, host, approval, report, monkeypatch)
    assert second["step_results"]["finish"]["result"]["reason"] == "integrate.complete"
    assert (
        (env["parent"] / "status.yaml")
        .read_text()
        .splitlines()[1]
        .endswith(": done  # keep")
    )
    third = _run(env, host, approval, report, monkeypatch)
    assert third["step_results"]["finish"]["result"]["refs"]["status_written"] is False
    assert host.calls.count("merge") == 1


def test_workflow_absent_approval_has_no_host_calls_or_push(
    tmp_path: Path, monkeypatch: Any
) -> None:
    env = _fixture(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)
    host = _Host(env)
    _run(env, host, None, None, monkeypatch)
    records = _records(tmp_path / "home")
    assert [(record["outcome"], record["reason"]) for record in records] == [
        ("refused", "approval.absent")
    ]
    assert host.calls == []
    assert (
        git(env["sub_bare"], "for-each-ref", "--format=%(refname)") == "refs/heads/main"
    )


def test_workflow_checks_failure_has_no_parent_record(
    tmp_path: Path, monkeypatch: Any
) -> None:
    env = _fixture(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)
    host = _Host(env)
    host.fail_checks = True
    approval, report = _approval(env)
    _run(env, host, approval, report, monkeypatch)
    records = _records(tmp_path / "home")
    assert [(record["outcome"], record["reason"]) for record in records] == [
        ("failed", "checks.failed")
    ]
    assert host.calls == ["pr", "checks", "merge"]


def test_workflow_failed_refetch_reuses_merge(tmp_path: Path, monkeypatch: Any) -> None:
    env = _fixture(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(exist_ok=True)
    host = _Host(env)
    approval, report = _approval(env)
    registry = load_kit(parse_kit_manifest(KITS_ROOT / "tools-git-kit" / "kit.yaml"))
    real_fetch = registry["git_fetch"]
    calls = {"count": 0}

    async def flaky_fetch(**kwargs: Any) -> Any:
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("fetch failed")
        return await real_fetch(**kwargs)

    _run(env, host, approval, report, monkeypatch, {"git_fetch": flaky_fetch})
    assert _records(tmp_path / "home")[-1]["reason"] == "fetch.failed"
    _run(env, host, approval, report, monkeypatch)
    assert _records(tmp_path / "home")[-2]["reason"] == "merge.reused"
    assert host.calls.count("merge") == 1
