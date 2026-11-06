"""Story 3.3 Evidence capture tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from beddel_profile_dev import _adapters
from beddel_profile_dev import config as cfg
from beddel_profile_dev._errors import (
    PROFILE_ATTEMPT_CONFLICT,
    PROFILE_ATTEMPT_UNSCOPED,
    ProfileError,
)
from beddel_profile_dev._io import records_root
from beddel_profile_dev.tools.attempt import profile_open_attempt
from beddel_profile_dev.tools.bind import profile_bind_inventory
from beddel_profile_dev.tools.change import profile_record_change
from beddel_profile_dev.tools.evidence import profile_capture_evidence
from beddel_profile_dev.tools.gate import profile_run_gate
from beddel_profile_dev.tools.impact import profile_derive_impact
from beddel_profile_dev.tools.review import profile_run_review

from ._helpers import FakeReviewAdapter, change_fixture


def _prepare(tmp_path: Path):
    repo, base, revision = change_fixture(
        tmp_path, lambda path: (path / "src" / "api.py").write_text("x = 2\n")
    )
    profile_record_change(str(repo), "c1", base, revision)
    profile_bind_inventory(str(repo), revision, "v1")
    profile_derive_impact(str(repo), "c1", revision)
    return repo, revision


def test_evidence_keeps_matching_gate_and_review_results_only(
    tmp_path: Path, monkeypatch
) -> None:
    repo, revision = _prepare(tmp_path)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("git", "status", "--porcelain"),))
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    profile_run_gate(str(repo), "c1", revision, attempt)
    fake = FakeReviewAdapter(output="review result\n")
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: fake,
    )
    asyncio.run(profile_run_review(str(repo), "c1", revision, attempt))
    result = profile_capture_evidence(str(repo), "c1", revision, attempt)
    assert result["evidence"] == 2
    records = records_root(repo, "records/profile-dev")
    evidence = list(
        (records / f"changes/c1/revisions/{revision}/attempts/{attempt}/evidence").glob(
            "*.json"
        )
    )
    assert len(evidence) == 2
    attempt_record = json.loads(
        (
            records / f"changes/c1/revisions/{revision}/attempts/1/attempt.json"
        ).read_text()
    )
    requirements = {
        (item["class"], item["affected_point"], item["criterion"]): item["kind"]
        for item in attempt_record["requirements"]
    }
    for path in evidence:
        data = json.loads(path.read_text())
        assert data["outcome_ref"]
        outcome_path = records / data["outcome_ref"]
        outcome_raw = outcome_path.read_bytes()
        outcome = json.loads(outcome_raw)
        assert data["outcome_sha256"] == hashlib.sha256(outcome_raw).hexdigest()
        identity = (data["class"], data["affected_point"], data["criterion"])
        assert data["kind"] == requirements[identity]
        assert data["outcome_ref"].endswith(f"/attempts/{attempt}/{data['kind']}.json")
        if data["kind"] == "gate":
            assert data["result"] == {
                "commands": outcome["commands"],
                "gate_ref": outcome["gate_ref"],
            }
        else:
            review_output = records / outcome["review_ref"]
            review_output_raw = review_output.read_bytes()
            assert data["result"] == {
                "agent": outcome["agent"],
                "model": outcome["model"],
                "review_ref": outcome["review_ref"],
                "review_sha256": hashlib.sha256(review_output_raw).hexdigest(),
            }
        assert data["schema"] == "profile-dev/evidence/1"
        assert set(data) == {
            "schema",
            "attempt",
            "change_id",
            "revision",
            "class",
            "affected_point",
            "criterion",
            "kind",
            "outcome_ref",
            "outcome_sha256",
            "result",
        }
        assert not set(data) & {
            "passed",
            "verdict",
            "classification",
            "finding",
            "pendency",
            "approval",
        }


def test_evidence_rejects_outcome_with_wrong_inventory_identity(
    tmp_path: Path, monkeypatch
) -> None:
    repo, revision = _prepare(tmp_path)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("git", "status", "--porcelain"),))
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    profile_run_gate(str(repo), "c1", revision, attempt)
    records = records_root(repo, "records/profile-dev")
    outcome_path = (
        records / f"changes/c1/revisions/{revision}/attempts/{attempt}/gate.json"
    )
    outcome = json.loads(outcome_path.read_text())
    outcome["inventory_version"] = "v9"
    outcome_path.write_text(json.dumps(outcome))
    with pytest.raises(ProfileError) as info:
        profile_capture_evidence(str(repo), "c1", revision, attempt)
    assert info.value.code == PROFILE_ATTEMPT_UNSCOPED
    assert not (outcome_path.parent / "evidence").exists()


def test_evidence_rejects_unknown_review_status(tmp_path: Path, monkeypatch) -> None:
    repo, revision = _prepare(tmp_path)
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    fake = FakeReviewAdapter(output="review\n")
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: fake,
    )
    asyncio.run(profile_run_review(str(repo), "c1", revision, attempt))
    records = records_root(repo, "records/profile-dev")
    outcome_path = (
        records / f"changes/c1/revisions/{revision}/attempts/{attempt}/review.json"
    )
    outcome = json.loads(outcome_path.read_text())
    outcome["status"] = "unknown"
    outcome_path.write_text(json.dumps(outcome))
    with pytest.raises(ProfileError) as info:
        profile_capture_evidence(str(repo), "c1", revision, attempt)
    assert info.value.code == PROFILE_ATTEMPT_UNSCOPED
    assert not (outcome_path.parent / "evidence").exists()


def test_evidence_rejects_missing_completed_review_output(
    tmp_path: Path, monkeypatch
) -> None:
    repo, revision = _prepare(tmp_path)
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    fake = FakeReviewAdapter(output="review\n")
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: fake,
    )
    asyncio.run(profile_run_review(str(repo), "c1", revision, attempt))
    records = records_root(repo, "records/profile-dev")
    outcome_path = (
        records / f"changes/c1/revisions/{revision}/attempts/{attempt}/review.json"
    )
    outcome = json.loads(outcome_path.read_text())
    (records / outcome["review_ref"]).unlink()
    with pytest.raises(ProfileError) as info:
        profile_capture_evidence(str(repo), "c1", revision, attempt)
    assert info.value.code == PROFILE_ATTEMPT_UNSCOPED
    assert not (outcome_path.parent / "evidence").exists()


def test_evidence_rejects_gate_commands_with_wrong_keys(
    tmp_path: Path, monkeypatch
) -> None:
    repo, revision = _prepare(tmp_path)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("git", "status", "--porcelain"),))
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    profile_run_gate(str(repo), "c1", revision, attempt)
    records = records_root(repo, "records/profile-dev")
    outcome_path = (
        records / f"changes/c1/revisions/{revision}/attempts/{attempt}/gate.json"
    )
    outcome = json.loads(outcome_path.read_text())
    outcome["commands"] = [{"name": "01-git"}]
    outcome_path.write_text(json.dumps(outcome))
    with pytest.raises(ProfileError) as info:
        profile_capture_evidence(str(repo), "c1", revision, attempt)
    assert info.value.code == PROFILE_ATTEMPT_UNSCOPED
    assert not (outcome_path.parent / "evidence").exists()


def test_missing_attempt_or_tampered_impact_writes_no_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    repo, revision = _prepare(tmp_path)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("git", "status", "--porcelain"),))
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    with pytest.raises(ProfileError) as missing:
        profile_capture_evidence(str(repo), "c1", revision, attempt + 1)
    assert missing.value.code == PROFILE_ATTEMPT_UNSCOPED
    records = records_root(repo, "records/profile-dev")
    evidence_dir = (
        records / f"changes/c1/revisions/{revision}/attempts/{attempt}/evidence"
    )
    assert not evidence_dir.exists()

    impact_path = records / f"changes/c1/revisions/{revision}/impact.json"
    impact = json.loads(impact_path.read_text())
    impact["inventory_version"] = "v9"
    impact_path.write_text(json.dumps(impact))
    with pytest.raises(ProfileError) as tampered:
        profile_capture_evidence(str(repo), "c1", revision, attempt)
    assert tampered.value.code == PROFILE_ATTEMPT_UNSCOPED
    assert not evidence_dir.exists()


def test_duplicate_requirement_constituents_claim_no_attempt(tmp_path: Path) -> None:
    repo, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    impact_path = records / f"changes/c1/revisions/{revision}/impact.json"
    impact = json.loads(impact_path.read_text())
    impact["required_evidence"].append(impact["required_evidence"][0].copy())
    impact_path.write_text(json.dumps(impact))
    with pytest.raises(ProfileError) as info:
        profile_open_attempt(str(repo), "c1", revision)
    assert info.value.code == PROFILE_ATTEMPT_UNSCOPED
    assert not (records / f"changes/c1/revisions/{revision}/attempts").exists()


@pytest.mark.parametrize(
    ("behavior", "output"),
    [("timeout", ""), ("error", ""), ("completed", "  \n")],
)
def test_indeterminate_or_blank_review_produces_no_review_evidence(
    tmp_path: Path, monkeypatch, behavior: str, output: str
) -> None:
    repo, revision = _prepare(tmp_path)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("git", "status", "--porcelain"),))
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    profile_run_gate(str(repo), "c1", revision, attempt)
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: FakeReviewAdapter(
            behavior, output=output
        ),
    )
    asyncio.run(profile_run_review(str(repo), "c1", revision, attempt))
    assert profile_capture_evidence(str(repo), "c1", revision, attempt)["evidence"] == 1
    evidence_dir = (
        records_root(repo, "records/profile-dev")
        / f"changes/c1/revisions/{revision}/attempts/{attempt}/evidence"
    )
    written = list(evidence_dir.glob("*.json"))
    assert len(written) == 1
    assert json.loads(written[0].read_text())["kind"] == "gate"


def test_evidence_recapture_is_idempotent_and_conflicts_on_different_bytes(
    tmp_path: Path, monkeypatch
) -> None:
    repo, revision = _prepare(tmp_path)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("git", "status", "--porcelain"),))
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    profile_run_gate(str(repo), "c1", revision, attempt)
    fake = FakeReviewAdapter(output="review result\n")
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: fake,
    )
    asyncio.run(profile_run_review(str(repo), "c1", revision, attempt))
    first = profile_capture_evidence(str(repo), "c1", revision, attempt)
    second = profile_capture_evidence(str(repo), "c1", revision, attempt)
    assert second == first
    records = records_root(repo, "records/profile-dev")
    evidence_dir = (
        records / f"changes/c1/revisions/{revision}/attempts/{attempt}/evidence"
    )
    evidence_path = next(evidence_dir.glob("*.json"))
    evidence_path.write_bytes(b"{}\n")
    before = {path.name: path.read_bytes() for path in evidence_dir.iterdir()}
    with pytest.raises(ProfileError) as info:
        profile_capture_evidence(str(repo), "c1", revision, attempt)
    assert getattr(info.value, "code", None) == PROFILE_ATTEMPT_CONFLICT
    # The refusal leaves the directory exactly as it was: nothing changed.
    after = {path.name: path.read_bytes() for path in evidence_dir.iterdir()}
    assert after == before
