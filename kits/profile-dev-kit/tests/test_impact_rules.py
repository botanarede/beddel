"""AC3, AC4: pure derivation of Affected points and the complete Required evidence."""

from __future__ import annotations

from typing import Any

import pytest
from beddel_profile_dev.impact import (
    affected_points,
    required_evidence,
    touches,
    unrecorded_touched,
)


def _snapshot() -> dict[str, Any]:
    def ob(point: str, present: bool, cls: str = "gate", crit: str = "ok") -> dict:
        return {
            "class": cls,
            "affected_point": point,
            "criterion": crit,
            "target_present": present,
        }

    return {
        "classes": [{"id": "gate", "kind": "gate"}, {"id": "rev", "kind": "review"}],
        "components": [
            {"id": "present", "kind": "component", "path": "src/present.py"},
            {"id": "absent", "kind": "component", "path": "src/absent.py"},
            {"id": "shared", "kind": "shared_contract", "path": "src/shared.yaml"},
            {"id": "gone", "kind": "component", "path": "src/gone.py"},
            {"id": "shared-hit", "kind": "shared_contract", "path": "docs/c.yaml"},
            {"id": "bare", "kind": "component", "path": "lib/bare"},
        ],
        "obligations": [
            ob("present", True),
            ob("present", True, "rev"),
            ob("absent", False),
            ob("shared", True),
            ob("gone", False),
            ob("shared-hit", True),
        ],
    }


def _evidence(footprint: list[str]) -> list[tuple[str, str, str, list[str]]]:
    snap = _snapshot()
    points = affected_points(snap, footprint)
    return [
        (o["class"], o["affected_point"], o["criterion"], o["basis"])
        for o in required_evidence(snap, points)
    ]


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("src/a.py", "src/a.py", True),
        ("src/a/b.py", "src/a", True),
        ("src", "src/a.py", True),
        ("src/ab", "src/a", False),
        ("src/a.py", "src/a", False),
        ("other", "src", False),
    ],
)
def test_touch_rule_compares_whole_segments(a: str, b: str, expected: bool) -> None:
    assert touches(a, b) is expected


def test_empty_footprint_touches_nothing_and_keeps_active_components() -> None:
    assert affected_points(_snapshot(), []) == []
    assert _evidence([]) == [
        ("gate", "present", "ok", ["active_component"]),
        ("rev", "present", "ok", ["active_component"]),
    ]


def test_untouched_present_component_in_absent_component_and_shared_out() -> None:
    got = _evidence(["unrelated/file"])
    ids = {(c, p) for c, p, _, _ in got}
    assert ("gate", "present") in ids
    assert ("gate", "absent") not in ids
    assert ("gate", "shared") not in ids
    assert ("gate", "gone") not in ids


def test_touched_absent_component_and_touched_shared_contract_are_in() -> None:
    got = _evidence(["src/gone.py", "docs/c.yaml"])
    by_point = {p: basis for _, p, _, basis in got}
    assert by_point["gone"] == ["affected_point"]
    assert by_point["shared-hit"] == ["affected_point"]
    assert by_point["present"] == ["active_component"]


def test_touched_present_component_has_both_bases_sorted() -> None:
    got = _evidence(["src/present.py"])
    assert ("gate", "present", "ok", ["active_component", "affected_point"]) in got


def test_set_is_sorted_and_carries_kind_and_presence() -> None:
    snap = _snapshot()
    points = affected_points(snap, ["src/gone.py"])
    derived = required_evidence(snap, points)
    keys = [(o["class"], o["affected_point"], o["criterion"]) for o in derived]
    assert keys == sorted(keys)
    gone = next(o for o in derived if o["affected_point"] == "gone")
    assert gone["target_present"] is False and gone["kind"] == "gate"


def test_affected_points_sorted_with_snapshot_presence() -> None:
    points = affected_points(_snapshot(), ["src/shared.yaml", "src/absent.py"])
    assert [p["id"] for p in points] == ["absent", "shared"]
    assert points[0]["target_present"] is False
    assert points[1]["target_present"] is True


def test_component_without_obligation_gets_the_fallback_presence() -> None:
    snap = _snapshot()
    assert [c["id"] for c in unrecorded_touched(snap, ["lib/bare/x.py"])] == ["bare"]
    points = affected_points(snap, ["lib/bare/x.py"], {"bare": True})
    assert points == [
        {"id": "bare", "kind": "component", "path": "lib/bare", "target_present": True}
    ]


def test_derivation_never_returns_a_subset_of_obligations_of_a_touched_point() -> None:
    got = _evidence(["src/present.py"])
    assert {(c, p, k) for c, p, k, _ in got} >= {
        ("gate", "present", "ok"),
        ("rev", "present", "ok"),
    }
