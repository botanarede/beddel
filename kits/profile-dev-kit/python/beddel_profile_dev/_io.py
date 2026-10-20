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
    "path_present",
    "read_confined",
    "real_repo_root",
    "resolve_revision",
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
