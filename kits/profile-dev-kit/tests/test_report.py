"""Story 4.1 Verification Report tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from beddel_profile_dev import _adapters
from beddel_profile_dev import config as cfg
from beddel_profile_dev._errors import (
    PROFILE_IMPACT_UNBOUND,
    PROFILE_REPOSITORY_INVALID,
    ProfileError,
)
from beddel_profile_dev._io import records_root
from beddel_profile_dev.findings import (
    ASSESSMENT_BEGIN,
    ASSESSMENT_END,
    REVIEW_ASSESSMENT_SCHEMA,
)
from beddel_profile_dev.tools.attempt import profile_open_attempt
from beddel_profile_dev.tools.bind import profile_bind_inventory
from beddel_profile_dev.tools.change import profile_record_change
from beddel_profile_dev.tools.determine import profile_declare_non_applicability
from beddel_profile_dev.tools.evidence import EVIDENCE_SCHEMA, profile_capture_evidence
from beddel_profile_dev.tools.gate import profile_run_gate
from beddel_profile_dev.tools.impact import profile_derive_impact
from beddel_profile_dev.tools.report import profile_read_report, profile_record_report
from beddel_profile_dev.tools.review import profile_run_review

from ._helpers import (
    FakeReviewAdapter,
    change_fixture,
    commit_all,
    good,
    stub_gate_tools,
)

_FORBIDDEN_KEYS = {"approval", "approved", "blocking", "finding", "passed"}


def _assert_no_forbidden_keys(value: object) -> None:
    if isinstance(value, dict):
        assert not _FORBIDDEN_KEYS.intersection(value)
        for nested in value.values():
            _assert_no_forbidden_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_forbidden_keys(nested)


def _prepare(tmp_path: Path, data: object = None) -> tuple[Path, str, str]:
    repo, base, revision = change_fixture(
        tmp_path,
        lambda path: (path / "src" / "api.py").write_text("x = 2\n"),
        data=data,
    )
    profile_record_change(str(repo), "c1", base, revision)
    profile_bind_inventory(str(repo), revision, "v1")
    profile_derive_impact(str(repo), "c1", revision)
    return repo, base, revision


def _run_results(
    repo: Path,
    revision: str,
    monkeypatch: pytest.MonkeyPatch,
    review_output: str | None = None,
) -> int:
    if review_output is None:
        review_output = (
            f"{ASSESSMENT_BEGIN}\n"
            + json.dumps(
                {
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
                },
                separators=(",", ":"),
            )
            + f"\n{ASSESSMENT_END}\n"
        )
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("git", "status", "--porcelain"),))
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    profile_run_gate(str(repo), "c1", revision, attempt)
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: FakeReviewAdapter(
            "completed", output=review_output
        ),
    )
    asyncio.run(profile_run_review(str(repo), "c1", revision, attempt))
    assert profile_capture_evidence(str(repo), "c1", revision, attempt)["evidence"] == 2
    return attempt


def test_full_report_has_seven_items_and_sorted_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    attempt = _run_results(repo, revision, monkeypatch)
    result = profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    path = records / result["report"]
    report = json.loads(path.read_text())
    _assert_no_forbidden_keys(report)
    assert report["record"] == 1
    assert report["schema"] == "profile-dev/verification-report/4"
    assert report["attempt"] == attempt
    assert report["attempt_state"] == "valid"
    assert set(report["items"]) == {
        "specification",
        "applicable_criteria",
        "affected_points",
        "implementation",
        "evidence",
        "divergences",
        "pendencies",
    }
    assert report["items"]["evidence"]["status"] == "present"
    assert report["items"]["pendencies"] == {"status": "absent"}
    assert report["verdict"] == "consistent"
    assert report["reads"] == sorted(report["reads"], key=lambda item: item["ref"])
    assert any(item["ref"].endswith("/attempt.json") for item in report["reads"])

    impact = json.loads(
        (records / f"changes/c1/revisions/{revision}/impact.json").read_text()
    )
    snapshot = json.loads((records / f"revisions/{revision}/snapshot.json").read_text())
    descriptions = {item["id"]: item["description"] for item in snapshot["criteria"]}
    requirements = sorted(
        impact["required_evidence"],
        key=lambda item: (item["class"], item["affected_point"], item["criterion"]),
    )
    assert report["items"]["specification"] == {"status": "absent"}
    assert report["items"]["applicable_criteria"] == {
        "status": "present",
        "value": [
            {
                "class": item["class"],
                "affected_point": item["affected_point"],
                "criterion": item["criterion"],
                "kind": item["kind"],
                "description": descriptions[item["criterion"]],
                "non_applicability": None,
            }
            for item in requirements
        ],
    }
    assert report["items"]["affected_points"] == {
        "status": "present",
        "value": impact["affected_points"],
    }
    assert report["items"]["implementation"] == {
        "status": "present",
        "value": {
            "base": impact["base"],
            "revision": impact["revision"],
            "footprint": impact["footprint"],
        },
    }
    evidence_dir = (
        records / f"changes/c1/revisions/{revision}/attempts/{attempt}/evidence"
    )
    evidence_records = [
        (path, json.loads(path.read_text()))
        for path in sorted(evidence_dir.glob("*.json"))
    ]
    expected_evidence = [
        {
            "class": data["class"],
            "affected_point": data["affected_point"],
            "criterion": data["criterion"],
            "kind": data["kind"],
            "ref": str(path.relative_to(records)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "result": data["result"],
        }
        for path, data in sorted(
            evidence_records,
            key=lambda pair: (
                pair[1]["class"],
                pair[1]["affected_point"],
                pair[1]["criterion"],
            ),
        )
    ]
    assert report["items"]["evidence"] == {
        "status": "present",
        "value": expected_evidence,
    }
    assert report["items"]["divergences"] == {"status": "absent"}
    assert report["assessments"] == [
        {
            "class": "gate-unit",
            "affected_point": "api",
            "criterion": "tests-pass",
            "kind": "gate",
            "state": "no_divergence",
        },
        {
            "class": "review-arch",
            "affected_point": "api",
            "criterion": "arch-ok",
            "kind": "review",
            "state": "no_divergence",
        },
    ]


def test_review_divergence_is_persisted_as_a_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    output = json.dumps(
        {
            "schema": REVIEW_ASSESSMENT_SCHEMA,
            "assessments": [
                {
                    "class": "review-arch",
                    "affected_point": "api",
                    "criterion": "arch-ok",
                    "divergences": [
                        {
                            "between": ["specification", "implementation"],
                            "description": "the API differs from the requirement",
                        }
                    ],
                }
            ],
            "unassociated": [],
        },
        separators=(",", ":"),
    )
    review_output = f"{ASSESSMENT_BEGIN}\n{output}\n{ASSESSMENT_END}\n"
    _run_results(repo, revision, monkeypatch, review_output)

    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )

    review_assessment = next(
        item for item in report["assessments"] if item["kind"] == "review"
    )
    assert review_assessment["state"] == "divergent"
    assert report["items"]["divergences"]["status"] == "present"
    assert report["items"]["divergences"]["value"] == [
        {
            "source": "review",
            "association": "requirement",
            "class": "review-arch",
            "affected_point": "api",
            "criterion": "arch-ok",
            "kind": "review",
            "classification": "unclassified",
            "between": ["specification", "implementation"],
            "detail": {
                "description": "the API differs from the requirement",
                "review_ref": next(
                    item["result"]["review_ref"]
                    for item in report["items"]["evidence"]["value"]
                    if item["kind"] == "review"
                ),
                "review_sha256": next(
                    item["result"]["review_sha256"]
                    for item in report["items"]["evidence"]["value"]
                    if item["kind"] == "review"
                ),
            },
        }
    ]
    assert report["items"]["pendencies"]["value"] == [
        {
            "reason": "finding_unclassified",
            "class": "review-arch",
            "affected_point": "api",
            "criterion": "arch-ok",
            "kind": "review",
            "finding_index": 0,
        }
    ]
    assert report["verdict"] == "has pendency"


def test_gate_failure_is_persisted_as_a_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("pytest", "-q"),))
    monkeypatch.setattr(cfg, "GATE_TOTAL_TIMEOUT_SECONDS", None)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("STUB_EXIT_PYTEST", "1")
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    profile_run_gate(str(repo), "c1", revision, attempt)
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: FakeReviewAdapter(
            "completed",
            output=(
                f"{ASSESSMENT_BEGIN}\n"
                + json.dumps(
                    {
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
                    },
                    separators=(",", ":"),
                )
                + f"\n{ASSESSMENT_END}\n"
            ),
        ),
    )
    asyncio.run(profile_run_review(str(repo), "c1", revision, attempt))
    profile_capture_evidence(str(repo), "c1", revision, attempt)

    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )
    gate_assessment = next(
        item for item in report["assessments"] if item["kind"] == "gate"
    )
    assert gate_assessment["state"] == "divergent"
    findings = report["items"]["divergences"]["value"]
    assert len(findings) == 1
    assert findings[0]["source"] == "gate"
    assert findings[0]["detail"]["exit_code"] == 1


def test_gate_timeout_is_indeterminate_without_a_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("pytest", "-q"),))
    monkeypatch.setattr(cfg, "GATE_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(cfg, "GATE_TOTAL_TIMEOUT_SECONDS", None)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("STUB_SLEEP_PYTEST", "2")
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    profile_run_gate(str(repo), "c1", revision, attempt)
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: FakeReviewAdapter(
            "completed",
            output=(
                f"{ASSESSMENT_BEGIN}\n"
                + json.dumps(
                    {
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
                    },
                    separators=(",", ":"),
                )
                + f"\n{ASSESSMENT_END}\n"
            ),
        ),
    )
    asyncio.run(profile_run_review(str(repo), "c1", revision, attempt))
    profile_capture_evidence(str(repo), "c1", revision, attempt)

    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )
    gate_assessment = next(
        item for item in report["assessments"] if item["kind"] == "gate"
    )
    assert gate_assessment["state"] == "indeterminate"
    assert report["items"]["divergences"] == {"status": "not_assessed"}


def test_read_report_accepts_an_older_schema_one_record_unchanged(
    tmp_path: Path,
) -> None:
    repo, _, _ = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    report_dir = records / "changes" / "c1" / "report"
    report_dir.mkdir()
    old = {
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
    raw = json.dumps(old, separators=(",", ":")).encode()
    (report_dir / "1.json").write_bytes(raw)
    result = profile_read_report(str(repo), "c1")
    assert result["report"] == old
    assert result["history"][0]["content"] == old
    assert (report_dir / "1.json").read_bytes() == raw


def test_read_report_rejects_schema_two_without_assessments(tmp_path: Path) -> None:
    repo, _, _ = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    report_dir = records / "changes" / "c1" / "report"
    report_dir.mkdir()
    (report_dir / "1.json").write_text(
        json.dumps(
            {
                "schema": "profile-dev/verification-report/2",
                "record": 1,
                "change_id": "c1",
            },
            separators=(",", ":"),
        )
    )
    with pytest.raises(ProfileError) as info:
        profile_read_report(str(repo), "c1")
    assert info.value.code == PROFILE_REPOSITORY_INVALID


def test_read_report_preserves_mixed_schema_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    report_dir = records / "changes" / "c1" / "report"
    report_dir.mkdir()
    old = {
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
    old_raw = json.dumps(old, separators=(",", ":")).encode()
    (report_dir / "1.json").write_bytes(old_raw)
    _run_results(repo, revision, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    result = profile_read_report(str(repo), "c1")
    assert [item["content"]["schema"] for item in result["history"]] == [
        "profile-dev/verification-report/1",
        "profile-dev/verification-report/4",
    ]
    assert result["history"][0]["content"] == old
    assert (report_dir / "1.json").read_bytes() == old_raw


def test_read_report_preserves_valid_schema_two_history_and_reverification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
        "items": {
            "divergences": {
                "status": "present",
                "value": [
                    {
                        "source": "review",
                        "class": "review-arch",
                        "affected_point": "api",
                        "criterion": "arch-ok",
                        "kind": "review",
                    }
                ],
            }
        },
    }
    raw = json.dumps(old, separators=(",", ":")).encode()
    (report_dir / "1.json").write_bytes(raw)

    _run_results(repo, revision, monkeypatch)
    written = profile_record_report(str(repo), "c1", revision)
    result = profile_read_report(str(repo), "c1")

    assert result["history"][0]["content"] == old
    assert (report_dir / "1.json").read_bytes() == raw
    assert written["record"] == 2
    report = json.loads((records / written["report"]).read_text())
    assert report["reverification"] == {
        "status": "recorded",
        "earlier_revision": "b" * 40,
        "links": [
            {
                "report_ref": "changes/c1/report/1.json",
                "finding_index": 0,
                "association": None,
                "class": None,
                "affected_point": None,
                "criterion": None,
                "kind": None,
                "state": None,
                "result": "not_reverified",
                "reason": "outside_scope",
            }
        ],
    }
    reverification = report["items"]["pendencies"]["value"][-1]
    assert reverification["reason"] == "earlier_finding_not_reverified"
    assert reverification["link_index"] == 0


@pytest.mark.parametrize(
    "tamper",
    [
        "missing_revision",
        "items_not_dict",
        "divergences_not_dict",
        "divergences_empty",
        "divergences_absent_value",
        "divergences_not_assessed_value",
    ],
)
def test_invalid_schema_two_history_stops_record_without_writing(
    tmp_path: Path, tamper: str
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
        "items": {
            "divergences": {
                "status": "present",
                "value": [
                    {
                        "source": "review",
                        "class": "review-arch",
                        "affected_point": "api",
                        "criterion": "arch-ok",
                        "kind": "review",
                    }
                ],
            }
        },
    }
    if tamper == "missing_revision":
        del old["revision"]
    elif tamper == "items_not_dict":
        old["items"] = []
    elif tamper == "divergences_not_dict":
        old["items"]["divergences"] = []
    elif tamper == "divergences_empty":
        old["items"]["divergences"] = {"status": "present", "value": []}
    elif tamper == "divergences_absent_value":
        old["items"]["divergences"] = {"status": "absent", "value": []}
    else:
        old["items"]["divergences"] = {
            "status": "not_assessed",
            "value": [],
        }
    (report_dir / "1.json").write_text(json.dumps(old, separators=(",", ":")))

    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)

    assert info.value.code == PROFILE_REPOSITORY_INVALID
    assert sorted(path.name for path in report_dir.iterdir()) == ["1.json"]


def test_rerun_appends_report_without_rewriting_previous_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    first_attempt = _run_results(repo, revision, monkeypatch)
    first = profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    first_path = records / first["report"]
    first_bytes = first_path.read_bytes()
    second_attempt = _run_results(repo, revision, monkeypatch)
    second = profile_record_report(str(repo), "c1", revision)
    assert (first_attempt, second_attempt) == (1, 2)
    assert second["record"] == 2
    assert second["attempt"] == 2
    assert first_path.read_bytes() == first_bytes


def test_timeout_review_is_recorded_as_pendency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("git", "status", "--porcelain"),))
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    profile_run_gate(str(repo), "c1", revision, attempt)
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: FakeReviewAdapter("timeout"),
    )
    asyncio.run(profile_run_review(str(repo), "c1", revision, attempt))
    profile_capture_evidence(str(repo), "c1", revision, attempt)
    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )
    assert report["items"]["evidence"]["status"] == "present"
    assert report["items"]["pendencies"]["status"] == "present"
    assert report["items"]["pendencies"]["value"] == [
        {
            "reason": "evidence_unrecorded",
            "class": "review-arch",
            "affected_point": "api",
            "criterion": "arch-ok",
            "kind": "review",
        }
    ]
    assert report["verdict"] == "has pendency"


def test_no_attempt_is_none_and_all_requirements_are_pending(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )
    assert report["attempt"] is None
    assert report["attempt_state"] == "none"
    assert report["items"]["evidence"] == {"status": "absent"}
    assert report["items"]["divergences"] == {"status": "not_assessed"}
    assert report["assessments"]
    assert all(item["state"] == "not_assessed" for item in report["assessments"])
    assert len(report["items"]["pendencies"]["value"]) == 3


def test_broken_latest_attempt_is_indeterminate_and_older_attempt_is_ignored(
    tmp_path: Path,
) -> None:
    repo, _, revision = _prepare(tmp_path)
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    records = records_root(repo, "records/profile-dev")
    attempts = records / f"changes/c1/revisions/{revision}/attempts"
    (attempts / "3").write_text("stray attempt entry\n")
    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads((records / result["report"]).read_text())
    assert attempt == 1
    assert report["attempt"] == 3
    assert report["attempt_state"] == "indeterminate"
    assert report["items"]["evidence"] == {"status": "absent"}
    assert report["items"]["divergences"] == {"status": "not_assessed"}
    assert report["assessments"]
    assert all(item["state"] == "not_assessed" for item in report["assessments"])
    assert report["items"]["pendencies"]["status"] == "present"
    assert len(report["items"]["pendencies"]["value"]) == 3
    assert all("/attempts/1/" not in item["ref"] for item in report["reads"])


def test_tampered_evidence_stays_unrecorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    attempt = _run_results(repo, revision, monkeypatch)
    records = records_root(repo, "records/profile-dev")
    evidence_dir = (
        records / f"changes/c1/revisions/{revision}/attempts/{attempt}/evidence"
    )
    tampered = next(evidence_dir.glob("*.json"))
    data = json.loads(tampered.read_text())
    data["outcome_sha256"] = "0" * 64
    tampered.write_text(json.dumps(data))
    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads((records / result["report"]).read_text())
    assert report["items"]["pendencies"]["status"] == "present"
    assert len(report["items"]["pendencies"]["value"]) == 1


def test_tampered_completed_review_with_error_code_stays_unrecorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    attempt = _run_results(repo, revision, monkeypatch)
    records = records_root(repo, "records/profile-dev")
    review_path = (
        records / f"changes/c1/revisions/{revision}/attempts/{attempt}/review.json"
    )
    review = json.loads(review_path.read_text())
    review["error_code"] = "BEDDEL-AGENT-701"
    review_path.write_text(json.dumps(review))
    evidence_path = (
        records / f"changes/c1/revisions/{revision}/attempts/{attempt}/evidence/"
        "review-arch+api+arch-ok.json"
    )
    evidence = json.loads(evidence_path.read_text())
    evidence["outcome_sha256"] = hashlib.sha256(review_path.read_bytes()).hexdigest()
    evidence_path.write_text(json.dumps(evidence))

    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads((records / result["report"]).read_text())
    assert report["items"]["pendencies"]["value"] == [
        {
            "reason": "evidence_unrecorded",
            "class": "review-arch",
            "affected_point": "api",
            "criterion": "arch-ok",
            "kind": "review",
        }
    ]


def test_unbound_change_writes_nothing(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    (records / "revisions" / revision / "binding.json").unlink()
    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)
    assert info.value.code == PROFILE_IMPACT_UNBOUND
    assert not (records / "changes" / "c1" / "report").exists()


def test_read_report_without_record_returns_null_and_empty_history(
    tmp_path: Path,
) -> None:
    repo, _, _ = _prepare(tmp_path)
    result = profile_read_report(str(repo), "c1")
    assert result["report"] is None
    assert result["history"] == []


def test_several_attempts_read_only_the_greatest_ordinal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    first = _run_results(repo, revision, monkeypatch)
    second = _run_results(repo, revision, monkeypatch)
    assert (first, second) == (1, 2)
    records = records_root(repo, "records/profile-dev")
    (records / f"changes/c1/revisions/{revision}/attempts/1/attempt.json").write_text(
        "{}"
    )

    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads((records / result["report"]).read_text())
    assert report["attempt"] == 2
    assert report["attempt_state"] == "valid"
    assert report["items"]["evidence"]["status"] == "present"
    assert report["items"]["pendencies"] == {"status": "absent"}
    assert all("/attempts/1/" not in item["ref"] for item in report["reads"])


def test_unrecorded_change_writes_nothing(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    (records / "changes" / "c1" / "change.json").unlink()
    before = {path.relative_to(records) for path in records.rglob("*")}

    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)

    assert info.value.code == PROFILE_IMPACT_UNBOUND
    assert {path.relative_to(records) for path in records.rglob("*")} == before
    assert not (records / "changes" / "c1" / "report").exists()


def test_escaping_records_subdir_writes_nothing(
    tmp_path: Path,
) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    outside = tmp_path / "outside"
    outside.mkdir()
    report_dir = records / "changes" / "c1" / "report"
    report_dir.symlink_to(outside, target_is_directory=True)
    before = {path.relative_to(records) for path in records.rglob("*")}

    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)

    assert info.value.code == PROFILE_REPOSITORY_INVALID
    assert {path.relative_to(records) for path in records.rglob("*")} == before
    assert not (outside / "1.json").exists()


def test_unbound_impact_writes_nothing(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    (records / "changes" / "c1" / "revisions" / revision / "impact.json").unlink()
    before = {path.relative_to(records) for path in records.rglob("*")}

    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)

    assert info.value.code == PROFILE_IMPACT_UNBOUND
    assert {path.relative_to(records) for path in records.rglob("*")} == before
    assert not (records / "changes" / "c1" / "report").exists()


def test_non_applicability_is_listed_but_remains_a_pendency(tmp_path: Path) -> None:
    repo, base, revision = change_fixture(
        tmp_path, lambda path: (path / "src" / "contracts.yaml").unlink()
    )
    profile_record_change(str(repo), "c1", base, revision)
    profile_bind_inventory(str(repo), revision, "v1")
    profile_derive_impact(str(repo), "c1", revision)
    declared = profile_declare_non_applicability(
        str(repo), revision, "gate-unit", "contracts", "tests-pass", "tester"
    )
    records = records_root(repo, "records/profile-dev")
    determination_path = records / declared["determination"]
    determination_sha256 = hashlib.sha256(determination_path.read_bytes()).hexdigest()
    first = profile_record_report(str(repo), "c1", revision)
    report = json.loads((records / first["report"]).read_text())
    criterion = next(
        item
        for item in report["items"]["applicable_criteria"]["value"]
        if item["affected_point"] == "contracts"
    )
    assert criterion["non_applicability"] == {
        "ref": declared["determination"],
        "sha256": determination_sha256,
    }
    assert {
        item["affected_point"]
        for item in report["items"]["pendencies"]["value"]
        if item["affected_point"] is not None
    } == {"api", "contracts"}
    assert any(
        item["reason"] == "attempt_not_valid"
        for item in report["items"]["pendencies"]["value"]
    )

    tampered = json.loads(determination_path.read_text())
    tampered["inventory_sha256"] = "0" * 64
    determination_path.write_text(json.dumps(tampered))
    second = profile_record_report(str(repo), "c1", revision)
    report = json.loads((records / second["report"]).read_text())
    criterion = next(
        item
        for item in report["items"]["applicable_criteria"]["value"]
        if item["affected_point"] == "contracts"
    )
    assert criterion["non_applicability"] is None


def test_read_report_returns_numeric_history_and_rejects_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    first = profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    report_dir = records / "changes" / "c1" / "report"
    first_content = json.loads((records / first["report"]).read_text())
    for ordinal in (2, 10):
        content = {**first_content, "record": ordinal}
        (report_dir / f"{ordinal}.json").write_text(json.dumps(content))

    result = profile_read_report(str(repo), "c1")
    assert [item["content"]["record"] for item in result["history"]] == [1, 2, 10]
    assert result["report"] == result["history"][-1]["content"]
    for item in result["history"]:
        path = records / item["ref"]
        assert item["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()

    tampered_path = report_dir / "10.json"
    tampered = json.loads(tampered_path.read_text())
    tampered["record"] = 9
    tampered_path.write_text(json.dumps(tampered))
    with pytest.raises(ProfileError) as info:
        profile_read_report(str(repo), "c1")
    assert info.value.code == PROFILE_REPOSITORY_INVALID

    tampered["record"] = 10
    tampered["change_id"] = "other"
    tampered_path.write_text(json.dumps(tampered))
    with pytest.raises(ProfileError) as info:
        profile_read_report(str(repo), "c1")
    assert info.value.code == PROFILE_REPOSITORY_INVALID


def test_read_report_rejects_an_unrecorded_change(tmp_path: Path) -> None:
    repo, _, _ = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    (records / "changes" / "c1" / "change.json").unlink()
    with pytest.raises(ProfileError) as info:
        profile_read_report(str(repo), "c1")
    assert info.value.code == PROFILE_IMPACT_UNBOUND


def test_non_object_impact_is_unbound_and_writes_nothing(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    impact_path = records / "changes" / "c1" / "revisions" / revision / "impact.json"
    impact_path.write_text("[]")
    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)
    assert info.value.code == PROFILE_IMPACT_UNBOUND
    assert not (records / "changes" / "c1" / "report").exists()


@pytest.mark.parametrize(
    "required_evidence",
    [
        {"affected_point": "api", "criterion": "tests-pass", "kind": "gate"},
        {
            "class": "gate-unit",
            "affected_point": "api",
            "criterion": 7,
            "kind": "gate",
        },
    ],
)
def test_malformed_required_evidence_is_unbound(
    tmp_path: Path, required_evidence: dict[str, object]
) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    impact_path = records / "changes" / "c1" / "revisions" / revision / "impact.json"
    impact = json.loads(impact_path.read_text())
    impact["required_evidence"][0] = required_evidence
    impact_path.write_text(json.dumps(impact))

    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)

    assert info.value.code == PROFILE_IMPACT_UNBOUND
    assert not (records / "changes" / "c1" / "report").exists()


def test_forged_evidence_of_a_timed_out_review_stays_unrecorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("git", "status", "--porcelain"),))
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    profile_run_gate(str(repo), "c1", revision, attempt)
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: FakeReviewAdapter("timeout"),
    )
    asyncio.run(profile_run_review(str(repo), "c1", revision, attempt))
    profile_capture_evidence(str(repo), "c1", revision, attempt)
    records = records_root(repo, "records/profile-dev")
    revision_dir = records / f"changes/c1/revisions/{revision}"
    impact = json.loads((revision_dir / "impact.json").read_text())
    requirement = next(
        item for item in impact["required_evidence"] if item["kind"] == "review"
    )
    outcome_path = revision_dir / f"attempts/{attempt}/review.json"
    outcome = json.loads(outcome_path.read_text())
    assert outcome["status"] == "timed_out"
    review_path = records / outcome["review_ref"]
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text("stale review text\n")
    review_output = review_path.read_bytes()
    forged = {
        "schema": EVIDENCE_SCHEMA,
        "attempt": attempt,
        "change_id": "c1",
        "revision": revision,
        "class": requirement["class"],
        "affected_point": requirement["affected_point"],
        "criterion": requirement["criterion"],
        "kind": "review",
        "outcome_ref": f"changes/c1/revisions/{revision}/attempts/{attempt}/review.json",
        "outcome_sha256": hashlib.sha256(outcome_path.read_bytes()).hexdigest(),
        "result": {
            "agent": outcome["agent"],
            "model": outcome["model"],
            "review_ref": outcome["review_ref"],
            "review_sha256": hashlib.sha256(review_output).hexdigest(),
        },
    }
    name = f"{requirement['class']}+{requirement['affected_point']}+{requirement['criterion']}.json"
    evidence_dir = revision_dir / f"attempts/{attempt}/evidence"
    evidence_dir.mkdir(exist_ok=True)
    (evidence_dir / name).write_text(json.dumps(forged))

    result = profile_record_report(str(repo), "c1", revision)

    report = json.loads((records / result["report"]).read_text())
    pending = report["items"]["pendencies"]
    assert pending["status"] == "present"
    assert [item["kind"] for item in pending["value"]] == ["review"]
    assert all(
        item["kind"] != "review" for item in report["items"]["evidence"]["value"]
    )


def test_broken_latest_attempt_directory_ignores_the_older_valid_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    records = records_root(repo, "records/profile-dev")
    attempts = records / f"changes/c1/revisions/{revision}/attempts"
    (attempts / "2").mkdir()

    result = profile_record_report(str(repo), "c1", revision)

    report = json.loads((records / result["report"]).read_text())
    assert report["attempt"] == 2
    assert report["attempt_state"] == "indeterminate"
    assert report["items"]["evidence"] == {"status": "absent"}
    assert len(report["items"]["pendencies"]["value"]) == 3
    assert all("/attempts/1/" not in item["ref"] for item in report["reads"])


def _review_divergence_output(criterion: str = "arch-ok") -> str:
    return (
        f"{ASSESSMENT_BEGIN}\n"
        + json.dumps(
            {
                "schema": REVIEW_ASSESSMENT_SCHEMA,
                "assessments": [
                    {
                        "class": "review-arch",
                        "affected_point": "api",
                        "criterion": criterion,
                        "divergences": [
                            {
                                "between": ["specification", "implementation"],
                                "description": "the API differs from the requirement",
                            }
                        ],
                    }
                ],
                "unassociated": [],
            },
            separators=(",", ":"),
        )
        + f"\n{ASSESSMENT_END}\n"
    )


def test_blocking_finding_derives_has_pendency_and_classification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = good()
    data["criteria"][1]["blocking"] = True
    repo, _, revision = _prepare(tmp_path, data)
    _run_results(repo, revision, monkeypatch, _review_divergence_output())
    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )
    _assert_no_forbidden_keys(report)
    finding = report["items"]["divergences"]["value"][0]
    assert finding["classification"] == "blocking"
    assert report["items"]["pendencies"]["value"][-1] == {
        "reason": "finding_blocking",
        "class": "review-arch",
        "affected_point": "api",
        "criterion": "arch-ok",
        "kind": "review",
        "finding_index": 0,
    }
    assert report["verdict"] == "has pendency"
    assert result["verdict"] == "has pendency"
    for pendency in report["items"]["pendencies"]["value"]:
        if pendency["reason"].startswith("finding_"):
            finding = report["items"]["divergences"]["value"][pendency["finding_index"]]
            assert {
                key: finding[key]
                for key in ("class", "affected_point", "criterion", "kind")
            } == {
                key: pendency[key]
                for key in ("class", "affected_point", "criterion", "kind")
            }


def test_non_blocking_finding_keeps_report_consistent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = good()
    data["criteria"][1]["blocking"] = False
    repo, _, revision = _prepare(tmp_path, data)
    _run_results(repo, revision, monkeypatch, _review_divergence_output())
    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )
    assert report["items"]["divergences"]["value"][0]["classification"] == (
        "non_blocking"
    )
    assert report["items"]["pendencies"] == {"status": "absent"}
    assert report["verdict"] == "consistent"


def test_earlier_revision_finding_requires_reverification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base, first_revision = _prepare(tmp_path)
    _run_results(repo, first_revision, monkeypatch, _review_divergence_output())
    profile_record_report(str(repo), "c1", first_revision)

    (repo / "src" / "api.py").write_text("x = 3\n")
    second_revision = commit_all(repo, "fix")
    profile_record_change(str(repo), "c1", base, second_revision)
    profile_bind_inventory(str(repo), second_revision, "v1")
    profile_derive_impact(str(repo), "c1", second_revision)
    _run_results(repo, second_revision, monkeypatch)
    result = profile_record_report(str(repo), "c1", second_revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )
    assert report["reverification"]["status"] == "recorded"
    assert report["reverification"]["earlier_revision"] == first_revision
    assert report["reverification"]["links"][0]["result"] == "resolved"
    assert report["reverification"]["links"][0]["state"] == "no_divergence"
    earlier_report = (
        records_root(repo, "records/profile-dev") / "changes/c1/report/1.json"
    )
    assert {
        "ref": "changes/c1/report/1.json",
        "sha256": hashlib.sha256(earlier_report.read_bytes()).hexdigest(),
    } in report["reads"]
    records = records_root(repo, "records/profile-dev")
    for link in report["reverification"]["links"]:
        assert {
            "ref": link["report_ref"],
            "sha256": hashlib.sha256(
                (records / link["report_ref"]).read_bytes()
            ).hexdigest(),
        } in report["reads"]
    assert not any(
        item["ref"].startswith(f"revisions/{first_revision}/")
        or f"changes/c1/revisions/{first_revision}/" in item["ref"]
        for item in report["reads"]
        if "ref" in item
    )
    attempt = json.loads(
        (
            records / f"changes/c1/revisions/{second_revision}/attempts/1/attempt.json"
        ).read_text()
    )
    impact = json.loads(
        (records / f"changes/c1/revisions/{second_revision}/impact.json").read_text()
    )
    keys = ("class", "affected_point", "criterion", "kind")
    assert attempt["requirements"] == [
        {key: item[key] for key in keys} for item in impact["required_evidence"]
    ]
    assert report["items"]["pendencies"] == {"status": "absent"}
    assert report["verdict"] == "consistent"


def test_non_blocking_still_divergent_finding_keeps_the_report_consistent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = good()
    data["criteria"][1]["blocking"] = False
    repo, base, first_revision = _prepare(tmp_path, data)
    _run_results(repo, first_revision, monkeypatch, _review_divergence_output())
    profile_record_report(str(repo), "c1", first_revision)
    second_revision = _prepare_next_revision(repo, base)
    _run_results(repo, second_revision, monkeypatch, _review_divergence_output())
    result = profile_record_report(str(repo), "c1", second_revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )
    assert report["reverification"]["links"][0]["result"] == "still_divergent"
    assert report["items"]["divergences"]["value"][0]["classification"] == (
        "non_blocking"
    )
    assert report["items"]["pendencies"] == {"status": "absent"}
    assert report["verdict"] == "consistent"


def test_invalid_earlier_schema_four_is_rejected_before_write(
    tmp_path: Path,
) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    report_dir = records / "changes" / "c1" / "report"
    report_dir.mkdir()
    (report_dir / "1.json").write_text(
        json.dumps(
            {
                "schema": "profile-dev/verification-report/4",
                "record": 1,
                "change_id": "c1",
                "verdict": "maybe",
            },
            separators=(",", ":"),
        )
    )
    before = (report_dir / "1.json").read_bytes()
    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)
    assert info.value.code == PROFILE_REPOSITORY_INVALID
    assert (report_dir / "1.json").read_bytes() == before
    assert not (report_dir / "2.json").exists()


def test_same_revision_rerun_does_not_create_reverification_pendency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch, _review_divergence_output())
    profile_record_report(str(repo), "c1", revision)
    _run_results(repo, revision, monkeypatch)
    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )
    assert report["verdict"] == "consistent"
    assert report["items"]["pendencies"] == {"status": "absent"}


@pytest.mark.parametrize("timed_out", [False, True])
def test_clean_reports_at_two_revisions_stay_consistent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, timed_out: bool
) -> None:
    repo, base, first_revision = _prepare(tmp_path)
    if timed_out:
        monkeypatch.setattr(cfg, "GATE_COMMANDS", (("git", "status", "--porcelain"),))
        attempt = profile_open_attempt(str(repo), "c1", first_revision)["attempt"]
        profile_run_gate(str(repo), "c1", first_revision, attempt)
        monkeypatch.setattr(
            _adapters,
            "get_review_adapter",
            lambda agent_name, *, timeout_seconds: FakeReviewAdapter("timeout"),
        )
        asyncio.run(profile_run_review(str(repo), "c1", first_revision, attempt))
        profile_capture_evidence(str(repo), "c1", first_revision, attempt)
    else:
        _run_results(repo, first_revision, monkeypatch)
    first = profile_record_report(str(repo), "c1", first_revision)
    first_report = json.loads(
        (records_root(repo, "records/profile-dev") / first["report"]).read_text()
    )
    if timed_out:
        assert first_report["items"]["divergences"] == {"status": "not_assessed"}

    (repo / "src" / "api.py").write_text("x = 3\n")
    second_revision = commit_all(repo, "second revision")
    profile_record_change(str(repo), "c1", base, second_revision)
    profile_bind_inventory(str(repo), second_revision, "v1")
    profile_derive_impact(str(repo), "c1", second_revision)
    _run_results(repo, second_revision, monkeypatch)
    second = profile_record_report(str(repo), "c1", second_revision)
    second_report = json.loads(
        (records_root(repo, "records/profile-dev") / second["report"]).read_text()
    )
    assert second_report["items"]["pendencies"] == {"status": "absent"}
    assert second_report["verdict"] == "consistent"


def test_earlier_non_blocking_finding_still_requires_reverification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = good()
    data["criteria"][1]["blocking"] = False
    repo, base, first_revision = _prepare(tmp_path, data)
    _run_results(repo, first_revision, monkeypatch, _review_divergence_output())
    first = profile_record_report(str(repo), "c1", first_revision)
    first_report = json.loads(
        (records_root(repo, "records/profile-dev") / first["report"]).read_text()
    )
    assert first_report["items"]["pendencies"] == {"status": "absent"}

    (repo / "src" / "api.py").write_text("x = 3\n")
    second_revision = commit_all(repo, "second revision")
    profile_record_change(str(repo), "c1", base, second_revision)
    profile_bind_inventory(str(repo), second_revision, "v1")
    profile_derive_impact(str(repo), "c1", second_revision)
    _run_results(repo, second_revision, monkeypatch)
    second = profile_record_report(str(repo), "c1", second_revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / second["report"]).read_text()
    )
    assert report["reverification"]["links"][0]["result"] == "resolved"
    assert report["items"]["pendencies"] == {"status": "absent"}
    assert report["verdict"] == "consistent"


@pytest.mark.parametrize(
    "tamper",
    [
        "verdict",
        "revision",
        "revision_invalid",
        "items",
        "divergences",
        "divergences_empty",
        "divergences_absent_value",
        "divergences_not_assessed_value",
        "pendencies",
        "pendencies_empty",
        "pendencies_absent_value",
    ],
)
def test_tampered_schema_three_history_stops_record_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tamper: str
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    first = profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    report_path = records / first["report"]
    content = json.loads(report_path.read_text())
    if tamper == "verdict":
        content["verdict"] = "has pendency"
    elif tamper == "revision":
        del content["revision"]
    elif tamper == "revision_invalid":
        content["revision"] = "x"
    elif tamper == "items":
        content["items"] = []
    elif tamper == "divergences":
        content["items"]["divergences"] = []
    elif tamper == "divergences_empty":
        content["items"]["divergences"] = {
            "status": "present",
            "value": [],
        }
    elif tamper == "divergences_absent_value":
        content["items"]["divergences"] = {"status": "absent", "value": []}
    elif tamper == "divergences_not_assessed_value":
        content["items"]["divergences"] = {
            "status": "not_assessed",
            "value": [],
        }
    elif tamper == "pendencies":
        content["items"]["pendencies"] = []
    elif tamper == "pendencies_empty":
        content["items"]["pendencies"] = {"status": "present", "value": []}
    else:
        content["items"]["pendencies"] = {"status": "absent", "value": []}
        content["verdict"] = "consistent"
    report_path.write_text(json.dumps(content))
    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)
    assert info.value.code == PROFILE_REPOSITORY_INVALID
    assert not (records / "changes" / "c1" / "report" / "2.json").exists()


@pytest.mark.parametrize("tamper", ["non_bool", "extra"])
def test_tampered_snapshot_criteria_is_repository_invalid(
    tmp_path: Path, tamper: str
) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    snapshot_path = records / f"revisions/{revision}/snapshot.json"
    snapshot = json.loads(snapshot_path.read_text())
    if tamper == "non_bool":
        snapshot["criteria"][0]["blocking"] = "yes"
    else:
        snapshot["criteria"][0]["extra"] = True
    snapshot_path.write_text(json.dumps(snapshot))
    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)
    assert info.value.code == PROFILE_REPOSITORY_INVALID
    assert not (records / "changes" / "c1" / "report").exists()


def test_deeply_nested_report_record_is_repository_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    first = profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    report_dir = records / "changes" / "c1" / "report"
    (report_dir / "2.json").write_bytes(b"[" * 100000)
    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)
    assert info.value.code == PROFILE_REPOSITORY_INVALID
    assert not (report_dir / "3.json").exists()
    with pytest.raises(ProfileError) as info:
        profile_read_report(str(repo), "c1")
    assert info.value.code == PROFILE_REPOSITORY_INVALID
    assert (records / first["report"]).exists()


def test_deeply_nested_evidence_is_unrecorded_without_recursion_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    records = records_root(repo, "records/profile-dev")
    evidence_dir = records / f"changes/c1/revisions/{revision}/attempts/1/evidence"
    tampered = next(evidence_dir.glob("*.json"))
    tampered.write_bytes(b"[" * 100000)
    result = profile_record_report(str(repo), "c1", revision)
    report = json.loads((records / result["report"]).read_text())
    assert any(
        item["reason"] == "evidence_unrecorded"
        for item in report["items"]["pendencies"]["value"]
    )


def _prepare_next_revision(repo: Path, base: str) -> str:
    (repo / "src" / "api.py").write_text("x = 3\n")
    revision = commit_all(repo, "next revision")
    profile_record_change(str(repo), "c1", base, revision)
    profile_bind_inventory(str(repo), revision, "v1")
    profile_derive_impact(str(repo), "c1", revision)
    return revision


def test_current_finding_is_still_divergent_in_reverification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base, first_revision = _prepare(tmp_path)
    _run_results(repo, first_revision, monkeypatch, _review_divergence_output())
    profile_record_report(str(repo), "c1", first_revision)
    second_revision = _prepare_next_revision(repo, base)
    _run_results(repo, second_revision, monkeypatch, _review_divergence_output())
    result = profile_record_report(str(repo), "c1", second_revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )
    assert report["reverification"]["links"][0]["result"] == "still_divergent"
    assert report["verdict"] == "has pendency"
    assert any(
        item["reason"] == "finding_unclassified"
        for item in report["items"]["pendencies"]["value"]
    )
    assert not any(
        item["reason"] == "earlier_finding_not_reverified"
        for item in report["items"]["pendencies"]["value"]
    )


def test_indeterminate_current_review_is_not_reverified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base, first_revision = _prepare(tmp_path)
    _run_results(repo, first_revision, monkeypatch, _review_divergence_output())
    profile_record_report(str(repo), "c1", first_revision)
    second_revision = _prepare_next_revision(repo, base)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("git", "status", "--porcelain"),))
    attempt = profile_open_attempt(str(repo), "c1", second_revision)["attempt"]
    profile_run_gate(str(repo), "c1", second_revision, attempt)
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: FakeReviewAdapter("timeout"),
    )
    asyncio.run(profile_run_review(str(repo), "c1", second_revision, attempt))
    profile_capture_evidence(str(repo), "c1", second_revision, attempt)
    result = profile_record_report(str(repo), "c1", second_revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )
    assert report["reverification"]["links"][0]["result"] == "not_reverified"
    assert report["reverification"]["links"][0]["reason"] == "indeterminate"
    assert any(
        item["reason"] == "earlier_finding_not_reverified"
        for item in report["items"]["pendencies"]["value"]
    )


def test_rerun_at_earlier_revision_does_not_clear_its_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base, first_revision = _prepare(tmp_path)
    _run_results(repo, first_revision, monkeypatch, _review_divergence_output())
    profile_record_report(str(repo), "c1", first_revision)
    _run_results(repo, first_revision, monkeypatch)
    profile_record_report(str(repo), "c1", first_revision)
    second_revision = _prepare_next_revision(repo, base)
    _run_results(repo, second_revision, monkeypatch)
    result = profile_record_report(str(repo), "c1", second_revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )
    assert report["reverification"]["earlier_revision"] == first_revision
    assert report["reverification"]["links"]
    assert all(
        link["result"] == "resolved" for link in report["reverification"]["links"]
    )


def test_rerun_at_current_revision_keeps_the_earlier_reverification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base, first_revision = _prepare(tmp_path)
    _run_results(repo, first_revision, monkeypatch, _review_divergence_output())
    profile_record_report(str(repo), "c1", first_revision)
    second_revision = _prepare_next_revision(repo, base)
    _run_results(repo, second_revision, monkeypatch)
    profile_record_report(str(repo), "c1", second_revision)
    _run_results(repo, second_revision, monkeypatch)
    result = profile_record_report(str(repo), "c1", second_revision)
    report = json.loads(
        (records_root(repo, "records/profile-dev") / result["report"]).read_text()
    )
    assert report["reverification"]["earlier_revision"] == first_revision
    assert report["reverification"]["links"]
    assert all(
        link["result"] == "resolved" for link in report["reverification"]["links"]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_reverification",
        "earlier_revision_not_sha",
        "earlier_revision_same_revision",
        "empty_links",
        "wrong_link_keys",
        "bad_report_ref",
        "negative_finding_index",
        "boolean_finding_index",
        "unknown_result",
        "reason_result_mismatch",
        "outside_scope_with_state",
        "resolved_with_wrong_state",
        "resolved_without_requirement_association",
        "unknown_state_value",
        "non_requirement_link_not_outside_scope",
        "outside_scope_partial_constituents",
        "not_applicable_extra_keys",
    ],
)
def test_malformed_schema_four_reverification_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    first = profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    report_path = records / first["report"]
    content = json.loads(report_path.read_text())
    link = {
        "report_ref": "changes/c1/report/1.json",
        "finding_index": 0,
        "association": "requirement",
        "class": "gate-unit",
        "affected_point": "api",
        "criterion": "tests-pass",
        "kind": "gate",
        "state": "no_divergence",
        "result": "resolved",
        "reason": None,
    }
    reverification = {
        "status": "recorded",
        "earlier_revision": "b" * 40,
        "links": [link],
    }
    if mutation == "missing_reverification":
        del content["reverification"]
    elif mutation == "earlier_revision_not_sha":
        reverification["earlier_revision"] = "not-a-sha"
        content["reverification"] = reverification
    elif mutation == "earlier_revision_same_revision":
        reverification["earlier_revision"] = revision
        content["reverification"] = reverification
    elif mutation == "empty_links":
        reverification["links"] = []
        content["reverification"] = reverification
    elif mutation == "wrong_link_keys":
        del link["reason"]
        content["reverification"] = reverification
    elif mutation == "bad_report_ref":
        link["report_ref"] = "changes/other/report/1.json"
        content["reverification"] = reverification
    elif mutation == "negative_finding_index":
        link["finding_index"] = -1
        content["reverification"] = reverification
    elif mutation == "boolean_finding_index":
        link["finding_index"] = True
        content["reverification"] = reverification
    elif mutation == "unknown_result":
        link["result"] = "unknown"
        content["reverification"] = reverification
    elif mutation == "reason_result_mismatch":
        link["reason"] = "indeterminate"
        content["reverification"] = reverification
    elif mutation == "outside_scope_with_state":
        link["result"] = "not_reverified"
        link["reason"] = "outside_scope"
        link["state"] = "indeterminate"
        content["reverification"] = reverification
    elif mutation == "resolved_with_wrong_state":
        link["state"] = "divergent"
        content["reverification"] = reverification
    elif mutation == "resolved_without_requirement_association":
        link.update(
            association=None,
            **{"class": None, "affected_point": None, "criterion": None, "kind": None},
        )
        content["reverification"] = reverification
    elif mutation == "unknown_state_value":
        link.update(result="still_divergent", state="banana")
        content["reverification"] = reverification
    elif mutation == "non_requirement_link_not_outside_scope":
        link.update(
            association="unknown",
            state=None,
            result="not_reverified",
            reason="indeterminate",
            **{"class": None, "affected_point": None, "criterion": None, "kind": None},
        )
        content["reverification"] = reverification
    elif mutation == "outside_scope_partial_constituents":
        link.update(
            state=None,
            result="not_reverified",
            reason="outside_scope",
            criterion=None,
        )
        content["reverification"] = reverification
    else:
        content["reverification"] = {"status": "not_applicable", "extra": True}
    report_path.write_text(json.dumps(content))
    before = report_path.read_bytes()

    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)

    assert info.value.code == PROFILE_REPOSITORY_INVALID
    assert report_path.read_bytes() == before
    assert not (records / "changes" / "c1" / "report" / "2.json").exists()


def test_valid_schema_three_is_preserved_and_accepted_as_earlier_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base, first_revision = _prepare(tmp_path)
    _run_results(repo, first_revision, monkeypatch, _review_divergence_output())
    first = profile_record_report(str(repo), "c1", first_revision)
    records = records_root(repo, "records/profile-dev")
    first_path = records / first["report"]
    content = json.loads(first_path.read_text())
    content["schema"] = "profile-dev/verification-report/3"
    del content["reverification"]
    raw = json.dumps(content, separators=(",", ":")).encode()
    first_path.write_bytes(raw)

    second_revision = _prepare_next_revision(repo, base)
    _run_results(repo, second_revision, monkeypatch)
    second = profile_record_report(str(repo), "c1", second_revision)
    result = profile_read_report(str(repo), "c1")

    assert first_path.read_bytes() == raw
    assert result["history"][0]["content"] == content
    report = json.loads((records / second["report"]).read_text())
    assert report["schema"] == "profile-dev/verification-report/4"
    assert report["reverification"]["earlier_revision"] == first_revision
    assert report["reverification"]["links"][0]["result"] == "resolved"


def test_malformed_schema_three_is_rejected_before_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, revision = _prepare(tmp_path)
    _run_results(repo, revision, monkeypatch)
    first = profile_record_report(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    report_path = records / first["report"]
    content = json.loads(report_path.read_text())
    content["schema"] = "profile-dev/verification-report/3"
    content.pop("reverification")
    content["verdict"] = "maybe"
    report_path.write_text(json.dumps(content))
    before = report_path.read_bytes()

    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)

    assert info.value.code == PROFILE_REPOSITORY_INVALID
    assert report_path.read_bytes() == before
    assert not (records / "changes" / "c1" / "report" / "2.json").exists()


def test_unbound_scope_precedes_malformed_report_history(tmp_path: Path) -> None:
    repo, _, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    impact = records / f"changes/c1/revisions/{revision}/impact.json"
    impact.unlink()
    report_dir = records / "changes" / "c1" / "report"
    report_dir.mkdir()
    (report_dir / "1.json").write_text("not json")

    with pytest.raises(ProfileError) as info:
        profile_record_report(str(repo), "c1", revision)

    assert info.value.code == PROFILE_IMPACT_UNBOUND


@pytest.mark.parametrize("consistent", [False, True])
def test_record_report_result_shape_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consistent: bool
) -> None:
    repo, _, revision = _prepare(tmp_path)
    if consistent:
        attempt = _run_results(repo, revision, monkeypatch)
        expected_attempt = attempt
        expected_attempt_state = "valid"
        expected_verdict = "consistent"
    else:
        expected_attempt = None
        expected_attempt_state = "none"
        expected_verdict = "has pendency"

    assert profile_record_report(str(repo), "c1", revision) == {
        "ok": True,
        "change_id": "c1",
        "revision": revision,
        "record": 1,
        "report": "changes/c1/report/1.json",
        "attempt": expected_attempt,
        "attempt_state": expected_attempt_state,
        "verdict": expected_verdict,
        "reverification": "not_applicable",
    }
