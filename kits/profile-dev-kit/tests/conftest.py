"""Shared fixtures: put the kit module on sys.path and isolate Git env."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))


@pytest.fixture(autouse=True)
def _clean_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inherited GIT_* variables must never influence a test repository."""
    import os

    for key in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(key)
