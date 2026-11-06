"""Transport for a committed human Approval decision."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import yaml
from beddel.tools import beddel_tool

from beddel_profile_dev._errors import PROFILE_APPROVAL_REFUSED, ProfileError
from beddel_profile_dev._io import (
    confined,
    in_head_history,
    in_index,
    real_repo_root,
    records_root,
    resolve_revision,
    write_create_only,
)
from beddel_profile_dev.config import load_config
from beddel_profile_dev.inventory import is_valid_id
from beddel_profile_dev.tools.ratify import TIMESTAMP_FORMAT, valid_actor
from beddel_profile_dev.tools.report import (
    _Reader,
    _report_history,
    _valid_change,
)

__all__ = [
    "APPROVAL_DECISION_SCHEMA",
    "approval_path",
    "profile_record_approval_decision",
]

APPROVAL_DECISION_SCHEMA = "profile-dev/approval-decision/1"


def approval_path(change_id: str, ordinal: int) -> str:
    """Return the repository-relative decision path for a Report ordinal."""
    return f".beddel-profile/approvals/{change_id}/{ordinal}.yaml"


def _refuse(reason: str) -> ProfileError:
    return ProfileError(
        PROFILE_APPROVAL_REFUSED,
        f"approval decision refused: {reason}",
        {"reason": reason},
    )


@beddel_tool(
    name="profile_record_approval_decision",
    description="Record an Approval decision for the maintainer to commit",
    category="profile",
)
def profile_record_approval_decision(
    repo_path: str, change_id: str, revision: str, actor: str
) -> dict[str, Any]:
    """Write one uncommitted Approval decision create-only."""
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
        history = _report_history(reader, records, change_id)
    except (ProfileError, OSError, ValueError):
        raise _refuse("report.malformed") from None
    if not history:
        raise _refuse("report.absent")
    ordinal, latest = history[-1]
    report_ref = f"changes/{change_id}/report/{ordinal}.json"
    if latest.get("revision") != sha:
        raise _refuse("revision.not_reported")

    path = approval_path(change_id, ordinal)
    try:
        decision = confined(repo, path)
    except ProfileError:
        raise _refuse("decision.exists") from None
    if decision.exists() or decision.is_symlink():
        raise _refuse("decision.exists")
    try:
        in_history = in_index(repo, path) or in_head_history(repo, path)
    except ProfileError:
        raise _refuse("history.unreadable") from None
    if in_history:
        raise _refuse("decision.exists")

    report_sha256 = reader.reads[report_ref]
    record = {
        "schema": APPROVAL_DECISION_SCHEMA,
        "change_id": change_id,
        "revision": sha,
        "report": report_ref,
        "report_sha256": report_sha256,
        "approved_by": actor,
        "approved_at": datetime.now(UTC).strftime(TIMESTAMP_FORMAT),
    }
    text = yaml.safe_dump(record, sort_keys=False, allow_unicode=True).encode("utf-8")
    if not write_create_only(repo, path, text):
        raise _refuse("decision.exists")
    return {
        "ok": True,
        "change_id": change_id,
        "revision": sha,
        "report": report_ref,
        "report_sha256": report_sha256,
        "approved_by": actor,
        "record": path,
    }
