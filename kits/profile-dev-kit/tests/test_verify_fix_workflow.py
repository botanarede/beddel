"""Shape and safety coverage for the verify-and-fix entry workflow."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from beddel.domain.kit import parse_kit_manifest
from beddel.domain.models import AgentResult, DefaultDependencies, StrategyType
from beddel.domain.parser import WorkflowParser
from beddel.domain.registry import PrimitiveRegistry
from beddel.primitives import register_builtins
from beddel.tools.kits import load_kit
from beddel_profile_dev import _adapters
from beddel_profile_dev.findings import (
    ASSESSMENT_BEGIN,
    ASSESSMENT_END,
    REVIEW_ASSESSMENT_SCHEMA,
)
from beddel_profile_dev.hook_proof import HOOK_KEYS, policy_path

from ._helpers import (
    FakeReviewAdapter,
    commit_all,
    emit_hook_events,
    git,
    good,
    init_repo,
    make_source,
    stub_gate_tools,
    write_version,
)

KIT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = KIT_ROOT / "workflows" / "verify-and-fix-story.yaml"


def test_workflow_shape_and_bound() -> None:
    document = yaml.safe_load(WORKFLOW_PATH.read_text())
    assert document["id"] == "verify-and-fix-story"
    assert document["requires_kits"] == ["profile-dev-kit", "agent-kiro-kit"]
    assert document["inputs"] == [
        "repo_path",
        "story_key",
        "spec_path",
        "branch",
        "base_ref",
        "change_id",
        "inventory_version",
        "instruction",
    ]
    assert document["allowed_tools"] == [
        "profile_fix_reconcile",
        "profile_fix_settle",
        "profile_record_stage_outcome",
        "profile_hook_open",
        "profile_hook_arm",
        "profile_hook_disarm",
        "profile_hook_proof",
        "profile_stage_instruction",
    ]
    assert "mcp_servers" not in document
    assert not any(
        word in document["allowed_tools"]
        for word in ("approve", "ratify", "integrate", "push", "publish")
    )
    steps = WorkflowParser.parse(WORKFLOW_PATH.read_text()).steps
    assert [step.id for step in steps] == [
        "hook_open",
        "reconcile",
        "verify",
        "round_1",
        "method",
        "arm_1",
        "fix_1",
        "fix_1_method",
        "disarm_1",
        "settle_1",
        "settle_1_stop",
        "verify_1",
        "round_2",
        "arm_2",
        "fix_2",
        "fix_2_method",
        "disarm_2",
        "settle_2",
        "settle_2_stop",
        "verify_2",
        "close",
        "proof",
        "record",
    ]
    assert all(
        step.config.get("arguments", {}).get("max_fix_rounds") == 2
        for step in steps
        if step.id in {"reconcile", "round_1", "round_2", "close"}
    )
    agents = [step for step in steps if step.primitive == "agent-exec"]
    assert len(agents) == 4
    assert all(
        step.config["adapter"] == "kiro-cli"
        and step.config["sandbox"] == "workspace-write"
        and step.timeout <= 600
        for step in agents
    )
    nested = [step for step in steps if step.primitive == "call-agent"]
    assert len(nested) == 3
    assert all(step.config["workflow"] == "verify-change.yaml" for step in nested)
    assert all(
        list(step.config["inputs"])
        == [
            "repo_path",
            "change_id",
            "base",
            "revision",
            "inventory_version",
        ]
        for step in nested
    )
    assert all(step.execution_strategy.type is StrategyType.SKIP for step in nested)
    step_map = {step.id: step for step in steps}
    assert (
        step_map["settle_1"].output_key
        == step_map["settle_1_stop"].output_key
        == "fixed_1"
    )
    assert (
        step_map["settle_2"].output_key
        == step_map["settle_2_stop"].output_key
        == "fixed_2"
    )
    assert {
        step.id: step.if_condition for step in steps if step.if_condition is not None
    } == {
        "verify": "$stepResult.reconcile.result.verify == true",
        "arm_1": "$stepResult.round_1.result.fix == true",
        "method": "$input.instruction",
        "fix_1": "$stepResult.arm_1.result.native == true",
        "fix_1_method": "$stepResult.arm_1.result.method == true",
        "disarm_1": "$stepResult.round_1.result.fix == true",
        "settle_1": "$stepResult.round_1.result.fix == true",
        "settle_1_stop": "$stepResult.round_1.result.fix != true",
        "verify_1": "$stepResult.fixed_1.result.verify == true",
        "arm_2": "$stepResult.round_2.result.fix == true",
        "fix_2": "$stepResult.arm_2.result.native == true",
        "fix_2_method": "$stepResult.arm_2.result.method == true",
        "disarm_2": "$stepResult.round_2.result.fix == true",
        "settle_2": "$stepResult.round_2.result.fix == true",
        "settle_2_stop": "$stepResult.round_2.result.fix != true",
        "verify_2": "$stepResult.fixed_2.result.verify == true",
    }
    assert all(
        step.execution_strategy.type is StrategyType.FAIL
        for step in steps
        if step.primitive == "tool" and step.id not in {"reconcile", "hook_open"}
    )


STORY = "7-5-verify-fix-fixture"
SPEC_PATH = "specs/story.md"
BRANCH = "feat/story-7-5"


def _spec() -> bytes:
    return (
        (
            f"---\nstory_key: {STORY}\nrequirements: [FR-14]\n"
            "repositories: [. ]\ndependencies: []\nsize_cap_bytes: 64000\n"
            'units:\n  - id: u1\n    paths: [src/api.py]\n    subject: "feat: update api"\n---\n\n# Fixture\n'
        )
        .replace("[. ]", "[.]")
        .encode()
    )


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = init_repo(tmp_path / "repo")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    make_source(repo)
    write_version(repo, "v1", good())
    from beddel_profile_dev.tools.ratify import profile_ratify_inventory

    profile_ratify_inventory(str(repo), "v1", "owner")
    (repo / SPEC_PATH).parent.mkdir()
    (repo / SPEC_PATH).write_bytes(_spec())
    base = commit_all(repo, "base")
    git(repo, "switch", "-q", "-c", BRANCH)
    (repo / "src/api.py").write_text("x = 2\n")
    git(repo, "add", "--", "src/api.py")
    git(
        repo,
        "commit",
        "-q",
        "-m",
        "feat: update api",
        "-m",
        f"Story-Key: {STORY}\nImplementation-Unit: u1",
    )
    return repo, base


class FixAgent:
    def __init__(
        self,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        hook_mode: str = "complete",
    ) -> None:
        self.repo = repo
        self.monkeypatch = monkeypatch
        self.hook_mode = hook_mode
        self.calls = 0

    async def execute(
        self,
        prompt: str,
        *,
        model: str | None = None,
        sandbox: str = "read-only",
        tools: list[str] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> AgentResult:
        self.calls += 1
        events: list[Any] = ["pre", "post", "stop"]
        if self.hook_mode == "missing-stop":
            events = ["pre", "post"]
        elif self.hook_mode == "hook-error":
            events = [{"hook_event_name": "unknown"}, "stop"]
        emit_hook_events(self.repo, events)
        (self.repo / "src/api.py").write_text("x = 3\n")
        self.monkeypatch.setenv("STUB_EXIT_PYTEST", "0")
        return AgentResult(0, "", [], [], {}, "fake")


def _run_stage(
    repo: Path, fake: FixAgent, base: str, **overrides: object
) -> dict[str, Any]:
    workflow = WorkflowParser.parse(WORKFLOW_PATH.read_text())
    registry = PrimitiveRegistry()
    register_builtins(registry)
    tools = load_kit(parse_kit_manifest(KIT_ROOT / "kit.yaml"))
    dependencies = DefaultDependencies(
        agent_registry={"kiro-cli": fake},
        tool_registry=tools,
        registry=registry,
        workflow_loader=lambda name: WorkflowParser.parse(
            (KIT_ROOT / "workflows" / name).read_text()
        ),
    )
    from beddel.domain.executor import WorkflowExecutor

    payload = {
        "repo_path": str(repo),
        "story_key": STORY,
        "spec_path": SPEC_PATH,
        "branch": BRANCH,
        "base_ref": base,
        "change_id": "c1",
        "inventory_version": "v1",
    }
    payload.update(overrides)
    return asyncio.run(
        WorkflowExecutor(registry, deps=dependencies).execute(workflow, payload)
    )


def _review_output() -> str:
    payload = {
        "schema": REVIEW_ASSESSMENT_SCHEMA,
        "assessments": [
            {
                "class": "review-arch",
                "affected_point": "api",
                "criterion": "arch-ok",
                "divergences": [],
            }
        ],
        "unassociated": [],
    }
    return f"{ASSESSMENT_BEGIN}\n{json.dumps(payload)}\n{ASSESSMENT_END}\n"


def test_in_process_consistent_run_has_one_report_and_no_fix_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("STUB_EXIT_PYTEST", "0")
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: FakeReviewAdapter(
            "completed", output=_review_output()
        ),
    )
    fake = FixAgent(repo, monkeypatch)
    result = _run_stage(repo, fake, base)
    close = result["step_results"]["close"]["result"]
    assert (close["outcome"], close["reason"], fake.calls) == (
        "succeeded",
        "verdict.consistent",
        0,
    )
    assert len(list((tmp_path / "home").rglob("changes/c1/report/*.json"))) == 1
    stored = json.loads(
        next((tmp_path / "home").rglob("stage-outcomes/*.json")).read_text()
    )
    assert all(stored["refs"][key] is None for key in HOOK_KEYS)


# fmt: off
def test_in_process_fix_round_commits_and_reverifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("STUB_EXIT_PYTEST", "1")
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: FakeReviewAdapter(
            "completed", output=_review_output()
        ),
    )
    fake = FixAgent(repo, monkeypatch)
    result = _run_stage(repo, fake, base)
    close = result["step_results"]["close"]["result"]
    reports = sorted((tmp_path / "home").rglob("changes/c1/report/*.json"))
    assert (close["outcome"], close["reason"], fake.calls) == (
        "succeeded",
        "verdict.consistent",
        1,
    )
    assert len(reports) == 2
    assert "Fix-Round: 1" in git(repo, "show", "-s", "--format=%B", "HEAD")
    assert json.loads(reports[1].read_text())["reverification"]["status"] == "recorded"
    first, second = (json.loads(path.read_text()) for path in reports)
    assert first["revision"] != second["revision"]
    links = [link for link in second["reverification"]["links"] if link["class"] == "gate-unit"]
    assert links and all(link["result"] == "resolved" for link in links)
    assert all(not item["ref"].startswith(f"revisions/{first['revision']}/") for item in second["reads"] if "ref" in item)
    record = json.loads(
        next((tmp_path / "home").rglob("stage-outcomes/*.json")).read_text()
    )
    refs = record["refs"]
    assert set(HOOK_KEYS) <= set(refs)
    assert refs["hook_stop"] == 1
    assert refs["hook_errors"] == 0
    assert refs["hook_policy_sha256"] == hashlib.sha256(
        policy_path("verify-and-fix").read_bytes()
    ).hexdigest()
class ErrorAgent(FixAgent):
    async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
        from beddel.domain.errors import AgentError
        from beddel.error_codes import AGENT_EXECUTION_FAILED

        self.calls += 1
        emit_hook_events(self.repo, ["pre", "post", "stop"])
        raise AgentError(code=AGENT_EXECUTION_FAILED, message="x")


class PersistentAgent(FixAgent):
    async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
        self.calls += 1
        emit_hook_events(self.repo, ["pre", "post", "stop"])
        (self.repo / "src/api.py").write_text(f"x = {self.calls + 2}\n")
        return AgentResult(0, "", [], [], {}, "fake")


class OutOfScopeAgent(FixAgent):
    async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
        self.calls += 1
        emit_hook_events(self.repo, ["pre", "post", "stop"])
        (self.repo / "README.md").write_text("outside\n")
        return AgentResult(0, "", [], [], {}, "fake")


def _install_review(monkeypatch: pytest.MonkeyPatch, behavior: str = "completed") -> None:
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: FakeReviewAdapter(
            behavior, output=_review_output()
        ),
    )


def test_workflow_persistent_finding_hits_bound_and_rerun_reuses_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("STUB_EXIT_PYTEST", "1")
    _install_review(monkeypatch)
    fake = PersistentAgent(repo, monkeypatch)
    result = _run_stage(repo, fake, base)
    close = result["step_results"]["close"]["result"]
    assert (close["outcome"], close["reason"], fake.calls) == ("stopped", "fix.bound_reached", 2)
    assert len(list(home.rglob("changes/c1/report/*.json"))) == 3
    assert not list(home.rglob("changes/c1/approval.json"))
    rerun = _run_stage(repo, fake, base)
    assert len(list(home.rglob("changes/c1/report/*.json"))) == 3
    records = sorted(home.rglob("stage-outcomes/*.json"))
    assert [path.name for path in records] == ["1.json", "2.json"]
    first_stage = json.loads(records[0].read_text())
    assert first_stage["refs"]["hook_stop"] == 2
    assert first_stage["refs"]["hook_errors"] == 0
    assert rerun["step_results"]["record"]["result"]["record"] == 2


def test_workflow_maps_agent_error_refusal_timeout_inventory_and_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cases = ["timeout", "agent", "refusal", "inventory", "scope"]
    for case in cases:
        root = tmp_path / case
        repo, base = _repo(root)
        monkeypatch.chdir(repo)
        monkeypatch.setenv("PATH", stub_gate_tools(root))
        monkeypatch.setenv("HOME", str(root / "home"))
        if case == "timeout":
            _install_review(monkeypatch, "timeout")
            fake: FixAgent = FixAgent(repo, monkeypatch)
            expected = "pendency.no_fixes"
        elif case == "agent":
            monkeypatch.setenv("STUB_EXIT_PYTEST", "1")
            _install_review(monkeypatch)
            fake = ErrorAgent(repo, monkeypatch)
            expected = "agent.failed"
        elif case == "scope":
            monkeypatch.setenv("STUB_EXIT_PYTEST", "1")
            _install_review(monkeypatch)
            fake = OutOfScopeAgent(repo, monkeypatch)
            expected = "scope.exceeded"
        else:
            _install_review(monkeypatch)
            fake = FixAgent(repo, monkeypatch)
            expected = "branch.protected" if case == "refusal" else "verify.failed"
        overrides: dict[str, object] = {}
        if case == "refusal": overrides["branch"] = "main"
        if case == "inventory": overrides["inventory_version"] = "missing"
        result = _run_stage(repo, fake, base, **overrides)
        close = result["step_results"]["close"]["result"]
        assert close["reason"] == expected
        if case in ("agent", "timeout"): assert fake.calls == (case == "agent")
        if case == "inventory": assert "verify" in str(result.get("absorbed_errors"))


# fmt: on


@pytest.mark.parametrize(
    ("hook_mode", "reason"),
    [("missing-stop", "hooks.missing"), ("hook-error", "hooks.errors")],
)
def test_workflow_records_hook_proof_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hook_mode: str,
    reason: str,
) -> None:
    repo, base = _repo(tmp_path / hook_mode)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path / hook_mode))
    monkeypatch.setenv("HOME", str(tmp_path / hook_mode / "home"))
    monkeypatch.setenv("STUB_EXIT_PYTEST", "1")
    _install_review(monkeypatch)
    result = _run_stage(repo, FixAgent(repo, monkeypatch, hook_mode), base)
    record = json.loads(
        next((tmp_path / hook_mode / "home").rglob("stage-outcomes/*.json")).read_text()
    )
    assert record["reason"] == reason
    assert result["step_results"]["record"]["result"]["record"] == 1
