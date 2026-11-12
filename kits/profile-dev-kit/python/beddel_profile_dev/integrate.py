"""Pure helpers for the integration stage."""

from __future__ import annotations

import re

from beddel_profile_dev.implement import STORY_TRAILER

APPROVALS_DIR = ".beddel-profile/approvals/"
REMOTE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
STATUS_VALUE = re.compile(r"[a-z][a-z0-9-]{0,31}")
MAX_STATUS_BYTES = 1048576
MERGE_TRAILER = "Integrate-Merge"


def approved_only(paths: list[str] | tuple[str, ...] | set[str]) -> bool:
    """Return whether every changed path belongs to the approval directory."""
    return all(path.startswith(APPROVALS_DIR) for path in paths)


def _matching(data: bytes, key: str) -> list[tuple[int, str, str]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []
    pattern = re.compile(rf"^[ \t]*{re.escape(key)}:[ \t]*[^\s#]*[ \t]*(#.*)?$")
    matches: list[tuple[int, str, str]] = []
    for index, raw in enumerate(text.splitlines(keepends=True)):
        line = raw.rstrip("\r\n")
        match = pattern.fullmatch(line)
        if match is not None:
            value_match = re.search(r":([ \t]*)([^\s#]+)", line)
            if value_match is not None:
                matches.append((index, line, value_match.group(2)))
    return matches


def status_lines(data: bytes, key: str) -> list[int]:
    """Return line indexes containing exactly one valid status mapping."""
    return [index for index, _line, _value in _matching(data, key)]


def status_value(data: bytes, key: str) -> str | None:
    """Return the status value when the requested key occurs exactly once."""
    matches = _matching(data, key)
    return matches[0][2] if len(matches) == 1 else None


def set_status(data: bytes, key: str, value: str) -> bytes | None:
    """Replace one status token without changing any other file bytes."""
    matches = _matching(data, key)
    if len(matches) != 1:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    lines = text.splitlines(keepends=True)
    index, line, _old = matches[0]
    match = re.match(
        rf"^(?P<prefix>[ \t]*{re.escape(key)}:[ \t]*)[^\s#]+(?P<suffix>.*)$", line
    )
    if match is None or not STATUS_VALUE.fullmatch(value):
        return None
    lines[index] = (
        f"{match.group('prefix')}{value}{match.group('suffix')}"
        + lines[index][len(line) :]
    )
    return "".join(lines).encode("utf-8")


def pointer_message(story_key: str, sub_path: str, merge: str) -> tuple[str, str]:
    """Return the pointer commit subject and its identity trailers."""
    return (
        f"chore: update {sub_path} pointer",
        f"{STORY_TRAILER}: {story_key}\n{MERGE_TRAILER}: {merge}",
    )
