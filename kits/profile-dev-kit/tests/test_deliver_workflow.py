"""Shape checks for the statically chained Deliver Story workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from beddel.domain.parser import WorkflowParser
from beddel_profile_dev.deliver import IMPLEMENT_SLOTS, STAGES

# fmt: off
KIT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = KIT_ROOT / "workflows" / "deliver-story.yaml"
STATIC = {"plan-story.yaml", "implement-story.yaml", "verify-and-fix-story.yaml", "approve-change.yaml", "integrate-story.yaml"}


def _document() -> dict[str, Any]:
    value = yaml.safe_load(WORKFLOW.read_text())
    assert isinstance(value, dict)
    return value


def test_deliver_workflow_shape() -> None:
    workflow = WorkflowParser.parse(WORKFLOW.read_text())
    assert workflow.id == "deliver-story"
    assert workflow.requires_kits == [
        "profile-dev-kit",
        "agent-kiro-kit",
        "tools-git-kit",
        "tools-github-kit",
    ]
    assert workflow.allowed_tools == [
        "profile_deliver_gate",
        "profile_deliver_approval",
        "profile_record_stage_outcome",
    ]
    document = _document()
    steps = document["steps"]
    implement = [step for step in steps if str(step["id"]).startswith("implement_")]
    assert len(implement) == IMPLEMENT_SLOTS
    assert [step["id"] for step in implement] == [f"implement_{n}" for n in range(1, 34)]
    calls = [
        step["config"]["workflow"]
        for step in steps
        if step.get("primitive") == "call-agent"
    ]
    assert set(calls) == STATIC
    assert calls.count("approve-change.yaml") == 1
    assert all("$" not in name for name in calls)
    assert "agent-exec" in document["description"]
    assert "kiro-cli" in document["description"]


def test_stage_workflows_state_their_coding_agent() -> None:
    for name in ("plan-story.yaml", "implement-story.yaml", "verify-and-fix-story.yaml"):
        document = yaml.safe_load((KIT_ROOT / "workflows" / name).read_text())
        assert "Coding agent" in document["description"]
        agents = [step for step in document["steps"] if step.get("primitive") == "agent-exec"]
        assert agents
        assert all(step["config"]["adapter"] == "kiro-cli" for step in agents)
        assert all(step["config"]["prompt"].startswith("You are the Coding agent") for step in agents)
    assert STAGES == ("plan", "implement", "verify-and-fix", "approval", "integrate")


def test_stage_calls_use_declared_inputs() -> None:
    document = _document()
    expected = {
        "plan-story.yaml": {"repo_path", "story_key", "story_path", "guide_path", "spec_path"},
        "implement-story.yaml": {"repo_path", "story_key", "spec_path", "branch", "base_ref"},
        "verify-and-fix-story.yaml": {"repo_path", "story_key", "spec_path", "branch", "base_ref", "change_id", "inventory_version"},
        "approve-change.yaml": {"repo_path", "change_id", "revision", "actor", "decision_commit"},
        "integrate-story.yaml": {"repo_path", "story_key", "spec_path", "branch", "base_branch", "remote", "change_id", "parent_path", "parent_branch", "status_path"},
    }
    for step in document["steps"]:
        if step.get("primitive") != "call-agent":
            continue
        name = step["config"]["workflow"]
        assert set(step["config"]["inputs"]) == expected[name]


import asyncio
import json
import sys

import pytest
from beddel.domain.executor import WorkflowExecutor
from beddel.domain.kit import parse_kit_manifest
from beddel.domain.models import AgentResult, DefaultDependencies
from beddel.domain.registry import PrimitiveRegistry
from beddel.primitives import register_builtins
from beddel.tools.kits import load_kit

from ._helpers import commit_all, git, stub_gate_tools
from .test_integrate_workflow import _fixture, _Host

sys.path.insert(0, str(KIT_ROOT.parent / "tools-git-kit" / "python"))
sys.path.insert(0, str(KIT_ROOT.parent / "tools-github-kit" / "python"))

STORY = "7-7-deliver-story-workflow-chains-stages-and-resumes"
BRANCH = "feat/work"


def _spec() -> bytes:
    return (
        f"---\nstory_key: {STORY}\nrequirements: [FR-13]\n"
        "repositories: [.]\ndependencies: []\nsize_cap_bytes: 64000\n"
        'units:\n  - id: u1\n    paths: [src/delivered.py]\n    subject: "feat: deliver"\n---\n\n# Fixture\n'
    ).encode()


class _CodingAgent:
    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.calls = 0

    async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
        self.calls += 1
        if "one plan stage" in prompt:
            (self.repo / "specs" / "story.md").write_bytes(_spec())
        elif "one implementation unit" in prompt:
            (self.repo / "src" / "delivered.py").write_text("delivered = True\n")
        return AgentResult(0, "", [], [], {}, "fake")


def _workflow_run(
    env: dict[str, Any],
    agent: _CodingAgent,
    host: _Host,
    monkeypatch: pytest.MonkeyPatch,
    approval: dict[str, Any] | None,
    report: dict[str, Any],
    approve_change: Any,
    *,
    stage: str = "all",
    actor: str = "owner",
) -> dict[str, Any]:
    from beddel_profile_dev.tools import deliver as deliver_tools
    from beddel_profile_dev.tools import integrate as integrate_tools

    monkeypatch.setattr(deliver_tools, "profile_read_approval", lambda *a: {"approval": approval["value"] if isinstance(approval, dict) and "value" in approval else approval})
    monkeypatch.setattr(deliver_tools, "profile_read_report", lambda *a: {"report": report, "history": [{"ref": "changes/c1/report/1.json", "content": report}]})
    monkeypatch.setattr(integrate_tools, "profile_read_approval", lambda *a: {"approval": approval["value"] if isinstance(approval, dict) and "value" in approval else approval})
    monkeypatch.setattr(integrate_tools, "profile_read_report", lambda *a: {"report": report})
    registry: dict[str, Any] = {}
    for name in ("profile-dev-kit", "tools-git-kit", "tools-github-kit"):
        registry.update(load_kit(parse_kit_manifest(KIT_ROOT.parent / name / "kit.yaml")))
    registry.update({
        "profile_approve_change": approve_change,
        "github_pr_create_or_reuse": host.create,
        "github_pr_checks_wait": host.checks,
        "github_pr_merge": host.merge,
    })
    async def consistent(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"stage": "verify-and-fix", "story_key": STORY, "verify": False, "fix": False, "outcome": "succeeded", "reason": "verdict.consistent", "refs": {"stage": "verify"}}
    registry["profile_fix_reconcile"] = consistent
    registry["profile_fix_settle"] = consistent
    primitive = PrimitiveRegistry()
    register_builtins(primitive)
    dependencies = DefaultDependencies(
        agent_registry={"kiro-cli": agent},
        tool_registry=registry,
        registry=primitive,
        workflow_loader=lambda name: WorkflowParser.parse((KIT_ROOT / "workflows" / name).read_text()),
    )
    inputs = {
        "repo_path": str(env["sub"]), "story_key": STORY, "stage": stage,
        "story_path": "story.md", "guide_path": "guide.md", "spec_path": "specs/story.md",
        "branch": BRANCH, "base_ref": env["base"], "change_id": "c1", "inventory_version": "v1",
        "actor": actor, "base_branch": "main", "remote": "origin", "parent_path": str(env["parent"]),
        "parent_branch": "main", "status_path": "status.yaml",
    }
    return asyncio.run(WorkflowExecutor(primitive, deps=dependencies).execute(WorkflowParser.parse(WORKFLOW.read_text()), inputs))


def _deliver_records(home: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text())
        for path in sorted(home.rglob("stage-outcomes/*.json"), key=lambda p: int(p.stem))
    ]


def test_end_to_end_stops_for_owner_then_resumes_to_integration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _fixture(tmp_path)
    sub = env["sub"]
    (sub / "story.md").write_text("story\n")
    (sub / "guide.md").write_text("guide\n")
    (sub / "specs").mkdir()
    (sub / "src").mkdir()
    (env["parent"] / "status.yaml").write_text(f"x: 1\n  {STORY}: review  # keep\n")
    env["tip"] = commit_all(sub, "delivery inputs")
    report = {"revision": env["tip"], "verdict": "consistent"}
    approval_box: dict[str, Any] = {"value": None}
    calls: list[str] = []
    def approve_change(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs["actor"])
        if kwargs["actor"] == "owner":
            approval_box["value"] = {"revision": report["revision"], "proof": {"commit": kwargs["decision_commit"]}}
        return {"ok": True}
    monkeypatch.chdir(sub)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    host = _Host(env)
    agent = _CodingAgent(sub)
    first = _workflow_run(env, agent, host, monkeypatch, approval_box, report, approve_change)
    assert first["step_results"]["record"]["result"]["reason"] == "stage.stopped"
    report["revision"] = git(sub, "rev-parse", "HEAD")
    assert calls == []
    decision = sub / ".beddel-profile" / "approvals" / "c1" / "1.yaml"
    decision.parent.mkdir(parents=True)
    decision.write_text("decision: approved\n")
    git(sub, "add", "--", ".beddel-profile/approvals")
    git(sub, "commit", "-q", "-m", "owner decision")
    env["tip"] = git(sub, "rev-parse", "HEAD")
    wrong = _workflow_run(env, agent, host, monkeypatch, approval_box["value"], report, approve_change, actor="wrong")
    assert wrong["step_results"]["record"]["result"]["reason"] == "stage.refused"
    assert calls == ["wrong"]
    approval_box["value"] = None
    right = _workflow_run(env, agent, host, monkeypatch, approval_box, report, approve_change)
    assert right["step_results"]["record"]["result"]["reason"] == "stage.stopped"
    assert calls == ["wrong", "owner"]
    git(env["parent"], "push", "-q", "origin", "main")
    resumed = _workflow_run(env, agent, host, monkeypatch, approval_box, report, approve_change)
    assert resumed["step_results"]["record"]["result"]["reason"] == "deliver.complete"
    _workflow_run(env, agent, host, monkeypatch, approval_box, report, approve_change)
    complete_records = _deliver_records(tmp_path / "home")
    assert any(record["reason"] == "deliver.complete" and record["refs"]["invoked"] == "" for record in complete_records)
    assert calls == ["wrong", "owner"]
    records = _deliver_records(tmp_path / "home")
    assert records and all(record["stage"] in {"plan", "implement", "verify-and-fix", "approval", "integrate", "deliver"} for record in records)
    assert host.calls.count("merge") == 1


def test_single_stage_runs_only_that_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _fixture(tmp_path)
    sub = env["sub"]
    (sub / "story.md").write_text("story\n")
    (sub / "guide.md").write_text("guide\n")
    (sub / "specs").mkdir()
    (sub / "src").mkdir()
    env["tip"] = commit_all(sub, "delivery inputs")
    monkeypatch.chdir(sub)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    agent = _CodingAgent(sub)
    host = _Host(env)
    report = {"revision": env["tip"], "verdict": "consistent"}
    (sub / "specs" / "story.md").write_bytes(_spec())
    result = _workflow_run(env, agent, host, monkeypatch, None, report, lambda **kwargs: {"ok": True}, stage="implement")
    assert result["step_results"]["record"]["result"]["stage"] == "deliver"
    records = _deliver_records(tmp_path / "home")
    assert {record["stage"] for record in records} == {"implement", "deliver"}
    assert records[-1]["stage"] == "deliver"


def test_stage_failure_unrecorded_stage_and_fix_bound_do_not_advance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _fixture(tmp_path)
    sub = env["sub"]
    (sub / "story.md").write_text("story\n")
    (sub / "guide.md").write_text("guide\n")
    (sub / "specs").mkdir()
    (sub / "src").mkdir()
    env["tip"] = commit_all(sub, "delivery inputs")
    monkeypatch.chdir(sub)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    class FailingAgent(_CodingAgent):
        async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
            self.calls += 1
            if "one plan stage" in prompt:
                (self.repo / "specs" / "story.md").write_bytes(_spec())
            return AgentResult(1, "failed", [], [], {}, "fake")
    agent = FailingAgent(sub)
    host = _Host(env)
    report = {"revision": env["tip"], "verdict": "consistent"}
    result = _workflow_run(env, agent, host, monkeypatch, None, report, lambda **kwargs: {"ok": True})
    assert result["step_results"]["record"]["result"]["reason"] == "stage.failed"
    assert host.calls == []
