"""Contract tests for the integration helpers and tool boundaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from beddel_profile_dev import integrate
from beddel_profile_dev.tools import integrate as tools

from ._helpers import commit_all, git, init_repo

STORY = "7-6-integrate-workflow-completes-only-after-approval"


def test_status_helpers_preserve_bytes_and_comments() -> None:
    data = b"  other: keep\n\t" + STORY.encode() + b": pending  # owner\nlast: keep\r\n"
    assert integrate.status_lines(data, STORY) == [1]
    assert integrate.status_value(data, STORY) == "pending"
    updated = integrate.set_status(data, STORY, "done")
    assert (
        updated
        == b"  other: keep\n\t" + STORY.encode() + b": done  # owner\nlast: keep\r\n"
    )
    assert integrate.set_status(data, "missing", "done") is None
    assert integrate.status_lines(data + STORY.encode() + b": another\n", STORY) == [
        1,
        3,
    ]
    assert (
        integrate.set_status(data + STORY.encode() + b": another\n", STORY, "done")
        is None
    )


def test_approved_paths_and_pointer_message() -> None:
    assert integrate.approved_only([".beddel-profile/approvals/c1/1.yaml"])
    assert integrate.approved_only([])
    assert not integrate.approved_only(["src/code.py"])
    subject, trailers = integrate.pointer_message(STORY, "packages/example", "a" * 40)
    assert subject == "chore: update packages/example pointer"
    assert trailers == f"Story-Key: {STORY}\nIntegrate-Merge: {'a' * 40}"


def test_prepare_rejects_bad_inputs_before_repository_access(tmp_path: Path) -> None:
    result = tools.profile_integrate_prepare(
        str(tmp_path / "missing"),
        "bad key!",
        "spec.md",
        "feature/work",
        "main",
        "origin",
        "c1",
        str(tmp_path / "parent"),
        "main",
        "status.yaml",
        "done",
    )
    assert result["outcome"] == "refused"
    assert result["reason"] == "story_key.invalid"


def test_reconcile_rejects_missing_fetch_and_forged_state(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "file").write_text("x\n")
    commit_all(repo)
    prior: dict[str, Any] = {
        "stage": "integrate",
        "phase": "land",
        "story_key": STORY,
        "change_id": "c1",
        "repo": str(repo),
        "branch": "feature/work",
        "base_branch": "main",
        "remote": "origin",
        "tip": git(repo, "rev-parse", "HEAD"),
        "refs": {},
        "outcome": None,
    }
    missing = tools.profile_integrate_reconcile(
        str(repo), STORY, "c1", "land", prior, None
    )
    assert missing["reason"] == "fetch.failed"
    forged = tools.profile_integrate_reconcile(
        str(repo), STORY, "other", "land", prior, {"ok": True}
    )
    assert forged["reason"] == "state.mismatch"


def test_settle_rejects_missing_prior(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    result = tools.profile_integrate_settle(str(repo), STORY, "c1", "pointer", None)
    assert result["outcome"] == "failed"
    assert result["reason"] == "pointer.failed"


@pytest.mark.parametrize("value", ["Done", "done now", "", "x" * 33])
def test_status_value_contract(value: str) -> None:
    assert integrate.STATUS_VALUE.fullmatch(value) is None
