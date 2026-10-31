"""Open an immutable, append-only VerificationAttempt scope."""

from __future__ import annotations

import hashlib
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
    confined,
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

__all__ = ["ATTEMPT_SCHEMA", "profile_open_attempt"]

ATTEMPT_SCHEMA = "profile-dev/verification-attempt/1"


def _unscoped() -> ProfileError:
    return ProfileError(
        PROFILE_ATTEMPT_UNSCOPED,
        "attempt needs a valid impact record and bound snapshot",
    )


def _conflict() -> ProfileError:
    return ProfileError(PROFILE_ATTEMPT_CONFLICT, "verification attempt already exists")


def _claim(records: Path, relative: str) -> int:
    directory = confined(records, relative)
    taken = []
    if directory.is_dir():
        for entry in directory.iterdir():
            if re.fullmatch(r"[1-9][0-9]*", entry.name):
                taken.append(int(entry.name))
    attempt = max(taken, default=0) + 1
    for _ in range(100):
        target = confined(records, f"{relative}/{attempt}")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            confined(records, f"{relative}/{attempt}")
            target.mkdir()
        except FileExistsError:
            attempt += 1
            continue
        except (OSError, RuntimeError, ValueError) as error:
            raise ProfileError(
                PROFILE_REPOSITORY_INVALID, "repository or revision invalid"
            ) from error
        return attempt
    raise _conflict()


def _requirements(impact: dict[str, Any]) -> list[dict[str, str]]:
    raw = impact.get("required_evidence")
    if not isinstance(raw, list):
        raise _unscoped()
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise _unscoped()
        values_raw = tuple(
            item.get(k) for k in ("class", "affected_point", "criterion")
        )
        kind = item.get("kind")
        if not all(
            isinstance(value, str) and is_valid_id(value) for value in values_raw
        ):
            raise _unscoped()
        if not isinstance(kind, str) or kind not in {"gate", "review"}:
            raise _unscoped()
        values: tuple[str, str, str] = cast(tuple[str, str, str], values_raw)
        if values in seen:
            raise _unscoped()
        seen.add(values)
        result.append(
            {
                "class": values[0],
                "affected_point": values[1],
                "criterion": values[2],
                "kind": kind,
            }
        )
    return sorted(
        result,
        key=lambda item: (item["class"], item["affected_point"], item["criterion"]),
    )


@beddel_tool(
    name="profile_open_attempt",
    description="Persist the immutable VerificationAttempt scope after Impact",
    category="profile",
)
def profile_open_attempt(
    repo_path: str, change_id: str, revision: str
) -> dict[str, Any]:
    """Persist the next strictly increasing attempt ordinal for a Change."""
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
        impact = _read_scope(records, impact_rel, change_id, sha, raw=impact_raw)
        snapshot_rel = f"revisions/{sha}/snapshot.json"
        snapshot_raw = read_confined(records, snapshot_rel)
        snapshot = _bound_snapshot(records, sha, snapshot_raw=snapshot_raw)
    except ProfileError as error:
        if error.code == PROFILE_REPOSITORY_INVALID:
            raise
        raise _unscoped() from None
    if impact.get("inventory_version") != snapshot.get(
        "inventory_version"
    ) or impact.get("inventory_sha256") != snapshot.get("inventory_sha256"):
        raise _unscoped()
    requirements = _requirements(impact)
    if snapshot_raw is None:
        raise _unscoped()
    ordinal = _claim(records, f"{revision_rel}/attempts")
    attempt_rel = f"{revision_rel}/attempts/{ordinal}/attempt.json"
    record = {
        "schema": ATTEMPT_SCHEMA,
        "attempt": ordinal,
        "change_id": change_id,
        "base": impact["base"],
        "revision": sha,
        "inventory_version": impact["inventory_version"],
        "inventory_sha256": impact["inventory_sha256"],
        "snapshot_ref": snapshot_rel,
        "snapshot_sha256": hashlib.sha256(snapshot_raw).hexdigest(),
        "impact_ref": impact_rel,
        "impact_sha256": hashlib.sha256(impact_raw).hexdigest(),
        "requirements": requirements,
    }
    if not write_create_only(records, attempt_rel, canonical_json(record)):
        raise _conflict()
    return {
        "ok": True,
        "change_id": change_id,
        "revision": sha,
        "attempt": ordinal,
        "attempt_ref": attempt_rel,
    }
