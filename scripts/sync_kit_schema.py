"""Regenerate spec/kits/kit-manifest.schema.json from the SolutionKit Pydantic model.

Requires: pip install beddel (beddel-py SDK)

Usage:
    python scripts/sync_kit_schema.py

Ensures the committed JSON Schema stays in sync with code changes.

NOTE: This is a developer utility script. It is NOT run in CI.
      It requires the beddel-py SDK to be installed (pip install beddel).
"""

from __future__ import annotations

import json
from pathlib import Path

from beddel.domain.kit import SolutionKit

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "spec" / "kits" / "kit-manifest.schema.json"

_METADATA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://beddel.dev/schemas/kit-manifest.schema.json",
    "title": "Beddel Kit Manifest",
    "description": (
        "JSON Schema for kit.yaml manifest files in the Beddel kit ecosystem"
    ),
}


def generate_kit_schema() -> dict[str, object]:
    """Generate the kit manifest JSON Schema with metadata fields."""
    schema = SolutionKit.model_json_schema()
    # Metadata fields override Pydantic defaults (title, description).
    return {**schema, **_METADATA}


def main() -> None:
    schema = generate_kit_schema()
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"Written {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
