#!/usr/bin/env python3
"""validate-kits — schema + parity validation for the Beddel kit catalog.

Runs in two phases:
  1. schema-validate: every kits/*/kit.yaml validates against spec/kits/kit-manifest.schema.json
  2. parity-check: every kit declares both targets.python and targets.typescript;
     each block has a valid status enum value when present; peer-kit references
     in unavailable_reason resolve to existing kits.

Exit code: 0 on success, 1 on any validation error (with grouped error output).

Usage:
  python3 .github/workflows/scripts/validate.py            # both phases
  python3 .github/workflows/scripts/validate.py --schema   # phase 1 only
  python3 .github/workflows/scripts/validate.py --parity   # phase 2 only
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
KITS_DIR = REPO_ROOT / "kits"
SCHEMA_PATH = REPO_ROOT / "spec" / "kits" / "kit-manifest.schema.json"

VALID_STATUSES = {"implemented", "planned", "unavailable"}


def load_manifests() -> list[tuple[str, dict, Path]]:
    out = []
    for kit_dir in sorted(KITS_DIR.iterdir()):
        if not kit_dir.is_dir():
            continue
        manifest_path = kit_dir / "kit.yaml"
        if not manifest_path.is_file():
            continue
        try:
            data = yaml.safe_load(manifest_path.read_text())
        except yaml.YAMLError as e:
            print(f"::error file={manifest_path}::YAML parse error: {e}", file=sys.stderr)
            sys.exit(1)
        out.append((kit_dir.name, data, manifest_path))
    return out


def validate_schema(manifests: list[tuple[str, dict, Path]]) -> int:
    print("=" * 60)
    print("Phase 1: schema-validate")
    print("=" * 60)
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = Draft202012Validator(schema)
    errors = 0
    failed_kits: list[str] = []
    for name, data, path in manifests:
        kit_errors = list(validator.iter_errors(data))
        if kit_errors:
            errors += len(kit_errors)
            failed_kits.append(name)
            for err in kit_errors:
                loc = "/".join(str(x) for x in err.absolute_path) or "<root>"
                print(f"::error file={path}::[{name}] {loc}: {err.message}", file=sys.stderr)
        else:
            print(f"  ✓ {name}")
    passed = len(manifests) - len(failed_kits)
    if errors == 0:
        print(f"\nAll {len(manifests)} kits passed schema validation.")
    else:
        print(f"\nFAILED: {len(failed_kits)} kit(s) failed schema validation ({errors} total errors).", file=sys.stderr)
    return 0 if errors == 0 else 1


def validate_parity(manifests: list[tuple[str, dict, Path]]) -> int:
    print("\n" + "=" * 60)
    print("Phase 2: parity-check")
    print("=" * 60)
    errors = 0
    failed_kits: list[str] = []
    kit_names = {name for name, _, _ in manifests}

    for name, data, path in manifests:
        targets = data.get("targets") or {}
        kit_errors = 0

        # Rule 1: both blocks present
        for lang in ("python", "typescript"):
            if lang not in targets:
                print(f"::error file={path}::[{name}] missing targets.{lang} block", file=sys.stderr)
                errors += 1
                kit_errors += 1
                continue

            block = targets[lang] or {}

            # Rule 2: status enum (when present)
            status = block.get("status")
            if status is not None and status not in VALID_STATUSES:
                print(f"::error file={path}::[{name}] invalid targets.{lang}.status={status!r}; must be one of {sorted(VALID_STATUSES)}", file=sys.stderr)
                errors += 1
                kit_errors += 1

            # Rule 3: peer-kit reference resolution (when status=unavailable)
            if status == "unavailable":
                reason = block.get("unavailable_reason", "") or ""
                peer_refs = re.findall(r"\b([a-z][a-z0-9-]*-kit)\b", reason)
                for peer in peer_refs:
                    if peer not in kit_names:
                        print(f"::error file={path}::[{name}] targets.{lang}.unavailable_reason references peer kit {peer!r} which does not exist in kits/", file=sys.stderr)
                        errors += 1
                        kit_errors += 1

        if kit_errors == 0:
            print(f"  ✓ {name}")
        else:
            failed_kits.append(name)

    if errors == 0:
        print(f"\nAll {len(manifests)} kits passed parity checks.")
    else:
        print(f"\nFAILED: {len(failed_kits)} kit(s) failed parity checks ({errors} total errors).", file=sys.stderr)
    return 0 if errors == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", action="store_true", help="run schema phase only")
    parser.add_argument("--parity", action="store_true", help="run parity phase only")
    args = parser.parse_args()

    run_schema = args.schema or not args.parity
    run_parity = args.parity or not args.schema

    manifests = load_manifests()
    if not manifests:
        print(f"::error::no kit.yaml files found under {KITS_DIR}", file=sys.stderr)
        return 1

    rc = 0
    if run_schema:
        rc |= validate_schema(manifests)
    if run_parity:
        rc |= validate_parity(manifests)

    if rc == 0:
        print(f"\nAll {len(manifests)} kits passed schema + parity checks.")
    else:
        print(f"\nFAILED: validation completed with errors across {len(manifests)} kits.", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
