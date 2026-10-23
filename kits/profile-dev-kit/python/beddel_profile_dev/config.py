"""Kit-internal configuration — the runtime source of the preflight lists.

The lists live here, not in ``kit.yaml`` (whose ``config:`` block is
documentation only and ignored by the core). Fail-closed: a missing or
malformed config raises; it never degrades to empty lists.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from beddel_profile_dev._errors import PROFILE_CONFIG_INVALID as _CONFIG_INVALID
from beddel_profile_dev._errors import (
    PROFILE_GATE_COMMAND_INVALID as _GATE_COMMAND_INVALID,
)
from beddel_profile_dev._errors import ProfileError

__all__ = [
    "GATE_COMMANDS",
    "GATE_EXECUTABLES",
    "GATE_TIMEOUT_SECONDS",
    "GATE_TOTAL_TIMEOUT_SECONDS",
    "INVENTORY_DIR",
    "RECORDS_DIR",
    "REQUIRED_ENV_KEYS",
    "REVIEW_AGENT",
    "REVIEW_MODEL",
    "REVIEW_TIMEOUT_SECONDS",
    "KitConfig",
    "get_kit_root",
    "load_config",
    "validate_config",
]

GATE_EXECUTABLES: tuple[str, ...] = ("git", "pytest", "ruff", "mypy")
REQUIRED_ENV_KEYS: tuple[str, ...] = ()  # Epic 3 adds the Review key names
# Repository-relative POSIX directories (Story 2.2, implementation detail).
INVENTORY_DIR: str = ".beddel-profile/inventory"
RECORDS_DIR: str = ".beddel-profile/records"
# Gate (Story 3.1, implementation detail, owner decision 4). Each command is an
# argv tuple whose argv[0] MUST be in GATE_EXECUTABLES; commands run in the
# target repository root with no shell. The per-command and total budgets are
# independent of any Review budget (AD-18). ``None`` disables the total budget.
GATE_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("ruff", "check", "."),
    ("ruff", "format", "--check", "."),
    ("mypy", "."),
    ("pytest", "-q"),
)
GATE_TIMEOUT_SECONDS: int = 300
GATE_TOTAL_TIMEOUT_SECONDS: int | None = 1200
# Review (Story 3.2, owner decision 3, AD-16, AD-18). The route and the model are
# names resolved from kit config, never hard-coded in a tool. The Review budget
# is independent of the Gate budgets. Names only: no secret is ever configured.
REVIEW_AGENT: str = "kiro"
REVIEW_MODEL: str = "claude-opus-4.5"
REVIEW_TIMEOUT_SECONDS: int = 900

# config key -> module constant name
_KEYS: dict[str, str] = {
    "gate_executables": "GATE_EXECUTABLES",
    "required_env_keys": "REQUIRED_ENV_KEYS",
    "inventory_dir": "INVENTORY_DIR",
    "records_dir": "RECORDS_DIR",
    "gate_commands": "GATE_COMMANDS",
    "gate_timeout_seconds": "GATE_TIMEOUT_SECONDS",
    "gate_total_timeout_seconds": "GATE_TOTAL_TIMEOUT_SECONDS",
    "review_agent": "REVIEW_AGENT",
    "review_model": "REVIEW_MODEL",
    "review_timeout_seconds": "REVIEW_TIMEOUT_SECONDS",
}

_INVALID_MESSAGE = "profile config invalid"
_MAX_TIMEOUT_SECONDS = 86400
# The entry workflow bounds the ``review`` step at a fixed number of seconds; the
# core would cancel the tool before it could record an outcome if the configured
# Review budget (plus the tool's own guard) outlived that step bound.
_MAX_REVIEW_TIMEOUT_SECONDS = 900


@dataclass(frozen=True)
class KitConfig:
    """Validated kit configuration."""

    gate_executables: tuple[str, ...]
    required_env_keys: tuple[str, ...]
    inventory_dir: str
    records_dir: str
    gate_commands: tuple[tuple[str, ...], ...]
    gate_timeout_seconds: int
    gate_total_timeout_seconds: int | None
    review_agent: str
    review_model: str
    review_timeout_seconds: int


def get_kit_root() -> Path:
    """Return the kit root (``python/beddel_profile_dev/config.py`` -> 3 parents up)."""
    return Path(__file__).resolve().parent.parent.parent


def _invalid() -> ProfileError:
    return ProfileError(_CONFIG_INVALID, _INVALID_MESSAGE)


_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# A route or model name: a short token, never a path, a URL or a KEY=value pair.
_ROUTE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def _route_name(value: object) -> str:
    """Return ``value`` if it is a plain route or model name (fail-closed)."""
    if not isinstance(value, str) or not _ROUTE_NAME.fullmatch(value):
        raise _invalid()
    return value


def _string_tuple(value: object, *, env_names: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise _invalid()
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise _invalid()
        # Env key names are echoed in failures; a mistyped KEY=value must not be.
        if env_names and not _ENV_NAME.fullmatch(item):
            raise _invalid()
        items.append(item)
    return tuple(items)


def _relative_posix(value: object) -> str:
    """Return ``value`` if it is a normalized, repository-relative POSIX path."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise _invalid()
    if value.startswith("/") or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise _invalid()
    if any(seg in ("", ".", "..") for seg in value.split("/")):
        raise _invalid()
    return value


def _timeout_seconds(
    value: object, *, optional: bool = False, maximum: int = _MAX_TIMEOUT_SECONDS
) -> int | None:
    """Return a strictly positive whole number of seconds (``None`` only if optional)."""
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid()
    if not 0 < value <= maximum:
        raise _invalid()
    return value


def _gate_commands(
    value: object, executables: tuple[str, ...]
) -> tuple[tuple[str, ...], ...]:
    """Return the validated Gate command list (fail-closed, never empty).

    A malformed list or argv raises ``PROFILE_CONFIG_INVALID``; a well-formed
    argv whose executable is outside ``executables`` (a path form is outside it
    by construction) raises ``PROFILE_GATE_COMMAND_INVALID``. An empty list
    would record an outcome in which no command ran, so it is refused too.
    """
    if not isinstance(value, (list, tuple)) or not value:
        raise _invalid()
    commands: list[tuple[str, ...]] = []
    for index, entry in enumerate(value):
        argv = _string_tuple(entry)
        if not argv or any("\x00" in part for part in argv):
            raise _invalid()
        # A bare executable name only: a path would bypass the allowlist by name.
        if "/" in argv[0] or "\\" in argv[0] or argv[0] not in executables:
            raise ProfileError(
                _GATE_COMMAND_INVALID,
                "gate command executable is not allowed",
                {"index": index},
            )
        commands.append(argv)
    return tuple(commands)


def validate_config(raw: Mapping[str, object]) -> KitConfig:
    """Validate a raw config mapping strictly.

    Raises:
        ProfileError: On unknown keys, missing keys, non-list values, or
            non-string / empty items (``PROFILE_CONFIG_INVALID``); on a Gate
            command outside the executable allowlist
            (``PROFILE_GATE_COMMAND_INVALID``).
    """
    if set(raw) != set(_KEYS):
        raise _invalid()
    gate_executables = _string_tuple(raw["gate_executables"])
    gate_timeout = _timeout_seconds(raw["gate_timeout_seconds"])
    if gate_timeout is None:  # unreachable (not optional); narrows the type
        raise _invalid()
    review_timeout = _timeout_seconds(
        raw["review_timeout_seconds"], maximum=_MAX_REVIEW_TIMEOUT_SECONDS
    )
    if review_timeout is None:  # unreachable (not optional); narrows the type
        raise _invalid()
    return KitConfig(
        gate_executables=gate_executables,
        required_env_keys=_string_tuple(raw["required_env_keys"], env_names=True),
        inventory_dir=_relative_posix(raw["inventory_dir"]),
        records_dir=_relative_posix(raw["records_dir"]),
        gate_commands=_gate_commands(raw["gate_commands"], gate_executables),
        gate_timeout_seconds=gate_timeout,
        gate_total_timeout_seconds=_timeout_seconds(
            raw["gate_total_timeout_seconds"], optional=True
        ),
        review_agent=_route_name(raw["review_agent"]),
        review_model=_route_name(raw["review_model"]),
        review_timeout_seconds=review_timeout,
    )


def load_config() -> KitConfig:
    """Load and validate the kit config from this module's constants."""
    module = sys.modules[__name__]
    # Any other public UPPER_CASE constant is an unknown config key: reject it.
    unknown = [
        name
        for name in vars(module)
        if name.isupper() and not name.startswith("_") and name not in _KEYS.values()
    ]
    if unknown:
        raise _invalid()
    raw: dict[str, object] = {}
    for key, attr in _KEYS.items():
        if not hasattr(module, attr):
            raise _invalid()
        raw[key] = getattr(module, attr)
    return validate_config(raw)
