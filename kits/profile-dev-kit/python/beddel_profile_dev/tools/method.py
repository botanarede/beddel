"""Tools for deriving and applying profile delivery methods."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from beddel.tools import beddel_tool

from beddel_profile_dev._errors import PROFILE_CONFIG_INVALID, ProfileError
from beddel_profile_dev._io import (
    blob_at,
    git_run,
    real_repo_root,
    records_root,
    resolve_revision,
)
from beddel_profile_dev.config import load_config
from beddel_profile_dev.implement import branch_reason
from beddel_profile_dev.integrate import APPROVALS_DIR
from beddel_profile_dev.inventory import is_valid_id
from beddel_profile_dev.method import (
    METHOD_FILE,
    METHOD_NAME,
    _rendered_input_valid,
    load_method,
    render,
    valid_instruction,
)
from beddel_profile_dev.tools.deliver import _records, _refs
from beddel_profile_dev.tools.implement import _git_text, _valid_story
from beddel_profile_dev.tools.ratify import valid_actor

__all__ = [
    "profile_deliver_derive",
    "profile_deliver_method",
    "profile_stage_instruction",
]

_FULL_SHA = re.compile(r"[0-9a-f]{40}")
_RECORD_PATH = re.compile(r"\.beddel-profile/approvals/[^/]+/([1-9][0-9]*)\.yaml")


def _refusal(story_key: str | None, reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "story_key": story_key,
        "reason": reason,
        "refs": _refs(request="all", stage="start", stage_reason=reason),
    }


def _tree_paths(repo: Path, prefix: str) -> list[str] | None:
    result = git_run(repo, "ls-tree", "-r", "--name-only", "HEAD", "--", prefix)
    if result is None or result.returncode != 0:
        return None
    text = _git_text(result)
    return text.splitlines() if text else []


def _inventory_version(repo: Path, inventory_dir: str) -> str | None:
    paths = _tree_paths(repo, inventory_dir)
    if paths is None:
        return None
    versions: set[str] = set()
    for path in paths:
        if not path.startswith(inventory_dir + "/"):
            continue
        name = path.rsplit("/", 1)[-1]
        if path != f"{inventory_dir}/{name}":
            continue
        if not name.endswith(".yaml") or name.endswith(".ratification.yaml"):
            continue
        version = name[:-5]
        if (
            is_valid_id(version)
            and f"{inventory_dir}/{version}.ratification.yaml" in paths
        ):
            versions.add(version)
    if len(versions) != 1:
        return "__absent__" if not versions else "__ambiguous__"
    return next(iter(versions))


def _actor(repo: Path, story_key: str) -> str | None:
    paths = _tree_paths(repo, f"{APPROVALS_DIR}{story_key}")
    latest: tuple[int, str] | None = None
    for path in paths or []:
        match = _RECORD_PATH.fullmatch(path)
        if match is None or f"/{story_key}/" not in path:
            continue
        number = int(match.group(1))
        if latest is None or number > latest[0]:
            latest = (number, path)
    if latest is not None:
        data = blob_at(repo, "HEAD", latest[1])
        try:
            value = yaml.safe_load(data) if data is not None else None
        except (TypeError, ValueError, yaml.YAMLError, RecursionError):
            value = None
        approved = value.get("approved_by") if isinstance(value, Mapping) else None
        if isinstance(approved, str) and valid_actor(approved):
            return approved
    return _git_text(git_run(repo, "config", "--get", "user.name"))


def _parent(repo: Path) -> tuple[str, str]:
    parent = (
        _git_text(git_run(repo, "rev-parse", "--show-superproject-working-tree")) or ""
    )
    if not parent:
        return "", ""
    branch = _git_text(git_run(Path(parent), "symbolic-ref", "--short", "HEAD")) or ""
    return parent, branch


def _base_ref(
    repo: Path, story_key: str, remote: str, base_branch: str
) -> tuple[str | None, str | None]:
    try:
        root = records_root(repo, load_config().records_dir)
        records = _records(root)
    except ProfileError:
        return None, "records.unreadable"
    for record in reversed(records):
        if record.get("story_key") != story_key or record.get("stage") not in {
            "implement",
            "verify-and-fix",
        }:
            continue
        refs = record.get("refs")
        base = refs.get("base") if isinstance(refs, Mapping) else None
        if isinstance(base, str) and _FULL_SHA.fullmatch(base):
            return base, None
        break
    try:
        return resolve_revision(repo, f"refs/remotes/{remote}/{base_branch}"), None
    except ProfileError:
        return None, "base.unknown"


def _method_data(repo: Path) -> dict[str, Any] | None:
    data = blob_at(repo, "HEAD", METHOD_FILE)
    return load_method(data) if data is not None else None


def _derive_inputs(
    repo: Path, story_key: str, chosen: str, data: dict[str, Any]
) -> dict[str, Any] | dict[str, str]:
    inputs = data["inputs"]
    rendered = {key: render(inputs[key], story_key) for key in inputs}
    if (
        any(not _rendered_input_valid(key, rendered[key]) for key in rendered)
        or branch_reason(rendered["branch"], rendered["base_branch"]) is not None
    ):
        return {"error": "method.invalid"}
    remote, base_branch = rendered["remote"], rendered["base_branch"]
    base_ref, error = _base_ref(repo, story_key, remote, base_branch)
    if error:
        return {"error": error}
    if base_ref is None:
        return {"error": "base.unknown"}
    change_id = story_key
    if not is_valid_id(change_id):
        return {"error": "change_id.invalid"}
    inventory = _inventory_version(repo, load_config().inventory_dir)
    if inventory == "__absent__":
        return {"error": "inventory.absent"}
    if inventory == "__ambiguous__" or inventory is None:
        return {"error": "inventory.ambiguous" if inventory else "records.unreadable"}
    actor = _actor(repo, story_key)
    if not valid_actor(actor):
        return {"error": "actor.unknown"}
    parent_path, parent_branch = _parent(repo)
    values: dict[str, Any] = {
        "repo_path": str(repo),
        "story_key": story_key,
        "stage": "all",
        "story_path": rendered["story_path"],
        "guide_path": rendered["guide_path"],
        "spec_path": rendered["spec_path"],
        "branch": rendered["branch"],
        "base_ref": base_ref,
        "change_id": change_id,
        "inventory_version": inventory,
        "actor": actor,
        "base_branch": base_branch,
        "remote": remote,
        "parent_path": parent_path,
        "parent_branch": parent_branch,
        "status_path": rendered["status_path"],
        "method": chosen,
    }
    return values


@beddel_tool(
    name="profile_deliver_derive",
    description="Derive the complete three-input Delivery request from committed repository state",
    category="profile",
)
def profile_deliver_derive(
    repo_path: str, story_key: str, method: str
) -> dict[str, Any]:
    try:
        repo = real_repo_root(repo_path)
    except ProfileError:
        return _refusal(None, "base.unknown")
    if not _valid_story(story_key):
        # An invalid key cannot name a record, so the refusal carries none.
        return _refusal(None, "story_key.invalid")
    if not isinstance(method, str):
        return _refusal(story_key, "method.invalid")
    chosen = "native" if method in ("", "native") else method
    if chosen != "native" and METHOD_NAME.fullmatch(chosen) is None:
        return _refusal(story_key, "method.invalid")
    data = _method_data(repo)
    if data is None:
        return _refusal(
            story_key,
            "method.absent"
            if blob_at(repo, "HEAD", METHOD_FILE) is None
            else "method.invalid",
        )
    if chosen != "native" and chosen not in data["methods"]:
        return _refusal(story_key, "method.unknown")
    values = _derive_inputs(repo, story_key, chosen, data)
    if "error" in values:
        return _refusal(story_key, values["error"])
    return {"ok": True, "method": chosen, "inputs": values}


def _config_error(reason: str) -> ProfileError:
    return ProfileError(PROFILE_CONFIG_INVALID, "method invalid", {"reason": reason})


@beddel_tool(
    name="profile_deliver_method",
    description="Read one committed delivery method and expose its neutral stage instructions",
    category="profile",
)
def profile_deliver_method(repo_path: str, method: str) -> dict[str, Any]:
    repo = real_repo_root(repo_path)
    if method in ("", "native"):
        return {
            "method": "native",
            "method_sha256": None,
            "plan": "",
            "implement": "",
            "fix": "",
        }
    if not isinstance(method, str) or METHOD_NAME.fullmatch(method) is None:
        raise _config_error("method.invalid")
    raw = blob_at(repo, "HEAD", METHOD_FILE)
    data = load_method(raw) if raw is not None else None
    if data is None:
        raise _config_error("method.invalid" if raw is not None else "method.absent")
    selected = data["methods"].get(method)
    if not isinstance(selected, Mapping):
        raise _config_error("method.unknown")
    return {
        "method": method,
        "method_sha256": hashlib.sha256(raw or b"").hexdigest(),
        "plan": selected["plan"],
        "implement": selected["implement"],
        "fix": selected["fix"],
    }


@beddel_tool(
    name="profile_stage_instruction",
    description="Validate a neutral instruction before it reaches a Coding agent",
    category="profile",
)
def profile_stage_instruction(stage: str, instruction: str) -> dict[str, Any]:
    if stage not in {"plan", "implement", "verify-and-fix"}:
        raise _config_error("stage.invalid")
    if not valid_instruction(instruction):
        raise _config_error("instruction.invalid")
    return {
        "stage": stage,
        "instruction": instruction,
        "instruction_sha256": hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
    }
