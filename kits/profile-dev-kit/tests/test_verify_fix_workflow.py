"""Shape and safety coverage for the verify-and-fix entry workflow."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from beddel.domain.kit import parse_kit_manifest
from beddel.domain.models import AgentResult, DefaultDependencies, StrategyType
from beddel.domain.parser import WorkflowParser
from beddel.domain.registry import PrimitiveRegistry
from beddel.primitives import register_builtins
from beddel.tools.kits import load_kit
from beddel_profile_dev import _adapters
from beddel_profile_dev.findings import (
    ASSESSMENT_BEGIN,
    ASSESSMENT_END,
    REVIEW_ASSESSMENT_SCHEMA,
)

from ._helpers import (
    FakeReviewAdapter,
    commit_all,
    git,
    good,
    init_repo,
    make_source,
    stub_gate_tools,
    write_version,
)

KIT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = KIT_ROOT / "workflows" / "verify-and-fix-story.yaml"


def test_workflow_shape_and_bound() -> None:
    document = yaml.safe_load(WORKFLOW_PATH.read_text())
    assert document["id"] == "verify-and-fix-story"
    assert document["requires_kits"] == ["profile-dev-kit", "agent-kiro-kit"]
    assert document["inputs"] == [
        "repo_path",
        "story_key",
        "spec_path",
        "branch",
        "base_ref",
        "change_id",
        "inventory_version",
    ]
    assert document["allowed_tools"] == [
        "profile_fix_reconcile",
        "profile_fix_settle",
        "profile_record_stage_outcome",
    ]
    assert "mcp_servers" not in document
    assert not any(
        word in document["allowed_tools"]
        for word in ("approve", "ratify", "integrate", "push", "publish")
    )
    steps = WorkflowParser.parse(WORKFLOW_PATH.read_text()).steps
    assert [step.id for step in steps] == [
        "reconcile",
        "verify",
        "round_1",
        "fix_1",
        "settle_1",
        "settle_1_stop",
        "verify_1",
        "round_2",
        "fix_2",
        "settle_2",
        "settle_2_stop",
        "verify_2",
        "close",
        "record",
    ]
    assert all(
        step.config.get("arguments", {}).get("max_fix_rounds") == 2
        for step in steps
        if step.id in {"reconcile", "round_1", "round_2", "close"}
    )
    agents = [step for step in steps if step.primitive == "agent-exec"]
    assert len(agents) == 2
    assert all(
        step.config["adapter"] == "kiro-cli"
        and step.config["sandbox"] == "workspace-write"
        and step.timeout <= 600
        for step in agents
    )
    nested = [step for step in steps if step.primitive == "call-agent"]
    assert len(nested) == 3
    assert all(step.config["workflow"] == "verify-change.yaml" for step in nested)
    assert all(
        list(step.config["inputs"])
        == [
            "repo_path",
            "change_id",
            "base",
            "revision",
            "inventory_version",
        ]
        for step in nested
    )
    assert all(step.execution_strategy.type is StrategyType.SKIP for step in nested)
    assert steps[4].output_key == steps[5].output_key == "fixed_1"
    assert steps[9].output_key == steps[10].output_key == "fixed_2"
    assert all(
        step.execution_strategy.type is StrategyType.FAIL
        for step in steps
        if step.primitive == "tool" and step.id != "reconcile"
    )


STORY = "7-5-verify-fix-fixture"
SPEC_PATH = "specs/story.md"
BRANCH = "feat/story-7-5"


def _spec() -> bytes:
    return (
        (
            f"---\nstory_key: {STORY}\nrequirements: [FR-14]\n"
            "repositories: [. ]\ndependencies: []\nsize_cap_bytes: 64000\n"
            'units:\n  - id: u1\n    paths: [src/api.py]\n    subject: "feat: update api"\n---\n\n# Fixture\n'
        )
        .replace("[. ]", "[.]")
        .encode()
    )


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = init_repo(tmp_path / "repo")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    make_source(repo)
    write_version(repo, "v1", good())
    from beddel_profile_dev.tools.ratify import profile_ratify_inventory

    profile_ratify_inventory(str(repo), "v1", "owner")
    (repo / SPEC_PATH).parent.mkdir()
    (repo / SPEC_PATH).write_bytes(_spec())
    base = commit_all(repo, "base")
    git(repo, "switch", "-q", "-c", BRANCH)
    (repo / "src/api.py").write_text("x = 2\n")
    git(repo, "add", "--", "src/api.py")
    git(
        repo,
        "commit",
        "-q",
        "-m",
        "feat: update api",
        "-m",
        f"Story-Key: {STORY}\nImplementation-Unit: u1",
    )
    return repo, base


class FixAgent:
    def __init__(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.repo = repo
        self.monkeypatch = monkeypatch
        self.calls = 0

    async def execute(
        self,
        prompt: str,
        *,
        model: str | None = None,
        sandbox: str = "read-only",
        tools: list[str] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> AgentResult:
        self.calls += 1
        (self.repo / "src/api.py").write_text("x = 3\n")
        self.monkeypatch.setenv("STUB_EXIT_PYTEST", "0")
        return AgentResult(0, "", [], [], {}, "fake")


def _run_stage(repo: Path, fake: FixAgent, base: str) -> dict[str, Any]:
    workflow = WorkflowParser.parse(WORKFLOW_PATH.read_text())
    registry = PrimitiveRegistry()
    register_builtins(registry)
    tools = load_kit(parse_kit_manifest(KIT_ROOT / "kit.yaml"))
    dependencies = DefaultDependencies(
        agent_registry={"kiro-cli": fake},
        tool_registry=tools,
        registry=registry,
        workflow_loader=lambda name: WorkflowParser.parse(
            (KIT_ROOT / "workflows" / name).read_text()
        ),
    )
    from beddel.domain.executor import WorkflowExecutor

    return asyncio.run(
        WorkflowExecutor(registry, deps=dependencies).execute(
            workflow,
            {
                "repo_path": str(repo),
                "story_key": STORY,
                "spec_path": SPEC_PATH,
                "branch": BRANCH,
                "base_ref": base,
                "change_id": "c1",
                "inventory_version": "v1",
            },
        )
    )


def _review_output() -> str:
    payload = {
        "schema": REVIEW_ASSESSMENT_SCHEMA,
        "assessments": [
            {
                "class": "review-arch",
                "affected_point": "api",
                "criterion": "arch-ok",
                "divergences": [],
            }
        ],
        "unassociated": [],
    }
    return f"{ASSESSMENT_BEGIN}\n{json.dumps(payload)}\n{ASSESSMENT_END}\n"


def test_in_process_consistent_run_has_one_report_and_no_fix_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("STUB_EXIT_PYTEST", "0")
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: FakeReviewAdapter(
            "completed", output=_review_output()
        ),
    )
    fake = FixAgent(repo, monkeypatch)
    result = _run_stage(repo, fake, base)
    close = result["step_results"]["close"]["result"]
    assert (close["outcome"], close["reason"], fake.calls) == (
        "succeeded",
        "verdict.consistent",
        0,
    )
    assert len(list((tmp_path / "home").rglob("changes/c1/report/*.json"))) == 1


def test_in_process_fix_round_commits_and_reverifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("STUB_EXIT_PYTEST", "1")
    monkeypatch.setattr(
        _adapters,
        "get_review_adapter",
        lambda agent_name, *, timeout_seconds: FakeReviewAdapter(
            "completed", output=_review_output()
        ),
    )
    fake = FixAgent(repo, monkeypatch)
    result = _run_stage(repo, fake, base)
    close = result["step_results"]["close"]["result"]
    reports = sorted((tmp_path / "home").rglob("changes/c1/report/*.json"))
    assert (close["outcome"], close["reason"], fake.calls) == (
        "succeeded",
        "verdict.consistent",
        1,
    )
    assert len(reports) == 2
    assert "Fix-Round: 1" in git(repo, "show", "-s", "--format=%B", "HEAD")
    assert json.loads(reports[1].read_text())["reverification"]["status"] == "recorded"
