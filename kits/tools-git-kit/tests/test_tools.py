"""Tests for tools-git-kit — all 10 typed async Git operations.

Uses real temporary git repos (no mocking of git).
"""

from __future__ import annotations

import pytest

from beddel_tools_git.tools import (
    GitToolError,
    _run_git,
    _run_git_checked,
    git_branch_create,
    git_branch_current,
    git_branch_delete,
    git_commit,
    git_diff_stat,
    git_fetch,
    git_merge,
    git_push,
    git_status,
    git_tag_create,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def git_repo(tmp_path: object) -> str:
    """Create a temporary git repo with an initial commit."""
    from pathlib import Path

    repo_path = str(tmp_path)
    await _run_git_checked("init", cwd=repo_path)
    await _run_git_checked("config", "user.email", "test@test.com", cwd=repo_path)
    await _run_git_checked("config", "user.name", "Test", cwd=repo_path)
    # Create initial commit
    readme = Path(repo_path) / "README.md"
    readme.write_text("# Test Repo\n")
    await _run_git_checked("add", "README.md", cwd=repo_path)
    await _run_git_checked("commit", "-m", "init", cwd=repo_path)
    return repo_path


@pytest.fixture
async def bare_remote(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Create a bare remote repo for push/fetch tests."""
    remote_path = str(tmp_path_factory.mktemp("bare"))
    await _run_git_checked("init", "--bare", cwd=remote_path)
    return remote_path


@pytest.fixture
async def git_repo_with_remote(
    git_repo: str, bare_remote: str
) -> tuple[str, str]:
    """Git repo with a configured remote pointing to bare repo."""
    await _run_git_checked(
        "remote", "add", "origin", bare_remote, cwd=git_repo
    )
    # Push initial commit to establish tracking
    await _run_git_checked(
        "push", "--set-upstream", "origin", "main", cwd=git_repo
    )
    return git_repo, bare_remote


# ---------------------------------------------------------------------------
# Test git_status
# ---------------------------------------------------------------------------


class TestGitStatus:
    async def test_clean_repo(self, git_repo: str) -> None:
        result = await git_status(cwd=git_repo)
        assert result["clean"] is True
        assert result["modified"] == []
        assert result["staged"] == []
        assert result["untracked"] == []

    async def test_dirty_repo_modified(self, git_repo: str) -> None:
        from pathlib import Path

        (Path(git_repo) / "README.md").write_text("modified content\n")
        result = await git_status(cwd=git_repo)
        assert result["clean"] is False
        assert "README.md" in result["modified"]

    async def test_dirty_repo_untracked(self, git_repo: str) -> None:
        from pathlib import Path

        (Path(git_repo) / "new_file.txt").write_text("new\n")
        result = await git_status(cwd=git_repo)
        assert result["clean"] is False
        assert "new_file.txt" in result["untracked"]

    async def test_staged_files(self, git_repo: str) -> None:
        from pathlib import Path

        (Path(git_repo) / "staged.txt").write_text("staged\n")
        await _run_git_checked("add", "staged.txt", cwd=git_repo)
        result = await git_status(cwd=git_repo)
        assert result["clean"] is False
        assert "staged.txt" in result["staged"]


# ---------------------------------------------------------------------------
# Test git_branch_create
# ---------------------------------------------------------------------------


class TestGitBranchCreate:
    async def test_create_valid_branch(self, git_repo: str) -> None:
        result = await git_branch_create(name="feature/test-branch", cwd=git_repo)
        assert result["branch"] == "feature/test-branch"
        assert result["created"] is True
        assert len(result["sha"]) == 40  # Full SHA

    async def test_create_from_specific_ref(self, git_repo: str) -> None:
        # Get current SHA
        sha_out = await _run_git_checked("rev-parse", "HEAD", cwd=git_repo)
        sha = sha_out.strip()
        result = await git_branch_create(
            name="from-sha", from_ref=sha, cwd=git_repo
        )
        assert result["sha"] == sha

    async def test_invalid_branch_name_spaces(self, git_repo: str) -> None:
        with pytest.raises(GitToolError, match="Invalid branch name"):
            await git_branch_create(name="bad branch name", cwd=git_repo)

    async def test_invalid_branch_name_special_chars(self, git_repo: str) -> None:
        with pytest.raises(GitToolError, match="Invalid branch name"):
            await git_branch_create(name="bad~branch", cwd=git_repo)


# ---------------------------------------------------------------------------
# Test git_branch_current
# ---------------------------------------------------------------------------


class TestGitBranchCurrent:
    async def test_on_branch(self, git_repo: str) -> None:
        result = await git_branch_current(cwd=git_repo)
        assert result["branch"] is not None
        assert result["detached"] is False
        assert len(result["sha"]) == 40

    async def test_detached_head(self, git_repo: str) -> None:
        sha_out = await _run_git_checked("rev-parse", "HEAD", cwd=git_repo)
        sha = sha_out.strip()
        await _run_git_checked("checkout", "--detach", cwd=git_repo)
        result = await git_branch_current(cwd=git_repo)
        assert result["branch"] is None
        assert result["detached"] is True
        assert result["sha"] == sha


# ---------------------------------------------------------------------------
# Test git_commit
# ---------------------------------------------------------------------------


class TestGitCommit:
    async def test_successful_commit(self, git_repo: str) -> None:
        from pathlib import Path

        (Path(git_repo) / "new.txt").write_text("content\n")
        result = await git_commit(
            files=["new.txt"], message="add new file", cwd=git_repo
        )
        assert result["files_staged"] == 1
        assert result["message"] == "add new file"
        assert len(result["sha"]) == 40

    async def test_multiple_files(self, git_repo: str) -> None:
        from pathlib import Path

        (Path(git_repo) / "a.txt").write_text("a\n")
        (Path(git_repo) / "b.txt").write_text("b\n")
        result = await git_commit(
            files=["a.txt", "b.txt"], message="add two files", cwd=git_repo
        )
        assert result["files_staged"] == 2

    async def test_empty_files_raises(self, git_repo: str) -> None:
        with pytest.raises(GitToolError, match="files list must not be empty"):
            await git_commit(files=[], message="empty", cwd=git_repo)

    async def test_empty_message_raises(self, git_repo: str) -> None:
        from pathlib import Path

        (Path(git_repo) / "x.txt").write_text("x\n")
        with pytest.raises(GitToolError, match="commit message must not be empty"):
            await git_commit(files=["x.txt"], message="", cwd=git_repo)


# ---------------------------------------------------------------------------
# Test git_push
# ---------------------------------------------------------------------------


class TestGitPush:
    async def test_push_to_remote(
        self, git_repo_with_remote: tuple[str, str]
    ) -> None:
        repo, _remote = git_repo_with_remote
        from pathlib import Path

        (Path(repo) / "push_test.txt").write_text("push\n")
        await _run_git_checked("add", "push_test.txt", cwd=repo)
        await _run_git_checked("commit", "-m", "push test", cwd=repo)

        result = await git_push(cwd=repo)
        assert result["pushed"] is True
        assert result["remote"] == "origin"

    async def test_push_set_upstream(
        self, git_repo_with_remote: tuple[str, str]
    ) -> None:
        repo, _remote = git_repo_with_remote
        await _run_git_checked("checkout", "-b", "new-branch", cwd=repo)
        from pathlib import Path

        (Path(repo) / "branch_file.txt").write_text("branch\n")
        await _run_git_checked("add", "branch_file.txt", cwd=repo)
        await _run_git_checked("commit", "-m", "branch commit", cwd=repo)

        result = await git_push(set_upstream=True, cwd=repo)
        assert result["pushed"] is True
        assert result["set_upstream"] is True
        assert result["branch"] == "new-branch"


# ---------------------------------------------------------------------------
# Test git_merge
# ---------------------------------------------------------------------------


class TestGitMerge:
    async def test_clean_merge(self, git_repo: str) -> None:
        from pathlib import Path

        # Create feature branch with changes
        await _run_git_checked("checkout", "-b", "feature", cwd=git_repo)
        (Path(git_repo) / "feature.txt").write_text("feature\n")
        await _run_git_checked("add", "feature.txt", cwd=git_repo)
        await _run_git_checked("commit", "-m", "feature commit", cwd=git_repo)

        # Switch back to main and merge
        await _run_git_checked("checkout", "main", cwd=git_repo)
        result = await git_merge(source_branch="feature", cwd=git_repo)
        assert result["merged"] is True
        assert result["source"] == "feature"
        assert result["conflicts"] is None
        assert result["merge_sha"] is not None

    async def test_conflict_merge(self, git_repo: str) -> None:
        from pathlib import Path

        # Create conflicting changes on two branches
        (Path(git_repo) / "README.md").write_text("main change\n")
        await _run_git_checked("add", "README.md", cwd=git_repo)
        await _run_git_checked("commit", "-m", "main edit", cwd=git_repo)

        await _run_git_checked("checkout", "-b", "conflict-branch", "HEAD~1", cwd=git_repo)
        (Path(git_repo) / "README.md").write_text("branch change\n")
        await _run_git_checked("add", "README.md", cwd=git_repo)
        await _run_git_checked("commit", "-m", "branch edit", cwd=git_repo)

        await _run_git_checked("checkout", "main", cwd=git_repo)
        result = await git_merge(source_branch="conflict-branch", cwd=git_repo)
        assert result["merged"] is False
        assert result["conflicts"] is not None
        assert "README.md" in result["conflicts"]


# ---------------------------------------------------------------------------
# Test git_diff_stat
# ---------------------------------------------------------------------------


class TestGitDiffStat:
    async def test_diff_between_refs(self, git_repo: str) -> None:
        from pathlib import Path

        # Record base SHA
        base_out = await _run_git_checked("rev-parse", "HEAD", cwd=git_repo)
        base = base_out.strip()

        # Make changes
        (Path(git_repo) / "diff_file.txt").write_text("line1\nline2\nline3\n")
        await _run_git_checked("add", "diff_file.txt", cwd=git_repo)
        await _run_git_checked("commit", "-m", "add diff file", cwd=git_repo)

        result = await git_diff_stat(base_ref=base, cwd=git_repo)
        assert result["files_changed"] >= 1
        assert result["insertions"] >= 3
        assert result["deletions"] >= 0
        assert any(f["path"] == "diff_file.txt" for f in result["files"])

    async def test_no_changes(self, git_repo: str) -> None:
        sha_out = await _run_git_checked("rev-parse", "HEAD", cwd=git_repo)
        sha = sha_out.strip()
        result = await git_diff_stat(base_ref=sha, head_ref=sha, cwd=git_repo)
        assert result["files_changed"] == 0
        assert result["insertions"] == 0
        assert result["deletions"] == 0


# ---------------------------------------------------------------------------
# Test git_fetch
# ---------------------------------------------------------------------------


class TestGitFetch:
    async def test_fetch_from_remote(
        self, git_repo_with_remote: tuple[str, str]
    ) -> None:
        repo, _remote = git_repo_with_remote
        result = await git_fetch(cwd=repo)
        assert result["remote"] == "origin"
        assert result["pruned"] is False

    async def test_fetch_with_prune(
        self, git_repo_with_remote: tuple[str, str]
    ) -> None:
        repo, _remote = git_repo_with_remote
        result = await git_fetch(prune=True, cwd=repo)
        assert result["pruned"] is True


# ---------------------------------------------------------------------------
# Test git_tag_create
# ---------------------------------------------------------------------------


class TestGitTagCreate:
    async def test_create_tag(self, git_repo: str) -> None:
        result = await git_tag_create(
            tag_name="v1.0.0", message="Release 1.0.0", cwd=git_repo
        )
        assert result["tag"] == "v1.0.0"
        assert len(result["sha"]) == 40
        assert result["pushed"] is False

    async def test_create_tag_and_push(
        self, git_repo_with_remote: tuple[str, str]
    ) -> None:
        repo, _remote = git_repo_with_remote
        result = await git_tag_create(
            tag_name="v2.0.0", message="Release 2.0.0", push=True, cwd=repo
        )
        assert result["tag"] == "v2.0.0"
        assert result["pushed"] is True


# ---------------------------------------------------------------------------
# Test git_branch_delete
# ---------------------------------------------------------------------------


class TestGitBranchDelete:
    async def test_delete_merged_branch(self, git_repo: str) -> None:
        # Create and merge a branch
        await _run_git_checked("checkout", "-b", "to-delete", cwd=git_repo)
        await _run_git_checked("checkout", "main", cwd=git_repo)

        result = await git_branch_delete(branch_name="to-delete", cwd=git_repo)
        assert result["deleted_local"] is True
        assert result["deleted_remote"] is False

    async def test_refuse_delete_current_branch(self, git_repo: str) -> None:
        # Try to delete current branch
        current = await git_branch_current(cwd=git_repo)
        branch = current["branch"]
        assert branch is not None
        with pytest.raises(GitToolError, match="Cannot delete currently checked-out"):
            await git_branch_delete(branch_name=branch, cwd=git_repo)

    async def test_force_delete_unmerged(self, git_repo: str) -> None:
        from pathlib import Path

        # Create branch with unmerged commit
        await _run_git_checked("checkout", "-b", "unmerged", cwd=git_repo)
        (Path(git_repo) / "unmerged.txt").write_text("unmerged\n")
        await _run_git_checked("add", "unmerged.txt", cwd=git_repo)
        await _run_git_checked("commit", "-m", "unmerged commit", cwd=git_repo)
        await _run_git_checked("checkout", "main", cwd=git_repo)

        # Normal delete should fail (unmerged)
        with pytest.raises(GitToolError):
            await git_branch_delete(branch_name="unmerged", cwd=git_repo)

        # Force delete should succeed
        result = await git_branch_delete(
            branch_name="unmerged", force=True, cwd=git_repo
        )
        assert result["deleted_local"] is True


# ---------------------------------------------------------------------------
# Test _run_git helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    async def test_run_git_returns_tuple(self, git_repo: str) -> None:
        code, stdout, stderr = await _run_git("status", cwd=git_repo)
        assert code == 0
        assert isinstance(stdout, str)
        assert isinstance(stderr, str)

    async def test_run_git_checked_raises_on_error(self, git_repo: str) -> None:
        with pytest.raises(GitToolError):
            await _run_git_checked("checkout", "nonexistent-branch", cwd=git_repo)
