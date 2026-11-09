"""Read-only access to a recorded Re-verification for publication."""

from __future__ import annotations

import hashlib
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import PROFILE_PUBLICATION_REFUSED, ProfileError
from beddel_profile_dev._io import real_repo_root, records_root
from beddel_profile_dev.config import load_config
from beddel_profile_dev.inventory import is_valid_id
from beddel_profile_dev.tools.report import (
    _DIGEST,
    REPORT_SCHEMA,
    _Reader,
    _report_history,
    _valid_change,
)

__all__ = ["profile_read_reverification"]


def _valid_latest_report(report: dict[str, Any]) -> bool:
    """Check the fields of a stored Report that the digest re-read relies on.

    Kept local: the structural boundary test keeps every module but the
    decision modules free of any import of them.
    """
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


def _refuse(reason: str) -> ProfileError:
    return ProfileError(
        PROFILE_PUBLICATION_REFUSED,
        f"publication refused: {reason}",
        {"reason": reason},
    )


@beddel_tool(
    name="profile_read_reverification",
    description="Read the recorded Re-verification entry of the latest stored Report without writing records",
    category="profile",
)
def profile_read_reverification(repo_path: str, change_id: str) -> dict[str, Any]:
    """Read the latest recorded Re-verification without changing records."""
    if not is_valid_id(change_id):
        raise _refuse("id.invalid")

    repo = real_repo_root(repo_path)
    records = records_root(repo, load_config().records_dir)
    reader = _Reader(records)
    if not _valid_change(reader.json(f"changes/{change_id}/change.json"), change_id):
        raise _refuse("change.unrecorded")

    try:
        history = _report_history(reader, records, change_id)
    except (ProfileError, OSError, ValueError, RecursionError):
        raise _refuse("report.malformed") from None
    if not history:
        raise _refuse("report.absent")

    ordinal, latest = history[-1]
    if latest.get("schema") != REPORT_SCHEMA:
        raise _refuse("reverification.not_recorded")
    if not _valid_latest_report(latest):
        raise _refuse("report.malformed")

    for item in latest["reads"]:
        try:
            raw = reader.read(item["ref"])
        except (ProfileError, OSError, ValueError):
            raise _refuse("digest.mismatch") from None
        if raw is None or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise _refuse("digest.mismatch")

    reverification = latest.get("reverification")
    if (
        not isinstance(reverification, dict)
        or reverification.get("status") != "recorded"
    ):
        raise _refuse("reverification.not_recorded")

    report_ref = f"changes/{change_id}/report/{ordinal}.json"
    return {
        "ok": True,
        "change_id": change_id,
        "report": report_ref,
        "report_sha256": reader.reads[report_ref],
        "reverification": reverification,
    }
