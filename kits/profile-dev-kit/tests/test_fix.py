"""Pure and boundary tests for the verify-and-fix stage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from beddel_profile_dev.fix import (
    FIXABLE_REASONS,
    MAX_FIX_ROUNDS,
    decision,
    fix_findings,
    fix_message,
    report_at,
    scope_paths,
    trailer_round,
)
from beddel_profile_dev.implement import Unit
from beddel_profile_dev.inventory import validate_inventory
from beddel_profile_dev.tools.fix import profile_fix_reconcile, profile_fix_settle

from ._helpers import commit_all, git, good, init_repo, stub_gate_tools
from .test_implement import BRANCH, SPEC_PATH, STORY, spec_bytes


def test_fix_message_and_trailer_round_contract() -> None:
    subject, trailers = fix_message(STORY, 2)
    assert subject == "fix: apply verification fixes (round 2)"
    assert trailer_round(f"{subject}\n\n{trailers}\n", STORY) == 2
    assert trailer_round(f"{trailers}\n{trailers}\n", STORY) is None
    assert trailer_round(f"Story-Key: {STORY}\nFix-Round: 3", STORY) is None
    assert trailer_round("Story-Key: other\nFix-Round: 1", STORY) is None


def _report(revision: str, verdict: str = "has pendency") -> dict[str, object]:
    finding = {
        "source": "gate",
        "association": "requirement",
        "class": "gate-unit",
        "affected_point": "api",
        "criterion": "tests-pass",
        "kind": "gate",
        "between": ["implementation", "validation"],
        "detail": {"description": "failed"},
        "classification": "blocking",
    }
    return {
        "revision": revision,
        "verdict": verdict,
        "items": {
            "divergences": {"status": "present", "value": [finding, {"x": 2}]},
            "pendencies": {
                "status": "present",
                "value": [
                    {"reason": "finding_blocking", "finding_index": 0},
                    {"reason": "evidence_unrecorded"},
                    {"reason": "finding_unclassified", "finding_index": 0},
                    {"reason": "finding_blocking", "finding_index": 1},
                ],
            },
        },
    }


def test_report_selection_findings_scope_and_decision() -> None:
    first = _report("a" * 40)
    history = [
        {"ref": "one", "sha256": "a", "content": first},
        {"ref": "two", "sha256": "b", "content": _report("b" * 40, "consistent")},
        {"ref": "three", "sha256": "c", "content": first},
    ]
    assert report_at(history, "a" * 40) == first
    findings = fix_findings(first)
    assert set(findings[0]) == {
        "source",
        "association",
        "class",
        "affected_point",
        "criterion",
        "kind",
        "between",
        "detail",
    }
    assert findings[0]["source"] == "gate"
    assert findings[1]["detail"] is None
    assert all("classification" not in finding for finding in findings)
    assert decision(first, 0, MAX_FIX_ROUNDS) == (None, None)
    assert decision(first, 2, MAX_FIX_ROUNDS) == ("stopped", "fix.bound_reached")
    assert decision(_report("a" * 40, "consistent"), 0, 2) == (
        "succeeded",
        "verdict.consistent",
    )
    no_fix = _report("a" * 40)
    no_fix["items"]["pendencies"]["value"] = [{"reason": "evidence_unrecorded"}]  # type: ignore[index]
    assert decision(no_fix, 0, 2) == ("stopped", "pendency.no_fixes")
    assert decision({"verdict": "unknown"}, 0, 2) == ("failed", "report.unreadable")
    assert FIXABLE_REASONS == {"finding_blocking", "finding_unclassified"}
    assert scope_paths(
        [Unit("b", ("tests", "src/b.py"), "feat: b"), Unit("a", ("src",), "feat: a")]
    ) == ("src", "src/b.py", "tests")


def _complete_repo(root: Path) -> tuple[Path, str]:
    repo = init_repo(root / "repo")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "src").mkdir()
    (repo / "src" / "base.py").write_text("base = True\n")
    (repo / SPEC_PATH).parent.mkdir()
    (repo / SPEC_PATH).write_bytes(spec_bytes())
    base = commit_all(repo, "base")
    git(repo, "switch", "-q", "-c", BRANCH)
    (repo / "src" / "one.py").write_text("one = 1\n")
    git(repo, "add", "--", "src/one.py")
    git(
        repo,
        "commit",
        "-q",
        "-m",
        "feat: one",
        "-m",
        f"Story-Key: {STORY}\nImplementation-Unit: u1",
    )
    (repo / "src" / "two.py").write_text("two = 2\n")
    git(repo, "add", "--", "src/two.py")
    git(
        repo,
        "commit",
        "-q",
        "-m",
        "feat: two",
        "-m",
        f"Story-Key: {STORY}\nImplementation-Unit: u2",
    )
    return repo, base


def test_reconcile_refusals_and_settle_state_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _complete_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert (
        profile_fix_reconcile(str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", 3, {})[
            "reason"
        ]
        == "bound.invalid"
    )
    assert (
        profile_fix_reconcile(str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", 2, None)[
            "reason"
        ]
        == "reconcile.failed"
    )
    prepared = profile_fix_reconcile(
        str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", 2, {}
    )
    assert prepared["verify"] is True, (prepared["reason"], prepared["refs"])
    assert (
        profile_fix_settle(str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", prepared)
        == prepared
    )
    assert json.loads(json.dumps(prepared))["stage"] == "verify-and-fix"


def test_ac2_review_lens_fixture_is_a_valid_inventory() -> None:
    data = good()
    ids = ["blind-hunter", "edge-case-hunter", "verification-gap", "acceptance-auditor"]
    data["classes"] = [{"id": item, "kind": "review"} for item in ids]
    data["obligations"] = [
        {"class": item, "affected_point": "api", "criterion": "arch-ok"} for item in ids
    ]
    inventory, failures = validate_inventory(data, "v1")
    assert inventory is not None
    assert not failures


# fmt: off
@pytest.mark.parametrize("bound", [-1, True, "2", 3])
def test_reconcile_rejects_every_invalid_fix_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bound: object
) -> None:
    repo, base = _complete_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    result = profile_fix_reconcile(
        str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", bound, {}
    )
    assert result["reason"] == "bound.invalid"


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("story_key", "BAD!", "story_key.invalid"),
        ("spec_path", "../bad", "path.invalid"),
        ("branch", "BAD", "branch.invalid"),
        ("branch", "main", "branch.protected"),
        ("base_ref", "", "base.invalid"),
        ("change_id", "bad!", "change_id.invalid"),
    ],
)
def test_reconcile_rejects_input_refusal_reasons(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    expected: str,
) -> None:
    repo, base = _complete_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    args: dict[str, object] = {
        "repo_path": str(repo), "story_key": STORY, "spec_path": SPEC_PATH,
        "branch": BRANCH, "base_ref": base, "change_id": "c1", "max_fix_rounds": 2, "prior": {},
    }
    args[field] = value
    result = profile_fix_reconcile(**args)  # type: ignore[arg-type]
    assert result["reason"] == expected


@pytest.mark.parametrize("kind", [
    "branch.absent", "branch.not_current", "cwd.mismatch", "spec.absent",
    "spec.unreadable", "spec.incomplete", "units.invalid", "units.incomplete",
    "gate.unavailable",
])
def test_reconcile_refusals_forward_without_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    repo, base = _complete_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    if kind == "branch.absent": branch = "feat/missing"
    elif kind == "branch.not_current":
        branch = "feat/other"
        git(repo, "branch", branch)
    else: branch = BRANCH
    if kind == "cwd.mismatch": monkeypatch.chdir(tmp_path)
    elif kind == "spec.absent": (repo / SPEC_PATH).unlink()
    elif kind == "spec.unreadable":
        (repo / SPEC_PATH).unlink()
        (repo / SPEC_PATH).mkdir()
    elif kind == "spec.incomplete": (repo / SPEC_PATH).write_text("---\nstory_key: wrong\n---\n")
    elif kind == "units.invalid": monkeypatch.setattr("beddel_profile_dev.tools.fix.spec_units", lambda *_: None)
    elif kind == "units.incomplete": monkeypatch.setattr("beddel_profile_dev.tools.fix._completed", lambda *_: set())
    elif kind == "gate.unavailable": monkeypatch.setattr("beddel_profile_dev.tools.fix.resolve_executable", lambda *_: None)
    first = profile_fix_reconcile(str(repo), STORY, SPEC_PATH, branch, base, "c1", 2, {})
    assert first["reason"] == kind
    assert first["head"] is None
    second = profile_fix_reconcile(str(repo), STORY, SPEC_PATH, branch, base, "c1", 2, first)
    assert second == first
    assert first["refs"]["spec_path"] == SPEC_PATH
    assert first["refs"]["branch"] == branch
    assert first["refs"]["change_id"] == "c1"


def test_reconcile_gate_changed_tree_is_a_recordable_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _complete_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setattr(
        "beddel_profile_dev.tools.fix.profile_read_report",
        lambda *_: {"history": [{"ref": "report-1", "sha256": "hash", "content": _report(git(repo, "rev-parse", "HEAD"))}]},
    )
    def dirty_gate(*_: object) -> list[dict[str, object]]:
        (repo / "src" / "gate-created.py").write_text("x = 1\n")
        return []
    monkeypatch.setattr("beddel_profile_dev.tools.fix._run_gates", dirty_gate)
    result = profile_fix_reconcile(str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", 2, {})
    assert result["reason"] == "gate.changed_tree"
    assert result["refs"]["findings"] == 2
    assert not isinstance(result["refs"]["findings"], str)


def test_reconcile_unexpected_exception_is_recordable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _complete_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setattr("beddel_profile_dev.tools.fix._report", lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))
    result = profile_fix_reconcile(str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", 2, {})
    assert result["reason"] == "reconcile.failed"


def test_settle_unexpected_exception_is_recordable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _complete_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    prepare = {
        "stage": "verify-and-fix", "story_key": STORY, "fix": True,
        "head": git(repo, "rev-parse", "HEAD"),
        "spec_sha256": hashlib.sha256(spec_bytes()).hexdigest(),
        "scope_paths": "src/one.py, src/two.py", "round": 1, "rounds": 0,
        "base": base,
        "baseline": [{"name": name} for name in ("01-ruff", "02-ruff", "03-mypy", "04-pytest")],
    }
    monkeypatch.setattr("beddel_profile_dev.tools.fix.changed_paths", lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))
    result = profile_fix_settle(str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", prepare, {})
    assert result["reason"] == "settle.failed"


def _due_prepare(
    repo: Path, base: str, monkeypatch: pytest.MonkeyPatch
) -> dict[str, object]:
    head = git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(
        "beddel_profile_dev.tools.fix.profile_read_report",
        lambda *_: {"history": [{"ref": "r", "sha256": "s", "content": _report(head)}]},
    )
    return profile_fix_reconcile(str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", 2, {})


@pytest.mark.parametrize("case", [
    "agent.failed", "branch.moved", "head.moved", "spec.changed", "fix.empty",
    "scope.exceeded", "size.exceeded", "secret.detected", "gate.regressed",
    "base-red", "gate.changed_tree", "commit.failed",
])
def test_settle_boundary_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    repo, base = _complete_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    if case == "base-red": monkeypatch.setenv("STUB_EXIT_PYTEST", "1")
    prepare = _due_prepare(repo, base, monkeypatch)
    assert prepare["fix"] is True
    if case == "branch.moved":
        git(repo, "switch", "-q", "-c", "feat/other")
    elif case == "head.moved":
        commit_all(repo, "moved")
    elif case == "spec.changed":
        (repo / SPEC_PATH).write_bytes(spec_bytes() + b"changed\n")
    elif case == "scope.exceeded":
        (repo / "README.md").write_text("outside\n")
    elif case == "size.exceeded":
        monkeypatch.setattr("beddel_profile_dev.tools.fix.diff_text", lambda *_: ("diff", True))
        (repo / "src" / "one.py").write_text("one = 2\n")
    elif case == "secret.detected":
        (repo / "src" / "one.py").write_text("token = 'github_pat_" + "x" * 11 + "'\n")
    elif case in {"gate.regressed", "base-red"}:
        if case == "gate.regressed": monkeypatch.setenv("STUB_EXIT_PYTEST", "1")
        (repo / "src" / "one.py").write_text("one = 2\n")
    elif case == "gate.changed_tree":
        (repo / "src" / "one.py").write_text("one = 2\n")
        def dirty_gate(*_: object) -> list[dict[str, object]]:
            (repo / "src" / "extra.py").write_text("extra = 1\n")
            return prepare["baseline"]  # type: ignore[return-value]
        monkeypatch.setattr("beddel_profile_dev.tools.fix._run_gates", dirty_gate)
    elif case == "commit.failed":
        (repo / "src" / "one.py").write_text("one = 2\n")
        hook = repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
    result = profile_fix_settle(
        str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", prepare,
        None if case == "agent.failed" else {},
    )
    expected = None if case == "base-red" else ("agent.failed" if case == "agent.failed" else case)
    assert result["reason"] == expected
    if case == "base-red": assert result["verify"] is True


def test_reconcile_dirty_state_and_state_chain_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _complete_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    (repo / "src" / "untracked.py").write_text("x = 1\n")
    dirty = profile_fix_reconcile(str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", 2, {})
    assert dirty["reason"] == "worktree.dirty"
    (repo / "src" / "untracked.py").unlink()
    clean = profile_fix_reconcile(str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", 2, {})
    assert profile_fix_reconcile(str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", 2, {"stage": "x"})["reason"] == "state.mismatch"
    moved = dict(clean)
    moved["head"] = "f" * 40
    assert profile_fix_reconcile(str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", 2, moved)["reason"] == "head.moved"


# fmt: on


# fmt: off
@pytest.mark.parametrize("kind", ["findings.too_large", "secret.detected"])
def test_findings_handoff_limits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    repo, base = _complete_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    head = git(repo, "rev-parse", "HEAD")
    report = _report(head)
    value = "x" * 33000 if kind == "findings.too_large" else "github_pat_" + "x" * 11
    report["items"]["divergences"]["value"][0]["detail"] = value  # type: ignore[index]
    monkeypatch.setattr("beddel_profile_dev.tools.fix.profile_read_report", lambda *_: {"history": [{"ref": "r", "sha256": "s", "content": report}]})
    result = profile_fix_reconcile(str(repo), STORY, SPEC_PATH, BRANCH, base, "c1", 2, {})
    assert result["reason"] == kind

# fmt: on
