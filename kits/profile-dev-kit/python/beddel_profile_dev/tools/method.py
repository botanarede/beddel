"""Tools for reading and applying profile delivery methods."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import PROFILE_CONFIG_INVALID, ProfileError
from beddel_profile_dev._io import blob_at, real_repo_root
from beddel_profile_dev.method import (
    METHOD_FILE,
    METHOD_NAME,
    load_method,
    valid_instruction,
)

__all__ = ["profile_deliver_method", "profile_stage_instruction"]


def _config_error(reason: str) -> ProfileError:
    return ProfileError(PROFILE_CONFIG_INVALID, "method invalid", {"reason": reason})


@beddel_tool(
    name="profile_deliver_method",
    description="Read one committed delivery method and expose its neutral stage instructions",
    category="profile",
)
def profile_deliver_method(repo_path: str, method: str) -> dict[str, Any]:
    repo = real_repo_root(repo_path)
    if method in ("", "native"):
        return {
            "method": "native",
            "method_sha256": None,
            "plan": "",
            "implement": "",
            "fix": "",
        }
    if not isinstance(method, str) or METHOD_NAME.fullmatch(method) is None:
        raise _config_error("method.invalid")
    raw = blob_at(repo, "HEAD", METHOD_FILE)
    data = load_method(raw) if raw is not None else None
    if data is None:
        raise _config_error("method.invalid" if raw is not None else "method.absent")
    selected = data["methods"].get(method)
    if not isinstance(selected, Mapping):
        raise _config_error("method.unknown")
    return {
        "method": method,
        "method_sha256": hashlib.sha256(raw or b"").hexdigest(),
        "plan": selected["plan"],
        "implement": selected["implement"],
        "fix": selected["fix"],
    }


@beddel_tool(
    name="profile_stage_instruction",
    description="Validate a neutral instruction before it reaches a Coding agent",
    category="profile",
)
def profile_stage_instruction(stage: str, instruction: str) -> dict[str, Any]:
    if stage not in {"plan", "implement", "verify-and-fix"}:
        raise _config_error("stage.invalid")
    if not valid_instruction(instruction):
        raise _config_error("instruction.invalid")
    return {
        "stage": stage,
        "instruction": instruction,
        "instruction_sha256": hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
    }
