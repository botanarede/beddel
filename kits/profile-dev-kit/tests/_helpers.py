"""Fixture helpers: throw-away Git repositories with inventory versions."""

from __future__ import annotations

import copy
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

INVENTORY_DIR = ".beddel-profile/inventory"

GOOD: dict[str, Any] = {
    "version": "v1",
    "classes": [
        {"id": "gate-unit", "kind": "gate"},
        {"id": "review-arch", "kind": "review"},
    ],
    "components": [
        {"id": "api", "kind": "component", "path": "src/api.py"},
        {"id": "contracts", "kind": "shared_contract", "path": "src/contracts.yaml"},
    ],
    "criteria": [
        {"id": "tests-pass", "description": "Unit tests pass"},
        {"id": "arch-ok", "description": "Architecture reviewed"},
    ],
    "obligations": [
        {"class": "gate-unit", "affected_point": "api", "criterion": "tests-pass"},
        {"class": "review-arch", "affected_point": "api", "criterion": "arch-ok"},
        {
            "class": "gate-unit",
            "affected_point": "contracts",
            "criterion": "tests-pass",
        },
    ],
}


def good(version: str = "v1") -> dict[str, Any]:
    data = copy.deepcopy(GOOD)
    data["version"] = version
    return data


def git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-C",
            str(repo),
            *args,
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        env=git_env(),
        check=True,
    )
    return result.stdout.strip()


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True, env=git_env())
    return path


def commit_all(repo: Path, message: str = "fixture") -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def write_version(repo: Path, version: str, data: Any) -> Path:
    path = repo / INVENTORY_DIR / f"{version}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def make_source(repo: Path, *, with_contracts: bool = True) -> None:
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "api.py").write_text("x = 1\n")
    if with_contracts:
        (repo / "src" / "contracts.yaml").write_text("a: 1\n")
