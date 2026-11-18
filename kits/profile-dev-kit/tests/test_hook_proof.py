from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest
from beddel_profile_dev.hook_proof import (
    count_log,
    null_keys,
    pointer_path,
    policy_path,
)
from beddel_profile_dev.tools.hook import (
    profile_hook_arm,
    profile_hook_disarm,
    profile_hook_open,
    profile_hook_proof,
)
from beddel_profile_dev.tools.stage_outcome import profile_record_stage_outcome

from ._helpers import commit_all, emit_hook_events, init_repo

STORY = "8-2-hook-proof-fixture"


def _repo(tmp_path: Path) -> Path:
    repo = init_repo(tmp_path / "repo")
    (repo / "story.md").write_text("story\n")
    commit_all(repo)
    return repo


def _settled(stage: str = "implement") -> dict[str, Any]:
    return {
        "stage": stage,
        "story_key": STORY,
        "outcome": "succeeded",
        "reason": "unit.committed",
        "refs": {"base": "a" * 40},
    }


def _open_arm(
    repo: Path, stage: str = "implement"
) -> tuple[dict[str, Any], dict[str, Any]]:
    opened = profile_hook_open(stage)
    assert opened["ok"] is True
    armed = profile_hook_arm(str(repo), stage, opened)
    assert armed["armed"] is True
    return opened, armed


def test_run_pointer_lifecycle_and_foreign_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(repo)
    first, armed = _open_arm(repo)
    second = profile_hook_open("implement")
    assert first["run"] != second["run"]
    run, policy, pointer = (
        Path(first["run"]),
        Path(first["policy_path"]),
        pointer_path(repo),
    )
    assert stat.S_IMODE(run.stat().st_mode) == 0o700
    assert stat.S_IMODE(policy.stat().st_mode) == 0o600
    assert policy.read_bytes() == policy_path("implement").read_bytes()
    assert first["policy_sha256"] == hashlib.sha256(policy.read_bytes()).hexdigest()
    assert (
        profile_hook_arm(str(repo), "implement", first)["reason"]
        == "hooks.pointer_exists"
    )
    emit_hook_events(
        repo,
        [
            {
                "hook_event_name": "pre",
                "tool_name": "shell",
                "tool_input": {"command": c},
            }
            for c in ("git push origin x", "gh pr merge 1", "ls")
        ]
        + ["stop"],
    )
    proof = profile_hook_proof("implement", first, [armed], _settled())
    assert (proof["outcome"], proof["refs"]["hook_denied"]) == ("succeeded", 2)
    policies = [
        json.loads(policy_path(stage).read_text())
        for stage in ("plan", "implement", "verify-and-fix")
    ]
    assert policies[0]["rules"] == policies[1]["rules"] == policies[2]["rules"]
    assert [policy["max_tool_calls"] for policy in policies] == [200, 400, 400]
    assert all(
        x in Path(first["log_path"]).read_text()
        for x in ("shell.git-push", "shell.gh-pr-merge", "shell.any")
    )
    pointer.write_bytes(b"foreign\n")
    assert profile_hook_disarm(str(repo), armed) == {"removed": False}
    assert pointer.read_bytes() == b"foreign\n"


def test_missing_stop_log_and_hook_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(repo)
    opened, armed = _open_arm(repo)
    emit_hook_events(repo, ["pre", "post"])
    profile_hook_disarm(str(repo), armed)
    result = profile_hook_proof("implement", opened, [armed], _settled())
    assert result["reason"] == "hooks.missing" and result["refs"]["hook_stop"] == 0

    opened, armed = _open_arm(repo, "plan")
    profile_hook_disarm(str(repo), armed)
    result = profile_hook_proof("plan", opened, [armed], _settled("plan"))
    assert result["reason"] == "hooks.missing" and result["refs"] == {
        **_settled("plan")["refs"],
        **null_keys(),
    }

    opened, armed = _open_arm(repo)
    emit_hook_events(repo, [{"hook_event_name": "unknown"}, "stop"])
    profile_hook_disarm(str(repo), armed)
    result = profile_hook_proof("implement", opened, [armed], _settled())
    assert result["reason"] == "hooks.errors" and result["refs"]["hook_errors"] == 1
    log = Path(str(opened["log_path"]))
    log.write_bytes(
        log.read_bytes() + b"not-json\n" + b"[" * 5000 + b"]" * 5000 + b"\n"
    )
    os.chmod(log, 0o600)
    counts = count_log(log)
    assert counts is not None and counts["hook_errors"] == 3
    insecure = log.parent / "insecure"
    insecure.write_text("{}\n")
    os.chmod(insecure, 0o644)
    assert count_log(insecure) is None
    oversized = log.parent / "oversized"
    oversized.write_bytes(b"x" * (8 * 1024 * 1024 + 1))
    os.chmod(oversized, 0o600)
    assert count_log(oversized) is None
    link = log.parent / "link"
    link.symlink_to(oversized)
    assert count_log(link) is None


def test_digest_sessions_cleanup_and_record_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(repo)
    opened, armed = _open_arm(repo)
    emit_hook_events(
        repo,
        [
            {"hook_event_name": "stop", "session_id": "s" * 60 + str(i)}
            for i in range(10)
        ],
    )
    log = Path(str(opened["log_path"]))
    counts = count_log(log, opened["policy_sha256"])
    assert counts is not None and len(counts["kiro_session"]) <= 512
    raw = json.loads(log.read_text().splitlines()[0])
    raw["policy_sha256"] = "0" * 64
    log.write_text(json.dumps(raw) + "\n")
    checked = count_log(log, opened["policy_sha256"])
    assert checked is not None and checked["hook_errors"] == 1
    assert profile_hook_disarm(str(repo), armed)["removed"] is True
    refs = {**_settled()["refs"], **counts}
    assert profile_record_stage_outcome(
        str(repo), STORY, "implement", "succeeded", "unit.committed", refs
    )["ok"]
    assert sorted(path.name for path in repo.iterdir()) == [".git", "story.md"]

    opened = profile_hook_open("implement")
    original = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("x")))
    refused = profile_hook_arm(str(repo), "implement", opened)
    monkeypatch.setattr(os, "fsync", original)
    assert not refused["armed"] and not pointer_path(repo).exists()


def test_tracked_policies_declare_cap_and_cap_denials_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook_path = (
        Path(__file__).resolve().parents[2]
        / "agent-kiro-kit"
        / "python"
        / "beddel_agent_kiro"
        / "hook.py"
    )
    spec = importlib.util.spec_from_file_location("hook_cap_test", hook_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for stage in ("plan", "implement", "verify-and-fix"):
        data = json.loads(policy_path(stage).read_text())
        assert type(data["max_tool_calls"]) is int and data["max_tool_calls"] > 0
        module._validate_policy(data)

    cap_policy = tmp_path / "cap-2.json"
    policy = json.loads(policy_path("implement").read_text())
    policy["max_tool_calls"] = 2
    cap_policy.write_text(json.dumps(policy))
    cap_policy.chmod(0o600)
    import beddel_profile_dev.hook_proof as proof_module

    monkeypatch.setattr(proof_module, "policy_path", lambda _stage: cap_policy)
    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)
    opened, armed = _open_arm(repo)
    emit_hook_events(repo, ["pre", "pre", "pre", "stop"])
    profile_hook_disarm(str(repo), armed)
    proof = profile_hook_proof("implement", opened, [armed], _settled())
    assert proof["outcome"] == "succeeded"
    assert proof["refs"]["hook_denied"] == 1
    assert set(proof["refs"]) == set({**_settled()["refs"], **null_keys()})
