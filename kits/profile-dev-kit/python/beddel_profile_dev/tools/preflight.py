"""Fail-closed preflight — first step of ``verify-change``.

Checks the target repository, the gate executables and the required environment
key *names*. No network. Secret values are never read into any output.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import PROFILE_PREFLIGHT_FAILED, ProfileError
from beddel_profile_dev.config import load_config

__all__ = ["profile_preflight"]

_GIT_TIMEOUT_SECONDS = 10


def _in_git_work_tree(path: Path) -> bool:
    """Return True if ``path`` is inside a Git work tree; any error -> False."""
    if not path.is_dir():
        return False
    git = shutil.which("git")
    if git is None:
        return False
    # Drop inherited GIT_* so the check cannot be redirected to another repository.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        result = subprocess.run(
            [git, "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            env=env,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == b"true"


@beddel_tool(
    name="profile_preflight",
    description="Fail-closed preflight: Git work tree, gate executables, required env keys",
    category="profile",
)
def profile_preflight(repo_path: str) -> dict[str, Any]:
    """Run all preflight checks; raise with failed check ids if any fails.

    Args:
        repo_path: Path of the repository to verify.

    Returns:
        ``{"ok": True, "checks": [{"id": ..., "ok": True}, ...]}``.

    Raises:
        ProfileError: On malformed config, or with a fixed message listing the
            failed check identifiers (never paths or values).
    """
    config = load_config()  # raises before any other check

    # A blank or non-string path must not fall through to the current directory.
    if isinstance(repo_path, str) and repo_path.strip():
        path = Path(repo_path)
        checks: list[tuple[str, bool]] = [
            ("repo.exists", path.exists()),
            ("repo.is_dir", path.is_dir()),
            ("repo.git_work_tree", _in_git_work_tree(path)),
        ]
    else:
        checks = [
            ("repo.exists", False),
            ("repo.is_dir", False),
            ("repo.git_work_tree", False),
        ]
    checks.extend(
        (f"executable.{name}", shutil.which(name) is not None)
        for name in config.gate_executables
    )
    checks.extend(
        (f"env.{key}", bool(os.environ.get(key))) for key in config.required_env_keys
    )

    failed = [check_id for check_id, ok in checks if not ok]
    if failed:
        raise ProfileError(
            PROFILE_PREFLIGHT_FAILED,
            "profile preflight failed: " + ", ".join(failed),
            {"failed": failed},
        )
    return {
        "ok": True,
        "checks": [{"id": check_id, "ok": True} for check_id, _ in checks],
    }
