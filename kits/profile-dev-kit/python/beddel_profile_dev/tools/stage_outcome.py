"""Append-only Stage outcome records for profile Delivery stages."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import (
    PROFILE_REPOSITORY_INVALID,
    PROFILE_STAGE_OUTCOME_REFUSED,
    ProfileError,
)
from beddel_profile_dev._io import (
    canonical_json,
    confined,
    real_repo_root,
    records_root,
    write_create_only,
)
from beddel_profile_dev.config import load_config
from beddel_profile_dev.plan import STORY_KEY
from beddel_profile_dev.tools.ratify import TIMESTAMP_FORMAT

__all__ = ["OUTCOMES", "STAGE_OUTCOME_SCHEMA", "profile_record_stage_outcome"]

STAGE_OUTCOME_SCHEMA = "profile-dev/stage-outcome/1"
OUTCOMES = ("succeeded", "refused", "failed", "stopped")
_STAGE = re.compile(r"[a-z][a-z0-9-]{0,31}")
_REASON = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*")
_TOKEN = re.compile(r"(?:gh[pousr]_\w{10,}|github_pat_\w{10,})")
_REF_KEY = re.compile(r"[a-z][a-z0-9_]{0,31}")


def _refuse(reason: str) -> ProfileError:
    return ProfileError(
        PROFILE_STAGE_OUTCOME_REFUSED,
        "stage outcome refused",
        {"reason": reason},
    )


def _has_control(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


def _valid_refs(refs: object) -> bool:
    if not isinstance(refs, dict) or len(refs) > 16:
        return False
    for key, value in refs.items():
        if not isinstance(key, str) or _REF_KEY.fullmatch(key) is None:
            return False
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, int):
            if not 0 <= value <= 10**9:
                return False
            continue
        if (
            not isinstance(value, str)
            or len(value) > 512
            or _has_control(value)
            or _TOKEN.search(value) is not None
        ):
            return False
    return True


def _next_ordinal(records: Path) -> int:
    directory = confined(records, "stage-outcomes")
    if not directory.exists():
        return 1
    if not directory.is_dir():
        raise ProfileError(PROFILE_REPOSITORY_INVALID, "repository or revision invalid")
    values = [
        int(match.group(1))
        for entry in directory.iterdir()
        if (match := re.fullmatch(r"([1-9][0-9]*)\.json", entry.name)) is not None
    ]
    return max(values, default=0) + 1


def _validate_fields(
    story_key: object,
    stage: object,
    outcome: object,
    reason: object,
    refs: object,
) -> None:
    if not isinstance(stage, str) or _STAGE.fullmatch(stage) is None:
        raise _refuse("stage.invalid")
    if outcome not in OUTCOMES:
        raise _refuse("outcome.invalid")
    if (
        not isinstance(reason, str)
        or len(reason) > 64
        or _REASON.fullmatch(reason) is None
    ):
        raise _refuse("reason.invalid")
    if story_key is not None and (
        not isinstance(story_key, str) or STORY_KEY.fullmatch(story_key) is None
    ):
        raise _refuse("story_key.invalid")
    if story_key is None and outcome != "refused":
        raise _refuse("story_key.required")
    if not _valid_refs(refs):
        raise _refuse("refs.invalid")


@beddel_tool(
    name="profile_record_stage_outcome",
    description="Append one create-only Stage outcome record outside the repository",
    category="profile",
)
def profile_record_stage_outcome(
    repo_path: str,
    story_key: str | None,
    stage: str,
    outcome: str,
    reason: str,
    refs: dict[str, Any],
) -> dict[str, Any]:
    """Validate and append one Stage outcome record."""
    _validate_fields(story_key, stage, outcome, reason, refs)
    repo = real_repo_root(repo_path)
    records = records_root(repo, load_config().records_dir)
    ordinal = _next_ordinal(records)
    record = {
        "schema": STAGE_OUTCOME_SCHEMA,
        "record": ordinal,
        "stage": stage,
        "story_key": story_key,
        "outcome": outcome,
        "reason": reason,
        "refs": refs,
        "recorded_at": datetime.now(UTC).strftime(TIMESTAMP_FORMAT),
    }
    for _ in range(100):
        if write_create_only(
            records, f"stage-outcomes/{ordinal}.json", canonical_json(record)
        ):
            return {
                "ok": True,
                "record": ordinal,
                "path": f"stage-outcomes/{ordinal}.json",
                "stage": stage,
                "story_key": story_key,
                "outcome": outcome,
                "reason": reason,
            }
        ordinal += 1
        record["record"] = ordinal
    raise ProfileError("PROFILE_REPOSITORY_INVALID", "repository or revision invalid")
