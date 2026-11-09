"""Read-only publication source tests for Story 7.1b."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from beddel_profile_dev._errors import PROFILE_PUBLICATION_REFUSED, ProfileError
from beddel_profile_dev._io import canonical_json, records_root
from beddel_profile_dev.tools.publication import profile_read_reverification
from beddel_profile_dev.tools.report import profile_read_report, profile_record_report

from ._helpers import change_fixture
from .test_report import (
    _prepare,
    _prepare_next_revision,
    _review_divergence_output,
    _run_results,
)


def _records_snapshot(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _recorded_publication_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, dict[str, object]]:
    repo, base, first_revision = _prepare(tmp_path)
    _run_results(repo, first_revision, monkeypatch, _review_divergence_output())
    profile_record_report(str(repo), "c1", first_revision)
    second_revision = _prepare_next_revision(repo, base)
    _run_results(repo, second_revision, monkeypatch)
    written = profile_record_report(str(repo), "c1", second_revision)
    records = records_root(repo, "records/profile-dev")
    return repo, records, json.loads((records / written["report"]).read_text())


def _assert_refusal(repo: Path, reason: str, records: Path | None = None) -> None:
    before = _records_snapshot(records) if records is not None else None
    with pytest.raises(ProfileError) as error:
        profile_read_reverification(str(repo), "c1")
    assert error.value.code == PROFILE_PUBLICATION_REFUSED
    assert error.value.details == {"reason": reason}
    assert error.value.message == f"publication refused: {reason}"
    if records is not None:
        assert _records_snapshot(records) == before


def test_returns_the_stored_reverification_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, records, stored = _recorded_publication_fixture(tmp_path, monkeypatch)
    before = _records_snapshot(records)

    result = profile_read_reverification(str(repo), "c1")
    report = profile_read_report(str(repo), "c1")

    assert canonical_json(result["reverification"]) == canonical_json(
        report["report"]["reverification"]
    )
    assert canonical_json(result["reverification"]) == canonical_json(
        stored["reverification"]
    )
    assert result["report"] == "changes/c1/report/2.json"
    assert (
        result["report_sha256"]
        == hashlib.sha256((records / result["report"]).read_bytes()).hexdigest()
    )
    assert _records_snapshot(records) == before


def test_refuses_invalid_id_before_repository_access(tmp_path: Path) -> None:
    with pytest.raises(ProfileError) as error:
        profile_read_reverification(str(tmp_path / "absent"), "not valid")
    assert error.value.code == PROFILE_PUBLICATION_REFUSED
    assert error.value.details == {"reason": "id.invalid"}


def test_refuses_when_change_is_unrecorded_and_creates_no_directory(
    tmp_path: Path,
) -> None:
    repo, _, _ = change_fixture(tmp_path, lambda path: None)
    records = records_root(repo, "records/profile-dev")
    assert not records.exists()
    _assert_refusal(repo, "change.unrecorded", records)
    assert not records.exists()


def test_refuses_when_report_is_absent(tmp_path: Path) -> None:
    repo, _, _ = _prepare(tmp_path)
    _assert_refusal(repo, "report.absent", records_root(repo, "records/profile-dev"))


def test_refuses_not_applicable_reverification(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    profile_record_report(str(repo), "c1", revision)
    _assert_refusal(
        repo, "reverification.not_recorded", records_root(repo, "records/profile-dev")
    )


def test_refuses_older_report_schema(tmp_path: Path) -> None:
    repo, _, _ = _prepare(tmp_path)
    report_dir = records_root(repo, "records/profile-dev") / "changes/c1/report"
    report_dir.mkdir()
    (report_dir / "1.json").write_text(
        json.dumps(
            {
                "schema": "profile-dev/verification-report/1",
                "record": 1,
                "change_id": "c1",
                "revision": "a" * 40,
            }
        )
    )
    _assert_refusal(
        repo, "reverification.not_recorded", report_dir.parent.parent.parent
    )


def test_refuses_malformed_latest_report_without_writing(
    tmp_path: Path,
) -> None:
    repo, _, _ = _prepare(tmp_path)
    report_dir = records_root(repo, "records/profile-dev") / "changes/c1/report"
    report_dir.mkdir()
    (report_dir / "1.json").write_text("not json")
    _assert_refusal(repo, "report.malformed", report_dir.parent.parent.parent)


def test_refuses_invalid_latest_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, records, _ = _recorded_publication_fixture(tmp_path, monkeypatch)
    report_path = records / "changes/c1/report/2.json"
    report = json.loads(report_path.read_text())
    report["reads"] = [{"ref": "not-a-record", "sha256": "bad"}]
    report_path.write_text(json.dumps(report))
    _assert_refusal(repo, "report.malformed", records)


def test_refuses_when_a_report_read_digest_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, records, stored = _recorded_publication_fixture(tmp_path, monkeypatch)
    ref = next(
        item["ref"]
        for item in stored["reads"]
        if "/report/" not in item["ref"] and not item["ref"].endswith("change.json")
    )
    (records / ref).write_bytes(b"changed\n")
    _assert_refusal(repo, "digest.mismatch", records)


def test_source_is_read_only_and_has_no_protocol_client_logic() -> None:
    source = (
        Path(__file__).parents[1] / "python/beddel_profile_dev/tools/publication.py"
    )
    text = source.read_text()
    assert "mcp" not in text.lower()
    assert "call_tool" not in text
    assert "write_create_only" not in text
    assert "open(" not in text
    module_root = source.parents[1]
    assert all(
        "mcp" not in path.read_text().lower() for path in module_root.rglob("*.py")
    )
