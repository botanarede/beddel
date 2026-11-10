"""Prepare and settle one implementation unit on a feature branch."""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import ProfileError
from beddel_profile_dev._io import (
    changed_paths,
    confined,
    diff_text,
    git_run,
    real_repo_root,
    resolve_revision,
)
from beddel_profile_dev.config import KitConfig, load_config
from beddel_profile_dev.implement import (
    branch_reason,
    commit_message,
    covered,
    spec_units,
    trailer_unit,
)
from beddel_profile_dev.plan import (
    STORY_KEY,
    front_matter,
    relative_path,
    spec_complete,
)
from beddel_profile_dev.tools._subprocess import resolve_executable, run_command
from beddel_profile_dev.tools.stage_outcome import _TOKEN

__all__ = ["profile_implement_prepare", "profile_implement_settle"]

_MAX_BASE_REF = 200


def _valid_story(value: object) -> bool:
    return isinstance(value, str) and STORY_KEY.fullmatch(value) is not None


def _valid_base(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= _MAX_BASE_REF
        and not value.startswith("-")
        and not any(ord(char) < 32 or ord(char) == 127 for char in value)
    )


def _refs(
    *,
    spec_path: str | None = None,
    spec_sha256: str | None = None,
    branch: str | None = None,
    base: str | None = None,
    head: str | None = None,
    commit: str | None = None,
    unit: str | None = None,
    completed: int = 0,
    remaining: int = 0,
    diff_bytes: int | None = None,
    out_of_scope: int = 0,
    regressed: str | None = None,
) -> dict[str, Any]:
    return {
        "spec_path": spec_path,
        "spec_sha256": spec_sha256,
        "branch": branch,
        "base": base,
        "head": head,
        "commit": commit,
        "unit": unit,
        "completed": completed,
        "remaining": remaining,
        "diff_bytes": diff_bytes,
        "out_of_scope": out_of_scope,
        "regressed": regressed,
    }


# fmt: off
def _state(spec, digest=None, branch=None, base=None, head=None, unit=None, **extra):
    return _refs(spec_path=spec, spec_sha256=digest, branch=branch, base=base, head=head, unit=unit, **extra)
# fmt: on


def _result(
    story_key: str | None,
    outcome: str | None,
    reason: str | None,
    refs: dict[str, Any],
    *,
    ready: bool = False,
    implement: bool = False,
    spec_sha256: str | None = None,
    base: str | None = None,
    head: str | None = None,
    unit_id: str | None = None,
    unit_paths: str = "",
    baseline: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "stage": "implement",
        "story_key": story_key,
        "ready": ready,
        "implement": implement,
        "outcome": outcome,
        "reason": reason,
        "refs": refs,
        "spec_sha256": spec_sha256,
        "base": base,
        "head": head,
        "unit_id": unit_id,
        "unit_paths": unit_paths,
        "baseline": baseline,
    }


def _refusal(
    story_key: str | None,
    reason: str,
    *,
    spec_path: str | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    return _result(
        story_key,
        "refused",
        reason,
        _refs(spec_path=spec_path, branch=branch),
    )


def _failure(
    story_key: str | None,
    reason: str,
    refs: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    return _result(story_key, "failed", reason, refs, **kwargs)


# fmt: off
def _fail(story, reason, spec, digest=None, branch=None, base=None, head=None, unit=None, **extra):
    return _failure(story, reason, _state(spec, digest, branch, base, head, unit, **extra))
# fmt: on


def _read_spec(repo: Path, spec_path: str) -> tuple[bytes | None, str | None]:
    try:
        path = confined(repo, spec_path)
        if not path.exists():
            return None, "spec.absent"
        if not path.is_file():
            return None, "spec.unreadable"
        return path.read_bytes(), None
    except (OSError, ProfileError, RuntimeError, ValueError):
        return None, "spec.unreadable"


def _git_text(result: Any) -> str | None:
    if result is None or result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", "replace").strip()


def _symbolic_branch(repo: Path) -> str | None:
    value = _git_text(git_run(repo, "symbolic-ref", "-q", "HEAD"))
    return value.removeprefix("refs/heads/") if value is not None else None


def _completed(repo: Path, base: str, story_key: str) -> set[str]:
    result = git_run(repo, "log", "-z", "--reverse", "--format=%H%n%B", f"{base}..HEAD")
    if result is None or result.returncode != 0:
        raise ProfileError(
            "PROFILE_REPOSITORY_INVALID", "repository or revision invalid"
        )
    completed: set[str] = set()
    for raw in result.stdout.split(b"\x00"):
        if not raw:
            continue
        message = raw.decode("utf-8", "replace")
        unit_id = trailer_unit(message, story_key)
        if unit_id is not None:
            completed.add(unit_id)
    return completed


def _run_gates(repo: Path, config: KitConfig) -> list[dict[str, Any]]:
    started_at = time.monotonic()
    results: list[dict[str, Any]] = []
    for index, argv in enumerate(config.gate_commands, start=1):
        remaining = (
            None
            if config.gate_total_timeout_seconds is None
            else config.gate_total_timeout_seconds - (time.monotonic() - started_at)
        )
        timed_out = remaining is not None and remaining <= 0
        if timed_out:
            exit_code = None
        else:
            timeout = (
                config.gate_timeout_seconds
                if remaining is None
                else min(config.gate_timeout_seconds, max(remaining, 0.0))
            )
            command = run_command(argv, repo, timeout)
            if not command.started:
                raise ProfileError(
                    "PROFILE_GATE_COMMAND_INVALID",
                    "gate command executable is not available",
                )
            exit_code = command.exit_code
            timed_out = command.timed_out
        results.append(
            {
                "name": f"{index:02d}-{argv[0]}",
                "exit_code": exit_code,
                "timed_out": timed_out,
            }
        )
    return results


def _candidate_tree(repo: Path, paths: tuple[str, ...]) -> str:
    with tempfile.TemporaryDirectory() as directory:
        index = Path(directory) / "index"
        for args in (("read-tree", "HEAD"), ("add", "-A", "--", *paths)):
            result = git_run(repo, *args, index_file=index)
            if result is None or result.returncode != 0:
                raise ProfileError(
                    "PROFILE_REPOSITORY_INVALID", "repository or revision invalid"
                )
        result = git_run(repo, "write-tree", index_file=index)
        value = _git_text(result)
        if value is None:
            raise ProfileError(
                "PROFILE_REPOSITORY_INVALID", "repository or revision invalid"
            )
        return value


def _validate_inputs(
    repo_path: str,
    story_key: object,
    spec_path: object,
    branch: object,
    base_ref: object,
) -> tuple[Path, str, str, str, str] | dict[str, Any]:
    valid_story: str | None = None
    if isinstance(story_key, str) and _valid_story(story_key):
        valid_story = story_key
    valid_spec: str | None = None
    if (
        isinstance(spec_path, str)
        and len(spec_path) <= 512
        and relative_path(spec_path)
    ):
        valid_spec = spec_path
    valid_branch: str | None = None
    if isinstance(branch, str) and len(branch) <= 128:
        valid_branch = branch
    if valid_story is None:
        return _refusal(
            None, "story_key.invalid", spec_path=valid_spec, branch=valid_branch
        )
    if (
        valid_spec is None
        or not isinstance(branch, str)
        or branch_reason(branch, base_ref) == "branch.invalid"
    ):
        return _refusal(
            valid_story,
            "path.invalid" if valid_spec is None else "branch.invalid",
            spec_path=valid_spec,
            branch=valid_branch,
        )
    branch_error = branch_reason(branch, base_ref)
    if branch_error is not None:
        return _refusal(valid_story, branch_error, spec_path=valid_spec, branch=branch)
    if not _valid_base(base_ref):
        return _refusal(
            valid_story, "base.invalid", spec_path=valid_spec, branch=branch
        )
    repo = real_repo_root(repo_path)
    assert isinstance(base_ref, str)
    return repo, valid_story, valid_spec, branch, base_ref


@beddel_tool(
    name="profile_implement_prepare",
    description="Prepare one implementation unit on a feature branch",
    category="profile",
)
def profile_implement_prepare(
    repo_path: str,
    story_key: str,
    spec_path: str,
    branch: str,
    base_ref: str,
) -> dict[str, Any]:
    """Validate state, create or reuse the branch, and run baseline gates."""
    checked = _validate_inputs(repo_path, story_key, spec_path, branch, base_ref)
    if isinstance(checked, dict):
        return checked
    repo, story, spec, branch_name, base = checked
    try:
        base_sha = resolve_revision(repo, base)
    except ProfileError:
        return _refusal(story, "base.invalid", spec_path=spec, branch=branch_name)
    if Path(os.path.realpath(os.getcwd())) != repo:
        return _refusal(story, "cwd.mismatch", spec_path=spec, branch=branch_name)
    data, error = _read_spec(repo, spec)
    if error == "spec.absent":
        return _refusal(story, error, spec_path=spec, branch=branch_name)
    if error is not None or data is None:
        return _refusal(
            story, error or "spec.unreadable", spec_path=spec, branch=branch_name
        )
    if not spec_complete(data, story):
        return _refusal(story, "spec.incomplete", spec_path=spec, branch=branch_name)
    units = spec_units(data, story)
    if units is None:
        return _refusal(story, "units.invalid", spec_path=spec, branch=branch_name)
    try:
        config = load_config()
        for argv in config.gate_commands:
            if resolve_executable(argv[0]) is None:
                return _refusal(
                    story, "gate.unavailable", spec_path=spec, branch=branch_name
                )
    except ProfileError:
        return _failure(story, "prepare.failed", _state(spec, branch=branch_name))
    dirty = changed_paths(repo) - {spec}
    if dirty:
        return _failure(story, "worktree.dirty", _state(spec, branch=branch_name))

    ref = git_run(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}")
    if ref is None or ref.returncode not in (0, 1):
        raise ProfileError(
            "PROFILE_REPOSITORY_INVALID", "repository or revision invalid"
        )
    if ref.returncode == 0:
        tip = resolve_revision(repo, f"refs/heads/{branch_name}")
        merge = git_run(repo, "merge-base", base_sha, tip)
        merge_sha = _git_text(merge)
        if merge_sha is None:
            return _refusal(story, "base.invalid", spec_path=spec, branch=branch_name)
        base_sha = merge_sha
        if _symbolic_branch(repo) != branch_name:
            switched = git_run(repo, "switch", "-q", branch_name)
            if switched is None or switched.returncode != 0:
                return _failure(
                    story, "checkout.failed", _state(spec, branch=branch_name)
                )
    else:
        switched = git_run(repo, "switch", "-q", "-c", branch_name, base_sha)
        if switched is None or switched.returncode != 0:
            return _failure(
                story,
                "checkout.failed",
                _refs(spec_path=spec, branch=branch_name, base=base_sha),
            )

    after_data, after_error = _read_spec(repo, spec)
    if after_error is not None or after_data != data or (changed_paths(repo) - {spec}):
        return _failure(
            story,
            "checkout.failed",
            _refs(
                spec_path=spec,
                spec_sha256=hashlib.sha256(after_data).hexdigest()
                if after_data is not None
                else None,
                branch=branch_name,
                base=base_sha,
                head=resolve_revision(repo, "HEAD"),
            ),
        )
    head = resolve_revision(repo, "HEAD")
    completed = _completed(repo, base_sha, story)
    remaining = [unit for unit in units if unit.id not in completed]
    if not remaining:
        return _result(
            story,
            "succeeded",
            "units.complete",
            _refs(
                spec_path=spec,
                spec_sha256=hashlib.sha256(data).hexdigest(),
                branch=branch_name,
                base=base_sha,
                head=head,
                completed=len(units),
                remaining=0,
            ),
            spec_sha256=hashlib.sha256(data).hexdigest(),
            base=base_sha,
            head=head,
        )
    unit = remaining[0]
    try:
        baseline = _run_gates(repo, config)
    except ProfileError:
        return _failure(
            story,
            "prepare.failed",
            _refs(
                spec_path=spec,
                spec_sha256=hashlib.sha256(data).hexdigest(),
                branch=branch_name,
                base=base_sha,
                head=head,
                unit=unit.id,
            ),
        )
    if changed_paths(repo) - {spec}:
        return _failure(
            story,
            "gate.changed_tree",
            _refs(
                spec_path=spec,
                spec_sha256=hashlib.sha256(data).hexdigest(),
                branch=branch_name,
                base=base_sha,
                head=head,
                unit=unit.id,
            ),
        )
    return _result(
        story,
        None,
        None,
        _refs(
            spec_path=spec,
            spec_sha256=hashlib.sha256(data).hexdigest(),
            branch=branch_name,
            base=base_sha,
            head=head,
            unit=unit.id,
            completed=len(completed),
            remaining=len(remaining),
        ),
        ready=True,
        implement=True,
        spec_sha256=hashlib.sha256(data).hexdigest(),
        base=base_sha,
        head=head,
        unit_id=unit.id,
        unit_paths=", ".join(unit.paths),
        baseline=baseline,
    )


# fmt: off
@beddel_tool(
    name="profile_implement_settle",
    description="Review and commit one implementation unit",
    category="profile",
)
def profile_implement_settle(
    repo_path: str,
    story_key: str,
    spec_path: str,
    branch: str,
    base_ref: str,
    prepare: Mapping[str, Any] | None,
    agent: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Settle the prepared unit, committing only its declared paths."""
    checked = _validate_inputs(repo_path, story_key, spec_path, branch, base_ref)
    if isinstance(checked, dict):
        return checked
    repo, story, spec, branch_name, _base_ref = checked
    if prepare is None:
        return _fail(story, "prepare.failed", spec, branch=branch_name)
    if not isinstance(prepare, Mapping):
        return _fail(story, "prepare.mismatch", spec, branch=branch_name)
    if prepare.get("story_key") != story or prepare.get("stage") != "implement":
        return _fail(story, "prepare.mismatch", spec, branch=branch_name)
    if prepare.get("implement") is not True:
        return _result(
            story,
            prepare.get("outcome"),
            prepare.get("reason"),
            prepare.get("refs", _state(spec, branch=branch_name)),
        )
    if not isinstance(agent, Mapping):
        return _fail(story, "agent.failed", spec, branch=branch_name)
    base = prepare.get("base")
    head = resolve_revision(repo, "HEAD")
    if _symbolic_branch(repo) != branch_name:
        return _fail(
            story, "branch.moved", spec, branch=branch_name,
            base=base if isinstance(base, str) else None, head=head,
        )
    if head != prepare.get("head"):
        return _fail(
            story, "head.moved", spec, branch=branch_name,
            base=base if isinstance(base, str) else None, head=head,
        )
    if not isinstance(base, str):
        return _fail(story, "prepare.mismatch", spec, branch=branch_name, head=head)
    data, error = _read_spec(repo, spec)
    if error is not None or data is None:
        return _fail(story, "spec.changed", spec, branch=branch_name, base=base, head=head)
    units = spec_units(data, story)
    if units is None:
        return _fail(story, "spec.changed", spec, branch=branch_name, base=base, head=head)
    spec_digest = hashlib.sha256(data).hexdigest()
    if prepare.get("spec_sha256") != spec_digest:
        return _fail(story, "spec.changed", spec, spec_digest, branch_name, base, head)
    unit_id = prepare.get("unit_id")
    unit = next((item for item in units if item.id == unit_id), None)
    if unit is None or prepare.get("unit_paths") != ", ".join(unit.paths):
        return _fail(story, "prepare.mismatch", spec, spec_digest, branch_name, base, head)
    try:
        config = load_config()
        names = [f"{i:02d}-{argv[0]}" for i, argv in enumerate(config.gate_commands, 1)]
        baseline = prepare.get("baseline")
        if (
            not isinstance(baseline, list)
            or any(not isinstance(item, Mapping) for item in baseline)
            or any(not {"name", "exit_code", "timed_out"} <= item.keys() for item in baseline)
            or [item.get("name") for item in baseline] != names
        ):
            return _fail(story, "prepare.mismatch", spec, spec_digest, branch_name, base, head, unit.id)
        for argv in config.gate_commands:
            if resolve_executable(argv[0]) is None:
                return _fail(story, "gate.unavailable", spec, spec_digest, branch_name, base, head, unit.id)
        current = changed_paths(repo) - {spec}
        if not current:
            return _fail(story, "unit.empty", spec, spec_digest, branch_name, base, head, unit.id)
        out_of_scope = sum(not covered(unit.paths, path) for path in current)
        if out_of_scope:
            return _fail(
                story, "scope.exceeded", spec, spec_digest, branch_name, base, head,
                unit.id, out_of_scope=out_of_scope,
            )
        paths = tuple(sorted(current))
        candidate = _candidate_tree(repo, paths)
        metadata = front_matter(data)
        assert metadata is not None
        cap = int(metadata["size_cap_bytes"])
        diff, truncated = diff_text(repo, base, candidate, cap)
        diff_bytes = len(diff.encode("utf-8"))
        if truncated:
            full, still_truncated = diff_text(repo, base, candidate, 262144)
            diff_bytes = len(full.encode("utf-8")) if not still_truncated else cap + 1
            return _fail(
                story, "size.exceeded", spec, spec_digest, branch_name, base, head,
                unit.id, diff_bytes=diff_bytes,
            )
        if _TOKEN.search("\n".join(x for x in diff.splitlines() if x.startswith("+"))):
            return _fail(
                story, "secret.detected", spec, spec_digest, branch_name, base, head,
                unit.id, diff_bytes=diff_bytes,
            )
        gates = _run_gates(repo, config)
        after = changed_paths(repo) - {spec}
        if after != current:
            return _fail(
                story, "gate.changed_tree", spec, spec_digest, branch_name, base, head,
                unit.id, diff_bytes=diff_bytes,
            )
        if _candidate_tree(repo, tuple(sorted(after))) != candidate:
            return _fail(
                story, "gate.changed_tree", spec, spec_digest, branch_name, base, head,
                unit.id, diff_bytes=diff_bytes,
            )
        regressed = [
            entry["name"] for entry, baseline_item in zip(gates, baseline)
            if baseline_item["exit_code"] == 0
            and (entry["timed_out"] or entry["exit_code"] != 0)
        ]
        if regressed:
            return _fail(
                story, "gate.regressed", spec, spec_digest, branch_name, base, head,
                unit.id, diff_bytes=diff_bytes, regressed=", ".join(regressed),
            )
        subject, trailers = commit_message(unit, story)
        committed = git_run(repo, "add", "-A", "--", *paths)
        if committed is None or committed.returncode != 0:
            return _fail(
                story, "commit.failed", spec, spec_digest, branch_name, base, head,
                unit.id, diff_bytes=diff_bytes,
            )
        committed = git_run(
            repo,
            "commit",
            "-q",
            "-m",
            subject,
            "-m",
            trailers,
            "--only",
            "--",
            *paths,
            timeout=120,
        )
        if committed is None or committed.returncode != 0:
            return _fail(
                story, "commit.failed", spec, spec_digest, branch_name, base, head,
                unit.id, diff_bytes=diff_bytes,
            )
        new_head = resolve_revision(repo, "HEAD")
        parent = _git_text(git_run(repo, "rev-parse", "HEAD^"))
        tree = _git_text(git_run(repo, "rev-parse", "HEAD^{tree}"))
        if parent != head or tree != candidate:
            return _fail(
                story, "commit.changed", spec, spec_digest, branch_name, base, new_head,
                unit.id, commit=new_head, diff_bytes=diff_bytes,
            )
        completed = _completed(repo, base, story)
        if unit.id not in completed:
            return _fail(
                story, "commit.changed", spec, spec_digest, branch_name, base, new_head,
                unit.id, commit=new_head, diff_bytes=diff_bytes,
            )
        return _result(
            story,
            "succeeded",
            "unit.committed",
            _state(
                spec, spec_digest, branch_name, base, new_head, unit.id,
                commit=new_head, completed=len(completed),
                remaining=len(units) - len(completed), diff_bytes=diff_bytes,
            ),
            spec_sha256=spec_digest,
            base=base,
            head=new_head,
            unit_id=unit.id,
            unit_paths=", ".join(unit.paths),
        )
    except ProfileError:
        return _fail(story, "settle.failed", spec, spec_digest, branch_name)
# fmt: on
