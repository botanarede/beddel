"""Pure and boundary tests for the verify-and-fix stage."""

from __future__ import annotations

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
    assert findings == [
        first["items"]["divergences"]["value"][0],
        first["items"]["divergences"]["value"][1],
    ]  # type: ignore[index]
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
