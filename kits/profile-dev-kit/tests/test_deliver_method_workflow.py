from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from beddel.domain.errors import BeddelError
from beddel.domain.models import AgentResult
from beddel_profile_dev._io import records_root
from beddel_profile_dev.tools.method import profile_deliver_derive
from beddel_profile_dev.tools.ratify import profile_ratify_inventory
from beddel_profile_dev.tools.stage_outcome import profile_record_stage_outcome

from ._helpers import commit_all, emit_hook_events, good, init_repo, write_version
from .test_deliver_workflow import (
    _CodingAgent,
    _deliver_records,
    _spec,
    _stage_env,
    _tuples,
    _workflow_run,
)
from .test_integrate_workflow import _Host
from .test_method import _method
from .test_run_cli import _beddel_argv
from .test_verify_fix_workflow import _install_review

KIT_ROOT = Path(__file__).resolve().parents[1]
STORY = "8-3b-deliver-method-fixture"
TO_APPROVAL = [
    ("plan", "succeeded", "spec.created"),
    ("implement", "succeeded", "unit.committed"),
    ("implement", "succeeded", "units.complete"),
    ("verify-and-fix", "succeeded", "verdict.consistent"),
    ("approval", "stopped", "approval.awaiting_owner"),
    ("deliver", "stopped", "stage.stopped"),
]


class _Prompts(_CodingAgent):
    def __init__(self, repo: Path) -> None:
        super().__init__(repo)
        self.prompts: list[str] = []

    async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
        self.prompts.append(prompt)
        return await super().execute(prompt, **kwargs)


class _TimedOut(_CodingAgent):
    async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
        self.calls += 1
        raise TimeoutError("agent timed out")


class _NoStop(_CodingAgent):
    async def execute(self, prompt: str, **kwargs: Any) -> AgentResult:
        self.calls += 1
        emit_hook_events(self.repo, ["pre", "post"])
        return AgentResult(0, "", [], [], {}, "fake")


def _go(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    agent_class: type[_CodingAgent],
    *,
    spec: bool = False,
    **kwargs: Any,
) -> tuple[Any, list[dict[str, Any]]]:
    env, sub = _stage_env(tmp_path, monkeypatch)
    (sub / ".beddel-profile").mkdir(exist_ok=True)
    (sub / ".beddel-profile" / "method.yaml").write_text(yaml.safe_dump(_method()))
    if spec:
        (sub / "specs" / "story.md").write_bytes(_spec())
    env["tip"] = commit_all(sub, "method file")
    _install_review(monkeypatch)
    agent = agent_class(sub)
    report = {"revision": env["tip"], "verdict": "consistent"}
    _workflow_run(
        env,
        agent,
        _Host(env),
        monkeypatch,
        None,
        report,
        lambda **_: {"ok": True},
        method=method,
        **kwargs,
    )
    return agent, _deliver_records(tmp_path / "home")


def test_native_method_runs_todays_prompts_to_the_approval_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    native_root = tmp_path / "native"
    empty_root = tmp_path / "empty"
    native_root.mkdir()
    empty_root.mkdir()
    agent, records = _go(native_root, monkeypatch, "native", _Prompts)
    native_prompts = list(agent.prompts)
    empty_agent, empty_records = _go(empty_root, monkeypatch, "", _Prompts)
    assert _tuples(records) == TO_APPROVAL
    assert _tuples(empty_records) == TO_APPROVAL
    assert native_prompts == empty_agent.prompts
    assert not any("Method instruction" in text for text in native_prompts)
    assert records[0]["refs"]["instruction_sha256"] is None


def test_named_method_appends_instructions_and_stops_at_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    native_root = tmp_path / "native"
    alpha_root = tmp_path / "alpha"
    native_root.mkdir()
    alpha_root.mkdir()
    native_agent, _ = _go(native_root, monkeypatch, "", _Prompts)
    agent, records = _go(alpha_root, monkeypatch, "alpha", _Prompts)
    assert _tuples(records) == TO_APPROVAL
    instructions = ["Plan this story.", "Implement this unit."]
    assert agent.prompts == [
        prompt + " Method instruction: " + instruction
        for prompt, instruction in zip(native_agent.prompts, instructions)
    ]
    refs = records[0]["refs"]
    assert refs["instruction_sha256"] == hashlib.sha256(b"Plan this story.").hexdigest()
    assert (refs["hook_stop"], refs["hook_errors"], refs["agent_timeouts"]) == (1, 0, 0)
    assert str(refs["agent_ms"]).isdigit()

    pending = {
        "verdict": "has pendency",
        "items": {
            "divergences": {"status": "present", "value": [{"finding_index": 0}]},
            "pendencies": {
                "status": "present",
                "value": [{"finding_index": 0, "reason": "finding_blocking"}],
            },
        },
    }
    native_fix_root = tmp_path / "native-fix"
    alpha_fix_root = tmp_path / "alpha-fix"
    native_fix_root.mkdir()
    alpha_fix_root.mkdir()
    native_fix, _ = _go(native_fix_root, monkeypatch, "", _Prompts, fix_report=pending)
    alpha_fix, _ = _go(
        alpha_fix_root, monkeypatch, "alpha", _Prompts, fix_report=pending
    )
    assert len(native_fix.prompts) == len(alpha_fix.prompts)
    fix_instructions = ["Plan this story.", "Implement this unit."] + [
        "Fix these findings."
    ] * max(0, len(native_fix.prompts) - 2)
    assert alpha_fix.prompts == [
        prompt + " Method instruction: " + instruction
        for prompt, instruction in zip(native_fix.prompts, fix_instructions)
    ]
    assert any("verification fix round" in prompt for prompt in alpha_fix.prompts)


def test_reused_spec_makes_no_plan_agent_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent, records = _go(
        tmp_path, monkeypatch, "alpha", _Prompts, spec=True, stage="plan"
    )
    assert _tuples(records)[0] == ("plan", "succeeded", "spec.reused")
    assert agent.calls == 0
    assert records[0]["refs"]["hook_stop"] is None
    assert records[0]["refs"]["agent_ms"] is None


def test_agent_timeout_fails_the_stage_with_its_duration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import beddel_profile_dev.tools.hook as hook_tools

    ticks = itertools.count(0, 601 * 10**9)
    monkeypatch.setattr(hook_tools, "_clock", lambda: next(ticks))
    _, records = _go(tmp_path, monkeypatch, "alpha", _TimedOut, stage="plan")
    assert _tuples(records)[0] == ("plan", "failed", "agent.timeout")
    assert records[0]["refs"]["agent_ms"] == "601000"
    assert records[0]["refs"]["agent_timeouts"] == 1


def test_missing_stop_fails_a_method_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, records = _go(tmp_path, monkeypatch, "alpha", _NoStop, stage="plan")
    assert _tuples(records)[0] == ("plan", "failed", "hooks.missing")


def test_invalid_method_file_fails_before_any_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env, sub = _stage_env(tmp_path, monkeypatch)
    method_path = sub / ".beddel-profile" / "method.yaml"
    method_path.parent.mkdir(exist_ok=True)
    method_path.write_text("schema: invalid\n")
    commit_all(sub, "invalid method file")
    _install_review(monkeypatch)
    agent = _Prompts(sub)
    report = {"revision": env["tip"], "verdict": "consistent"}
    with pytest.raises(BeddelError) as error:
        _workflow_run(
            env,
            agent,
            _Host(env),
            monkeypatch,
            None,
            report,
            lambda **_: {"ok": True},
            method="alpha",
        )
    assert error.value.code == "BEDDEL-EXEC-002"
    assert agent.calls == 0
    assert not list((tmp_path / "home").rglob("stage-outcomes/*.json"))


@pytest.mark.parametrize(
    ("story_key", "method", "reason"),
    [
        (STORY, "alpha", "method.absent"),
        ("../x", "native", "story_key.invalid"),
    ],
)
def test_beddel_run_three_inputs_refuses_without_a_method_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    story_key: str,
    method: str,
    reason: str,
) -> None:
    home = tmp_path / "home"
    repo = init_repo(tmp_path / "repo")
    commit_all(repo)
    (home / ".config" / "beddel").mkdir(parents=True)
    (home / ".config" / "beddel" / "config.json").write_text(
        json.dumps({"kits_paths": [str(KIT_ROOT.parent)]})
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("GIT_", "BEDDEL_", "PYTHON"))
    }
    env.update({"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")})
    command = [
        *_beddel_argv(),
        "run",
        "--json-output",
        "-i",
        f"repo_path={repo}",
        "-i",
        f"story_key={story_key}",
        "-i",
        f"method={method}",
        str(KIT_ROOT / "workflows" / "deliver.yaml"),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    stored = [
        json.loads(path.read_text()) for path in home.rglob("stage-outcomes/*.json")
    ]
    assert [(r["stage"], r["outcome"], r["reason"]) for r in stored] == [
        ("deliver", "refused", reason)
    ]


def test_three_input_workflow_shape() -> None:
    document = yaml.safe_load((KIT_ROOT / "workflows" / "deliver.yaml").read_text())
    assert document["id"] == "deliver"
    assert document["inputs"] == ["repo_path", "story_key", "method"]
    assert document["allowed_tools"] == [
        "profile_deliver_derive",
        "profile_record_stage_outcome",
    ]
    assert [step["id"] for step in document["steps"]] == ["derive", "deliver", "record"]
    assert document["steps"][1]["config"]["workflow"] == "deliver-story.yaml"
    deliver_inputs = document["steps"][1]["config"]["inputs"]
    base_inputs = yaml.safe_load(
        (KIT_ROOT / "workflows" / "deliver-story.yaml").read_text()
    )["inputs"]
    assert set(deliver_inputs) == set(base_inputs) | {"method"}
    assert {
        name: ref == f"$stepResult.derive.result.inputs.{name}"
        for name, ref in deliver_inputs.items()
    } == dict.fromkeys(deliver_inputs, True)


def test_derive_refusal_records_a_refused_deliver_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_repo(tmp_path / "repo")
    commit_all(repo)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    derived = profile_deliver_derive(str(repo), STORY, "native")
    assert derived == {
        "ok": False,
        "story_key": STORY,
        "reason": "method.absent",
        "refs": {
            "request": "all",
            "resume": None,
            "stage": "start",
            "stage_record": None,
            "stage_outcome": None,
            "stage_reason": "method.absent",
            "first_record": None,
            "invoked": None,
        },
    }
    stored = profile_record_stage_outcome(
        str(repo),
        derived["story_key"],
        "deliver",
        "refused",
        derived["reason"],
        derived["refs"],
    )
    assert stored["outcome"] == "refused"
    path = records_root(repo, "records/profile-dev") / "stage-outcomes/1.json"
    assert path.exists()


def _entry_method() -> dict[str, object]:
    return {
        "schema": "profile-dev/method/1",
        "inputs": {
            "story_path": "story.md",
            "guide_path": "guide.md",
            "spec_path": "specs/story.md",
            "status_path": "status.yaml",
            "branch": "feat/work",
            "remote": "origin",
            "base_branch": "main",
        },
        "methods": {
            "alpha": {
                "plan": "Plan this story.",
                "implement": "Implement this unit.",
                "fix": "Fix these findings.",
            }
        },
    }


def _prepare_entry_fixture(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], Path]:
    root.mkdir(parents=True, exist_ok=True)
    env, sub = _stage_env(root, monkeypatch)
    profile = sub / ".beddel-profile"
    profile.mkdir(exist_ok=True)
    (profile / "method.yaml").write_text(
        yaml.safe_dump(_entry_method(), sort_keys=False)
    )
    write_version(sub, "v1", good())
    commit_all(sub, "method and inventory")
    profile_ratify_inventory(str(sub), "v1", "Fixture")
    env["tip"] = commit_all(sub, "inventory ratification")
    return env, sub


def test_three_input_entry_runs_native_and_named_method_to_the_approval_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    native_env, native_sub = _prepare_entry_fixture(tmp_path / "native", monkeypatch)
    _install_review(monkeypatch)
    native_agent = _Prompts(native_sub)
    native_report = {"revision": native_env["tip"], "verdict": "consistent"}
    _workflow_run(
        native_env,
        native_agent,
        _Host(native_env),
        monkeypatch,
        None,
        native_report,
        lambda **_: {"ok": True},
        method="native",
        entry=True,
    )
    native_records = _deliver_records(tmp_path / "native" / "home")
    assert _tuples(native_records) == TO_APPROVAL
    assert not any("Method instruction" in prompt for prompt in native_agent.prompts)
    native_derived = profile_deliver_derive(
        str(native_sub),
        "7-7-deliver-story-workflow-chains-stages-and-resumes",
        "native",
    )
    assert native_derived["inputs"]["base_ref"] == native_env["base"]
    assert Path(native_derived["inputs"]["parent_path"]) == native_env["parent"]
    assert native_derived["inputs"]["parent_branch"] == "main"

    alpha_env, alpha_sub = _prepare_entry_fixture(tmp_path / "alpha", monkeypatch)
    _install_review(monkeypatch)
    alpha_agent = _Prompts(alpha_sub)
    alpha_report = {"revision": alpha_env["tip"], "verdict": "consistent"}
    _workflow_run(
        alpha_env,
        alpha_agent,
        _Host(alpha_env),
        monkeypatch,
        None,
        alpha_report,
        lambda **_: {"ok": True},
        method="alpha",
        entry=True,
    )
    alpha_records = _deliver_records(tmp_path / "alpha" / "home")
    assert _tuples(alpha_records) == TO_APPROVAL
    assert alpha_agent.prompts[0].endswith("Method instruction: Plan this story.")
    assert alpha_agent.prompts[1].endswith("Method instruction: Implement this unit.")
    alpha_derived = profile_deliver_derive(
        str(alpha_sub), "7-7-deliver-story-workflow-chains-stages-and-resumes", "alpha"
    )
    assert alpha_derived["inputs"]["base_ref"] == alpha_env["base"]
