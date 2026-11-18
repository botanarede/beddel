from __future__ import annotations

import hashlib
import itertools
from pathlib import Path
from typing import Any

import pytest
import yaml
from beddel.domain.errors import BeddelError
from beddel.domain.models import AgentResult

from ._helpers import commit_all, emit_hook_events
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
from .test_verify_fix_workflow import _install_review

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
