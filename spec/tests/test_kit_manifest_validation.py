"""Kit manifest fixture validation against JSON Schema and Pydantic models.

Validates that:
- All valid kit fixtures pass JSON Schema validation (AC 6).
- Invalid kit fixtures with structural errors fail JSON Schema validation.
- All valid kit fixtures load successfully via SolutionKit.model_validate().
- All invalid kit fixtures fail Pydantic validation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate
from pydantic import ValidationError as PydanticValidationError

from beddel.domain.kit import SolutionKit

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SPEC_DIR = Path(__file__).resolve().parent.parent
VALID_DIR = SPEC_DIR / "kits" / "fixtures" / "valid"
INVALID_DIR = SPEC_DIR / "kits" / "fixtures" / "invalid"
SCHEMA_PATH = SPEC_DIR / "kits" / "kit-manifest.schema.json"

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

# Fixtures that violate JSON Schema structural rules (missing required fields,
# wrong types).  Pydantic-only violations (kebab-case name, semver version,
# adapter model_validator) are excluded — JSON Schema cannot express those.
_SCHEMA_INVALID_STEMS = {
    "missing-name",
    "missing-version",
    "missing-description",
    "invalid-tool-missing-target",
}
SCHEMA_INVALID_FIXTURES = [
    p for p in INVALID_FIXTURES if p.stem in _SCHEMA_INVALID_STEMS
]


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def kit_schema() -> dict[str, object]:
    """Load the committed JSON Schema for kit manifests."""
    return json.loads(SCHEMA_PATH.read_text())  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Valid fixtures — JSON Schema
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=_fixture_ids(VALID_FIXTURES),
)
def test_valid_fixtures_pass_schema(
    fixture_path: Path,
    kit_schema: dict[str, object],
) -> None:
    """Each valid kit fixture must pass JSON Schema validation."""
    data = yaml.safe_load(fixture_path.read_text())
    validate(instance=data, schema=kit_schema)  # raises on failure


# ---------------------------------------------------------------------------
# Invalid fixtures — JSON Schema (structural violations only)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_path",
    SCHEMA_INVALID_FIXTURES,
    ids=_fixture_ids(SCHEMA_INVALID_FIXTURES),
)
def test_invalid_fixtures_fail_schema(
    fixture_path: Path,
    kit_schema: dict[str, object],
) -> None:
    """Structurally invalid kit fixtures must fail JSON Schema validation."""
    data = yaml.safe_load(fixture_path.read_text())
    with pytest.raises(JsonSchemaValidationError):
        validate(instance=data, schema=kit_schema)


# ---------------------------------------------------------------------------
# Valid fixtures — Pydantic cross-validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=_fixture_ids(VALID_FIXTURES),
)
def test_valid_fixtures_load_pydantic(fixture_path: Path) -> None:
    """Each valid kit fixture must load via SolutionKit.model_validate()."""
    data = yaml.safe_load(fixture_path.read_text())
    kit = SolutionKit.model_validate(data)
    assert kit.name
    assert kit.version
    assert kit.description


# ---------------------------------------------------------------------------
# Invalid fixtures — Pydantic (all invalid fixtures must fail)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_path",
    INVALID_FIXTURES,
    ids=_fixture_ids(INVALID_FIXTURES),
)
def test_invalid_fixtures_fail_pydantic(fixture_path: Path) -> None:
    """Every invalid kit fixture must fail Pydantic validation."""
    data = yaml.safe_load(fixture_path.read_text())
    with pytest.raises(PydanticValidationError):
        SolutionKit.model_validate(data)
