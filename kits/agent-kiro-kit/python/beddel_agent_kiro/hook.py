"""Stdlib-only Kiro hook policy evaluator and redacted event logger."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

DEFAULT_POINTERS_DIR = Path.home() / ".local/state/beddel/kiro-hook/pointers"
SCHEMA = "beddel.kiro-hook/1"
_POLICY_SCHEMA = "beddel.kiro-hook-policy/1"
_POINTER_KEYS = frozenset({"policy", "log_path", "stage"})
_POLICY_KEYS = frozenset({"schema", "rules"})
_RULE_KEYS = frozenset({"id", "effect", "tool_class", "argv_prefix"})
_ID_RE = re.compile(r"[a-z0-9._-]{1,64}")
_CMD_RE = re.compile(r"[a-z0-9._-]{1,32}")
_SPLIT_RE = re.compile(r"&&|\|\||[;|&\n]")
_CLASSES = {"read", "write", "shell", "other"}
_LOG_KEYS = (
    "v",
    "ts",
    "seq",
    "session_id",
    "event",
    "tool_name",
    "tool_class",
    "cmd_head",
    "input_sha256",
    "input_len",
    "response_sha256",
    "response_len",
    "decision",
    "rule_id",
    "policy_sha256",
    "hook_ms",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Any) -> tuple[str, int]:
    raw = _canonical(value)
    return hashlib.sha256(raw).hexdigest(), len(raw)


def pointer_path(pointers: Path, cwd: str | os.PathLike[str]) -> Path:
    """Return the cwd-realpath keyed pointer path."""
    digest = hashlib.sha256(os.path.realpath(os.fspath(cwd)).encode()).hexdigest()
    return Path(pointers) / f"{digest}.json"


def classify(tool_name: Any) -> str:
    name = str(tool_name or "").lower()
    if name in {"read", "fs_read", "glob", "grep", "code"}:
        return "read"
    if name in {"write", "fs_write"}:
        return "write"
    if name in {"shell", "execute_bash", "execute_cmd"}:
        return "shell"
    return "other"


def _command(tool_input: Any) -> str | None:
    if isinstance(tool_input, str):
        return tool_input
    if isinstance(tool_input, dict):
        value = tool_input.get("command", tool_input.get("cmd"))
        if isinstance(value, str):
            return value
    return None


def _segments(command: str) -> list[str]:
    return [part.strip() for part in _SPLIT_RE.split(command) if part.strip()]


def cmd_head(command: Any) -> str | None:
    try:
        parts = _segments(command) if isinstance(command, str) else []
        tokens = shlex.split(parts[0]) if parts else []
        if not tokens:
            return None
        head = os.path.basename(tokens[0]).lower()
        return head if _CMD_RE.fullmatch(head) else None
    except (TypeError, ValueError):
        return None


def _secure_file(path: Path) -> bool:
    try:
        return (
            path.is_file()
            and not path.is_symlink()
            and not (path.stat().st_mode & 0o022)
        )
    except OSError:
        return False


def _load_json(path: Path) -> Any:
    if not _secure_file(path):
        raise ValueError("insecure or missing file")
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_policy(policy: Any) -> None:
    if not isinstance(policy, dict) or set(policy) != _POLICY_KEYS:
        raise ValueError("invalid policy keys")
    if policy.get("schema") != _POLICY_SCHEMA or not isinstance(
        policy.get("rules"), list
    ):
        raise ValueError("invalid policy schema")
    seen: set[str] = set()
    for rule in policy["rules"]:
        if not isinstance(rule, dict) or not set(rule) <= _RULE_KEYS:
            raise ValueError("invalid policy rule")
        rule_id = rule.get("id")
        if (
            not isinstance(rule_id, str)
            or not _ID_RE.fullmatch(rule_id)
            or rule_id in seen
        ):
            raise ValueError("invalid or duplicate rule id")
        seen.add(rule_id)
        if (
            rule.get("effect") not in {"allow", "deny"}
            or rule.get("tool_class") not in _CLASSES
        ):
            raise ValueError("invalid policy rule")
        prefix = rule.get("argv_prefix")
        if prefix is not None and (
            rule["tool_class"] != "shell"
            or not isinstance(prefix, list)
            or not prefix
            or not all(isinstance(item, str) for item in prefix)
        ):
            raise ValueError("invalid argv prefix")


def _pointer_paths(data: dict[str, Any]) -> tuple[Path, Path]:
    if set(data) != _POINTER_KEYS:
        raise ValueError("invalid pointer")
    policy, log_path = data.get("policy"), data.get("log_path")
    if not isinstance(policy, str) or not isinstance(log_path, str):
        raise TypeError("invalid pointer paths")
    policy_path, log = Path(policy), Path(log_path)
    if (
        not policy_path.is_absolute()
        or not log.is_absolute()
        or not isinstance(data.get("stage"), str)
    ):
        raise ValueError("invalid pointer paths")
    return policy_path, log


def _load_context(
    data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str, Path]:
    policy_path, log_path = _pointer_paths(data)
    policy = _load_json(policy_path)
    _validate_policy(policy)
    return data, policy, hashlib.sha256(_canonical(policy)).hexdigest(), log_path


def _evaluate(
    policy: dict[str, Any], tool_class: str, command: str | None
) -> tuple[str, str]:
    if tool_class == "shell":
        if command is None:
            return "deny", "shell.no_command"
        if any(marker in command for marker in ("$(", "`", "<(", ">(")):
            return "deny", "shell.substitution"
        parts = _segments(command) or [""]
    else:
        parts = [""]
    selected = None
    for part in parts:
        try:
            tokens = shlex.split(part)
        except ValueError:
            return "deny", "shell.parse"
        rule = next(
            (
                r
                for r in policy["rules"]
                if r["tool_class"] == tool_class
                and (
                    r.get("argv_prefix") is None
                    or tokens[: len(r["argv_prefix"])] == r["argv_prefix"]
                )
            ),
            None,
        )
        if rule is None:
            return "deny", "policy.default_deny"
        if rule["effect"] != "allow":
            return "deny", rule["id"]
        selected = rule["id"]
    return "allow", selected or "policy.allow"


def _record(
    event: str,
    decision: str,
    rule_id: str,
    policy_sha: str | None,
    elapsed: float,
    payload: dict[str, Any],
    command: str | None,
    tool_class: str | None,
) -> dict[str, Any]:
    inp = (
        _digest(payload.get("tool_input")) if event in {"pre", "post"} else (None, None)
    )
    response = (
        _digest(payload.get("tool_response")) if event == "post" else (None, None)
    )
    values = {
        "v": SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat(),
        "seq": 0,
        "session_id": payload.get("session_id"),
        "event": event,
        "tool_name": payload.get("tool_name") if event != "stop" else None,
        "tool_class": tool_class if event != "stop" else None,
        "cmd_head": cmd_head(command)
        if event != "stop" and tool_class == "shell"
        else None,
        "input_sha256": inp[0],
        "input_len": inp[1],
        "response_sha256": response[0],
        "response_len": response[1],
        "decision": decision,
        "rule_id": rule_id,
        "policy_sha256": policy_sha,
        "hook_ms": elapsed,
    }
    return {key: values[key] for key in _LOG_KEYS}


def _append_log(path: Path, record: dict[str, Any]) -> None:
    import fcntl

    if path.is_symlink() or not path.parent.is_dir():
        raise OSError("log path or parent directory is unavailable")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    read_fd: int | None = None
    locked = False
    try:
        os.fchmod(fd, 0o600)
        mode = os.fstat(fd).st_mode
        if not stat.S_ISREG(mode) or mode & 0o077:
            raise OSError("log file is not a private regular file")
        fcntl.flock(fd, fcntl.LOCK_EX)
        locked = True
        read_fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        maximum = 0
        with os.fdopen(read_fd, "r", encoding="utf-8", errors="replace") as stream:
            read_fd = None
            for line in stream:
                try:
                    value = json.loads(line)
                    if isinstance(value, dict) and isinstance(value.get("seq"), int):
                        maximum = max(maximum, value["seq"])
                except (json.JSONDecodeError, TypeError):
                    pass
        record["seq"] = maximum + 1
        raw = (
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        while raw:
            raw = raw[os.write(fd, raw) :]
        os.fsync(fd)
    finally:
        if locked:
            fcntl.flock(fd, fcntl.LOCK_UN)
        if read_fd is not None:
            os.close(read_fd)
        os.close(fd)


def _emit(decision: str, rule_id: str) -> None:
    print(
        f"decision=allow rule_id={rule_id}"
        if decision == "allow"
        else f"beddel-kiro-hook: {rule_id}",
        file=None if decision == "allow" else sys.stderr,
    )


def _run(payload: dict[str, Any], pointers: Path) -> int:
    cwd = payload.get("cwd")
    if not isinstance(cwd, str):
        raise TypeError("missing cwd")
    pointer = pointer_path(pointers, cwd)
    if not _secure_file(pointer):
        _emit("deny", "pointer.missing")
        return 2
    log_path: Path | None = None
    policy_sha: str | None = None
    loaded = False
    try:
        data = _load_json(pointer)
        if not isinstance(data, dict):
            raise TypeError("invalid pointer")
        _, log_path = _pointer_paths(data)
        data, policy, policy_sha, log_path = _load_context(data)
        loaded = True
        name = str(payload.get("hook_event_name", "")).lower()
        event = {
            "pretooluse": "pre",
            "pre": "pre",
            "posttooluse": "post",
            "post": "post",
            "stop": "stop",
            "sessionend": "stop",
        }.get(name)
        if event is None:
            raise ValueError("unknown event")
        started = time.perf_counter()
        tool_class = classify(payload.get("tool_name"))
        command = _command(payload.get("tool_input"))
        decision, rule = (
            _evaluate(policy, tool_class, command)
            if event == "pre"
            else ("allow", f"hook.{event}")
        )
        _append_log(
            log_path,
            _record(
                event,
                decision,
                rule,
                policy_sha,
                (time.perf_counter() - started) * 1000,
                payload,
                command,
                tool_class,
            ),
        )
        _emit(decision, rule)
        return 0 if decision == "allow" else 2
    except BaseException:  # noqa: BLE001
        if log_path is not None:
            try:
                _append_log(
                    log_path,
                    _record(
                        "error",
                        "error",
                        "hook.internal" if loaded else "policy.invalid",
                        policy_sha,
                        0.0,
                        payload,
                        None,
                        None,
                    ),
                )
            except BaseException:  # noqa: BLE001
                log_path = None
        _emit("error", "hook.internal" if loaded else "policy.invalid")
        return 2


def main(argv: list[str] | None = None, stdin: TextIO | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] != "--pointers":
        _emit("error", "hook.internal")
        return 2
    try:
        payload = json.load(stdin or sys.stdin)
        if not isinstance(payload, dict):
            raise TypeError("event is not an object")
        return _run(payload, Path(args[1]))
    except BaseException:  # noqa: BLE001
        _emit("error", "hook.internal")
        return 2


def summarize(pointers: Path, cwd: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": "kiro-hook",
        "events": 0,
        "pre": 0,
        "post": 0,
        "denied": 0,
        "stop": 0,
        "errors": 0,
        "log_sha256": None,
    }
    try:
        data = _load_json(pointer_path(pointers, str(cwd)))
        if not isinstance(data, dict):
            return result
        _, log_path = _pointer_paths(data)
        if not _secure_file(log_path):
            return result
        raw = log_path.read_bytes()
        result["log_sha256"] = hashlib.sha256(raw).hexdigest()
        for line in raw.decode("utf-8", errors="replace").splitlines():
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, UnicodeError):
                continue
            event = record.get("event") if isinstance(record, dict) else None
            if event in {"pre", "post", "stop"}:
                result["events"] += 1
                result[event] += 1
            if isinstance(record, dict) and record.get("decision") == "deny":
                result["denied"] += 1
            if isinstance(record, dict) and (
                record.get("decision") == "error" or event == "error"
            ):
                result["errors"] += 1
    except BaseException:  # noqa: BLE001
        return result
    return result


if __name__ == "__main__":
    sys.exit(main())
