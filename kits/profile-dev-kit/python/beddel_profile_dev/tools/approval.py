"""Human Approval decision verification and create-only persistence."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import yaml
from beddel.tools import beddel_tool

from beddel_profile_dev._errors import (
    PROFILE_APPROVAL_REFUSED,
    PROFILE_CHANGE_INVALID,
    PROFILE_REPOSITORY_INVALID,
    ProfileError,
)
from beddel_profile_dev._io import (
    blob_at,
    canonical_json,
    confined,
    is_ancestor,
    real_repo_root,
    records_root,
    resolve_revision,
    write_create_only,
)
from beddel_profile_dev.config import load_config
from beddel_profile_dev.inventory import is_valid_id
from beddel_profile_dev.tools.approval_decision import (
    APPROVAL_DECISION_SCHEMA,
    approval_path,
)
from beddel_profile_dev.tools.bind import _valid_timestamp
from beddel_profile_dev.tools.ratify import valid_actor
from beddel_profile_dev.tools.report import (
    _DIGEST,
    REPORT_SCHEMA,
    _derive_report,
    _latest_attempt,
    _load_change,
    _Reader,
    _report_history,
    _unbound,
    _valid_change,
)

__all__ = ["profile_approve_change", "profile_read_approval"]

_FULL_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_APPROVAL_SCHEMA = "profile-dev/approval/1"
_APPROVAL_KEYS = {
    "schema",
    "change_id",
    "revision",
    "report",
    "report_sha256",
    "attempt",
    "approved_by",
    "proof",
}
_PROOF_KEYS = {"commit", "path", "sha256"}


def _refuse(reason: str) -> ProfileError:
    return ProfileError(
        PROFILE_APPROVAL_REFUSED,
        f"approval refused: {reason}",
        {"reason": reason},
    )


def _valid_latest_report(report: dict[str, Any]) -> bool:
    if "attempt" not in report:
        return False
    attempt = report.get("attempt")
    if attempt is not None and (type(attempt) is not int or attempt < 1):
        return False
    reads = report.get("reads")
    if not isinstance(reads, list):
        return False
    if any(
        not isinstance(item, dict)
        or set(item) != {"ref", "sha256"}
        or not isinstance(item["ref"], str)
        or not isinstance(item["sha256"], str)
        or _DIGEST.fullmatch(item["sha256"]) is None
        for item in reads
    ):
        return False
    return report.get("verdict") in {"consistent", "has pendency"}


def _revalidate(
    repo: Any, records: Any, change_id: str, sha: str
) -> tuple[int, dict[str, Any], str, str]:
    """Run Story 5.1 checks and return the authoritative Report details."""
    reader = _Reader(records)
    try:
        change = reader.json(f"changes/{change_id}/change.json")
    except (ProfileError, OSError, ValueError):
        raise _refuse("change.unrecorded") from None
    if not _valid_change(change, change_id):
        raise _refuse("change.unrecorded")
    try:
        _load_change(reader, repo, change_id, sha)
    except (ProfileError, OSError, ValueError):
        raise _refuse("revision.unlinked") from None

    try:
        history = _report_history(reader, records, change_id)
    except (ProfileError, OSError, ValueError):
        raise _refuse("report.malformed") from None
    if not history:
        raise _refuse("report.absent")
    ordinal, latest = history[-1]
    if not _valid_latest_report(latest):
        raise _refuse("report.malformed")
    if latest.get("schema") != REPORT_SCHEMA:
        raise _refuse("report.outdated")
    if latest.get("revision") != sha:
        raise _refuse("revision.not_reported")

    try:
        attempt = _latest_attempt(records, f"changes/{change_id}/revisions/{sha}")
    except (ProfileError, OSError):
        raise _refuse("attempt.superseded") from None
    if attempt != latest["attempt"]:
        raise _refuse("attempt.superseded")

    for item in latest["reads"]:
        try:
            raw = reader.read(item["ref"])
        except (ProfileError, OSError, ValueError):
            raise _refuse("digest.mismatch") from None
        if raw is None or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise _refuse("digest.mismatch")

    try:
        derive_reader = _Reader(records)
        prior_history = _report_history(
            derive_reader, records, change_id, before=ordinal
        )
        derived = _derive_report(
            derive_reader, repo, records, change_id, sha, prior_history
        )
    except (ProfileError, OSError, ValueError, RecursionError):
        raise _refuse("verdict.underivable") from None
    if derived.get("verdict") != latest.get("verdict"):
        raise _refuse("verdict.mismatch")
    if derived.get("verdict") == "has pendency":
        raise _refuse("verdict.has_pendency")
    report_ref = f"changes/{change_id}/report/{ordinal}.json"
    return ordinal, latest, report_ref, reader.reads[report_ref]


def _verify_decision(
    repo: Any,
    change_id: str,
    sha: str,
    actor: str,
    decision_commit: str,
    ordinal: int,
    report_ref: str,
    report_sha256: str,
) -> tuple[str, str, str]:
    """Verify the Approval decision from the named reachable commit tree."""
    try:
        commit = resolve_revision(repo, decision_commit)
    except ProfileError:
        raise _refuse("decision.commit_invalid") from None
    try:
        head = resolve_revision(repo, "HEAD")
        reachable = is_ancestor(repo, commit, head)
    except ProfileError:
        raise _refuse("decision.unreachable") from None
    if not reachable:
        raise _refuse("decision.unreachable")

    path = approval_path(change_id, ordinal)
    blob = blob_at(repo, commit, path)
    if blob is None:
        raise _refuse("decision.absent")
    try:
        data = yaml.safe_load(blob)
    except (TypeError, ValueError, yaml.YAMLError, RecursionError):
        raise _refuse("decision.malformed") from None
    if not isinstance(data, dict):
        raise _refuse("decision.malformed")
    if data.get("schema") != APPROVAL_DECISION_SCHEMA:
        raise _refuse("decision.unsupported")
    if (
        set(data)
        != {
            "schema",
            "change_id",
            "revision",
            "report",
            "report_sha256",
            "approved_by",
            "approved_at",
        }
        or not all(isinstance(value, str) for value in data.values())
        or _DIGEST.fullmatch(data.get("report_sha256", "")) is None
        or not _valid_timestamp(data.get("approved_at"))
    ):
        raise _refuse("decision.malformed")
    approved_by = data["approved_by"]
    if not valid_actor(approved_by):
        raise _refuse("decision.actor_invalid")
    if (
        data["change_id"] != change_id
        or data["revision"] != sha
        or data["report"] != report_ref
    ):
        raise _refuse("decision.target_mismatch")
    if data["report_sha256"] != report_sha256:
        raise _refuse("decision.digest_mismatch")
    if actor != approved_by:
        raise _refuse("actor.mismatch")
    return commit, path, hashlib.sha256(blob).hexdigest()


def _write_approval(
    records: Any,
    change_id: str,
    sha: str,
    report_ref: str,
    report_sha256: str,
    attempt: int | None,
    approved_by: str,
    proof: tuple[str, str, str],
) -> dict[str, Any]:
    """Write the sole Change.approved record create-only."""
    commit, path, decision_sha256 = proof
    approval_rel = f"changes/{change_id}/approval.json"
    record = {
        "schema": _APPROVAL_SCHEMA,
        "change_id": change_id,
        "revision": sha,
        "report": report_ref,
        "report_sha256": report_sha256,
        "attempt": attempt,
        "approved_by": approved_by,
        "proof": {"commit": commit, "path": path, "sha256": decision_sha256},
    }
    if not write_create_only(records, approval_rel, canonical_json(record)):
        raise _refuse("approval.exists")
    return {
        "ok": True,
        "change_id": change_id,
        "revision": sha,
        "approval": approval_rel,
        "approved_by": approved_by,
        "proof": record["proof"],
    }


def _valid_approval(record: object, change_id: str) -> bool:
    if not isinstance(record, dict) or set(record) != _APPROVAL_KEYS:
        return False
    proof = record.get("proof")
    return bool(
        record.get("schema") == _APPROVAL_SCHEMA
        and record.get("change_id") == change_id
        and isinstance(record.get("revision"), str)
        and _FULL_SHA.fullmatch(record["revision"]) is not None
        and isinstance(record.get("report"), str)
        and re.fullmatch(
            rf"changes/{re.escape(change_id)}/report/[1-9][0-9]*\.json",
            record["report"],
        )
        and isinstance(record.get("report_sha256"), str)
        and _DIGEST.fullmatch(record["report_sha256"]) is not None
        and (
            record.get("attempt") is None
            or (type(record["attempt"]) is int and record["attempt"] >= 1)
        )
        and valid_actor(record.get("approved_by"))
        and isinstance(proof, dict)
        and set(proof) == _PROOF_KEYS
        and isinstance(proof.get("commit"), str)
        and _FULL_SHA.fullmatch(proof["commit"]) is not None
        and isinstance(proof.get("path"), str)
        and proof["path"]
        == approval_path(
            change_id,
            int(record["report"].rsplit("/", 1)[1][:-5]),
        )
        and isinstance(proof.get("sha256"), str)
        and _DIGEST.fullmatch(proof["sha256"]) is not None
    )


@beddel_tool(
    name="profile_approve_change",
    description="Revalidate a Change and accept its Approval from a committed decision",
    category="profile",
)
def profile_approve_change(
    repo_path: str,
    change_id: str,
    revision: str,
    actor: str,
    decision_commit: str,
) -> dict[str, Any]:
    """Revalidate and persist one Approval from a committed decision."""
    config = load_config()
    if not is_valid_id(change_id):
        raise _refuse("id.invalid")
    if not valid_actor(actor):
        raise _refuse("actor.invalid")
    repo = real_repo_root(repo_path)
    records = records_root(repo, config.records_dir)
    try:
        sha = resolve_revision(repo, revision)
    except ProfileError:
        raise _refuse("revision.invalid") from None

    approval_rel = f"changes/{change_id}/approval.json"
    try:
        approval_file = confined(records, approval_rel)
    except ProfileError:
        raise _refuse("approval.exists") from None
    if approval_file.exists() or approval_file.is_symlink():
        raise _refuse("approval.exists")

    ordinal, latest, report_ref, report_sha256 = _revalidate(
        repo, records, change_id, sha
    )
    proof = _verify_decision(
        repo,
        change_id,
        sha,
        actor,
        decision_commit,
        ordinal,
        report_ref,
        report_sha256,
    )
    return _write_approval(
        records,
        change_id,
        sha,
        report_ref,
        report_sha256,
        latest["attempt"],
        actor,
        proof,
    )


@beddel_tool(
    name="profile_read_approval",
    description="Read the stored Change Approval without writing records",
    category="profile",
)
def profile_read_approval(repo_path: str, change_id: str) -> dict[str, Any]:
    """Read the stored Change Approval record, if present."""
    config = load_config()
    if not is_valid_id(change_id):
        raise ProfileError(PROFILE_CHANGE_INVALID, "change id invalid")
    repo = real_repo_root(repo_path)
    records = records_root(repo, config.records_dir)
    reader = _Reader(records)
    change = reader.json(f"changes/{change_id}/change.json")
    if not _valid_change(change, change_id):
        raise _unbound()
    approval_rel = f"changes/{change_id}/approval.json"
    raw = reader.read(approval_rel)
    if raw is None:
        approval: dict[str, Any] | None = None
    else:
        try:
            approval = json.loads(raw)
        except (TypeError, ValueError, RecursionError):
            raise ProfileError(
                PROFILE_REPOSITORY_INVALID,
                "repository or revision invalid",
            ) from None
        if not _valid_approval(approval, change_id):
            raise ProfileError(
                PROFILE_REPOSITORY_INVALID,
                "repository or revision invalid",
            )
    return {"ok": True, "change_id": change_id, "approval": approval}
