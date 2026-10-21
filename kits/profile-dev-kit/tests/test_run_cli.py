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
DECLARE = KIT_ROOT / "workflows" / "declare-non-applicability.yaml"
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
    change_id: str = "c1",
    base: str = "HEAD",
    **extra_env: str,
) -> subprocess.CompletedProcess[str]:
    return _run_workflow(
        WORKFLOW,
        {
            "repo_path": repo_path,
            "change_id": change_id,
            "base": base,
            "revision": revision,
            "inventory_version": version,
        },
        tmp_path,
        **extra_env,
    )


def _declare(
    repo: Path,
    tmp_path: Path,
    revision: str,
    point: str,
    actor: str = "Fixture Owner",
) -> subprocess.CompletedProcess[str]:
    return _run_workflow(
        DECLARE,
        {
            "repo_path": str(repo),
            "revision": revision,
            "class_id": "gate-unit",
            "affected_point_id": point,
            "criterion_id": "tests-pass",
            "actor": actor,
        },
        tmp_path,
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


def test_ratify_then_verify_change_passes_all_four_steps(tmp_path: Path) -> None:
    repo = _fixture(tmp_path)
    _ratify(repo, tmp_path)
    base = commit_all(repo)
    (repo / "src" / "api.py").write_text("x = 2\n")
    sha = commit_all(repo, "change")
    result = _run(str(repo), tmp_path, revision=sha, base=base)
    assert result.returncode == 0, result.stderr
    for tool in (
        "profile_preflight",
        "profile_record_change",
        "profile_bind_inventory",
        "profile_derive_impact",
    ):
        assert f"'tool': '{tool}'" in result.stdout
    assert (repo / RECORDS / "revisions" / sha / "snapshot.json").is_file()
    impact = json.loads(
        (
            repo / RECORDS / "changes" / "c1" / "revisions" / sha / "impact.json"
        ).read_text()
    )
    assert impact["footprint"] == ["src/api.py"]
    assert [p["id"] for p in impact["affected_points"]] == ["api"]
    assert len(impact["required_evidence"]) == 2


def test_block_then_fix_commit_discharges_the_earlier_block(tmp_path: Path) -> None:
    broken = good()
    broken["obligations"][0]["class"] = "ghost"
    repo = _fixture(tmp_path, broken)
    _ratify(repo, tmp_path)
    base = commit_all(repo)
    (repo / "src" / "api.py").write_text("x = 2\n")
    first = commit_all(repo, "change")
    blocked = _run(str(repo), tmp_path, revision=first, base=base)
    assert blocked.returncode != 0
    assert "Step 'bind_inventory' failed" in blocked.stderr
    change_dir = repo / RECORDS / "changes" / "c1"
    assert (change_dir / "change.json").is_file()
    assert (change_dir / "revisions" / first / "revision.json").is_file()
    assert not (change_dir / "revisions" / first / "impact.json").exists()

    write_version(repo, "v2", good("v2"))
    _ratify(repo, tmp_path, "v2")
    second = commit_all(repo, "fix")
    fixed = _run(str(repo), tmp_path, revision=second, base=base, version="v2")
    assert fixed.returncode == 0, fixed.stderr
    assert (change_dir / "revisions" / second / "impact.json").is_file()
    blocks = repo / RECORDS / "revisions" / first / "integrity-blocks"
    discharged = list(blocks.glob("*.discharged.json"))
    assert len(discharged) == 1
    record = json.loads(discharged[0].read_text())
    assert record["schema"] == "profile-dev/integrity-discharge-by-revision/1"
    assert record["resolved_by_revision"] == second
    assert len(list(blocks.glob("*.json"))) == 2


def test_declare_non_applicability_for_deleted_component_only(tmp_path: Path) -> None:
    repo = _fixture(tmp_path)
    _ratify(repo, tmp_path)
    base = commit_all(repo)
    (repo / "src" / "contracts.yaml").unlink()
    sha = commit_all(repo, "delete contract")
    assert _run(str(repo), tmp_path, revision=sha, base=base).returncode == 0
    impact_path = repo / RECORDS / "changes" / "c1" / "revisions" / sha / "impact.json"
    before = impact_path.read_bytes()

    declared = _declare(repo, tmp_path, sha, "contracts")
    assert declared.returncode == 0, declared.stderr
    record = (
        repo
        / RECORDS
        / "revisions"
        / sha
        / "non-applicability"
        / "gate-unit+contracts+tests-pass.json"
    )
    assert json.loads(record.read_text())["determined_by"] == "Fixture Owner"
    assert impact_path.read_bytes() == before

    present = _declare(repo, tmp_path, sha, "api")
    assert present.returncode != 0
    assert "target.present" in present.stderr
    again = _declare(repo, tmp_path, sha, "contracts")
    assert again.returncode != 0
    assert "determination.exists" in again.stderr


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


def test_unratified_version_stops_at_bind_inventory_and_writes_no_impact(
    tmp_path: Path,
) -> None:
    repo = _fixture(tmp_path)
    base = commit_all(repo)
    (repo / "src" / "api.py").write_text("x = 2\n")
    sha = commit_all(repo, "change")
    result = _run(str(repo), tmp_path, revision=sha, base=base)
    assert result.returncode != 0
    assert "Step 'bind_inventory' failed" in result.stderr
    assert "no ratified inventory version" in result.stderr
    assert not (repo / RECORDS / "revisions").exists()
    assert not (
        repo / RECORDS / "changes" / "c1" / "revisions" / sha / "impact.json"
    ).exists()
