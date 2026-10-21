"""AC1: manifest validates, kit is discovered cleanly, tool imports with metadata."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml
from beddel.domain.kit import SolutionKit
from beddel.tools.kits import discover_kits

KIT_ROOT = Path(__file__).resolve().parent.parent
KITS_DIR = KIT_ROOT.parent
KIT_NAME = "profile-dev-kit"
_TOOLS = [
    "profile_preflight",
    "profile_ratify_inventory",
    "profile_bind_inventory",
    "profile_record_change",
    "profile_derive_impact",
    "profile_run_gate",
    "profile_declare_non_applicability",
]


def _manifest() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((KIT_ROOT / "kit.yaml").read_text())
    return data


def test_manifest_validates_against_solution_kit() -> None:
    kit = SolutionKit(**_manifest())
    assert kit.name == KIT_NAME
    assert kit.targets["python"]["module"] == "beddel_profile_dev"
    assert kit.targets["typescript"]["status"] == "unavailable"
    assert "AD-15" in kit.targets["typescript"]["unavailable_reason"]


def test_category_is_profile() -> None:
    assert _manifest()["category"] == "profile"


def test_discovered_without_errors_or_skips() -> None:
    result = discover_kits([KITS_DIR])
    assert KIT_NAME in {m.kit.name for m in result.manifests}
    assert all(e.kit_name != KIT_NAME for e in result.errors)
    assert KIT_NAME not in result.skipped


def test_every_declared_tool_imports_with_metadata() -> None:
    kit = SolutionKit(**_manifest())
    assert [t.name for t in kit.tools] == _TOOLS
    for tool in kit.tools:
        module_path, func_name = tool.target.split(":")
        fn = getattr(importlib.import_module(module_path), func_name)
        meta = fn._beddel_tool_meta
        assert meta["name"] == tool.name
        assert meta["category"] == "profile"


def test_load_kit_registers_the_declared_tool() -> None:
    from beddel.domain.kit import parse_kit_manifest
    from beddel.tools.kits import load_kit

    tools = load_kit(parse_kit_manifest(KIT_ROOT / "kit.yaml"))
    assert set(tools) == set(_TOOLS)


def test_kit_yaml_config_block_matches_config_module() -> None:
    from beddel_profile_dev import config as cfg

    documented = _manifest()["config"]
    assert tuple(documented["gate_executables"]) == cfg.GATE_EXECUTABLES
    assert tuple(documented["required_env_keys"]) == cfg.REQUIRED_ENV_KEYS
    assert documented["inventory_dir"] == cfg.INVENTORY_DIR
    assert documented["records_dir"] == cfg.RECORDS_DIR
    assert tuple(tuple(c) for c in documented["gate_commands"]) == cfg.GATE_COMMANDS
    assert documented["gate_timeout_seconds"] == cfg.GATE_TIMEOUT_SECONDS
    assert documented["gate_total_timeout_seconds"] == cfg.GATE_TOTAL_TIMEOUT_SECONDS


def test_manifest_declares_all_workflows_and_python_targets() -> None:
    manifest = _manifest()
    assert [w["name"] for w in manifest["workflows"]] == [
        "verify-change",
        "ratify-inventory",
        "declare-non-applicability",
    ]
    declared = {t["name"] for t in manifest["tools"]}
    targeted = {t["name"] for t in manifest["targets"]["python"]["tools"]}
    assert declared == targeted == set(_TOOLS)


def test_registry_lists_the_kit() -> None:
    import json

    entries = json.loads((KITS_DIR / "registry.json").read_text())
    assert any(e["name"] == KIT_NAME and e["category"] == "profile" for e in entries)
