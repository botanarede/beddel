"""Gate configuration (Story 3.1, Task 1): strategy B, fail-closed."""

from __future__ import annotations

from typing import Any

import pytest
from beddel_profile_dev import config as cfg
from beddel_profile_dev._errors import (
    PROFILE_CONFIG_INVALID,
    PROFILE_GATE_COMMAND_INVALID,
    ProfileError,
)


def _raw(**overrides: Any) -> dict[str, object]:
    raw: dict[str, object] = {
        "gate_executables": ["git", "pytest", "ruff", "mypy"],
        "required_env_keys": [],
        "inventory_dir": ".beddel-profile/inventory",
        "records_dir": ".beddel-profile/records",
        "gate_commands": [["ruff", "check", "."], ["pytest", "-q"]],
        "gate_timeout_seconds": 30,
        "gate_total_timeout_seconds": 90,
    }
    raw.update(overrides)
    return raw


def test_default_gate_config_is_valid_and_allowlisted() -> None:
    loaded = cfg.load_config()
    assert loaded.gate_commands == cfg.GATE_COMMANDS
    assert loaded.gate_commands, "the default Gate must not be empty"
    assert all(argv[0] in loaded.gate_executables for argv in loaded.gate_commands)
    assert loaded.gate_timeout_seconds == cfg.GATE_TIMEOUT_SECONDS
    assert loaded.gate_total_timeout_seconds == cfg.GATE_TOTAL_TIMEOUT_SECONDS


def test_valid_gate_config_is_normalised_to_tuples() -> None:
    loaded = cfg.validate_config(_raw())
    assert loaded.gate_commands == (("ruff", "check", "."), ("pytest", "-q"))
    assert loaded.gate_timeout_seconds == 30
    assert loaded.gate_total_timeout_seconds == 90


def test_total_budget_is_optional() -> None:
    loaded = cfg.validate_config(_raw(gate_total_timeout_seconds=None))
    assert loaded.gate_total_timeout_seconds is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"gate_commands": []},  # an outcome in which no command ran
        {"gate_commands": "ruff check ."},  # not a list
        {"gate_commands": ["ruff"]},  # an argv is a list, not a string
        {"gate_commands": [[]]},  # empty argv
        {"gate_commands": [[""]]},  # blank executable
        {"gate_commands": [["ruff", 1]]},  # non-string argument
        {"gate_commands": [["ruff", ""]]},  # blank argument
        {"gate_commands": [["ruff", "a\x00b"]]},  # NUL in an argument
        {"gate_timeout_seconds": 0},
        {"gate_timeout_seconds": -5},
        {"gate_timeout_seconds": True},
        {"gate_timeout_seconds": 1.5},
        {"gate_timeout_seconds": "30"},
        {"gate_timeout_seconds": None},  # the per-command budget is mandatory
        {"gate_timeout_seconds": 86401},
        {"gate_total_timeout_seconds": 0},
        {"gate_total_timeout_seconds": False},
        {"gate_total_timeout_seconds": "90"},
    ],
)
def test_malformed_gate_config_raises_config_invalid(overrides: dict[str, Any]) -> None:
    with pytest.raises(ProfileError) as info:
        cfg.validate_config(_raw(**overrides))
    assert info.value.code == PROFILE_CONFIG_INVALID


@pytest.mark.parametrize("missing", ["gate_commands", "gate_timeout_seconds"])
def test_missing_gate_key_raises_config_invalid(missing: str) -> None:
    raw = _raw()
    del raw[missing]
    with pytest.raises(ProfileError) as info:
        cfg.validate_config(raw)
    assert info.value.code == PROFILE_CONFIG_INVALID


def test_non_allowlisted_executable_is_refused_with_its_own_code() -> None:
    with pytest.raises(ProfileError) as info:
        cfg.validate_config(_raw(gate_commands=[["ruff", "check"], ["curl", "x"]]))
    assert info.value.code == PROFILE_GATE_COMMAND_INVALID
    assert info.value.details == {"index": 1}  # identifiers only, never the argv


@pytest.mark.parametrize(
    "executable", ["/usr/bin/ruff", "..\\ruff", "./ruff", "bin/ruff"]
)
def test_a_path_form_executable_is_refused_with_the_command_code(
    executable: str,
) -> None:
    with pytest.raises(ProfileError) as info:
        cfg.validate_config(_raw(gate_commands=[["ruff", "check"], [executable]]))
    assert info.value.code == PROFILE_GATE_COMMAND_INVALID
    assert info.value.details == {"index": 1}


def test_allowlist_is_the_configured_one_not_a_hard_coded_one() -> None:
    raw = _raw(gate_executables=["git"], gate_commands=[["git", "status"]])
    assert cfg.validate_config(raw).gate_commands == (("git", "status"),)
    with pytest.raises(ProfileError) as info:
        cfg.validate_config(_raw(gate_executables=["git"]))  # ruff not allowlisted
    assert info.value.code == PROFILE_GATE_COMMAND_INVALID


def test_load_config_rejects_a_non_allowlisted_command_constant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("sh", "-c", "true"),))
    with pytest.raises(ProfileError) as info:
        cfg.load_config()
    assert info.value.code == PROFILE_GATE_COMMAND_INVALID


def test_load_config_rejects_a_missing_gate_constant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(cfg, "GATE_TIMEOUT_SECONDS")
    with pytest.raises(ProfileError) as info:
        cfg.load_config()
    assert info.value.code == PROFILE_CONFIG_INVALID
