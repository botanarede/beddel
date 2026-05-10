"""Spec fixture validation tests for Beddel workflow parser and JSON Schema.

Tests that:
- All valid fixtures parse successfully via WorkflowParser (AC 6).
- All invalid fixtures are rejected with BEDDEL-PARSE-* error codes (AC 5).
- Specific invalid fixtures produce the expected error codes.
- Valid fixtures pass JSON Schema validation (AC 4).
- Invalid fixtures with structural errors fail JSON Schema validation.
- Minimum fixture counts are met (AC 5, 6).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from beddel.domain.errors import ParseError
from beddel.domain.models import Workflow
from beddel.domain.parser import WorkflowParser

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SPEC_DIR = Path(__file__).resolve().parent.parent
VALID_DIR = SPEC_DIR / "fixtures" / "valid"
INVALID_DIR = SPEC_DIR / "fixtures" / "invalid"
SCHEMA_PATH = SPEC_DIR / "schemas" / "workflow.schema.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _yaml_files(directory: Path) -> list[Path]:
    """Return sorted list of .yaml files in *directory*."""
    return sorted(directory.glob("*.yaml"))


def _fixture_ids(paths: list[Path]) -> list[str]:
    """Return stem names for readable pytest IDs."""
    return [p.stem for p in paths]


VALID_FIXTURES = _yaml_files(VALID_DIR)
INVALID_FIXTURES = _yaml_files(INVALID_DIR)


# ---------------------------------------------------------------------------
# AC 5 / AC 6 — Minimum fixture counts
# ---------------------------------------------------------------------------


def test_minimum_valid_fixture_count() -> None:
    """AC 6: at least 2 valid fixtures (including one with branching)."""
    assert len(VALID_FIXTURES) >= 2, (
        f"Expected >= 2 valid fixtures, found {len(VALID_FIXTURES)}"
    )


def test_minimum_invalid_fixture_count() -> None:
    """AC 5: at least 3 invalid fixtures rejected with BEDDEL-PARSE-* codes."""
    assert len(INVALID_FIXTURES) >= 3, (
        f"Expected >= 3 invalid fixtures, found {len(INVALID_FIXTURES)}"
    )


# ---------------------------------------------------------------------------
# Valid fixtures — parser acceptance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=_fixture_ids(VALID_FIXTURES),
)
def test_valid_fixture_parses_successfully(fixture_path: Path) -> None:
    """Each valid fixture must parse into a Workflow via WorkflowParser."""
    yaml_str = fixture_path.read_text()
    workflow = WorkflowParser.parse(yaml_str)
    assert isinstance(workflow, Workflow)
    assert workflow.id  # non-empty id


# ---------------------------------------------------------------------------
# Invalid fixtures — parser rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_path",
    INVALID_FIXTURES,
    ids=_fixture_ids(INVALID_FIXTURES),
)
def test_invalid_fixture_raises_parse_error(fixture_path: Path) -> None:
    """Each invalid fixture must raise ParseError with a BEDDEL-PARSE-* code."""
    yaml_str = fixture_path.read_text()
    with pytest.raises(ParseError) as exc_info:
        WorkflowParser.parse(yaml_str)
    assert exc_info.value.code.startswith("BEDDEL-PARSE-")


# ---------------------------------------------------------------------------
# Specific error codes per invalid fixture
# ---------------------------------------------------------------------------

_EXPECTED_CODES: dict[str, str] = {
    "missing-steps": "BEDDEL-PARSE-002",
    "bad-strategy": "BEDDEL-PARSE-002",
    "circular-ref": "BEDDEL-PARSE-003",
}


@pytest.mark.parametrize(
    ("fixture_name", "expected_code"),
    list(_EXPECTED_CODES.items()),
    ids=list(_EXPECTED_CODES.keys()),
)
def test_invalid_fixture_error_code(fixture_name: str, expected_code: str) -> None:
    """Each known invalid fixture must produce its expected error code."""
    fixture_path = INVALID_DIR / f"{fixture_name}.yaml"
    assert fixture_path.exists(), f"Fixture not found: {fixture_path}"

    yaml_str = fixture_path.read_text()
    with pytest.raises(ParseError) as exc_info:
        WorkflowParser.parse(yaml_str)
    assert exc_info.value.code == expected_code


# ---------------------------------------------------------------------------
# AC 4 — JSON Schema validates valid fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def workflow_schema() -> dict:
    """Load the committed JSON Schema for Workflow."""
    return json.loads(SCHEMA_PATH.read_text())  # type: ignore[no-any-return]


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=_fixture_ids(VALID_FIXTURES),
)
def test_valid_fixture_passes_json_schema(
    fixture_path: Path,
    workflow_schema: dict,
) -> None:
    """Valid YAML fixtures must also pass JSON Schema validation."""
    data = yaml.safe_load(fixture_path.read_text())
    validate(instance=data, schema=workflow_schema)  # raises on failure


# ---------------------------------------------------------------------------
# JSON Schema rejects structurally invalid fixtures
# ---------------------------------------------------------------------------

# circular-ref is valid at the JSON Schema level (semantic error only).
_SCHEMA_INVALID_FIXTURES = [
    p for p in INVALID_FIXTURES if p.stem != "circular-ref"
]


@pytest.mark.parametrize(
    "fixture_path",
    _SCHEMA_INVALID_FIXTURES,
    ids=_fixture_ids(_SCHEMA_INVALID_FIXTURES),
)
def test_invalid_fixture_fails_json_schema(
    fixture_path: Path,
    workflow_schema: dict,
) -> None:
    """Structurally invalid fixtures must fail JSON Schema validation."""
    data = yaml.safe_load(fixture_path.read_text())
    with pytest.raises(JsonSchemaValidationError):
        validate(instance=data, schema=workflow_schema)


# ---------------------------------------------------------------------------
# Reflection loop fixture — tag and metadata validation
# ---------------------------------------------------------------------------


def test_reflection_loop_fixture_has_tags() -> None:
    """Reflection loop fixture has generate and evaluate tagged steps."""
    fixture_path = VALID_DIR / "reflection-loop.yaml"
    assert fixture_path.exists(), "reflection-loop.yaml fixture not found"
    yaml_str = fixture_path.read_text()
    workflow = WorkflowParser.parse(yaml_str)

    # Verify step tags
    draft_step = next(s for s in workflow.steps if s.id == "draft")
    review_step = next(s for s in workflow.steps if s.id == "review")
    assert "generate" in draft_step.tags
    assert "evaluate" in review_step.tags

    # Verify metadata contains reflection config
    assert "_reflection_config" in workflow.metadata
    assert workflow.metadata["_reflection_config"]["max_iterations"] == 3
    assert workflow.metadata["_reflection_config"]["convergence_algorithm"] == "exact-match"


def test_parallel_execution_fixture_has_parallel_fields() -> None:
    """Parallel execution fixture has correct parallel field values."""
    fixture_path = VALID_DIR / "parallel-execution.yaml"
    assert fixture_path.exists(), "parallel-execution.yaml fixture not found"
    yaml_str = fixture_path.read_text()
    workflow = WorkflowParser.parse(yaml_str)

    assert len(workflow.steps) == 4

    # Sequential steps (parallel=False, the default)
    prepare = next(s for s in workflow.steps if s.id == "prepare")
    synthesize = next(s for s in workflow.steps if s.id == "synthesize")
    assert prepare.parallel is False
    assert synthesize.parallel is False

    # Parallel steps (parallel=True)
    research = next(s for s in workflow.steps if s.id == "research")
    examples = next(s for s in workflow.steps if s.id == "examples")
    assert research.parallel is True
    assert examples.parallel is True
