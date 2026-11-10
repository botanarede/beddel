"""In-process plan workflow coverage with a fake Coding agent."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from beddel.domain.errors import AgentError
from beddel.domain.executor import WorkflowExecutor
from beddel.domain.kit import parse_kit_manifest
from beddel.domain.models import AgentResult, DefaultDependencies
from beddel.domain.parser import WorkflowParser
from beddel.domain.registry import PrimitiveRegistry
from beddel.error_codes import AGENT_EXECUTION_FAILED
from beddel.primitives import register_builtins
from beddel.tools.kits import load_kit
from beddel_profile_dev._io import records_root
from beddel_profile_dev.tools.plan import profile_plan_settle
from beddel_profile_dev.tools.stage_outcome import profile_record_stage_outcome

from ._helpers import commit_all, init_repo

KIT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = KIT_ROOT / "workflows" / "plan-story.yaml"
STORY = "7-3-plan-workflow-turns-one-story-into-one-spec"


def complete_spec() -> bytes:
    return (
        f"---\nstory_key: {STORY}\nrequirements: [FR-13]\n"
        "repositories: [kits/profile-dev-kit]\ndependencies: []\n"
        "size_cap_bytes: 64000\n---\n\n# Plan\n"
    ).encode()


class FakeAgent:
    def __init__(self, repo: Path, mode: str) -> None:
        self.repo = repo
        self.mode = mode
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
        spec = self.repo / "specs" / "story.md"
        spec.parent.mkdir(exist_ok=True)
        if self.mode == "error":
            raise AgentError(code=AGENT_EXECUTION_FAILED, message="fake agent failed")
        if self.mode == "incomplete":
            spec.write_text("unfinished")
        else:
            spec.write_bytes(complete_spec())
        if self.mode == "extra":
            (self.repo / "extra.txt").write_text("out of scope")
        if self.mode == "commit":
            await asyncio.to_thread(
                subprocess.run,
                ["git", "-C", str(self.repo), "add", "-A"],
                check=True,
            )
            await asyncio.to_thread(
                subprocess.run,
                [
                    "git",
                    "-C",
                    str(self.repo),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "agent",
                ],
                check=True,
            )
        return AgentResult(
            exit_code=0,
            output="",
            events=[],
            files_changed=[],
            usage={},
            agent_id="fake",
        )


def _repo(tmp_path: Path) -> Path:
    repo = init_repo(tmp_path / "repo")
    (repo / "story.md").write_text("story")
    (repo / "guide.md").write_text("guide")
    (repo / "specs").mkdir()
    commit_all(repo)
    return repo


def _run(
    repo: Path,
    fake: FakeAgent,
    monkeypatch: pytest.MonkeyPatch,
    story_key: str = STORY,
) -> dict[str, Any]:
    workflow = WorkflowParser.parse(WORKFLOW_PATH.read_text())
    registry = PrimitiveRegistry()
    register_builtins(registry)
    tools = load_kit(parse_kit_manifest(KIT_ROOT / "kit.yaml"))
    executor = WorkflowExecutor(
        registry,
        deps=DefaultDependencies(
            agent_registry={"kiro-cli": fake}, tool_registry=tools
        ),
    )
    import asyncio

    return asyncio.run(
        executor.execute(
            workflow,
            {
                "repo_path": str(repo),
                "story_key": story_key,
                "story_path": "story.md",
                "guide_path": "guide.md",
                "spec_path": "specs/story.md",
            },
        )
    )


def test_workflow_shape() -> None:
    document = yaml.safe_load(WORKFLOW_PATH.read_text())
    assert document["id"] == "plan-story"
    assert document["requires_kits"] == ["profile-dev-kit", "agent-kiro-kit"]
    assert document["inputs"] == [
        "repo_path",
        "story_key",
        "story_path",
        "guide_path",
        "spec_path",
    ]
    assert document["allowed_tools"] == [
        "profile_plan_reconcile",
        "profile_plan_settle",
        "profile_record_stage_outcome",
    ]
    assert "Coding agent" in document["description"]
    assert {step["id"] for step in document["steps"]} == {
        "reconcile",
        "author",
        "settle",
        "record",
    }
    author = next(step for step in document["steps"] if step["id"] == "author")
    assert author["execution_strategy"]["type"] == "skip"
    assert author["config"]["adapter"] == "kiro-cli"
    assert author["config"]["sandbox"] == "workspace-write"
    assert author["timeout"] <= 600
    assert "verify" not in document["allowed_tools"]
    workflow = WorkflowParser.parse(WORKFLOW_PATH.read_text())
    steps = {step.id: step for step in workflow.steps}
    assert steps["reconcile"].execution_strategy.type.value == "skip"
    assert steps["author"].if_condition == "$stepResult.reconcile.result.author == true"
    assert steps["settle"].execution_strategy.type.value == "fail"
    assert steps["record"].execution_strategy.type.value == "fail"


@pytest.mark.parametrize(
    ("mode", "expected", "reason", "calls"),
    [
        ("complete", "succeeded", "spec.created", 1),
        ("incomplete", "failed", "spec.incomplete", 1),
        ("extra", "failed", "scope.exceeded", 1),
        ("commit", "failed", "head.moved", 1),
        ("error", "failed", "spec.incomplete", 1),
    ],
)
def test_workflow_settles_agent_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected: str,
    reason: str,
    calls: int,
) -> None:
    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    fake = FakeAgent(repo, mode)
    result = _run(repo, fake, monkeypatch)
    assert result["step_results"]["settle"]["result"]["outcome"] == expected
    assert result["step_results"]["settle"]["result"]["reason"] == reason
    assert fake.calls == calls
    records = records_root(repo, "records/profile-dev") / "stage-outcomes"
    stored = json.loads((records / "1.json").read_text())
    assert stored["reason"] == reason


def test_reuse_and_refusal_skip_agent_and_still_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    (repo / "specs" / "story.md").write_bytes(complete_spec())
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    fake = FakeAgent(repo, "error")
    records = records_root(repo, "records/profile-dev") / "stage-outcomes"
    result = _run(repo, fake, monkeypatch)
    assert result["step_results"]["settle"]["result"]["reason"] == "spec.reused"
    first_record = json.loads((records / "1.json").read_text())
    assert first_record["story_key"] == STORY
    result_again = _run(repo, fake, monkeypatch)
    assert result_again["step_results"]["settle"]["result"]["reason"] == "spec.reused"
    assert fake.calls == 0
    second_record = json.loads((records / "2.json").read_text())
    assert second_record["record"] == 2
    assert second_record["reason"] == "spec.reused"

    repo2 = _repo(tmp_path / "refusal")
    (repo2 / "specs").rmdir()
    monkeypatch.chdir(repo2)
    fake2 = FakeAgent(repo2, "error")
    result2 = _run(repo2, fake2, monkeypatch, story_key="BAD KEY")
    assert result2["step_results"]["settle"]["result"]["reason"] == "story_key.invalid"
    assert result2["step_results"]["settle"]["result"]["outcome"] == "refused"
    assert fake2.calls == 0
    refusal_record = json.loads(
        (
            records_root(repo2, "records/profile-dev") / "stage-outcomes/1.json"
        ).read_text()
    )
    assert refusal_record["story_key"] is None


def test_mismatch_and_invalid_path_records_are_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "mismatch")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    mismatch = profile_plan_settle(
        str(repo), STORY, "story.md", "guide.md", "specs/story.md", {"wrong": True}
    )
    assert mismatch["reason"] == "reconcile.mismatch"
    profile_record_stage_outcome(
        str(repo),
        mismatch["story_key"],
        mismatch["stage"],
        mismatch["outcome"],
        mismatch["reason"],
        mismatch["refs"],
    )
    mismatch_record = json.loads(
        (
            records_root(repo, "records/profile-dev") / "stage-outcomes/1.json"
        ).read_text()
    )
    assert mismatch_record["reason"] == "reconcile.mismatch"

    repo2 = _repo(tmp_path / "invalid-path")
    monkeypatch.chdir(repo2)
    invalid = profile_plan_settle(
        str(repo2), STORY, "story.md", "guide.md", "specs/a\nb.md", None
    )
    assert invalid["reason"] == "path.invalid"
    profile_record_stage_outcome(
        str(repo2),
        invalid["story_key"],
        invalid["stage"],
        invalid["outcome"],
        invalid["reason"],
        invalid["refs"],
    )
    invalid_record = json.loads(
        (
            records_root(repo2, "records/profile-dev") / "stage-outcomes/1.json"
        ).read_text()
    )
    assert invalid_record["refs"]["spec_path"] is None
