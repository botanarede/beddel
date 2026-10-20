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
from beddel_profile_dev._errors import ProfileError

__all__ = [
    "GATE_EXECUTABLES",
    "INVENTORY_DIR",
    "RECORDS_DIR",
    "REQUIRED_ENV_KEYS",
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

# config key -> module constant name
_KEYS: dict[str, str] = {
    "gate_executables": "GATE_EXECUTABLES",
    "required_env_keys": "REQUIRED_ENV_KEYS",
    "inventory_dir": "INVENTORY_DIR",
    "records_dir": "RECORDS_DIR",
}

_INVALID_MESSAGE = "profile config invalid"


@dataclass(frozen=True)
class KitConfig:
    """Validated kit configuration."""

    gate_executables: tuple[str, ...]
    required_env_keys: tuple[str, ...]
    inventory_dir: str
    records_dir: str


def get_kit_root() -> Path:
    """Return the kit root (``python/beddel_profile_dev/config.py`` -> 3 parents up)."""
    return Path(__file__).resolve().parent.parent.parent


def _invalid() -> ProfileError:
    return ProfileError(_CONFIG_INVALID, _INVALID_MESSAGE)


_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


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


def validate_config(raw: Mapping[str, object]) -> KitConfig:
    """Validate a raw config mapping strictly.

    Raises:
        ProfileError: On unknown keys, missing keys, non-list values, or
            non-string / empty items.
    """
    if set(raw) != set(_KEYS):
        raise _invalid()
    return KitConfig(
        gate_executables=_string_tuple(raw["gate_executables"]),
        required_env_keys=_string_tuple(raw["required_env_keys"], env_names=True),
        inventory_dir=_relative_posix(raw["inventory_dir"]),
        records_dir=_relative_posix(raw["records_dir"]),
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
