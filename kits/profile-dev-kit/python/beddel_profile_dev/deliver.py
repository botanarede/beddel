"""Pure contracts for the chained profile Delivery workflow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from beddel_profile_dev.implement import MAX_UNITS

__all__ = [
    "COMPLETE",
    "IMPLEMENT_SLOTS",
    "REQUESTS",
    "STAGES",
    "complete",
    "next_stage",
    "resume",
]

STAGES = ("plan", "implement", "verify-and-fix", "approval", "integrate")
REQUESTS = ("all", *STAGES)
IMPLEMENT_SLOTS = MAX_UNITS + 1
COMPLETE = {
    "plan": ("spec.created", "spec.reconciled", "spec.reused"),
    "implement": ("units.complete",),
    "verify-and-fix": ("verdict.consistent",),
    "approval": ("approval.recorded", "approval.reused"),
    "integrate": ("integrate.complete",),
}


def complete(stage: object, outcome: object, reason: object) -> bool:
    """Return whether a stage outcome is a complete stage boundary."""
    return (
        isinstance(stage, str)
        and isinstance(outcome, str)
        and outcome == "succeeded"
        and reason in COMPLETE.get(stage, ())
    )


def next_stage(stage: str) -> str | None:
    """Return the next Delivery stage after ``stage``."""
    try:
        index = STAGES.index(stage)
    except ValueError:
        return None
    return STAGES[index + 1] if index + 1 < len(STAGES) else None


def resume(records: list[Mapping[str, Any]]) -> tuple[str | None, bool]:
    """Choose the next stage from the story's ordered Stage outcomes."""
    if not records:
        return "plan", False
    latest = records[-1]
    stage = latest.get("stage")
    outcome = latest.get("outcome")
    reason = latest.get("reason")
    if complete(stage, outcome, reason):
        following = next_stage(stage) if isinstance(stage, str) else None
        return (following, False) if following is not None else (None, True)
    return (stage if stage in STAGES else "plan"), False
