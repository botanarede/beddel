from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from beddel_profile_dev._io import canonical_json
from beddel_profile_dev.tools.stage_outcome import profile_record_stage_outcome
from beddel_profile_dev.tools.summary import profile_read_delivery_summary

from ._helpers import commit_all, init_repo, records_root_for
from .test_run_cli import _beddel_argv

KIT_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = KIT_ROOT / "workflows" / "read-delivery-summary.yaml"
STORY = "8-7-summary-fixture"


def _repo(tmp_path: Path) -> Path:
    repo = init_repo(tmp_path / "repo")
    (repo / "story.md").write_text("story\n")
    commit_all(repo)
    return repo


def _record(repo: Path, stage: str, refs: dict[str, object]) -> None:
    profile_record_stage_outcome(
        str(repo), STORY, stage, "succeeded", "stage.complete", refs
    )


def _complete(repo: Path) -> Path:
    hooks = {"hook_stop": 2, "hook_denied": 1}
    _record(repo, "plan", {**hooks})
    _record(repo, "implement", {"hook_stop": 3, "hook_denied": 0})
    _record(
        repo, "verify-and-fix", {"hook_stop": 1, "hook_denied": 0, "change_id": "c1"}
    )
    _record(repo, "approval", {})
    _record(repo, "integrate", {})
    _record(repo, "deliver", {"first_record": 1})
    root = records_root_for(repo)
    revision = "a" * 40
    report = {
        "schema": "profile-dev/verification-report/1",
        "record": 1,
        "change_id": "c1",
        "revision": revision,
        "attempt": 1,
    }
    report_path = root / "changes" / "c1" / "report" / "1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_bytes(canonical_json(report))
    gate = {
        "schema": "profile-dev/attempt-gate-outcome/1",
        "attempt": 1,
        "output_attempt": 1,
        "change_id": "c1",
        "revision": revision,
        "inventory_version": "v1",
        "inventory_sha256": "b" * 64,
        "status": "completed",
        "commands": [
            {
                "name": "01-ruff",
                "argv": ["ruff", "check", "."],
                "exit_code": 0,
                "timed_out": False,
            },
            {
                "name": "02-pytest",
                "argv": ["pytest", "-q"],
                "exit_code": None,
                "timed_out": True,
            },
        ],
        "gate_ref": "changes/c1/revisions/" + revision + "/gate-output/1",
    }
    gate_path = (
        root
        / "changes"
        / "c1"
        / "revisions"
        / revision
        / "attempts"
        / "1"
        / "gate.json"
    )
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_bytes(canonical_json(gate))
    return root


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(relative)
        if path.is_dir():
            digest.update(b"/")
        elif path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_complete_records_summary_has_values_and_totals(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _complete(repo)
    summary = profile_read_delivery_summary(str(repo), STORY)
    verify = next(row for row in summary["stages"] if row["stage"] == "verify-and-fix")
    assert verify["records"] == [3]
    assert verify["agent_calls"] == 1
    assert verify["denied_calls"] == 0
    assert verify["review_rounds"] == 1
    assert verify["gate_exit_codes"] == [
        {"report": 1, "commands": {"01-ruff": 0, "02-pytest": "timeout"}}
    ]
    assert all(
        row["kiro_credits"] == "not observable" and row["tokens"] == "not observable"
        for row in summary["stages"]
    )
    assert summary["total"]["agent_calls"] == 6
    assert summary["total"]["denied_calls"] == 1
    assert summary["missing"] == ["plan.wall_seconds"]


def test_missing_records_and_fields_are_reported(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _record(repo, "plan", {"hook_stop": 1, "hook_denied": 0})
    _record(repo, "verify-and-fix", {})
    _record(repo, "deliver", {"first_record": 1})
    summary = profile_read_delivery_summary(str(repo), STORY)
    implement = next(row for row in summary["stages"] if row["stage"] == "implement")
    verify = next(row for row in summary["stages"] if row["stage"] == "verify-and-fix")
    assert all(
        implement[field] == "missing"
        for field in (
            "wall_seconds",
            "agent_calls",
            "denied_calls",
            "review_rounds",
            "gate_exit_codes",
        )
    )
    assert verify["agent_calls"] == "missing"
    assert verify["review_rounds"] == "missing"
    assert verify["gate_exit_codes"] == "missing"
    assert "implement.wall_seconds" in summary["missing"]
    assert summary["total"]["agent_calls"] == "missing"
    assert summary["stages"][0]["kiro_credits"] == "not observable"


def test_cli_summary_does_not_change_records(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = _repo(tmp_path)
    root = _complete(repo)
    before = _tree_digest(root)
    config_dir = home / ".config" / "beddel"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps({"kits_paths": [str(KIT_ROOT.parent)]})
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GIT_", "BEDDEL_", "PYTHON")) and key != "KIRO_API_KEY"
    }
    env.update({"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")})
    result = subprocess.run(
        [
            *_beddel_argv(),
            "run",
            "--json-output",
            "-i",
            f"repo_path={repo}",
            "-i",
            f"story_key={STORY}",
            str(WORKFLOW),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "not observable" in result.stdout
    assert "8-7-summary-fixture" in result.stdout
    assert _tree_digest(root) == before
