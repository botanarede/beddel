from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest
from beddel_profile_dev._errors import PROFILE_REPOSITORY_INVALID, ProfileError
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


def _record(
    repo: Path,
    stage: str,
    refs: dict[str, object],
    *,
    reason: str = "stage.complete",
    recorded_at: str | None = None,
) -> None:
    result = profile_record_stage_outcome(
        str(repo), STORY, stage, "succeeded", reason, refs
    )
    if recorded_at is not None:
        path = records_root_for(repo) / result["path"]
        data = json.loads(path.read_text())
        data["recorded_at"] = recorded_at
        path.write_bytes(canonical_json(data))


def _complete(repo: Path) -> Path:
    hooks = {"hook_stop": 2, "hook_denied": 1}
    _record(
        repo,
        "plan",
        {**hooks},
        recorded_at="2026-01-01T00:00:10Z",
    )
    _record(
        repo,
        "implement",
        {"hook_stop": 3, "hook_denied": 0},
        recorded_at="2026-01-01T00:00:20Z",
    )
    _record(
        repo,
        "verify-and-fix",
        {"hook_stop": 1, "hook_denied": 0, "change_id": "c1"},
        recorded_at="2026-01-01T00:00:30Z",
    )
    _record(repo, "approval", {}, recorded_at="2026-01-01T00:00:40Z")
    _record(repo, "integrate", {}, recorded_at="2026-01-01T00:00:50Z")
    _record(
        repo,
        "deliver",
        {"first_record": 1},
        recorded_at="2026-01-01T00:01:20Z",
    )
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
    rows = {row["stage"]: row for row in summary["stages"]}
    assert {
        stage: {
            "records": row["records"],
            "wall_seconds": row["wall_seconds"],
            "agent_calls": row["agent_calls"],
            "denied_calls": row["denied_calls"],
            "review_rounds": row["review_rounds"],
            "gate_exit_codes": row["gate_exit_codes"],
        }
        for stage, row in rows.items()
    } == {
        "plan": {
            "records": [1],
            "wall_seconds": "missing",
            "agent_calls": 2,
            "denied_calls": 1,
            "review_rounds": 0,
            "gate_exit_codes": [],
        },
        "implement": {
            "records": [2],
            "wall_seconds": 10,
            "agent_calls": 3,
            "denied_calls": 0,
            "review_rounds": 0,
            "gate_exit_codes": [],
        },
        "verify-and-fix": {
            "records": [3],
            "wall_seconds": 10,
            "agent_calls": 1,
            "denied_calls": 0,
            "review_rounds": 1,
            "gate_exit_codes": [
                {
                    "change_id": "c1",
                    "report": 1,
                    "commands": {"01-ruff": 0, "02-pytest": "timeout"},
                }
            ],
        },
        "approval": {
            "records": [4],
            "wall_seconds": 10,
            "agent_calls": 0,
            "denied_calls": 0,
            "review_rounds": 0,
            "gate_exit_codes": [],
        },
        "integrate": {
            "records": [5],
            "wall_seconds": 10,
            "agent_calls": 0,
            "denied_calls": 0,
            "review_rounds": 0,
            "gate_exit_codes": [],
        },
        "deliver": {
            "records": [6],
            "wall_seconds": 30,
            "agent_calls": 0,
            "denied_calls": 0,
            "review_rounds": 0,
            "gate_exit_codes": [],
        },
    }
    assert all(
        row["kiro_credits"] == "not observable" and row["tokens"] == "not observable"
        for row in summary["stages"]
    )
    assert summary["total"] == {
        "wall_seconds": "missing",
        "agent_calls": 6,
        "denied_calls": 1,
        "review_rounds": 1,
        "gate_exit_codes": [
            {
                "change_id": "c1",
                "report": 1,
                "commands": {"01-ruff": 0, "02-pytest": "timeout"},
            }
        ],
        "kiro_credits": "not observable",
        "tokens": "not observable",
    }
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
    output = json.loads(result.stdout)
    summary = output["summary"]["result"]
    rows = {row["stage"]: row for row in summary["stages"]}
    assert rows["deliver"]["wall_seconds"] == 30
    assert rows["verify-and-fix"]["review_rounds"] == 1
    assert summary["total"]["gate_exit_codes"][0]["change_id"] == "c1"
    assert summary["total"]["gate_exit_codes"][0]["commands"]["01-ruff"] == 0
    assert _tree_digest(root) == before


def test_hook_null_reason_controls_missing_vs_zero(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _record(
        repo, "plan", {"hook_stop": None, "hook_denied": None}, reason="hooks.missing"
    )
    _record(repo, "implement", {"hook_stop": None, "hook_denied": None})
    summary = profile_read_delivery_summary(str(repo), STORY)
    rows = {row["stage"]: row for row in summary["stages"]}
    assert rows["plan"]["agent_calls"] == "missing"
    assert rows["plan"]["denied_calls"] == "missing"
    assert rows["implement"]["agent_calls"] == 0
    assert rows["implement"]["denied_calls"] == 0


def test_absent_gate_with_report_is_missing_but_report_is_counted(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    root = _complete(repo)
    gate_path = (
        root
        / "changes"
        / "c1"
        / "revisions"
        / ("a" * 40)
        / "attempts"
        / "1"
        / "gate.json"
    )
    gate_path.unlink()
    summary = profile_read_delivery_summary(str(repo), STORY)
    verify = next(row for row in summary["stages"] if row["stage"] == "verify-and-fix")
    assert verify["review_rounds"] == 1
    assert verify["gate_exit_codes"] == "missing"
    assert summary["total"]["review_rounds"] == 1
    assert summary["total"]["gate_exit_codes"] == "missing"


def test_record_outside_closed_run_has_missing_wall_time(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _record(
        repo,
        "plan",
        {"hook_stop": 1, "hook_denied": 0},
        recorded_at="2026-01-01T00:00:10Z",
    )
    _record(repo, "deliver", {"first_record": 1}, recorded_at="2026-01-01T00:00:20Z")
    _record(
        repo,
        "plan",
        {"hook_stop": 1, "hook_denied": 0},
        recorded_at="2026-01-01T00:00:30Z",
    )
    summary = profile_read_delivery_summary(str(repo), STORY)
    plan = next(row for row in summary["stages"] if row["stage"] == "plan")
    assert plan["records"] == [1, 3]
    assert plan["wall_seconds"] == "missing"


def test_malformed_gate_outcome_fails_closed_without_writing(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    root = _complete(repo)
    gate_path = (
        root
        / "changes"
        / "c1"
        / "revisions"
        / ("a" * 40)
        / "attempts"
        / "1"
        / "gate.json"
    )
    gate_path.write_text("{}")
    before = _tree_digest(root)
    with pytest.raises(ProfileError) as error:
        profile_read_delivery_summary(str(repo), STORY)
    assert error.value.code == PROFILE_REPOSITORY_INVALID
    assert _tree_digest(root) == before


def test_malformed_stage_outcome_fails_closed_without_writing(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    root = _complete(repo)
    stage_files = sorted((root / "stage-outcomes").rglob("*.json"))
    assert stage_files
    stage_files[0].write_text("{")
    before = _tree_digest(root)
    with pytest.raises(ProfileError) as error:
        profile_read_delivery_summary(str(repo), STORY)
    assert error.value.code == PROFILE_REPOSITORY_INVALID
    assert _tree_digest(root) == before
