"""Capture immutable Evidence from one VerificationAttempt."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import (
    PROFILE_ATTEMPT_CONFLICT,
    PROFILE_ATTEMPT_UNSCOPED,
    PROFILE_CHANGE_INVALID,
    PROFILE_REPOSITORY_INVALID,
    ProfileError,
)
from beddel_profile_dev._io import (
    canonical_json,
    read_confined,
    real_repo_root,
    records_root,
    resolve_revision,
    write_create_only,
)
from beddel_profile_dev.config import load_config
from beddel_profile_dev.inventory import is_valid_id
from beddel_profile_dev.tools.impact import _bound_snapshot
from beddel_profile_dev.tools.review import _read_scope

__all__ = ["EVIDENCE_SCHEMA", "profile_capture_evidence"]

EVIDENCE_SCHEMA = "profile-dev/evidence/1"


def _unscoped() -> ProfileError:
    return ProfileError(
        PROFILE_ATTEMPT_UNSCOPED,
        "evidence needs a valid attempt scope",
    )


def _attempt(
    records: Path,
    revision_rel: str,
    attempt: int,
    change_id: str,
    sha: str,
    impact_raw: bytes,
) -> dict[str, Any]:
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise _unscoped()
    raw = read_confined(records, f"{revision_rel}/attempts/{attempt}/attempt.json")
    try:
        data = json.loads(raw) if raw is not None else None
    except ValueError:
        data = None
    expected = {
        "schema",
        "attempt",
        "change_id",
        "base",
        "revision",
        "inventory_version",
        "inventory_sha256",
        "snapshot_ref",
        "snapshot_sha256",
        "impact_ref",
        "impact_sha256",
        "requirements",
    }
    if (
        not isinstance(data, dict)
        or set(data) != expected
        or data.get("schema") != "profile-dev/verification-attempt/1"
        or data.get("attempt") != attempt
        or data.get("change_id") != change_id
        or data.get("revision") != sha
        or data.get("impact_ref") != f"{revision_rel}/impact.json"
        or data.get("impact_sha256") != hashlib.sha256(impact_raw).hexdigest()
    ):
        raise _unscoped()
    try:
        impact = json.loads(impact_raw)
        snapshot_raw = read_confined(records, data["snapshot_ref"])
    except (KeyError, ValueError, TypeError):
        raise _unscoped() from None
    if (
        not isinstance(impact, dict)
        or data.get("base") != impact.get("base")
        or data.get("inventory_version") != impact.get("inventory_version")
        or data.get("inventory_sha256") != impact.get("inventory_sha256")
        or data.get("snapshot_ref") != f"revisions/{sha}/snapshot.json"
        or snapshot_raw is None
        or data.get("snapshot_sha256") != hashlib.sha256(snapshot_raw).hexdigest()
    ):
        raise _unscoped()
    expected_keys: list[tuple[str, str, str, str]] = []
    for item in impact.get("required_evidence", []):
        if not isinstance(item, dict):
            raise _unscoped()
        values = tuple(
            item.get(key) for key in ("class", "affected_point", "criterion")
        )
        kind = item.get("kind")
        if not all(
            isinstance(value, str) and is_valid_id(value) for value in values
        ) or kind not in {"gate", "review"}:
            raise _unscoped()
        expected_keys.append((*values, kind))
    expected_keys.sort()
    requirements = data.get("requirements")
    if not isinstance(requirements, list):
        raise _unscoped()
    seen: set[tuple[str, str, str]] = set()
    actual_keys: list[tuple[str, str, str, str]] = []
    for item in requirements:
        if not isinstance(item, dict) or set(item) != {
            "class",
            "affected_point",
            "criterion",
            "kind",
        }:
            raise _unscoped()
        values = tuple(item[key] for key in ("class", "affected_point", "criterion"))
        if (
            not all(isinstance(value, str) and is_valid_id(value) for value in values)
            or item["kind"] not in {"gate", "review"}
            or values in seen
        ):
            raise _unscoped()
        values = cast(tuple[str, str, str], values)
        seen.add(values)
        actual_keys.append((*values, item["kind"]))
    if actual_keys != sorted(actual_keys) or actual_keys != expected_keys:
        raise _unscoped()
    return data


def _load_outcome(
    records: Path,
    relative: str,
    attempt: int,
    change_id: str,
    revision: str,
    inventory_version: str,
    inventory_sha256: str,
    schema: str,
) -> tuple[dict[str, Any], bytes] | None:
    raw = read_confined(records, relative)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        raise _unscoped() from None
    if not isinstance(data, dict):
        raise _unscoped()
    if schema == "profile-dev/attempt-gate-outcome/1":
        expected = {
            "schema",
            "attempt",
            "output_attempt",
            "change_id",
            "revision",
            "inventory_version",
            "inventory_sha256",
            "status",
            "commands",
            "gate_ref",
        }
    else:
        expected = {
            "schema",
            "attempt",
            "output_attempt",
            "change_id",
            "revision",
            "inventory_version",
            "inventory_sha256",
            "agent",
            "model",
            "status",
            "review_ref",
        }
    allowed_keys = (
        (expected, expected | {"error_code"})
        if schema == "profile-dev/attempt-review-outcome/1"
        else (expected,)
    )
    attempt_value = data.get("attempt")
    output_attempt = data.get("output_attempt")
    if (
        set(data) not in allowed_keys
        or data.get("schema") != schema
        or isinstance(attempt_value, bool)
        or not isinstance(attempt_value, int)
        or attempt_value != attempt
        or isinstance(output_attempt, bool)
        or not isinstance(output_attempt, int)
        or output_attempt < 1
        or data.get("change_id") != change_id
        or data.get("revision") != revision
        or data.get("inventory_version") != inventory_version
        or data.get("inventory_sha256") != inventory_sha256
    ):
        raise _unscoped()
    if schema == "profile-dev/attempt-review-outcome/1":
        status = data.get("status")
        if status not in {"completed", "timed_out", "errored"}:
            raise _unscoped()
        has_error = "error_code" in data
        if (status == "completed") == has_error or (
            has_error and not isinstance(data["error_code"], str)
        ):
            raise _unscoped()
    elif data.get("status") != "completed":
        raise _unscoped()
    return data, raw


def _write_or_match(records: Path, relative: str, data: bytes) -> None:
    if write_create_only(records, relative, data):
        return
    if read_confined(records, relative) != data:
        raise ProfileError(
            PROFILE_ATTEMPT_CONFLICT, "evidence already exists differently"
        )


@beddel_tool(
    name="profile_capture_evidence",
    description="Capture append-only Evidence for the matching results of one VerificationAttempt",
    category="profile",
)
def profile_capture_evidence(
    repo_path: str, change_id: str, revision: str, attempt: int
) -> dict[str, Any]:
    """Capture one create-only Evidence record per matching Requirement ID."""
    config = load_config()
    if not is_valid_id(change_id):
        raise ProfileError(PROFILE_CHANGE_INVALID, "change id invalid")
    repo = real_repo_root(repo_path)
    sha = resolve_revision(repo, revision)
    records = records_root(repo, config.records_dir)
    revision_rel = f"changes/{change_id}/revisions/{sha}"
    impact_rel = f"{revision_rel}/impact.json"
    impact_raw = read_confined(records, impact_rel)
    if impact_raw is None:
        raise _unscoped()
    try:
        _read_scope(records, impact_rel, change_id, sha)
        _bound_snapshot(records, sha)
    except ProfileError as error:
        if error.code == PROFILE_REPOSITORY_INVALID:
            raise
        raise _unscoped() from None
    attempt_record = _attempt(
        records, revision_rel, attempt, change_id, sha, impact_raw
    )
    requirements = attempt_record["requirements"]
    gate = _load_outcome(
        records,
        f"{revision_rel}/attempts/{attempt}/gate.json",
        attempt,
        change_id,
        sha,
        attempt_record["inventory_version"],
        attempt_record["inventory_sha256"],
        "profile-dev/attempt-gate-outcome/1",
    )
    review = _load_outcome(
        records,
        f"{revision_rel}/attempts/{attempt}/review.json",
        attempt,
        change_id,
        sha,
        attempt_record["inventory_version"],
        attempt_record["inventory_sha256"],
        "profile-dev/attempt-review-outcome/1",
    )

    records_to_write: list[tuple[str, bytes]] = []
    for requirement in requirements:
        kind = requirement["kind"]
        outcome = gate if kind == "gate" else review
        if outcome is None:
            continue
        data, outcome_raw = outcome
        if kind == "review":
            status = data.get("status")
            if status not in {"completed", "timed_out", "errored"}:
                raise _unscoped()
            if status != "completed":
                continue
            review_ref = data.get("review_ref")
            expected_prefix = f"{revision_rel}/review-output/"
            if (
                not isinstance(review_ref, str)
                or re.fullmatch(
                    re.escape(expected_prefix) + r"[1-9][0-9]*\.txt", review_ref
                )
                is None
                or not review_ref.endswith(f"/{data['output_attempt']}.txt")
            ):
                raise _unscoped()
            try:
                output = read_confined(records, review_ref)
            except (OSError, RuntimeError, ValueError):
                raise _unscoped() from None
            if output is None:
                raise _unscoped()
            if not output.decode("utf-8", "replace").strip():
                continue
            result: dict[str, Any] = {
                "agent": data.get("agent"),
                "model": data.get("model"),
                "review_ref": review_ref,
                "review_sha256": hashlib.sha256(output).hexdigest(),
            }
            if not isinstance(result["agent"], str) or not isinstance(
                result["model"], str
            ):
                raise _unscoped()
        else:
            commands = data.get("commands")
            gate_ref = data.get("gate_ref")
            expected_prefix = f"{revision_rel}/gate-output/"
            if (
                not isinstance(commands, list)
                or not commands
                or not isinstance(gate_ref, str)
                or re.fullmatch(re.escape(expected_prefix) + r"[1-9][0-9]*", gate_ref)
                is None
                or not gate_ref.endswith(f"/{data['output_attempt']}")
            ):
                raise _unscoped()
            command_keys = {"name", "argv", "exit_code", "timed_out"}
            for command in commands:
                if (
                    not isinstance(command, dict)
                    or set(command) != command_keys
                    or not isinstance(command["name"], str)
                    or not isinstance(command["argv"], list)
                    or not all(isinstance(arg, str) for arg in command["argv"])
                    or (
                        command["exit_code"] is not None
                        and (
                            isinstance(command["exit_code"], bool)
                            or not isinstance(command["exit_code"], int)
                        )
                    )
                    or not isinstance(command["timed_out"], bool)
                ):
                    raise _unscoped()
            result = {"commands": commands, "gate_ref": gate_ref}
        evidence = {
            "schema": EVIDENCE_SCHEMA,
            "attempt": attempt,
            "change_id": change_id,
            "revision": sha,
            "class": requirement["class"],
            "affected_point": requirement["affected_point"],
            "criterion": requirement["criterion"],
            "kind": kind,
            "outcome_ref": f"{revision_rel}/attempts/{attempt}/{kind}.json",
            "outcome_sha256": hashlib.sha256(outcome_raw).hexdigest(),
            "result": result,
        }
        filename = (
            f"{requirement['class']}+{requirement['affected_point']}+"
            f"{requirement['criterion']}.json"
        )
        records_to_write.append(
            (
                f"{revision_rel}/attempts/{attempt}/evidence/{filename}",
                canonical_json(evidence),
            )
        )

    for relative, evidence_bytes in records_to_write:
        existing = read_confined(records, relative)
        if existing is not None and existing != evidence_bytes:
            raise ProfileError(
                PROFILE_ATTEMPT_CONFLICT, "evidence already exists differently"
            )
    for relative, evidence_bytes in records_to_write:
        _write_or_match(records, relative, evidence_bytes)
    return {
        "ok": True,
        "change_id": change_id,
        "revision": sha,
        "attempt": attempt,
        "evidence": len(records_to_write),
    }
