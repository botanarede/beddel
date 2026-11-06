"""Pure Story 4.4 selection and linking tests."""

from __future__ import annotations

from typing import Any

from beddel_profile_dev.reverification import link_findings, select_earlier_findings

A = "a" * 40
B = "b" * 40
C = "c" * 40
REQUIREMENT = {
    "class": "gate-unit",
    "affected_point": "api",
    "criterion": "tests-pass",
    "kind": "gate",
}


def report(
    ordinal: int, revision: str, findings: list[Any]
) -> tuple[int, dict[str, Any]]:
    return (
        ordinal,
        {
            "change_id": "c1",
            "revision": revision,
            "items": {"divergences": {"status": "present", "value": findings}},
        },
    )


def finding(**values: Any) -> dict[str, Any]:
    return {
        "association": "requirement",
        **REQUIREMENT,
        "source": "gate",
        **values,
    }


def assessment(state: str) -> dict[str, Any]:
    return {**REQUIREMENT, "state": state}


def test_selects_findings_from_the_latest_earlier_revision_in_history_order() -> None:
    first = finding(source="first")
    second = finding(source="second")
    selected, entries = select_earlier_findings(
        [
            report(1, A, [first]),
            report(2, B, [second]),
            report(3, B, [finding(source="third")]),
        ],
        C,
        "c1",
    )
    assert selected == B
    assert [entry[:2] for entry in entries] == [
        ("changes/c1/report/2.json", 0),
        ("changes/c1/report/3.json", 0),
    ]
    assert [entry[2]["source"] for entry in entries] == ["second", "third"]


def test_selection_ignores_same_revision_clean_history_and_reruns() -> None:
    selected, entries = select_earlier_findings(
        [
            report(1, A, []),
            (2, {"revision": B, "items": {"divergences": {"status": "absent"}}}),
        ],
        B,
        "c1",
    )
    assert (selected, entries) == (None, [])


def test_links_resolved_findings_without_a_pendency() -> None:
    links = link_findings(
        [("changes/c1/report/1.json", 0, finding())],
        [REQUIREMENT],
        [assessment("no_divergence")],
        [],
    )
    assert links == [
        {
            "report_ref": "changes/c1/report/1.json",
            "finding_index": 0,
            "association": "requirement",
            **REQUIREMENT,
            "state": "no_divergence",
            "result": "resolved",
            "reason": None,
        }
    ]


def test_links_still_divergent_when_state_or_current_finding_is_divergent() -> None:
    earlier = [("changes/c1/report/1.json", 0, finding())]
    assert (
        link_findings(earlier, [REQUIREMENT], [assessment("divergent")], [])[0][
            "result"
        ]
        == "still_divergent"
    )
    assert (
        link_findings(
            earlier, [REQUIREMENT], [assessment("no_divergence")], [finding()]
        )[0]["result"]
        == "still_divergent"
    )


def test_links_indeterminate_assessments_as_not_reverified() -> None:
    link = link_findings(
        [("changes/c1/report/1.json", 0, finding())],
        [REQUIREMENT],
        [assessment("indeterminate")],
        [],
    )[0]
    assert (link["result"], link["reason"], link["state"]) == (
        "not_reverified",
        "indeterminate",
        "indeterminate",
    )


def test_links_outside_scope_and_unknown_associations() -> None:
    outside = link_findings(
        [("changes/c1/report/1.json", 0, finding())],
        [],
        [],
        [],
    )[0]
    unknown = link_findings(
        [("changes/c1/report/1.json", 1, {"association": "unknown"})],
        [REQUIREMENT],
        [assessment("no_divergence")],
        [],
    )[0]
    assert outside["result"] == unknown["result"] == "not_reverified"
    assert outside["reason"] == unknown["reason"] == "outside_scope"
    assert outside["state"] is None
    assert all(
        unknown[key] is None for key in ("class", "affected_point", "criterion", "kind")
    )


def test_selection_uses_all_findings_at_the_selected_revision() -> None:
    one = finding(source="one")
    two = finding(source="two")
    _, entries = select_earlier_findings(
        [report(1, A, [one]), report(2, A, [two])], B, "c1"
    )
    assert [entry[1] for entry in entries] == [0, 0]
    assert [entry[2]["source"] for entry in entries] == ["one", "two"]


def test_greatest_report_ordinal_selects_the_revision_and_all_its_findings() -> None:
    selected, entries = select_earlier_findings(
        [
            report(1, A, [finding(source="a1")]),
            report(2, B, [finding(source="b")]),
            report(3, A, [finding(source="a3")]),
        ],
        C,
        "c1",
    )
    assert selected == A
    assert [entry[0] for entry in entries] == [
        "changes/c1/report/1.json",
        "changes/c1/report/3.json",
    ]
    assert [entry[2]["source"] for entry in entries] == ["a1", "a3"]


def test_empty_selection_returns_not_applicable() -> None:
    selected, entries = select_earlier_findings(
        [
            report(1, A, []),
            report(2, B, []),
        ],
        C,
        "c1",
    )
    assert (selected, entries) == (None, [])
