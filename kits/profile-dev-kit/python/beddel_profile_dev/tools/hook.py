from __future__ import annotations

import time
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

AGENT_TIMEOUT_SECONDS = 600
_clock = time.monotonic_ns


def _runtime_failure(stage: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "reason": "hooks.unavailable",
        "native": False,
        "method": False,
    }
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
    repo_path: str,
    stage: str,
    hook: Mapping[str, Any] | None,
    method: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        if not isinstance(hook, Mapping):
            return {
                **_runtime_failure(stage),
                "log_path": None,
                "pointer_sha256": None,
            }
        result = write_pointer(repo_path, stage, hook)
        result.update(native=False, method=False, instruction_sha256=None)
        if result.get("armed") is True:
            result["started_ns"] = _clock()
            if (
                isinstance(method, Mapping)
                and method.get("stage") == stage
                and isinstance(method.get("instruction"), str)
            ):
                result.update(
                    native=False,
                    method=True,
                    instruction_sha256=method.get("instruction_sha256"),
                )
            elif not isinstance(method, Mapping):
                result["native"] = True
            else:
                result["armed"] = False
                result["reason"] = "hooks.unavailable"
                remove_pointer(repo_path, result)
        return result
    except Exception:  # noqa: BLE001
        return {
            **_runtime_failure(stage),
            "log_path": hook.get("log_path") if isinstance(hook, Mapping) else None,
            "pointer_sha256": None,
            "instruction_sha256": None,
        }


@beddel_tool(
    name="profile_hook_disarm",
    description="Remove a Kiro hook pointer only when its bytes are unchanged",
    category="profile",
)
def profile_hook_disarm(
    repo_path: str,
    armed: Mapping[str, Any] | None,
    agent: object = None,
) -> dict[str, Any]:
    if not isinstance(armed, Mapping) or armed.get("armed") is not True:
        return {
            "removed": False,
            "armed": False,
            "agent_ms": None,
            "agent_state": None,
            "instruction_sha256": None,
        }
    try:
        removed = remove_pointer(repo_path, armed)
    except Exception:  # noqa: BLE001
        removed = {"removed": False}
    started = armed.get("started_ns")
    if not isinstance(started, int):
        return {
            **removed,
            "armed": True,
            "agent_ms": None,
            "agent_state": "failed",
            "instruction_sha256": armed.get("instruction_sha256"),
        }
    elapsed = max(0, (_clock() - started) // 10**6)
    state = (
        "ok"
        if isinstance(agent, Mapping)
        else ("timeout" if elapsed >= AGENT_TIMEOUT_SECONDS * 1000 else "failed")
    )
    return {
        **removed,
        "armed": True,
        "agent_ms": elapsed,
        "agent_state": state,
        "instruction_sha256": armed.get("instruction_sha256"),
    }


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
    timings: list[Mapping[str, Any] | None] | None = None,
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
    hook_keys: dict[str, Any] = null_keys()
    timing_values: list[int] = []
    timeout_count = 0
    unmeasured = False
    timeout = False
    if isinstance(timings, list):
        hook_keys.update(agent_ms=None, agent_timeouts=None, instruction_sha256=None)
        for index, item in enumerate(entries):
            if not isinstance(item, Mapping) or item.get("armed") is not True:
                continue
            timing = timings[index] if index < len(timings) else None
            if not isinstance(timing, Mapping) or not isinstance(
                timing.get("agent_ms"), int
            ):
                unmeasured = True
                continue
            timing_values.append(timing["agent_ms"])
            if timing.get("agent_state") == "timeout":
                timeout_count += 1
                timeout = True
        if len(timing_values) != n_calls:
            unmeasured = True

    refusal = next(
        (
            item.get("reason") or "hooks.unavailable"
            for item in entries
            if isinstance(item, Mapping) and item.get("armed") is not True
        ),
        None,
    )
    if refusal is not None:
        refusal_reason = refusal if isinstance(refusal, str) else "hooks.unavailable"
        return {
            "stage": stage,
            "story_key": settled.get("story_key"),
            "outcome": "failed",
            "reason": refusal_reason,
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
        hook_keys.clear()
        hook_keys.update(null_keys())
    else:
        hook_keys = counts
        reason = (
            "hooks.missing"
            if counts["hook_stop"] != n_calls
            else ("hooks.errors" if counts["hook_errors"] > 0 else None)
        )
    if isinstance(timings, list):
        hook_keys["agent_ms"] = (
            ",".join(str(value) for value in timing_values) if timing_values else None
        )
        hook_keys["agent_timeouts"] = timeout_count
        hook_keys["instruction_sha256"] = next(
            (
                item.get("instruction_sha256")
                for item in entries
                if isinstance(item, Mapping)
                and isinstance(item.get("instruction_sha256"), str)
            ),
            None,
        )
        if unmeasured:
            reason = "agent.unmeasured"
        elif timeout:
            reason = "agent.timeout"
    return {
        "stage": stage,
        "story_key": settled.get("story_key"),
        "outcome": "failed" if reason is not None else settled.get("outcome"),
        "reason": reason if reason is not None else settled.get("reason"),
        "refs": {**base_refs, **hook_keys},
    }
