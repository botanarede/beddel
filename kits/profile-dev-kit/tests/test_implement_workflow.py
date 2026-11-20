"""Workflow shape and in-process Coding-agent coverage."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from beddel.domain.errors import AgentError, BeddelError
from beddel.domain.executor import WorkflowExecutor
from beddel.domain.kit import parse_kit_manifest
from beddel.domain.models import AgentResult, DefaultDependencies
from beddel.domain.parser import WorkflowParser
from beddel.domain.registry import PrimitiveRegistry
from beddel.error_codes import AGENT_EXECUTION_FAILED
from beddel.primitives import register_builtins
from beddel.tools.kits import load_kit
from beddel_profile_dev._errors import ProfileError
from beddel_profile_dev.hook_proof import HOOK_KEYS, policy_path
from beddel_profile_dev.tools import implement as implement_tools
from beddel_profile_dev.tools.stage_outcome import profile_record_stage_outcome

from ._helpers import commit_all, emit_hook_events, git, init_repo, stub_gate_tools
from .test_implement import BRANCH, SPEC_PATH, STORY, spec_bytes

KIT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = KIT_ROOT / "workflows" / "implement-story.yaml"


class FakeAgent:
    def __init__(
        self,
        repo: Path,
        mode: str = "sequence",
        patch: pytest.MonkeyPatch | None = None,
    ) -> None:
        self.repo = repo
        self.mode = mode
        self.patch = patch
        self.calls = 0
        self.prompts: list[str] = []

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
        self.prompts.append(prompt)
        events: list[Any] = ["pre", "post", "stop"]
        if self.mode == "missing-stop":
            events = ["pre", "post"]
        elif self.mode == "hook-error":
            events = [{"hook_event_name": "unknown"}, "stop"]
        emit_hook_events(self.repo, events)
        if self.mode == "error":
            raise AgentError(code=AGENT_EXECUTION_FAILED, message="fake agent failed")
        if self.mode == "nothing":
            pass
        elif self.mode == "out-of-scope":
            (self.repo / "outside.py").write_text("outside\n")
        elif self.mode == "commit":
            (self.repo / "src" / "one.py").write_text("one\n")
            await asyncio.to_thread(
                subprocess.run,
                ["git", "-C", str(self.repo), "add", "-A"],
                check=True,
            )
            await asyncio.to_thread(
                subprocess.run,
                [
                    "git",
                    "-C",
                    str(self.repo),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "agent",
                ],
                check=True,
            )
        elif self.mode == "switch":
            await asyncio.to_thread(
                subprocess.run,
                ["git", "-C", str(self.repo), "switch", "-q", "-c", "wrong"],
                check=True,
            )
        else:
            first = self.calls == 1 or self.mode in {"regression", "repaired"}
            target = "one.py" if first else "two.py"
            (self.repo / "src" / target).write_text(f"{target}\n")
        if self.mode == "regression" or (self.mode == "repaired" and self.calls == 1):
            (self.repo / "src" / "one.py").write_text("one\n")
            if self.patch is not None:
                self.patch.setenv("STUB_EXIT_PYTEST", "1")
        elif self.mode == "repaired" and self.patch is not None:
            self.patch.delenv("STUB_EXIT_PYTEST", raising=False)
        return AgentResult(
            exit_code=0,
            output="",
            events=[],
            files_changed=[],
            usage={},
            agent_id="fake",
        )


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = init_repo(tmp_path / "repo")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "src").mkdir()
    (repo / "src" / "base.py").write_text("base\n")
    (repo / SPEC_PATH).parent.mkdir()
    (repo / SPEC_PATH).write_bytes(spec_bytes())
    base = commit_all(repo, "base")
    return repo, base


def _run(
    repo: Path, base: str, fake: FakeAgent, instruction: str | None = None
) -> dict[str, Any]:
    workflow = WorkflowParser.parse(WORKFLOW_PATH.read_text())
    registry = PrimitiveRegistry()
    register_builtins(registry)
    tools = load_kit(parse_kit_manifest(KIT_ROOT / "kit.yaml"))
    executor = WorkflowExecutor(
        registry,
        deps=DefaultDependencies(
            agent_registry={"kiro-cli": fake}, tool_registry=tools
        ),
    )
    return asyncio.run(
        executor.execute(
            workflow,
            {
                "repo_path": str(repo),
                "story_key": STORY,
                "spec_path": SPEC_PATH,
                "branch": BRANCH,
                "base_ref": base,
                **({"instruction": instruction} if instruction else {}),
            },
        )
    )


def test_workflow_shape_and_safety() -> None:
    document = yaml.safe_load(WORKFLOW_PATH.read_text())
    assert document["id"] == "implement-story"
    assert document["requires_kits"] == ["profile-dev-kit", "agent-kiro-kit"]
    assert document["inputs"] == [
        "repo_path",
        "story_key",
        "spec_path",
        "branch",
        "base_ref",
        "instruction",
    ]
    assert document["allowed_tools"] == [
        "profile_implement_prepare",
        "profile_implement_settle",
        "profile_record_stage_outcome",
        "profile_hook_open",
        "profile_hook_arm",
        "profile_hook_disarm",
        "profile_hook_proof",
        "profile_stage_instruction",
    ]
    assert "Coding agent" in document["description"]
    assert {step["id"] for step in document["steps"]} == {
        "hook_open",
        "prepare",
        "method",
        "arm",
        "implement",
        "implement_method",
        "disarm",
        "settle",
        "repair_arm",
        "repair",
        "repair_disarm",
        "resettle",
        "settle_stop",
        "proof",
        "proof_stop",
        "record",
        "record_stop",
    }
    assert "push" not in document["allowed_tools"]
    assert "verify" not in document["allowed_tools"]
    agent = next(step for step in document["steps"] if step["id"] == "implement")
    assert agent["config"]["adapter"] == "kiro-cli"
    assert agent["config"]["sandbox"] == "workspace-write"
    assert agent["timeout"] <= 600
    workflow = WorkflowParser.parse(WORKFLOW_PATH.read_text())
    steps = {step.id: step for step in workflow.steps}
    assert steps["arm"].if_condition == "$stepResult.prepare.result.implement == true"
    assert steps["implement"].if_condition == "$stepResult.arm.result.native == true"
    assert (
        steps["implement_method"].if_condition
        == "$stepResult.arm.result.method == true"
    )
    assert steps["implement_method"].config["prompt"] == (
        steps["implement"].config["prompt"]
        + " Method instruction: $stepResult.method.result.instruction"
    )
    assert (
        steps["disarm"].if_condition == "$stepResult.prepare.result.implement == true"
    )
    assert (
        steps["settle"].if_condition == "$stepResult.prepare.result.implement == true"
    )
    assert (
        steps["settle_stop"].if_condition
        == "$stepResult.prepare.result.implement != true"
    )
    assert (
        steps["record"].if_condition == "$stepResult.prepare.result.implement == true"
    )
    assert (
        steps["record_stop"].if_condition
        == "$stepResult.prepare.result.implement != true"
    )
    repair = next(step for step in document["steps"] if step["id"] == "repair")
    assert repair["config"] == {**agent["config"], "prompt": repair["config"]["prompt"]}
    assert repair["timeout"] == agent["timeout"]
    prompt = repair["config"]["prompt"]
    assert "$stepResult.settle.result.refs.regressed" in prompt
    assert "$stepResult.prepare.result.unit_paths" in prompt
    assert "spec_path" not in prompt and "instruction" not in prompt
    assert "commit" in prompt and "push" in prompt
    repair_if = "$stepResult.settle.result.repair == true"
    assert steps["repair_arm"].if_condition == repair_if
    assert "method" not in steps["repair_arm"].config["arguments"]
    assert (
        steps["repair"].if_condition == "$stepResult.repair_arm.result.native == true"
    )
    assert steps["repair_disarm"].if_condition == repair_if
    assert (
        steps["resettle"].if_condition == "$stepResult.prepare.result.implement == true"
    )
    assert steps["resettle"].config["arguments"]["prior"] == (
        "$stepResult.settle.result"
    )
    proof = steps["proof"].config["arguments"]
    assert proof["calls"] == ["$stepResult.arm.result", "$stepResult.repair_arm.result"]
    assert proof["timings"] == [
        "$stepResult.disarm.result",
        "$stepResult.repair_disarm.result",
    ]
    assert proof["settled"] == "$stepResult.resettle.result"


def test_two_unit_sequence_records_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    fake = FakeAgent(repo)
    first = _run(repo, base, fake)
    first_result = first["step_results"]["settle"]["result"]
    assert first_result["reason"] == "unit.committed"
    assert first_result["refs"]["base"] == base
    assert first_result["refs"]["commit"] == first_result["refs"]["head"]
    assert (first_result["refs"]["completed"], first_result["refs"]["remaining"]) == (
        1,
        1,
    )
    assert git(repo, "show", "--name-only", "--format=", "HEAD").split() == [
        "src/one.py"
    ]
    assert "Implementation-Unit: u1" in git(repo, "show", "-s", "--format=%B", "HEAD")
    assert fake.calls == 1
    second = _run(repo, base, fake)
    second_result = second["step_results"]["settle"]["result"]
    assert second_result["reason"] == "unit.committed"
    assert fake.calls == 2
    third_head = git(repo, "rev-parse", "HEAD")
    third = _run(repo, base, fake)
    stop = third["step_results"]["settle_stop"]["result"]
    assert stop["reason"] == "units.complete"
    assert stop["outcome"] == "succeeded"
    assert fake.calls == 2
    assert git(repo, "rev-parse", "HEAD") == third_head
    stored = list((tmp_path / "home").rglob("stage-outcomes/*.json"))
    assert len(stored) == 3
    records = [json.loads(path.read_text()) for path in sorted(stored)]
    for record in records[:2]:
        refs = record["refs"]
        assert set(HOOK_KEYS) <= set(refs)
        assert refs["hook_stop"] == 1
        assert refs["hook_errors"] == 0
        assert refs["repair"] is None and refs["resume_blocked"] is None
        assert len(refs) <= 32
        assert (
            refs["hook_policy_sha256"]
            == hashlib.sha256(policy_path("implement").read_bytes()).hexdigest()
        )
    assert all(records[2]["refs"][key] is None for key in HOOK_KEYS)


@pytest.mark.parametrize(
    ("mode", "reason"),
    [
        ("out-of-scope", "scope.exceeded"),
        ("commit", "head.moved"),
        ("nothing", "unit.empty"),
        ("error", "agent.failed"),
        ("switch", "branch.moved"),
        ("regression", "gate.regressed"),
        ("missing-stop", "hooks.missing"),
        ("hook-error", "hooks.errors"),
    ],
)
def test_agent_modes_are_recorded_without_losing_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, reason: str
) -> None:
    repo, base = _repo(tmp_path / mode)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path / mode))
    monkeypatch.setenv("HOME", str(tmp_path / mode / "home"))
    fake = FakeAgent(repo, mode, monkeypatch)
    before = git(repo, "rev-parse", "HEAD")
    result = _run(repo, base, fake)
    settle = result["step_results"].get(
        "resettle", result["step_results"].get("settle_stop")
    )
    assert settle["result"]["reason"] == (
        "unit.committed" if reason.startswith("hooks.") else reason
    )
    assert settle["result"]["outcome"] == (
        "succeeded" if reason.startswith("hooks.") else "failed"
    )
    records = list((tmp_path / mode / "home").rglob("stage-outcomes/*.json"))
    assert len(records) == 1
    stored = json.loads(records[0].read_text())
    assert (stored["outcome"], stored["reason"]) == ("failed", reason)
    assert fake.calls == (2 if mode == "regression" else 1)
    assert stored["refs"]["repair"] == ("04-pytest" if mode == "regression" else None)
    assert git(repo, "rev-parse", "HEAD") == before or reason in {
        "head.moved",
        "hooks.missing",
        "hooks.errors",
    }


def test_bad_repository_fails_at_record_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    bad = tmp_path / "not-a-repository"
    bad.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with pytest.raises(BeddelError) as error:
        _run(bad, base, FakeAgent(bad))
    assert error.value.code == "BEDDEL-EXEC-002"
    with pytest.raises(BeddelError) as record_error:
        profile_record_stage_outcome(
            str(bad), STORY, "implement", "failed", "prepare.failed", {}
        )
    assert record_error.value.code == "PROFILE_REPOSITORY_INVALID"


def test_absorbed_prepare_error_records_prepare_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    def boom(_repo: Path) -> set[str]:
        raise ProfileError("PROFILE_REPOSITORY_INVALID", "fixture")

    monkeypatch.setattr(implement_tools, "changed_paths", boom)
    result = _run(repo, base, FakeAgent(repo))
    stop = result["step_results"]["settle_stop"]["result"]
    assert (stop["outcome"], stop["reason"]) == ("failed", "prepare.failed")
    records = list((tmp_path / "home").rglob("stage-outcomes/*.json"))
    assert len(records) == 1
    stored = json.loads(records[0].read_text())
    assert (stored["outcome"], stored["reason"]) == ("failed", "prepare.failed")


def _records(home: Path) -> list[dict[str, Any]]:
    stored = sorted(home.rglob("stage-outcomes/*.json"))
    return [json.loads(path.read_text()) for path in stored]


def test_repair_round_commits_unit_and_counts_both_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    fake = FakeAgent(repo, "repaired", monkeypatch)
    result = _run(repo, base, fake)
    steps = result["step_results"]
    assert steps["settle"]["result"]["repair"] is True
    assert steps["settle"]["result"]["refs"]["regressed"] == "04-pytest"
    assert steps["resettle"]["result"]["reason"] == "unit.committed"
    assert fake.calls == 2
    repair_prompt = fake.prompts[1]
    assert "04-pytest" in repair_prompt and "src/one.py" in repair_prompt
    assert SPEC_PATH not in repair_prompt
    arm, repair_arm = steps["arm"]["result"], steps["repair_arm"]["result"]
    assert repair_arm["armed"] is True and repair_arm["native"] is True
    # One stage log for both calls, so the policy's max_tool_calls covers both.
    assert repair_arm["log_path"] == arm["log_path"]
    (record,) = _records(tmp_path / "home")
    refs = record["refs"]
    assert (record["outcome"], record["reason"]) == ("succeeded", "unit.committed")
    assert refs["repair"] == "04-pytest" and refs["regressed"] is None
    assert refs["resume_blocked"] is None
    assert (refs["hook_stop"], refs["hook_errors"]) == (2, 0)
    assert len(str(refs["agent_ms"]).split(",")) == 2
    assert refs["agent_timeouts"] == 0
    assert len(refs) <= 32
    assert "Implementation-Unit: u1" in git(repo, "show", "-s", "--format=%B", "HEAD")


def test_failed_repair_records_gate_regressed_and_blocked_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    fake = FakeAgent(repo, "regression", monkeypatch)
    result = _run(repo, base, fake)
    assert result["step_results"]["resettle"]["result"]["repair"] is False
    assert fake.calls == 2
    (record,) = _records(tmp_path / "home")
    refs = record["refs"]
    assert (record["outcome"], record["reason"]) == ("failed", "gate.regressed")
    assert (refs["repair"], refs["regressed"]) == ("04-pytest", "04-pytest")
    assert refs["resume_blocked"] == "worktree.dirty"
    assert (refs["hook_stop"], refs["hook_errors"]) == (2, 0)
    assert git(repo, "rev-parse", "HEAD") == base
    assert "src/one.py" in git(repo, "status", "--porcelain")


def test_repair_call_shares_the_stage_tool_call_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from beddel_profile_dev import hook_proof

    policy = json.loads(policy_path("implement").read_text())
    policy["max_tool_calls"] = 1
    capped = tmp_path / "implement.json"
    capped.write_text(json.dumps(policy))
    monkeypatch.setattr(hook_proof, "policy_path", lambda _stage: capped)
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    result = _run(repo, base, FakeAgent(repo, "repaired", monkeypatch))
    log = Path(result["step_results"]["arm"]["result"]["log_path"])
    pre = [
        json.loads(line)
        for line in log.read_text().splitlines()
        if json.loads(line)["event"] == "pre"
    ]
    assert [(item["decision"], item["rule_id"]) for item in pre] == [
        ("allow", "read.any"),
        ("deny", "cap.max_tool_calls"),
    ]
    (record,) = _records(tmp_path / "home")
    assert (record["refs"]["hook_denied"], record["refs"]["hook_stop"]) == (1, 2)


def test_repair_under_a_method_keeps_the_method_digest_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    instruction = "Use the named method for this unit only."
    fake = FakeAgent(repo, "repaired", monkeypatch)
    _run(repo, base, fake, instruction)
    assert fake.calls == 2
    assert instruction in fake.prompts[0] and instruction not in fake.prompts[1]
    (record,) = _records(tmp_path / "home")
    assert record["reason"] == "unit.committed"
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
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    fake = FakeAgent(repo, "repaired", monkeypatch)
    _run(repo, base, fake)
    assert fake.calls == 1
    (record,) = _records(tmp_path / "home")
    assert (record["outcome"], record["reason"]) == ("failed", "hooks.pointer_exists")
    assert record["refs"]["repair"] == "04-pytest"
    assert record["refs"]["resume_blocked"] == "worktree.dirty"
    assert git(repo, "rev-parse", "HEAD") == base
