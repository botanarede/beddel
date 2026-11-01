"""Story 3.3 VerificationAttempt scope tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from beddel_profile_dev import _adapters
from beddel_profile_dev import config as cfg
from beddel_profile_dev._errors import (
    PROFILE_ATTEMPT_CONFLICT,
    PROFILE_ATTEMPT_UNSCOPED,
    PROFILE_GATE_UNSCOPED,
    PROFILE_REVIEW_UNSCOPED,
    ProfileError,
)
from beddel_profile_dev._io import records_root
from beddel_profile_dev.tools import attempt as attempt_module
from beddel_profile_dev.tools.attempt import profile_open_attempt
from beddel_profile_dev.tools.bind import profile_bind_inventory
from beddel_profile_dev.tools.change import profile_record_change
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


def test_attempt_scope_is_immutable_and_ordinals_are_strictly_increasing(
    tmp_path: Path,
) -> None:
    repo, revision = _prepare(tmp_path)
    first = profile_open_attempt(str(repo), "c1", revision)
    records = records_root(repo, "records/profile-dev")
    first_path = records / first["attempt_ref"]
    first_bytes = first_path.read_bytes()
    second = profile_open_attempt(str(repo), "c1", revision)
    assert (first["attempt"], second["attempt"]) == (1, 2)
    assert first_path.read_bytes() == first_bytes
    data = json.loads(first_bytes)
    assert set(data) == {
        "schema",
        "attempt",
        "change_id",
        "base",
        "revision",
        "inventory_version",
        "inventory_sha256",
        "snapshot_ref",
        "snapshot_sha256",
        "impact_ref",
        "impact_sha256",
        "requirements",
    }
    assert data["schema"] == "profile-dev/verification-attempt/1"
    assert data["requirements"] == sorted(
        data["requirements"],
        key=lambda item: (item["class"], item["affected_point"], item["criterion"]),
    )


def test_attempt_ordinal_scan_ignores_non_ascii_digits(tmp_path: Path) -> None:
    repo, revision = _prepare(tmp_path)
    records = records_root(repo, "records/profile-dev")
    attempts = records / f"changes/c1/revisions/{revision}/attempts"
    attempts.mkdir(parents=True)
    (attempts / "²").mkdir()
    result = profile_open_attempt(str(repo), "c1", revision)
    assert result["attempt"] == 1


def test_attempt_hashes_the_single_read_of_impact_and_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, revision = _prepare(tmp_path)
    original = attempt_module.read_confined
    reads: list[str] = []

    def counted(root: Path, relative: str) -> bytes | None:
        if relative.endswith(("/impact.json", "/snapshot.json")):
            reads.append(relative)
        return original(root, relative)

    monkeypatch.setattr(attempt_module, "read_confined", counted)
    profile_open_attempt(str(repo), "c1", revision)
    assert sum(relative.endswith("/impact.json") for relative in reads) == 1
    assert sum(relative.endswith("/snapshot.json") for relative in reads) == 1


def test_attempt_without_impact_claims_no_ordinal(tmp_path: Path) -> None:
    repo, _base, revision = change_fixture(tmp_path)
    with pytest.raises(ProfileError) as info:
        profile_open_attempt(str(repo), "c1", revision)
    assert info.value.code == PROFILE_ATTEMPT_UNSCOPED
    records = records_root(repo, "records/profile-dev")
    assert not (records / f"changes/c1/revisions/{revision}/attempts").exists()


def test_wrong_attempt_is_unscoped_and_gate_outcome_cannot_be_rebound(
    tmp_path: Path, monkeypatch
) -> None:
    repo, revision = _prepare(tmp_path)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("git", "status", "--porcelain"),))
    attempt = profile_open_attempt(str(repo), "c1", revision)["attempt"]
    with pytest.raises(ProfileError) as wrong:
        profile_run_gate(str(repo), "c1", revision, attempt + 1)
    assert wrong.value.code == PROFILE_GATE_UNSCOPED
    profile_run_gate(str(repo), "c1", revision, attempt)
    output = records_root(repo, "records/profile-dev") / (
        f"changes/c1/revisions/{revision}/gate-output"
    )
    before = sorted(path.name for path in output.iterdir())
    with pytest.raises(ProfileError) as conflict:
        profile_run_gate(str(repo), "c1", revision, attempt)
    assert conflict.value.code == PROFILE_ATTEMPT_CONFLICT
    assert sorted(path.name for path in output.iterdir()) == before


def test_wrong_review_attempt_is_unscoped_and_bound_review_conflicts(
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
    with pytest.raises(ProfileError) as wrong:
        asyncio.run(profile_run_review(str(repo), "c1", revision, attempt + 1))
    assert wrong.value.code == PROFILE_REVIEW_UNSCOPED
    asyncio.run(profile_run_review(str(repo), "c1", revision, attempt))
    calls = len(fake.calls)
    output = records_root(repo, "records/profile-dev") / (
        f"changes/c1/revisions/{revision}/review-output"
    )
    before = sorted(path.name for path in output.iterdir())
    with pytest.raises(ProfileError) as conflict:
        asyncio.run(profile_run_review(str(repo), "c1", revision, attempt))
    assert conflict.value.code == PROFILE_ATTEMPT_CONFLICT
    assert len(fake.calls) == calls
    assert sorted(path.name for path in output.iterdir()) == before


def test_rerun_appends_a_new_attempt_and_leaves_the_previous_one_byte_identical(
    tmp_path: Path, monkeypatch
) -> None:
    from beddel_profile_dev.tools.evidence import profile_capture_evidence

    repo, revision = _prepare(tmp_path)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("git", "status", "--porcelain"),))
    fake = FakeReviewAdapter(output="review result\n")
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: fake,
    )
    attempts = (
        records_root(repo, "records/profile-dev")
        / f"changes/c1/revisions/{revision}/attempts"
    )

    def run_full_attempt() -> int:
        number = profile_open_attempt(str(repo), "c1", revision)["attempt"]
        profile_run_gate(str(repo), "c1", revision, number)
        asyncio.run(profile_run_review(str(repo), "c1", revision, number))
        profile_capture_evidence(str(repo), "c1", revision, number)
        return number

    def snapshot(number: int) -> dict[str, bytes]:
        root = attempts / str(number)
        return {
            str(path.relative_to(root)): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    assert run_full_attempt() == 1
    first = snapshot(1)
    assert any(name.startswith("evidence/") for name in first)
    assert run_full_attempt() == 2
    assert snapshot(1) == first
    second = snapshot(2)
    assert any(name.startswith("evidence/") for name in second)
    assert {"attempt.json", "gate.json", "review.json"} <= set(second)
