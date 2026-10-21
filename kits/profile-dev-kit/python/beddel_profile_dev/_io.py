"""Git access, confinement and create-only record I/O for the profile tools.

Git runs without a shell, with ``GIT_*`` removed from its environment, stdin
closed and a timeout. Every work-tree path resolves, after ``realpath``,
inside the real repository root. Records are create-only.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from beddel_profile_dev._errors import PROFILE_REPOSITORY_INVALID, ProfileError

__all__ = [
    "blob_at",
    "canonical_json",
    "confined",
    "footprint",
    "in_head_history",
    "in_index",
    "is_ancestor",
    "path_present",
    "read_confined",
    "real_repo_root",
    "resolve_revision",
    "work_tree_at",
    "write_create_only",
]

_GIT_TIMEOUT_SECONDS = 20
_FULL_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_REPO_INVALID = "repository or revision invalid"


def _repo_error() -> ProfileError:
    return ProfileError(PROFILE_REPOSITORY_INVALID, _REPO_INVALID)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes] | None:
    git = shutil.which("git")
    if git is None:
        return None
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_NO_LAZY_FETCH"] = "1"  # no network, even in a partial clone
    try:
        return subprocess.run(
            [
                git,
                "--no-replace-objects",
                "--literal-pathspecs",
                "-C",
                str(repo),
                *args,
            ],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            env=env,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def real_repo_root(repo_path: object) -> Path:
    """Return the real repository root; ``repo_path`` must be that root."""
    if not isinstance(repo_path, str) or not repo_path.strip() or "\x00" in repo_path:
        raise _repo_error()
    real = Path(os.path.realpath(repo_path))
    if not real.is_dir():
        raise _repo_error()
    result = _git(real, "rev-parse", "--show-toplevel")
    if result is None or result.returncode != 0:
        raise _repo_error()
    top = Path(os.path.realpath(result.stdout.decode("utf-8", "replace").strip()))
    if top != real:
        raise _repo_error()
    return real


def resolve_revision(repo: Path, revision: object) -> str:
    """Resolve ``revision`` to a full commit SHA (the Analyzed revision identity)."""
    if (
        not isinstance(revision, str)
        or not revision.strip()
        or revision.startswith("-")
    ):
        raise _repo_error()
    result = _git(
        repo, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"
    )
    if result is None or result.returncode != 0:
        raise _repo_error()
    sha = result.stdout.decode("ascii", "replace").strip()
    if _FULL_SHA.fullmatch(sha) is None:
        raise _repo_error()
    return sha


def blob_at(repo: Path, sha: str, path: str) -> bytes | None:
    """Return the blob bytes of ``path`` in the tree of ``sha``, or None."""
    result = _git(repo, "cat-file", "blob", f"{sha}:{path}")
    if result is None or result.returncode != 0:
        return None
    return result.stdout


def path_present(repo: Path, sha: str, path: str) -> bool:
    """Return True if ``path`` exists in the tree of ``sha``.

    A Git failure is an error, never "absent": it would be frozen into the snapshot.
    """
    result = _git(repo, "ls-tree", "-z", sha, "--", path)
    if result is None or result.returncode != 0:
        raise _repo_error()
    return bool(result.stdout)


def is_ancestor(repo: Path, base: str, revision: str) -> bool:
    """Return True if commit ``base`` is an ancestor of ``revision``.

    Exit 0 is True, exit 1 is False; any other outcome is a Git failure.
    """
    if _FULL_SHA.fullmatch(base) is None or _FULL_SHA.fullmatch(revision) is None:
        raise _repo_error()
    result = _git(repo, "merge-base", "--is-ancestor", base, revision)
    if result is None or result.returncode not in (0, 1):
        raise _repo_error()
    return result.returncode == 0


def footprint(repo: Path, base: str, revision: str) -> list[str]:
    """Sorted, unique paths that differ between the trees of two commits.

    Plumbing only: no rename detection, no diff configuration, no work tree and
    no index. A Git failure raises; it is never an empty footprint.
    """
    if _FULL_SHA.fullmatch(base) is None or _FULL_SHA.fullmatch(revision) is None:
        raise _repo_error()
    result = _git(
        repo,
        "diff-tree",
        "-r",
        "-z",
        "--no-renames",
        "--ignore-submodules=none",
        "--no-commit-id",
        "--name-only",
        base,
        revision,
    )
    if result is None or result.returncode != 0:
        raise _repo_error()
    names = {
        raw.decode("utf-8", "surrogateescape")
        for raw in result.stdout.split(b"\x00")
        if raw
    }
    return sorted(names)


def in_index(repo: Path, path: str) -> bool:
    """Return True if ``path`` is in the Git index. A Git failure raises."""
    result = _git(repo, "ls-files", "-z", "--cached", "--", path)
    if result is None or result.returncode != 0:
        raise _repo_error()
    return bool(result.stdout)


def in_head_history(repo: Path, path: str) -> bool:
    """Return True if any commit reachable from ``HEAD`` touches ``path``.

    An unborn ``HEAD`` has no history and is not an error; any other Git
    failure raises.
    """
    head = _git(repo, "rev-parse", "--verify", "--quiet", "HEAD")
    if head is None:
        raise _repo_error()
    if head.returncode != 0:
        # Only a HEAD that names a branch with no commit yet is unborn; a
        # broken ref or a detached HEAD that cannot be read is a failure.
        unborn = _git(repo, "symbolic-ref", "--quiet", "HEAD")
        if unborn is None or unborn.returncode != 0:
            raise _repo_error()
        ref = unborn.stdout.decode("utf-8", "replace").strip()
        exists = _git(repo, "show-ref", "--quiet", "--verify", ref)
        if exists is None or exists.returncode != 1:
            raise _repo_error()
        return False
    result = _git(repo, "rev-list", "-n", "1", "--full-history", "HEAD", "--", path)
    if result is None or result.returncode != 0:
        raise _repo_error()
    return bool(result.stdout.strip())


def work_tree_at(repo: Path, sha: str, ignore_dir: str) -> bool:
    """Return True if the work tree IS commit ``sha`` and no tracked file differs.

    Untracked files are not looked at, and neither is anything tracked under
    ``ignore_dir`` (the records directory, whose files the kit itself updates).
    A Git failure is an error, never a mismatch.
    """
    head = _git(repo, "rev-parse", "--verify", "--end-of-options", "HEAD^{commit}")
    if head is None or head.returncode != 0:
        raise _repo_error()
    if head.stdout.decode("ascii", "replace").strip() != sha:
        return False
    status = _git(
        repo,
        "--no-optional-locks",
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=no",
        "--ignore-submodules=untracked",
    )
    if status is None or status.returncode != 0:
        raise _repo_error()
    prefix = ignore_dir.rstrip("/") + "/"
    # ``status`` cannot see a tracked file flagged assume-unchanged or
    # skip-worktree (a sparse checkout): refuse those, they could hide an edit.
    flags = _git(repo, "ls-files", "-v", "-z")
    if flags is None or flags.returncode != 0:
        raise _repo_error()
    for entry in flags.stdout.decode("utf-8", "surrogateescape").split("\0"):
        hidden = entry and (entry[0].islower() or entry[0] == "S")
        if hidden and not entry[2:].startswith(prefix):
            return False
    original = False  # the next token is the source path of a rename or copy
    for token in status.stdout.decode("utf-8", "surrogateescape").split("\0"):
        if not token:
            continue
        if original:
            path = token
            original = False
        else:
            path = token[3:]
            original = "R" in token[:2] or "C" in token[:2]
        if not path.startswith(prefix):
            return False
    return True


def confined(root: Path, relative: str) -> Path:
    """Return ``root/relative`` if its real path stays inside ``root``."""
    target = Path(os.path.realpath(root / relative))
    if target != root and root not in target.parents:
        raise _repo_error()
    return root / relative


def canonical_json(data: Any) -> bytes:
    """Deterministic JSON: sorted keys, ASCII, no timestamp, trailing newline."""
    return (
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("ascii")


def read_confined(root: Path, relative: str) -> bytes | None:
    """Read a regular file under ``root`` (confined); None if absent."""
    path = confined(root, relative)
    if not path.is_file():
        return None
    return path.read_bytes()


def write_create_only(root: Path, relative: str, data: bytes) -> bool:
    """Create ``relative`` under ``root`` exclusively.

    Returns True if created, False if it already existed (never overwritten;
    the caller re-reads and applies its idempotency rule).
    """
    path = confined(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    confined(root, relative)  # re-check after the directories exist
    try:
        with open(path, "xb") as handle:
            handle.write(data)
    except FileExistsError:
        return False
    return True
