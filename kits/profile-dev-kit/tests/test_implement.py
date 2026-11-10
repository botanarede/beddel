from __future__ import annotations

import os
from pathlib import Path

import pytest
from beddel_profile_dev.implement import (
    Unit,
    branch_reason,
    commit_message,
    covered,
    spec_units,
    trailer_unit,
)
from beddel_profile_dev.tools import implement as implement_tools
from beddel_profile_dev.tools.implement import (
    profile_implement_prepare,
    profile_implement_settle,
)

from ._helpers import commit_all, git, init_repo, stub_gate_tools

# fmt: off
STORY = "7-4-implement-workflow-turns-a-spec-into-a-branch-and-commits"
SPEC_PATH = "specs/story.md"
BRANCH = "feat/story-7-4"

def spec_bytes(units=None, *, cap=64000):
    values = units or [{"id":"u1","paths":["src/one.py"],"subject":"feat(core): add one"},{"id":"u2","paths":["src/two.py"],"subject":"feat(core): add two"}]
    return (f"---\nstory_key: {STORY}\nrequirements: [FR-10]\nrepositories: [.]\ndependencies: []\nsize_cap_bytes: {cap}\nunits: {values!r}\n---\n\n# Spec\n").replace("'", '"').encode()

def _repo(root, units=None, spec=SPEC_PATH, track=True):
    repo = init_repo(root / "repo")
    git(repo,"config","user.name","Fixture"); git(repo,"config","user.email","fixture@example.invalid")
    (repo / "src").mkdir(); (repo / "src" / "base.py").write_text("base = True\n")
    (repo / spec).parent.mkdir(exist_ok=True); (repo / spec).write_bytes(spec_bytes(units))
    base = commit_all(repo,"base")
    if not track: (repo / spec).unlink(); (repo / spec).write_bytes(spec_bytes(units))
    return repo, base

def _prepare(repo, base, patch, spec=SPEC_PATH, branch=BRANCH):
    patch.chdir(repo); patch.setenv("PATH",stub_gate_tools(repo.parent)); patch.setenv("HOME",str(repo.parent / "home"))
    return profile_implement_prepare(str(repo),STORY,spec,branch,base)

def _settle(repo, base, prepared, spec=SPEC_PATH):
    return profile_implement_settle(str(repo),STORY,spec,BRANCH,base,prepared,agent={})

def test_pure_unit_contract():
    assert spec_units(spec_bytes(),STORY) == (Unit("u1",("src/one.py",),"feat(core): add one"),Unit("u2",("src/two.py",),"feat(core): add two"))
    assert spec_units(spec_bytes([{"id":"bad id","paths":["x"],"subject":"feat: x"}]),STORY) is None
    assert branch_reason("main","origin/main") == "branch.protected"; assert branch_reason("feat/x","feat/x") == "branch.protected"
    assert branch_reason("../bad","main") == branch_reason("feat.lock/x","main") == "branch.invalid"; assert branch_reason("feat/x","main") is None
    assert covered(("src",),"src/a.py") and covered(("src/a.py",),"src/a.py") and not covered(("src/a.py",),"src/ab.py")
    subject, trailers = commit_message(Unit("u1",("x",),"feat: x"),STORY)
    assert subject == "feat: x" and trailer_unit(f"{subject}\n\n{trailers}\n",STORY) == "u1"
    assert trailer_unit(f"{trailers}\n{trailers}\n",STORY) is None

def test_first_resume_complete_and_failure_paths(tmp_path, monkeypatch):
    repo, base = _repo(tmp_path); prepared = _prepare(repo,base,monkeypatch); assert prepared["implement"]
    (repo / "src/one.py").write_text("one = 1\n"); first = _settle(repo,base,prepared); assert first["reason"] == "unit.committed"
    assert first["refs"]["commit"] == first["refs"]["head"] and (first["refs"]["completed"],first["refs"]["remaining"]) == (1,1)
    assert git(repo,"show","--name-only","--format=","HEAD").split() == ["src/one.py"] and "Implementation-Unit: u1" in git(repo,"show","-s","--format=%B","HEAD")
    prepared2 = _prepare(repo,base,monkeypatch); assert prepared2["unit_id"] == "u2"; (repo / "src/two.py").write_text("two = 2\n"); second = _settle(repo,base,prepared2); assert second["refs"]["completed"] == 2
    head = git(repo,"rev-parse","HEAD"); prepared3 = _prepare(repo,base,monkeypatch); assert prepared3["reason"] == "units.complete"; assert _settle(repo,base,prepared3)["reason"] == "units.complete"; assert git(repo,"rev-parse","HEAD") == head

def test_dirty_agent_scope_empty_and_tip_unchanged(tmp_path, monkeypatch):
    repo, base = _repo(tmp_path); patch = monkeypatch; patch.chdir(repo); patch.setenv("PATH",stub_gate_tools(repo.parent)); patch.setenv("HOME",str(repo.parent / "home")); before = git(repo,"rev-parse","HEAD")
    (repo / "unexpected.txt").write_text("dirty\n"); assert profile_implement_prepare(str(repo),STORY,SPEC_PATH,BRANCH,base)["reason"] == "worktree.dirty"; (repo / "unexpected.txt").unlink()
    prepared = _prepare(repo,base,patch); assert profile_implement_settle(str(repo),STORY,SPEC_PATH,BRANCH,base,prepared)["reason"] == "agent.failed"; assert _settle(repo,base,prepared)["reason"] == "unit.empty"
    (repo / "outside.py").write_text("outside\n"); assert _settle(repo,base,prepared)["reason"] == "scope.exceeded"; assert git(repo,"rev-parse","HEAD") == before

def test_regression_token_and_size(tmp_path, monkeypatch):
    repo, base = _repo(tmp_path); prepared = _prepare(repo,base,monkeypatch); (repo / "src/one.py").write_text("one\n"); monkeypatch.setenv("STUB_EXIT_PYTEST","1"); assert _settle(repo,base,prepared)["reason"] == "gate.regressed"; monkeypatch.delenv("STUB_EXIT_PYTEST")
    repo2, base2 = _repo(tmp_path / "token"); prepared2 = _prepare(repo2,base2,monkeypatch); token = "gh"+"p_"+"A"*36; before = git(repo2,"rev-parse","HEAD"); (repo2 / "src/one.py").write_text(token); result = _settle(repo2,base2,prepared2); assert result["reason"] == "secret.detected" and token not in repr(result) and git(repo2,"rev-parse","HEAD") == before
    repo3, base3 = _repo(tmp_path / "size"); (repo3 / SPEC_PATH).write_bytes(spec_bytes(cap=10)); prepared3 = _prepare(repo3,base3,monkeypatch); (repo3 / "src/one.py").write_text("x = "+"a"*100+"\n"); assert _settle(repo3,base3,prepared3)["reason"] == "size.exceeded"

@pytest.mark.parametrize(("case","reason"),[("story","story_key.invalid"),("path","path.invalid"),("branch","branch.invalid"),("protected","branch.protected"),("base","base.invalid"),("cwd","cwd.mismatch"),("absent","spec.absent"),("unreadable","spec.unreadable"),("incomplete","spec.incomplete"),("units","units.invalid"),("gate","gate.unavailable")])
def test_prepare_refusals_keep_tip(tmp_path, monkeypatch, case, reason):
    repo, base = _repo(tmp_path / case); monkeypatch.chdir(repo); monkeypatch.setenv("PATH",stub_gate_tools(tmp_path / case)); monkeypatch.setenv("HOME",str(tmp_path / case / "home")); before = git(repo,"rev-parse","HEAD"); story,spec,branch,ref = STORY,SPEC_PATH,BRANCH,base
    if case == "story": story = "BAD KEY"
    elif case == "path": spec = "../outside.md"
    elif case == "branch": branch = "Bad Branch"
    elif case == "protected": branch = "main"
    elif case == "base": ref = "missing-base"
    elif case == "cwd": (tmp_path / case / "elsewhere").mkdir(); monkeypatch.chdir(tmp_path / case / "elsewhere")
    elif case == "absent": (repo / spec).unlink()
    elif case == "unreadable": (repo / spec).unlink(); (repo / spec).mkdir()
    elif case == "incomplete": (repo / spec).write_bytes(b"unfinished")
    elif case == "units": (repo / spec).write_bytes(spec_bytes([{"id":"bad id","paths":["src/one.py"],"subject":"feat: bad"}]))
    else:
        original = implement_tools.resolve_executable; monkeypatch.setattr(implement_tools,"resolve_executable",lambda name: None if name == "ruff" else original(name))
    assert profile_implement_prepare(str(repo),story,spec,branch,ref)["reason"] == reason and git(repo,"rev-parse","HEAD") == before

def test_checkout_and_prepare_failure(tmp_path, monkeypatch):
    repo, base = _repo(tmp_path); _prepare(repo,base,monkeypatch); original = implement_tools.git_run
    def fail(repo_path, *args, **kwargs): return type("R",(),{"returncode":1,"stdout":b""})() if args[:2] == ("switch","-q") else original(repo_path,*args,**kwargs)
    monkeypatch.setattr(implement_tools,"git_run",fail); assert profile_implement_prepare(str(repo),STORY,SPEC_PATH,"feat/other",base)["reason"] == "checkout.failed"; monkeypatch.setattr(implement_tools,"git_run",original)
    monkeypatch.setattr(implement_tools,"load_config",lambda: (_ for _ in ()).throw(implement_tools.ProfileError("x","x"))); assert profile_implement_prepare(str(repo),STORY,SPEC_PATH,BRANCH,base)["reason"] == "prepare.failed"; assert git(repo,"rev-parse","HEAD") == base

def test_forged_prepare_and_changed_spec(tmp_path, monkeypatch):
    repo, base = _repo(tmp_path); prepared = _prepare(repo,base,monkeypatch); forged = dict(prepared); forged["unit_id"] = "u2"; assert _settle(repo,base,forged)["reason"] == "prepare.mismatch"; (repo / SPEC_PATH).write_bytes(spec_bytes(cap=63999)); assert _settle(repo,base,prepared)["reason"] == "spec.changed"

def test_base_red_hook_and_commit_changed(tmp_path, monkeypatch):
    repo, base = _repo(tmp_path / "red"); monkeypatch.setenv("STUB_EXIT_PYTEST","1"); prepared = _prepare(repo,base,monkeypatch); (repo / "src/one.py").write_text("one\n"); assert _settle(repo,base,prepared)["reason"] == "unit.committed"; monkeypatch.delenv("STUB_EXIT_PYTEST")
    repo2, base2 = _repo(tmp_path / "hook"); hook = repo2 / ".git/hooks/pre-commit"; hook.write_text("#!/bin/sh\nexit 1\n"); hook.chmod(0o755); prepared2 = _prepare(repo2,base2,monkeypatch); (repo2 / "src/one.py").write_text("one\n"); assert _settle(repo2,base2,prepared2)["reason"] == "commit.failed" and git(repo2,"rev-parse","HEAD") == base2
    repo3, base3 = _repo(tmp_path / "changed"); hook = repo3 / ".git/hooks/commit-msg"; hook.write_text("#!/bin/sh\nhead -n1 \"$1\" > \"$1.x\" && mv \"$1.x\" \"$1\"\n"); hook.chmod(0o755); prepared3 = _prepare(repo3,base3,monkeypatch); (repo3 / "src/one.py").write_text("one\n"); assert _settle(repo3,base3,prepared3)["reason"] == "commit.changed"

def test_changed_paths_and_gate_rewrite(tmp_path, monkeypatch):
    spec = "src/spec.md"; units = [{"id":"u1","paths":["src","tests/test_one.py"],"subject":"feat: one"}]; repo, base = _repo(tmp_path,units,spec,False); prepared = _prepare(repo,base,monkeypatch,spec); (repo / "src/one.py").write_text("one\n"); result = _settle(repo,base,prepared,spec); assert result["reason"] == "unit.committed" and git(repo,"show","--name-only","--format=","HEAD").split() == ["src/one.py"] and "Story-Key: "+STORY in git(repo,"show","-s","--format=%B","HEAD")
    repo2, base2 = _repo(tmp_path / "gate"); prepared2 = _prepare(repo2,base2,monkeypatch); gate = Path(os.environ["PATH"].split(os.pathsep)[0]) / "ruff"; gate.write_text("#!/usr/bin/env python3\nfrom pathlib import Path\nPath('src/one.py').write_text('rewritten ghp_' + 'B' * 36)\n"); gate.chmod(0o755); (repo2 / "src/one.py").write_text("one\n"); assert _settle(repo2,base2,prepared2)["reason"] == "gate.changed_tree" and git(repo2,"rev-parse","HEAD") == base2

def test_size_baseline_and_invalid_branches(tmp_path, monkeypatch):
    repo, base = _repo(tmp_path / "measure"); prepared = _prepare(repo,base,monkeypatch); (repo / "src/one.py").write_text("x = "+"a"*100+"\n"); measured = _settle(repo,base,prepared); repo2, base2 = _repo(tmp_path / "cap"); (repo2 / SPEC_PATH).write_bytes(spec_bytes(cap=measured["refs"]["diff_bytes"]-1)); prepared2 = _prepare(repo2,base2,monkeypatch); (repo2 / "src/one.py").write_text("x = "+"a"*100+"\n"); assert _settle(repo2,base2,prepared2)["reason"] == "size.exceeded"
    for branch in ("feat/x.lock","feat/.x"):
        repo3, base3 = _repo(tmp_path / branch.replace("/","_")); monkeypatch.chdir(repo3); monkeypatch.setenv("PATH",stub_gate_tools(tmp_path)); assert profile_implement_prepare(str(repo3),STORY,SPEC_PATH,branch,base3)["reason"] == "branch.invalid"
    repo4, base4 = _repo(tmp_path / "baseline"); prepared4 = _prepare(repo4,base4,monkeypatch); prepared4["baseline"] = [{"name":"wrong"}]; (repo4 / "src/one.py").write_text("one\n"); assert _settle(repo4,base4,prepared4)["reason"] == "prepare.mismatch"

def test_rename_head_base_foreign_trailer_and_unborn_head(tmp_path, monkeypatch):
    repo, base = _repo(tmp_path / "mv", [{"id":"u1","paths":["src"],"subject":"feat: one"}]); prepared = _prepare(repo,base,monkeypatch); git(repo,"mv","src/base.py","src/new.py"); assert _settle(repo,base,prepared)["reason"] == "unit.committed"
    repo, base = _repo(tmp_path / "head"); prepared = _prepare(repo,"HEAD",monkeypatch); (repo / "src/one.py").write_text("one\n"); assert _settle(repo,"HEAD",prepared)["reason"] == "unit.committed"; assert _prepare(repo,"HEAD",monkeypatch)["reason"] == "branch.protected"
    repo, base = _repo(tmp_path / "foreign"); git(repo,"switch","-q","-c",BRANCH); git(repo,"commit","-q","--allow-empty","-m","feat: x","-m",f"Story-Key: {STORY}\nImplementation-Unit: zz"); git(repo,"switch","-q","-"); assert _prepare(repo,base,monkeypatch)["refs"]["completed"] == 0
    repo, base = _repo(tmp_path / "orphan"); prepared = _prepare(repo,base,monkeypatch); git(repo,"switch","-q","--orphan","x"); assert _settle(repo,base,prepared)["reason"] == "branch.moved"
# fmt: on
