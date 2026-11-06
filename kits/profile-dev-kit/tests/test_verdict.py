"""Pure Story 4.2 classification and Verdict derivation tests."""

from __future__ import annotations

from typing import Any

from beddel_profile_dev.verdict import classify_findings, derive_verdict

REQUIREMENTS = [
    {
        "class": "gate-unit",
        "affected_point": "api",
        "criterion": "tests-pass",
        "kind": "gate",
    },
    {
        "class": "review-arch",
        "affected_point": "api",
        "criterion": "arch-ok",
        "kind": "review",
    },
]
SNAPSHOT = {
    "criteria": [
        {"id": "tests-pass", "description": "Tests", "blocking": True},
        {"id": "arch-ok", "description": "Architecture", "blocking": False},
        {"id": "no-policy", "description": "No policy"},
    ]
}
EVIDENCE = [{**item, "record": {}} for item in REQUIREMENTS]
CLEAN_ASSESSMENTS = [{**item, "state": "no_divergence"} for item in REQUIREMENTS]


def finding(**values: Any) -> dict[str, Any]:
    return {
        "source": "gate",
        "association": "requirement",
        "class": "gate-unit",
        "affected_point": "api",
        "criterion": "tests-pass",
        "kind": "gate",
        "between": ["implementation", "validation"],
        "detail": {"exit_code": 1},
        **values,
    }


def test_classification_uses_only_the_bound_criterion_policy() -> None:
    result = classify_findings(
        [
            finding(),
            finding(
                **{
                    "class": "review-arch",
                    "criterion": "arch-ok",
                    "kind": "review",
                    "source": "review",
                }
            ),
            finding(criterion="no-policy"),
            finding(
                **{
                    "association": "unknown",
                    "class": None,
                    "criterion": None,
                    "kind": None,
                }
            ),
        ],
        SNAPSHOT,
    )
    assert [item["classification"] for item in result] == [
        "blocking",
        "non_blocking",
        "unclassified",
        "unclassified",
    ]


def _derive(
    *,
    attempt_state: str = "valid",
    evidence: list[dict[str, Any]] | None = None,
    assessments: list[dict[str, Any]] | None = None,
    findings: list[dict[str, Any]] | None = None,
    links: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    return derive_verdict(
        REQUIREMENTS,
        attempt_state,
        EVIDENCE if evidence is None else evidence,
        CLEAN_ASSESSMENTS if assessments is None else assessments,
        [] if findings is None else findings,
        [] if links is None else links,
    )


def test_clean_is_consistent_with_absent_pendencies() -> None:
    assert _derive() == ([], "consistent")


def test_non_blocking_finding_stays_consistent() -> None:
    pendencies, verdict = _derive(findings=[finding(classification="non_blocking")])
    assert pendencies == []
    assert verdict == "consistent"


def test_blocking_finding_is_a_pendency() -> None:
    pendencies, verdict = _derive(findings=[finding(classification="blocking")])
    assert pendencies == [
        {
            "reason": "finding_blocking",
            "class": "gate-unit",
            "affected_point": "api",
            "criterion": "tests-pass",
            "kind": "gate",
            "finding_index": 0,
        }
    ]
    assert verdict == "has pendency"


def test_unclassified_findings_include_unknown_and_no_policy_cases() -> None:
    unclassified = [
        finding(classification="unclassified"),
        finding(
            **{
                "association": "unknown",
                "class": None,
                "affected_point": None,
                "criterion": None,
                "kind": None,
                "classification": "unclassified",
            }
        ),
    ]
    pendencies, verdict = _derive(findings=unclassified)
    assert [item["reason"] for item in pendencies] == [
        "finding_unclassified",
        "finding_unclassified",
    ]
    assert pendencies[0]["finding_index"] == 0
    assert pendencies[1]["finding_index"] == 1
    assert all(
        all(
            item[key] is None
            for key in ("class", "affected_point", "criterion", "kind")
        )
        for item in pendencies[1:]
    )
    assert verdict == "has pendency"


def test_indeterminate_assessment_requires_recorded_evidence() -> None:
    assessments = [
        {**REQUIREMENTS[0], "state": "indeterminate"},
        {**REQUIREMENTS[1], "state": "no_divergence"},
    ]
    pendencies, verdict = _derive(assessments=assessments)
    assert pendencies == [
        {
            "reason": "assessment_indeterminate",
            "class": "gate-unit",
            "affected_point": "api",
            "criterion": "tests-pass",
            "kind": "gate",
        }
    ]
    assert verdict == "has pendency"


def test_missing_attempt_and_evidence_are_both_reported() -> None:
    pendencies, verdict = _derive(attempt_state="none", evidence=[], assessments=[])
    assert pendencies == [
        {
            "reason": "attempt_not_valid",
            "class": None,
            "affected_point": None,
            "criterion": None,
            "kind": None,
        },
        {
            "reason": "evidence_unrecorded",
            "class": "gate-unit",
            "affected_point": "api",
            "criterion": "tests-pass",
            "kind": "gate",
        },
        {
            "reason": "evidence_unrecorded",
            "class": "review-arch",
            "affected_point": "api",
            "criterion": "arch-ok",
            "kind": "review",
        },
    ]
    assert verdict == "has pendency"


def test_not_reverified_link_is_a_pendency_after_finding_pendencies() -> None:
    link = {
        "report_ref": "changes/c1/report/1.json",
        "finding_index": 0,
        "association": "requirement",
        "class": "gate-unit",
        "affected_point": "api",
        "criterion": "tests-pass",
        "kind": "gate",
        "state": "indeterminate",
        "result": "not_reverified",
        "reason": "indeterminate",
    }
    pendencies, verdict = _derive(
        findings=[finding(classification="blocking")], links=[link]
    )
    assert pendencies[-1] == {
        "reason": "earlier_finding_not_reverified",
        "class": "gate-unit",
        "affected_point": "api",
        "criterion": "tests-pass",
        "kind": "gate",
        "link_index": 0,
    }
    assert verdict == "has pendency"


def test_resolved_and_still_divergent_links_add_no_pendency() -> None:
    for result in ("resolved", "still_divergent"):
        pendencies, verdict = _derive(
            links=[
                {
                    "class": "gate-unit",
                    "affected_point": "api",
                    "criterion": "tests-pass",
                    "kind": "gate",
                    "result": result,
                }
            ]
        )
        assert pendencies == []
        assert verdict == "consistent"


def test_evidence_without_a_mapping_record_is_unrecorded() -> None:
    pendencies, verdict = _derive(evidence=[dict(REQUIREMENTS[0])])
    assert pendencies[0] == {
        "reason": "evidence_unrecorded",
        "class": "gate-unit",
        "affected_point": "api",
        "criterion": "tests-pass",
        "kind": "gate",
    }
    assert verdict == "has pendency"
