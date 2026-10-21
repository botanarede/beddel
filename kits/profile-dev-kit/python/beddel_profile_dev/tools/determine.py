"""Determination of non-applicability: a recorded human act (AD-13).

The tool is transport for the maintainer's act: it never derives the actor from
the environment or the Git configuration, and nothing in the runtime writes a
determination on its own. A determination is scoped to one Analyzed revision
and one obligation whose declared target is absent; it changes no other record.
Refusals use a fixed message with a reason code and write nothing.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import yaml
from beddel.tools import beddel_tool

from beddel_profile_dev._errors import PROFILE_DETERMINATION_REFUSED, ProfileError
from beddel_profile_dev._io import (
    blob_at,
    canonical_json,
    confined,
    path_present,
    read_confined,
    real_repo_root,
    resolve_revision,
    write_create_only,
)
from beddel_profile_dev.config import load_config
from beddel_profile_dev.inventory import is_valid_id, validate_inventory
from beddel_profile_dev.tools.bind import BINDING_SCHEMA, _record_is_valid
from beddel_profile_dev.tools.ratify import TIMESTAMP_FORMAT, valid_actor

__all__ = ["profile_declare_non_applicability"]

NON_APPLICABILITY_SCHEMA = "profile-dev/non-applicability/1"


def _refuse(reason: str) -> ProfileError:
    return ProfileError(
        PROFILE_DETERMINATION_REFUSED,
        f"determination of non-applicability refused: {reason}",
        {"reason": reason},
    )


@beddel_tool(
    name="profile_declare_non_applicability",
    description="Record the maintainer's determination that an obligation with an absent target is not applicable (transport only)",
    category="profile",
)
def profile_declare_non_applicability(
    repo_path: str,
    revision: str,
    class_id: str,
    affected_point_id: str,
    criterion_id: str,
    actor: str,
) -> dict[str, Any]:
    """Write the determination record of one obligation at one revision, create-only.

    Raises:
        ProfileError: ``PROFILE_DETERMINATION_REFUSED`` with a fixed message
            and a reason code; nothing is written on refusal.
    """
    config = load_config()
    if not (
        is_valid_id(class_id)
        and is_valid_id(affected_point_id)
        and is_valid_id(criterion_id)
    ):
        raise _refuse("id.invalid")
    if not valid_actor(actor):
        raise _refuse("actor.invalid")
    root = real_repo_root(repo_path)
    sha = resolve_revision(root, revision)

    base = f"{config.records_dir}/revisions/{sha}"
    raw = read_confined(root, f"{base}/binding.json")
    try:
        binding = json.loads(raw) if raw is not None else None
    except ValueError:
        binding = None
    if (
        not isinstance(binding, dict)
        or binding.get("schema") != BINDING_SCHEMA
        or binding.get("revision") != sha
        or not is_valid_id(binding.get("inventory_version"))
        or not isinstance(binding.get("inventory_sha256"), str)
    ):
        raise _refuse("binding.absent")
    version = binding["inventory_version"]

    # Trust nothing local: re-check the bound version and its ratification
    # record in the tree of the Analyzed revision against the binding digest.
    version_blob = blob_at(root, sha, f"{config.inventory_dir}/{version}.yaml")
    record_blob = blob_at(
        root, sha, f"{config.inventory_dir}/{version}.ratification.yaml"
    )
    if version_blob is None or record_blob is None:
        raise _refuse("version.unratified")
    digest = hashlib.sha256(version_blob).hexdigest()
    if digest != binding["inventory_sha256"] or not _record_is_valid(
        record_blob, version, digest
    ):
        raise _refuse("version.unratified")
    record = yaml.safe_load(record_blob)
    if actor != record["ratified_by"]:
        raise _refuse("actor.not_ratifier")

    try:
        parsed = yaml.safe_load(version_blob)
    except (yaml.YAMLError, RecursionError):
        raise _refuse("version.unratified") from None
    inventory, _ = validate_inventory(parsed, version)
    if inventory is None:
        raise _refuse("version.unratified")
    wanted = (class_id, affected_point_id, criterion_id)
    if not any(
        (o.class_id, o.affected_point_id, o.criterion_id) == wanted
        for o in inventory.obligations
    ):
        raise _refuse("obligation.unknown")
    path = next(c.path for c in inventory.components if c.id == affected_point_id)
    if path_present(root, sha, path):
        raise _refuse("target.present")

    record_rel = (
        f"{base}/non-applicability/{class_id}+{affected_point_id}+{criterion_id}.json"
    )
    existing = confined(root, record_rel)
    if existing.exists() or existing.is_symlink():
        raise _refuse("determination.exists")

    determination = {
        "schema": NON_APPLICABILITY_SCHEMA,
        "revision": sha,
        "inventory_version": version,
        "inventory_sha256": digest,
        "class": class_id,
        "affected_point": affected_point_id,
        "criterion": criterion_id,
        "determined_by": actor,
        "determined_at": datetime.now(UTC).strftime(TIMESTAMP_FORMAT),
    }
    if not write_create_only(root, record_rel, canonical_json(determination)):
        raise _refuse("determination.exists")
    return {
        "ok": True,
        "revision": sha,
        "inventory_version": version,
        "determination": record_rel,
    }
