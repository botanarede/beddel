"""Pure fix contracts."""

# fmt: off
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from beddel_profile_dev.implement import STORY_TRAILER, Unit

FIX_TRAILER = "Fix-Round"
MAX_FIX_ROUNDS = 2
MAX_FINDINGS_BYTES = 32768
FIXABLE_REASONS = frozenset({"finding_blocking", "finding_unclassified"})
_ROUND = re.compile(r"[1-2]")


def fix_message(story_key: str, round_: int) -> tuple[str, str]:
    """Return the subject and trailers for a fix commit."""
    return (f"fix: apply verification fixes (round {round_})", f"{STORY_TRAILER}: {story_key}\n{FIX_TRAILER}: {round_}")


def trailer_round(message: str, story_key: str) -> int | None:
    """Return the valid fix-round trailer in a commit message."""
    if not isinstance(message, str):
        return None
    lines = message.splitlines()
    story = [line for line in lines if line == f"{STORY_TRAILER}: {story_key}"]
    rounds = [line for line in lines if line.startswith(f"{FIX_TRAILER}: ")]
    if len(story) != 1 or len(rounds) != 1:
        return None
    value = rounds[0][len(f"{FIX_TRAILER}: ") :]
    return int(value) if _ROUND.fullmatch(value) else None


def report_at(history: object, head: str) -> dict[str, Any] | None:
    """Return the last report recorded at ``head``."""
    selected: dict[str, Any] | None = None
    if not isinstance(history, Iterable) or isinstance(history, (str, bytes)):
        return None
    for entry in history:
        content = entry.get("content") if isinstance(entry, Mapping) else None
        if isinstance(content, Mapping) and content.get("revision") == head:
            selected = dict(content)
    return selected


def fix_findings(report: object) -> list[dict[str, Any]]:
    """Return Findings named by fixable Pendencies in index order."""
    if not isinstance(report, Mapping) or not isinstance(report.get("items"), Mapping):
        return []
    items = report["items"]
    divergences, pendencies = items.get("divergences"), items.get("pendencies")
    if not isinstance(divergences, Mapping) or not isinstance(pendencies, Mapping):
        return []
    values, pending = divergences.get("value"), pendencies.get("value")
    if divergences.get("status") != "present" or pendencies.get("status") != "present" or not isinstance(values, list) or not isinstance(pending, list):
        return []
    indexes = {item["finding_index"] for item in pending if isinstance(item, Mapping) and item.get("reason") in FIXABLE_REASONS and type(item.get("finding_index")) is int and item["finding_index"] >= 0}
    keys = ("source", "association", "class", "affected_point", "criterion", "kind", "between", "detail")
    return [{key: values[index].get(key) for key in keys} for index in sorted(indexes) if index < len(values) and isinstance(values[index], Mapping)]


def decision(report: object, rounds: int, max_rounds: int) -> tuple[str | None, str | None]:
    """Return the stage decision for one Report."""
    if not isinstance(report, Mapping):
        return "failed", "report.unreadable"
    verdict = report.get("verdict")
    if verdict == "consistent":
        return "succeeded", "verdict.consistent"
    if verdict != "has pendency":
        return "failed", "report.unreadable"
    if not fix_findings(report):
        return "stopped", "pendency.no_fixes"
    if rounds >= max_rounds:
        return "stopped", "fix.bound_reached"
    return None, None


def scope_paths(units: Iterable[Unit]) -> tuple[str, ...]:
    return tuple(sorted({path for unit in units for path in unit.paths}))
# fmt: on
