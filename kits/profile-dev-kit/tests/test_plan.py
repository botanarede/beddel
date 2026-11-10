"""Plan contract, reconciliation and settlement coverage."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from beddel_profile_dev._errors import PROFILE_PLAN_REFUSED, ProfileError
from beddel_profile_dev.plan import front_matter, relative_path, spec_complete
from beddel_profile_dev.tools.plan import profile_plan_reconcile, profile_plan_settle

from ._helpers import commit_all, init_repo

STORY = "7-3-plan-workflow-turns-one-story-into-one-spec"
STORY_PATH = "stories/story.md"
GUIDE_PATH = "guides/guide.md"
SPEC_PATH = "specs/7-3.md"


def complete_spec(story_key: str = STORY) -> bytes:
    return (
        f"---\nstory_key: {story_key}\nrequirements: [FR-13]\n"
        "repositories: [kits/profile-dev-kit]\ndependencies: []\n"
        "size_cap_bytes: 64000\n---\n\n# Implementation\n"
    ).encode()


def prepared_repo(tmp_path: Path) -> Path:
    repo = init_repo(tmp_path / "repo")
    (repo / "stories").mkdir()
    (repo / STORY_PATH).write_text("selected story")
    (repo / "guides").mkdir()
    (repo / GUIDE_PATH).write_text("guide")
    commit_all(repo)
    return repo


def call_reconcile(repo: Path, **kwargs: str) -> dict[str, object]:
    values = {
        "repo_path": str(repo),
        "story_key": STORY,
        "story_path": STORY_PATH,
        "guide_path": GUIDE_PATH,
        "spec_path": SPEC_PATH,
    }
    values.update(kwargs)
    return profile_plan_reconcile(**values)


def test_pure_contract() -> None:
    data = complete_spec()
    assert front_matter(data)["story_key"] == STORY
    assert spec_complete(data, STORY)
    assert not spec_complete(
        data.replace(b"size_cap_bytes: 64000", b"size_cap_bytes: 0"), STORY
    )
    assert relative_path(".", allow_dot=True)
    assert not relative_path(".")
    assert not relative_path("../outside")
    assert not relative_path("a\\b")


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("story_key", "BAD KEY", "story_key.invalid"),
        ("story_path", "../story.md", "path.invalid"),
    ],
)
def test_invalid_inputs_refuse(
    tmp_path: Path, field: str, value: str, reason: str
) -> None:
    repo = prepared_repo(tmp_path)
    with pytest.raises(ProfileError) as exc_info:
        call_reconcile(repo, **{field: value})
    assert exc_info.value.code == PROFILE_PLAN_REFUSED
    assert exc_info.value.details["reason"] == reason


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        ("story_absent", "story.absent"),
        ("guide_absent", "guide.absent"),
        ("spec_dir_absent", "spec_dir.absent"),
        ("cwd_mismatch", "cwd.mismatch"),
        ("worktree_dirty", "worktree.dirty"),
        ("spec_unreadable", "spec.unreadable"),
        ("spec_foreign", "spec.foreign"),
        ("spec_duplicate", "spec.duplicate"),
    ],
)
def test_refusal_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, reason: str
) -> None:
    root = prepared_repo(tmp_path)
    monkeypatch.chdir(root)
    if kind == "story_absent":
        (root / STORY_PATH).unlink()
    elif kind == "guide_absent":
        (root / GUIDE_PATH).unlink()
    elif kind == "spec_dir_absent":
        pass
    elif kind == "cwd_mismatch":
        (root / "specs").mkdir()
        monkeypatch.chdir(tmp_path)
    elif kind == "worktree_dirty":
        (root / "specs").mkdir()
        (root / "other.txt").write_text("outside spec")
    elif kind == "spec_unreadable":
        (root / "specs").mkdir()
        (root / SPEC_PATH).mkdir()
    elif kind == "spec_foreign":
        (root / "specs").mkdir()
        (root / SPEC_PATH).write_bytes(complete_spec("other-story"))
    elif kind == "spec_duplicate":
        (root / "specs").mkdir()
        (root / SPEC_PATH).write_bytes(complete_spec())
        (root / "specs" / "other.md").write_bytes(complete_spec())
        commit_all(root)
    with pytest.raises(ProfileError) as exc_info:
        call_reconcile(root)
    assert exc_info.value.code == PROFILE_PLAN_REFUSED
    assert exc_info.value.details["reason"] == reason


def test_create_reconcile_reuse_and_settle_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = prepared_repo(tmp_path)
    (repo / "specs").mkdir()
    monkeypatch.chdir(repo)

    absent = call_reconcile(repo)
    assert absent["state"] == "absent"
    assert absent["author"] is True
    (repo / SPEC_PATH).write_bytes(complete_spec())
    created = profile_plan_settle(
        str(repo), STORY, STORY_PATH, GUIDE_PATH, SPEC_PATH, absent
    )
    assert created["outcome"] == "succeeded"
    assert created["reason"] == "spec.created"
    assert created["refs"]["spec_sha256"] == hashlib.sha256(complete_spec()).hexdigest()

    incomplete_bytes = b"---\nstory_key: " + STORY.encode() + b"\n---\nunfinished\n"
    (repo / SPEC_PATH).write_bytes(incomplete_bytes)
    incomplete = call_reconcile(repo)
    assert incomplete["state"] == "incomplete"
    (repo / SPEC_PATH).write_bytes(complete_spec())
    reconciled = profile_plan_settle(
        str(repo), STORY, STORY_PATH, GUIDE_PATH, SPEC_PATH, incomplete
    )
    assert reconciled["reason"] == "spec.reconciled"

    reused_before = (repo / SPEC_PATH).read_bytes()
    reused = call_reconcile(repo)
    reused_result = profile_plan_settle(
        str(repo), STORY, STORY_PATH, GUIDE_PATH, SPEC_PATH, reused
    )
    assert reused_result["reason"] == "spec.reused"
    assert (repo / SPEC_PATH).read_bytes() == reused_before


def test_settle_scope_commit_changed_and_agent_failure_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = prepared_repo(tmp_path)
    (repo / "specs").mkdir()
    monkeypatch.chdir(repo)
    absent = call_reconcile(repo)
    (repo / SPEC_PATH).write_bytes(complete_spec())
    (repo / "extra.txt").write_text("scope")
    scope = profile_plan_settle(
        str(repo), STORY, STORY_PATH, GUIDE_PATH, SPEC_PATH, absent
    )
    assert scope["reason"] == "scope.exceeded"
    assert scope["refs"]["out_of_scope"] == 1

    (repo / "extra.txt").unlink()
    commit_all(repo, "agent commit")
    moved = profile_plan_settle(
        str(repo), STORY, STORY_PATH, GUIDE_PATH, SPEC_PATH, absent
    )
    assert moved["reason"] == "head.moved"

    repo2 = prepared_repo(tmp_path / "second")
    (repo2 / "specs").mkdir()
    (repo2 / SPEC_PATH).write_bytes(complete_spec())
    monkeypatch.chdir(repo2)
    complete = call_reconcile(repo2)
    (repo2 / SPEC_PATH).write_bytes(
        complete_spec().replace(b"# Implementation", b"# Changed")
    )
    changed = profile_plan_settle(
        str(repo2), STORY, STORY_PATH, GUIDE_PATH, SPEC_PATH, complete
    )
    assert changed["reason"] == "spec.changed"


def test_settle_without_reconcile_refuses_and_records_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = prepared_repo(tmp_path)
    monkeypatch.chdir(repo)
    result = profile_plan_settle(
        str(repo), STORY, STORY_PATH, GUIDE_PATH, SPEC_PATH, None
    )
    assert result["outcome"] == "refused"
    assert result["reason"] == "spec_dir.absent"
