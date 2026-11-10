"""Pure validation helpers for the profile plan stage."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import yaml

__all__ = [
    "MAX_SIZE_CAP_BYTES",
    "MAX_SPEC_BYTES",
    "STORY_KEY",
    "front_matter",
    "relative_path",
    "spec_complete",
]

STORY_KEY = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_REQUIREMENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
MAX_SIZE_CAP_BYTES = 64000
MAX_SPEC_BYTES = 262144


def front_matter(data: bytes) -> dict[str, Any] | None:
    """Parse the kit-owned YAML front matter contract, or return ``None``."""
    if not data.startswith(b"---\n"):
        return None
    closing = data.find(b"\n---\n", 4)
    if closing < 0:
        return None
    try:
        text = data[4:closing].decode("utf-8")
        value = yaml.safe_load(text)
    except (UnicodeDecodeError, TypeError, ValueError, yaml.YAMLError):
        return None
    return dict(value) if isinstance(value, Mapping) else None


def relative_path(value: object, *, allow_dot: bool = False) -> bool:
    """Return whether ``value`` is a normalized repository-relative POSIX path."""
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    if value == ".":
        return allow_dot
    if value.startswith("/") or any(
        ord(char) < 32 or ord(char) == 127 for char in value
    ):
        return False
    return not any(segment in ("", ".", "..") for segment in value.split("/"))


def _valid_story_key(value: object) -> bool:
    return isinstance(value, str) and STORY_KEY.fullmatch(value) is not None


def spec_complete(data: bytes, story_key: str) -> bool:
    """Return whether bytes satisfy the complete implementation-spec contract."""
    if len(data) > MAX_SPEC_BYTES or not isinstance(story_key, str):
        return False
    metadata = front_matter(data)
    if metadata is None or metadata.get("story_key") != story_key:
        return False
    closing = data.find(b"\n---\n", 4)
    if closing < 0 or not data[closing + len(b"\n---\n") :].strip():
        return False

    requirements = metadata.get("requirements")
    if (
        not isinstance(requirements, list)
        or not requirements
        or not all(
            isinstance(item, str) and _REQUIREMENT_ID.fullmatch(item) is not None
            for item in requirements
        )
    ):
        return False

    repositories = metadata.get("repositories")
    if (
        not isinstance(repositories, list)
        or not repositories
        or not all(
            isinstance(item, str) and relative_path(item, allow_dot=True)
            for item in repositories
        )
    ):
        return False

    dependencies = metadata.get("dependencies")
    if not isinstance(dependencies, list) or not all(
        _valid_story_key(item) for item in dependencies
    ):
        return False

    size_cap = metadata.get("size_cap_bytes")
    return (
        isinstance(size_cap, int)
        and not isinstance(size_cap, bool)
        and 1 <= size_cap <= MAX_SIZE_CAP_BYTES
    )
