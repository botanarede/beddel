"""Impact of a Change at its Analyzed revision (FR-1, AD-9, AD-12, AD-13, AD-17).

Derives the footprint, the Affected points and the complete set of Required
evidence from the ratified InventorySnapshot bound to the revision, and from
nothing else. The impact record is create-only and deterministic: a stored
record that differs from the re-derived one is a defect, never a variant.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import (
    PROFILE_CHANGE_INVALID,
    PROFILE_IMPACT_CONFLICT,
    PROFILE_IMPACT_UNBOUND,
    ProfileError,
)
from beddel_profile_dev._io import (
    canonical_json,
    confined,
    footprint,
    is_ancestor,
    path_present,
    read_confined,
    real_repo_root,
    resolve_revision,
    write_create_only,
)
from beddel_profile_dev.config import load_config
from beddel_profile_dev.impact import (
    affected_points,
    required_evidence,
    unrecorded_touched,
)
from beddel_profile_dev.inventory import is_valid_id
from beddel_profile_dev.tools.bind import BINDING_SCHEMA, BLOCK_SCHEMA, SNAPSHOT_SCHEMA
from beddel_profile_dev.tools.change import CHANGE_REVISION_SCHEMA, CHANGE_SCHEMA

__all__ = ["profile_derive_impact"]

IMPACT_SCHEMA = "profile-dev/impact/1"
DISCHARGE_BY_REVISION_SCHEMA = "profile-dev/integrity-discharge-by-revision/1"


def _unbound() -> ProfileError:
    return ProfileError(
        PROFILE_IMPACT_UNBOUND,
        "impact needs a recorded Change, its revision link and the binding of the revision",
    )


def _conflict() -> ProfileError:
    return ProfileError(
        PROFILE_IMPACT_CONFLICT,
        "a stored impact record differs from the re-derived one",
    )


def _load(root: Path, relative: str) -> dict[str, Any]:
    raw = read_confined(root, relative)
    try:
        data = json.loads(raw) if raw is not None else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise _unbound()
    return data


def _is_list_of_dicts(value: object, keys: frozenset[str]) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, dict) and keys <= set(item) for item in value
    )


def _snapshot_shape_ok(snapshot: dict[str, Any]) -> bool:
    ok = _is_list_of_dicts(snapshot.get("classes"), frozenset({"id", "kind"}))
    ok = ok and _is_list_of_dicts(
        snapshot.get("components"), frozenset({"id", "kind", "path"})
    )
    ok = ok and _is_list_of_dicts(
        snapshot.get("obligations"),
        frozenset({"class", "affected_point", "criterion", "target_present"}),
    )
    if not ok:
        return False
    version = snapshot.get("inventory_version")
    digest = snapshot.get("inventory_sha256")
    if not (isinstance(version, str) and is_valid_id(version)):
        return False
    if not (isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)):
        return False
    if any(
        not isinstance(c["id"], str) or not isinstance(c["kind"], str)
        for c in snapshot["classes"]
    ) or any(
        not isinstance(c["id"], str)
        or not isinstance(c["kind"], str)
        or not isinstance(c["path"], str)
        for c in snapshot["components"]
    ):
        return False
    component_ids = {c["id"] for c in snapshot["components"]}
    class_ids = {c["id"] for c in snapshot["classes"]}
    return all(
        all(isinstance(o[k], str) for k in ("class", "affected_point", "criterion"))
        and o["affected_point"] in component_ids
        and o["class"] in class_ids
        and isinstance(o["target_present"], bool)
        for o in snapshot["obligations"]
    )


def _bound_snapshot(root: Path, records: str, sha: str) -> dict[str, Any]:
    base = f"{records}/revisions/{sha}"
    binding = _load(root, f"{base}/binding.json")
    snapshot = _load(root, f"{base}/snapshot.json")
    if (
        binding.get("schema") != BINDING_SCHEMA
        or binding.get("snapshot") != f"{base}/snapshot.json"
        or snapshot.get("schema") != SNAPSHOT_SCHEMA
        or binding.get("revision") != sha
        or snapshot.get("revision") != sha
        or binding.get("inventory_version") != snapshot.get("inventory_version")
        or binding.get("inventory_sha256") != snapshot.get("inventory_sha256")
        or not _snapshot_shape_ok(snapshot)
    ):
        raise _unbound()
    return snapshot


def _linked_change(root: Path, records: str, change_id: str, sha: str) -> str:
    """Validate the Change record and the revision link; return the base SHA."""
    change = _load(root, f"{records}/changes/{change_id}/change.json")
    link = _load(root, f"{records}/changes/{change_id}/revisions/{sha}/revision.json")
    base = change.get("base")
    if (
        change.get("schema") != CHANGE_SCHEMA
        or change.get("change_id") != change_id
        or not isinstance(base, str)
        or link.get("schema") != CHANGE_REVISION_SCHEMA
        or link.get("change_id") != change_id
        or link.get("base") != base
        or link.get("revision") != sha
    ):
        raise _unbound()
    try:
        resolved = resolve_revision(root, base)
    except ProfileError:
        raise _unbound() from None
    if resolved != base or not is_ancestor(root, base, sha):
        raise _unbound()
    return base


def _discharge_blocks_of_other_revisions(
    root: Path,
    records: str,
    change_id: str,
    sha: str,
    version: str,
    digest: str,
) -> None:
    """AD-12: a new Analyzed revision of the Change discharges earlier blocks, once."""
    revisions = confined(root, f"{records}/changes/{change_id}/revisions")
    if not revisions.is_dir():
        return
    for other in sorted(p.name for p in revisions.iterdir()):
        if other == sha:
            continue
        try:
            link = _load(
                root, f"{records}/changes/{change_id}/revisions/{other}/revision.json"
            )
        except ProfileError:
            continue  # not a well-formed link: not linked to this Change
        if (
            link.get("schema") != CHANGE_REVISION_SCHEMA
            or link.get("change_id") != change_id
            or link.get("revision") != other
        ):
            continue
        blocks = f"{records}/revisions/{other}/integrity-blocks"
        directory = confined(root, blocks)
        if not directory.is_dir():
            continue
        for entry in sorted(p.name for p in directory.iterdir()):
            if not entry.endswith(".json") or entry.endswith(".discharged.json"):
                continue
            name = entry[: -len(".json")] + ".discharged.json"
            discharged = confined(root, f"{blocks}/{name}")
            if discharged.is_symlink() or discharged.exists():
                continue  # a block is discharged once, by either kind
            raw = read_confined(root, f"{blocks}/{entry}")
            try:
                block = json.loads(raw) if raw is not None else None
            except ValueError:
                continue
            if (
                not isinstance(block, dict)
                or block.get("schema") != BLOCK_SCHEMA
                or block.get("revision") != other
            ):
                continue
            discharge = {
                "schema": DISCHARGE_BY_REVISION_SCHEMA,
                "revision": other,
                "block": entry,
                "change_id": change_id,
                "resolved_by_revision": sha,
                "resolved_by_version": version,
                "resolved_by_sha256": digest,
            }
            write_create_only(root, f"{blocks}/{name}", canonical_json(discharge))


@beddel_tool(
    name="profile_derive_impact",
    description="Derive the footprint, Affected points and Required evidence of a Change",
    category="profile",
)
def profile_derive_impact(
    repo_path: str, change_id: str, revision: str
) -> dict[str, Any]:
    """Derive and record the impact of a Change at its Analyzed revision.

    Raises:
        ProfileError: ``PROFILE_IMPACT_UNBOUND``, ``PROFILE_IMPACT_CONFLICT``,
            ``PROFILE_CHANGE_INVALID`` or ``PROFILE_REPOSITORY_INVALID``.
    """
    config = load_config()
    records = config.records_dir
    if not is_valid_id(change_id):
        raise ProfileError(PROFILE_CHANGE_INVALID, "change id invalid")
    root = real_repo_root(repo_path)
    sha = resolve_revision(root, revision)

    base = _linked_change(root, records, change_id, sha)
    snapshot = _bound_snapshot(root, records, sha)

    paths = footprint(root, base, sha)
    fallback = {
        c["id"]: path_present(root, sha, c["path"])
        for c in unrecorded_touched(snapshot, paths)
    }
    points = affected_points(snapshot, paths, fallback)
    evidence = required_evidence(snapshot, points)
    impact = {
        "schema": IMPACT_SCHEMA,
        "change_id": change_id,
        "base": base,
        "revision": sha,
        "inventory_version": snapshot["inventory_version"],
        "inventory_sha256": snapshot["inventory_sha256"],
        "footprint": paths,
        "affected_points": points,
        "required_evidence": evidence,
    }
    impact_rel = f"{records}/changes/{change_id}/revisions/{sha}/impact.json"
    data = canonical_json(impact)
    if not write_create_only(root, impact_rel, data) and (
        read_confined(root, impact_rel) != data
    ):
        raise _conflict()

    _discharge_blocks_of_other_revisions(
        root,
        records,
        change_id,
        sha,
        snapshot["inventory_version"],
        snapshot["inventory_sha256"],
    )
    return {
        "ok": True,
        "change_id": change_id,
        "revision": sha,
        "impact": impact_rel,
        "affected_points": len(points),
        "required_evidence": len(evidence),
        "targets_absent": sum(1 for o in evidence if not o["target_present"]),
    }
