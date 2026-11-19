"""Tests for the policy hook, redacted log, and result summary."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from beddel_agent_kiro import hook

_OMIT_CAP = object()


def _setup(
    tmp_path: Path,
    rules: list[dict[str, Any]] | None = None,
    cap: Any = 100,
) -> tuple[Path, Path, Path]:
    pointers = tmp_path / "pointers"
    pointers.mkdir(parents=True, mode=0o700)
    policy_path, log_path = tmp_path / "policy.json", tmp_path / "events.jsonl"
    policy = {
        "schema": "beddel.kiro-hook-policy/1",
        "rules": rules
        or [
            {"id": "shell.any", "effect": "allow", "tool_class": "shell"},
            {"id": "read.any", "effect": "allow", "tool_class": "read"},
        ],
    }
    if cap is not _OMIT_CAP:
        policy["max_tool_calls"] = cap
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    os.chmod(policy_path, 0o600)
    pointer = hook.pointer_path(pointers, str(tmp_path))
    pointer.write_text(
        json.dumps(
            {"policy": str(policy_path), "log_path": str(log_path), "stage": "test"}
        ),
        encoding="utf-8",
    )
    os.chmod(pointer, 0o600)
    return pointers, policy_path, log_path


def _event(
    root: Path,
    tool: str = "shell",
    command: str | None = None,
    name: str = "preToolUse",
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "cwd": str(root),
        "hook_event_name": name,
        "tool_name": tool,
    }
    if command is not None:
        value["tool_input"] = {"command": command}
    return value


def _call(pointers: Path, payload: dict[str, Any]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    old_out, old_err = __import__("sys").stdout, __import__("sys").stderr
    try:
        __import__("sys").stdout, __import__("sys").stderr = out, err
        code = hook.main(
            ["--pointers", str(pointers)], io.StringIO(json.dumps(payload))
        )
    finally:
        __import__("sys").stdout, __import__("sys").stderr = old_out, old_err
    return code, out.getvalue(), err.getvalue()


@pytest.mark.parametrize(
    ("command", "rule"),
    [
        ("true\nblocked", "shell.blocked"),
        ("true|blocked", "shell.blocked"),
        ("true&blocked", "shell.blocked"),
        ("true||blocked", "shell.blocked"),
        ("true;blocked", "shell.blocked"),
        ("echo $(blocked)", "shell.substitution"),
        ("a&&blocked", "shell.blocked"),
        ("cat <(blocked)", "shell.substitution"),
        ("cat >(blocked)", "shell.substitution"),
        ("'unbalanced", "shell.parse"),
    ],
)
def test_shell_segments_and_substitutions_deny(
    tmp_path: Path, command: str, rule: str
) -> None:
    rules = [
        {
            "id": "shell.blocked",
            "effect": "deny",
            "tool_class": "shell",
            "argv_prefix": ["blocked"],
        },
        {"id": "shell.any", "effect": "allow", "tool_class": "shell"},
    ]
    pointers, _policy, log = _setup(tmp_path, rules)
    code, _out, err = _call(pointers, _event(tmp_path, command=command))
    assert code == 2 and f"beddel-kiro-hook: {rule}" in err
    assert command not in log.read_text(encoding="utf-8")


def test_allow_pointer_errors_and_no_command(tmp_path: Path) -> None:
    pointers, policy, log = _setup(tmp_path)
    assert _call(pointers, _event(tmp_path, command="true"))[0] == 0
    payload = _event(tmp_path)
    payload["tool_input"] = {"args": ["true"]}
    assert "shell.no_command" in _call(pointers, payload)[2]
    pointer = hook.pointer_path(pointers, str(tmp_path))
    before = log.read_bytes()
    pointer.unlink()
    assert _call(pointers, _event(tmp_path))[0] == 2 and log.read_bytes() == before
    pointers, policy, log = _setup(tmp_path / "invalid")
    policy.write_text("{}", encoding="utf-8")
    os.chmod(policy, 0o600)
    assert "policy.invalid" in _call(pointers, _event(policy.parent))[2]
    pointers, _policy, _log = _setup(tmp_path / "default")
    root = tmp_path / "default"
    code, _out, err = _call(pointers, _event(root, tool="other", command="x"))
    assert code == 2 and "policy.default_deny" in err
    assert hook.cmd_head("K=v x") is None
    assert hook.cmd_head("/usr/bin/Git") == "git"
    assert hook.cmd_head("cmd=git push") is None


def test_post_stop_redaction_schema_and_digest(tmp_path: Path) -> None:
    pointers, _policy, log = _setup(tmp_path)
    marker = "TOP-SECRET-PROMPT-MARKER"
    post = _event(tmp_path, command="printf x", name="postToolUse")
    post["tool_input"]["marker"] = marker
    post["tool_response"] = {"marker": marker}
    code, out, err = _call(pointers, post)
    assert code == 0 and marker not in out and marker not in err
    assert _call(pointers, _event(tmp_path, name="stop"))[0] == 0
    raw = log.read_text(encoding="utf-8")
    records = [json.loads(line) for line in raw.splitlines()]
    assert all(set(record) == set(hook._LOG_KEYS) for record in records)
    assert marker not in raw and records[0]["response_sha256"]
    assert records[1]["tool_name"] is None


def test_policy_schema_log_permissions_and_relative_path(tmp_path: Path) -> None:
    cases = (
        [
            {
                "id": "shell.empty",
                "effect": "allow",
                "tool_class": "shell",
                "argv_prefix": [],
            }
        ],
        [
            {"id": "shell.same", "effect": "allow", "tool_class": "shell"},
            {"id": "shell.same", "effect": "deny", "tool_class": "shell"},
        ],
    )
    for index, rules in enumerate(cases):
        root = tmp_path / str(index)
        pointers, _policy, log = _setup(root, rules)
        assert "policy.invalid" in _call(pointers, _event(root, command="true"))[2]
        assert log.exists()


def test_internal_and_pointer_error_rows(tmp_path: Path) -> None:
    pointers, policy, log = _setup(tmp_path)
    assert hook.main(["--pointers", str(pointers)], io.StringIO("{")) == 2
    assert _call(pointers, {"hook_event_name": "preToolUse"})[0] == 2
    assert _call(pointers, _event(tmp_path, command="true", name="other"))[0] == 2
    assert any(
        json.loads(line)["event"] == "unknown" for line in log.read_text().splitlines()
    )
    policy.chmod(0o622)
    code, _out, err = _call(pointers, _event(tmp_path, command="true"))
    assert code == 2 and "policy.invalid" in err
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert record["policy_sha256"]
    assert record["event"] == "pre"
    policy.chmod(0o600)
    before = (log.stat().st_mode, log.read_bytes())
    pointer = hook.pointer_path(pointers, str(tmp_path))
    pointer.chmod(0o622)
    assert "policy.invalid" in _call(pointers, _event(tmp_path, command="true"))[2]
    assert (log.stat().st_mode, log.read_bytes()) == before


@pytest.mark.parametrize("target", ["policy", "log"])
def test_fifo_paths_do_not_hang(tmp_path: Path, target: str) -> None:
    pointers, policy, log = _setup(tmp_path)
    fifo = tmp_path / f"{target}.fifo"
    os.mkfifo(fifo)
    if target == "policy":
        pointer_data = {"policy": str(fifo), "log_path": str(log), "stage": "test"}
    else:
        pointer_data = {"policy": str(policy), "log_path": str(fifo), "stage": "test"}
    hook.pointer_path(pointers, str(tmp_path)).write_text(
        json.dumps(pointer_data), encoding="utf-8"
    )
    command = [
        sys.executable,
        "-P",
        "-m",
        "beddel_agent_kiro.hook",
        "--pointers",
        str(pointers),
    ]
    env = {
        "PYTHONPATH": str(Path(__file__).resolve().parent.parent / "python"),
        "PATH": os.environ["PATH"],
    }
    completed = subprocess.run(
        command,
        input=json.dumps(_event(tmp_path, command="true")),
        text=True,
        capture_output=True,
        check=False,
        env=env,
        timeout=5,
    )
    assert completed.returncode == 2


def test_cap_max_tool_calls_denies_past_the_cap(tmp_path: Path) -> None:
    rules = [
        {
            "id": "shell.git-push",
            "effect": "deny",
            "tool_class": "shell",
            "argv_prefix": ["git", "push"],
        },
        {"id": "shell.any", "effect": "allow", "tool_class": "shell"},
    ]
    pointers, _policy, log = _setup(tmp_path, rules, cap=2)
    assert _call(pointers, _event(tmp_path, command="true"))[0] == 0
    assert _call(pointers, _event(tmp_path, command="true"))[0] == 0
    code, _out, err = _call(pointers, _event(tmp_path, command="git push origin x"))
    assert code == 2 and "cap.max_tool_calls" in err
    assert _call(pointers, _event(tmp_path, command="true", name="postToolUse"))[0] == 0
    assert _call(pointers, _event(tmp_path, name="stop"))[0] == 0
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert records[2]["decision"] == "deny"
    assert records[2]["rule_id"] == "cap.max_tool_calls"


@pytest.mark.parametrize("cap", [_OMIT_CAP, 0, -1, True, 1.5, "2", None])
def test_cap_missing_or_invalid_policy_denies(tmp_path: Path, cap: Any) -> None:
    pointers, _policy, log = _setup(tmp_path, cap=cap)
    code, _out, err = _call(pointers, _event(tmp_path, command="true"))
    assert code == 2 and "policy.invalid" in err
    code, _out, err = _call(pointers, _event(tmp_path, command="true"))
    assert code == 2 and "policy.invalid" in err
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert [record["rule_id"] for record in records] == [
        "policy.invalid",
        "policy.invalid",
    ]


def test_internal_error_past_the_cap_stays_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pointers, _policy, log = _setup(tmp_path, cap=1)
    assert _call(pointers, _event(tmp_path, command="true"))[0] == 0

    def fail(*_args: Any) -> tuple[str, str]:
        raise RuntimeError("test failure")

    monkeypatch.setattr(hook, "_evaluate", fail)
    code, _out, err = _call(pointers, _event(tmp_path, command="true"))
    assert code == 2 and "hook.internal" in err
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert records[-1]["decision"] == "error"
    assert records[-1]["rule_id"] == "hook.internal"
    summary = hook.summarize(pointers, tmp_path)
    assert summary["errors"] == 1 and summary["denied"] == 0


_PLAN_POLICY = (
    Path(__file__).resolve().parents[2] / "profile-dev-kit" / "policies" / "plan.json"
)


@pytest.mark.parametrize(
    ("name", "tool_class"),
    [
        *[
            (name, "read")
            for name in (
                "read",
                "fs_read",
                "glob",
                "grep",
                "code",
                "read_file",
                "read_files",
                "list_directory",
                "file_search",
                "grep_search",
                "disclose_context",
                "READ_FILE",
            )
        ],
        *[
            (name, "write")
            for name in ("write", "fs_write", "fs_append", "str_replace", "delete_file")
        ],
        *[
            (name, "shell")
            for name in ("shell", "execute_bash", "execute_cmd", "execute_pwsh")
        ],
    ],
)
def test_classify_maps_kiro_tool_ids(name: str, tool_class: str) -> None:
    assert hook.classify(name) == tool_class


@pytest.mark.parametrize(
    "name",
    [
        "web_fetch",
        "remote_web_search",
        "invoke_sub_agent",
        "introspect",
        "read_file_x",
        "",
        None,
    ],
)
def test_classify_unknown_names_stay_other(name: str | None) -> None:
    assert hook.classify(name) == "other"


@pytest.mark.parametrize(
    ("tool", "tool_class", "decision", "rule"),
    [
        ("read_file", "read", "allow", "read.any"),
        ("disclose_context", "read", "allow", "read.any"),
        ("str_replace", "write", "allow", "write.any"),
        ("web_fetch", "other", "deny", "policy.default_deny"),
    ],
)
def test_plan_policy_pre_allows_v3_ids_and_denies_other(
    tmp_path: Path, tool: str, tool_class: str, decision: str, rule: str
) -> None:
    plan = json.loads(_PLAN_POLICY.read_text(encoding="utf-8"))
    pointers, _policy, log = _setup(tmp_path, plan["rules"], plan["max_tool_calls"])
    code, out, err = _call(pointers, _event(tmp_path, tool=tool))
    assert code == (0 if decision == "allow" else 2)
    assert rule in (out if decision == "allow" else err)
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert (record["tool_name"], record["tool_class"]) == (tool, tool_class)
    assert (record["decision"], record["rule_id"]) == (decision, rule)
