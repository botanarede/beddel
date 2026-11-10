"""Workflow shape and in-process Coding-agent coverage."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from beddel.domain.errors import AgentError, BeddelError
from beddel.domain.executor import WorkflowExecutor
from beddel.domain.kit import parse_kit_manifest
from beddel.domain.models import AgentResult, DefaultDependencies
from beddel.domain.parser import WorkflowParser
from beddel.domain.registry import PrimitiveRegistry
from beddel.error_codes import AGENT_EXECUTION_FAILED
from beddel.primitives import register_builtins
from beddel.tools.kits import load_kit
from beddel_profile_dev._errors import ProfileError
from beddel_profile_dev.tools import implement as implement_tools
from beddel_profile_dev.tools.stage_outcome import profile_record_stage_outcome

from ._helpers import commit_all, git, init_repo, stub_gate_tools
from .test_implement import BRANCH, SPEC_PATH, STORY, spec_bytes

KIT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = KIT_ROOT / "workflows" / "implement-story.yaml"


class FakeAgent:
    def __init__(
        self,
        repo: Path,
        mode: str = "sequence",
        patch: pytest.MonkeyPatch | None = None,
    ) -> None:
        self.repo = repo
        self.mode = mode
        self.patch = patch
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
        if self.mode == "error":
            raise AgentError(code=AGENT_EXECUTION_FAILED, message="fake agent failed")
        if self.mode == "nothing":
            pass
        elif self.mode == "out-of-scope":
            (self.repo / "outside.py").write_text("outside\n")
        elif self.mode == "commit":
            (self.repo / "src" / "one.py").write_text("one\n")
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
        elif self.mode == "switch":
            await asyncio.to_thread(
                subprocess.run,
                ["git", "-C", str(self.repo), "switch", "-q", "-c", "wrong"],
                check=True,
            )
        else:
            target = "one.py" if self.calls == 1 else "two.py"
            (self.repo / "src" / target).write_text(f"{target}\n")
        if self.mode == "regression":
            (self.repo / "src" / "one.py").write_text("one\n")
            if self.patch is not None:
                self.patch.setenv("STUB_EXIT_PYTEST", "1")
        return AgentResult(
            exit_code=0,
            output="",
            events=[],
            files_changed=[],
            usage={},
            agent_id="fake",
        )


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = init_repo(tmp_path / "repo")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "src").mkdir()
    (repo / "src" / "base.py").write_text("base\n")
    (repo / SPEC_PATH).parent.mkdir()
    (repo / SPEC_PATH).write_bytes(spec_bytes())
    base = commit_all(repo, "base")
    return repo, base


def _run(repo: Path, base: str, fake: FakeAgent) -> dict[str, Any]:
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
    return asyncio.run(
        executor.execute(
            workflow,
            {
                "repo_path": str(repo),
                "story_key": STORY,
                "spec_path": SPEC_PATH,
                "branch": BRANCH,
                "base_ref": base,
            },
        )
    )


def test_workflow_shape_and_safety() -> None:
    document = yaml.safe_load(WORKFLOW_PATH.read_text())
    assert document["id"] == "implement-story"
    assert document["requires_kits"] == ["profile-dev-kit", "agent-kiro-kit"]
    assert document["inputs"] == [
        "repo_path",
        "story_key",
        "spec_path",
        "branch",
        "base_ref",
    ]
    assert document["allowed_tools"] == [
        "profile_implement_prepare",
        "profile_implement_settle",
        "profile_record_stage_outcome",
    ]
    assert "Coding agent" in document["description"]
    assert {step["id"] for step in document["steps"]} == {
        "prepare",
        "implement",
        "settle",
        "settle_stop",
        "record",
        "record_stop",
    }
    assert "push" not in document["allowed_tools"]
    assert "verify" not in document["allowed_tools"]
    agent = next(step for step in document["steps"] if step["id"] == "implement")
    assert agent["config"]["adapter"] == "kiro-cli"
    assert agent["config"]["sandbox"] == "workspace-write"
    assert agent["timeout"] <= 600
    workflow = WorkflowParser.parse(WORKFLOW_PATH.read_text())
    steps = {step.id: step for step in workflow.steps}
    assert (
        steps["implement"].if_condition
        == "$stepResult.prepare.result.implement == true"
    )
    assert (
        steps["settle"].if_condition == "$stepResult.prepare.result.implement == true"
    )
    assert (
        steps["settle_stop"].if_condition
        == "$stepResult.prepare.result.implement != true"
    )
    assert (
        steps["record"].if_condition == "$stepResult.prepare.result.implement == true"
    )
    assert (
        steps["record_stop"].if_condition
        == "$stepResult.prepare.result.implement != true"
    )


def test_two_unit_sequence_records_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    fake = FakeAgent(repo)
    first = _run(repo, base, fake)
    first_result = first["step_results"]["settle"]["result"]
    assert first_result["reason"] == "unit.committed"
    assert first_result["refs"]["base"] == base
    assert first_result["refs"]["commit"] == first_result["refs"]["head"]
    assert (first_result["refs"]["completed"], first_result["refs"]["remaining"]) == (
        1,
        1,
    )
    assert git(repo, "show", "--name-only", "--format=", "HEAD").split() == [
        "src/one.py"
    ]
    assert "Implementation-Unit: u1" in git(repo, "show", "-s", "--format=%B", "HEAD")
    assert fake.calls == 1
    second = _run(repo, base, fake)
    second_result = second["step_results"]["settle"]["result"]
    assert second_result["reason"] == "unit.committed"
    assert fake.calls == 2
    third_head = git(repo, "rev-parse", "HEAD")
    third = _run(repo, base, fake)
    stop = third["step_results"]["settle_stop"]["result"]
    assert stop["reason"] == "units.complete"
    assert stop["outcome"] == "succeeded"
    assert fake.calls == 2
    assert git(repo, "rev-parse", "HEAD") == third_head
    stored = list((tmp_path / "home").rglob("*.json"))
    assert len(stored) == 3
    assert sorted(json.loads(path.read_text())["record"] for path in stored) == [
        1,
        2,
        3,
    ]


@pytest.mark.parametrize(
    ("mode", "reason"),
    [
        ("out-of-scope", "scope.exceeded"),
        ("commit", "head.moved"),
        ("nothing", "unit.empty"),
        ("error", "agent.failed"),
        ("switch", "branch.moved"),
        ("regression", "gate.regressed"),
    ],
)
def test_agent_modes_are_recorded_without_losing_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, reason: str
) -> None:
    repo, base = _repo(tmp_path / mode)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path / mode))
    monkeypatch.setenv("HOME", str(tmp_path / mode / "home"))
    fake = FakeAgent(repo, mode, monkeypatch)
    before = git(repo, "rev-parse", "HEAD")
    result = _run(repo, base, fake)
    settle = result["step_results"].get(
        "settle", result["step_results"].get("settle_stop")
    )
    assert settle["result"]["reason"] == reason
    assert settle["result"]["outcome"] == "failed"
    records = list((tmp_path / mode / "home").rglob("*.json"))
    assert len(records) == 1
    stored = json.loads(records[0].read_text())
    assert (stored["outcome"], stored["reason"]) == ("failed", reason)
    assert git(repo, "rev-parse", "HEAD") == before or reason == "head.moved"


def test_bad_repository_fails_at_record_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    bad = tmp_path / "not-a-repository"
    bad.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with pytest.raises(BeddelError) as error:
        _run(bad, base, FakeAgent(bad))
    assert error.value.code == "BEDDEL-EXEC-002"
    with pytest.raises(BeddelError) as record_error:
        profile_record_stage_outcome(
            str(bad), STORY, "implement", "failed", "prepare.failed", {}
        )
    assert record_error.value.code == "PROFILE_REPOSITORY_INVALID"


def test_absorbed_prepare_error_records_prepare_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    def boom(_repo: Path) -> set[str]:
        raise ProfileError("PROFILE_REPOSITORY_INVALID", "fixture")

    monkeypatch.setattr(implement_tools, "changed_paths", boom)
    result = _run(repo, base, FakeAgent(repo))
    stop = result["step_results"]["settle_stop"]["result"]
    assert (stop["outcome"], stop["reason"]) == ("failed", "prepare.failed")
    records = list((tmp_path / "home").rglob("*.json"))
    assert len(records) == 1
    stored = json.loads(records[0].read_text())
    assert (stored["outcome"], stored["reason"]) == ("failed", "prepare.failed")
