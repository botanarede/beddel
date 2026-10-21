"""Pure derivation of Affected points and Required evidence (FR-1, AD-9, AD-13).

No I/O here. The inputs are the InventorySnapshot mapping and the footprint of
a Change; nothing else enters the derivation. The result is the complete set
of Required evidence of the Change: the derivation never filters, narrows or
judges an obligation, and a determination of non-applicability is not an input.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

__all__ = ["affected_points", "required_evidence", "touches", "unrecorded_touched"]

COMPONENT = "component"
SHARED_CONTRACT = "shared_contract"


def touches(footprint_path: str, component_path: str) -> bool:
    """True if the paths are equal or one is an ancestor of the other.

    Compared by whole ``/`` segments, so ``src/ab`` does not touch ``src/a``.
    """
    a = footprint_path.split("/")
    b = component_path.split("/")
    n = min(len(a), len(b))
    return a[:n] == b[:n]


def _presence(snapshot: Mapping[str, Any]) -> dict[str, bool | None]:
    """``target_present`` of each component, as the snapshot records it.

    The snapshot records it on obligations only; a component without any
    obligation has no recorded value (None).
    """
    present: dict[str, bool | None] = {c["id"]: None for c in snapshot["components"]}
    for obligation in snapshot["obligations"]:
        present[obligation["affected_point"]] = obligation["target_present"]
    return present


def affected_points(
    snapshot: Mapping[str, Any],
    footprint: Iterable[str],
    presence_of_unrecorded: Mapping[str, bool] | None = None,
) -> list[dict[str, Any]]:
    """Components (any kind) touched by the footprint, sorted by id.

    ``presence_of_unrecorded`` supplies ``target_present`` for a touched
    component that carries no obligation in the snapshot (resolved by the
    caller at the same Analyzed revision).
    """
    paths = list(footprint)
    recorded = _presence(snapshot)
    fallback = presence_of_unrecorded or {}
    points: list[dict[str, Any]] = []
    for component in snapshot["components"]:
        if component["kind"] not in (COMPONENT, SHARED_CONTRACT):
            continue
        if not any(touches(p, component["path"]) for p in paths):
            continue
        value = recorded[component["id"]]
        if value is None:
            value = fallback.get(component["id"], False)
        points.append(
            {
                "id": component["id"],
                "kind": component["kind"],
                "path": component["path"],
                "target_present": value,
            }
        )
    return sorted(points, key=lambda p: p["id"])


def unrecorded_touched(
    snapshot: Mapping[str, Any], footprint: Iterable[str]
) -> list[dict[str, Any]]:
    """Touched components whose presence the snapshot does not record."""
    recorded = _presence(snapshot)
    paths = list(footprint)
    return [
        c
        for c in snapshot["components"]
        if recorded[c["id"]] is None and any(touches(p, c["path"]) for p in paths)
    ]


def required_evidence(
    snapshot: Mapping[str, Any], points: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """The complete derived set of obligations that apply to the Change (AC 4).

    An obligation is Required evidence iff its Affected point is (a) an Active
    product component present at the Analyzed revision, touched or not, or
    (b) an Affected point of the Change, whatever its kind and presence.
    """
    kind_of = {c["id"]: c["kind"] for c in snapshot["components"]}
    class_kind = {c["id"]: c["kind"] for c in snapshot["classes"]}
    touched = {p["id"] for p in points}
    derived: list[dict[str, Any]] = []
    for obligation in snapshot["obligations"]:
        point = obligation["affected_point"]
        basis: list[str] = []
        if kind_of[point] == COMPONENT and obligation["target_present"] is True:
            basis.append("active_component")
        if point in touched:
            basis.append("affected_point")
        if not basis:
            continue
        derived.append(
            {
                "class": obligation["class"],
                "affected_point": point,
                "criterion": obligation["criterion"],
                "kind": class_kind[obligation["class"]],
                "target_present": obligation["target_present"],
                "basis": sorted(basis),
            }
        )
    return sorted(
        derived, key=lambda o: (o["class"], o["affected_point"], o["criterion"])
    )
