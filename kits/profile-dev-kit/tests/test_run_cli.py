"""AC7: run verify-change through the real ``beddel run`` CLI, hermetically."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent
KITS_DIR = KIT_ROOT.parent
WORKFLOW = KIT_ROOT / "workflows" / "verify-change.yaml"


def _beddel_argv() -> list[str]:
    """Prefer the console script next to this interpreter; never skip."""
    console_script = Path(sys.executable).parent / "beddel"
    if console_script.is_file():
        return [str(console_script)]
    return [sys.executable, "-c", "from beddel.cli import main; main()"]


def _run(
    repo_path: str, tmp_path: Path, **extra_env: str
) -> subprocess.CompletedProcess[str]:
    # Throw-away HOME whose config points kits_paths at this checkout, so the
    # user's global config cannot shadow the kit under test and no PYTHONPATH
    # is needed (configured kit paths are put on sys.path by the core).
    home = tmp_path / "home"
    config_dir = home / ".config" / "beddel"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(json.dumps({"kits_paths": [str(KITS_DIR)]}))
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("GIT_", "BEDDEL_", "PYTHON"))
    }
    env.update(
        {"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"), **extra_env}
    )
    return subprocess.run(
        [*_beddel_argv(), "run", "-i", f"repo_path={repo_path}", str(WORKFLOW)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        timeout=60,
        check=False,
    )


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    return repo


def test_run_passes_preflight_on_git_repo(tmp_path: Path) -> None:
    result = _run(str(_git_repo(tmp_path)), tmp_path)
    assert result.returncode == 0, result.stderr
    assert "'tool': 'profile_preflight'" in result.stdout
    assert "'ok': True" in result.stdout


def test_run_fails_closed_on_non_repository(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    result = _run(str(plain), tmp_path)
    assert result.returncode != 0
    assert "Step 'preflight' failed" in result.stderr
    assert "profile preflight failed: repo.git_work_tree" in result.stderr


def test_run_fails_closed_on_empty_repo_path(tmp_path: Path) -> None:
    result = _run("", tmp_path)
    assert result.returncode != 0
    assert (
        "profile preflight failed: repo.exists, repo.is_dir, repo.git_work_tree"
        in result.stderr
    )


def test_inherited_git_dir_cannot_redirect_the_check(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    plain = tmp_path / "plain"
    plain.mkdir()
    # _run keeps GIT_* out of the child env; set one explicitly to prove the
    # tool itself ignores it.
    result = _run(str(plain), tmp_path, GIT_DIR=str(repo / ".git"))
    assert result.returncode != 0
    assert "repo.git_work_tree" in result.stderr
