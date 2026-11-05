"""Pure assembly of the seven Story 4.1 Verification Report items."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

__all__ = ["REPORT_SCHEMA", "build_items"]

REPORT_SCHEMA = "profile-dev/verification-report/1"
_REQUIREMENT_KEYS = ("class", "affected_point", "criterion")
_MISSING = object()


def _status(status: str, value: Any = _MISSING) -> dict[str, Any]:
    result: dict[str, Any] = {"status": status}
    if value is not _MISSING:
        result["value"] = value
    return result


def _requirement_key(value: Mapping[str, Any]) -> tuple[str, str, str]:
    return tuple(str(value[key]) for key in _REQUIREMENT_KEYS)  # type: ignore[return-value]


def _link_map(
    entries: Mapping[object, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    if isinstance(entries, Mapping):
        return {
            tuple(key): value
            for key, value in entries.items()
            if isinstance(key, tuple) and len(key) == 3 and isinstance(value, Mapping)
        }
    result: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, Mapping):
            try:
                result[_requirement_key(entry)] = entry
            except (KeyError, TypeError):
                continue
    return result


def _criteria(snapshot: Mapping[str, Any]) -> dict[str, str]:
    raw = snapshot.get("criteria", [])
    if not isinstance(raw, list):
        return {}
    return {
        item["id"]: item["description"]
        for item in raw
        if isinstance(item, Mapping)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("description"), str)
    }


def build_items(
    impact: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    attempt_state: str,
    evidence: Mapping[object, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    determinations: Mapping[object, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build the seven Report items without reading or writing anything.

    ``evidence`` and ``determinations`` contain only records already validated
    by the I/O layer. Each link entry carries ``ref`` and ``sha256``; Evidence
    entries also carry the stored record under ``record``.
    """
    if attempt_state not in {"valid", "indeterminate", "none"}:
        raise ValueError("invalid attempt state")

    requirements = [
        item
        for item in impact.get("required_evidence", [])
        if isinstance(item, Mapping)
    ]
    requirements.sort(key=lambda item: _requirement_key(item))
    evidence_by_id = _link_map(evidence)
    determination_by_id = _link_map(determinations)

    applicable: list[dict[str, Any]] = []
    recorded_evidence: list[dict[str, Any]] = []
    pendencies: list[dict[str, Any]] = []
    descriptions = _criteria(snapshot)
    for requirement in requirements:
        key = _requirement_key(requirement)
        criterion = {
            "class": requirement["class"],
            "affected_point": requirement["affected_point"],
            "criterion": requirement["criterion"],
            "kind": requirement.get("kind"),
            "description": descriptions.get(requirement["criterion"], ""),
            "non_applicability": None,
        }
        determination = determination_by_id.get(key)
        if determination is not None:
            criterion["non_applicability"] = {
                "ref": determination["ref"],
                "sha256": determination["sha256"],
            }
        applicable.append(criterion)

        evidence_link = evidence_by_id.get(key)
        if evidence_link is None:
            pendencies.append(
                {
                    "class": requirement["class"],
                    "affected_point": requirement["affected_point"],
                    "criterion": requirement["criterion"],
                    "kind": requirement.get("kind"),
                }
            )
            continue
        record = evidence_link.get("record")
        if not isinstance(record, Mapping):
            pendencies.append(
                {
                    "class": requirement["class"],
                    "affected_point": requirement["affected_point"],
                    "criterion": requirement["criterion"],
                    "kind": requirement.get("kind"),
                }
            )
            continue
        recorded_evidence.append(
            {
                "class": requirement["class"],
                "affected_point": requirement["affected_point"],
                "criterion": requirement["criterion"],
                "kind": requirement.get("kind"),
                "ref": evidence_link["ref"],
                "sha256": evidence_link["sha256"],
                "result": record["result"],
            }
        )

    return {
        "specification": _status("absent"),
        "applicable_criteria": (
            _status("present", applicable) if applicable else _status("absent")
        ),
        "affected_points": (
            _status("present", impact["affected_points"])
            if impact.get("affected_points")
            else _status("absent")
        ),
        "implementation": _status(
            "present",
            {
                "base": impact["base"],
                "revision": impact["revision"],
                "footprint": impact["footprint"],
            },
        ),
        "evidence": (
            _status("present", recorded_evidence)
            if recorded_evidence
            else _status("absent")
        ),
        "divergences": _status("not_assessed"),
        "pendencies": (
            _status("present", pendencies) if pendencies else _status("not_assessed")
        ),
    }
