"""AC11: run the entry workflows through the real ``beddel run`` CLI, hermetically."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ._helpers import commit_all, good, init_repo, make_source, write_version

KIT_ROOT = Path(__file__).resolve().parent.parent
KITS_DIR = KIT_ROOT.parent
WORKFLOW = KIT_ROOT / "workflows" / "verify-change.yaml"
RATIFY = KIT_ROOT / "workflows" / "ratify-inventory.yaml"
RECORDS = ".beddel-profile/records"


def _beddel_argv() -> list[str]:
    """Prefer the console script next to this interpreter; never skip."""
    console_script = Path(sys.executable).parent / "beddel"
    if console_script.is_file():
        return [str(console_script)]
    return [sys.executable, "-c", "from beddel.cli import main; main()"]


def _run_workflow(
    workflow: Path,
    inputs: dict[str, str],
    tmp_path: Path,
    **extra_env: str,
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
    args = [arg for k, v in inputs.items() for arg in ("-i", f"{k}={v}")]
    return subprocess.run(
        [*_beddel_argv(), "run", *args, str(workflow)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        timeout=60,
        check=False,
    )


def _run(
    repo_path: str,
    tmp_path: Path,
    revision: str = "HEAD",
    version: str = "v1",
    **extra_env: str,
) -> subprocess.CompletedProcess[str]:
    return _run_workflow(
        WORKFLOW,
        {"repo_path": repo_path, "revision": revision, "inventory_version": version},
        tmp_path,
        **extra_env,
    )


def _ratify(repo: Path, tmp_path: Path, version: str = "v1") -> None:
    result = _run_workflow(
        RATIFY,
        {
            "repo_path": str(repo),
            "inventory_version": version,
            "actor": "Fixture Owner",
        },
        tmp_path,
    )
    assert result.returncode == 0, result.stderr


def _fixture(tmp_path: Path, data: object = None) -> Path:
    repo = init_repo(tmp_path / "repo")
    make_source(repo)
    write_version(repo, "v1", good() if data is None else data)
    return repo


def test_ratify_then_verify_change_passes_both_steps(tmp_path: Path) -> None:
    repo = _fixture(tmp_path)
    _ratify(repo, tmp_path)
    sha = commit_all(repo)
    result = _run(str(repo), tmp_path)
    assert result.returncode == 0, result.stderr
    assert "'tool': 'profile_preflight'" in result.stdout
    assert "'tool': 'profile_bind_inventory'" in result.stdout
    assert (repo / RECORDS / "revisions" / sha / "snapshot.json").is_file()


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
    repo = init_repo(tmp_path / "repo")
    plain = tmp_path / "plain"
    plain.mkdir()
    # _run keeps GIT_* out of the child env; set one explicitly to prove the
    # tool itself ignores it.
    result = _run(str(plain), tmp_path, GIT_DIR=str(repo / ".git"))
    assert result.returncode != 0
    assert "repo.git_work_tree" in result.stderr


def test_integrity_block_stops_at_bind_inventory_and_leaves_the_record(
    tmp_path: Path,
) -> None:
    data = good()
    data["obligations"][0]["class"] = "ghost"
    repo = _fixture(tmp_path, data)
    _ratify(repo, tmp_path)
    sha = commit_all(repo)
    result = _run(str(repo), tmp_path)
    assert result.returncode != 0
    assert "Step 'bind_inventory' failed" in result.stderr
    assert "PROFILE_INVENTORY_INTEGRITY_BLOCK" in result.stderr or (
        "inventory integrity block: ref.class_unresolved" in result.stderr
    )
    blocks = list((repo / RECORDS / "revisions" / sha / "integrity-blocks").glob("*"))
    assert len(blocks) == 1
    assert not (repo / RECORDS / "revisions" / sha / "snapshot.json").exists()


def test_unratified_version_stops_at_bind_inventory_and_writes_nothing(
    tmp_path: Path,
) -> None:
    repo = _fixture(tmp_path)
    commit_all(repo)
    result = _run(str(repo), tmp_path)
    assert result.returncode != 0
    assert "Step 'bind_inventory' failed" in result.stderr
    assert "no ratified inventory version" in result.stderr
    assert not (repo / ".beddel-profile" / "records").exists()
