"""Regenerate spec/schemas/workflow.schema.json from the Workflow Pydantic model.

Usage:
    python spec/scripts/sync_workflow_schema.py

Ensures the committed JSON Schema stays in sync with code changes.
"""

from __future__ import annotations

import json
from pathlib import Path

from beddel.domain.models import Workflow

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "workflow.schema.json"

_METADATA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://beddel.dev/schemas/workflow.schema.json",
    "title": "Beddel Workflow",
    "description": "JSON Schema for Beddel YAML workflow definition files",
}


def generate_workflow_schema() -> dict[str, object]:
    """Generate the workflow JSON Schema with metadata fields."""
    schema = Workflow.model_json_schema()
    # Metadata fields override Pydantic defaults (title, description).
    return {**schema, **_METADATA}


def main() -> None:
    schema = generate_workflow_schema()
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"✅ Written {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
