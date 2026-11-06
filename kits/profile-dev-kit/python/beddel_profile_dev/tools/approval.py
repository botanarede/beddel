"""Refuse every Change Approval until Story 5.2 accepts a decision."""

from __future__ import annotations

import hashlib
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import PROFILE_APPROVAL_REFUSED, ProfileError
from beddel_profile_dev._io import real_repo_root, records_root, resolve_revision
from beddel_profile_dev.config import load_config
from beddel_profile_dev.inventory import is_valid_id
from beddel_profile_dev.tools.ratify import valid_actor
from beddel_profile_dev.tools.report import (
    _DIGEST,
    REPORT_SCHEMA,
    _derive_report,
    _latest_attempt,
    _load_change,
    _Reader,
    _report_history,
    _valid_change,
)

__all__ = ["profile_approve_change"]


def _refuse(reason: str) -> ProfileError:
    return ProfileError(
        PROFILE_APPROVAL_REFUSED,
        f"approval refused: {reason}",
        {"reason": reason},
    )


def _valid_latest_report(report: dict[str, Any]) -> bool:
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


@beddel_tool(
    name="profile_approve_change",
    description="Revalidate a Change Approval request without accepting or writing it",
    category="profile",
)
def profile_approve_change(
    repo_path: str, change_id: str, revision: str, actor: str
) -> dict[str, Any]:
    """Revalidate the latest Report and refuse the Approval request.

    Raises:
        ProfileError: ``PROFILE_APPROVAL_REFUSED`` with a fixed reason code;
            no record is written on refusal.
    """
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

    reader = _Reader(records)
    try:
        change = reader.json(f"changes/{change_id}/change.json")
    except (ProfileError, OSError, ValueError):
        raise _refuse("change.unrecorded") from None
    if not _valid_change(change, change_id):
        raise _refuse("change.unrecorded")
    try:
        _load_change(reader, repo, change_id, sha)
    except ProfileError:
        raise _refuse("revision.unlinked") from None

    try:
        history = _report_history(reader, records, change_id)
    except ProfileError:
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
    except (ProfileError, OSError, ValueError):
        raise _refuse("verdict.underivable") from None
    if derived.get("verdict") != latest.get("verdict"):
        raise _refuse("verdict.mismatch")
    if derived.get("verdict") == "has pendency":
        raise _refuse("verdict.has_pendency")
    raise _refuse("approval.unaccepted")
