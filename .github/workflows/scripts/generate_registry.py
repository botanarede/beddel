"""Generate kits/registry.json from all kits/*/kit.yaml files.

Run from the repo root:
    python3 .github/workflows/scripts/generate_registry.py

Outputs kits/registry.json sorted by kit name.
Schema: [{name, version, description, category}]
Category is inferred from the kit name prefix (first segment before '-').
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    print("Error: pyyaml is required. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def _infer_category(name: str) -> str:
    parts = name.split("-", 1)
    return parts[0] if len(parts) > 1 else "other"


def main() -> None:
    repo_root = Path(__file__).parent.parent.parent.parent  # repo/
    kits_dir = repo_root / "kits"

    if not kits_dir.is_dir():
        print(f"Error: kits directory not found at {kits_dir}", file=sys.stderr)
        sys.exit(1)

    entries = []
    for kit_yaml in sorted(kits_dir.glob("*/kit.yaml")):
        with open(kit_yaml) as f:
            data = yaml.safe_load(f) or {}
        name = data.get("name", kit_yaml.parent.name)
        entries.append(
            {
                "name": name,
                "version": data.get("version", "0.1.0"),
                "description": data.get("description", ""),
                "category": _infer_category(name),
            }
        )

    entries.sort(key=lambda e: e["name"])

    output = kits_dir / "registry.json"
    with open(output, "w") as f:
        json.dump(entries, f, indent=2)
        f.write("\n")

    print(f"Generated {output} with {len(entries)} entries.")


if __name__ == "__main__":
    main()
