"""Story 5.1: Approval revalidation is fail-closed and write-free."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from beddel_profile_dev._errors import PROFILE_APPROVAL_REFUSED, ProfileError
from beddel_profile_dev._io import records_root
from beddel_profile_dev.tools.approval import profile_approve_change
from beddel_profile_dev.tools.bind import profile_bind_inventory
from beddel_profile_dev.tools.change import profile_record_change
from beddel_profile_dev.tools.impact import profile_derive_impact
from beddel_profile_dev.tools.report import profile_record_report

from ._helpers import change_fixture, commit_all
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
) -> ProfileError:
    with pytest.raises(ProfileError) as info:
        profile_approve_change(str(repo), change_id, revision, actor)
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


def test_consistent_is_still_refused_until_story_5_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, revision, "approval.unaccepted")
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
    _refused(repo, first_revision, "approval.unaccepted")
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
        if path.name not in {"approval.py", "_errors.py"}:
            assert "approv" not in path.read_text().lower()
    source = (PYTHON_ROOT / "beddel_profile_dev" / "tools" / "approval.py").read_text()
    for forbidden in (
        "write_create_only",
        "open(",
        "mkdir",
        "write_bytes",
        "write_text",
    ):
        assert forbidden not in source
    tree = ast.parse(source)
    imported_modules = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    ] + [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    forbidden_modules = {
        "datetime",
        "time",
        "subprocess",
        "_adapters",
        "socket",
        "urllib",
        "http",
    }
    assert all(
        not forbidden_modules.intersection(module.split("."))
        for module in imported_modules
    )
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
        profile_approve_change(str(tmp_path / "missing"), "c1", "HEAD", "tester")
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
            "approval.unaccepted",
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


def test_change_symlink_escape_is_unrecorded_without_writing(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    change_dir = records / "changes" / "c1"
    outside = tmp_path / "outside"
    outside.mkdir()
    change_dir.rename(outside / "c1")
    change_dir.symlink_to(outside / "c1", target_is_directory=True)
    before = _snapshot(records)
    _refused(repo, revision, "change.unrecorded")
    assert _snapshot(records) == before


def test_combined_precedence_uses_documented_order(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    before = _snapshot(records)
    _refused(repo, revision, "id.invalid", change_id="bad/id", actor="\x00")
    _refused(repo, "unknown-revision", "revision.invalid", change_id="c2")
    assert _snapshot(records) == before
