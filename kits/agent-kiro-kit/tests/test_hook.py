"""Tests for the policy hook, redacted log, and result summary."""

from __future__ import annotations

import io
import json
import multiprocessing
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from beddel_agent_kiro import hook


def _setup(
    tmp_path: Path, rules: list[dict[str, Any]] | None = None
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
        ("echo `blocked`", "shell.substitution"),
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
    assert hook.cmd_head("écho") is None


def test_post_stop_redaction_schema_and_digest(tmp_path: Path) -> None:
    pointers, _policy, log = _setup(tmp_path)
    marker = "TOP-SECRET-PROMPT-MARKER"
    post = _event(tmp_path, command="printf x", name="postToolUse")
    post["tool_input"]["marker"] = marker
    post["tool_response"] = {"marker": marker}
    assert _call(pointers, post)[0] == 0
    assert _call(pointers, _event(tmp_path, name="stop"))[0] == 0
    raw = log.read_text(encoding="utf-8")
    records = [json.loads(line) for line in raw.splitlines()]
    assert all(set(record) == set(hook._LOG_KEYS) for record in records)
    assert marker not in raw and records[0]["response_sha256"]
    assert records[1]["tool_name"] is None


def _child(pointers: str, cwd: str) -> None:
    payload = _event(Path(cwd), tool="read")
    payload["tool_input"] = {}
    raise SystemExit(
        hook.main(["--pointers", pointers], io.StringIO(json.dumps(payload)))
    )


def test_concurrent_sequences_are_unique(tmp_path: Path) -> None:
    pointers, _policy, log = _setup(tmp_path)
    processes = [
        multiprocessing.Process(target=_child, args=(str(pointers), str(tmp_path)))
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(5)
        assert process.exitcode == 0
    records = [
        json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()
    ]
    assert sorted(record["seq"] for record in records) == [1, 2]


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
    pointers, policy, _log = _setup(tmp_path / "relative")
    root = tmp_path / "relative"
    hook.pointer_path(pointers, str(root)).write_text(
        json.dumps(
            {"policy": str(policy), "log_path": "relative.json", "stage": "test"}
        ),
        encoding="utf-8",
    )
    assert (
        _call(pointers, _event(root, name="stop"))[0] == 2
        and not (root / "relative.json").exists()
    )


def test_fresh_log_umask_and_invalid_utf8(tmp_path: Path) -> None:
    pointers, _policy, log = _setup(tmp_path)
    payload = _event(tmp_path, tool="read")
    payload["tool_input"] = {}
    old_umask = os.umask(0o002)
    try:
        assert _call(pointers, payload)[0] == _call(pointers, payload)[0] == 0
    finally:
        os.umask(old_umask)
    assert log.stat().st_mode & 0o077 == 0
    log.write_bytes(log.read_bytes() + b"\xff\n")
    assert _call(pointers, payload)[0] == 0


def test_getattr_and_rendered_commands(tmp_path: Path) -> None:
    import beddel_agent_kiro
    from beddel_agent_kiro.adapter import KiroCLIAgentAdapter
    from beddel_agent_kiro.agent_config import render

    assert getattr(beddel_agent_kiro, "KiroCLIAgentAdapter") is KiroCLIAgentAdapter  # noqa: B009
    pointers, _policy, log = _setup(
        tmp_path, [{"id": "shell.deny", "effect": "deny", "tool_class": "shell"}]
    )
    command = json.loads(render(pointers))["hooks"][0]["action"]["command"]
    env = {"PATH": os.environ["PATH"]}
    denied = subprocess.run(
        command,
        input=json.dumps(_event(tmp_path, command="true")),
        text=True,
        shell=True,
        check=False,
        env=env,
    )
    invalid = subprocess.run(
        command,
        input=json.dumps(_event(tmp_path / "missing")),
        text=True,
        shell=True,
        check=False,
        env=env,
    )
    assert denied.returncode == invalid.returncode == 2
    assert log.exists()
    stub = tmp_path / "stub" / "beddel"
    stub.mkdir(parents=True)
    (stub / "__init__.py").write_text(
        "raise RuntimeError('must not import')", encoding="utf-8"
    )
    stub_command = command.replace("PYTHONPATH=", f"PYTHONPATH={stub}:", 1)
    assert (
        subprocess.run(
            stub_command,
            input=json.dumps(_event(tmp_path, command="true")),
            text=True,
            shell=True,
            check=False,
            env=env,
        ).returncode
        == 2
    )


def test_internal_and_pointer_error_rows(tmp_path: Path) -> None:
    pointers, policy, log = _setup(tmp_path)
    assert hook.main(["--pointers", str(pointers)], io.StringIO("{")) == 2
    assert _call(pointers, {"hook_event_name": "preToolUse"})[0] == 2
    assert _call(pointers, _event(tmp_path, name="other"))[0] == 2
    policy.chmod(0o622)
    code, _out, err = _call(pointers, _event(tmp_path, command="true"))
    assert code == 2 and "policy.invalid" in err
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert record["policy_sha256"]
    pointer = hook.pointer_path(pointers, str(tmp_path))
    pointer.chmod(0o622)
    assert "policy.invalid" in _call(pointers, _event(tmp_path, command="true"))[2]
    assert (
        json.loads(log.read_text(encoding="utf-8").splitlines()[-1])["event"] == "pre"
    )
