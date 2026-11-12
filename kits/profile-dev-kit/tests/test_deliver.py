"""Unit coverage for chained Delivery gates and Approval reconciliation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from beddel_profile_dev._errors import PROFILE_IMPACT_UNBOUND, ProfileError
from beddel_profile_dev._io import records_root
from beddel_profile_dev.config import load_config
from beddel_profile_dev.deliver import resume
from beddel_profile_dev.tools.deliver import (
    profile_deliver_approval,
    profile_deliver_gate,
)
from beddel_profile_dev.tools.stage_outcome import profile_record_stage_outcome

from ._helpers import commit_all, git, init_repo

# fmt: off
STORY = "7-7-deliver-story-workflow-chains-stages-and-resumes"


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = init_repo(tmp_path / "repo")
    (repo / "README.md").write_text("fixture\n")
    commit_all(repo)
    git(repo, "switch", "-q", "-c", "feature/test")
    return repo


def _record(repo: Path, stage: str, outcome: str, reason: str) -> None:
    profile_record_stage_outcome(
        str(repo), STORY, stage, outcome, reason, {"stage": stage}
    )


def test_approval_check_stops_without_committed_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, monkeypatch)
    gate = profile_deliver_gate(str(repo), STORY, "all", "start", {})
    gate.update(go="approval")
    monkeypatch.setattr(
        "beddel_profile_dev.tools.deliver.profile_read_approval",
        lambda *args: {"approval": None},
    )
    monkeypatch.setattr(
        "beddel_profile_dev.tools.deliver.profile_read_report",
        lambda *args: {
            "report": {"revision": "a" * 40},
            "history": [{"ref": "changes/c1/report/3.json"}],
        },
    )
    result = profile_deliver_approval(
        str(repo), STORY, "c1", git(repo, "branch", "--show-current"), "tester", "check", gate
    )
    assert result["outcome"] == "stopped"
    assert result["reason"] == "approval.awaiting_owner"
    from beddel_profile_dev.tools.approval_decision import approval_path

    path = repo / approval_path("c1", 3)
    path.parent.mkdir(parents=True)
    path.write_text("decision: approved\n")
    git(repo, "add", "--", approval_path("c1", 3))
    staged = profile_deliver_approval(
        str(repo), STORY, "c1", git(repo, "branch", "--show-current"), "tester", "check", gate
    )
    assert staged["reason"] == "approval.awaiting_owner"


def test_approval_settle_reuses_recorded_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, monkeypatch)
    prior: dict[str, Any] = {
        "stage": "approval",
        "phase": "check",
        "story_key": STORY,
        "repo": str(repo.resolve()),
        "change_id": "c1",
        "branch": "main",
        "revision": "a" * 40,
        "outcome": None,
        "refs": {},
    }
    monkeypatch.setattr(
        "beddel_profile_dev.tools.deliver.profile_read_approval",
        lambda *args: {"approval": {"revision": "a" * 40}},
    )
    result = profile_deliver_approval(
        str(repo), STORY, "c1", "main", "tester", "settle", prior
    )
    assert result["outcome"] == "succeeded"
    assert result["reason"] == "approval.recorded"


def _gate_for_approval(repo: Path) -> dict[str, Any]:
    state = profile_deliver_gate(str(repo), STORY, "all", "start", {})
    state["go"] = "approval"
    return state


def test_gate_uses_configured_records_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    from beddel_profile_dev.tools import deliver as deliver_tools
    from beddel_profile_dev.tools import stage_outcome

    config = replace(load_config(), records_dir="records/custom")
    monkeypatch.setattr(deliver_tools, "load_config", lambda: config)
    monkeypatch.setattr(stage_outcome, "load_config", lambda: config)
    _record(repo, "plan", "succeeded", "spec.created")
    result = profile_deliver_gate(str(repo), STORY, "all", "start", {})
    assert result["go"] == "implement"


def test_start_reports_complete_delivery_without_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    for stage, reason in (("plan", "spec.created"), ("implement", "units.complete"), ("verify-and-fix", "verdict.consistent"), ("approval", "approval.recorded"), ("integrate", "integrate.complete")):
        _record(repo, stage, "succeeded", reason)
    result = profile_deliver_gate(str(repo), STORY, "all", "start", {})
    assert (result["outcome"], result["reason"], result["go"], result["invoked"]) == ("succeeded", "deliver.complete", None, "")


def test_approval_check_reuses_recorded_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    monkeypatch.setattr("beddel_profile_dev.tools.deliver.profile_read_approval", lambda *args: {"approval": {"revision": "a" * 40}})
    result = profile_deliver_approval(str(repo), STORY, "c1", "feature/test", "tester", "check", _gate_for_approval(repo))
    assert (result["outcome"], result["reason"], result["refs"]["invoked"]) == ("succeeded", "approval.reused", False)


def test_approval_check_finds_committed_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from beddel_profile_dev.tools.approval_decision import approval_path

    repo = _repo(tmp_path, monkeypatch)
    monkeypatch.setattr("beddel_profile_dev.tools.deliver.profile_read_approval", lambda *args: {"approval": None})
    monkeypatch.setattr("beddel_profile_dev.tools.deliver.profile_read_report", lambda *args: {"report": {"revision": "a" * 40}, "history": [{"ref": "changes/c1/report/1.json"}]})
    path = repo / approval_path("c1", 1)
    path.parent.mkdir(parents=True)
    path.write_text("decision: approved\n")
    git(repo, "add", "--", approval_path("c1", 1))
    git(repo, "commit", "-q", "-m", "decision")
    result = profile_deliver_approval(str(repo), STORY, "c1", "feature/test", "tester", "check", _gate_for_approval(repo))
    assert result["approve"] is True
    assert result["revision"] == "a" * 40
    assert result["refs"]["decision_path"] == approval_path("c1", 1)
    assert len(result["decision_commit"]) == 40


def test_approval_check_refusals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    gate = _gate_for_approval(repo)
    assert profile_deliver_approval(str(repo), STORY, "bad/id", "feature/test", "tester", "check", gate)["reason"] == "change_id.invalid"
    assert profile_deliver_approval(str(repo), STORY, "c1", "bad branch", "tester", "check", gate)["reason"] == "branch.invalid"
    assert profile_deliver_approval(str(repo), STORY, "c1", "feature/test", "\x00", "check", gate)["reason"] == "actor.invalid"
    assert profile_deliver_approval(str(repo), STORY, "c1", "other", "tester", "check", gate)["reason"] == "branch.not_current"
    monkeypatch.setattr("beddel_profile_dev.tools.deliver.profile_read_approval", lambda *args: (_ for _ in ()).throw(ProfileError(PROFILE_IMPACT_UNBOUND, "absent")))
    assert profile_deliver_approval(str(repo), STORY, "c1", "feature/test", "tester", "check", gate)["reason"] == "report.absent"
    monkeypatch.setattr("beddel_profile_dev.tools.deliver.profile_read_approval", lambda *args: (_ for _ in ()).throw(ProfileError("X", "invalid")))
    assert profile_deliver_approval(str(repo), STORY, "c1", "feature/test", "tester", "check", gate)["reason"] == "approval.invalid"
    monkeypatch.setattr("beddel_profile_dev.tools.deliver.profile_read_approval", lambda *args: {"approval": None})
    monkeypatch.setattr("beddel_profile_dev.tools.deliver.profile_read_report", lambda *args: (_ for _ in ()).throw(ProfileError("X", "unreadable")))
    monkeypatch.setattr("beddel_profile_dev.tools.deliver.profile_read_report", lambda *args: {"report": {"revision": "a" * 40}, "history": [{"ref": "changes/c1/report/3.json"}]})
    monkeypatch.setattr("beddel_profile_dev.tools.deliver.path_present", lambda *args: (_ for _ in ()).throw(ProfileError("X", "git")))
    assert profile_deliver_approval(str(repo), STORY, "c1", "feature/test", "tester", "check", gate)["reason"] == "decision.unreadable"


def test_start_refuses_invalid_request_and_story_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    invalid_request = profile_deliver_gate(str(repo), STORY, "bad", "start", {})
    invalid_story = profile_deliver_gate(str(repo), "BAD KEY", "all", "start", {})
    assert (invalid_request["outcome"], invalid_request["reason"]) == ("refused", "request.invalid")
    assert (invalid_story["story_key"], invalid_story["reason"]) == (None, "story_key.invalid")


def test_gate_maps_unrecorded_incomplete_and_failed_stages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    start = profile_deliver_gate(str(repo), STORY, "all", "start", {})
    assert profile_deliver_gate(str(repo), STORY, "all", "plan", start)["reason"] == "stage.unrecorded"
    _record(repo, "plan", "succeeded", "spec.created")
    after_plan = profile_deliver_gate(str(repo), STORY, "all", "plan", start)
    _record(repo, "implement", "succeeded", "unit.committed")
    assert profile_deliver_gate(str(repo), STORY, "all", "implement", after_plan)["reason"] == "stage.incomplete"
    repo2 = _repo(tmp_path / "failed", monkeypatch)
    start2 = profile_deliver_gate(str(repo2), STORY, "all", "start", {})
    _record(repo2, "plan", "failed", "agent.failed")
    failed = profile_deliver_gate(str(repo2), STORY, "all", "plan", start2)
    assert (failed["outcome"], failed["reason"]) == ("failed", "stage.failed")


def test_gate_rejects_forged_prior_and_unreadable_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    start = profile_deliver_gate(str(repo), STORY, "all", "start", {})
    assert profile_deliver_gate(str(repo), STORY, "all", "plan", None)["reason"] == "gate.failed"
    assert profile_deliver_gate(str(repo), STORY, "all", "plan", {**start, "repo": "other"})["reason"] == "state.mismatch"
    root = records_root(repo, "records/profile-dev") / "stage-outcomes"
    root.mkdir(parents=True)
    (root / "1.json").write_text("[]")
    assert profile_deliver_gate(str(repo), STORY, "all", "start", {})["reason"] == "records.unreadable"


def test_resume_point_from_latest_story_record() -> None:
    assert resume([]) == ("plan", False)
    assert resume([{"stage": "implement", "outcome": "failed", "reason": "agent.failed"}]) == ("implement", False)
    assert resume([{"stage": "implement", "outcome": "succeeded", "reason": "unit.committed"}]) == ("implement", False)
    assert resume([{"stage": "verify-and-fix", "outcome": "succeeded", "reason": "verdict.consistent"}]) == ("approval", False)
    assert resume([{"stage": "integrate", "outcome": "succeeded", "reason": "integrate.complete"}]) == (None, True)


def test_start_resumes_after_latest_complete_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    _record(repo, "plan", "succeeded", "spec.reused")
    first = profile_deliver_gate(str(repo), STORY, "all", "start", {})
    assert first["go"] == "implement"
    _record(repo, "implement", "succeeded", "units.complete")
    second = profile_deliver_gate(str(repo), STORY, "all", "start", {})
    assert second["go"] == "verify-and-fix"
