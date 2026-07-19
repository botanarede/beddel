"""Beddel tools-git-kit — 10 typed async Git operations.

Wraps the ``git`` CLI via ``asyncio.create_subprocess_exec``.
All tools return structured dicts and enforce explicit file staging.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from beddel.tools import beddel_tool

logger = logging.getLogger(__name__)

MAX_OUTPUT_BYTES = 102_400  # 100KB


# ---------------------------------------------------------------------------
# Error Model
# ---------------------------------------------------------------------------


class GitToolError(RuntimeError):
    """Raised when a git subprocess exits non-zero or times out."""

    def __init__(self, command: str, exit_code: int, stderr: str) -> None:
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"git command failed (exit {exit_code}): {stderr[:200]}")


# ---------------------------------------------------------------------------
# Private Helpers
# ---------------------------------------------------------------------------

_BRANCH_NAME_RE = re.compile(r"^[a-zA-Z0-9/_.\-]+$")


def _truncate(text: str, max_bytes: int = MAX_OUTPUT_BYTES) -> str:
    """Cap output at max_bytes to prevent memory exhaustion (tail-preserving)."""
    if len(text) <= max_bytes:
        return text
    return "[truncated]\n" + text[-max_bytes:]


async def _run_git(
    *args: str, cwd: str | None = None, timeout: int = 120
) -> tuple[int, str, str]:
    """Low-level: run git command with timeout, return (exit_code, stdout, stderr).

    Default 120s for local ops. Network tools should pass timeout=300.
    """
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise GitToolError(
            command=f"git {' '.join(args)}", exit_code=-1, stderr="timeout"
        )
    return proc.returncode or 0, stdout_bytes.decode(), stderr_bytes.decode()


async def _run_git_checked(
    *args: str, cwd: str | None = None, timeout: int = 120
) -> str:
    """Checked: raises GitToolError if exit code != 0."""
    code, stdout, stderr = await _run_git(*args, cwd=cwd, timeout=timeout)
    if code != 0:
        raise GitToolError(
            command=f"git {' '.join(args)}", exit_code=code, stderr=stderr
        )
    return stdout


# ---------------------------------------------------------------------------
# Tool 1: git_status
# ---------------------------------------------------------------------------


@beddel_tool(
    name="git_status",
    description="Check worktree status (clean/dirty, modified files, ahead/behind)",
    category="git",
)
async def git_status(*, cwd: str | None = None) -> dict[str, Any]:
    """Check worktree status — clean/dirty, modified/staged/untracked files, ahead/behind.

    Returns:
        Dict with keys: clean, branch, modified, staged, untracked, ahead, behind.
    """
    # Get porcelain status
    _code, porcelain_out, _err = await _run_git(
        "status", "--porcelain=v1", cwd=cwd
    )

    modified: list[str] = []
    staged: list[str] = []
    untracked: list[str] = []

    for line in porcelain_out.splitlines():
        if len(line) < 3:
            continue
        index_status = line[0]
        worktree_status = line[1]
        filepath = line[3:]

        # Staged changes (index has changes)
        if index_status in ("A", "M", "D", "R", "C"):
            staged.append(filepath)
        # Worktree modifications (not staged)
        if worktree_status in ("M", "D"):
            modified.append(filepath)
        # Untracked
        if index_status == "?" and worktree_status == "?":
            untracked.append(filepath)

    # Get branch name
    _code2, branch_out, _err2 = await _run_git(
        "branch", "--show-current", cwd=cwd
    )
    branch = branch_out.strip()

    # Get ahead/behind
    ahead = 0
    behind = 0
    code3, rev_out, _err3 = await _run_git(
        "rev-list", "--left-right", "--count", "@{upstream}...HEAD", cwd=cwd
    )
    if code3 == 0 and rev_out.strip():
        parts = rev_out.strip().split()
        if len(parts) == 2:
            behind = int(parts[0])
            ahead = int(parts[1])

    clean = not modified and not staged and not untracked

    return {
        "clean": clean,
        "branch": branch,
        "modified": modified,
        "staged": staged,
        "untracked": untracked,
        "ahead": ahead,
        "behind": behind,
    }


# ---------------------------------------------------------------------------
# Tool 2: git_branch_create
# ---------------------------------------------------------------------------


@beddel_tool(
    name="git_branch_create",
    description="Create and checkout a new branch",
    category="git",
)
async def git_branch_create(
    *, name: str, from_ref: str = "HEAD", cwd: str | None = None
) -> dict[str, Any]:
    """Create and checkout a new branch from an optional base ref.

    Args:
        name: Branch name (must match ^[a-zA-Z0-9/_.-]+$).
        from_ref: Base ref to branch from. Defaults to HEAD.
        cwd: Working directory (git repo path).

    Returns:
        Dict with keys: branch, sha, created.

    Raises:
        GitToolError: If branch name is invalid or git command fails.
    """
    if not _BRANCH_NAME_RE.match(name):
        raise GitToolError(
            command=f"git checkout -b {name}",
            exit_code=-1,
            stderr=f"Invalid branch name: '{name}'. Must match ^[a-zA-Z0-9/_.-]+$",
        )

    await _run_git_checked("checkout", "-b", name, from_ref, cwd=cwd)
    sha_out = await _run_git_checked("rev-parse", "HEAD", cwd=cwd)

    return {
        "branch": name,
        "sha": sha_out.strip(),
        "created": True,
    }


# ---------------------------------------------------------------------------
# Tool 3: git_branch_current
# ---------------------------------------------------------------------------


@beddel_tool(
    name="git_branch_current",
    description="Get current branch name and SHA",
    category="git",
)
async def git_branch_current(*, cwd: str | None = None) -> dict[str, Any]:
    """Get current branch name, HEAD SHA, and detached state.

    Returns:
        Dict with keys: branch (str|None), detached (bool), sha (str).
    """
    code, branch_out, _err = await _run_git(
        "symbolic-ref", "--short", "HEAD", cwd=cwd
    )
    detached = code != 0
    branch = None if detached else branch_out.strip()

    sha_out = await _run_git_checked("rev-parse", "HEAD", cwd=cwd)

    return {
        "branch": branch,
        "detached": detached,
        "sha": sha_out.strip(),
    }


# ---------------------------------------------------------------------------
# Tool 4: git_commit
# ---------------------------------------------------------------------------


@beddel_tool(
    name="git_commit",
    description="Stage specific files and commit with message",
    category="git",
)
async def git_commit(
    *,
    files: list[str],
    message: str,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Stage specific files and commit with a message.

    NEVER uses ``git add .`` or ``git add -A``. Files must be explicitly listed.

    Args:
        files: List of file paths to stage. Must not be empty.
        message: Commit message. Must not be empty.
        cwd: Working directory (git repo path).

    Returns:
        Dict with keys: sha, files_staged, message.

    Raises:
        GitToolError: If files is empty, message is empty, or git fails.
    """
    if not files:
        raise GitToolError(
            command="git commit",
            exit_code=-1,
            stderr="files list must not be empty — explicit staging required",
        )
    if not message.strip():
        raise GitToolError(
            command="git commit",
            exit_code=-1,
            stderr="commit message must not be empty",
        )

    # Atomic staging: single git add with all files
    await _run_git_checked("add", "--", *files, cwd=cwd)

    # Commit
    await _run_git_checked("commit", "-m", message, cwd=cwd)

    # Get new SHA
    sha_out = await _run_git_checked("rev-parse", "HEAD", cwd=cwd)

    return {
        "sha": sha_out.strip(),
        "files_staged": len(files),
        "message": message,
    }


# ---------------------------------------------------------------------------
# Tool 5: git_push
# ---------------------------------------------------------------------------


@beddel_tool(
    name="git_push",
    description="Push branch to remote",
    category="git",
)
async def git_push(
    *,
    remote: str = "origin",
    set_upstream: bool = False,
    force: bool = False,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Push current branch to remote.

    Args:
        remote: Remote name. Defaults to "origin".
        set_upstream: If True, uses --set-upstream.
        force: If True, force push. Logs a warning.
        cwd: Working directory (git repo path).

    Returns:
        Dict with keys: branch, remote, pushed, set_upstream.
    """
    if force:
        logger.warning("git_push called with force=True — destructive operation")

    # Get current branch
    branch_out = await _run_git_checked(
        "symbolic-ref", "--short", "HEAD", cwd=cwd
    )
    branch = branch_out.strip()

    # Build push args
    args: list[str] = ["push"]
    if set_upstream:
        args.append("--set-upstream")
    if force:
        args.append("--force")
    args.extend([remote, branch])

    await _run_git_checked(*args, cwd=cwd, timeout=300)

    return {
        "branch": branch,
        "remote": remote,
        "pushed": True,
        "set_upstream": set_upstream,
    }


# ---------------------------------------------------------------------------
# Tool 6: git_merge
# ---------------------------------------------------------------------------


@beddel_tool(
    name="git_merge",
    description="Merge a branch into current",
    category="git",
)
async def git_merge(
    *,
    source_branch: str,
    no_ff: bool = False,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Merge a source branch into the current branch.

    Aborts on conflict and reports conflicting files.

    Args:
        source_branch: Branch to merge from.
        no_ff: If True, creates a merge commit even for fast-forward.
        cwd: Working directory (git repo path).

    Returns:
        Dict with keys: merged, source, target, conflicts, merge_sha.
    """
    # Get current branch (target)
    target_out = await _run_git_checked(
        "symbolic-ref", "--short", "HEAD", cwd=cwd
    )
    target = target_out.strip()

    # Build merge args
    args: list[str] = ["merge"]
    if no_ff:
        args.append("--no-ff")
    args.append(source_branch)

    code, _stdout, stderr = await _run_git(*args, cwd=cwd)

    if code != 0:
        # Conflict detected — get list of conflicting files
        _c2, diff_out, _e2 = await _run_git(
            "diff", "--name-only", "--diff-filter=U", cwd=cwd
        )
        conflicts = [f for f in diff_out.strip().splitlines() if f]

        # Abort the merge
        await _run_git("merge", "--abort", cwd=cwd)

        return {
            "merged": False,
            "source": source_branch,
            "target": target,
            "conflicts": conflicts,
            "merge_sha": None,
        }

    # Success — get merge SHA
    sha_out = await _run_git_checked("rev-parse", "HEAD", cwd=cwd)

    return {
        "merged": True,
        "source": source_branch,
        "target": target,
        "conflicts": None,
        "merge_sha": sha_out.strip(),
    }


# ---------------------------------------------------------------------------
# Tool 7: git_diff_stat
# ---------------------------------------------------------------------------


@beddel_tool(
    name="git_diff_stat",
    description="Get diff statistics between two refs",
    category="git",
)
async def git_diff_stat(
    *,
    base_ref: str,
    head_ref: str = "HEAD",
    cwd: str | None = None,
) -> dict[str, Any]:
    """Get diff statistics between two refs (insertions, deletions, files changed).

    Args:
        base_ref: Base reference (e.g. "main", commit SHA).
        head_ref: Head reference. Defaults to "HEAD".
        cwd: Working directory (git repo path).

    Returns:
        Dict with keys: files_changed, insertions, deletions, files.
    """
    numstat_out = await _run_git_checked(
        "diff", "--numstat", f"{base_ref}...{head_ref}", cwd=cwd
    )

    numstat_out = _truncate(numstat_out)

    files: list[dict[str, Any]] = []
    total_insertions = 0
    total_deletions = 0

    for line in numstat_out.splitlines():
        if line.startswith("[truncated]"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        ins_str, del_str, path = parts
        # Binary files show "-" for insertions/deletions
        ins = int(ins_str) if ins_str != "-" else 0
        dels = int(del_str) if del_str != "-" else 0
        files.append({"path": path, "insertions": ins, "deletions": dels})
        total_insertions += ins
        total_deletions += dels

    return {
        "files_changed": len(files),
        "insertions": total_insertions,
        "deletions": total_deletions,
        "files": files,
    }


# ---------------------------------------------------------------------------
# Tool 8: git_fetch
# ---------------------------------------------------------------------------


@beddel_tool(
    name="git_fetch",
    description="Fetch from remote with optional prune",
    category="git",
)
async def git_fetch(
    *,
    remote: str = "origin",
    prune: bool = False,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Fetch from remote with optional prune of deleted remote-tracking branches.

    Args:
        remote: Remote name. Defaults to "origin".
        prune: If True, prune deleted remote-tracking refs.
        cwd: Working directory (git repo path).

    Returns:
        Dict with keys: remote, pruned, updated_refs.
    """
    args: list[str] = ["fetch"]
    if prune:
        args.append("--prune")
    args.append(remote)

    _code, _stdout, stderr = await _run_git(*args, cwd=cwd, timeout=300)

    # Parse stderr for updated refs (git fetch outputs to stderr)
    updated_refs = 0
    for line in stderr.splitlines():
        stripped = line.strip()
        if stripped.startswith("->") or "[new" in stripped or "..." in stripped:
            updated_refs += 1

    return {
        "remote": remote,
        "pruned": prune,
        "updated_refs": updated_refs,
    }


# ---------------------------------------------------------------------------
# Tool 9: git_tag_create
# ---------------------------------------------------------------------------


@beddel_tool(
    name="git_tag_create",
    description="Create annotated tag and optionally push",
    category="git",
)
async def git_tag_create(
    *,
    tag_name: str,
    message: str,
    push: bool = False,
    remote: str = "origin",
    cwd: str | None = None,
) -> dict[str, Any]:
    """Create an annotated tag with message. Optionally push to remote.

    Args:
        tag_name: Tag name (e.g. "v1.0.0").
        message: Tag annotation message.
        push: If True, push the tag to remote immediately.
        remote: Remote to push to. Defaults to "origin".
        cwd: Working directory (git repo path).

    Returns:
        Dict with keys: tag, sha, pushed.
    """
    await _run_git_checked("tag", "-a", tag_name, "-m", message, cwd=cwd)
    sha_out = await _run_git_checked("rev-parse", tag_name, cwd=cwd)

    pushed = False
    if push:
        await _run_git_checked(
            "push", remote, tag_name, cwd=cwd, timeout=300
        )
        pushed = True

    return {
        "tag": tag_name,
        "sha": sha_out.strip(),
        "pushed": pushed,
    }


# ---------------------------------------------------------------------------
# Tool 10: git_branch_delete
# ---------------------------------------------------------------------------


@beddel_tool(
    name="git_branch_delete",
    description="Delete branch locally and optionally on remote",
    category="git",
)
async def git_branch_delete(
    *,
    branch_name: str,
    remote: bool = False,
    force: bool = False,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Delete a branch locally and optionally on remote.

    Refuses to delete the currently checked-out branch.

    Args:
        branch_name: Branch to delete.
        remote: If True, also delete from origin.
        force: If True, use -D (force delete even if not merged).
        cwd: Working directory (git repo path).

    Returns:
        Dict with keys: branch, deleted_local, deleted_remote.

    Raises:
        GitToolError: If attempting to delete the current branch.
    """
    # Check current branch
    code, current_out, _err = await _run_git(
        "symbolic-ref", "--short", "HEAD", cwd=cwd
    )
    if code == 0 and current_out.strip() == branch_name:
        raise GitToolError(
            command=f"git branch -d {branch_name}",
            exit_code=-1,
            stderr=f"Cannot delete currently checked-out branch: {branch_name}",
        )

    # Delete locally
    delete_flag = "-D" if force else "-d"
    await _run_git_checked("branch", delete_flag, branch_name, cwd=cwd)

    deleted_remote = False
    if remote:
        await _run_git_checked(
            "push", "origin", "--delete", branch_name, cwd=cwd, timeout=300
        )
        deleted_remote = True

    return {
        "branch": branch_name,
        "deleted_local": True,
        "deleted_remote": deleted_remote,
    }
