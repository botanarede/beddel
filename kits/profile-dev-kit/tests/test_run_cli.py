"""AC11: run the entry workflows through the real ``beddel run`` CLI, hermetically."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ._helpers import (
    commit_all,
    fake_review_env,
    good,
    init_repo,
    make_source,
    stub_gate_tools,
    write_version,
)

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
    kits_dir: Path = KITS_DIR,
    **extra_env: str,
) -> subprocess.CompletedProcess[str]:
    # Throw-away HOME whose config points kits_paths at this checkout, so the
    # user's global config cannot shadow the kit under test and no PYTHONPATH
    # is needed (configured kit paths are put on sys.path by the core).
    home = tmp_path / "home"
    config_dir = home / ".config" / "beddel"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(json.dumps({"kits_paths": [str(kits_dir)]}))
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("GIT_", "BEDDEL_", "PYTHON")) and k != "KIRO_API_KEY"
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
    kits_dir: Path = KITS_DIR,
    review_mode: str = "completed",
    **extra_env: str,
) -> subprocess.CompletedProcess[str]:
    # The Gate runs the default command list: keep it fast and hermetic. The
    # Review route is always faked through the adapter seam: the real route is
    # never reachable from a test, even though the real PATH is inherited.
    kit_python = kits_dir / "profile-dev-kit" / "python"
    extra_env = {
        "PATH": stub_gate_tools(tmp_path),
        **fake_review_env(tmp_path, kit_python, review_mode),
        **extra_env,
    }
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
        kits_dir,
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


def test_ratify_then_verify_change_passes_all_six_steps(tmp_path: Path) -> None:
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
        "profile_run_gate",
        "profile_run_review",
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


def _gate_json(repo: Path, sha: str) -> dict[str, object]:
    path = repo / RECORDS / "changes" / "c1" / "revisions" / sha / "gate.json"
    data = json.loads(path.read_text())
    assert isinstance(data, dict)
    return data


def test_verify_change_records_a_non_zero_gate_exit_as_a_result(
    tmp_path: Path,
) -> None:
    repo = _fixture(tmp_path)
    _ratify(repo, tmp_path)
    base = commit_all(repo)
    (repo / "src" / "api.py").write_text("x = 2\n")
    sha = commit_all(repo, "change")
    result = _run(str(repo), tmp_path, revision=sha, base=base, STUB_EXIT_PYTEST="1")
    assert result.returncode == 0, result.stderr  # a non-zero exit is not an error
    gate = _gate_json(repo, sha)
    assert gate["status"] == "completed"
    commands = gate["commands"]
    assert isinstance(commands, list)
    assert [c["exit_code"] for c in commands] == [0, 0, 0, 1]
    assert [c["timed_out"] for c in commands] == [False] * 4
    output = repo / RECORDS / "changes" / "c1" / "revisions" / sha / "gate-output" / "1"
    assert (output / "04-pytest.stdout.txt").read_text() == "stub -q\n"


def test_rerunning_verify_change_appends_a_gate_attempt(tmp_path: Path) -> None:
    repo = _fixture(tmp_path)
    _ratify(repo, tmp_path)
    base = commit_all(repo)
    (repo / "src" / "api.py").write_text("x = 2\n")
    sha = commit_all(repo, "change")
    assert _run(str(repo), tmp_path, revision=sha, base=base).returncode == 0
    second = _run(str(repo), tmp_path, revision=sha, base=base, STUB_EXIT_RUFF="2")
    assert second.returncode == 0, second.stderr
    gate = _gate_json(repo, sha)
    assert str(gate["gate_ref"]).endswith("/gate-output/2")
    output = repo / RECORDS / "changes" / "c1" / "revisions" / sha / "gate-output"
    assert sorted(p.name for p in output.iterdir()) == ["1", "2"]


def _kit_copy(tmp_path: Path, *replacements: tuple[str, str]) -> Path:
    """Copy the kit under ``tmp_path`` with an edited ``config.py``; return its dir.

    The Gate constants are not injectable into the CLI subprocess, so a test
    that needs another command list or budget runs the real CLI over this copy.
    """
    kits = tmp_path / "kits"
    shutil.copytree(
        KIT_ROOT,
        kits / "profile-dev-kit",
        ignore=shutil.ignore_patterns("__pycache__", "tests", ".*", "*.egg-info"),
    )
    config = kits / "profile-dev-kit" / "python" / "beddel_profile_dev" / "config.py"
    text = config.read_text()
    for old, new in replacements:
        assert old in text
        text = text.replace(old, new)
    config.write_text(text)
    return kits


def _committed_change(tmp_path: Path) -> tuple[Path, str, str]:
    repo = _fixture(tmp_path)
    _ratify(repo, tmp_path)
    base = commit_all(repo)
    (repo / "src" / "api.py").write_text("x = 2\n")
    return repo, base, commit_all(repo, "change")


def test_verify_change_records_a_hanging_gate_command_as_timed_out(
    tmp_path: Path,
) -> None:
    repo, base, sha = _committed_change(tmp_path)
    kits = _kit_copy(
        tmp_path, ("GATE_TIMEOUT_SECONDS: int = 300", "GATE_TIMEOUT_SECONDS: int = 3")
    )
    result = _run(
        str(repo),
        tmp_path,
        revision=sha,
        base=base,
        kits_dir=kits,
        STUB_SLEEP_MYPY="60",
    )
    # A timeout is an outcome, not an error.
    assert result.returncode == 0, result.stderr
    commands = _gate_json(repo, sha)["commands"]
    assert isinstance(commands, list)
    assert [(c["exit_code"], c["timed_out"]) for c in commands] == [
        (0, False),
        (0, False),
        (None, True),
        (0, False),
    ]


def test_verify_change_refuses_a_gate_command_outside_the_allowlist(
    tmp_path: Path,
) -> None:
    repo, base, sha = _committed_change(tmp_path)
    kits = _kit_copy(tmp_path, ('("mypy", ".")', '("curl", "--version")'))
    result = _run(str(repo), tmp_path, revision=sha, base=base, kits_dir=kits)
    assert result.returncode != 0
    # Every tool loads the config first, so the refusal surfaces at the first step.
    assert "Step 'preflight' failed" in result.stderr
    assert "PROFILE_GATE_COMMAND_INVALID" in result.stderr
    assert "gate command executable is not allowed" in result.stderr
    revision_dir = repo / RECORDS / "changes" / "c1" / "revisions" / sha
    assert not (revision_dir / "gate.json").exists()
    assert not (revision_dir / "gate-output").exists()


def test_the_gate_step_alone_stops_without_an_impact_record(tmp_path: Path) -> None:
    repo, _, sha = _committed_change(tmp_path)
    workflow = tmp_path / "gate-only.yaml"
    workflow.write_text(
        "id: gate-only\n"
        "name: Gate only\n"
        "description: Runs the gate step without the earlier steps.\n"
        'version: "1.0"\n'
        "requires_kits:\n"
        "  - profile-dev-kit\n"
        "allowed_tools:\n"
        "  - profile_run_gate\n"
        "inputs:\n"
        "  - repo_path\n"
        "  - change_id\n"
        "  - revision\n"
        "steps:\n"
        "  - id: gate\n"
        "    primitive: tool\n"
        "    config:\n"
        "      tool: profile_run_gate\n"
        "      arguments:\n"
        '        repo_path: "$input.repo_path"\n'
        '        change_id: "$input.change_id"\n'
        '        revision: "$input.revision"\n'
    )
    result = _run_workflow(
        workflow,
        {"repo_path": str(repo), "change_id": "c1", "revision": sha},
        tmp_path,
        PATH=stub_gate_tools(tmp_path),
    )
    assert result.returncode != 0
    assert "Step 'gate' failed" in result.stderr
    assert "PROFILE_GATE_UNSCOPED" in result.stderr
    assert (
        "gate needs the impact record of the Change at this revision" in result.stderr
    )
    revision_dir = repo / RECORDS / "changes" / "c1" / "revisions" / sha
    assert not (revision_dir / "gate.json").exists()
    assert not (revision_dir / "gate-output").exists()


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


def _revision_dir(repo: Path, sha: str) -> Path:
    return repo / RECORDS / "changes" / "c1" / "revisions" / sha


def _review_json(repo: Path, sha: str) -> dict[str, object]:
    data = json.loads((_revision_dir(repo, sha) / "review.json").read_text())
    assert isinstance(data, dict)
    return data


def test_verify_change_records_a_completed_review_through_the_fake_route(
    tmp_path: Path,
) -> None:
    repo, base, sha = _committed_change(tmp_path)
    result = _run(str(repo), tmp_path, revision=sha, base=base)
    assert result.returncode == 0, result.stderr
    review = _review_json(repo, sha)
    assert review == {
        "schema": "profile-dev/review-outcome/1",
        "change_id": "c1",
        "revision": sha,
        "inventory_version": "v1",
        "inventory_sha256": review["inventory_sha256"],
        "agent": "kiro",
        "model": "claude-opus-4.5",
        "status": "completed",
        "review_ref": f"{RECORDS}/changes/c1/revisions/{sha}/review-output/1.txt",
    }
    output = _revision_dir(repo, sha) / "review-output" / "1.txt"
    assert output.read_text() == "canned review\n"
    calls = [
        json.loads(line)
        for line in (tmp_path / "review-calls.jsonl").read_text().splitlines()
    ]
    assert len(calls) == 1
    assert calls[0]["sandbox"] == "read-only"
    assert calls[0]["model"] == "claude-opus-4.5"
    assert calls[0]["tools"] is None
    assert calls[0]["api_key_in_env"] is False
    assert "+x = 2" in calls[0]["prompt"]
    assert '"id": "api"' in calls[0]["prompt"]


def test_verify_change_records_a_timed_out_review_as_a_result(tmp_path: Path) -> None:
    repo, base, sha = _committed_change(tmp_path)
    result = _run(str(repo), tmp_path, revision=sha, base=base, review_mode="timeout")
    assert result.returncode == 0, result.stderr  # a timeout is an outcome
    review = _review_json(repo, sha)
    assert review["status"] == "timed_out"
    assert review["error_code"] == "BEDDEL-AGENT-702"
    assert (_revision_dir(repo, sha) / "review-output" / "1.txt").read_text() == ""


def test_verify_change_records_a_failed_review_as_a_result(tmp_path: Path) -> None:
    repo, base, sha = _committed_change(tmp_path)
    result = _run(str(repo), tmp_path, revision=sha, base=base, review_mode="error")
    assert result.returncode == 0, result.stderr
    review = _review_json(repo, sha)
    assert review["status"] == "errored"
    assert review["error_code"] == "BEDDEL-AGENT-701"
    assert "fake failure" not in json.dumps(review)  # never the adapter's message


def test_an_ambient_api_key_stops_the_review_step_before_the_route(
    tmp_path: Path,
) -> None:
    repo, base, sha = _committed_change(tmp_path)
    result = _run(str(repo), tmp_path, revision=sha, base=base, KIRO_API_KEY="x")
    assert result.returncode != 0
    assert "Step 'review' failed" in result.stderr
    assert "PROFILE_REVIEW_UNSCOPED" in result.stderr
    assert not (_revision_dir(repo, sha) / "review.json").exists()
    assert not (tmp_path / "review-calls.jsonl").exists()  # the route was never called


def test_the_review_step_alone_stops_without_an_impact_record(tmp_path: Path) -> None:
    repo, _, sha = _committed_change(tmp_path)
    workflow = tmp_path / "review-only.yaml"
    workflow.write_text(
        "id: review-only\n"
        "name: Review only\n"
        "description: Runs the review step without the earlier steps.\n"
        'version: "1.0"\n'
        "requires_kits:\n"
        "  - profile-dev-kit\n"
        "allowed_tools:\n"
        "  - profile_run_review\n"
        "inputs:\n"
        "  - repo_path\n"
        "  - change_id\n"
        "  - revision\n"
        "steps:\n"
        "  - id: review\n"
        "    primitive: tool\n"
        "    config:\n"
        "      tool: profile_run_review\n"
        "      timeout: 960\n"
        "      arguments:\n"
        '        repo_path: "$input.repo_path"\n'
        '        change_id: "$input.change_id"\n'
        '        revision: "$input.revision"\n'
    )
    result = _run_workflow(
        workflow,
        {"repo_path": str(repo), "change_id": "c1", "revision": sha},
        tmp_path,
        **fake_review_env(tmp_path, KIT_ROOT / "python"),
    )
    assert result.returncode != 0
    assert "Step 'review' failed" in result.stderr
    assert "PROFILE_REVIEW_UNSCOPED" in result.stderr
    revision_dir = _revision_dir(repo, sha)
    assert not (revision_dir / "review.json").exists()
    assert not (revision_dir / "review-output").exists()
    assert not (tmp_path / "review-calls.jsonl").exists()  # the route was never called
