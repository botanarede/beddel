"""Validation for profile delivery method files."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import yaml

from beddel_profile_dev.implement import branch_reason
from beddel_profile_dev.plan import relative_path
from beddel_profile_dev.tools.stage_outcome import _TOKEN

METHOD_FILE = ".beddel-profile/method.yaml"
METHOD_SCHEMA = "profile-dev/method/1"
STAGE_KEYS = ("plan", "implement", "fix")
MAX_INSTRUCTION_BYTES = 2000
MAX_METHOD_BYTES = 65536
METHOD_NAME = re.compile(r"[a-z][a-z0-9-]{0,31}")
_REMOTE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,63}")
_INPUT_KEYS = (
    "story_path",
    "guide_path",
    "spec_path",
    "status_path",
    "branch",
    "remote",
    "base_branch",
)


def _valid_text(value: object) -> bool:
    return isinstance(value, str) and not any(
        unicodedata.category(char) in {"Cc", "Zl", "Zp"} for char in value
    )


def valid_instruction(text: object) -> bool:
    """Return whether a stage instruction is safe to pass through resolution."""
    if not isinstance(text, str):
        return False
    try:
        size = len(text.encode("utf-8"))
    except UnicodeError:
        return False
    return (
        1 <= size <= MAX_INSTRUCTION_BYTES
        and _valid_text(text)
        and "$" not in text
        and _TOKEN.search(text) is None
    )


def _valid_template(value: object) -> bool:
    if not isinstance(value, str) or not _valid_text(value):
        return False
    if "{" in value or "}" in value:
        remainder = value.replace("{story_key}", "")
        if "{" in remainder or "}" in remainder:
            return False
    return True


def _rendered_input_valid(key: str, value: object) -> bool:
    if not isinstance(value, str) or not _valid_template(value):
        return False
    rendered = value.replace("{story_key}", "story-key")
    if key in {"story_path", "guide_path", "spec_path"}:
        return relative_path(rendered)
    if key == "status_path":
        return rendered == "" or relative_path(rendered)
    if key == "branch":
        return _valid_text(value)
    return _REMOTE_NAME.fullmatch(rendered) is not None and ".." not in rendered


def load_method(data: bytes) -> dict[str, Any] | None:
    """Parse and validate one committed method file."""
    if not isinstance(data, bytes) or len(data) > MAX_METHOD_BYTES:
        return None
    try:
        value = yaml.safe_load(data)
    except (UnicodeDecodeError, TypeError, ValueError, RecursionError, yaml.YAMLError):
        return None
    if not isinstance(value, dict) or set(value) != {"schema", "inputs", "methods"}:
        return None
    if value.get("schema") != METHOD_SCHEMA:
        return None
    inputs = value.get("inputs")
    methods = value.get("methods")
    if not isinstance(inputs, dict) or set(inputs) != set(_INPUT_KEYS):
        return None
    if not isinstance(methods, dict):
        return None
    if not all(_rendered_input_valid(key, inputs[key]) for key in _INPUT_KEYS):
        return None
    rendered_base = str(inputs["base_branch"]).replace("{story_key}", "story-key")
    rendered_branch = str(inputs["branch"]).replace("{story_key}", "story-key")
    if branch_reason(rendered_branch, rendered_base) is not None:
        return None
    for name, method in methods.items():
        if (
            not isinstance(name, str)
            or METHOD_NAME.fullmatch(name) is None
            or name == "native"
        ):
            return None
        if not isinstance(method, dict) or set(method) != set(STAGE_KEYS):
            return None
        if not all(valid_instruction(method[key]) for key in STAGE_KEYS):
            return None
    return value
