"""Story 5.1: Approval revalidation is fail-closed and write-free."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest
import yaml
from beddel_profile_dev._errors import (
    PROFILE_APPROVAL_REFUSED,
    PROFILE_CHANGE_INVALID,
    PROFILE_REPOSITORY_INVALID,
    ProfileError,
)
from beddel_profile_dev._io import records_root
from beddel_profile_dev.tools.approval import (
    profile_approve_change,
    profile_read_approval,
)
from beddel_profile_dev.tools.bind import profile_bind_inventory
from beddel_profile_dev.tools.change import profile_record_change
from beddel_profile_dev.tools.determine import NON_APPLICABILITY_SCHEMA
from beddel_profile_dev.tools.impact import profile_derive_impact
from beddel_profile_dev.tools.report import profile_record_report

from ._helpers import change_fixture, commit_all, git
from .test_report import _run_results

KIT_ROOT = Path(__file__).resolve().parent.parent
PYTHON_ROOT = KIT_ROOT / "python"
WORKFLOWS_ROOT = KIT_ROOT / "workflows"


def _prepare(tmp_path: Path) -> tuple[Path, str, str]:
    repo, base, revision = change_fixture(
        tmp_path, lambda path: (path / "src" / "api.py").write_text("x = 2\n")
    )
    profile_record_change(str(repo), "c1", base, revision)
    profile_bind_inventory(str(repo), revision, "v1")
    profile_derive_impact(str(repo), "c1", revision)
    return repo, base, revision


def _snapshot(root: Path) -> dict[str, bytes | None]:
    result: dict[str, bytes | None] = {"": None}
    if not root.exists():
        return result
    for path in root.rglob("*"):
        relative = str(path.relative_to(root))
        result[relative] = path.read_bytes() if path.is_file() else None
    return result


def _refused(
    repo: Path,
    revision: str,
    reason: str,
    *,
    change_id: str = "c1",
    actor: str = "tester",
    decision_commit: str = "HEAD",
) -> ProfileError:
    with pytest.raises(ProfileError) as info:
        profile_approve_change(str(repo), change_id, revision, actor, decision_commit)
    error = info.value
    assert error.code == PROFILE_APPROVAL_REFUSED
    assert error.details == {"reason": reason}
    assert error.message == f"approval refused: {reason}"
    return error


def test_has_pendency_refuses_without_writing(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, revision, "verdict.has_pendency")
    assert _snapshot(records) == before


def test_consistent_without_decision_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, revision, "decision.absent")
    assert _snapshot(records) == before


def test_later_revision_attempt_does_not_supersede_earlier_revision_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base, first_revision = _prepare(tmp_path)
    _run_results(repo, first_revision, monkeypatch)
    profile_record_report(str(repo), "c1", first_revision)

    (repo / "src" / "api.py").write_text("x = 3\n")
    later_revision = commit_all(repo, "later revision")
    profile_record_change(str(repo), "c1", base, later_revision)
    profile_bind_inventory(str(repo), later_revision, "v1")
    profile_derive_impact(str(repo), "c1", later_revision)
    from beddel_profile_dev.tools.attempt import profile_open_attempt

    profile_open_attempt(str(repo), "c1", later_revision)
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, first_revision, "decision.absent")
    assert _snapshot(records) == before


def test_load_change_oserror_is_revision_unlinked_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    from beddel_profile_dev.tools import approval

    monkeypatch.setattr(
        approval,
        "_load_change",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("read failed")),
    )
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, revision, "revision.unlinked")
    assert _snapshot(records) == before


def test_report_history_oserror_is_malformed_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    from beddel_profile_dev.tools import approval

    monkeypatch.setattr(
        approval,
        "_report_history",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("read failed")),
    )
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, revision, "report.malformed")
    assert _snapshot(records) == before


def test_basic_reason_precedence_and_no_writes(tmp_path: Path) -> None:
    repo, base, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, revision, "id.invalid", change_id="bad/id")
    _refused(repo, revision, "actor.invalid", actor="\x00")
    _refused(repo, "unknown-revision", "revision.invalid")
    _refused(repo, revision, "change.unrecorded", change_id="c2")
    _refused(repo, base, "revision.unlinked")
    assert _snapshot(records) == before


def test_no_report_refuses(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, revision, "report.absent")
    assert _snapshot(records) == before


@pytest.mark.parametrize("tamper", ["edited", "deleted"])
def test_report_digest_tampering_refuses_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tamper: str
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    result = profile_record_report(str(repo), "c1", revision)
    report = records_root(repo, "records/profile-dev")
    report_file = report / result["report"]
    data = json.loads(report_file.read_text())
    read_ref = next(
        item["ref"] for item in data["reads"] if "/attempts/" in item["ref"]
    )
    read_path = report / read_ref
    if tamper == "edited":
        read_path.write_bytes(read_path.read_bytes() + b"tampered")
    else:
        read_path.unlink()
    before = _snapshot(report)
    _refused(repo, revision, "digest.mismatch")
    assert _snapshot(report) == before


def test_underivable_is_a_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    from beddel_profile_dev.tools import approval

    monkeypatch.setattr(
        approval,
        "_derive_report",
        lambda *args: (_ for _ in ()).throw(ProfileError("TEST", "derivation failed")),
    )
    _refused(repo, revision, "verdict.underivable")
    assert _snapshot(records) == before


def test_structural_approval_boundaries() -> None:
    for path in PYTHON_ROOT.rglob("*.py"):
        if path.name not in {"approval.py", "approval_decision.py", "_errors.py"}:
            assert "approv" not in path.read_text().lower()
    source = (PYTHON_ROOT / "beddel_profile_dev" / "tools" / "approval.py").read_text()
    assert source.count("write_create_only(") == 1
    for forbidden in ("open(", "mkdir", "write_bytes", "write_text"):
        assert forbidden not in source
    for module_path in (
        PYTHON_ROOT / "beddel_profile_dev" / "tools" / "approval.py",
        PYTHON_ROOT / "beddel_profile_dev" / "tools" / "approval_decision.py",
    ):
        module_source = module_path.read_text()
        tree = ast.parse(module_source)
        imported_modules = (
            [
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            ]
            + [
                node.module or ""
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            ]
            + [
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                for alias in node.names
            ]
        )
        forbidden_modules = {
            "time",
            "subprocess",
            "_adapters",
            "socket",
            "urllib",
            "http",
        }
        if module_path.name == "approval.py":
            forbidden_modules.add("datetime")
        assert all(
            not forbidden_modules.intersection(module.split("."))
            for module in imported_modules
        )
        assert all(
            forbidden not in module_source
            for forbidden in ("environ", "getenv", "getpass", "user.name", "user.email")
        )
    assert "profile-dev/approval/1" in source
    assert "approval.json" in source
    decision_source = (
        PYTHON_ROOT / "beddel_profile_dev" / "tools" / "approval_decision.py"
    ).read_text()
    assert "profile-dev/approval/1" not in decision_source
    assert "approval.json" not in decision_source
    assert (
        "profile_approve_change"
        not in (WORKFLOWS_ROOT / "verify-change.yaml").read_text()
    )
    assert (
        sum(
            "profile_approve_change" in path.read_text()
            for path in WORKFLOWS_ROOT.glob("*.yaml")
        )
        == 1
    )
    assert (
        sum(
            "profile_record_approval_decision" in path.read_text()
            for path in WORKFLOWS_ROOT.glob("*.yaml")
        )
        == 1
    )
    assert (
        sum(
            "profile_read_approval" in path.read_text()
            for path in WORKFLOWS_ROOT.glob("*.yaml")
        )
        == 1
    )


def test_malformed_report_refuses(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    report_dir = records_root(repo, "records/profile-dev") / "changes" / "c1" / "report"
    report_dir.mkdir()
    (report_dir / "1.json").write_text("not json")
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, revision, "report.malformed")
    assert _snapshot(records) == before


def test_outdated_report_refuses(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    result = profile_record_report(str(repo), "c1", revision)
    report_file = records_root(repo, "records/profile-dev") / result["report"]
    report = json.loads(report_file.read_text())
    report["schema"] = "profile-dev/verification-report/3"
    report_file.write_text(json.dumps(report))
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, revision, "report.outdated")
    assert _snapshot(records) == before


@pytest.mark.parametrize("completed", [False, True])
def test_newer_attempt_at_same_revision_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, completed: bool
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    if completed:
        _run_results(repo, revision, monkeypatch)
    else:
        from beddel_profile_dev.tools.attempt import profile_open_attempt

        profile_open_attempt(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, revision, "attempt.superseded")
    assert _snapshot(records) == before


def test_report_for_another_revision_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    (repo / "src" / "api.py").write_text("x = 3\n")
    from ._helpers import commit_all

    other_revision = commit_all(repo, "second revision")
    profile_record_change(str(repo), "c1", base, other_revision)
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, other_revision, "revision.not_reported")
    assert _snapshot(records) == before


def test_verdict_mismatch_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    from beddel_profile_dev.tools import approval

    monkeypatch.setattr(
        approval,
        "_derive_report",
        lambda *args: {"verdict": "has pendency"},
    )
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, revision, "verdict.mismatch")
    assert _snapshot(records) == before


def test_invalid_repository_keeps_repository_error(tmp_path: Path) -> None:
    with pytest.raises(ProfileError) as info:
        profile_approve_change(
            str(tmp_path / "missing"), "c1", "HEAD", "tester", "HEAD"
        )
    assert info.value.code == "PROFILE_REPOSITORY_INVALID"


@pytest.mark.parametrize(
    "tamper",
    [
        "missing_sha256",
        "missing_attempt",
        "non_int_attempt",
        "missing_verdict",
        "legacy_one",
        "legacy_two",
    ],
)
def test_malformed_latest_report_is_refused_without_writing(
    tmp_path: Path, tamper: str
) -> None:
    repo, _, revision = _prepare(tmp_path)
    result = profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    report_file = records / result["report"]
    report = json.loads(report_file.read_text())
    if tamper == "missing_sha256":
        del report["reads"][0]["sha256"]
    elif tamper == "missing_attempt":
        del report["attempt"]
    elif tamper == "non_int_attempt":
        report["attempt"] = "1"
    elif tamper == "missing_verdict":
        del report["verdict"]
    elif tamper == "legacy_one":
        report = {
            "schema": "profile-dev/verification-report/1",
            "record": 1,
            "change_id": "c1",
            "base": "a" * 40,
            "revision": "b" * 40,
            "attempt": None,
            "attempt_state": "none",
            "reads": [],
            "items": {},
        }
    else:
        report = {
            "schema": "profile-dev/verification-report/2",
            "record": 1,
            "change_id": "c1",
            "revision": "b" * 40,
            "assessments": [],
            "items": {
                "divergences": {
                    "status": "present",
                    "value": [{"source": "review"}],
                }
            },
        }
    report_file.write_text(json.dumps(report))
    before = _snapshot(records)
    _refused(repo, revision, "report.malformed")
    assert _snapshot(records) == before


def test_forged_consistent_verdict_is_detected_without_monkeypatch(
    tmp_path: Path,
) -> None:
    repo, _, revision = _prepare(tmp_path)
    result = profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    report_file = records / result["report"]
    report = json.loads(report_file.read_text())
    assert report["verdict"] == "has pendency"
    report["items"]["pendencies"] = {"status": "absent"}
    report["verdict"] = "consistent"
    report_file.write_text(json.dumps(report))
    before = _snapshot(records)
    _refused(repo, revision, "verdict.mismatch")
    assert _snapshot(records) == before


@pytest.mark.parametrize(
    ("finding", "expected_reason", "expected_result"),
    [
        (
            {
                "source": "review",
                "class": "review-arch",
                "affected_point": "api",
                "criterion": "arch-ok",
                "kind": "review",
            },
            "verdict.has_pendency",
            "not_reverified",
        ),
        (
            {
                "source": "review",
                "association": "requirement",
                "class": "review-arch",
                "affected_point": "api",
                "criterion": "arch-ok",
                "kind": "review",
            },
            "decision.absent",
            "resolved",
        ),
    ],
)
def test_approval_derives_with_history_before_latest_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    finding: dict[str, str],
    expected_reason: str,
    expected_result: str,
) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    report_dir = records / "changes" / "c1" / "report"
    report_dir.mkdir()
    old = {
        "schema": "profile-dev/verification-report/2",
        "record": 1,
        "change_id": "c1",
        "revision": "b" * 40,
        "assessments": [],
        "items": {"divergences": {"status": "present", "value": [finding]}},
    }
    (report_dir / "1.json").write_text(json.dumps(old, separators=(",", ":")))
    _run_results(repo, revision, monkeypatch)
    result = profile_record_report(str(repo), "c1", revision)
    latest = json.loads((records / result["report"]).read_text())
    assert latest["reverification"]["links"][0]["result"] == expected_result
    before = _snapshot(records)
    _refused(repo, revision, expected_reason)
    assert _snapshot(records) == before


def test_nul_in_read_reference_is_digest_mismatch_without_writing(
    tmp_path: Path,
) -> None:
    repo, _, revision = _prepare(tmp_path)
    result = profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    report_file = records / result["report"]
    report = json.loads(report_file.read_text())
    report["reads"][0]["ref"] += "\x00"
    report_file.write_text(json.dumps(report))
    before = _snapshot(records)
    _refused(repo, revision, "digest.mismatch")
    assert _snapshot(records) == before


def test_change_symlink_escape_refuses_approval_exists_without_writing(
    tmp_path: Path,
) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    change_dir = records / "changes" / "c1"
    outside = tmp_path / "outside"
    outside.mkdir()
    change_dir.rename(outside / "c1")
    change_dir.symlink_to(outside / "c1", target_is_directory=True)
    before = _snapshot(records)
    _refused(repo, revision, "approval.exists")
    assert _snapshot(records) == before


def test_combined_precedence_uses_documented_order(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, revision, "id.invalid", change_id="bad/id", actor="\x00")
    _refused(repo, "unknown-revision", "revision.invalid", change_id="c2")
    assert _snapshot(records) == before


def test_valid_committed_decision_writes_approval_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    report = profile_record_report(str(repo), "c1", revision)
    from beddel_profile_dev._io import blob_at
    from beddel_profile_dev.tools.approval_decision import (
        approval_path,
        profile_record_approval_decision,
    )

    profile_record_approval_decision(str(repo), "c1", revision, "tester")
    decision_commit = commit_all(repo, "commit approval decision")
    result = profile_approve_change(
        str(repo), "c1", revision, "tester", decision_commit
    )
    assert set(result) == {
        "ok",
        "change_id",
        "revision",
        "approval",
        "approved_by",
        "proof",
    }
    assert result["ok"] is True
    records = records_root(repo, "records/profile-dev")
    approval_file = records / "changes" / "c1" / "approval.json"
    approval = json.loads(approval_file.read_text())
    assert set(approval) == {
        "schema",
        "change_id",
        "revision",
        "report",
        "report_sha256",
        "attempt",
        "approved_by",
        "proof",
    }
    assert approval["report"] == report["report"]
    assert approval["approved_by"] == "tester"
    decision_rel = approval_path("c1", 1)
    decision_blob = blob_at(repo, decision_commit, decision_rel)
    assert decision_blob is not None
    assert approval["proof"] == {
        "commit": decision_commit,
        "path": decision_rel,
        "sha256": hashlib.sha256(decision_blob).hexdigest(),
    }
    before = approval_file.read_bytes()
    profile_record_report(str(repo), "c1", revision)
    assert approval_file.read_bytes() == before


def test_read_approval_present_absent_and_malformed(tmp_path: Path) -> None:
    from beddel_profile_dev.tools.approval import profile_read_approval

    repo, _, _ = _prepare(tmp_path)
    assert profile_read_approval(str(repo), "c1") == {
        "ok": True,
        "change_id": "c1",
        "approval": None,
    }
    approval_file = (
        records_root(repo, "records/profile-dev") / "changes" / "c1" / "approval.json"
    )
    approval_file.parent.mkdir(parents=True, exist_ok=True)
    approval_file.write_text("not json")
    with pytest.raises(ProfileError) as info:
        profile_read_approval(str(repo), "c1")
    assert info.value.code == "PROFILE_REPOSITORY_INVALID"


def _repo_snapshot(repo: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(repo)): path.read_bytes()
        for path in repo.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(repo).parts
    }


def _committed_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, str, str, Path]:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    from beddel_profile_dev.tools.approval_decision import (
        profile_record_approval_decision,
    )

    decision = profile_record_approval_decision(str(repo), "c1", revision, "tester")
    path = repo / decision["record"]
    return repo, revision, commit_all(repo, "commit approval decision"), path


def _refused_without_changes(
    repo: Path,
    revision: str,
    reason: str,
    decision_commit: str = "HEAD",
    actor: str = "tester",
) -> None:
    records = records_root(repo, "records/profile-dev")
    before_records = _snapshot(records)
    before_repo = _repo_snapshot(repo)
    _refused(repo, revision, reason, decision_commit=decision_commit, actor=actor)
    assert _snapshot(records) == before_records
    assert _repo_snapshot(repo) == before_repo


@pytest.mark.parametrize(
    "variant",
    [
        "non_yaml",
        "non_mapping",
        "wrong_keys",
        "extra_key",
        "bad_types",
        "bad_date",
        "bad_digest",
    ],
)
def test_decision_malformed_variants_refuse_without_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    repo, revision, decision_commit, path = _committed_decision(tmp_path, monkeypatch)
    if variant == "non_yaml":
        path.write_bytes(b"[unterminated")
    else:
        data = yaml.safe_load(path.read_bytes())
        if variant == "non_mapping":
            path.write_text("approval\n")
        elif variant == "wrong_keys":
            del data["approved_at"]
            path.write_text(yaml.safe_dump(data, sort_keys=False))
        elif variant == "extra_key":
            data["extra"] = "value"
            path.write_text(yaml.safe_dump(data, sort_keys=False))
        elif variant == "bad_types":
            data["approved_by"] = []
            path.write_text(yaml.safe_dump(data, sort_keys=False))
        elif variant == "bad_digest":
            data["report_sha256"] = "0" * 63
            path.write_text(yaml.safe_dump(data, sort_keys=False))
        else:
            path.write_text(
                yaml.safe_dump({**data, "approved_at": "2026-13-45"}, sort_keys=False)
            )
    decision_commit = commit_all(repo, f"malformed decision {variant}")
    _refused_without_changes(repo, revision, "decision.malformed", decision_commit)


@pytest.mark.parametrize("foreign", ["ratification", "determination"])
def test_foreign_decision_records_are_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, foreign: str
) -> None:
    repo, revision, _, path = _committed_decision(tmp_path, monkeypatch)
    if foreign == "ratification":
        path.write_text(
            yaml.safe_dump(
                {"schema": "profile-dev/ratification/1", "inventory_version": "v1"},
                sort_keys=False,
            )
        )
    else:
        path.write_text(json.dumps({"schema": NON_APPLICABILITY_SCHEMA}) + "\n")
    decision_commit = commit_all(repo, f"foreign {foreign}")
    _refused_without_changes(repo, revision, "decision.unsupported", decision_commit)


@pytest.mark.parametrize("approved_by", ["\x00", "", "x" * 201])
def test_invalid_decision_actor_refuses_without_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, approved_by: str
) -> None:
    repo, revision, _, path = _committed_decision(tmp_path, monkeypatch)
    data = yaml.safe_load(path.read_bytes())
    data["approved_by"] = approved_by
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    decision_commit = commit_all(repo, "invalid decision actor")
    _refused_without_changes(repo, revision, "decision.actor_invalid", decision_commit)


@pytest.mark.parametrize("field", ["change_id", "revision", "report"])
def test_decision_target_mismatch_refuses_without_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    repo, revision, _, path = _committed_decision(tmp_path, monkeypatch)
    data = yaml.safe_load(path.read_bytes())
    data[field] = "other" if field != "revision" else "0" * 40
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    decision_commit = commit_all(repo, "mismatched decision target")
    _refused_without_changes(
        repo, revision, "decision.target_mismatch", decision_commit
    )


def test_decision_digest_mismatch_refuses_without_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, revision, _, path = _committed_decision(tmp_path, monkeypatch)
    data = yaml.safe_load(path.read_bytes())
    data["report_sha256"] = "0" * 64
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    decision_commit = commit_all(repo, "mismatched decision digest")
    _refused_without_changes(
        repo, revision, "decision.digest_mismatch", decision_commit
    )


def test_actor_mismatch_refuses_without_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, revision, decision_commit, _ = _committed_decision(tmp_path, monkeypatch)
    _refused_without_changes(
        repo, revision, "actor.mismatch", decision_commit, actor="other"
    )


def test_decision_commit_invalid_refuses_without_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, revision, _, _ = _committed_decision(tmp_path, monkeypatch)
    _refused_without_changes(
        repo, revision, "decision.commit_invalid", "missing-commit"
    )


def test_decision_unreachable_refuses_without_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    original = git(repo, "branch", "--show-current")
    git(repo, "checkout", "-q", "-b", "approval-side")
    from beddel_profile_dev.tools.approval_decision import (
        profile_record_approval_decision,
    )

    profile_record_approval_decision(str(repo), "c1", revision, "tester")
    side_commit = commit_all(repo, "unreachable decision")
    git(repo, "checkout", "-q", original)
    _refused_without_changes(repo, revision, "decision.unreachable", side_commit)


def test_decision_absent_when_only_in_worktree_or_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    from beddel_profile_dev.tools.approval_decision import (
        profile_record_approval_decision,
    )

    profile_record_approval_decision(str(repo), "c1", revision, "tester")
    path = repo / ".beddel-profile" / "approvals" / "c1" / "1.yaml"
    assert path.is_file()
    _refused_without_changes(repo, revision, "decision.absent")
    git(repo, "add", str(path.relative_to(repo)))
    path.unlink()
    _refused_without_changes(repo, revision, "decision.absent")
    git(repo, "rm", "-q", "--cached", str(path.relative_to(repo)))


def test_stale_decision_after_a_newer_report_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, revision, decision_commit, _ = _committed_decision(tmp_path, monkeypatch)
    newer = profile_record_report(str(repo), "c1", revision)
    assert newer["report"].endswith("/2.json")
    _refused_without_changes(repo, revision, "decision.absent", decision_commit)


def test_committed_decision_cannot_pass_has_pendency(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    profile_record_report(str(repo), "c1", revision)
    from beddel_profile_dev.tools.approval_decision import (
        profile_record_approval_decision,
    )

    profile_record_approval_decision(str(repo), "c1", revision, "tester")
    decision_commit = commit_all(repo, "decision for a has pendency Report")
    _refused_without_changes(repo, revision, "verdict.has_pendency", decision_commit)


def test_ancestry_failure_is_unreachable_without_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, revision, decision_commit, _ = _committed_decision(tmp_path, monkeypatch)
    from beddel_profile_dev.tools import approval

    def fail(*args: object, **kwargs: object) -> bool:
        raise ProfileError(PROFILE_REPOSITORY_INVALID, "ancestry failed")

    monkeypatch.setattr(approval, "is_ancestor", fail)
    _refused_without_changes(repo, revision, "decision.unreachable", decision_commit)


def test_dangling_approval_symlink_counts_as_existing_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, revision, decision_commit, _ = _committed_decision(tmp_path, monkeypatch)
    approval_file = (
        records_root(repo, "records/profile-dev") / "changes" / "c1" / "approval.json"
    )
    approval_file.symlink_to("missing-approval.json")
    _refused_without_changes(repo, revision, "approval.exists", decision_commit)


def test_approval_is_create_only_even_after_a_newer_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, revision, decision_commit, _ = _committed_decision(tmp_path, monkeypatch)
    profile_approve_change(str(repo), "c1", revision, "tester", decision_commit)
    approval_file = (
        records_root(repo, "records/profile-dev") / "changes" / "c1" / "approval.json"
    )
    before = approval_file.read_bytes()
    _refused_without_changes(repo, revision, "approval.exists", decision_commit)
    profile_record_report(str(repo), "c1", revision)
    _refused_without_changes(repo, revision, "approval.exists", decision_commit)
    assert approval_file.read_bytes() == before


def _stored_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, str]:
    repo, revision, decision_commit, _ = _committed_decision(tmp_path, monkeypatch)
    profile_approve_change(str(repo), "c1", revision, "tester", decision_commit)
    return (
        repo,
        records_root(repo, "records/profile-dev") / "changes" / "c1" / "approval.json",
        revision,
    )


@pytest.mark.parametrize(
    "tamper",
    [
        "extra_key",
        "wrong_schema",
        "other_change",
        "short_commit",
        "attempt_zero",
        "bad_report",
        "bad_proof_path",
    ],
)
def test_read_approval_wrong_shapes_refuse_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tamper: str
) -> None:
    repo, approval_file, _ = _stored_approval(tmp_path, monkeypatch)
    data = json.loads(approval_file.read_text())
    if tamper == "extra_key":
        data["extra"] = True
    elif tamper == "wrong_schema":
        data["schema"] = "profile-dev/approval/0"
    elif tamper == "other_change":
        data["change_id"] = "other"
    elif tamper == "short_commit":
        data["proof"]["commit"] = "short"
    elif tamper == "attempt_zero":
        data["attempt"] = 0
    elif tamper == "bad_report":
        data["report"] = "changes/c1/report/01.json"
    else:
        data["proof"]["path"] = ".beddel-profile/approvals/c1/2.yaml"
    approval_file.write_text(json.dumps(data))
    records = records_root(repo, "records/profile-dev")
    before_records = _snapshot(records)
    before_repo = _repo_snapshot(repo)
    with pytest.raises(ProfileError) as info:
        profile_read_approval(str(repo), "c1")
    assert info.value.code == PROFILE_REPOSITORY_INVALID
    assert _snapshot(records) == before_records
    assert _repo_snapshot(repo) == before_repo


def test_read_approval_valid_present_and_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, approval_file, _ = _stored_approval(tmp_path, monkeypatch)
    expected = json.loads(approval_file.read_text())
    records = records_root(repo, "records/profile-dev")
    before_records = _snapshot(records)
    before_repo = _repo_snapshot(repo)
    assert profile_read_approval(str(repo), "c1")["approval"] == expected
    assert _snapshot(records) == before_records
    assert _repo_snapshot(repo) == before_repo


def test_read_approval_invalid_id_and_unrecorded_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, _ = _stored_approval(tmp_path, monkeypatch)
    with pytest.raises(ProfileError) as invalid:
        profile_read_approval(str(repo), "bad/id")
    assert invalid.value.code == PROFILE_CHANGE_INVALID
    with pytest.raises(ProfileError) as unrecorded:
        profile_read_approval(str(repo), "other")
    assert unrecorded.value.code == "PROFILE_IMPACT_UNBOUND"
