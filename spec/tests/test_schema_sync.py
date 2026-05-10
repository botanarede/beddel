"""Verify that the committed JSON Schema stays in sync with Pydantic models."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from beddel.domain.kit import SolutionKit
from beddel.domain.models import Workflow

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "schemas" / "workflow.schema.json"
)

_WORKFLOW_METADATA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://beddel.dev/schemas/workflow.schema.json",
    "title": "Beddel Workflow",
    "description": "JSON Schema for Beddel YAML workflow definition files",
}

REGEN_HINT = (
    "Workflow JSON Schema is out of sync with Pydantic models. "
    "Regenerate with: python spec/scripts/sync_workflow_schema.py"
)


def test_workflow_schema_matches_pydantic_model() -> None:
    """The committed schema file must match Workflow.model_json_schema()."""
    assert SCHEMA_PATH.exists(), f"Schema file not found: {SCHEMA_PATH}"

    committed = json.loads(SCHEMA_PATH.read_text())
    generated = {**Workflow.model_json_schema(), **_WORKFLOW_METADATA}

    assert committed == generated, REGEN_HINT


# --- Kit manifest schema sync ---

KIT_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "kits" / "kit-manifest.schema.json"

_KIT_METADATA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://beddel.dev/schemas/kit-manifest.schema.json",
    "title": "Beddel Kit Manifest",
    "description": (
        "JSON Schema for kit.yaml manifest files in the Beddel kit ecosystem"
    ),
}

KIT_REGEN_HINT = (
    "Kit manifest JSON Schema is out of sync with SolutionKit model. "
    "Regenerate with: python spec/scripts/sync_kit_schema.py"
)


def test_kit_manifest_schema_in_sync() -> None:
    """The committed kit-manifest schema must match SolutionKit.model_json_schema()."""
    assert KIT_SCHEMA_PATH.exists(), f"Schema file not found: {KIT_SCHEMA_PATH}"

    committed = json.loads(KIT_SCHEMA_PATH.read_text())
    generated = {**SolutionKit.model_json_schema(), **_KIT_METADATA}

    assert committed == generated, KIT_REGEN_HINT


# --- Fixture-based schema coverage tests ---

FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "fixtures"

# Invalid fixtures that are structurally valid YAML but only semantically wrong.
# JSON Schema cannot catch these — they require runtime validation.
_SEMANTIC_ONLY_INVALID: set[str] = {"circular-ref.yaml"}


def _load_workflow_schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text())  # type: ignore[return-value]


def _discover_fixtures(subdir: str) -> list[pytest.param]:  # type: ignore[type-arg]
    folder = FIXTURES_ROOT / subdir
    files = sorted(folder.glob("*.yaml"))
    assert files, f"No YAML fixtures found in {folder}"
    return [pytest.param(f, id=f.name) for f in files]


@pytest.mark.parametrize("fixture_path", _discover_fixtures("valid"))
def test_valid_fixtures_pass_schema_validation(fixture_path: Path) -> None:
    """Every valid fixture must pass JSON Schema validation."""
    schema = _load_workflow_schema()
    instance = yaml.safe_load(fixture_path.read_text())
    jsonschema.validate(instance=instance, schema=schema)


@pytest.mark.parametrize("fixture_path", _discover_fixtures("invalid"))
def test_invalid_fixtures_fail_schema_validation(fixture_path: Path) -> None:
    """Every invalid fixture must be rejected by JSON Schema validation."""
    if fixture_path.name in _SEMANTIC_ONLY_INVALID:
        pytest.xfail(
            f"{fixture_path.name}: semantic error only — "
            "JSON Schema cannot catch invalid variable references"
        )

    schema = _load_workflow_schema()
    instance = yaml.safe_load(fixture_path.read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=instance, schema=schema)
