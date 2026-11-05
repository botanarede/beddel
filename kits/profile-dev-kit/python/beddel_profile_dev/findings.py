"""Pure derivation of Story 4.3 Findings and Requirement assessments."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

__all__ = [
    "ASSESSMENT_BEGIN",
    "ASSESSMENT_END",
    "REVIEW_ASSESSMENT_SCHEMA",
    "derive_findings",
    "parse_review_assessment",
]

ASSESSMENT_BEGIN = "BEDDEL-ASSESSMENT-BEGIN"
ASSESSMENT_END = "BEDDEL-ASSESSMENT-END"
REVIEW_ASSESSMENT_SCHEMA = "profile-dev/review-assessment/1"
_BETWEEN = frozenset(
    {"specification", "implementation", "validation", "affected_point"}
)
_REQUIREMENT_KEYS = ("class", "affected_point", "criterion")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _between(value: Any) -> list[str] | None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(item, str) for item in value)
        or value[0] == value[1]
        or any(item not in _BETWEEN for item in value)
    ):
        return None
    return [value[0], value[1]]


def _description(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_divergence(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or set(value) != {"between", "description"}:
        return None
    between = _between(value["between"])
    if between is None or not _description(value["description"]):
        return None
    return {"between": between, "description": value["description"]}


def _parse_entry(value: Any, *, unassociated: bool) -> dict[str, Any] | None:
    required = (
        {"between", "description"}
        if unassociated
        else {"class", "affected_point", "criterion", "divergences"}
    )
    if not isinstance(value, dict) or set(value) != required:
        return None
    if unassociated:
        between = _between(value["between"])
        if between is None or not _description(value["description"]):
            return None
        return {"between": between, "description": value["description"]}
    if not all(
        isinstance(value[key], str) and bool(value[key].strip())
        for key in ("class", "affected_point", "criterion")
    ) or not isinstance(value["divergences"], list):
        return None
    divergences = [_parse_divergence(item) for item in value["divergences"]]
    if any(item is None for item in divergences):
        return None
    return {
        "class": value["class"],
        "affected_point": value["affected_point"],
        "criterion": value["criterion"],
        "divergences": [item for item in divergences if item is not None],
    }


def parse_review_assessment(output: bytes) -> dict[str, Any] | None:
    """Parse exactly one strict assessment block from verified Review bytes.

    The caller is responsible for proving that ``output`` is the byte sequence
    named by the Evidence digest. This function performs no I/O and returns
    ``None`` for any unreadable block.
    """
    if not isinstance(output, bytes):
        return None
    try:
        text = output.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return None
    lines = text.splitlines()
    begin = [
        index for index, line in enumerate(lines) if line.strip() == ASSESSMENT_BEGIN
    ]
    end = [index for index, line in enumerate(lines) if line.strip() == ASSESSMENT_END]
    if len(begin) != 1 or len(end) != 1 or begin[0] >= end[0]:
        return None
    payload = "\n".join(lines[begin[0] + 1 : end[0]]).strip()
    if not payload:
        return None
    try:
        value = json.loads(
            payload,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (TypeError, ValueError, RecursionError):
        return None
    if not isinstance(value, dict) or set(value) != {
        "schema",
        "assessments",
        "unassociated",
    }:
        return None
    if value["schema"] != REVIEW_ASSESSMENT_SCHEMA:
        return None
    if not isinstance(value["assessments"], list) or not isinstance(
        value["unassociated"], list
    ):
        return None
    assessments = [
        _parse_entry(item, unassociated=False) for item in value["assessments"]
    ]
    unassociated = [
        _parse_entry(item, unassociated=True) for item in value["unassociated"]
    ]
    if any(item is None for item in assessments) or any(
        item is None for item in unassociated
    ):
        return None
    return {
        "schema": value["schema"],
        "assessments": [item for item in assessments if item is not None],
        "unassociated": [item for item in unassociated if item is not None],
    }


def _key(value: Mapping[str, Any]) -> tuple[str, str, str] | None:
    if not all(isinstance(value.get(item), str) for item in _REQUIREMENT_KEYS):
        return None
    return tuple(value[item] for item in _REQUIREMENT_KEYS)  # type: ignore[return-value]


def _requirements(
    requirements: Iterable[Mapping[str, Any]] | Mapping[object, Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    values = (
        requirements.values() if isinstance(requirements, Mapping) else requirements
    )
    result = [item for item in values if isinstance(item, Mapping) and _key(item)]
    return sorted(result, key=lambda item: _key(item) or ("", "", ""))


def _evidence_map(
    evidence: Iterable[Mapping[str, Any]] | Mapping[object, Mapping[str, Any]],
) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    values = evidence.values() if isinstance(evidence, Mapping) else evidence
    result: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for item in values:
        if not isinstance(item, Mapping):
            continue
        key = _key(item)
        if key is not None:
            result.setdefault(key, item)
    return result


def _result(item: Mapping[str, Any]) -> Mapping[str, Any] | None:
    record = item.get("record")
    if isinstance(record, Mapping) and isinstance(record.get("result"), Mapping):
        return record["result"]
    value = item.get("result")
    return value if isinstance(value, Mapping) else None


def _review_digest(item: Mapping[str, Any]) -> tuple[str, str] | None:
    result = _result(item)
    if result is None:
        return None
    review_ref = result.get("review_ref")
    review_sha256 = result.get("review_sha256")
    if not isinstance(review_ref, str) or not isinstance(review_sha256, str):
        return None
    return review_ref, review_sha256


def _finding(
    *,
    source: str,
    requirement: Mapping[str, Any] | None,
    between: list[str],
    detail: Mapping[str, Any],
) -> dict[str, Any]:
    if requirement is None:
        association = "unknown"
        values = {key: None for key in (*_REQUIREMENT_KEYS, "kind")}
    else:
        association = "requirement"
        values = {
            "class": requirement["class"],
            "affected_point": requirement["affected_point"],
            "criterion": requirement["criterion"],
            "kind": requirement.get("kind"),
        }
    return {
        "source": source,
        "association": association,
        **values,
        "between": between,
        "detail": dict(detail),
    }


def _finding_sort_key(value: Mapping[str, Any]) -> tuple[str, ...]:
    detail = json.dumps(value["detail"], sort_keys=True, separators=(",", ":"))
    between = value["between"]
    return (
        str(value.get("class") or ""),
        str(value.get("affected_point") or ""),
        str(value.get("criterion") or ""),
        str(value.get("kind") or ""),
        str(value["source"]),
        str(value["association"]),
        str(between[0]),
        str(between[1]),
        detail,
    )


def derive_findings(
    requirements: Iterable[Mapping[str, Any]] | Mapping[object, Mapping[str, Any]],
    attempt_state: str,
    evidence: Iterable[Mapping[str, Any]] | Mapping[object, Mapping[str, Any]],
    review_output: bytes | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Derive Findings and one assessment for every Requirement ID.

    ``evidence`` is already validated by the I/O layer. The Review bytes are
    still checked against each Review Evidence digest before their block is
    interpreted. No filesystem or other external state is read here.
    """
    ordered = _requirements(requirements)
    by_key = {_key(item): item for item in ordered}
    evidence_by_id = _evidence_map(evidence)
    findings: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    review_entries: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    assessment_states: dict[tuple[str, str, str], str] = {}
    parsed_review: dict[str, Any] | None = None
    review_source: tuple[str, str] | None = None

    if attempt_state == "valid" and isinstance(review_output, bytes):
        for item in evidence_by_id.values():
            review_requirement = by_key.get(_key(item))
            if review_requirement is None or review_requirement.get("kind") != "review":
                continue
            digest = _review_digest(item)
            if digest is None or hashlib.sha256(review_output).hexdigest() != digest[1]:
                continue
            parsed = parse_review_assessment(review_output)
            if parsed is not None:
                parsed_review = parsed
                review_source = digest
                break

    if parsed_review is not None and review_source is not None:
        for entry in parsed_review["assessments"]:
            key = tuple(entry[item] for item in _REQUIREMENT_KEYS)
            review_entries.setdefault(key, []).append(entry)
        for entry in parsed_review["unassociated"]:
            findings.append(
                _finding(
                    source="review",
                    requirement=None,
                    between=entry["between"],
                    detail={
                        "description": entry["description"],
                        "review_ref": review_source[0],
                        "review_sha256": review_source[1],
                    },
                )
            )

    for requirement in ordered:
        requirement_key = _key(requirement)
        assert requirement_key is not None
        evidence_item = evidence_by_id.get(requirement_key)
        state = "not_assessed"
        if attempt_state == "valid" and evidence_item is not None:
            if requirement.get("kind") == "gate":
                result = _result(evidence_item)
                commands = result.get("commands") if result is not None else None
                if isinstance(commands, list) and commands:
                    invalid = False
                    divergent = False
                    for command in commands:
                        if not isinstance(command, Mapping):
                            invalid = True
                            continue
                        exit_code = command.get("exit_code")
                        timed_out = command.get("timed_out")
                        if (
                            timed_out is not False
                            or isinstance(exit_code, bool)
                            or not isinstance(exit_code, int)
                        ):
                            invalid = True
                            continue
                        if exit_code != 0:
                            divergent = True
                            findings.append(
                                _finding(
                                    source="gate",
                                    requirement=requirement,
                                    between=["implementation", "validation"],
                                    detail={
                                        "command": command.get("name"),
                                        "argv": command.get("argv"),
                                        "exit_code": exit_code,
                                        "gate_ref": result.get("gate_ref")
                                        if result is not None
                                        else None,
                                    },
                                )
                            )
                    if invalid:
                        state = "indeterminate"
                    else:
                        state = "divergent" if divergent else "no_divergence"
                else:
                    state = "indeterminate"
            elif requirement.get("kind") == "review":
                digest = _review_digest(evidence_item)
                if (
                    parsed_review is None
                    or digest is None
                    or not isinstance(review_output, bytes)
                    or hashlib.sha256(review_output).hexdigest() != digest[1]
                ):
                    state = "indeterminate"
                else:
                    entries = review_entries.get(requirement_key, [])
                    if len(entries) != 1:
                        state = "indeterminate"
                    else:
                        divergences = entries[0]["divergences"]
                        state = "divergent" if divergences else "no_divergence"
            else:
                state = "indeterminate"
        assessment_states[requirement_key] = state
        assessments.append(
            {
                "class": requirement["class"],
                "affected_point": requirement["affected_point"],
                "criterion": requirement["criterion"],
                "kind": requirement.get("kind"),
                "state": state,
            }
        )

    if parsed_review is not None and review_source is not None:
        for key, entries in review_entries.items():
            if len(entries) != 1:
                continue
            matched_requirement = by_key.get(key)
            if (
                matched_requirement is not None
                and matched_requirement.get("kind") == "review"
                and assessment_states.get(key) != "divergent"
            ):
                continue
            for divergence in entries[0]["divergences"]:
                findings.append(
                    _finding(
                        source="review",
                        requirement=matched_requirement,
                        between=divergence["between"],
                        detail={
                            "description": divergence["description"],
                            "review_ref": review_source[0],
                            "review_sha256": review_source[1],
                        },
                    )
                )

    findings.sort(key=_finding_sort_key)
    return findings, assessments
