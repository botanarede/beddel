"""Inventory version model and pure validation (AD-8, AD-9, AD-11, AD-12, AD-16).

No I/O here. Validation checks only identity formation and univocal
resolution: it never executes a criterion and never judges whether an
obligation should exist. Every failing entry is reported with a locator and a
reason code; nothing is silently dropped.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

__all__ = [
    "ID_PATTERN",
    "Component",
    "Failure",
    "Inventory",
    "RequirementId",
    "is_valid_id",
    "validate_inventory",
]

ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")

_TOP_KEYS = frozenset({"version", "classes", "components", "criteria", "obligations"})
_CLASS_KINDS = frozenset({"gate", "review"})
_COMPONENT_KINDS = frozenset({"component", "shared_contract"})


@dataclass(frozen=True)
class RequirementId:
    """AD-8: frozen value of the three constituents; never parsed from text."""

    class_id: str
    affected_point_id: str
    criterion_id: str

    def display(self) -> str:
        """Display only; never parsed back or compared."""
        return f"{self.class_id}/{self.affected_point_id}/{self.criterion_id}"


@dataclass(frozen=True)
class Component:
    """An Affected point: a component or a shared contract at a path."""

    id: str
    kind: str
    path: str


@dataclass(frozen=True)
class Failure:
    """One failing entry: where it is and why (reason code only)."""

    locator: str
    code: str


@dataclass(frozen=True)
class Inventory:
    """A structurally valid inventory version."""

    version: str
    classes: tuple[tuple[str, str], ...]
    components: tuple[Component, ...]
    criteria: tuple[tuple[str, str], ...]
    obligations: tuple[RequirementId, ...]


def is_valid_id(value: object) -> bool:
    """Return True if ``value`` is a string id matching the id pattern."""
    return isinstance(value, str) and ID_PATTERN.fullmatch(value) is not None


def _valid_path(value: str) -> bool:
    if not value or value.startswith("/") or "\\" in value:
        return False
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        return False
    return all(seg not in ("", ".", "..") for seg in value.split("/"))


def _entries(
    data: Mapping[str, object],
    key: str,
    keys: frozenset[str],
    failures: list[Failure],
) -> list[tuple[int, Mapping[str, object]]]:
    """Return the well-formed mapping entries of a list, recording the rest."""
    raw = data.get(key)
    if not isinstance(raw, list):
        failures.append(Failure(key, "schema.type"))
        return []
    entries: list[tuple[int, Mapping[str, object]]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            failures.append(Failure(f"{key}[{index}]", "schema.type"))
        elif set(item) != keys:
            failures.append(Failure(f"{key}[{index}]", "schema.keys"))
        else:
            entries.append((index, item))
    return entries


def _declared_ids(
    key: str,
    entries: list[tuple[int, Mapping[str, object]]],
    failures: list[Failure],
) -> dict[str, int]:
    """Check ids of declarations; return the first index of each valid id."""
    seen: dict[str, int] = {}
    for index, item in entries:
        value = item["id"]
        if not isinstance(value, str) or not is_valid_id(value):
            failures.append(Failure(f"{key}[{index}].id", "id.invalid"))
            continue
        if value in seen:
            failures.append(Failure(f"{key}[{index}].id", "id.duplicate"))
        else:
            seen[value] = index
    return seen


def validate_inventory(
    data: object, expected_version: str
) -> tuple[Inventory | None, list[Failure]]:
    """Validate a parsed inventory version.

    Returns ``(inventory, [])`` when every identity forms and resolves, else
    ``(None, failures)`` listing every failing entry.
    """
    failures: list[Failure] = []
    if not isinstance(data, dict):
        return None, [Failure("$", "schema.type")]
    if set(data) != _TOP_KEYS:
        return None, [Failure("$", "schema.keys")]

    version = data["version"]
    if not is_valid_id(version):
        failures.append(Failure("version", "id.invalid"))
    elif version != expected_version:
        failures.append(Failure("version", "version.mismatch"))

    class_entries = _entries(data, "classes", frozenset({"id", "kind"}), failures)
    component_entries = _entries(
        data, "components", frozenset({"id", "kind", "path"}), failures
    )
    criterion_entries = _entries(
        data, "criteria", frozenset({"id", "description"}), failures
    )
    obligation_entries = _entries(
        data,
        "obligations",
        frozenset({"class", "affected_point", "criterion"}),
        failures,
    )

    class_ids = _declared_ids("classes", class_entries, failures)
    component_ids = _declared_ids("components", component_entries, failures)
    criterion_ids = _declared_ids("criteria", criterion_entries, failures)

    for index, item in class_entries:
        if not isinstance(item["kind"], str) or item["kind"] not in _CLASS_KINDS:
            failures.append(Failure(f"classes[{index}].kind", "kind.invalid"))
    for index, item in component_entries:
        if not isinstance(item["kind"], str) or item["kind"] not in _COMPONENT_KINDS:
            failures.append(Failure(f"components[{index}].kind", "kind.invalid"))
        path = item["path"]
        if not isinstance(path, str) or not _valid_path(path):
            failures.append(Failure(f"components[{index}].path", "path.invalid"))
    for index, item in criterion_entries:
        if not isinstance(item["description"], str):
            failures.append(Failure(f"criteria[{index}].description", "schema.type"))

    obligations: list[RequirementId] = []
    composed: set[RequirementId] = set()
    for index, item in obligation_entries:
        constituents = (item["class"], item["affected_point"], item["criterion"])
        names = ("class", "affected_point", "criterion")
        declared = (class_ids, component_ids, criterion_ids)
        codes = (
            "ref.class_unresolved",
            "ref.affected_point_unresolved",
            "ref.criterion_unresolved",
        )
        ok = True
        for name, value, known, code in zip(names, constituents, declared, codes):
            if not is_valid_id(value):
                failures.append(Failure(f"obligations[{index}].{name}", "id.invalid"))
                ok = False
            elif value not in known:
                failures.append(Failure(f"obligations[{index}].{name}", code))
                ok = False
        if not ok:
            continue
        requirement = RequirementId(
            str(constituents[0]), str(constituents[1]), str(constituents[2])
        )
        if requirement in composed:
            failures.append(Failure(f"obligations[{index}]", "obligation.duplicate"))
        else:
            composed.add(requirement)
            obligations.append(requirement)

    if failures:
        return None, failures

    return (
        Inventory(
            version=str(version),
            classes=tuple((str(i["id"]), str(i["kind"])) for _, i in class_entries),
            components=tuple(
                Component(str(i["id"]), str(i["kind"]), str(i["path"]))
                for _, i in component_entries
            ),
            criteria=tuple(
                (str(i["id"]), str(i["description"])) for _, i in criterion_entries
            ),
            obligations=tuple(obligations),
        ),
        [],
    )
