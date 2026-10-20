"""AC1, AC2, AC5: strict inventory schema, Requirement ID, failure reasons."""

from __future__ import annotations

import copy
import dataclasses
from typing import Any

import pytest
import yaml
from beddel_profile_dev.inventory import (
    RequirementId,
    is_valid_id,
    validate_inventory,
)

from ._helpers import GOOD, good


def _codes(data: Any, version: str = "v1") -> list[tuple[str, str]]:
    inventory, failures = validate_inventory(data, version)
    assert inventory is None
    return [(f.locator, f.code) for f in failures]


def test_good_inventory_validates() -> None:
    inventory, failures = validate_inventory(good(), "v1")
    assert failures == []
    assert inventory is not None
    assert inventory.version == "v1"
    assert len(inventory.obligations) == 3
    assert inventory.classes[0] == ("gate-unit", "gate")


def test_requirement_id_is_a_frozen_value_over_its_constituents() -> None:
    a = RequirementId("c", "p", "k")
    b = RequirementId("c", "p", "k")
    assert a == b and hash(a) == hash(b) and len({a, b}) == 1
    assert a != RequirementId("c", "p", "other")
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.class_id = "x"  # type: ignore[misc]
    # Display only: a rendering collision never makes two identities equal.
    assert (
        RequirementId("a/b", "c", "d").display()
        == RequirementId("a", "b/c", "d").display()
    )
    assert RequirementId("a/b", "c", "d") != RequirementId("a", "b/c", "d")


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("v1", True),
        ("a.b_c-d", True),
        ("0abc", True),
        ("", False),
        ("-a", False),
        ("A", False),
        ("a b", False),
        ("a" * 65, False),
        ("a" * 64, True),
        ("a\n", False),
        (1, False),
        (None, False),
    ],
)
def test_id_pattern(value: object, ok: bool) -> None:
    assert is_valid_id(value) is ok


def test_unknown_or_missing_top_level_keys_are_rejected() -> None:
    extra = good()
    extra["extra"] = 1
    assert _codes(extra) == [("$", "schema.keys")]
    missing = good()
    del missing["criteria"]
    assert _codes(missing) == [("$", "schema.keys")]
    assert _codes([1]) == [("$", "schema.type")]


def test_unknown_key_inside_an_entry_is_rejected() -> None:
    data = good()
    data["classes"][0]["extra"] = 1
    assert ("classes[0]", "schema.keys") in _codes(data)


def test_wrong_types_are_rejected() -> None:
    data = good()
    data["classes"] = "nope"
    assert ("classes", "schema.type") in _codes(data)
    data = good()
    data["components"][0] = "x"
    assert ("components[0]", "schema.type") in _codes(data)
    data = good()
    data["criteria"][0]["description"] = 3
    assert ("criteria[0].description", "schema.type") in _codes(data)


def test_version_must_equal_the_expected_stem_and_be_valid() -> None:
    data = good("v2")
    assert ("version", "version.mismatch") in _codes(data, "v1")
    data = good()
    data["version"] = "BAD"
    assert ("version", "id.invalid") in _codes(data)


def test_invalid_kinds() -> None:
    data = good()
    data["classes"][0]["kind"] = ["gate"]
    data["components"][0]["kind"] = {"gate": 1}
    data["components"][1]["kind"] = 7
    codes = _codes(data)
    assert ("classes[0].kind", "kind.invalid") in codes
    assert ("components[0].kind", "kind.invalid") in codes
    assert ("components[1].kind", "kind.invalid") in codes


def test_invalid_kinds_by_value() -> None:
    data = good()
    data["classes"][0]["kind"] = "other"
    data["components"][0]["kind"] = "gate"
    codes = _codes(data)
    assert ("classes[0].kind", "kind.invalid") in codes
    assert ("components[0].kind", "kind.invalid") in codes


@pytest.mark.parametrize("key", ["classes", "components", "criteria"])
def test_duplicate_declared_id(key: str) -> None:
    data = good()
    data[key].append(copy.deepcopy(data[key][0]))
    assert (f"{key}[2].id", "id.duplicate") in _codes(data)


def test_invalid_declared_id() -> None:
    data = good()
    data["criteria"][1]["id"] = "Bad Id"
    assert ("criteria[1].id", "id.invalid") in _codes(data)


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("class", "ref.class_unresolved"),
        ("affected_point", "ref.affected_point_unresolved"),
        ("criterion", "ref.criterion_unresolved"),
    ],
)
def test_unresolved_constituent(field: str, code: str) -> None:
    data = good()
    data["obligations"][0][field] = "ghost"
    assert (f"obligations[0].{field}", code) in _codes(data)


def test_invalid_or_missing_constituent() -> None:
    data = good()
    data["obligations"][0]["class"] = 5
    assert ("obligations[0].class", "id.invalid") in _codes(data)
    data = good()
    del data["obligations"][1]["criterion"]
    assert ("obligations[1]", "schema.keys") in _codes(data)


def test_duplicate_requirement_id() -> None:
    data = good()
    data["obligations"].append(copy.deepcopy(data["obligations"][0]))
    assert ("obligations[3]", "obligation.duplicate") in _codes(data)


@pytest.mark.parametrize(
    "path",
    ["/abs", "../x", "a/../b", "a\\b", "a//b", "./a", "a/", "", "a/./b", "a\x00b"],
)
def test_invalid_component_path(path: str) -> None:
    data = good()
    data["components"][0]["path"] = path
    assert ("components[0].path", "path.invalid") in _codes(data)


def test_every_failing_entry_is_listed() -> None:
    data = good()
    data["obligations"][0]["class"] = "ghost"
    data["obligations"][1]["criterion"] = "ghost"
    data["components"][0]["path"] = "/abs"
    assert len(_codes(data)) == 3


def test_yaml_is_loaded_with_safe_load_only() -> None:
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load("!!python/object/apply:os.system ['true']")
    assert GOOD["version"] == "v1"
