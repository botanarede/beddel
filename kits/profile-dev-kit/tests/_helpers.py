"""Fixture helpers: throw-away Git repositories with inventory versions."""

from __future__ import annotations

import copy
import os
import subprocess
import sys
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


def change_fixture(
    tmp_path: Path,
    mutate: Any = None,
    data: Any = None,
    *,
    actor: str = "tester",
) -> tuple[Path, str, str]:
    """A ratified repository: returns ``(repo, base_sha, revision_sha)``.

    ``mutate(repo)`` edits the work tree between the base and the revision.
    """
    from beddel_profile_dev.tools.ratify import profile_ratify_inventory

    repo = init_repo(tmp_path / "repo")
    make_source(repo)
    write_version(repo, "v1", good() if data is None else data)
    profile_ratify_inventory(str(repo), "v1", actor)
    base = commit_all(repo, "base")
    if mutate is not None:
        mutate(repo)
    return repo, base, commit_all(repo, "change")


def stub_gate_tools(tmp_path: Path) -> str:
    """Return a ``PATH`` whose ``ruff``, ``mypy`` and ``pytest`` are fast stubs.

    A stub prints its arguments, sleeps ``$STUB_SLEEP_<NAME>`` seconds (default
    0) and exits with ``$STUB_EXIT_<NAME>`` (default 0), so a test drives the
    Gate with the default command list without ever running the real tools.
    ``git`` still comes from the real ``PATH``.
    """
    bin_dir = tmp_path / "gate-bin"
    bin_dir.mkdir(exist_ok=True)
    for tool in ("ruff", "mypy", "pytest"):
        stub = bin_dir / tool
        if not stub.exists():
            name = tool.upper()
            stub.write_text(
                f"#!{sys.executable}\n"
                "import os, sys, time\n"
                "print('stub', *sys.argv[1:], flush=True)\n"
                f"time.sleep(float(os.environ.get('STUB_SLEEP_{name}', '0')))\n"
                f"sys.exit(int(os.environ.get('STUB_EXIT_{name}', '0')))\n"
            )
            stub.chmod(0o755)
    return os.pathsep.join([str(bin_dir), os.environ.get("PATH", "")])


class FakeReviewAdapter:
    """A stand-in for the review route: no CLI, no network, no credential.

    ``behavior`` is ``completed`` (returns ``output``), ``timeout`` (raises the
    adapter's timeout error), ``error`` (raises its execution error), ``os_error``
    (cannot start the route), ``hang`` (never returns) or ``crash`` (an
    unexpected exception that is not an adapter error).
    """

    def __init__(self, behavior: str = "completed", output: str = "canned review\n"):
        self.behavior = behavior
        self.output = output
        self.calls: list[dict[str, Any]] = []

    async def execute(
        self,
        prompt: str,
        *,
        model: str | None = None,
        sandbox: str = "read-only",
        tools: list[str] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> Any:
        import asyncio

        from beddel.domain.errors import AgentError
        from beddel.domain.models import AgentResult
        from beddel.error_codes import AGENT_EXECUTION_FAILED, AGENT_TIMEOUT

        self.calls.append(
            {
                "prompt": prompt,
                "model": model,
                "sandbox": sandbox,
                "tools": tools,
                "output_schema": output_schema,
                "api_key_in_env": "KIRO_API_KEY" in os.environ,
            }
        )
        if self.behavior == "timeout":
            raise AgentError(code=AGENT_TIMEOUT, message="fake review timed out")
        if self.behavior == "error":
            raise AgentError(
                code=AGENT_EXECUTION_FAILED, message="fake review failed: secret-xyz"
            )
        if self.behavior == "os_error":
            raise OSError("cannot start the fake route")
        if self.behavior == "crash":
            raise RuntimeError("unexpected")
        if self.behavior == "hang":
            await asyncio.sleep(3600)
        return AgentResult(
            exit_code=0,
            output=self.output,
            events=[],
            files_changed=[],
            usage={},
            agent_id="fake",
        )


def install_fake_review(
    monkeypatch: Any, adapter: FakeReviewAdapter | None = None
) -> tuple[FakeReviewAdapter, list[tuple[str, int]]]:
    """Replace the single adapter seam; return the fake and the factory calls."""
    from beddel_profile_dev import _adapters

    fake = adapter if adapter is not None else FakeReviewAdapter()
    factory_calls: list[tuple[str, int]] = []

    def _factory(agent_name: str, *, timeout_seconds: int) -> FakeReviewAdapter:
        factory_calls.append((agent_name, timeout_seconds))
        return fake

    monkeypatch.setattr(_adapters, "get_review_adapter", _factory)
    return fake, factory_calls


# Loaded by the CLI subprocess before ``beddel run`` starts: it replaces the
# same seam the in-process tests replace, so the real route is never reached.
_SITECUSTOMIZE = """\
import json
import os

_mode = os.environ.get("FAKE_REVIEW_MODE")
if _mode:
    from beddel.domain.errors import AgentError
    from beddel.domain.models import AgentResult
    from beddel.error_codes import AGENT_EXECUTION_FAILED, AGENT_TIMEOUT
    from beddel_profile_dev import _adapters

    class _Fake:
        async def execute(
            self, prompt, *, model=None, sandbox="read-only", tools=None,
            output_schema=None,
        ):
            record = {
                "model": model,
                "sandbox": sandbox,
                "tools": tools,
                "api_key_in_env": "KIRO_API_KEY" in os.environ,
                "prompt": prompt,
            }
            with open(os.environ["FAKE_REVIEW_LOG"], "a") as handle:
                handle.write(json.dumps(record) + "\\n")
            if _mode == "timeout":
                raise AgentError(code=AGENT_TIMEOUT, message="fake timeout")
            if _mode == "error":
                raise AgentError(code=AGENT_EXECUTION_FAILED, message="fake failure")
            return AgentResult(
                exit_code=0, output="canned review\\n", events=[],
                files_changed=[], usage={}, agent_id="fake",
            )

    def _factory(agent_name, *, timeout_seconds):
        return _Fake()

    _adapters.get_review_adapter = _factory
"""


def fake_review_env(
    tmp_path: Path, kit_python: Path, mode: str = "completed"
) -> dict[str, str]:
    """Environment that makes a ``beddel run`` subprocess use a fake review route.

    ``kit_python`` is the ``python/`` directory of the kit under test; the fake
    is installed on that very module. Calls are logged to ``review-calls.jsonl``.
    """
    inject = tmp_path / "review-inject"
    inject.mkdir(exist_ok=True)
    (inject / "sitecustomize.py").write_text(_SITECUSTOMIZE)
    return {
        "PYTHONPATH": os.pathsep.join([str(inject), str(kit_python)]),
        "FAKE_REVIEW_MODE": mode,
        "FAKE_REVIEW_LOG": str(tmp_path / "review-calls.jsonl"),
    }
