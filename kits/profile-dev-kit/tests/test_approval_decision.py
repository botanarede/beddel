"""Story 5.2: Approval decisions are transport-only and create-only."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml
from beddel_profile_dev._errors import PROFILE_APPROVAL_REFUSED, ProfileError
from beddel_profile_dev._io import records_root
from beddel_profile_dev.tools.approval_decision import (
    APPROVAL_DECISION_SCHEMA,
    profile_record_approval_decision,
)
from beddel_profile_dev.tools.report import profile_record_report

from ._helpers import commit_all, git
from .test_approval import _prepare, _repo_snapshot, _snapshot
from .test_report import _run_results


def _refused(
    repo: Path,
    revision: str,
    reason: str,
    *,
    change_id: str = "c1",
    actor: str = "tester",
) -> None:
    records = records_root(repo, "records/profile-dev")
    before_records = _snapshot(records)
    before_repo = _repo_snapshot(repo)
    with pytest.raises(ProfileError) as info:
        profile_record_approval_decision(str(repo), change_id, revision, actor)
    error = info.value
    assert error.code == PROFILE_APPROVAL_REFUSED
    assert error.details == {"reason": reason}
    assert error.message == f"approval decision refused: {reason}"
    assert _snapshot(records) == before_records
    assert _repo_snapshot(repo) == before_repo


def test_records_exact_yaml_and_never_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    result = profile_record_report(str(repo), "c1", revision)
    before_head = commit_all(repo, "before decision")
    monkeypatch.setenv("USER", "ambient-user")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "ambient-author")
    git(repo, "config", "user.name", "repo-user")

    decision = profile_record_approval_decision(str(repo), "c1", revision, "tester")

    assert git(repo, "rev-parse", "HEAD") == before_head
    assert "?? .beddel-profile/approvals/" in git(repo, "status", "--short")
    assert commit_all(repo, "commit decision") != before_head
    path = repo / decision["record"]
    raw = path.read_bytes()
    assert b"ambient-user" not in raw
    assert b"ambient-author" not in raw
    assert b"repo-user" not in raw
    record = yaml.safe_load(raw)
    assert set(record) == {
        "schema",
        "change_id",
        "revision",
        "report",
        "report_sha256",
        "approved_by",
        "approved_at",
    }
    assert record["schema"] == APPROVAL_DECISION_SCHEMA
    assert record["approved_by"] == "tester"
    report_path = records_root(repo, "records/profile-dev") / result["report"]
    assert (
        record["report_sha256"] == hashlib.sha256(report_path.read_bytes()).hexdigest()
    )
    assert path.exists()


def test_decision_path_in_head_history_is_duplicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    decision = profile_record_approval_decision(str(repo), "c1", revision, "tester")
    path = repo / decision["record"]
    commit_all(repo, "commit decision")
    path.unlink()
    _refused(repo, revision, "decision.exists")


def test_decision_is_create_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    decision = profile_record_approval_decision(str(repo), "c1", revision, "tester")
    before = _snapshot(records_root(repo, "records/profile-dev"))
    decision_tree = repo / ".beddel-profile" / "approvals"
    before_tree = _snapshot(decision_tree)
    decision_bytes = Path(repo / decision["record"]).read_bytes()
    _refused(repo, revision, "decision.exists")
    assert _snapshot(records_root(repo, "records/profile-dev")) == before
    assert _snapshot(decision_tree) == before_tree
    assert Path(repo / decision["record"]).read_bytes() == decision_bytes


def test_decision_reason_precedence(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    _refused(repo, revision, "report.absent")
    _refused(repo, revision, "id.invalid", change_id="bad/id")
    _refused(repo, "missing", "revision.invalid")


def test_history_error_is_refused_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    from beddel_profile_dev.tools import approval_decision

    monkeypatch.setattr(
        approval_decision,
        "in_index",
        lambda *args: (_ for _ in ()).throw(
            ProfileError("TEST", "history unavailable")
        ),
    )
    _refused(repo, revision, "history.unreadable")


def test_malformed_report_refuses_without_changing_report_records(
    tmp_path: Path,
) -> None:
    repo, _, revision = _prepare(tmp_path)
    report_dir = records_root(repo, "records/profile-dev") / "changes" / "c1" / "report"
    report_dir.mkdir()
    (report_dir / "1.json").write_text("not json")
    before = _snapshot(records_root(repo, "records/profile-dev"))
    _refused(repo, revision, "report.malformed")
    assert _snapshot(records_root(repo, "records/profile-dev")) == before


def test_decision_transport_reason_precedence_and_invalid_actor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _refused(repo, revision, "actor.invalid", actor="\x00")
    _refused(repo, revision, "change.unrecorded", change_id="other")
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    _refused(repo, "missing", "revision.invalid")


def test_decision_transport_rejects_report_for_another_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    (repo / "src" / "api.py").write_text("x = 3\n")
    other_revision = commit_all(repo, "other revision")
    _refused(repo, other_revision, "revision.not_reported")


def test_decision_transport_staged_only_is_duplicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    from beddel_profile_dev.tools.approval_decision import (
        profile_record_approval_decision,
    )

    decision = profile_record_approval_decision(str(repo), "c1", revision, "tester")
    path = repo / decision["record"]
    git(repo, "add", str(path.relative_to(repo)))
    path.unlink()
    _refused(repo, revision, "decision.exists")
