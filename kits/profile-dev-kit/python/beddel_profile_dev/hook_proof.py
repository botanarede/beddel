# fmt: off
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from beddel_profile_dev.config import get_kit_root

HOOK_KEYS = ("hook_log_sha256", "hook_events", "hook_pre", "hook_post", "hook_denied", "hook_stop", "hook_errors", "hook_policy_sha256", "kiro_session")
_STAGE_RE = re.compile(r"[a-z][a-z0-9-]{0,31}")
_SESSION_RE = re.compile(r"[A-Za-z0-9._-]{1,128}")
_MAX_LOG_BYTES = 8 * 1024 * 1024
_HOOK_SCHEMA = "beddel.kiro-hook/1"


def pointers_dir() -> Path:
    return Path.home() / ".local/state/beddel/kiro-hook/pointers"


def runs_dir() -> Path:
    return Path.home() / ".local/state/beddel/kiro-hook/runs"


def pointer_path(cwd: str | os.PathLike[str]) -> Path:
    digest = hashlib.sha256(os.path.realpath(os.fspath(cwd)).encode()).hexdigest()
    return pointers_dir() / f"{digest}.json"


def policy_path(stage: str) -> Path:
    return get_kit_root() / "policies" / f"{stage}.json"


def _private_directory(path: Path) -> bool:
    try:
        if path.is_symlink(): return False
        if not path.exists(): path.mkdir(parents=True, mode=0o700)
        info = path.stat()
        return stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077
    except OSError: return False


def _secure_regular(path: Path, *, maximum: int | None = None) -> bool:
    try:
        info = path.lstat()
        return stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077 and (maximum is None or info.st_size <= maximum)
    except OSError: return False


def _write_exclusive(path: Path, data: bytes, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, mode)
    try:
        remaining = data
        while remaining: remaining = remaining[os.write(fd, remaining):]
        os.fchmod(fd, mode)
        os.fsync(fd)
    except BaseException:
        try: path.unlink()
        except OSError: pass
        raise
    finally: os.close(fd)


def open_run(stage: str) -> dict[str, Any]:
    if not isinstance(stage, str) or _STAGE_RE.fullmatch(stage) is None: return {"ok": False, "reason": "hooks.unavailable"}
    source = policy_path(stage)
    try:
        if source.is_symlink() or not source.is_file(): return {"ok": False, "reason": "hooks.unavailable"}
        policy = source.read_bytes()
        root = runs_dir()
        if not _private_directory(root): return {"ok": False, "reason": "hooks.unavailable"}
        run = root / f"{stage}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{secrets.token_hex(8)}"
        try: os.mkdir(run, 0o700)
        except FileExistsError: return {"ok": False, "reason": "hooks.unavailable"}
        policy_copy, log_path = run / "policy.json", run / "hook.jsonl"
        try: _write_exclusive(policy_copy, policy, 0o600)
        except OSError:
            try: policy_copy.unlink(missing_ok=True); run.rmdir()
            except OSError: pass
            return {"ok": False, "reason": "hooks.unavailable"}
        return {"ok": True, "stage": stage, "run": str(run), "log_path": str(log_path), "policy_path": str(policy_copy), "policy_sha256": hashlib.sha256(policy).hexdigest()}
    except (OSError, ValueError): return {"ok": False, "reason": "hooks.unavailable"}


def _repo_cwd(repo_path: str) -> Path | None:
    try:
        repo, cwd = Path(os.path.realpath(repo_path)), Path(os.path.realpath(os.getcwd()))
        return repo if repo.is_dir() and cwd == repo else None
    except (OSError, TypeError, ValueError): return None


def write_pointer(repo_path: str, stage: str, hook: Mapping[str, Any]) -> dict[str, Any]:
    repo = _repo_cwd(repo_path)
    result = {"armed": False, "reason": "hooks.unavailable", "stage": stage, "log_path": hook.get("log_path") if isinstance(hook, Mapping) else None, "pointer_sha256": None}
    if repo is None or not isinstance(hook, Mapping) or hook.get("ok") is not True: return result
    log_path, policy = hook.get("log_path"), hook.get("policy_path")
    if not isinstance(log_path, str) or not isinstance(policy, str) or not Path(log_path).is_absolute() or not Path(policy).is_absolute() or hook.get("stage") != stage or not _secure_regular(Path(policy)): return result
    if not _private_directory(pointers_dir()): return result
    pointer = pointer_path(repo)
    raw = json.dumps({"log_path": log_path, "policy": policy, "stage": stage}, sort_keys=True, separators=(",", ":")).encode()
    try: _write_exclusive(pointer, raw, 0o600)
    except FileExistsError:
        result["reason"] = "hooks.pointer_exists"
        return result
    except OSError: return result
    result.update(armed=True, reason=None, pointer_sha256=hashlib.sha256(raw).hexdigest())
    return result


def remove_pointer(repo_path: str, armed: Mapping[str, Any] | None) -> dict[str, bool]:
    if not isinstance(armed, Mapping) or armed.get("armed") is not True: return {"removed": False}
    expected, repo = armed.get("pointer_sha256"), _repo_cwd(repo_path)
    if repo is None or not isinstance(expected, str): return {"removed": False}
    pointer = pointer_path(repo)
    try:
        if not _secure_regular(pointer) or hashlib.sha256(pointer.read_bytes()).hexdigest() != expected: return {"removed": False}
        pointer.unlink()
        return {"removed": True}
    except OSError: return {"removed": False}


def null_keys() -> dict[str, None]: return {key: None for key in HOOK_KEYS}


def count_log(log_path: str | os.PathLike[str], policy_sha256: str | None = None) -> dict[str, Any] | None:
    path = Path(log_path)
    if not _secure_regular(path, maximum=_MAX_LOG_BYTES): return None
    try: raw = path.read_bytes()
    except OSError: return None
    result: dict[str, Any] = null_keys()
    result.update({"hook_log_sha256": hashlib.sha256(raw).hexdigest(), "hook_events": 0, "hook_pre": 0, "hook_post": 0, "hook_denied": 0, "hook_stop": 0, "hook_errors": 0})
    sessions: list[str] = []
    for line in raw.splitlines():
        if not line.strip(): continue
        result["hook_events"] += 1
        try: record = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, RecursionError, ValueError):
            result["hook_errors"] += 1
            continue
        if not isinstance(record, dict) or record.get("v") != _HOOK_SCHEMA:
            result["hook_errors"] += 1
            continue
        event, digest = record.get("event"), record.get("policy_sha256")
        if event in {"pre", "post", "stop"}: result[f"hook_{event}"] += 1
        if record.get("decision") == "deny": result["hook_denied"] += 1
        if record.get("decision") == "error": result["hook_errors"] += 1
        if policy_sha256 is not None and digest != policy_sha256: result["hook_errors"] += 1
        if result["hook_policy_sha256"] is None and isinstance(digest, str): result["hook_policy_sha256"] = digest
        session = record.get("session_id")
        if isinstance(session, str) and _SESSION_RE.fullmatch(session):
            joined = ",".join([*sessions, session])
            if session not in sessions and len(joined) <= 512: sessions.append(session)
    result["kiro_session"] = ",".join(sessions) if sessions else None
    return result
# fmt: on
