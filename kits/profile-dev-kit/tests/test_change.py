"""AC1, AC2, AC11: the Change record, the Analyzed revision link and the footprint."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from beddel_profile_dev._errors import (
    PROFILE_CHANGE_CONFLICT,
    PROFILE_CHANGE_INVALID,
    PROFILE_REPOSITORY_INVALID,
    ProfileError,
)
from beddel_profile_dev._io import footprint, in_head_history, is_ancestor
from beddel_profile_dev.tools.change import profile_record_change

from ._helpers import change_fixture, commit_all, git, init_repo

CHANGES = ".beddel-profile/records/changes"


def _fails(repo: Path, change_id: str, base: str, rev: str) -> ProfileError:
    with pytest.raises(ProfileError) as info:
        profile_record_change(str(repo), change_id, base, rev)
    return info.value


def test_writes_exactly_the_change_and_the_revision_link(tmp_path: Path) -> None:
    repo, base, rev = change_fixture(tmp_path)
    result = profile_record_change(str(repo), "c1", "HEAD~1", "HEAD")
    assert result["ok"] is True
    change = json.loads((repo / CHANGES / "c1" / "change.json").read_text())
    link = json.loads(
        (repo / CHANGES / "c1" / "revisions" / rev / "revision.json").read_text()
    )
    assert change == {"schema": "profile-dev/change/1", "change_id": "c1", "base": base}
    assert link == {
        "schema": "profile-dev/change-revision/1",
        "change_id": "c1",
        "base": base,
        "revision": rev,
    }


def test_rerun_is_idempotent_and_byte_identical(tmp_path: Path) -> None:
    repo, base, rev = change_fixture(tmp_path)
    profile_record_change(str(repo), "c1", base, rev)
    files = sorted(p for p in (repo / CHANGES).rglob("*") if p.is_file())
    before = [p.read_bytes() for p in files]
    profile_record_change(str(repo), "c1", base, rev)
    assert [p.read_bytes() for p in files] == before


def test_a_second_revision_of_the_same_change_adds_a_link(tmp_path: Path) -> None:
    repo, base, first = change_fixture(tmp_path)
    (repo / "src" / "api.py").write_text("x = 3\n")
    second = commit_all(repo, "more")
    profile_record_change(str(repo), "c1", base, first)
    profile_record_change(str(repo), "c1", base, second)
    revisions = sorted(p.name for p in (repo / CHANGES / "c1" / "revisions").iterdir())
    assert revisions == sorted([first, second])


def test_another_base_for_a_recorded_change_conflicts_and_writes_nothing(
    tmp_path: Path,
) -> None:
    repo, base, rev = change_fixture(tmp_path)
    profile_record_change(str(repo), "c1", base, rev)
    (repo / "src" / "api.py").write_text("x = 3\n")
    later = commit_all(repo, "later")
    before = sorted(str(p) for p in (repo / CHANGES).rglob("*"))
    err = _fails(repo, "c1", rev, later)
    assert err.code == PROFILE_CHANGE_CONFLICT
    assert sorted(str(p) for p in (repo / CHANGES).rglob("*")) == before


def test_a_stored_link_that_differs_conflicts(tmp_path: Path) -> None:
    repo, base, rev = change_fixture(tmp_path)
    profile_record_change(str(repo), "c1", base, rev)
    link = repo / CHANGES / "c1" / "revisions" / rev / "revision.json"
    link.write_text("{}\n")
    assert _fails(repo, "c1", base, rev).code == PROFILE_CHANGE_CONFLICT


@pytest.mark.parametrize("change_id", ["", "Bad Id", "../x", "-a", "a" * 65])
def test_invalid_change_id_is_refused(tmp_path: Path, change_id: str) -> None:
    repo, base, rev = change_fixture(tmp_path)
    assert _fails(repo, change_id, base, rev).code == PROFILE_CHANGE_INVALID
    assert not (repo / CHANGES).exists()


def test_base_that_is_not_an_ancestor_is_refused(tmp_path: Path) -> None:
    repo, base, rev = change_fixture(tmp_path)
    assert _fails(repo, "c1", rev, base).code == PROFILE_CHANGE_INVALID
    git(repo, "checkout", "-q", "-b", "side", base)
    (repo / "side.txt").write_text("s\n")
    side = commit_all(repo, "side")
    assert _fails(repo, "c1", side, rev).code == PROFILE_CHANGE_INVALID
    assert not (repo / CHANGES).exists()


def test_unresolvable_revision_or_base_fails_closed(tmp_path: Path) -> None:
    repo, base, rev = change_fixture(tmp_path)
    assert _fails(repo, "c1", "nope", rev).code == PROFILE_CHANGE_INVALID
    assert _fails(repo, "c1", base, "--oops").code == PROFILE_REPOSITORY_INVALID


def test_equal_base_and_revision_is_valid_with_an_empty_footprint(
    tmp_path: Path,
) -> None:
    repo, _, rev = change_fixture(tmp_path)
    profile_record_change(str(repo), "c1", rev, rev)
    assert footprint(repo, rev, rev) == []


def test_symlinked_changes_dir_escaping_the_repo_is_refused(tmp_path: Path) -> None:
    repo, base, rev = change_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    records = repo / ".beddel-profile" / "records"
    records.mkdir(parents=True)
    os.symlink(outside, records / "changes")
    assert _fails(repo, "c1", base, rev).code == PROFILE_REPOSITORY_INVALID
    assert list(outside.iterdir()) == []


# --- footprint (AC2) ---------------------------------------------------------


def test_footprint_covers_rename_delete_mode_change_and_non_utf8(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "keep.txt").write_text("k\n")
    (repo / "old.txt").write_text("a long enough body for rename detection\n" * 5)
    (repo / "gone.txt").write_text("g\n")
    (repo / "exe.sh").write_text("#!/bin/sh\n")
    base = commit_all(repo, "base")
    git(repo, "mv", "old.txt", "new.txt")
    (repo / "gone.txt").unlink()
    (repo / "exe.sh").chmod(0o755)
    git(repo, "update-index", "--chmod=+x", "exe.sh")
    raw = os.fsencode(repo) + b"/caf\xe9.txt"
    with open(raw, "wb") as handle:
        handle.write(b"x\n")
    rev = commit_all(repo, "change")
    paths = footprint(repo, base, rev)
    assert paths == sorted(paths) and len(paths) == len(set(paths))
    assert {"old.txt", "new.txt", "gone.txt", "exe.sh"} <= set(paths)
    assert "keep.txt" not in paths
    assert os.fsdecode(b"caf\xe9.txt") in paths


def test_footprint_counts_a_submodule_pointer_change(tmp_path: Path) -> None:
    sub = init_repo(tmp_path / "sub")
    (sub / "f").write_text("1\n")
    first = commit_all(sub, "one")
    repo = init_repo(tmp_path / "repo")
    git(repo, "-c", "protocol.file.allow=always", "submodule", "add", str(sub), "mod")
    base = commit_all(repo, "base")
    (sub / "f").write_text("2\n")
    second = commit_all(sub, "two")
    git(repo / "mod", "-c", "protocol.file.allow=always", "fetch", "-q")
    git(repo / "mod", "checkout", "-q", second)
    rev = commit_all(repo, "bump")
    assert first != second
    assert footprint(repo, base, rev) == ["mod"]


def test_footprint_ignores_uncommitted_edits_and_untracked_files(
    tmp_path: Path,
) -> None:
    repo, base, rev = change_fixture(
        tmp_path, lambda r: (r / "a.txt").write_text("a\n")
    )
    (repo / "src" / "api.py").write_text("dirty\n")
    (repo / "untracked.txt").write_text("u\n")
    assert footprint(repo, base, rev) == ["a.txt"]


def test_footprint_git_failure_is_an_error_never_empty(tmp_path: Path) -> None:
    repo, base, _ = change_fixture(tmp_path)
    with pytest.raises(ProfileError) as info:
        footprint(repo, base, "0" * 40)
    assert info.value.code == PROFILE_REPOSITORY_INVALID


@pytest.mark.parametrize("bad", ["--output=x", "HEAD~1", "HEAD", "abc", ""])
def test_footprint_and_ancestry_accept_only_full_shas(tmp_path: Path, bad: str) -> None:
    repo, base, rev = change_fixture(tmp_path)
    for args in ((bad, rev), (base, bad)):
        with pytest.raises(ProfileError):
            footprint(repo, *args)
        with pytest.raises(ProfileError):
            is_ancestor(repo, *args)


def test_submodule_ignore_configuration_cannot_hide_a_pointer_change(
    tmp_path: Path,
) -> None:
    sub = init_repo(tmp_path / "sub")
    (sub / "f").write_text("1\n")
    commit_all(sub, "one")
    repo = init_repo(tmp_path / "repo")
    git(repo, "-c", "protocol.file.allow=always", "submodule", "add", str(sub), "mod")
    base = commit_all(repo, "base")
    (sub / "f").write_text("2\n")
    second = commit_all(sub, "two")
    git(repo / "mod", "-c", "protocol.file.allow=always", "fetch", "-q")
    git(repo / "mod", "checkout", "-q", second)
    rev = commit_all(repo, "bump")
    with open(repo / ".gitmodules", "a", encoding="utf-8") as handle:
        handle.write("\tignore = all\n")  # uncommitted work-tree edit
    git(repo, "config", "submodule.mod.ignore", "all")
    git(repo, "config", "diff.ignoreSubmodules", "all")
    assert footprint(repo, base, rev) == ["mod"]


def test_a_broken_head_ref_is_not_an_unborn_head(tmp_path: Path) -> None:
    repo, _, _ = change_fixture(tmp_path)
    branch = git(repo, "symbolic-ref", "HEAD").strip()
    (repo / ".git" / branch).write_text("not-a-sha\n")
    with pytest.raises(ProfileError) as info:
        in_head_history(repo, "x")
    assert info.value.code == PROFILE_REPOSITORY_INVALID


def test_unborn_head_has_no_history(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    assert in_head_history(repo, "x") is False
