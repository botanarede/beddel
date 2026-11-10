# fmt: off
# ruff: noqa: I001
import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from beddel.tools import beddel_tool
from beddel_profile_dev._errors import PROFILE_IMPACT_UNBOUND, ProfileError
from beddel_profile_dev._io import changed_paths, diff_text, git_run, real_repo_root, resolve_revision
from beddel_profile_dev.config import load_config
from beddel_profile_dev.fix import MAX_FINDINGS_BYTES, MAX_FIX_ROUNDS, decision, fix_findings, fix_message, report_at, scope_paths, trailer_round
from beddel_profile_dev.implement import branch_reason, covered, spec_units
from beddel_profile_dev.inventory import is_valid_id
from beddel_profile_dev.plan import front_matter, relative_path, spec_complete
from beddel_profile_dev.tools._subprocess import resolve_executable
from beddel_profile_dev.tools.implement import _TOKEN, _candidate_tree, _completed, _git_text, _read_spec, _repo_error, _run_gates, _symbolic_branch, _valid_base, _valid_story
from beddel_profile_dev.tools.report import profile_read_report

def _refs(**values: Any) -> dict[str, Any]:
    names = ("spec_path", "spec_sha256", "branch", "base", "head", "commit", "change_id", "report", "report_sha256", "round", "rounds", "findings", "diff_bytes", "out_of_scope", "regressed")
    return {name: values.get(name) for name in names}

def _result(story: str | None, outcome: str | None, reason: str | None, refs: dict[str, Any], **values: Any) -> dict[str, Any]:
    return {"stage": "verify-and-fix", "story_key": story, "verify": values.get("verify", False), "fix": values.get("fix", False), "outcome": outcome, "reason": reason, "refs": refs, "spec_sha256": values.get("spec_sha256"), "base": values.get("base"), "head": values.get("head"), "round": values.get("round"), "rounds": values.get("rounds", 0), "findings": values.get("findings", ""), "scope_paths": values.get("scope", ""), "baseline": values.get("baseline")}

def _bad(story: str | None, reason: str, **values: Any) -> dict[str, Any]:
    return _result(story, "failed", reason, _refs(**values), **values)

def _refused(story: str | None, reason: str, **values: Any) -> dict[str, Any]:
    return _result(story, "refused", reason, _refs(**values), **values)

def _inputs(repo_path: str, story: object, spec: object, branch: object, base: object, change: object, bound: object):
    s = story if isinstance(story, str) and _valid_story(story) else None
    p = spec if isinstance(spec, str) and len(spec) <= 512 and relative_path(spec) else None
    b = branch if isinstance(branch, str) and len(branch) <= 128 else None
    c = change if isinstance(change, str) and is_valid_id(change) else None
    if s is None: return _refused(None, "story_key.invalid", spec_path=p, branch=b, change_id=c)
    if p is None: return _refused(s, "path.invalid", branch=b, change_id=c)
    if not isinstance(branch, str) or branch_reason(branch, base) == "branch.invalid": return _refused(s, "branch.invalid", spec_path=p, change_id=c)
    branch_error = branch_reason(branch, base)
    if branch_error is not None: return _refused(s, branch_error, spec_path=p, change_id=c)
    if not _valid_base(base): return _refused(s, "base.invalid", spec_path=p, change_id=c)
    if c is None: return _refused(s, "change_id.invalid", spec_path=p, branch=branch)
    if type(bound) is not int or not 0 <= bound <= MAX_FIX_ROUNDS: return _refused(s, "bound.invalid", spec_path=p, change_id=c)
    return real_repo_root(repo_path), s, p, branch, str(base), c, bound

def _report(repo: Path, change: str, head: str):
    try: data = profile_read_report(str(repo), change)
    except ProfileError as error:
        if error.code == PROFILE_IMPACT_UNBOUND: return None, None
        raise
    history = data.get("history") if isinstance(data, Mapping) else None
    if not isinstance(history, list): return None, None
    item = next((item for item in reversed(history) if isinstance(item, Mapping) and isinstance(item.get("content"), Mapping) and item["content"].get("revision") == head), None)
    return (report_at(history, head) if item is not None else None), item

def _state_refs(spec: str, digest: str, branch: str, base: str, head: str, change: str, rounds: int, **values: Any):
    item = values.pop("report", None)
    if isinstance(item, Mapping): values.update(report=item.get("ref"), report_sha256=item.get("sha256"))
    return _refs(spec_path=spec, spec_sha256=digest, branch=branch, base=base, head=head, change_id=change, rounds=rounds, **values)

def _repo_state(repo: Path, story: str, spec: str, branch: str, base_ref: str, change: str):
    refused = lambda reason: _refused(story, reason, spec_path=spec, branch=branch, change_id=change)
    base0 = resolve_revision(repo, base_ref)
    result = git_run(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
    if result is None or result.returncode not in (0, 1): raise _repo_error()
    if result.returncode == 1: return refused("branch.absent")
    if _symbolic_branch(repo) != branch: return refused("branch.not_current")
    if Path(os.path.realpath(os.getcwd())) != repo: return refused("cwd.mismatch")
    data, error = _read_spec(repo, spec)
    if error is not None or data is None: return refused(error or "spec.unreadable")
    if not spec_complete(data, story): return refused("spec.incomplete")
    units = spec_units(data, story)
    if units is None: return refused("units.invalid")
    config = load_config()
    if any(resolve_executable(argv[0]) is None for argv in config.gate_commands): return refused("gate.unavailable")
    fail = lambda reason, **values: _bad(story, reason, **values)
    if changed_paths(repo) - {spec}: return fail("worktree.dirty", head=resolve_revision(repo, "HEAD"))
    head = resolve_revision(repo, "HEAD")
    base = _git_text(git_run(repo, "merge-base", base0, head))
    if base is None: return refused("base.invalid")
    if any(unit.id not in _completed(repo, base, story) for unit in units): return refused("units.incomplete")
    log = git_run(repo, "log", "-z", "--format=%H%n%B", f"{base}..HEAD")
    if log is None or log.returncode != 0: raise _repo_error()
    rounds = sum(trailer_round(raw.decode("utf-8", "replace"), story) is not None for raw in log.stdout.split(b"\x00") if raw)
    return data, hashlib.sha256(data).hexdigest(), units, config, base, head, rounds

@beddel_tool(name="profile_fix_reconcile", description="fix", category="profile")
def profile_fix_reconcile(repo_path: str, story_key: str, spec_path: str, branch: str, base_ref: str, change_id: str, max_fix_rounds: int, prior: Mapping[str, Any] | None) -> dict[str, Any]:
    checked = _inputs(repo_path, story_key, spec_path, branch, base_ref, change_id, max_fix_rounds)
    if isinstance(checked, dict): return checked
    repo, story, spec, branch, base_ref, change, bound = checked
    fail = lambda reason, **values: _bad(story, reason, **values)
    if prior is None: return fail("reconcile.failed")
    if prior != {} and (not isinstance(prior, Mapping) or prior.get("stage") != "verify-and-fix" or prior.get("story_key") != story): return fail("state.mismatch")
    try:
        if prior != {} and (prior.get("outcome") is not None or prior.get("fix") is True):
            if prior.get("outcome") in ("failed", "refused") and prior.get("fix") is not True and prior.get("head") is None:
                return dict(prior)
            head = resolve_revision(repo, "HEAD")
            return fail("head.moved", head=head) if head != prior.get("head") else dict(prior)
        if prior != {} and prior.get("verify") not in (False, True): return fail("state.mismatch")
        state = _repo_state(repo, story, spec, branch, base_ref, change)
        if isinstance(state, dict): return state
        _data, digest, units, config, base, head, rounds = state
        if prior.get("verify") is True and head != prior.get("head"): return fail("head.moved", base=base, head=head, rounds=rounds)
        try: report, item = _report(repo, change, head)
        except ProfileError: return fail("report.unreadable", base=base, head=head, rounds=rounds)
        scope = ", ".join(scope_paths(units))
        if report is None:
            refs = _state_refs(spec, digest, branch, base, head, change, rounds)
            return fail("verify.failed", **refs) if prior.get("verify") is True else _result(story, None, None, refs, verify=True, spec_sha256=digest, base=base, head=head, rounds=rounds, scope=scope)
        outcome, reason = decision(report, rounds, bound)
        findings = fix_findings(report)
        text = json.dumps(findings, sort_keys=True, separators=(",", ":"))
        prior_refs = prior.get("refs") if prior.get("verify") is True else None
        commit = prior_refs.get("commit") if isinstance(prior_refs, Mapping) else None
        refs = _state_refs(spec, digest, branch, base, head, change, rounds, report=item, findings=len(findings), commit=commit)
        if outcome is not None: return _result(story, outcome, reason, refs, spec_sha256=digest, base=base, head=head, rounds=rounds, findings=text, scope=scope)
        if len(text.encode()) > MAX_FINDINGS_BYTES: return fail("findings.too_large", **refs)
        if _TOKEN.search(text): return fail("secret.detected", **refs)
        baseline = _run_gates(repo, config)
        if changed_paths(repo) - {spec}: return fail("gate.changed_tree", **refs)
        return _result(story, None, None, {**refs, "round": rounds + 1}, verify=False, fix=True, spec_sha256=digest, base=base, head=head, round=rounds + 1, rounds=rounds, findings=text, scope=scope, baseline=baseline)
    except ProfileError: return fail("reconcile.failed")
    except Exception:  # noqa: BLE001
        return fail("reconcile.failed")

@beddel_tool(name="profile_fix_settle", description="fix", category="profile")
def profile_fix_settle(repo_path: str, story_key: str, spec_path: str, branch: str, base_ref: str, change_id: str, prepare: Mapping[str, Any] | None, agent: Mapping[str, Any] | None = None) -> dict[str, Any]:
    checked = _inputs(repo_path, story_key, spec_path, branch, base_ref, change_id, MAX_FIX_ROUNDS)
    if isinstance(checked, dict): return checked
    repo, story, spec, branch, base_ref, change, _ = checked
    fail = lambda reason, **values: _bad(story, reason, **values)
    if prepare is None: return fail("reconcile.failed")
    if not isinstance(prepare, Mapping) or prepare.get("stage") != "verify-and-fix" or prepare.get("story_key") != story: return fail("state.mismatch")
    if prepare.get("fix") is not True: return dict(prepare)
    if not isinstance(agent, Mapping): return fail("agent.failed")
    try:
        head = resolve_revision(repo, "HEAD")
        if _symbolic_branch(repo) != branch: return fail("branch.moved", head=head)
        if head != prepare.get("head"): return fail("head.moved", head=head)
        data, error = _read_spec(repo, spec)
        if error is not None or data is None: return fail("spec.changed", head=head)
        digest = hashlib.sha256(data).hexdigest()
        if prepare.get("spec_sha256") != digest: return fail("spec.changed", head=head)
        units = spec_units(data, story)
        if units is None: return fail("spec.changed", head=head)
        paths, scope = scope_paths(units), ", ".join(scope_paths(units))
        round_, rounds = prepare.get("round"), prepare.get("rounds")
        if prepare.get("scope_paths") != scope or type(round_) is not int or not 1 <= round_ <= MAX_FIX_ROUNDS or type(rounds) is not int or rounds != round_ - 1: return fail("state.mismatch", head=head)
        config = load_config()
        names = [f"{i:02d}-{argv[0]}" for i, argv in enumerate(config.gate_commands, 1)]
        baseline = prepare.get("baseline")
        if not isinstance(baseline, list) or any(not isinstance(item, Mapping) for item in baseline) or [item.get("name") for item in baseline] != names: return fail("state.mismatch", head=head, rounds=round_)
        if any(resolve_executable(argv[0]) is None for argv in config.gate_commands): return fail("gate.unavailable", head=head, rounds=round_)
        current = changed_paths(repo) - {spec}
        if not current: return fail("fix.empty", head=head, rounds=round_)
        outside = sum(not covered(paths, path) for path in current)
        if outside: return fail("scope.exceeded", head=head, rounds=round_, out_of_scope=outside)
        candidate = _candidate_tree(repo, tuple(sorted(current)))
        metadata = front_matter(data)
        if metadata is None: return fail("spec.changed", head=head, rounds=round_)
        base = prepare.get("base")
        if not isinstance(base, str): return fail("state.mismatch", head=head, rounds=round_)
        diff, truncated = diff_text(repo, base, candidate, int(metadata["size_cap_bytes"]))
        diff_bytes = len(diff.encode())
        if truncated:
            full, still = diff_text(repo, base, candidate, 262144)
            return fail("size.exceeded", base=base, head=head, rounds=round_, diff_bytes=len(full.encode()) if not still else int(metadata["size_cap_bytes"]) + 1)
        if _TOKEN.search("\n".join(line for line in diff.splitlines() if line.startswith("+"))): return fail("secret.detected", base=base, head=head, rounds=round_, diff_bytes=diff_bytes)
        gates = _run_gates(repo, config)
        after = changed_paths(repo) - {spec}
        if after != current or _candidate_tree(repo, tuple(sorted(after))) != candidate: return fail("gate.changed_tree", base=base, head=head, rounds=round_, diff_bytes=diff_bytes)
        regressed = [entry["name"] for entry, old in zip(gates, baseline) if old.get("exit_code") == 0 and (entry["timed_out"] or entry["exit_code"] != 0)]
        if regressed: return fail("gate.regressed", base=base, head=head, rounds=round_, diff_bytes=diff_bytes, regressed=", ".join(regressed))
        subject, trailers = fix_message(story, round_)
        present = [path for path in sorted(current) if os.path.lexists(repo / path)]
        added = git_run(repo, "add", "-A", "--", *present) if present else None
        if present and (added is None or added.returncode != 0): return fail("commit.failed", base=base, head=head, rounds=round_, diff_bytes=diff_bytes)
        committed = git_run(repo, "commit", "-q", "-m", subject, "-m", trailers, "--only", "--", *sorted(current), timeout=120)
        if committed is None or committed.returncode != 0: return fail("commit.failed", base=base, head=head, rounds=round_, diff_bytes=diff_bytes)
        new_head = resolve_revision(repo, "HEAD")
        parent, tree = _git_text(git_run(repo, "rev-parse", "HEAD^")), _git_text(git_run(repo, "rev-parse", "HEAD^{tree}"))
        message = _git_text(git_run(repo, "show", "-s", "--format=%B", "HEAD"))
        if parent != head or tree != candidate or message is None or trailer_round(message, story) != round_: return fail("commit.changed", base=base, head=new_head, commit=new_head, rounds=round_, diff_bytes=diff_bytes)
        refs = _refs(spec_path=spec, branch=branch, base=base, head=new_head, commit=new_head, change_id=change, round=round_, rounds=round_, diff_bytes=diff_bytes)
        return _result(story, None, None, refs, verify=True, spec_sha256=digest, base=base, head=new_head, round=round_, rounds=round_, scope=scope)
    except ProfileError: return fail("settle.failed")
    except Exception:  # noqa: BLE001
        return fail("settle.failed")
# fmt: on
