"""Pure selection and linking of Findings across revisions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

__all__ = ["link_findings", "select_earlier_findings"]

_REQUIREMENT_KEYS = ("class", "affected_point", "criterion")
_EARLIER_RECORD = tuple[int, Mapping[str, Any]]
_EARLIER_FINDING = tuple[str, int, Any]


def _key(value: Mapping[str, Any]) -> tuple[str, str, str] | None:
    if value.get("association") != "requirement":
        return None
    if not all(isinstance(value.get(item), str) for item in _REQUIREMENT_KEYS):
        return None
    return tuple(value[item] for item in _REQUIREMENT_KEYS)  # type: ignore[return-value]


def _divergences(record: Mapping[str, Any]) -> list[Any] | None:
    items = record.get("items")
    if not isinstance(items, Mapping):
        return None
    divergences = items.get("divergences")
    if not isinstance(divergences, Mapping):
        return None
    if divergences.get("status") != "present":
        return None
    value = divergences.get("value")
    return value if isinstance(value, list) and value else None


def select_earlier_findings(
    history: Iterable[_EARLIER_RECORD], revision: str, change_id: str
) -> tuple[str | None, list[_EARLIER_FINDING]]:
    """Select Findings from the latest earlier revision with divergences."""
    candidates: list[tuple[int, str, Mapping[str, Any], list[Any]]] = []
    for ordinal, record in history:
        record_revision = record.get("revision")
        divergences = _divergences(record)
        if (
            isinstance(record_revision, str)
            and record_revision != revision
            and divergences is not None
        ):
            candidates.append((ordinal, record_revision, record, divergences))

    if not candidates:
        return None, []

    selected_revision = max(candidates, key=lambda item: item[0])[1]
    selected: list[_EARLIER_FINDING] = []
    for ordinal, record_revision, _, divergences in sorted(candidates):
        if record_revision != selected_revision:
            continue
        report_ref = f"changes/{change_id}/report/{ordinal}.json"
        selected.extend(
            (report_ref, index, finding) for index, finding in enumerate(divergences)
        )
    return (selected_revision, selected) if selected else (None, [])


def _requirements(
    requirements: Iterable[Mapping[str, Any]],
) -> set[tuple[str, str, str]]:
    return {
        key
        for requirement in requirements
        if isinstance(requirement, Mapping)
        and (key := _key({"association": "requirement", **dict(requirement)}))
        is not None
    }


def _assessment_states(
    assessments: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str, str], str | None]:
    result: dict[tuple[str, str, str], str | None] = {}
    for assessment in assessments:
        if not isinstance(assessment, Mapping):
            continue
        if not all(isinstance(assessment.get(item), str) for item in _REQUIREMENT_KEYS):
            continue
        key = tuple(assessment[item] for item in _REQUIREMENT_KEYS)  # type: ignore[return-value]
        state = assessment.get("state")
        result.setdefault(key, state if isinstance(state, str) else None)
    return result


def _current_finding_keys(
    findings: Iterable[Mapping[str, Any]],
) -> set[tuple[str, str, str]]:
    return {
        key
        for finding in findings
        if isinstance(finding, Mapping) and (key := _key(finding)) is not None
    }


def link_findings(
    earlier: Iterable[_EARLIER_FINDING],
    requirements: Iterable[Mapping[str, Any]],
    assessments: Iterable[Mapping[str, Any]],
    findings: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Link earlier Findings to the current revision's assessment results."""
    required = _requirements(requirements)
    states = _assessment_states(assessments)
    current_findings = _current_finding_keys(findings)
    links: list[dict[str, Any]] = []

    for report_ref, finding_index, earlier_finding in earlier:
        association = (
            earlier_finding.get("association")
            if isinstance(earlier_finding, Mapping)
            else None
        )
        key = _key(earlier_finding) if isinstance(earlier_finding, Mapping) else None
        valid = key is not None
        if key is not None:
            constituents = {
                "class": earlier_finding["class"],
                "affected_point": earlier_finding["affected_point"],
                "criterion": earlier_finding["criterion"],
                "kind": earlier_finding.get("kind"),
            }
        else:
            constituents = {
                "class": None,
                "affected_point": None,
                "criterion": None,
                "kind": None,
            }

        state = states.get(key) if valid and key in required else None
        if not valid or key not in required:
            result = "not_reverified"
            reason = "outside_scope"
        elif state == "divergent" or key in current_findings:
            result = "still_divergent"
            reason = None
        elif state == "no_divergence":
            result = "resolved"
            reason = None
        else:
            result = "not_reverified"
            reason = "indeterminate"

        links.append(
            {
                "report_ref": report_ref,
                "finding_index": finding_index,
                "association": association,
                **constituents,
                "state": state,
                "result": result,
                "reason": reason,
            }
        )
    return links
