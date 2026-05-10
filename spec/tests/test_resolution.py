"""Spec fixture resolution tests for Beddel variable resolver (AC 5).

Tests that parsed workflows, when resolved with sample inputs/step results/env
from the expected JSON fixtures, produce the expected resolved configs.

Fixtures are loaded from ``spec/fixtures/`` — no inline YAML strings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from beddel.domain.models import ExecutionContext, Step
from beddel.domain.parser import WorkflowParser
from beddel.domain.resolver import VariableResolver

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SPEC_DIR = Path(__file__).resolve().parent.parent
VALID_DIR = SPEC_DIR / "fixtures" / "valid"
EXPECTED_DIR = SPEC_DIR / "fixtures" / "expected"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_expected(name: str) -> dict[str, Any]:
    """Load an expected JSON fixture by base name (e.g. ``"simple"``)."""
    path = EXPECTED_DIR / f"{name}.expected.json"
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def _collect_all_steps(steps: list[Step]) -> list[Step]:
    """Flatten a step tree into a list including nested then/else steps."""
    result: list[Step] = []
    for step in steps:
        result.append(step)
        if step.then_steps:
            result.extend(_collect_all_steps(step.then_steps))
        if step.else_steps:
            result.extend(_collect_all_steps(step.else_steps))
    return result


def _resolve_and_collect(
    workflow_yaml: str,
    expected: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, dict[str, Any]]:
    """Parse a workflow, resolve all step configs, return resolved configs by step id.

    Sets up the execution context and environment from the expected fixture,
    then resolves every step config (including nested then/else branches).
    """
    # Arrange
    workflow = WorkflowParser.parse(workflow_yaml)
    context = ExecutionContext(
        workflow_id=workflow.id,
        inputs=expected.get("sample_inputs", {}),
        step_results=expected.get("sample_step_results", {}),
    )
    for env_key, env_val in expected.get("sample_env", {}).items():
        monkeypatch.setenv(env_key, env_val)

    resolver = VariableResolver()

    # Act
    all_steps = _collect_all_steps(workflow.steps)
    resolved: dict[str, dict[str, Any]] = {}
    for step in all_steps:
        resolved[step.id] = resolver.resolve(step.config, context)

    return resolved


# ---------------------------------------------------------------------------
# Tests — simple.yaml resolution
# ---------------------------------------------------------------------------


class TestSimpleResolution:
    """Verify simple.yaml resolves to simple.expected.json."""

    def test_simple_resolution_matches_expected(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Parsed simple.yaml, resolved with sample inputs, matches expected JSON."""
        yaml_str = (VALID_DIR / "simple.yaml").read_text()
        expected = _load_expected("simple")

        resolved = _resolve_and_collect(yaml_str, expected, monkeypatch)

        for step_id, step_expected in expected["steps"].items():
            assert step_id in resolved, f"Step '{step_id}' not found in resolved output"
            assert resolved[step_id] == step_expected["config"]

    def test_simple_all_steps_present(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """All expected step ids are present in the resolved output."""
        yaml_str = (VALID_DIR / "simple.yaml").read_text()
        expected = _load_expected("simple")

        resolved = _resolve_and_collect(yaml_str, expected, monkeypatch)

        assert set(expected["steps"].keys()) <= set(resolved.keys())


# ---------------------------------------------------------------------------
# Tests — branching.yaml resolution
# ---------------------------------------------------------------------------


class TestBranchingResolution:
    """Verify branching.yaml resolves to branching.expected.json."""

    def test_branching_resolution_matches_expected(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Parsed branching.yaml, resolved with sample inputs/step results/env, matches expected."""
        yaml_str = (VALID_DIR / "branching.yaml").read_text()
        expected = _load_expected("branching")

        resolved = _resolve_and_collect(yaml_str, expected, monkeypatch)

        for step_id, step_expected in expected["steps"].items():
            assert step_id in resolved, f"Step '{step_id}' not found in resolved output"
            assert resolved[step_id] == step_expected["config"], (
                f"Mismatch for step '{step_id}': "
                f"got {resolved[step_id]!r}, expected {step_expected['config']!r}"
            )

    def test_branching_all_steps_present(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """All expected step ids (including nested then/else) are present."""
        yaml_str = (VALID_DIR / "branching.yaml").read_text()
        expected = _load_expected("branching")

        resolved = _resolve_and_collect(yaml_str, expected, monkeypatch)

        assert set(expected["steps"].keys()) <= set(resolved.keys())

    def test_branching_env_variable_resolved(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The translate step resolves $env.TRANSLATE_API_KEY from environment."""
        yaml_str = (VALID_DIR / "branching.yaml").read_text()
        expected = _load_expected("branching")

        resolved = _resolve_and_collect(yaml_str, expected, monkeypatch)

        assert "sk-test-123" in resolved["translate"]["prompt"]

    def test_branching_step_result_resolved(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The classify step's $input.query reference is resolved correctly."""
        yaml_str = (VALID_DIR / "branching.yaml").read_text()
        expected = _load_expected("branching")

        resolved = _resolve_and_collect(yaml_str, expected, monkeypatch)

        assert "How does TCP work?" in resolved["classify"]["prompt"]


# ---------------------------------------------------------------------------
# Tests — multi-step.yaml resolution
# ---------------------------------------------------------------------------


class TestMultiStepResolution:
    """Verify multi-step.yaml resolves to multi-step.expected.json."""

    def test_multi_step_resolution_matches_expected(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Parsed multi-step.yaml, resolved with sample inputs/step results/env, matches expected."""
        yaml_str = (VALID_DIR / "multi-step.yaml").read_text()
        expected = _load_expected("multi-step")

        resolved = _resolve_and_collect(yaml_str, expected, monkeypatch)

        for step_id, step_expected in expected["steps"].items():
            assert step_id in resolved, f"Step '{step_id}' not found in resolved output"
            assert resolved[step_id] == step_expected["config"], (
                f"Mismatch for step '{step_id}': "
                f"got {resolved[step_id]!r}, expected {step_expected['config']!r}"
            )

    def test_multi_step_all_steps_present(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """All expected step ids are present in the resolved output."""
        yaml_str = (VALID_DIR / "multi-step.yaml").read_text()
        expected = _load_expected("multi-step")

        resolved = _resolve_and_collect(yaml_str, expected, monkeypatch)

        assert set(expected["steps"].keys()) <= set(resolved.keys())

    def test_multi_step_cross_step_refs_resolved(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Step result references from prior steps are resolved correctly."""
        yaml_str = (VALID_DIR / "multi-step.yaml").read_text()
        expected = _load_expected("multi-step")

        resolved = _resolve_and_collect(yaml_str, expected, monkeypatch)

        # extract_keywords references $stepResult.summarize.text
        assert "Quantum computing uses qubits" in resolved["extract_keywords"]["prompt"]
        # report references $stepResult.extract_keywords.keywords
        assert "qubits, superposition, entanglement" in resolved["report"]["prompt"]

    def test_multi_step_env_resolved(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Environment variable $env.REPORT_API_KEY is resolved in the report step."""
        yaml_str = (VALID_DIR / "multi-step.yaml").read_text()
        expected = _load_expected("multi-step")

        resolved = _resolve_and_collect(yaml_str, expected, monkeypatch)

        assert "rk-test-456" in resolved["report"]["prompt"]

