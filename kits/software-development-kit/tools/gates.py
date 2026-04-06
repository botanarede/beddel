"""Validation gate tools — thin subprocess wrappers.

Each gate runs a CLI tool via :func:`subprocess.run` and returns a
structured result dict with ``passed``, ``output``, and ``exit_code``.
"""

from __future__ import annotations

import subprocess
from typing import Any

__all__ = [
    "mypy_gate",
    "pytest_gate",
    "ruff_check_gate",
    "ruff_format_gate",
]


def _run_gate(cmd: list[str], project_path: str) -> dict[str, Any]:
    """Run a command and return a structured gate result."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=project_path,
        shell=False,
    )
    return {
        "passed": result.returncode == 0,
        "output": (result.stdout + result.stderr).strip(),
        "exit_code": result.returncode,
    }


def pytest_gate(project_path: str = ".") -> dict[str, Any]:
    """Run pytest with fail-on-error."""
    return _run_gate(["pytest", "-x", "--timeout=30", "-q"], project_path)


def ruff_check_gate(project_path: str = ".") -> dict[str, Any]:
    """Run ruff linter."""
    return _run_gate(["ruff", "check", "."], project_path)


def ruff_format_gate(project_path: str = ".") -> dict[str, Any]:
    """Run ruff formatter check."""
    return _run_gate(["ruff", "format", "--check", "."], project_path)


def mypy_gate(project_path: str = ".") -> dict[str, Any]:
    """Run mypy type checker."""
    return _run_gate(["mypy", "."], project_path)
