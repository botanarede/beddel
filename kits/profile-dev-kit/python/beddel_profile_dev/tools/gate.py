"""Deterministic Gate of a Change (AD-16, AD-17, AD-18, AD-19).

Runs the local commands named in kit config over the scope that Story 2.3's
``impact.json`` already holds, and records each command's name, argv, exit code
and timeout flag as an OPERATIONAL outcome. It never re-derives the scope, makes
no judgement of a non-zero exit, and its record is neither Evidence nor a
Verdict: classifying an outcome belongs to a later epic.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import (
    PROFILE_CHANGE_INVALID,
    PROFILE_GATE_COMMAND_INVALID,
    PROFILE_GATE_UNSCOPED,
    PROFILE_REPOSITORY_INVALID,
    ProfileError,
)
from beddel_profile_dev._io import (
    canonical_json,
    confined,
    read_confined,
    real_repo_root,
    resolve_revision,
    work_tree_at,
    write_create_only,
)
from beddel_profile_dev.config import load_config
from beddel_profile_dev.inventory import is_valid_id
from beddel_profile_dev.tools._subprocess import (
    CommandResult,
    resolve_executable,
    run_command,
)
from beddel_profile_dev.tools.impact import IMPACT_SCHEMA

__all__ = ["GATE_SCHEMA", "profile_run_gate"]

GATE_SCHEMA = "profile-dev/gate-outcome/1"

_IMPACT_KEYS = frozenset(
    {
        "schema",
        "change_id",
        "base",
        "revision",
        "inventory_version",
        "inventory_sha256",
        "footprint",
        "affected_points",
        "required_evidence",
    }
)
_FULL_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_ATTEMPT = re.compile(r"[1-9][0-9]*")
_ATTEMPT_TRIES = 100


def _unscoped(
    message: str = "gate needs the impact record of the Change at this revision",
) -> ProfileError:
    return ProfileError(PROFILE_GATE_UNSCOPED, message)


def _read_scope(
    root: Path, impact_rel: str, change_id: str, sha: str
) -> dict[str, str]:
    """Return the identity fields of the impact record; refuse if it is unusable.

    Only identity is read. The footprint, the Affected points and the Required
    evidence are never read for decisions and never re-derived.
    """
    raw = read_confined(root, impact_rel)
    try:
        data = json.loads(raw) if raw is not None else None
    except ValueError:
        data = None
    if not isinstance(data, dict) or set(data) != _IMPACT_KEYS:
        raise _unscoped()
    version = data["inventory_version"]
    digest = data["inventory_sha256"]
    base = data["base"]
    if (
        data["schema"] != IMPACT_SCHEMA
        or data["change_id"] != change_id
        or data["revision"] != sha
        or not (isinstance(base, str) and _FULL_SHA.fullmatch(base))
        or not (isinstance(version, str) and is_valid_id(version))
        or not (isinstance(digest, str) and _DIGEST.fullmatch(digest))
    ):
        raise _unscoped()
    return {"inventory_version": version, "inventory_sha256": digest}


def _claim_attempt(root: Path, output_rel: str) -> int:
    """Create the next ``gate-output/<attempt>`` directory (append-only, from 1)."""
    directory = confined(root, output_rel)
    taken = (
        [int(p.name) for p in directory.iterdir() if _ATTEMPT.fullmatch(p.name)]
        if directory.is_dir()
        else []
    )
    attempt = max(taken, default=0) + 1
    for _ in range(_ATTEMPT_TRIES):
        target = confined(root, f"{output_rel}/{attempt}")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Re-check the confinement now that the directories exist.
        confined(root, f"{output_rel}/{attempt}")
        try:
            target.mkdir()
        except FileExistsError:
            attempt += 1
            continue
        return attempt
    raise ProfileError(PROFILE_REPOSITORY_INVALID, "repository or revision invalid")


def _record_streams(
    root: Path, attempt_rel: str, name: str, result: CommandResult
) -> None:
    for stream, data in (("stdout", result.stdout), ("stderr", result.stderr)):
        text = data.decode("utf-8", "replace").encode("utf-8")
        if not write_create_only(root, f"{attempt_rel}/{name}.{stream}.txt", text):
            raise ProfileError(
                PROFILE_REPOSITORY_INVALID, "repository or revision invalid"
            )


def _publish_latest(root: Path, relative: str, attempt: int, data: bytes) -> None:
    """Create ``gate.json``, or atomically point it at the latest attempt.

    The first run creates it exclusively. A re-run replaces only this pointer;
    every attempt directory it names stays untouched. Concurrent runs are not
    ordered: the last one to finish names its attempt.
    """
    if write_create_only(root, relative, data):
        return
    path = confined(root, relative)
    scratch = confined(root, f"{relative}.{attempt}.tmp")  # unique per claimed attempt
    try:
        with open(scratch, "xb") as handle:
            handle.write(data)
    except OSError as error:
        raise ProfileError(
            PROFILE_REPOSITORY_INVALID, "repository or revision invalid"
        ) from error
    try:
        os.replace(scratch, path)
    except OSError as error:
        scratch.unlink(missing_ok=True)
        raise ProfileError(
            PROFILE_REPOSITORY_INVALID, "repository or revision invalid"
        ) from error


@beddel_tool(
    name="profile_run_gate",
    description="Run the configured local gate commands over the derived set of a Change and record their exit codes",
    category="profile",
)
def profile_run_gate(repo_path: str, change_id: str, revision: str) -> dict[str, Any]:
    """Run the Gate of a Change at its Analyzed revision.

    The commands run over the current work tree, so it must be that revision:
    ``HEAD`` equal to it and no tracked file modified (the records directory
    aside). The outcome is operational: exit codes and timeout flags, never a
    verdict.

    Raises:
        ProfileError: ``PROFILE_GATE_UNSCOPED`` (no usable impact record, or a
            work tree that is not the Analyzed revision),
            ``PROFILE_GATE_COMMAND_INVALID`` (a configured executable is not
            allowed or not available), ``PROFILE_CONFIG_INVALID``,
            ``PROFILE_CHANGE_INVALID`` or ``PROFILE_REPOSITORY_INVALID``.
            Nothing is written when it raises before the commands start.
    """
    # Fail-closed: a malformed or non-allowlisted config raises before any write.
    config = load_config()
    records = config.records_dir
    if not is_valid_id(change_id):
        raise ProfileError(PROFILE_CHANGE_INVALID, "change id invalid")
    root = real_repo_root(repo_path)
    sha = resolve_revision(root, revision)

    revision_rel = f"{records}/changes/{change_id}/revisions/{sha}"
    scope = _read_scope(root, f"{revision_rel}/impact.json", change_id, sha)
    if not work_tree_at(root, sha, records):
        raise _unscoped("gate needs the work tree to be the analyzed revision")

    # Every executable must resolve before the first write: a command that
    # cannot be started never becomes a recorded outcome.
    for index, argv in enumerate(config.gate_commands):
        if resolve_executable(argv[0]) is None:
            raise ProfileError(
                PROFILE_GATE_COMMAND_INVALID,
                "gate command executable is not available",
                {"index": index},
            )
    gate_rel = f"{revision_rel}/gate.json"
    existing = confined(root, gate_rel)
    if os.path.lexists(existing) and not existing.is_file():
        raise ProfileError(PROFILE_REPOSITORY_INVALID, "repository or revision invalid")
    output_dir = confined(root, f"{revision_rel}/gate-output")
    if os.path.lexists(output_dir) and not output_dir.is_dir():
        raise ProfileError(PROFILE_REPOSITORY_INVALID, "repository or revision invalid")

    # Run every command before the first write: a command that cannot be started
    # (resolved, but not executable) aborts the step with nothing on disk.
    total = config.gate_total_timeout_seconds
    started_at = time.monotonic()
    ran: list[tuple[str, tuple[str, ...], CommandResult]] = []
    for index, argv in enumerate(config.gate_commands, start=1):
        name = f"{index:02d}-{argv[0]}"
        budget: float = config.gate_timeout_seconds
        out_of_time = False
        if total is not None:
            remaining = total - (time.monotonic() - started_at)
            out_of_time = remaining <= 0
            budget = min(budget, max(remaining, 0.0))
        if out_of_time:
            # The total budget is spent: record the command as timed out, unrun.
            result = CommandResult(
                started=True, exit_code=None, timed_out=True, stdout=b"", stderr=b""
            )
        else:
            result = run_command(argv, root, budget)
            if not result.started:
                raise ProfileError(
                    PROFILE_GATE_COMMAND_INVALID,
                    "gate command executable is not available",
                    {"index": index - 1},
                )
        ran.append((name, tuple(argv), result))

    # A command may have rewritten tracked files (a formatter or a fixer): the
    # outcome would then describe a tree that is not the Analyzed revision.
    if not work_tree_at(root, sha, records):
        raise _unscoped("a gate command modified the work tree")

    attempt = _claim_attempt(root, f"{revision_rel}/gate-output")
    attempt_rel = f"{revision_rel}/gate-output/{attempt}"
    entries: list[dict[str, Any]] = []
    for name, argv, result in ran:
        _record_streams(root, attempt_rel, name, result)
        entries.append(
            {
                "name": name,
                "argv": list(argv),
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
            }
        )

    outcome = {
        "schema": GATE_SCHEMA,
        "change_id": change_id,
        "revision": sha,
        "inventory_version": scope["inventory_version"],
        "inventory_sha256": scope["inventory_sha256"],
        "status": "completed",
        "commands": entries,
        "gate_ref": attempt_rel,
    }
    _publish_latest(root, gate_rel, attempt, canonical_json(outcome))
    return {
        "ok": True,
        "change_id": change_id,
        "revision": sha,
        "gate": gate_rel,
        "gate_ref": attempt_rel,
        "attempt": attempt,
        "status": "completed",
        "commands": len(entries),
        "timed_out": sum(1 for e in entries if e["timed_out"]),
    }
