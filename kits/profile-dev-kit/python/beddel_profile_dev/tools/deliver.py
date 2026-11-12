"""Gate and Approval-stage tools for chained profile Delivery."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import PROFILE_IMPACT_UNBOUND, ProfileError
from beddel_profile_dev._io import (
    git_run,
    path_present,
    real_repo_root,
    records_root,
)
from beddel_profile_dev.config import load_config
from beddel_profile_dev.deliver import REQUESTS, STAGES, complete, next_stage, resume
from beddel_profile_dev.implement import branch_reason
from beddel_profile_dev.integrate import APPROVALS_DIR
from beddel_profile_dev.inventory import is_valid_id
from beddel_profile_dev.tools.approval import profile_read_approval
from beddel_profile_dev.tools.implement import _git_text, _symbolic_branch, _valid_story
from beddel_profile_dev.tools.ratify import valid_actor
from beddel_profile_dev.tools.report import profile_read_report
from beddel_profile_dev.tools.stage_outcome import (
    OUTCOMES,
    STAGE_OUTCOME_SCHEMA,
    _next_ordinal,
)

__all__ = ["profile_deliver_approval", "profile_deliver_gate"]
# fmt: off
_RECORD = re.compile(r"([1-9][0-9]*)\.json")
_KEYS = ("request", "resume", "stage", "stage_record", "stage_outcome", "stage_reason", "first_record", "invoked")
_BAD = ProfileError("PROFILE_REPOSITORY_INVALID", "repository or revision invalid")


def _num(path: Path) -> int:
    match = _RECORD.fullmatch(path.name)
    return int(match.group(1)) if match is not None else 0


def _refs(**values: Any) -> dict[str, Any]:
    return {key: values.get(key) for key in _KEYS}


def _records(root: Path) -> list[dict[str, Any]]:
    directory = root / "stage-outcomes"  # The gate is the other reader of Stage-outcome records.
    if not directory.exists(): return []
    if not directory.is_dir(): raise _BAD
    found: list[dict[str, Any]] = []
    for path in sorted(directory.iterdir(), key=_num):
        match = _RECORD.fullmatch(path.name)
        if match is None: continue
        try: data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError): raise _BAD from None
        if (not isinstance(data, dict) or set(data) != {"schema", "record", "stage", "story_key", "outcome", "reason", "refs", "recorded_at"} or data.get("schema") != STAGE_OUTCOME_SCHEMA or data.get("record") != int(match.group(1)) or not isinstance(data.get("stage"), str) or (data.get("story_key") is not None and not _valid_story(data.get("story_key"))) or data.get("outcome") not in OUTCOMES or not isinstance(data.get("reason"), str) or not isinstance(data.get("refs"), dict) or not isinstance(data.get("recorded_at"), str)):
            raise _BAD
        found.append(data)
    return found


def _state(repo: Path, story: str | None, request: str, step: str, **values: Any) -> dict[str, Any]:
    go, outcome, reason = values.get("go"), values.get("outcome"), values.get("reason")
    return {"stage": "deliver", "step": step, "story_key": story, "request": request, "repo": str(repo), "go": go, "mark": values.get("mark"), "first": values.get("first"), "resume": go, "invoked": values.get("invoked", ""), "outcome": outcome, "reason": reason, "refs": values.get("refs") or _refs(request=request, resume=go, stage=step, invoked=values.get("invoked", ""))}


def _failed(repo: Path, story: str | None, request: str, step: str, reason: str, **values: Any) -> dict[str, Any]:
    return _state(repo, story, request, step, outcome="failed", reason=reason, refs=_refs(request=request, resume=values.get("resume"), stage=values.get("stage", step), stage_record=values.get("stage_record"), stage_outcome=values.get("stage_outcome"), stage_reason=reason, first_record=values.get("first"), invoked=values.get("invoked")), **{key: value for key, value in values.items() if key in {"mark", "first", "invoked", "go"}})


@beddel_tool(name="profile_deliver_gate", description="Gate a Delivery stage from create-only Stage outcomes", category="profile")
def profile_deliver_gate(repo_path: str, story_key: str, request: str, step: str, prior: object) -> dict[str, Any]:
    repo = real_repo_root(repo_path)
    if not _valid_story(story_key): return _state(repo, None, request, step, outcome="refused", reason="story_key.invalid", refs=_refs(request=request, stage=step, stage_reason="story_key.invalid"))
    if request not in REQUESTS: return _state(repo, story_key, request, step, outcome="refused", reason="request.invalid", refs=_refs(request=request, stage=step, stage_reason="request.invalid"))
    root = records_root(repo, load_config().records_dir)
    g = lambda **values: _state(repo, story_key, request, step, **values)
    f = lambda reason, **values: _failed(repo, story_key, request, step, reason, **values)
    if step == "start":
        try:
            records = _records(root)
            story_records: list[Mapping[str, Any]] = [record for record in records if record.get("story_key") == story_key and record.get("stage") in STAGES]
            mark = _next_ordinal(root)
            go, done = (request, False) if request != "all" else resume(story_records)
            return g(go=None if done else go, outcome="succeeded" if done else None, reason="deliver.complete" if done else None, mark=mark, first=mark, refs=_refs(request=request, resume=None if done else go, first_record=mark, invoked=""))
        except ProfileError: return f("records.unreadable")
    if step not in STAGES: return g(outcome="failed", reason="gate.failed", refs=_refs(request=request, stage=step, stage_reason="gate.failed"))
    if prior is None: return f("gate.failed")
    if not isinstance(prior, Mapping) or any(prior.get(key) != value for key, value in (("stage", "deliver"), ("story_key", story_key), ("request", request), ("repo", str(repo)))): return f("state.mismatch")
    if prior.get("outcome") is not None or prior.get("go") != step:
        if step == "integrate" and prior.get("outcome") is None:
            return f("gate.failed")
        return dict(prior)
    mark_value = prior.get("mark")
    if not isinstance(mark_value, int): return f("state.mismatch")
    mark = mark_value
    try: records = _records(root)
    except ProfileError: return f("records.unreadable", mark=mark)
    candidates = [record for record in records if isinstance(record.get("record"), int) and record["record"] >= mark and record.get("stage") == step and record.get("story_key") == story_key]
    invoked = ", ".join(filter(None, [str(prior.get("invoked", "")), step]))
    if not candidates: return f("stage.unrecorded", mark=mark, first=prior.get("first"), invoked=invoked, go=step, stage=step)
    record, outcome, record_reason = candidates[-1], candidates[-1]["outcome"], candidates[-1]["reason"]
    refs = _refs(request=request, resume=step, stage=step, stage_record=record["record"], stage_outcome=outcome, stage_reason=record_reason, first_record=prior.get("first"), invoked=invoked)
    if complete(step, outcome, record_reason):
        following = next_stage(step)
        if following is None: return g(outcome="succeeded", reason="deliver.complete", mark=_next_ordinal(root), first=prior.get("first"), invoked=invoked, refs=refs)
        if request != "all": return g(outcome="succeeded", reason="stage.complete", mark=_next_ordinal(root), first=prior.get("first"), invoked=invoked, refs=refs)
        return g(go=following, mark=_next_ordinal(root), first=prior.get("first"), invoked=invoked, refs={**refs, "resume": following, "stage": following})
    if outcome == "succeeded": return g(outcome="failed", reason="stage.incomplete", mark=mark, first=prior.get("first"), invoked=invoked, refs=refs)
    return g(outcome=outcome, reason=f"stage.{outcome}", mark=mark, first=prior.get("first"), invoked=invoked, refs=refs)


def _approval(repo: Path, story: str, change: str, branch: str, **values: Any) -> dict[str, Any]:
    return {"stage": "approval", "phase": values.get("phase", "check"), "story_key": story, "repo": str(repo), "change_id": change, "branch": branch, "approve": values.get("approve", False), "revision": values.get("revision"), "decision_commit": values.get("decision_commit"), "outcome": values.get("outcome"), "reason": values.get("reason"), "refs": values.get("refs") or {"change_id": change, "branch": branch, "revision": values.get("revision"), "report": None, "decision_path": None, "decision_commit": values.get("decision_commit"), "approval": None, "invoked": values.get("approve", False)}}
def _a(repo: Path, story: str, change: str, branch: str, outcome: str, reason: str, **values: Any) -> dict[str, Any]:
    return _approval(repo, story, change, branch, outcome=outcome, reason=reason, **values)
@beddel_tool(name="profile_deliver_approval", description="Reconcile and settle the Approval stage boundary", category="profile")
def profile_deliver_approval(repo_path: str, story_key: str, change_id: str, branch: str, actor: str, phase: str, prior: object) -> dict[str, Any]:
    repo = real_repo_root(repo_path)
    a = lambda outcome, reason, **values: _a(repo, story_key, change_id, branch, outcome, reason, **values)
    if phase not in ("check", "settle"): return a("failed", "approval.invalid")
    if not isinstance(prior, Mapping) or prior.get("story_key") != story_key or prior.get("repo") != str(repo): return a("failed", "state.mismatch")
    if phase == "check":
        if prior.get("outcome") is not None:
            return dict(prior)
        if prior.get("stage") != "deliver" or prior.get("go") != "approval": return a("failed", "state.mismatch")
        if not is_valid_id(change_id): return a("refused", "change_id.invalid")
        if branch_reason(branch, None) is not None: return a("refused", "branch.invalid")
        if not valid_actor(actor): return a("refused", "actor.invalid")
        if _symbolic_branch(repo) != branch: return a("refused", "branch.not_current")
        try: stored = profile_read_approval(str(repo), change_id).get("approval")
        except ProfileError as error:
            return a("refused" if error.code == PROFILE_IMPACT_UNBOUND else "failed", "report.absent" if error.code == PROFILE_IMPACT_UNBOUND else "approval.invalid")
        if stored is not None:
            revision = stored.get("revision") if isinstance(stored, Mapping) else None
            return a("succeeded", "approval.reused", revision=revision, refs={"change_id": change_id, "branch": branch, "revision": revision, "report": None, "decision_path": None, "decision_commit": None, "approval": "proof.commit", "invoked": False})
        try:
            data = profile_read_report(str(repo), change_id)
            history, report = data.get("history"), data.get("report")
        except ProfileError: return a("failed", "report.unreadable")
        if not isinstance(history, list) or not history or not isinstance(report, Mapping): return a("refused", "report.absent")
        latest = history[-1] if isinstance(history[-1], Mapping) else {}
        match, revision = re.search(r"/(\d+)\.json$", str(latest.get("ref"))), report.get("revision")
        if match is None or not isinstance(revision, str): return a("failed", "report.unreadable")
        path = f"{APPROVALS_DIR}{change_id}/{match.group(1)}.yaml"
        refs = {"change_id": change_id, "branch": branch, "revision": revision, "report": latest.get("ref"), "decision_path": path, "decision_commit": None, "approval": None, "invoked": True}
        try:
            present = path_present(repo, "HEAD", path)
        except ProfileError:
            return a("failed", "decision.unreadable", revision=revision, refs=refs)
        if not present: return a("stopped", "approval.awaiting_owner", revision=revision, refs=refs)
        commit = _git_text(git_run(repo, "log", "-1", "--format=%H", "--diff-filter=A", "HEAD", "--", path))
        if not commit or not re.fullmatch(r"[0-9a-f]{40}", commit): return a("failed", "decision.unreadable", revision=revision, refs=refs)
        refs["decision_commit"] = commit
        return _approval(repo, story_key, change_id, branch, approve=True, revision=revision, decision_commit=commit, refs=refs)
    if prior.get("stage") != "approval" or prior.get("phase") != "check" or prior.get("change_id") != change_id: return a("failed", "state.mismatch")
    if prior.get("outcome") is not None: return dict(prior)
    try: stored = profile_read_approval(str(repo), change_id).get("approval")
    except ProfileError: return {**dict(prior), "outcome": "failed", "reason": "approval.invalid"}
    if stored is None: return {**dict(prior), "outcome": "refused", "reason": "approval.refused"}
    if not isinstance(stored, Mapping) or stored.get("revision") != prior.get("revision"): return {**dict(prior), "outcome": "failed", "reason": "approval.invalid"}
    refs = dict(prior.get("refs") or {}); refs.update(approval="proof.commit", invoked=True)
    return {**dict(prior), "outcome": "succeeded", "reason": "approval.recorded", "refs": refs}
# fmt: on
