"""Pure contracts for the profile implement stage."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from beddel_profile_dev.plan import (
    MAX_SPEC_BYTES,
    front_matter,
    relative_path,
    spec_complete,
)

__all__ = [
    "MAX_UNITS",
    "MAX_UNIT_PATHS",
    "PROTECTED_BRANCHES",
    "STORY_TRAILER",
    "SUBJECT",
    "UNIT_ID",
    "UNIT_TRAILER",
    "Unit",
    "branch_reason",
    "commit_message",
    "covered",
    "spec_units",
    "trailer_unit",
]

UNIT_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
MAX_UNITS = 32
MAX_UNIT_PATHS = 64
SUBJECT = re.compile(
    r"(?:build|chore|docs|feat|fix|perf|refactor|test)"
    r"(?:\([a-z0-9._-]{1,64}\))?: [^\x00-\x1f\x7f]{1,100}"
)
PROTECTED_BRANCHES = ("main", "master", "mainline")
STORY_TRAILER = "Story-Key"
UNIT_TRAILER = "Implementation-Unit"
_BRANCH = re.compile(r"[a-z0-9][a-z0-9._/-]{0,127}")


@dataclass(frozen=True)
class Unit:
    """One ordered implementation unit from a complete plan spec."""

    id: str
    paths: tuple[str, ...]
    subject: str


def _valid_unit(value: object) -> Unit | None:
    if not isinstance(value, Mapping) or set(value) != {"id", "paths", "subject"}:
        return None
    unit_id = value["id"]
    paths = value["paths"]
    subject = value["subject"]
    if not isinstance(unit_id, str) or UNIT_ID.fullmatch(unit_id) is None:
        return None
    if (
        not isinstance(paths, list)
        or not 1 <= len(paths) <= MAX_UNIT_PATHS
        or len(set(paths)) != len(paths)
        or not all(
            isinstance(path, str) and len(path) <= 512 and relative_path(path)
            for path in paths
        )
    ):
        return None
    if not isinstance(subject, str) or SUBJECT.fullmatch(subject) is None:
        return None
    return Unit(unit_id, tuple(paths), subject)


def spec_units(data: bytes, story_key: str) -> tuple[Unit, ...] | None:
    """Return validated implementation units, or ``None`` for an incomplete spec."""
    if len(data) > MAX_SPEC_BYTES or not spec_complete(data, story_key):
        return None
    metadata = front_matter(data)
    if metadata is None:
        return None
    values = metadata.get("units")
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_UNITS:
        return None
    units: list[Unit] = []
    seen: set[str] = set()
    for value in values:
        unit = _valid_unit(value)
        if unit is None or unit.id in seen:
            return None
        seen.add(unit.id)
        units.append(unit)
    return tuple(units)


def branch_reason(branch: object, base_ref: object) -> str | None:
    """Return the refusal reason for a branch/base pair, if any."""
    if not isinstance(branch, str) or _BRANCH.fullmatch(branch) is None:
        return "branch.invalid"
    parts = branch.split("/")
    if (
        branch in PROTECTED_BRANCHES
        or branch == base_ref
        or branch.startswith("-")
        or branch.endswith(("/", "."))
        or any(p.startswith(".") or p.endswith(".lock") for p in parts)
        or ".." in branch
        or "//" in branch
        or "@{" in branch
    ):
        return (
            "branch.protected"
            if branch in PROTECTED_BRANCHES or branch == base_ref
            else "branch.invalid"
        )
    return None


def covered(paths: tuple[str, ...] | list[str], path: str) -> bool:
    """Return whether a changed path belongs to a unit's file or directory paths."""
    return any(path == item or path.startswith(item + "/") for item in paths)


def commit_message(unit: Unit, story_key: str) -> tuple[str, str]:
    """Return the subject and trailer paragraph for a unit commit."""
    return unit.subject, f"{STORY_TRAILER}: {story_key}\n{UNIT_TRAILER}: {unit.id}"


def trailer_unit(message: str, story_key: str) -> str | None:
    """Return a unit id when a commit message has exactly the required trailers."""
    if not isinstance(message, str):
        return None
    story_lines = [
        line for line in message.splitlines() if line == f"{STORY_TRAILER}: {story_key}"
    ]
    unit_lines = [
        line for line in message.splitlines() if line.startswith(f"{UNIT_TRAILER}: ")
    ]
    if len(story_lines) != 1 or len(unit_lines) != 1:
        return None
    unit_id = unit_lines[0][len(f"{UNIT_TRAILER}: ") :]
    return unit_id if UNIT_ID.fullmatch(unit_id) is not None else None
