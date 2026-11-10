"""Contract and I/O matrix coverage for the implement stage."""

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

STORY = "7-4-implement-workflow-turns-a-spec-into-a-branch-and-commits"
SPEC_PATH = "specs/story.md"
BRANCH = "feat/story-7-4"


def spec_bytes(
    units: list[dict[str, object]] | None = None, *, cap: int = 64000
) -> bytes:
    values = units or [
        {"id": "u1", "paths": ["src/one.py"], "subject": "feat(core): add one"},
        {"id": "u2", "paths": ["src/two.py"], "subject": "feat(core): add two"},
    ]
    return (
        (
            f"---\nstory_key: {STORY}\nrequirements: [FR-10]\n"
            "repositories: [.]\ndependencies: []\n"
            f"size_cap_bytes: {cap}\nunits: {values!r}\n---\n\n# Spec\n"
        )
        .replace("'", '"')
        .encode()
    )


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = init_repo(tmp_path / "repo")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "src").mkdir()
    (repo / "src" / "base.py").write_text("base = True\n")
    (repo / SPEC_PATH).parent.mkdir()
    (repo / SPEC_PATH).write_bytes(spec_bytes())
    base = commit_all(repo, "base")
    (repo / SPEC_PATH).write_bytes(spec_bytes())
    return repo, base


def _prepare(
    repo: Path, base: str, monkeypatch: pytest.MonkeyPatch
) -> dict[str, object]:
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(repo.parent))
    monkeypatch.setenv("HOME", str(repo.parent / "home"))
    return profile_implement_prepare(str(repo), STORY, SPEC_PATH, BRANCH, base)


def test_pure_unit_contract() -> None:
    units = spec_units(spec_bytes(), STORY)
    assert units == (
        Unit("u1", ("src/one.py",), "feat(core): add one"),
        Unit("u2", ("src/two.py",), "feat(core): add two"),
    )
    assert (
        spec_units(
            spec_bytes([{"id": "bad id", "paths": ["x"], "subject": "feat: x"}]), STORY
        )
        is None
    )
    assert branch_reason("main", "origin/main") == "branch.protected"
    assert branch_reason("feat/x", "feat/x") == "branch.protected"
    assert branch_reason("../bad", "main") == "branch.invalid"
    assert branch_reason("feat/x", "main") is None
    assert covered(("src",), "src/a.py")
    assert covered(("src/a.py",), "src/a.py")
    assert not covered(("src/a.py",), "src/ab.py")
    subject, trailers = commit_message(Unit("u1", ("x",), "feat: x"), STORY)
    assert subject == "feat: x"
    assert trailer_unit(f"{subject}\n\n{trailers}\n", STORY) == "u1"
    assert trailer_unit(f"{trailers}\n{trailers}\n", STORY) is None


def test_first_resume_complete_and_failure_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    prepared = _prepare(repo, base, monkeypatch)
    assert prepared["implement"] is True
    (repo / "src" / "one.py").write_text("one = 1\n")
    first = profile_implement_settle(
        str(repo), STORY, SPEC_PATH, BRANCH, base, prepared, agent={}
    )
    assert first["reason"] == "unit.committed"
    first_head = git(repo, "rev-parse", "HEAD")

    prepared2 = _prepare(repo, base, monkeypatch)
    assert prepared2["unit_id"] == "u2"
    (repo / "src" / "two.py").write_text("two = 2\n")
    second = profile_implement_settle(
        str(repo), STORY, SPEC_PATH, BRANCH, base, prepared2, agent={}
    )
    assert second["reason"] == "unit.committed"
    assert second["refs"]["completed"] == 2

    prepared3 = _prepare(repo, base, monkeypatch)
    assert prepared3["reason"] == "units.complete"
    assert git(repo, "rev-parse", "HEAD") == second["refs"]["head"]
    complete = profile_implement_settle(
        str(repo), STORY, SPEC_PATH, BRANCH, base, prepared3
    )
    assert complete["reason"] == "units.complete"
    assert git(repo, "rev-parse", "HEAD") == second["refs"]["head"]
    assert first_head != second["refs"]["head"]


def test_refusal_dirty_agent_scope_empty_and_branch_tip_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(repo.parent))
    monkeypatch.setenv("HOME", str(repo.parent / "home"))
    (repo / "unexpected.txt").write_text("dirty\n")
    before = git(repo, "rev-parse", "HEAD")
    dirty = profile_implement_prepare(str(repo), STORY, SPEC_PATH, BRANCH, base)
    assert dirty["reason"] == "worktree.dirty"
    assert git(repo, "rev-parse", "HEAD") == before
    (repo / "unexpected.txt").unlink()
    prepared = _prepare(repo, base, monkeypatch)
    assert (
        profile_implement_settle(str(repo), STORY, SPEC_PATH, BRANCH, base, prepared)[
            "reason"
        ]
        == "agent.failed"
    )
    empty = profile_implement_settle(
        str(repo), STORY, SPEC_PATH, BRANCH, base, prepared, agent={}
    )
    assert empty["reason"] == "unit.empty"
    (repo / "outside.py").write_text("outside\n")
    out = profile_implement_settle(
        str(repo), STORY, SPEC_PATH, BRANCH, base, prepared, agent={}
    )
    assert out["reason"] == "scope.exceeded"
    assert git(repo, "rev-parse", "HEAD") == before


def test_gate_regression_token_and_size_overflow_leave_tip_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    prepared = _prepare(repo, base, monkeypatch)
    (repo / "src" / "one.py").write_text("one = 1\n")
    monkeypatch.setenv("STUB_EXIT_PYTEST", "1")
    regressed = profile_implement_settle(
        str(repo), STORY, SPEC_PATH, BRANCH, base, prepared, agent={}
    )
    assert regressed["reason"] == "gate.regressed"
    monkeypatch.delenv("STUB_EXIT_PYTEST")

    repo2, base2 = _repo(tmp_path / "token")
    prepared2 = _prepare(repo2, base2, monkeypatch)
    token_value = "gh" + "p_" + "A" * 36
    token_before = git(repo2, "rev-parse", "HEAD")
    (repo2 / "src" / "one.py").write_text(f"token = '{token_value}'\n")
    token = profile_implement_settle(
        str(repo2), STORY, SPEC_PATH, BRANCH, base2, prepared2, agent={}
    )
    assert token["reason"] == "secret.detected"
    assert token_value not in repr(token)
    assert git(repo2, "rev-parse", "HEAD") == token_before

    repo3, base3 = _repo(tmp_path / "size")
    (repo3 / SPEC_PATH).write_bytes(spec_bytes(cap=10))
    prepared3 = _prepare(repo3, base3, monkeypatch)
    (repo3 / "src" / "one.py").write_text("x = " + "a" * 100 + "\n")
    size = profile_implement_settle(
        str(repo3), STORY, SPEC_PATH, BRANCH, base3, prepared3, agent={}
    )
    assert size["reason"] == "size.exceeded"


def test_gate_changed_tree_stops_without_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    prepared = _prepare(repo, base, monkeypatch)
    gate_bin = Path(os.environ["PATH"].split(os.pathsep)[0])
    (gate_bin / "ruff").write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "Path('gate-output.txt').write_text('changed')\n"
    )
    (gate_bin / "ruff").chmod(0o755)
    (repo / "src" / "one.py").write_text("one = 1\n")
    result = profile_implement_settle(
        str(repo), STORY, SPEC_PATH, BRANCH, base, prepared, agent={}
    )
    assert result["reason"] == "gate.changed_tree"
    assert git(repo, "rev-parse", "HEAD") == base


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("story", "story_key.invalid"),
        ("path", "path.invalid"),
        ("branch", "branch.invalid"),
        ("protected", "branch.protected"),
        ("base", "base.invalid"),
        ("cwd", "cwd.mismatch"),
        ("absent", "spec.absent"),
        ("unreadable", "spec.unreadable"),
        ("incomplete", "spec.incomplete"),
        ("units", "units.invalid"),
        ("gate", "gate.unavailable"),
    ],
)
def test_prepare_refusals_keep_branch_tip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    reason: str,
) -> None:
    repo, base = _repo(tmp_path / case)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path / case))
    monkeypatch.setenv("HOME", str(tmp_path / case / "home"))
    before = git(repo, "rev-parse", "HEAD")
    story, spec, branch, base_ref = STORY, SPEC_PATH, BRANCH, base
    if case == "story":
        story = "BAD KEY"
    elif case == "path":
        spec = "../outside.md"
    elif case == "branch":
        branch = "Bad Branch"
    elif case == "protected":
        branch = "main"
    elif case == "base":
        base_ref = "missing-base"
    elif case == "cwd":
        (tmp_path / case / "elsewhere").mkdir()
        monkeypatch.chdir(tmp_path / case / "elsewhere")
    elif case == "absent":
        (repo / spec).unlink()
    elif case == "unreadable":
        (repo / spec).unlink()
        (repo / spec).mkdir()
    elif case == "incomplete":
        (repo / spec).write_bytes(b"unfinished")
    elif case == "units":
        (repo / spec).write_bytes(
            spec_bytes(
                [{"id": "bad id", "paths": ["src/one.py"], "subject": "feat: bad"}]
            )
        )
    else:
        original = implement_tools.resolve_executable
        monkeypatch.setattr(
            implement_tools,
            "resolve_executable",
            lambda name: None if name == "ruff" else original(name),
        )
    result = profile_implement_prepare(str(repo), story, spec, branch, base_ref)
    assert result["reason"] == reason
    assert git(repo, "rev-parse", "HEAD") == before


def test_checkout_failure_and_prepare_failure_are_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    prepared = _prepare(repo, base, monkeypatch)
    assert prepared["implement"] is True
    monkeypatch.chdir(repo)
    original = implement_tools.git_run

    def fail_switch(repo_path: Path, *args: str, **kwargs: object) -> object:
        if args[:2] == ("switch", "-q"):
            return type("Result", (), {"returncode": 1, "stdout": b""})()
        return original(repo_path, *args, **kwargs)

    monkeypatch.setattr(implement_tools, "git_run", fail_switch)
    failed = profile_implement_prepare(str(repo), STORY, SPEC_PATH, "feat/other", base)
    assert failed["reason"] == "checkout.failed"
    monkeypatch.setattr(implement_tools, "git_run", original)
    monkeypatch.setattr(
        implement_tools,
        "load_config",
        lambda: (_ for _ in ()).throw(implement_tools.ProfileError("x", "x")),
    )
    prepared_failed = profile_implement_prepare(
        str(repo), STORY, SPEC_PATH, BRANCH, base
    )
    assert prepared_failed["reason"] == "prepare.failed"
    assert git(repo, "rev-parse", "HEAD") == base


def test_settle_rejects_forged_prepare_and_changed_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    prepared = _prepare(repo, base, monkeypatch)
    before = git(repo, "rev-parse", "HEAD")
    forged = dict(prepared)
    forged["unit_id"] = "u2"
    mismatch = profile_implement_settle(
        str(repo), STORY, SPEC_PATH, BRANCH, base, forged, agent={}
    )
    assert mismatch["reason"] == "prepare.mismatch"
    (repo / SPEC_PATH).write_bytes(spec_bytes(cap=63999))
    changed = profile_implement_settle(
        str(repo), STORY, SPEC_PATH, BRANCH, base, prepared, agent={}
    )
    assert changed["reason"] == "spec.changed"
    assert git(repo, "rev-parse", "HEAD") == before


def test_base_red_gate_is_advisory_and_commit_failure_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path / "red")
    monkeypatch.setenv("STUB_EXIT_PYTEST", "1")
    prepared = _prepare(repo, base, monkeypatch)
    (repo / "src" / "one.py").write_text("one\n")
    result = profile_implement_settle(
        str(repo), STORY, SPEC_PATH, BRANCH, base, prepared, agent={}
    )
    assert result["reason"] == "unit.committed"

    repo2, base2 = _repo(tmp_path / "hook")
    hook = repo2 / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    prepared2 = _prepare(repo2, base2, monkeypatch)
    (repo2 / "src" / "one.py").write_text("one\n")
    failed = profile_implement_settle(
        str(repo2), STORY, SPEC_PATH, BRANCH, base2, prepared2, agent={}
    )
    assert failed["reason"] == "commit.failed"
    assert git(repo2, "rev-parse", "HEAD") == base2


def test_commit_changed_is_detected_after_hook_rewrites_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nprintf altered > src/one.py\ngit add src/one.py\n")
    hook.chmod(0o755)
    prepared = _prepare(repo, base, monkeypatch)
    (repo / "src" / "one.py").write_text("one\n")
    result = profile_implement_settle(
        str(repo), STORY, SPEC_PATH, BRANCH, base, prepared, agent={}
    )
    assert result["reason"] == "commit.changed"
    assert git(repo, "rev-parse", "HEAD") != base
