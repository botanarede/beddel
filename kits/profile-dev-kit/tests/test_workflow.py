"""AC2/AC3: entry workflow parses, requires the kit and allowlists every tool."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from beddel.domain.models import Step, StrategyType, Workflow
from beddel.domain.parser import WorkflowParser

WORKFLOW_PATH = (
    Path(__file__).resolve().parent.parent / "workflows" / "verify-change.yaml"
)


def _load() -> Workflow:
    return WorkflowParser.parse(WORKFLOW_PATH.read_text())


def _walk(steps: list[Step] | None) -> Iterator[Step]:
    for step in steps or []:
        yield step
        yield from _walk(step.then_steps)
        yield from _walk(step.else_steps)
        fallback = step.execution_strategy.fallback_step
        if fallback is not None:
            yield from _walk([fallback])


def _tool_names(steps: list[Step]) -> set[str]:
    return {
        str(s.config["tool"])
        for s in _walk(steps)
        if s.primitive == "tool" and "tool" in s.config
    }


def test_parses_and_requires_kit() -> None:
    wf = _load()
    assert wf.id == "verify-change"
    assert wf.requires_kits == ["profile-dev-kit"]


def test_preflight_is_the_first_and_only_step_and_fails_closed() -> None:
    steps = _load().steps
    assert [s.id for s in steps] == ["preflight"]
    assert steps[0].primitive == "tool"
    assert steps[0].config["tool"] == "profile_preflight"
    # A failing preflight must stop the run: no retry, no fallback, no skip.
    assert steps[0].execution_strategy.type is StrategyType.FAIL


def test_allowlist_equals_the_tools_the_steps_name() -> None:
    wf = _load()
    assert set(wf.allowed_tools or []) == _tool_names(wf.steps) == {"profile_preflight"}


def test_walk_catches_a_tool_hidden_in_a_nested_branch() -> None:
    wf = WorkflowParser.parse(
        """
id: nested
name: Nested
version: "1.0"
allowed_tools: [a]
steps:
  - id: s1
    primitive: tool
    config: {tool: a}
  - id: s2
    primitive: tool
    if: "true"
    config: {tool: a}
    then:
      - id: s3
        primitive: tool
        config: {tool: sneaky}
"""
    )
    assert _tool_names(wf.steps) - set(wf.allowed_tools or []) == {"sneaky"}
