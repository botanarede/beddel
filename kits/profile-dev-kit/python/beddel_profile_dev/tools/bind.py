"""Pre-binding validation and binding of a ratified inventory version (AD-9, AD-11, AD-12).

The version file and its ratification record are read from the tree of the
Analyzed revision, never from the work tree. Records written here live under
``<records_dir>/revisions/<sha>/`` in the work tree and are create-only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from beddel.tools import beddel_tool

from beddel_profile_dev._errors import (
    PROFILE_INVENTORY_BINDING_CONFLICT,
    PROFILE_INVENTORY_INTEGRITY_BLOCK,
    PROFILE_INVENTORY_UNRATIFIED,
    ProfileError,
)
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
from beddel_profile_dev.inventory import (
    Failure,
    Inventory,
    is_valid_id,
    validate_inventory,
)
from beddel_profile_dev.tools.ratify import (
    RATIFICATION_SCHEMA,
    TIMESTAMP_FORMAT,
    valid_actor,
)

__all__ = ["profile_bind_inventory"]

BLOCK_SCHEMA = "profile-dev/integrity-block/1"
DISCHARGE_SCHEMA = "profile-dev/integrity-discharge/1"
BINDING_SCHEMA = "profile-dev/binding/1"
SNAPSHOT_SCHEMA = "profile-dev/inventory-snapshot/1"

_RECORD_KEYS = frozenset(
    {"schema", "inventory_version", "inventory_sha256", "ratified_by", "ratified_at"}
)


def _unratified() -> ProfileError:
    return ProfileError(
        PROFILE_INVENTORY_UNRATIFIED,
        "no ratified inventory version at the analyzed revision",
    )


def _conflict() -> ProfileError:
    return ProfileError(
        PROFILE_INVENTORY_BINDING_CONFLICT,
        "the revision is already bound to a different inventory version or snapshot",
    )


def _blocked(codes: list[str], block: str) -> ProfileError:
    return ProfileError(
        PROFILE_INVENTORY_INTEGRITY_BLOCK,
        "inventory integrity block: " + ", ".join(codes),
        {"codes": codes, "block": block},
    )


def _recorded_codes(raw: bytes | None) -> list[str]:
    """Reason codes of a stored block (no re-validation); fallback if unreadable."""
    try:
        block = json.loads(raw) if raw is not None else {}
        codes = {f["code"] for f in block["failures"]}
    except (ValueError, KeyError, TypeError):
        return ["block.recorded"]
    return sorted(c for c in codes if isinstance(c, str)) or ["block.recorded"]


def _record_is_valid(blob: bytes, version: str, digest: str) -> bool:
    try:
        record = yaml.safe_load(blob)
    except (yaml.YAMLError, RecursionError):
        return False
    if not isinstance(record, dict) or set(record) != _RECORD_KEYS:
        return False
    return (
        record["schema"] == RATIFICATION_SCHEMA
        and record["inventory_version"] == version
        and record["inventory_sha256"] == digest
        and valid_actor(record["ratified_by"])
        and _valid_timestamp(record["ratified_at"])
    )


def _valid_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, TIMESTAMP_FORMAT)
    except ValueError:
        return False
    return True


def _write_or_match(root: Path, relative: str, data: bytes) -> None:
    """Create-only write; if present, the stored bytes must be identical."""
    if write_create_only(root, relative, data):
        return
    if read_confined(root, relative) != data:
        raise _conflict()


def _snapshot(
    inventory: Inventory,
    revision: str,
    digest: str,
    present: dict[str, bool],
) -> dict[str, Any]:
    path_of = {c.id: c.path for c in inventory.components}
    obligations = sorted(
        (o.class_id, o.affected_point_id, o.criterion_id) for o in inventory.obligations
    )
    return {
        "schema": SNAPSHOT_SCHEMA,
        "revision": revision,
        "inventory_version": inventory.version,
        "inventory_sha256": digest,
        "classes": [{"id": i, "kind": k} for i, k in sorted(inventory.classes)],
        "components": [
            {"id": c.id, "kind": c.kind, "path": c.path}
            for c in sorted(inventory.components, key=lambda c: c.id)
        ],
        "criteria": [
            {"id": i, "description": d} for i, d in sorted(inventory.criteria)
        ],
        "obligations": [
            {
                "class": c,
                "affected_point": a,
                "criterion": k,
                "target_present": present[path_of[a]],
            }
            for c, a, k in obligations
        ],
    }


def _discharge_other_blocks(
    root: Path, base: str, revision: str, version: str, digest: str
) -> None:
    directory = confined(root, f"{base}/integrity-blocks")
    if not directory.is_dir():
        return
    for entry in sorted(p.name for p in directory.iterdir()):
        if not entry.endswith(".json") or entry.endswith(".discharged.json"):
            continue
        raw = read_confined(root, f"{base}/integrity-blocks/{entry}")
        try:
            block = json.loads(raw) if raw is not None else None
        except ValueError:
            continue
        if (
            not isinstance(block, dict)
            or block.get("schema") != BLOCK_SCHEMA
            or block.get("revision") != revision
            or block.get("inventory_version") == version
        ):
            continue
        discharge = {
            "schema": DISCHARGE_SCHEMA,
            "revision": revision,
            "block": entry,
            "resolved_by_version": version,
            "resolved_by_sha256": digest,
        }
        name = entry[: -len(".json")] + ".discharged.json"
        _write_or_match(
            root, f"{base}/integrity-blocks/{name}", canonical_json(discharge)
        )


@beddel_tool(
    name="profile_bind_inventory",
    description="Validate a ratified inventory version at a revision and bind its snapshot",
    category="profile",
)
def profile_bind_inventory(
    repo_path: str, revision: str, inventory_version: str
) -> dict[str, Any]:
    """Bind exactly one ratified inventory version to an Analyzed revision.

    Raises:
        ProfileError: ``PROFILE_INVENTORY_UNRATIFIED``,
            ``PROFILE_INVENTORY_INTEGRITY_BLOCK``,
            ``PROFILE_INVENTORY_BINDING_CONFLICT`` or
            ``PROFILE_REPOSITORY_INVALID``.
    """
    config = load_config()
    root = real_repo_root(repo_path)
    sha = resolve_revision(root, revision)
    if not is_valid_id(inventory_version):
        raise _unratified()

    version_blob = blob_at(
        root, sha, f"{config.inventory_dir}/{inventory_version}.yaml"
    )
    record_blob = blob_at(
        root, sha, f"{config.inventory_dir}/{inventory_version}.ratification.yaml"
    )
    if version_blob is None or record_blob is None:
        raise _unratified()
    digest = hashlib.sha256(version_blob).hexdigest()
    if not _record_is_valid(record_blob, inventory_version, digest):
        raise _unratified()

    base = f"{config.records_dir}/revisions/{sha}"
    binding_rel = f"{base}/binding.json"
    snapshot_rel = f"{base}/snapshot.json"

    existing = read_confined(root, binding_rel)
    if existing is not None:
        try:
            stored = json.loads(existing)
        except ValueError:
            raise _conflict() from None
        if (
            not isinstance(stored, dict)
            or stored.get("inventory_version") != inventory_version
        ):
            raise _conflict()

    block_rel = f"{base}/integrity-blocks/{inventory_version}-{digest[:12]}.json"
    if read_confined(root, block_rel) is not None:
        raise _blocked(_recorded_codes(read_confined(root, block_rel)), block_rel)

    failures: list[Failure]
    inventory: Inventory | None
    try:
        parsed = yaml.safe_load(version_blob)
    except (yaml.YAMLError, RecursionError):
        inventory, failures = None, [Failure("$", "yaml.invalid")]
    else:
        inventory, failures = validate_inventory(parsed, inventory_version)
    if inventory is None:
        block = {
            "schema": BLOCK_SCHEMA,
            "revision": sha,
            "inventory_version": inventory_version,
            "inventory_sha256": digest,
            "failures": [{"locator": f.locator, "code": f.code} for f in failures],
        }
        _write_or_match(root, block_rel, canonical_json(block))
        raise _blocked(sorted({f.code for f in failures}), block_rel)

    present = {c.path: path_present(root, sha, c.path) for c in inventory.components}
    snapshot = _snapshot(inventory, sha, digest, present)
    binding = {
        "schema": BINDING_SCHEMA,
        "revision": sha,
        "inventory_version": inventory_version,
        "inventory_sha256": digest,
        "snapshot": snapshot_rel,
    }
    _write_or_match(root, snapshot_rel, canonical_json(snapshot))
    _write_or_match(root, binding_rel, canonical_json(binding))
    _discharge_other_blocks(root, base, sha, inventory_version, digest)

    return {
        "ok": True,
        "revision": sha,
        "inventory_version": inventory_version,
        "inventory_sha256": digest,
        "snapshot": snapshot_rel,
        "obligations": len(snapshot["obligations"]),
        "targets_absent": sum(
            1 for o in snapshot["obligations"] if not o["target_present"]
        ),
    }
