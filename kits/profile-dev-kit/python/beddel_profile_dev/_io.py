"""Git access, confinement and create-only record I/O for the profile tools.

Git runs without a shell, with ``GIT_*`` removed from its environment, stdin
closed and a timeout. Every work-tree path resolves, after ``realpath``,
inside the real repository root. Records are create-only.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from beddel_profile_dev._errors import PROFILE_REPOSITORY_INVALID, ProfileError

__all__ = [
    "blob_at",
    "canonical_json",
    "confined",
    "diff_text",
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
_ALL_ZEROS = re.compile(r"^0+$")
_GITLINK_MODE = "160000"
# Binary threshold: NUL anywhere in either blob, or size exceeds this limit.
_BINARY_SIZE = 1 << 20  # 1 MiB
_REPO_INVALID = "repository or revision invalid"


@dataclass(frozen=True)
class _Change:
    status: str
    mode_a: str
    mode_b: str
    oid_a: str
    oid_b: str
    path: str


def _is_binary(data: bytes) -> bool:
    """Return True if ``data`` should be treated as binary.

    Binary rule (kit-owned, fixed): NUL anywhere OR size > 1 MiB.
    """
    return b"\x00" in data or len(data) > _BINARY_SIZE


def _repo_error() -> ProfileError:
    return ProfileError(PROFILE_REPOSITORY_INVALID, _REPO_INVALID)


def _git(
    repo: Path,
    *args: str,
) -> subprocess.CompletedProcess[bytes] | None:
    git = shutil.which("git")
    if git is None:
        return None
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_NO_LAZY_FETCH"] = "1"  # no network, even in a partial clone
    env["GIT_ATTR_NOSYSTEM"] = "1"  # the system attributes file never applies
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


def _blob_by_oid(repo: Path, oid: str) -> bytes:
    """Return the raw blob bytes for ``oid`` via ``cat-file blob``.

    A Git failure or non-zero exit raises ``_repo_error()``.
    An all-zero OID (absent side) must never be passed here.
    """
    result = _git(repo, "cat-file", "blob", oid)
    if result is None or result.returncode != 0:
        raise _repo_error()
    return result.stdout


def _raw_changes(repo: Path, base: str, revision: str) -> list[_Change]:
    """Return per-path change records between ``base`` and ``revision``.

    Uses ``diff-tree -r -z --raw`` plumbing: no config scope can reach it.
    A Git failure raises; it is never silently empty.
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
        "--raw",
        base,
        revision,
    )
    if result is None or result.returncode != 0:
        raise _repo_error()
    # The -z --raw stream: each entry is
    #   :<mode_a> <mode_b> <oid_a> <oid_b> <status>\0<path>\0
    # (C/R would add a second path, but --no-renames disables them.)
    changes: list[_Change] = []
    tokens = result.stdout.split(b"\x00")
    i = 0
    while i < len(tokens):
        meta_raw = tokens[i]
        i += 1
        if not meta_raw:
            continue
        # meta starts with ':' followed by "mode_a mode_b oid_a oid_b status"
        meta = meta_raw.lstrip(b":").decode("ascii", "replace")
        parts = meta.split()
        if len(parts) < 5:
            continue
        mode_a, mode_b, oid_a, oid_b, status = (
            parts[0],
            parts[1],
            parts[2],
            parts[3],
            parts[4][0],
        )
        # Consume the path token
        if i >= len(tokens):
            break
        path_raw = tokens[i]
        i += 1
        path = path_raw.decode("utf-8", "surrogateescape")
        changes.append(
            _Change(
                status=status,
                mode_a=mode_a,
                mode_b=mode_b,
                oid_a=oid_a,
                oid_b=oid_b,
                path=path,
            )
        )
    return sorted(changes, key=lambda c: c.path)


def _render_change(repo: Path, c: _Change) -> str:
    """Render one path's git-shaped diff text from plumbing object reads.

    The output is a pure function of the object store and this code; no git
    config or attribute scope can change it.
    """
    path = c.path
    header = f"diff --git a/{path} b/{path}\n"

    # Gitlink (submodule): never read a blob.
    if c.mode_a == _GITLINK_MODE or c.mode_b == _GITLINK_MODE:
        return header + f"Subproject commit {c.oid_a}..{c.oid_b}\n"

    absent_a = bool(_ALL_ZEROS.fullmatch(c.oid_a))
    absent_b = bool(_ALL_ZEROS.fullmatch(c.oid_b))

    # Pure mode change (same content, modes differ).
    if c.oid_a == c.oid_b and c.mode_a != c.mode_b and not absent_a:
        return header + f"old mode {c.mode_a}\nnew mode {c.mode_b}\n"

    # Read present blobs.
    data_a = b"" if absent_a else _blob_by_oid(repo, c.oid_a)
    data_b = b"" if absent_b else _blob_by_oid(repo, c.oid_b)

    # Type change: treat as delete of oid_a + add of oid_b.
    if c.status == "T":
        del_change = _Change("D", c.mode_a, c.mode_b, c.oid_a, "0" * len(c.oid_a), path)
        add_change = _Change("A", c.mode_a, c.mode_b, "0" * len(c.oid_b), c.oid_b, path)
        return _render_change(repo, del_change) + _render_change(repo, add_change)

    # Binary rule: NUL anywhere in either present side, or size > 1 MiB.
    if (not absent_a and _is_binary(data_a)) or (not absent_b and _is_binary(data_b)):
        side_a = "/dev/null" if absent_a else f"a/{path}"
        side_b = "/dev/null" if absent_b else f"b/{path}"
        return header + f"Binary files {side_a} and {side_b} differ\n"

    # File mode annotation.
    mode_lines = ""
    if absent_a and not absent_b:
        mode_lines = f"new file mode {c.mode_b}\n"
    elif absent_b and not absent_a:
        mode_lines = f"deleted file mode {c.mode_a}\n"

    # Index line.
    oid_a_short = c.oid_a[:12]
    oid_b_short = c.oid_b[:12]
    # Use the present mode; for a content-only change modes are equal.
    mode = c.mode_b if not absent_b else c.mode_a
    index_line = f"index {oid_a_short}..{oid_b_short} {mode}\n"

    # --- / +++ lines.
    from_file = "/dev/null" if absent_a else f"a/{path}"
    to_file = "/dev/null" if absent_b else f"b/{path}"

    # Text diff via stdlib difflib.
    lines_a = data_a.decode("utf-8", "replace").splitlines(keepends=True)
    lines_b = data_b.decode("utf-8", "replace").splitlines(keepends=True)
    # ``lineterm=""`` so difflib does NOT append a newline to its control lines
    # (``---``, ``+++``, ``@@``); content lines keep their own via ``keepends``.
    # We then re-add ``\n`` to each control line ourselves, which keeps a hunk
    # header like ``@@ -1 +1 @@`` on its own single line instead of doubling it.
    diff_lines = list(
        difflib.unified_diff(
            lines_a,
            lines_b,
            fromfile=from_file,
            tofile=to_file,
            n=3,
            lineterm="",
        )
    )

    if not diff_lines:
        # No textual difference (e.g. pure mode change handled above, or empty→empty).
        return header + mode_lines + index_line

    # difflib emits "--- fromfile", "+++ tofile" as the first two lines, then
    # hunks whose ``@@`` headers now carry no trailing newline. Strip the
    # leading --- and +++ (we emit them ourselves to match git's exact format,
    # with no timestamp); re-terminate every remaining control line (one that
    # does not already end in a newline from ``keepends``).
    body_lines = diff_lines[2:]  # skip --- and +++ from difflib
    hunk_body = "".join(
        line if line.endswith("\n") else line + "\n" for line in body_lines
    )

    return (
        header
        + mode_lines
        + index_line
        + f"--- {from_file}\n"
        + f"+++ {to_file}\n"
        + hunk_body
    )


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


def diff_text(repo: Path, base: str, revision: str, limit: int) -> tuple[str, bool]:
    """Return the textual diff ``base..revision`` and whether it was truncated.

    Deterministic by construction: the diff is RENDERED inside the kit from
    ``diff-tree --raw`` + ``cat-file blob`` plumbing object reads and stdlib
    ``difflib``. No git config or attribute scope (system, user, the repository's
    own ``.git/config``, or ``.git/info/attributes``) can change the output.

    Binary is decided by the kit: NUL anywhere in either blob, or size > 1 MiB,
    yields ``Binary files a/<path> and b/<path> differ``. The ``@@`` hunk header
    carries no funcname text by design. The byte cut is applied AFTER UTF-8
    encoding; NUL bytes are replaced with U+FFFD, keeping the result argv-safe.
    A Git failure raises; it is never an empty diff.
    """
    if _FULL_SHA.fullmatch(base) is None or _FULL_SHA.fullmatch(revision) is None:
        raise _repo_error()
    changes = _raw_changes(repo, base, revision)
    assembled = "".join(_render_change(repo, c) for c in changes)
    data = assembled.encode("utf-8")  # encode FIRST
    cut = data[:limit]  # byte cut AFTER encoding
    text = cut.decode("utf-8", "replace").replace("\x00", "\ufffd")
    return text, len(data) > limit


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
