from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import PROFILE_STAGE_OUTCOME_REFUSED, ProfileError
from beddel_profile_dev.hook_proof import (
    count_log,
    null_keys,
    open_run,
    remove_pointer,
    write_pointer,
)


def _runtime_failure(stage: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": False, "reason": "hooks.unavailable"}
    if stage is not None:
        result["stage"] = stage
    return result


@beddel_tool(
    name="profile_hook_open",
    description="Open one private per-stage hook run and copy its tracked policy",
    category="profile",
)
def profile_hook_open(stage: str) -> dict[str, Any]:
    try:
        return open_run(stage)
    except Exception:  # noqa: BLE001
        return _runtime_failure(stage)


@beddel_tool(
    name="profile_hook_arm",
    description="Arm the exclusive Kiro hook pointer for the repository cwd",
    category="profile",
)
def profile_hook_arm(
    repo_path: str, stage: str, hook: Mapping[str, Any] | None
) -> dict[str, Any]:
    try:
        if not isinstance(hook, Mapping):
            return {
                "armed": False,
                "reason": "hooks.unavailable",
                "stage": stage,
                "log_path": None,
                "pointer_sha256": None,
            }
        return write_pointer(repo_path, stage, hook)
    except Exception:  # noqa: BLE001
        return {
            "armed": False,
            "reason": "hooks.unavailable",
            "stage": stage,
            "log_path": hook.get("log_path") if isinstance(hook, Mapping) else None,
            "pointer_sha256": None,
        }


@beddel_tool(
    name="profile_hook_disarm",
    description="Remove a Kiro hook pointer only when its bytes are unchanged",
    category="profile",
)
def profile_hook_disarm(
    repo_path: str, armed: Mapping[str, Any] | None
) -> dict[str, bool]:
    try:
        return remove_pointer(repo_path, armed)
    except Exception:  # noqa: BLE001
        return {"removed": False}


@beddel_tool(
    name="profile_hook_proof",
    description="Merge hook counts and proof gates into a Stage outcome",
    category="profile",
)
def profile_hook_proof(
    stage: str,
    hook: Mapping[str, Any] | None,
    calls: list[Mapping[str, Any] | None] | None,
    settled: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(settled, Mapping):
        raise ProfileError(
            PROFILE_STAGE_OUTCOME_REFUSED,
            "stage outcome refused",
            {"reason": "settled.invalid"},
        )
    refs = settled.get("refs")
    base_refs = dict(refs) if isinstance(refs, Mapping) else {}
    entries = calls if isinstance(calls, list) else ([] if calls is None else [calls])
    armed_entries = [
        item
        for item in entries
        if isinstance(item, Mapping) and item.get("armed") is True
    ]
    n_calls = len(armed_entries)
    hook_keys = null_keys()

    refusal = next(
        (
            item.get("reason") or "hooks.unavailable"
            for item in entries
            if isinstance(item, Mapping) and item.get("armed") is not True
        ),
        None,
    )
    if refusal is not None:
        return {
            "stage": stage,
            "story_key": settled.get("story_key"),
            "outcome": "failed",
            "reason": refusal if isinstance(refusal, str) else "hooks.unavailable",
            "refs": {**base_refs, **hook_keys},
        }
    if n_calls == 0:
        return {
            "stage": stage,
            "story_key": settled.get("story_key"),
            "outcome": settled.get("outcome"),
            "reason": settled.get("reason"),
            "refs": {**base_refs, **hook_keys},
        }

    log_path = hook.get("log_path") if isinstance(hook, Mapping) else None
    policy_digest = hook.get("policy_sha256") if isinstance(hook, Mapping) else None
    counts = count_log(log_path, policy_digest) if isinstance(log_path, str) else None
    if counts is None:
        reason: str | None = "hooks.missing"
    else:
        hook_keys = counts
        reason = (
            "hooks.errors"
            if counts["hook_errors"] > 0
            else ("hooks.missing" if counts["hook_stop"] != n_calls else None)
        )
    return {
        "stage": stage,
        "story_key": settled.get("story_key"),
        "outcome": "failed" if reason is not None else settled.get("outcome"),
        "reason": reason if reason is not None else settled.get("reason"),
        "refs": {**base_refs, **hook_keys},
    }
