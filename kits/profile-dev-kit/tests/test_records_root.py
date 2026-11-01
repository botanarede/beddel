"""Story 3.3 storage-root identity tests."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest
from beddel_profile_dev._errors import PROFILE_REPOSITORY_INVALID, ProfileError
from beddel_profile_dev._io import records_root, repository_key
from beddel_profile_dev.tools.change import profile_record_change

from ._helpers import change_fixture, commit_all, init_repo


def test_records_root_is_setup_relative_and_keyed_by_git_common_dir(
    tmp_path: Path, monkeypatch
) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "file.txt").write_text("x\n")
    commit_all(repo)
    worktree = tmp_path / "worktree"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", str(worktree), "HEAD"],
        check=True,
    )
    try:
        first = records_root(repo, "records/profile-dev")
        second = records_root(worktree, "records/profile-dev")
        assert first == second
        expected = hashlib.sha256(
            str(Path(os.path.realpath(repo / ".git"))).encode("utf-8")
        ).hexdigest()
        assert repository_key(repo) == expected
        assert (
            first
            == Path.home() / ".config" / "beddel" / "records/profile-dev" / expected
        )
        assert not (repo / ".beddel-profile" / "records").exists()
    finally:
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "remove", str(worktree)],
            check=True,
        )


def test_separate_clone_gets_a_different_key(tmp_path: Path) -> None:
    first = init_repo(tmp_path / "first")
    (first / "file.txt").write_text("x\n")
    commit_all(first)
    second = init_repo(tmp_path / "second")
    (second / "file.txt").write_text("x\n")
    commit_all(second)
    assert repository_key(first) != repository_key(second)


def test_legacy_repository_records_are_untouched_and_unread(tmp_path: Path) -> None:
    repo, base, revision = change_fixture(tmp_path)
    legacy = repo / ".beddel-profile" / "records" / "legacy.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"legacy\n")
    profile_record_change(str(repo), "c1", base, revision)
    assert legacy.read_bytes() == b"legacy\n"
    assert not (repo / ".beddel-profile" / "records" / "changes").exists()


def test_records_root_failure_modes_are_profile_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base, revision = change_fixture(tmp_path)

    def no_home() -> Path:
        raise RuntimeError("HOME unavailable")

    monkeypatch.setattr(Path, "home", no_home)
    with pytest.raises(ProfileError) as home_error:
        records_root(repo, "records/profile-dev")
    assert home_error.value.code == PROFILE_REPOSITORY_INVALID

    monkeypatch.undo()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    original_mkdir = Path.mkdir

    def no_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        raise OSError("setup unavailable")

    monkeypatch.setattr(Path, "mkdir", no_mkdir)
    with pytest.raises(ProfileError) as setup_error:
        profile_record_change(str(repo), "c1", base, revision)
    assert setup_error.value.code == PROFILE_REPOSITORY_INVALID
    monkeypatch.setattr(Path, "mkdir", original_mkdir)


def test_records_subdirectory_symlink_escaping_root_is_refused(
    tmp_path: Path,
) -> None:
    repo, base, revision = change_fixture(tmp_path)
    records = records_root(repo, "records/profile-dev")
    outside = tmp_path / "outside"
    outside.mkdir()
    records.mkdir(parents=True)
    (records / "changes").symlink_to(outside)
    with pytest.raises(ProfileError) as info:
        profile_record_change(str(repo), "c1", base, revision)
    assert info.value.code == PROFILE_REPOSITORY_INVALID
    assert list(outside.iterdir()) == []
