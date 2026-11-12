# fmt: off
# ruff: noqa: I001
from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import ProfileError
from beddel_profile_dev._io import changed_paths, confined, footprint, git_run, is_ancestor, read_confined, real_repo_root, resolve_revision
from beddel_profile_dev.integrate import MAX_STATUS_BYTES, REMOTE, STATUS_VALUE, approved_only, pointer_message, set_status, status_lines, status_value
from beddel_profile_dev.inventory import is_valid_id
from beddel_profile_dev.plan import relative_path
from beddel_profile_dev.implement import _BRANCH
from beddel_profile_dev.tools.approval import profile_read_approval
from beddel_profile_dev.tools.implement import _git_text, _repo_error, _symbolic_branch, _valid_story
from beddel_profile_dev.tools.implement import branch_reason
from beddel_profile_dev.tools.report import profile_read_report


_REF_NAMES = ("boundary", "spec_path", "branch", "base_branch", "change_id", "revision", "tip", "approval", "report", "pr", "merge", "sub_path", "pointer", "status_path", "status_written")


def _refs(**values: Any) -> dict[str, Any]:
    return {name: values.get(name, False if name == "status_written" else None) for name in _REF_NAMES}


_CARRY_FIELDS = ("change_id", "repo", "spec_path", "branch", "base_branch", "parent", "parent_branch", "sub_path", "status_path", "status_value", "revision")


def _carry(prior: Mapping[str, Any]) -> dict[str, Any]:
    return {key: prior.get(key) for key in _CARRY_FIELDS}


def _carry_refs(prior: Mapping[str, Any], **updates: Any) -> dict[str, Any]:
    refs = dict(prior.get("refs") or {}) if isinstance(prior.get("refs"), Mapping) else {}
    refs.update(updates)
    return _refs(**refs)


def _forwarded(prior: object) -> dict[str, Any] | None:
    return dict(prior) if isinstance(prior, Mapping) and prior.get("outcome") is not None else None


def _state(story: str | None, outcome: str | None, reason: str | None, refs: Mapping[str, Any] | None = None, **values: Any) -> dict[str, Any]:
    data = {"stage": "integrate", "phase": values.get("phase"), "story_key": story, "change_id": values.get("change_id"), "outcome": outcome, "reason": reason, "refs": dict(refs or _refs()), "pr": values.get("pr", False), "merged": values.get("merged", False), "repo": values.get("repo"), "spec_path": values.get("spec_path"), "branch": values.get("branch"), "base_branch": values.get("base_branch"), "remote": values.get("remote"), "parent": values.get("parent"), "parent_branch": values.get("parent_branch"), "sub_path": values.get("sub_path"), "status_path": values.get("status_path"), "status_value": values.get("status_value"), "revision": values.get("revision"), "tip": values.get("tip"), "merge": values.get("merge"), "pointer": values.get("pointer")}
    return data


def _fail(story: str | None, reason: str, refs: Mapping[str, Any] | None = None, **values: Any) -> dict[str, Any]:
    values["remote"] = None
    return _state(story, "failed", reason, refs, **values)


def _refuse(story: str | None, reason: str, refs: Mapping[str, Any] | None = None, **values: Any) -> dict[str, Any]:
    values["remote"] = None
    return _state(story, "refused", reason, refs, **values)


def _repository(repo_path: str) -> Path:
    return real_repo_root(repo_path)


def _remotes(repo: Path) -> set[str]:
    result = git_run(repo, "remote")
    if result is None or result.returncode != 0:
        raise _repo_error()
    return {line for line in result.stdout.decode("utf-8", "replace").splitlines() if line}


def _ref_exists(repo: Path, ref: str) -> bool:
    result = git_run(repo, "show-ref", "--verify", "--quiet", ref)
    if result is None or result.returncode not in (0, 1):
        raise _repo_error()
    return result.returncode == 0


def _gitlink(repo: Path, tree: str, sub_path: str) -> str | None:
    result = git_run(repo, "ls-tree", "-z", tree, "--", sub_path)
    if result is None or result.returncode != 0:
        raise _repo_error()
    entries = [item for item in result.stdout.split(b"\x00") if item]
    if len(entries) != 1 or b"\t" not in entries[0]:
        return None
    mode_oid, path = entries[0].split(b"\t", 1)
    fields = mode_oid.decode("ascii", "replace").split()
    if len(fields) != 3 or fields[0] != "160000" or path.decode("utf-8", "replace") != sub_path:
        return None
    return fields[2]


def _valid_inputs(story_key: object, spec_path: object, branch: object, base_branch: object, remote: object, change_id: object, parent_path: object, parent_branch: object, status_path: object, status: object) -> tuple[str, str, str, str, str, str, str, str, str] | dict[str, Any]:
    story = story_key if isinstance(story_key, str) and _valid_story(story_key) else None
    spec = spec_path if isinstance(spec_path, str) and len(spec_path) <= 512 and relative_path(spec_path) else None
    if story is None: return _refuse(None, "story_key.invalid", _refs(spec_path=spec))
    if spec is None: return _refuse(story, "path.invalid", _refs())
    if not isinstance(branch, str) or _BRANCH.fullmatch(branch) is None: return _refuse(story, "branch.invalid", _refs(spec_path=spec))
    if not isinstance(base_branch, str) or _BRANCH.fullmatch(base_branch) is None: return _refuse(story, "base.invalid", _refs(spec_path=spec, branch=branch))
    reason = branch_reason(branch, base_branch)
    if reason is not None: return _refuse(story, reason, _refs(spec_path=spec, branch=branch, base_branch=base_branch))
    if not isinstance(parent_branch, str) or _BRANCH.fullmatch(parent_branch) is None: return _refuse(story, "base.invalid", _refs(spec_path=spec, branch=branch, base_branch=base_branch))
    if not isinstance(remote, str) or REMOTE.fullmatch(remote) is None: return _refuse(story, "remote.invalid", _refs(spec_path=spec, branch=branch, base_branch=base_branch))
    if not isinstance(change_id, str) or not is_valid_id(change_id): return _refuse(story, "change_id.invalid", _refs(spec_path=spec, branch=branch, base_branch=base_branch))
    if not isinstance(parent_path, str) or not parent_path.strip(): return _refuse(story, "path.invalid", _refs(spec_path=spec, branch=branch, base_branch=base_branch, change_id=change_id))
    if not isinstance(status_path, str) or len(status_path) > 512 or (status_path and not relative_path(status_path)): return _refuse(story, "path.invalid", _refs(spec_path=spec, branch=branch, base_branch=base_branch, change_id=change_id))
    if not isinstance(status, str) or STATUS_VALUE.fullmatch(status) is None: return _refuse(story, "status.invalid", _refs(spec_path=spec, branch=branch, base_branch=base_branch, change_id=change_id))
    return story, spec, branch, base_branch, remote, change_id, parent_branch, status_path, status


def _with(prior: Mapping[str, Any], *, outcome: str | None = None, reason: str | None = None, refs: Mapping[str, Any] | None = None, **values: Any) -> dict[str, Any]:
    data = dict(prior)
    data.update(values)
    data["outcome"] = outcome
    data["reason"] = reason
    prior_refs_object = prior.get("refs")
    prior_refs: dict[str, Any] = dict(prior_refs_object) if isinstance(prior_refs_object, Mapping) else {}
    merged_refs = dict(prior_refs)
    merged_refs.update(dict(refs or {}))
    data["refs"] = _refs(**merged_refs)
    return data


def _prior_check(repo: Path, story: str, change: str, prior: object, phase: str) -> dict[str, Any] | None:
    if prior is None: return _fail(story, "reconcile.failed" if phase == "confirm" or phase == "land" else "pointer.failed", _refs(change_id=change), change_id=change, phase=phase, repo=str(repo))
    if not isinstance(prior, Mapping) or prior.get("stage") != "integrate" or prior.get("story_key") != story or prior.get("change_id") != change or os.path.realpath(str(prior.get("repo"))) != str(repo):
        return _fail(story, "state.mismatch", _refs(change_id=change), change_id=change, phase=phase, repo=str(repo))
    return None


def _fetch_check(fetch: object, story: str, change: str, repo: Path, phase: str) -> dict[str, Any] | None:
    if not isinstance(fetch, Mapping) or not fetch:
        return _fail(story, "fetch.failed", _refs(change_id=change), change_id=change, phase=phase, repo=str(repo))
    return None


def _tracking(repo: Path, remote: str, branch: str) -> str:
    return resolve_revision(repo, f"refs/remotes/{remote}/{branch}")


def _merge_commit(repo: Path, tip: str, tracking: str) -> str | None:
    if tip == tracking: return tip
    result = git_run(repo, "rev-list", "--first-parent", "--ancestry-path", "--reverse", f"{tip}..{tracking}")
    if result is None or result.returncode != 0: raise _repo_error()
    first = result.stdout.decode("ascii", "replace").splitlines()
    if not first: return None
    candidate = first[0].strip()
    parent = _git_text(git_run(repo, "rev-parse", f"{candidate}^1"))
    if parent == tip: return tip
    return candidate if is_ancestor(repo, tip, candidate) else None


def _host_ok(value: object) -> bool:
    return isinstance(value, Mapping) and bool(value) and not value.get("error")


@beddel_tool(name="profile_integrate_prepare", description="Prepare one approved Change for integration", category="profile")
def profile_integrate_prepare(repo_path: str, story_key: str, spec_path: str, branch: str, base_branch: str, remote: str, change_id: str, parent_path: str, parent_branch: str, status_path: str, status_value: str) -> dict[str, Any]:
    checked = _valid_inputs(story_key, spec_path, branch, base_branch, remote, change_id, parent_path, parent_branch, status_path, status_value)
    if isinstance(checked, dict): return checked
    story, spec, branch, base, remote, change, pbranch, status, value = checked
    repo = _repository(repo_path)
    try:
        if remote not in _remotes(repo): return _refuse(story, "remote.invalid", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change), story_key=story, change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, parent_branch=pbranch, status_path=status, status_value=value)
        if not _ref_exists(repo, f"refs/heads/{branch}"): return _refuse(story, "branch.absent", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent_branch=pbranch, status_path=status, status_value=value)
        tip = resolve_revision(repo, f"refs/heads/{branch}")
        dirty = changed_paths(repo) - {spec}
        if dirty: return _fail(story, "worktree.dirty", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, tip=tip), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent_branch=pbranch, status_path=status, status_value=value, tip=tip)
        try: approval_result = profile_read_approval(str(repo), change)
        except ProfileError: return _refuse(story, "approval.invalid", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, tip=tip), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent_branch=pbranch, status_path=status, status_value=value, tip=tip)
        approval = approval_result.get("approval") if isinstance(approval_result, Mapping) else None
        if approval is None: return _refuse(story, "approval.absent", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, tip=tip), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent_branch=pbranch, status_path=status, status_value=value, tip=tip)
        if not isinstance(approval, Mapping): return _refuse(story, "approval.invalid", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, tip=tip), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent_branch=pbranch, status_path=status, status_value=value, tip=tip)
        revision = approval.get("revision")
        if not isinstance(revision, str): return _refuse(story, "approval.invalid", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, tip=tip), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent_branch=pbranch, status_path=status, status_value=value, tip=tip)
        try: approved = resolve_revision(repo, revision)
        except ProfileError: return _refuse(story, "approval.invalid", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, tip=tip), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent_branch=pbranch, status_path=status, status_value=value, tip=tip)
        try: report_result = profile_read_report(str(repo), change)
        except ProfileError: return _refuse(story, "approval.invalid", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, revision=approved, tip=tip), repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent_branch=pbranch, status_path=status, status_value=value, tip=tip, revision=approved)
        report = report_result.get("report") if isinstance(report_result, Mapping) else None
        if not isinstance(report, Mapping): return _refuse(story, "approval.invalid", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, revision=approved, tip=tip), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent_branch=pbranch, status_path=status, status_value=value, revision=approved, tip=tip)
        if report.get("revision") != approved: return _refuse(story, "report.superseded", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, revision=approved, tip=tip), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent_branch=pbranch, status_path=status, status_value=value, revision=approved, tip=tip)
        if report.get("verdict") != "consistent": return _refuse(story, "verdict.has_pendency", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, revision=approved, tip=tip), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent_branch=pbranch, status_path=status, status_value=value, revision=approved, tip=tip)
        if not is_ancestor(repo, approved, tip) or not approved_only(footprint(repo, approved, tip)): return _refuse(story, "revision.unapproved", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, revision=approved, tip=tip), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent_branch=pbranch, status_path=status, status_value=value, revision=approved, tip=tip)
        try:
            parent = _repository(parent_path)
        except ProfileError:
            return _refuse(story, "parent.invalid", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, revision=approved, tip=tip), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent=parent_path, parent_branch=pbranch, status_path=status, status_value=value, revision=approved, tip=tip)
        try: sub_path = Path(os.path.relpath(repo, parent)).as_posix()
        except ValueError: sub_path = ""
        if not relative_path(sub_path) or _gitlink(parent, "HEAD", sub_path) is None: return _refuse(story, "parent.invalid", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, revision=approved, tip=tip, sub_path=sub_path), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent=str(parent), parent_branch=pbranch, sub_path=sub_path, status_path=status, status_value=value, revision=approved, tip=tip)
        if _symbolic_branch(parent) != pbranch: return _refuse(story, "parent.not_current", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, revision=approved, tip=tip, sub_path=sub_path), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent=str(parent), parent_branch=pbranch, sub_path=sub_path, status_path=status, status_value=value, revision=approved, tip=tip)
        if remote not in _remotes(parent): return _refuse(story, "remote.invalid", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, revision=approved, tip=tip, sub_path=sub_path), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent=str(parent), parent_branch=pbranch, sub_path=sub_path, status_path=status, status_value=value, revision=approved, tip=tip)
        if status:
            data = read_confined(parent, status)
            if data is None: return _refuse(story, "status.absent", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, revision=approved, tip=tip, sub_path=sub_path, status_path=status), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent=str(parent), parent_branch=pbranch, sub_path=sub_path, status_path=status, status_value=value, revision=approved, tip=tip)
            if len(data) > MAX_STATUS_BYTES or len(status_lines(data, story)) != 1: return _refuse(story, "status.unmatched", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change, revision=approved, tip=tip, sub_path=sub_path, status_path=status), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent=str(parent), parent_branch=pbranch, sub_path=sub_path, status_path=status, status_value=value, revision=approved, tip=tip)
        proof_value = approval.get("proof")
        proof: Mapping[str, Any] = proof_value if isinstance(proof_value, Mapping) else {}
        refs = _refs(boundary="repository", spec_path=spec, branch=branch, base_branch=base, change_id=change, revision=approved, tip=tip, report=approval.get("report"), sub_path=sub_path, status_path=status, approval=proof.get("commit"))
        return _state(story, None, None, refs, phase="prepare", change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=remote, parent=str(parent), parent_branch=pbranch, sub_path=sub_path, status_path=status, status_value=value, revision=approved, tip=tip)
    except ProfileError:
        return _fail(story, "prepare.failed", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=None, parent_branch=pbranch, status_path=status, status_value=value)
    except OSError:
        return _fail(story, "prepare.failed", _refs(spec_path=spec, branch=branch, base_branch=base, change_id=change), change_id=change, repo=str(repo), spec_path=spec, branch=branch, base_branch=base, remote=None, parent_branch=pbranch, status_path=status, status_value=value)


@beddel_tool(name="profile_integrate_reconcile", description="Reconcile remote integration state", category="profile")
def profile_integrate_reconcile(repo_path: str, story_key: str, change_id: str, phase: str, prior: Mapping[str, Any] | None, fetch: Mapping[str, Any] | None, push: Mapping[str, Any] | None = None, pull_request: Mapping[str, Any] | None = None, checks: Mapping[str, Any] | None = None, merge: Mapping[str, Any] | None = None) -> dict[str, Any]:
    forwarded = _forwarded(prior)
    if forwarded is not None:
        return forwarded
    story = story_key if isinstance(story_key, str) and _valid_story(story_key) else None
    if story is None or not isinstance(change_id, str) or not is_valid_id(change_id) or phase not in ("land", "confirm"): return _fail(story, "reconcile.failed", _refs(change_id=change_id), change_id=change_id, phase=phase)
    repo = _repository(repo_path)
    mismatch = _prior_check(repo, story, change_id, prior, phase)
    if mismatch is not None: return mismatch
    assert isinstance(prior, Mapping)
    if prior.get("outcome") is not None: return dict(prior)
    bad_fetch = _fetch_check(fetch, story, change_id, repo, phase)
    if bad_fetch is not None: return bad_fetch
    try:
        branch, remote, base = prior.get("branch"), prior.get("remote"), prior.get("base_branch")
        tip = resolve_revision(repo, f"refs/heads/{branch}")
        if tip != prior.get("tip"): return _fail(story, "head.moved", _carry_refs(prior, tip=tip), **_carry(prior), phase=phase, tip=tip)
        tracking = _tracking(repo, str(remote), str(base))
        if phase == "land":
            if is_ancestor(repo, tip, tracking): return _with(prior, merged=True, pr=False, phase="land", tip=tip)
            if _symbolic_branch(repo) != branch: return _fail(story, "branch.not_current", _carry_refs(prior, tip=tip), **_carry(prior), phase="land", tip=tip, pr=False, merged=False)
            return _with(prior, phase="land", pr=True, merged=False, tip=tip)
        contained = is_ancestor(repo, tip, tracking)
        if contained:
            merge_sha = _merge_commit(repo, tip, tracking)
            if merge_sha is None: return _fail(story, "merge.unconfirmed", _carry_refs(prior, tip=tip), **_carry(prior), phase="confirm", tip=tip)
            if isinstance(merge, Mapping):
                result = merge.get("result")
                reported = result.get("merge_sha") if isinstance(result, Mapping) else None
                if reported != merge_sha: return _fail(story, "merge.mismatch", _carry_refs(prior, tip=tip, merge=merge_sha), **_carry(prior), phase="confirm", tip=tip, merge=merge_sha)
            number = pull_request.get("result", {}).get("number") if isinstance(pull_request, Mapping) and isinstance(pull_request.get("result"), Mapping) else None
            refs = _carry_refs(prior, boundary="repository", tip=tip, merge=merge_sha, pr=number)
            return _with(prior, outcome="succeeded", reason="merge.confirmed" if prior.get("pr") else "merge.reused", refs=refs, phase="confirm", tip=tip, merge=merge_sha, merged=True)
        if prior.get("pr") is True:
            for item, reason in ((push, "push.failed"), (pull_request, "pr.failed"), (checks, "checks.failed"), (merge, "merge.failed")):
                if not _host_ok(item): return _fail(story, reason, _carry_refs(prior, tip=tip), **_carry(prior), phase="confirm", tip=tip)
        return _fail(story, "merge.unconfirmed", _carry_refs(prior, tip=tip), **_carry(prior), phase="confirm", tip=tip)
    except ProfileError:
        return _fail(story, "reconcile.failed", _carry_refs(prior), **_carry(prior), phase=phase)
    except OSError:
        return _fail(story, "reconcile.failed", _carry_refs(prior), **_carry(prior), phase=phase)


@beddel_tool(name="profile_integrate_settle", description="Settle the parent integration boundary", category="profile")
def profile_integrate_settle(repo_path: str, story_key: str, change_id: str, phase: str, prior: Mapping[str, Any] | None, fetch: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if phase == "finish":
        forwarded = _forwarded(prior)
        if forwarded is not None:
            return forwarded
    story = story_key if isinstance(story_key, str) and _valid_story(story_key) else None
    if story is None or not isinstance(change_id, str) or not is_valid_id(change_id) or phase not in ("pointer", "finish"): return _fail(story, "pointer.failed", _refs(change_id=change_id), change_id=change_id, phase=phase)
    repo = _repository(repo_path)
    mismatch = _prior_check(repo, story, change_id, prior, phase)
    if mismatch is not None: return mismatch
    assert isinstance(prior, Mapping)
    if phase == "finish":
        bad_fetch = _fetch_check(fetch, story, change_id, repo, phase)
        if bad_fetch is not None: return bad_fetch
    try:
        if phase == "pointer" and (prior.get("phase") != "confirm" or prior.get("merged") is not True): return _fail(story, "pointer.failed", _carry_refs(prior), **_carry(prior), phase="pointer")
        if phase == "finish" and prior.get("phase") != "pointer": return _fail(story, "pointer.failed", _carry_refs(prior), **_carry(prior), phase="finish")
        parent = _repository(str(prior.get("parent")))
        sub_path, merge = prior.get("sub_path"), prior.get("merge")
        if not isinstance(sub_path, str) or not relative_path(sub_path) or not isinstance(merge, str): return _fail(story, "pointer.failed", _carry_refs(prior), **_carry(prior), phase=phase)
        if phase == "pointer":
            parent_head = resolve_revision(parent, "HEAD")
            current = _gitlink(parent, "HEAD", sub_path)
            reused = current == merge
            if not reused and current is not None:
                try: reused = is_ancestor(repo, merge, resolve_revision(repo, current))
                except ProfileError: reused = False
            if reused: return _with(prior, phase="pointer", pointer=parent_head, refs=_carry_refs(prior, boundary="parent", pointer=parent_head, sub_path=sub_path))
            if _symbolic_branch(parent) != prior.get("parent_branch"): return _fail(story, "parent.not_current", _carry_refs(prior, boundary="parent", sub_path=sub_path), **_carry(prior), phase="pointer")
            if changed_paths(repo) - {prior.get("spec_path")}: return _fail(story, "worktree.dirty", _carry_refs(prior, boundary="parent", sub_path=sub_path), **_carry(prior), phase="pointer")
            if resolve_revision(repo, "HEAD") != merge:
                switched = git_run(repo, "switch", "-q", "--detach", merge)
                if switched is None or switched.returncode != 0: return _fail(story, "checkout.failed", _carry_refs(prior, boundary="parent", sub_path=sub_path), **_carry(prior), phase="pointer")
            if resolve_revision(repo, "HEAD") != merge: return _fail(story, "checkout.failed", _carry_refs(prior, boundary="parent", sub_path=sub_path), **_carry(prior), phase="pointer")
            old = parent_head
            subject, trailers = pointer_message(story, sub_path, merge)
            committed = git_run(parent, "commit", "-q", "-m", subject, "-m", trailers, "--only", "--", sub_path, timeout=120)
            if committed is None or committed.returncode != 0: return _fail(story, "commit.failed", _carry_refs(prior, boundary="parent", sub_path=sub_path), **_carry(prior), phase="pointer")
            pointer = resolve_revision(parent, "HEAD")
            if _git_text(git_run(parent, "rev-parse", "HEAD^")) != old or _gitlink(parent, "HEAD", sub_path) != merge: return _fail(story, "commit.changed", _carry_refs(prior, boundary="parent", sub_path=sub_path, pointer=pointer), **{k: prior.get(k) for k in ("change_id", "repo", "spec_path", "branch", "base_branch", "remote", "parent", "parent_branch", "status_path", "status_value", "revision", "tip", "merge")}, phase="pointer", pointer=pointer)
            return _with(prior, phase="pointer", pointer=pointer, refs=_carry_refs(prior, boundary="parent", sub_path=sub_path, pointer=pointer))
        tracking = _tracking(parent, str(prior.get("remote")), str(prior.get("parent_branch")))
        remote_gitlink = _gitlink(parent, tracking, sub_path)
        published = remote_gitlink == merge
        if not published and remote_gitlink is not None:
            try: published = is_ancestor(repo, merge, resolve_revision(repo, remote_gitlink))
            except ProfileError: published = False
        if not published: return _with(prior, outcome="stopped", reason="pointer.unpublished", phase="finish", refs=_carry_refs(prior, boundary="parent", sub_path=sub_path, pointer=prior.get("pointer")), pointer=prior.get("pointer"))
        status = prior.get("status_path")
        if not status: return _with(prior, outcome="succeeded", reason="integrate.complete", phase="finish", refs=_carry_refs(prior, boundary="parent", sub_path=sub_path, pointer=prior.get("pointer"), status_written=False), pointer=prior.get("pointer"))
        data = read_confined(parent, str(status))
        if data is None: return _fail(story, "status.unmatched", _carry_refs(prior, boundary="parent", sub_path=sub_path, pointer=prior.get("pointer")), **_carry(prior), phase="finish")
        value = str(prior.get("status_value"))
        if status_value(data, story) == value: return _with(prior, outcome="succeeded", reason="integrate.complete", phase="finish", refs=_carry_refs(prior, boundary="parent", sub_path=sub_path, pointer=prior.get("pointer"), status_written=False), pointer=prior.get("pointer"))
        updated = set_status(data, story, value)
        if updated is None: return _fail(story, "status.unmatched", _carry_refs(prior, boundary="parent", sub_path=sub_path, pointer=prior.get("pointer")), **_carry(prior), phase="finish")
        target = confined(parent, str(status))
        fd, temporary = tempfile.mkstemp(prefix=".beddel-status-", dir=str(target.parent))
        try:
            with os.fdopen(fd, "wb") as handle: handle.write(updated)
            os.chmod(temporary, stat.S_IMODE(os.stat(target).st_mode))
            os.replace(temporary, target)
        except OSError:
            try: os.unlink(temporary)
            except OSError: pass
            return _fail(story, "status.failed", _carry_refs(prior, boundary="parent", sub_path=sub_path, pointer=prior.get("pointer")), **_carry(prior), phase="finish")
        return _with(prior, outcome="succeeded", reason="integrate.complete", phase="finish", refs=_carry_refs(prior, boundary="parent", sub_path=sub_path, pointer=prior.get("pointer"), status_written=True), pointer=prior.get("pointer"))
    except ProfileError:
        return _fail(story, "pointer.failed", _carry_refs(prior), **_carry(prior), phase=phase)
    except OSError:
        return _fail(story, "pointer.failed", _carry_refs(prior), **_carry(prior), phase=phase)
# fmt: on
