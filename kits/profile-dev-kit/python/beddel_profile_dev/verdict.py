"""Pure classification of Findings and derivation of Report Verdicts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

__all__ = ["classify_findings", "derive_verdict"]

_REQUIREMENT_KEYS = ("class", "affected_point", "criterion")


def _key(value: Mapping[str, Any]) -> tuple[str, str, str] | None:
    if not all(isinstance(value.get(item), str) for item in _REQUIREMENT_KEYS):
        return None
    return tuple(value[item] for item in _REQUIREMENT_KEYS)  # type: ignore[return-value]


def _requirements(
    requirements: Iterable[Mapping[str, Any]] | Mapping[object, Mapping[str, Any]],
) -> list[tuple[tuple[str, str, str], Mapping[str, Any]]]:
    values = (
        requirements.values() if isinstance(requirements, Mapping) else requirements
    )
    result = [
        (key, item)
        for item in values
        if isinstance(item, Mapping) and (key := _key(item)) is not None
    ]
    return sorted(result, key=lambda pair: pair[0])


def _criterion_blocking(snapshot: Mapping[str, Any]) -> dict[str, bool]:
    criteria = snapshot.get("criteria")
    if not isinstance(criteria, list):
        return {}
    return {
        item["id"]: item["blocking"]
        for item in criteria
        if isinstance(item, Mapping)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("blocking"), bool)
    }


def classify_findings(
    findings: Iterable[Mapping[str, Any]], snapshot: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Attach the ratified criterion's blocking classification to each Finding."""
    blocking = _criterion_blocking(snapshot)
    classified: list[dict[str, Any]] = []
    for finding in findings:
        item = dict(finding)
        if finding.get("association") == "requirement":
            criterion = finding.get("criterion")
            value = blocking.get(criterion) if isinstance(criterion, str) else None
            item["classification"] = (
                "blocking"
                if value is True
                else "non_blocking"
                if value is False
                else "unclassified"
            )
        else:
            item["classification"] = "unclassified"
        classified.append(item)
    return classified


def _pendency(
    reason: str, requirement: Mapping[str, Any] | None = None, **extra: Any
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "reason": reason,
        "class": None,
        "affected_point": None,
        "criterion": None,
        "kind": None,
    }
    if requirement is not None:
        result.update(
            {
                "class": requirement.get("class"),
                "affected_point": requirement.get("affected_point"),
                "criterion": requirement.get("criterion"),
                "kind": requirement.get("kind"),
            }
        )
    result.update(extra)
    return result


def _evidence_keys(
    evidence: Iterable[Mapping[str, Any]] | Mapping[object, Mapping[str, Any]],
) -> set[tuple[str, str, str]]:
    values = evidence.values() if isinstance(evidence, Mapping) else evidence
    return {
        key
        for item in values
        if isinstance(item, Mapping)
        and isinstance(item.get("record"), Mapping)
        and (key := _key(item)) is not None
    }


def _assessment_map(
    assessments: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str, str], str]:
    result: dict[tuple[str, str, str], str] = {}
    for item in assessments:
        key = _key(item)
        state = item.get("state")
        if key is not None and isinstance(state, str):
            result.setdefault(key, state)
    return result


def _revision_values(earlier_revisions: Iterable[Any]) -> list[str]:
    values: set[str] = set()
    for item in earlier_revisions:
        if isinstance(item, str):
            values.add(item)
        elif isinstance(item, Mapping) and isinstance(item.get("revision"), str):
            values.add(item["revision"])
    return sorted(values)


def derive_verdict(
    requirements: Iterable[Mapping[str, Any]] | Mapping[object, Mapping[str, Any]],
    attempt_state: str,
    evidence: Iterable[Mapping[str, Any]] | Mapping[object, Mapping[str, Any]],
    assessments: Iterable[Mapping[str, Any]],
    findings: Iterable[Mapping[str, Any]],
    earlier_revisions: Iterable[Any],
) -> tuple[list[dict[str, Any]], str]:
    """Return deterministic Pendencies and the binary Report Verdict."""
    ordered = _requirements(requirements)
    evidence_keys = _evidence_keys(evidence)
    assessment_states = _assessment_map(assessments)
    pendencies: list[dict[str, Any]] = []

    if attempt_state != "valid":
        pendencies.append(_pendency("attempt_not_valid"))

    for key, requirement in ordered:
        if key not in evidence_keys:
            pendencies.append(_pendency("evidence_unrecorded", requirement))

    for key, requirement in ordered:
        if key in evidence_keys and assessment_states.get(key) not in {
            "no_divergence",
            "divergent",
        }:
            pendencies.append(_pendency("assessment_indeterminate", requirement))

    for index, finding in enumerate(findings):
        classification = finding.get("classification")
        if classification == "blocking":
            pendencies.append(
                _pendency(
                    "finding_blocking",
                    finding if finding.get("association") == "requirement" else None,
                    finding_index=index,
                )
            )
        elif classification != "non_blocking":
            pendencies.append(
                _pendency(
                    "finding_unclassified",
                    finding if finding.get("association") == "requirement" else None,
                    finding_index=index,
                )
            )

    revisions = _revision_values(earlier_revisions)
    if revisions:
        pendencies.append(_pendency("reverification_unrecorded", revisions=revisions))

    return pendencies, "consistent" if not pendencies else "has pendency"
