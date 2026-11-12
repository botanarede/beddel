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

def test_deliver_workflow_shape() -> None:
    document = yaml.safe_load(WORKFLOW.read_text())
    assert document["id"] == "deliver-story"
    assert document["requires_kits"] == ["profile-dev-kit", "agent-kiro-kit", "tools-git-kit", "tools-github-kit"]
    steps = document["steps"]
    assert len([step for step in steps if str(step["id"]).startswith("implement_")]) == IMPLEMENT_SLOTS
    calls = [step["config"]["workflow"] for step in steps if step.get("primitive") == "call-agent"]
    assert set(calls) == {"plan-story.yaml", "implement-story.yaml", "verify-and-fix-story.yaml", "approve-change.yaml", "integrate-story.yaml"}
    assert calls.count("approve-change.yaml") == 1 and all("$" not in call for call in calls)


def test_stage_workflows_state_their_coding_agent() -> None:
    for name in ("plan-story.yaml", "implement-story.yaml", "verify-and-fix-story.yaml"):
        document = yaml.safe_load((KIT_ROOT / "workflows" / name).read_text())
        assert "Coding agent" in document["description"]
        agents = [step for step in document["steps"] if step.get("primitive") == "agent-exec"]
        assert agents and all(step["config"]["adapter"] == "kiro-cli" for step in agents)
        assert all(step["config"]["prompt"].startswith("You are the Coding agent") for step in agents)
    assert STAGES == ("plan", "implement", "verify-and-fix", "approval", "integrate")


def test_stage_call_names_are_static() -> None:
    document = yaml.safe_load(WORKFLOW.read_text())
    calls = [step["config"]["workflow"] for step in document["steps"] if step.get("primitive") == "call-agent"]
    assert all(call in {"plan-story.yaml", "implement-story.yaml", "verify-and-fix-story.yaml", "approve-change.yaml", "integrate-story.yaml"} for call in calls)


import asyncio
import json

import pytest
from beddel.domain.executor import WorkflowExecutor
from beddel.domain.kit import parse_kit_manifest
from beddel.domain.models import AgentResult, DefaultDependencies
from beddel.domain.registry import PrimitiveRegistry
from beddel.primitives import register_builtins
from beddel.tools.kits import load_kit

from ._helpers import commit_all, git, stub_gate_tools
from .test_integrate_workflow import _fixture, _Host

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
        elif "verification fix round" in prompt:
            (self.repo / "src" / "delivered.py").write_text(f"round = {self.calls}\n")
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
    fix_report: dict[str, Any] | None = None,
    loader_error: bool = False,
) -> dict[str, Any]:
    from beddel_profile_dev.tools import deliver as deliver_tools
    from beddel_profile_dev.tools import fix as fix_tools
    from beddel_profile_dev.tools import integrate as integrate_tools

    def current_report(repo: str, change: str) -> dict[str, Any]:
        revision = git(Path(repo), "rev-parse", "HEAD")
        content = {**(fix_report or report), "revision": revision, "verdict": (fix_report or report).get("verdict", "consistent")}
        return {"report": content, "history": [{"ref": f"changes/{change}/report/1.json", "content": content}]}

    monkeypatch.setattr(fix_tools, "profile_read_report", current_report)
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
    primitive = PrimitiveRegistry()
    register_builtins(primitive)
    def load_workflow(name: str) -> Any:
        if loader_error and name == "plan-story.yaml":
            raise RuntimeError("loader failed")
        return WorkflowParser.parse((KIT_ROOT / "workflows" / name).read_text())

    dependencies = DefaultDependencies(
        agent_registry={"kiro-cli": agent},
        tool_registry=registry,
        registry=primitive,
        workflow_loader=load_workflow,
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

def _tuples(records: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    return [(record["stage"], record["outcome"], record["reason"]) for record in records]

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
    from .test_verify_fix_workflow import _install_review

    _install_review(monkeypatch)
    _workflow_run(env, agent, host, monkeypatch, approval_box, report, approve_change)
    phase_one = _deliver_records(tmp_path / "home")
    assert _tuples(phase_one) == [
        ("plan", "succeeded", "spec.created"),
        ("implement", "succeeded", "unit.committed"),
        ("implement", "succeeded", "units.complete"),
        ("verify-and-fix", "succeeded", "verdict.consistent"),
        ("approval", "stopped", "approval.awaiting_owner"),
        ("deliver", "stopped", "stage.stopped"),
    ]
    calls_after_phase_one = agent.calls
    report["revision"] = git(sub, "rev-parse", "HEAD")
    assert calls == []
    decision = sub / ".beddel-profile" / "approvals" / "c1" / "1.yaml"
    decision.parent.mkdir(parents=True)
    decision.write_text("decision: approved\n")
    git(sub, "add", "--", ".beddel-profile/approvals")
    git(sub, "commit", "-q", "-m", "owner decision")
    env["tip"] = git(sub, "rev-parse", "HEAD")
    _workflow_run(env, agent, host, monkeypatch, approval_box["value"], report, approve_change, actor="wrong")
    wrong_records = _deliver_records(tmp_path / "home")
    assert _tuples(wrong_records)[-2:] == [("approval", "refused", "approval.refused"), ("deliver", "refused", "stage.refused")]
    assert calls == ["wrong"]
    approval_box["value"] = None
    _workflow_run(env, agent, host, monkeypatch, approval_box, report, approve_change)
    right_records = _deliver_records(tmp_path / "home")
    assert _tuples(right_records)[-4:] == [
        ("approval", "succeeded", "approval.recorded"),
        ("integrate", "succeeded", "merge.confirmed"),
        ("integrate", "stopped", "pointer.unpublished"),
        ("deliver", "stopped", "stage.stopped"),
    ]
    assert calls == ["wrong", "owner"]
    assert agent.calls == calls_after_phase_one
    git(env["parent"], "push", "-q", "origin", "main")
    _workflow_run(env, agent, host, monkeypatch, approval_box, report, approve_change)
    resumed_records = _deliver_records(tmp_path / "home")
    assert _tuples(resumed_records)[-3:] == [
        ("integrate", "succeeded", "merge.reused"),
        ("integrate", "succeeded", "integrate.complete"),
        ("deliver", "succeeded", "deliver.complete"),
    ]
    assert agent.calls == calls_after_phase_one
    assert host.calls.count("merge") == 1
    _workflow_run(env, agent, host, monkeypatch, approval_box, report, approve_change)
    complete_records = _deliver_records(tmp_path / "home")
    assert _tuples(complete_records)[-1:] == [("deliver", "succeeded", "deliver.complete")]
    assert agent.calls == calls_after_phase_one
    assert calls == ["wrong", "owner"]

def _stage_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], Path]:
    env = _fixture(tmp_path)
    sub = env["sub"]
    for name in ("story.md", "guide.md"):
        (sub / name).write_text("story\n")
    (sub / "specs").mkdir()
    (sub / "src").mkdir()
    env["tip"] = commit_all(sub, "delivery inputs")
    monkeypatch.chdir(sub)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return env, sub

def test_single_stage_runs_only_that_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env, sub = _stage_env(tmp_path, monkeypatch)
    agent = _CodingAgent(sub)
    host = _Host(env)
    report = {"revision": env["tip"], "verdict": "consistent"}
    (sub / "specs" / "story.md").write_bytes(_spec())
    result = _workflow_run(env, agent, host, monkeypatch, None, report, lambda **kwargs: {"ok": True}, stage="implement")
    assert result["step_results"]["record"]["result"]["stage"] == "deliver"
    assert result["step_results"]["record"]["result"]["outcome"] == "succeeded"
    assert result["step_results"]["record"]["result"]["reason"] == "stage.complete"
    records = _deliver_records(tmp_path / "home")
    assert records[-1]["stage"] == "deliver"
    assert records[-1]["refs"]["invoked"] == "implement"

    (tmp_path / "plan").mkdir()
    plan_env = _fixture(tmp_path / "plan")
    plan_sub = plan_env["sub"]
    (plan_sub / "story.md").write_text("story\n")
    (plan_sub / "guide.md").write_text("guide\n")
    (plan_sub / "specs").mkdir()
    commit_all(plan_sub, "planning inputs")
    monkeypatch.chdir(plan_sub)
    monkeypatch.setenv("HOME", str(tmp_path / "plan-home"))
    plan_agent = _CodingAgent(plan_sub)
    plan_host = _Host(plan_env)
    plan_result = _workflow_run(plan_env, plan_agent, plan_host, monkeypatch, None, {"revision": plan_env["tip"], "verdict": "consistent"}, lambda **kwargs: {"ok": True}, stage="plan")
    assert plan_result["step_results"]["record"]["result"]["reason"] == "stage.complete"

def test_stage_failure_unrecorded_stage_and_fix_bound_do_not_advance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env, sub = _stage_env(tmp_path, monkeypatch)
    from beddel.domain.errors import AgentError
    from beddel.error_codes import AGENT_EXECUTION_FAILED

    class FailingAgent(_CodingAgent):
        async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
            self.calls += 1
            if "one plan stage" in prompt:
                (self.repo / "specs" / "story.md").write_bytes(_spec())
                return AgentResult(0, "", [], [], {}, "fake")
            raise AgentError(code=AGENT_EXECUTION_FAILED, message="agent failed")
    agent = FailingAgent(sub)
    host = _Host(env)
    report = {"revision": env["tip"], "verdict": "consistent"}
    _workflow_run(env, agent, host, monkeypatch, None, report, lambda **kwargs: {"ok": True})
    records = _deliver_records(tmp_path / "home")
    assert _tuples(records)[-2:] == [("implement", "failed", "agent.failed"), ("deliver", "failed", "stage.failed")]
    first_calls = agent.calls
    _workflow_run(env, agent, host, monkeypatch, None, report, lambda **kwargs: {"ok": True})
    rerun_records = _deliver_records(tmp_path / "home")
    assert _tuples(rerun_records)[-2:] == [("implement", "failed", "agent.failed"), ("deliver", "failed", "stage.failed")]
    assert agent.calls == first_calls + 1
    assert host.calls == []

def test_fix_bound_stops_before_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env, sub = _stage_env(tmp_path, monkeypatch)
    agent = _CodingAgent(sub)
    report = {"revision": env["tip"], "verdict": "consistent"}
    pending = {"verdict": "has pendency", "items": {"divergences": {"status": "present", "value": [{"finding_index": 0}]}, "pendencies": {"status": "present", "value": [{"finding_index": 0, "reason": "finding_blocking"}]}}}
    _workflow_run(env, agent, _Host(env), monkeypatch, None, report, lambda **kwargs: {"ok": True}, fix_report=pending)
    records = _deliver_records(tmp_path / "home")
    assert _tuples(records)[-2:] == [("verify-and-fix", "stopped", "fix.bound_reached"), ("deliver", "stopped", "stage.stopped")]
    assert not any(record["stage"] == "approval" for record in records)

def test_loader_failure_stops_at_plan_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env, sub = _stage_env(tmp_path, monkeypatch)
    agent = _CodingAgent(sub)
    _workflow_run(env, agent, _Host(env), monkeypatch, None, {"revision": env["tip"], "verdict": "consistent"}, lambda **kwargs: {"ok": True}, loader_error=True)
    records = _deliver_records(tmp_path / "home")
    assert _tuples(records)[-1] == ("deliver", "failed", "stage.unrecorded")
    assert records[-1]["refs"]["stage"] == "plan"
    assert agent.calls == 0
