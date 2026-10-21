"""Ratification transport (AD-11): the tool records a human act, it never constitutes one.

The actor is the ``actor`` input, never derived from the environment or the
Git configuration. Refusals use a fixed message with a reason code and write
nothing.
"""

from __future__ import annotations

import hashlib
import unicodedata
from datetime import UTC, datetime
from typing import Any

import yaml
from beddel.tools import beddel_tool

from beddel_profile_dev._errors import PROFILE_RATIFICATION_REFUSED, ProfileError
from beddel_profile_dev._io import (
    confined,
    in_head_history,
    in_index,
    read_confined,
    real_repo_root,
    write_create_only,
)
from beddel_profile_dev.config import load_config
from beddel_profile_dev.inventory import is_valid_id

__all__ = ["profile_ratify_inventory", "valid_actor"]

_ACTOR_MAX = 200
RATIFICATION_SCHEMA = "profile-dev/ratification/1"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _refuse(reason: str) -> ProfileError:
    return ProfileError(
        PROFILE_RATIFICATION_REFUSED,
        f"inventory ratification refused: {reason}",
        {"reason": reason},
    )


def valid_actor(actor: object) -> bool:
    return (
        isinstance(actor, str)
        and bool(actor.strip())
        and len(actor) <= _ACTOR_MAX
        and not any(unicodedata.category(c) == "Cc" for c in actor)
    )


@beddel_tool(
    name="profile_ratify_inventory",
    description="Record the maintainer's ratification of an inventory version (transport only)",
    category="profile",
)
def profile_ratify_inventory(
    repo_path: str, inventory_version: str, actor: str
) -> dict[str, Any]:
    """Write the ratification record of an inventory version, create-only.

    Raises:
        ProfileError: ``PROFILE_RATIFICATION_REFUSED`` with a fixed message;
            nothing is written on refusal.
    """
    config = load_config()
    if not is_valid_id(inventory_version):
        raise _refuse("id.invalid")
    if not valid_actor(actor):
        raise _refuse("actor.invalid")
    root = real_repo_root(repo_path)

    version_rel = f"{config.inventory_dir}/{inventory_version}.yaml"
    record_rel = f"{config.inventory_dir}/{inventory_version}.ratification.yaml"
    blob = read_confined(root, version_rel)
    if blob is None:
        raise _refuse("inventory.absent")
    try:
        data = yaml.safe_load(blob)
    except (yaml.YAMLError, RecursionError):
        raise _refuse("inventory.not_mapping") from None
    if not isinstance(data, dict):
        raise _refuse("inventory.not_mapping")
    if data.get("version") != inventory_version:
        raise _refuse("version.mismatch")

    record_path = confined(root, record_rel)
    if record_path.exists() or record_path.is_symlink():
        raise _refuse("record.exists")
    try:
        in_history = in_index(root, record_rel) or in_head_history(root, record_rel)
    except ProfileError:
        raise _refuse("history.unreadable") from None
    if in_history:
        raise _refuse("record.exists")
    digest = hashlib.sha256(blob).hexdigest()
    record = {
        "schema": RATIFICATION_SCHEMA,
        "inventory_version": inventory_version,
        "inventory_sha256": digest,
        "ratified_by": actor,
        "ratified_at": datetime.now(UTC).strftime(TIMESTAMP_FORMAT),
    }
    text = yaml.safe_dump(record, sort_keys=False, allow_unicode=True)
    if not write_create_only(root, record_rel, text.encode("utf-8")):
        raise _refuse("record.exists")
    return {
        "ok": True,
        "inventory_version": inventory_version,
        "inventory_sha256": digest,
        "record": record_rel,
    }
