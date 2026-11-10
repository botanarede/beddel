"""Plan-stage reconciliation and settlement tools."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import (
    PROFILE_PLAN_REFUSED,
    PROFILE_REPOSITORY_INVALID,
    ProfileError,
)
from beddel_profile_dev._io import (
    changed_paths,
    confined,
    real_repo_root,
    resolve_revision,
)
from beddel_profile_dev.plan import (
    STORY_KEY,
    front_matter,
    relative_path,
    spec_complete,
)

__all__ = ["profile_plan_reconcile", "profile_plan_settle"]


def _refuse(reason: str) -> ProfileError:
    return ProfileError(
        PROFILE_PLAN_REFUSED,
        f"plan refused: {reason}",
        {"reason": reason},
    )


def _valid_story_key(value: object) -> bool:
    return isinstance(value, str) and STORY_KEY.fullmatch(value) is not None


def _validate_inputs(
    story_key: object, story_path: object, guide_path: object, spec_path: object
) -> tuple[str, str, str, str]:
    if not _valid_story_key(story_key):
        raise _refuse("story_key.invalid")
    if (
        not all(
            isinstance(value, str) and relative_path(value)
            for value in (story_path, guide_path, spec_path)
        )
        or not isinstance(spec_path, str)
        or len(spec_path) > 512
    ):
        raise _refuse("path.invalid")
    assert isinstance(story_key, str)
    assert isinstance(story_path, str)
    assert isinstance(guide_path, str)
    assert isinstance(spec_path, str)
    return story_key, story_path, guide_path, spec_path


def _read_required(repo: Path, relative: str, reason: str) -> None:
    try:
        path = confined(repo, relative)
        if not path.is_file():
            raise _refuse(reason)
        path.read_bytes()
    except ProfileError as error:
        if error.code == PROFILE_REPOSITORY_INVALID:
            raise _refuse("path.invalid") from error
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise _refuse(reason) from error


def _duplicate_reason(repo: Path, spec_path: str, story_key: str) -> str | None:
    parent = confined(repo, str(Path(spec_path).parent).replace("\\", "/"))
    try:
        if not parent.is_dir():
            return "spec_dir.absent"
        entries = list(parent.iterdir())
        if len(entries) > 10000:
            return "spec.unreadable"
        target = confined(repo, spec_path)
        for entry in entries:
            if (
                entry == target
                or entry.suffix != ".md"
                or entry.is_symlink()
                or not entry.is_file()
            ):
                continue
            try:
                data = entry.read_bytes()
            except (OSError, RuntimeError, ValueError):
                return "spec.unreadable"
            metadata = front_matter(data)
            if metadata is not None and metadata.get("story_key") == story_key:
                return "spec.duplicate"
    except (OSError, RuntimeError, ValueError) as error:
        raise _refuse("spec.unreadable") from error
    return None


def _state(
    repo_path: str,
    story_key: object,
    story_path: object,
    guide_path: object,
    spec_path: object,
) -> dict[str, Any]:
    story, source, guide, spec = _validate_inputs(
        story_key, story_path, guide_path, spec_path
    )
    repo = real_repo_root(repo_path)
    _read_required(repo, source, "story.absent")
    _read_required(repo, guide, "guide.absent")
    try:
        spec_file = confined(repo, spec)
        spec_dir = spec_file.parent
        if not spec_dir.is_dir():
            raise _refuse("spec_dir.absent")
    except ProfileError as error:
        if error.code == PROFILE_REPOSITORY_INVALID:
            raise _refuse("path.invalid") from error
        raise
    except OSError as error:
        raise _refuse("spec.unreadable") from error
    if Path(os.path.realpath(os.getcwd())) != repo:
        raise _refuse("cwd.mismatch")
    dirty = changed_paths(repo)
    if any(path != spec for path in dirty):
        raise _refuse("worktree.dirty")

    try:
        if not spec_file.exists():
            data: bytes | None = None
        elif not spec_file.is_file():
            raise _refuse("spec.unreadable")
        else:
            data = spec_file.read_bytes()
    except OSError as error:
        raise _refuse("spec.unreadable") from error
    if data is not None:
        metadata = front_matter(data)
        if metadata is not None and metadata.get("story_key") not in (None, story):
            raise _refuse("spec.foreign")
    duplicate = _duplicate_reason(repo, spec, story)
    if duplicate is not None:
        raise _refuse(duplicate)
    head = resolve_revision(repo, "HEAD")
    complete = data is not None and spec_complete(data, story)
    return {
        "story_key": story,
        "spec_path": spec,
        "head": head,
        "state": "complete"
        if complete
        else ("incomplete" if data is not None else "absent"),
        "spec_sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
        "author": not complete,
    }


def _refs(
    spec_path: str | None,
    spec_sha256: str | None,
    revision: str | None,
    out_of_scope: int = 0,
) -> dict[str, Any]:
    return {
        "spec_path": spec_path,
        "spec_sha256": spec_sha256,
        "revision": revision,
        "out_of_scope": out_of_scope,
    }


def _result(
    story_key: str | None,
    outcome: str,
    reason: str,
    *,
    spec_path: str | None,
    spec_sha256: str | None,
    revision: str | None,
    out_of_scope: int = 0,
) -> dict[str, Any]:
    return {
        "stage": "plan",
        "story_key": story_key,
        "outcome": outcome,
        "reason": reason,
        "refs": _refs(spec_path, spec_sha256, revision, out_of_scope),
    }


@beddel_tool(
    name="profile_plan_reconcile",
    description="Reconcile one selected story with exactly one implementation spec",
    category="profile",
)
def profile_plan_reconcile(
    repo_path: str,
    story_key: str,
    story_path: str,
    guide_path: str,
    spec_path: str,
) -> dict[str, Any]:
    """Validate plan inputs and report whether the Coding agent must author."""
    return _state(repo_path, story_key, story_path, guide_path, spec_path)


def _mapping_matches(
    reconcile: Mapping[str, Any],
    story_key: str,
    spec_path: str,
) -> bool:
    return (
        reconcile.get("story_key") == story_key
        and reconcile.get("spec_path") == spec_path
        and isinstance(reconcile.get("head"), str)
        and reconcile.get("state") in {"absent", "incomplete", "complete"}
        and (
            isinstance(reconcile.get("spec_sha256"), str)
            or reconcile.get("spec_sha256") is None
        )
        and reconcile.get("author") is (reconcile.get("state") != "complete")
    )


def _settle_current(
    repo: Path, story_key: str, spec_path: str
) -> tuple[str, bytes | None, int]:
    current = changed_paths(repo)
    extras = current - {spec_path}
    if extras:
        return "scope.exceeded", None, len(extras)
    try:
        spec_file = confined(repo, spec_path)
        if not spec_file.is_file():
            return "spec.incomplete", None, 0
        data = spec_file.read_bytes()
    except (OSError, ProfileError, RuntimeError, ValueError):
        return "spec.incomplete", None, 0
    try:
        duplicate = _duplicate_reason(repo, spec_path, story_key)
    except ProfileError as error:
        # After the agent ran, an unreadable scan is a failure, not a refusal.
        duplicate = str(error.details.get("reason", "spec.unreadable"))
    if duplicate is not None:
        return duplicate, data, 0
    if not spec_complete(data, story_key):
        return "spec.incomplete", data, 0
    return "ok", data, 0


@beddel_tool(
    name="profile_plan_settle",
    description="Settle a plan stage without writing or committing the spec",
    category="profile",
)
def profile_plan_settle(
    repo_path: str,
    story_key: str,
    story_path: str,
    guide_path: str,
    spec_path: str,
    reconcile: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Derive a success, refusal, or failure outcome from the settled work tree."""
    valid_story = story_key if _valid_story_key(story_key) else None
    valid_spec = (
        spec_path
        if isinstance(spec_path, str)
        and len(spec_path) <= 512
        and relative_path(spec_path)
        else None
    )
    try:
        story, _source, _guide, spec = _validate_inputs(
            story_key, story_path, guide_path, spec_path
        )
        repo = real_repo_root(repo_path)
        current_head = resolve_revision(repo, "HEAD")
        if reconcile is None:
            try:
                state = _state(repo_path, story, story_path, guide_path, spec)
            except ProfileError as error:
                reason = str(error.details.get("reason", "reconcile.failed"))
                return _result(
                    valid_story,
                    "refused",
                    reason,
                    spec_path=valid_spec,
                    spec_sha256=None,
                    revision=current_head,
                )
            return _result(
                story,
                "failed",
                "reconcile.failed",
                spec_path=spec,
                spec_sha256=state["spec_sha256"],
                revision=state["head"],
            )
        if not isinstance(reconcile, Mapping) or not _mapping_matches(
            reconcile, story, spec
        ):
            return _result(
                valid_story,
                "failed",
                "reconcile.mismatch",
                spec_path=valid_spec,
                spec_sha256=None,
                revision=current_head,
            )
        if current_head != reconcile.get("head"):
            return _result(
                story,
                "failed",
                "head.moved",
                spec_path=spec,
                spec_sha256=None,
                revision=current_head,
            )
        initial_sha = reconcile.get("spec_sha256")
        settle_state, data, out_of_scope = _settle_current(repo, story, spec)
        if settle_state == "scope.exceeded":
            return _result(
                story,
                "failed",
                settle_state,
                spec_path=spec,
                spec_sha256=None,
                revision=current_head,
                out_of_scope=out_of_scope,
            )
        if settle_state != "ok":
            return _result(
                story,
                "failed",
                settle_state,
                spec_path=spec,
                spec_sha256=hashlib.sha256(data).hexdigest()
                if data is not None
                else None,
                revision=current_head,
            )
        assert data is not None
        digest = hashlib.sha256(data).hexdigest()
        if reconcile.get("state") == "complete" and digest != initial_sha:
            return _result(
                story,
                "failed",
                "spec.changed",
                spec_path=spec,
                spec_sha256=digest,
                revision=current_head,
            )
        return _result(
            story,
            "succeeded",
            {
                "absent": "spec.created",
                "incomplete": "spec.reconciled",
                "complete": "spec.reused",
            }[str(reconcile["state"])],
            spec_path=spec,
            spec_sha256=digest,
            revision=current_head,
        )
    except ProfileError as error:
        reason = str(error.details.get("reason", "reconcile.failed"))
        return _result(
            valid_story,
            "refused" if error.code == PROFILE_PLAN_REFUSED else "failed",
            reason,
            spec_path=valid_spec,
            spec_sha256=None,
            revision=None,
        )
