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
        "repair_arm_1",
        "repair_1",
        "repair_disarm_1",
        "resettle_1",
        "settle_1_stop",
        "verify_1",
        "round_2",
        "arm_2",
        "fix_2",
        "fix_2_method",
        "disarm_2",
        "settle_2",
        "repair_arm_2",
        "repair_2",
        "repair_disarm_2",
        "resettle_2",
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
    assert len(agents) == 6
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
    for name in ("fix_1", "fix_2"):
        assert step_map[f"{name}_method"].config["prompt"] == (
            step_map[name].config["prompt"]
            + " Method instruction: $stepResult.method.result.instruction"
        )
    assert (
        step_map["resettle_1"].output_key
        == step_map["settle_1_stop"].output_key
        == "fixed_1"
    )
    assert (
        step_map["resettle_2"].output_key
        == step_map["settle_2_stop"].output_key
        == "fixed_2"
    )
    assert step_map["settle_1"].output_key is None
    assert step_map["settle_2"].output_key is None
    for n in ("1", "2"):
        repair, fix = step_map[f"repair_{n}"], step_map[f"fix_{n}"]
        assert {**repair.config, "prompt": None} == {**fix.config, "prompt": None}
        assert repair.timeout == fix.timeout == 600
        prompt = repair.config["prompt"]
        assert f"$stepResult.round_{n}.result.round" in prompt
        assert f"$stepResult.settle_{n}.result.refs.regressed" in prompt
        assert f"$stepResult.round_{n}.result.scope_paths" in prompt
        assert "findings" not in prompt and "spec_path" not in prompt
        assert "instruction" not in prompt and "commit" in prompt
        assert "method" not in step_map[f"repair_arm_{n}"].config["arguments"]
        assert step_map[f"resettle_{n}"].config["arguments"] == {
            **step_map[f"settle_{n}"].config["arguments"],
            "agent": f"$stepResult.repair_{n}",
            "prior": f"$stepResult.settle_{n}.result",
        }
    proof = step_map["proof"].config["arguments"]
    assert proof["calls"] == [
        f"$stepResult.{name}.result"
        for name in ("arm_1", "repair_arm_1", "arm_2", "repair_arm_2")
    ]
    assert proof["timings"] == [
        f"$stepResult.{name}.result"
        for name in ("disarm_1", "repair_disarm_1", "disarm_2", "repair_disarm_2")
    ]
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
        "repair_arm_1": "$stepResult.settle_1.result.repair == true",
        "repair_1": "$stepResult.repair_arm_1.result.native == true",
        "repair_disarm_1": "$stepResult.settle_1.result.repair == true",
        "resettle_1": "$stepResult.round_1.result.fix == true",
        "settle_1_stop": "$stepResult.round_1.result.fix != true",
        "verify_1": "$stepResult.fixed_1.result.verify == true",
        "arm_2": "$stepResult.round_2.result.fix == true",
        "fix_2": "$stepResult.arm_2.result.native == true",
        "fix_2_method": "$stepResult.arm_2.result.method == true",
        "disarm_2": "$stepResult.round_2.result.fix == true",
        "settle_2": "$stepResult.round_2.result.fix == true",
        "repair_arm_2": "$stepResult.settle_2.result.repair == true",
        "repair_2": "$stepResult.repair_arm_2.result.native == true",
        "repair_disarm_2": "$stepResult.settle_2.result.repair == true",
        "resettle_2": "$stepResult.round_2.result.fix == true",
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
    assert refs["repair"] is None and len(refs) <= 32
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


class RepairAgent(FixAgent):
    """Odd calls are fix rounds that regress ``03-mypy``; even calls repair it.

    ``mode`` ``repaired`` clears the Finding with the first fix, ``persistent``
    keeps it so both rounds run, ``still-red`` leaves the Gate red after the
    repair and ``error`` fails the repair call.
    """

    def __init__(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch, mode: str = "repaired"
    ) -> None:
        super().__init__(repo, monkeypatch)
        self.mode = mode
        self.prompts: list[str] = []

    async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
        from beddel.domain.errors import AgentError
        from beddel.error_codes import AGENT_EXECUTION_FAILED

        self.calls += 1
        self.prompts.append(prompt)
        emit_hook_events(self.repo, ["pre", "post", "stop"])
        if self.mode == "error" and self.calls == 2:
            raise AgentError(code=AGENT_EXECUTION_FAILED, message="x")
        (self.repo / "src/api.py").write_text(f"x = {self.calls + 2}\n")
        if self.mode != "persistent":
            self.monkeypatch.setenv("STUB_EXIT_PYTEST", "0")
        red = self.calls % 2 == 1 or self.mode == "still-red"
        self.monkeypatch.setenv("STUB_EXIT_MYPY", "1" if red else "0")
        return AgentResult(0, "", [], [], {}, "fake")


def _repair_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, **overrides: object
) -> tuple[Path, str, RepairAgent, dict[str, Any], dict[str, Any]]:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("STUB_EXIT_PYTEST", "1")
    _install_review(monkeypatch)
    fake = RepairAgent(repo, monkeypatch, mode)
    result = _run_stage(repo, fake, base, **overrides)
    (path,) = (tmp_path / "home").rglob("stage-outcomes/1.json")
    return repo, base, fake, result["step_results"], json.loads(path.read_text())


def test_repair_round_commits_fix_round_and_reverifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _base, fake, steps, record = _repair_stage(tmp_path, monkeypatch, "repaired")
    first = steps["settle_1"]["result"]
    assert (first["repair"], first["refs"]["regressed"]) == (True, "03-mypy")
    fixed = steps["fixed_1"]["result"]
    assert (fixed["verify"], fixed["refs"]["repair"]) == (True, "03-mypy")
    assert fixed["refs"]["regressed"] is None
    assert len(list((tmp_path / "home").rglob("changes/c1/report/*.json"))) == 2
    assert fake.calls == 2
    repair_prompt = fake.prompts[1]
    assert "round 1 " in repair_prompt and "03-mypy" in repair_prompt
    assert "src/api.py" in repair_prompt and SPEC_PATH not in repair_prompt
    assert steps["round_1"]["result"]["findings"] not in repair_prompt
    arm, repair_arm = steps["arm_1"]["result"], steps["repair_arm_1"]["result"]
    assert repair_arm["native"] is True and repair_arm["log_path"] == arm["log_path"]
    assert "Fix-Round: 1" in git(repo, "show", "-s", "--format=%B", "HEAD")
    assert (record["outcome"], record["reason"]) == ("succeeded", "verdict.consistent")
    refs = record["refs"]
    assert (refs["hook_stop"], refs["hook_errors"], refs["agent_timeouts"]) == (2, 0, 0)
    assert len(str(refs["agent_ms"]).split(",")) == 2
    # The record comes from the reconcile after verify_1, which rebuilds refs.
    assert refs["repair"] is None
    assert len(refs) <= 32


def test_each_round_gets_one_repair_and_the_proof_counts_four_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _base, fake, steps, record = _repair_stage(
        tmp_path, monkeypatch, "persistent"
    )
    assert fake.calls == 4
    assert (record["outcome"], record["reason"]) == ("stopped", "fix.bound_reached")
    assert steps["fixed_2"]["result"]["refs"]["repair"] == "03-mypy"
    assert "round 2 " in fake.prompts[3]
    refs = record["refs"]
    assert (refs["hook_stop"], refs["hook_errors"]) == (4, 0)
    assert len(str(refs["agent_ms"]).split(",")) == 4
    assert "Fix-Round: 2" in git(repo, "show", "-s", "--format=%B", "HEAD")


@pytest.mark.parametrize(
    ("mode", "reason"), [("still-red", "gate.regressed"), ("error", "agent.failed")]
)
def test_failed_repair_ends_failed_without_a_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, reason: str
) -> None:
    repo, _base, fake, steps, record = _repair_stage(tmp_path, monkeypatch, mode)
    before = steps["round_1"]["result"]["head"]
    assert fake.calls == 2
    assert (record["outcome"], record["reason"]) == ("failed", reason)
    refs = record["refs"]
    assert refs["repair"] == "03-mypy"
    assert refs["regressed"] == ("03-mypy" if mode == "still-red" else None)
    assert (refs["hook_stop"], refs["hook_errors"]) == (2, 0)
    assert git(repo, "rev-parse", "HEAD") == before
    assert len(list((tmp_path / "home").rglob("changes/c1/report/*.json"))) == 1


def test_repair_call_shares_the_stage_tool_call_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from beddel_profile_dev import hook_proof

    policy = json.loads(policy_path("verify-and-fix").read_text())
    policy["max_tool_calls"] = 1
    capped = tmp_path / "verify-and-fix.json"
    capped.write_text(json.dumps(policy))
    monkeypatch.setattr(hook_proof, "policy_path", lambda _stage: capped)
    _repo_path, _base, _fake, steps, record = _repair_stage(
        tmp_path, monkeypatch, "repaired"
    )
    log = Path(steps["arm_1"]["result"]["log_path"])
    pre = [
        item
        for item in (json.loads(line) for line in log.read_text().splitlines())
        if item["event"] == "pre"
    ]
    assert [(item["decision"], item["rule_id"]) for item in pre] == [
        ("allow", "read.any"),
        ("deny", "cap.max_tool_calls"),
    ]
    assert (record["refs"]["hook_denied"], record["refs"]["hook_stop"]) == (1, 2)


def test_repair_under_a_method_keeps_the_method_digest_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instruction = "Use the named method for this round only."
    _repo_path, _base, fake, _steps, record = _repair_stage(
        tmp_path, monkeypatch, "repaired", instruction=instruction
    )
    assert fake.calls == 2
    assert instruction in fake.prompts[0] and instruction not in fake.prompts[1]
    assert record["reason"] == "verdict.consistent"
    assert (
        record["refs"]["instruction_sha256"]
        == hashlib.sha256(instruction.encode()).hexdigest()
    )


def test_unarmed_repair_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from beddel_profile_dev.tools import hook as hook_tools

    original = hook_tools.write_pointer
    seen: list[int] = []

    def second_refused(*args: Any) -> dict[str, Any]:
        seen.append(1)
        if len(seen) == 2:
            return {"armed": False, "reason": "hooks.pointer_exists"}
        return original(*args)

    monkeypatch.setattr(hook_tools, "write_pointer", second_refused)
    repo, _base, fake, steps, record = _repair_stage(tmp_path, monkeypatch, "repaired")
    assert fake.calls == 1
    assert (record["outcome"], record["reason"]) == ("failed", "hooks.pointer_exists")
    assert record["refs"]["repair"] == "03-mypy"
    assert git(repo, "rev-parse", "HEAD") == steps["round_1"]["result"]["head"]
