"""Neutral tracked workflow and configured-term checks."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml

KIT_ROOT = Path(__file__).resolve().parents[1]


def _tracked_text_files(root: Path) -> list[Path]:
    output = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "-z"], text=False
    )
    return [
        root / relative
        for relative in output.decode().split("\0")
        if relative and (root / relative).is_file()
    ]


def test_untracked_destination_terms_are_absent() -> None:
    terms_path = os.environ.get("BEDDEL_GUARD_TERMS_FILE")
    if not terms_path or not Path(terms_path).is_file():
        pytest.skip("BEDDEL_GUARD_TERMS_FILE is not configured")
    terms = [
        line.strip()
        for line in Path(terms_path).read_text().splitlines()
        if line.strip()
    ]
    root = Path(
        subprocess.check_output(
            ["git", "-C", str(KIT_ROOT), "rev-parse", "--show-toplevel"],
            text=True,
        ).strip()
    )
    for path in _tracked_text_files(root):
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        folded = text.casefold()
        for index, term in enumerate(terms):
            assert term.casefold() not in folded, f"{path}:{index}"


def test_tracked_workflow_uses_a_non_routable_placeholder() -> None:
    workflow = yaml.safe_load(
        (KIT_ROOT / "workflows" / "publish-reverification.yaml").read_text()
    )
    endpoint = workflow["mcp_servers"]["copy_destination"]["endpoint"]
    host = urlsplit(endpoint).hostname
    assert host is not None and host.endswith(".invalid")
