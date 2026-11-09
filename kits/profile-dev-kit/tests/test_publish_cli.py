"""CLI publication workflow tests with an in-process fake protocol kit."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from beddel_profile_dev._io import records_root
from beddel_profile_dev.tools.report import profile_record_report

from ._helpers import change_fixture
from .test_publication import _recorded_publication_fixture, _records_snapshot
from .test_report import _prepare
from .test_run_cli import _beddel_argv

KIT_ROOT = Path(__file__).resolve().parent.parent
PUBLISH = KIT_ROOT / "workflows" / "publish-reverification.yaml"

_FAKE_KIT_YAML = """\
name: protocol-mcp-kit
version: 0.0.0
description: Fake protocol kit for publication tests
author: tests
adapters:
- port: IMCPClient
  implementation: StreamableHTTPMCPClient
  description: fake
targets:
  python:
    status: implemented
    module: beddel_protocol_mcp
    dependencies: []
    adapters:
    - port: IMCPClient
      name: mcp-streamable-http
      target: beddel_protocol_mcp.http_client:StreamableHTTPMCPClient
"""

_FAKE_INIT = """\
from beddel_protocol_mcp.http_client import StreamableHTTPMCPClient
from beddel_protocol_mcp.schema_validator import validate_tool_arguments

__all__ = ["StreamableHTTPMCPClient", "validate_tool_arguments"]
"""

_FAKE_CLIENT = """\
import asyncio
import json
import os
from pathlib import Path

from beddel.domain.errors import MCPError
from beddel.error_codes import (
    MCP_AUTHORIZATION_REQUIRED,
    MCP_CONNECTION_FAILED,
    MCP_SCHEMA_VALIDATION_FAILED,
    MCP_TOOL_INVOCATION_FAILED,
)


class StreamableHTTPMCPClient:
    def __init__(self, *, transport, endpoint, authorization):
        self.endpoint = endpoint

    async def list_tools(self):
        mode = os.environ.get("FAKE_MCP_MODE", "ok")
        if mode == "unreachable":
            raise MCPError(MCP_CONNECTION_FAILED, "FAKE-MCP-MARKER")
        if mode == "token":
            raise MCPError(MCP_AUTHORIZATION_REQUIRED, "FAKE-MCP-MARKER")
        return [{
            "name": "write_copy",
            "inputSchema": {
                "type": "object",
                "properties": {"entry": {"type": "object"}},
                "required": ["entry"],
            },
        }]

    async def call_tool(self, name, arguments):
        log = os.environ.get("FAKE_MCP_LOG")
        if log:
            with Path(log).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"tool": name, "arguments": arguments}) + "\\n")
        mode = os.environ.get("FAKE_MCP_MODE", "ok")
        if mode == "unreachable":
            raise MCPError(MCP_CONNECTION_FAILED, "FAKE-MCP-MARKER")
        if mode == "token":
            raise MCPError(MCP_AUTHORIZATION_REQUIRED, "FAKE-MCP-MARKER")
        if mode == "rejected":
            raise MCPError(MCP_SCHEMA_VALIDATION_FAILED, "FAKE-MCP-MARKER")
        if mode == "timeout":
            await asyncio.sleep(30)
        if mode == "server_error":
            raise MCPError(MCP_TOOL_INVOCATION_FAILED, "FAKE-MCP-MARKER")
        return {"ok": True}

    async def disconnect(self):
        return None
"""

_FAKE_VALIDATOR = """\
import os

from beddel.domain.errors import MCPError
from beddel.error_codes import MCP_SCHEMA_VALIDATION_FAILED


def validate_tool_arguments(arguments, schema):
    if os.environ.get("FAKE_MCP_MODE") == "rejected":
        raise MCPError(MCP_SCHEMA_VALIDATION_FAILED, "FAKE-MCP-MARKER")
    if "entry" not in arguments:
        raise MCPError(MCP_SCHEMA_VALIDATION_FAILED, "FAKE-MCP-MARKER")
"""


def _kit_copy(tmp_path: Path) -> Path:
    kits_dir = tmp_path / "kits"
    shutil.copytree(KIT_ROOT, kits_dir / "profile-dev-kit")
    return kits_dir


def _write_fake_protocol_kit(kits_dir: Path) -> None:
    package = kits_dir / "protocol-mcp-kit" / "python" / "beddel_protocol_mcp"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(_FAKE_INIT)
    (package / "http_client.py").write_text(
        "from ._client import StreamableHTTPMCPClient\n"
    )
    (package / "_client.py").write_text(_FAKE_CLIENT)
    (package / "schema_validator.py").write_text(_FAKE_VALIDATOR)
    (kits_dir / "protocol-mcp-kit" / "kit.yaml").write_text(_FAKE_KIT_YAML)


def _configure_home(tmp_path: Path, kits_dir: Path) -> Path:
    home = tmp_path / "home"
    config = home / ".config" / "beddel"
    config.mkdir(parents=True, exist_ok=True)
    (config / "config.json").write_text(json.dumps({"kits_paths": [str(kits_dir)]}))
    return home


def _run_json(
    workflow: Path,
    inputs: dict[str, str],
    tmp_path: Path,
    kits_dir: Path,
    **extra_env: str,
) -> subprocess.CompletedProcess[str]:
    home = _configure_home(tmp_path, kits_dir)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GIT_", "BEDDEL_", "PYTHON")) and key != "KIRO_API_KEY"
    }
    env.update({"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")})
    env.update(extra_env)
    args = [arg for key, value in inputs.items() for arg in ("-i", f"{key}={value}")]
    return subprocess.run(
        [*_beddel_argv(), "run", "--json-output", *args, str(workflow)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        timeout=60,
        check=False,
    )


def _inputs(repo: Path) -> dict[str, str]:
    return {"repo_path": str(repo), "change_id": "c1"}


def _shared_recorded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, dict[str, Any]]:
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    return _recorded_publication_fixture(tmp_path, monkeypatch)


def _read_log(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_success_passes_the_stored_entry_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, records, stored = _shared_recorded(tmp_path, monkeypatch)
    before = _records_snapshot(records)
    kits_dir = _kit_copy(tmp_path)
    _write_fake_protocol_kit(kits_dir)
    log = tmp_path / "mcp.jsonl"
    result = _run_json(
        kits_dir / "profile-dev-kit/workflows/publish-reverification.yaml",
        _inputs(repo),
        tmp_path,
        kits_dir,
        FAKE_MCP_LOG=str(log),
        FAKE_MCP_MODE="ok",
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["publish"]["tool"] == "write_copy"
    assert _read_log(log) == [
        {"tool": "write_copy", "arguments": {"entry": stored["reverification"]}}
    ]
    assert _records_snapshot(records) == before


@pytest.mark.parametrize(
    ("mode", "code"),
    [
        ("unreachable", "BEDDEL-MCP-600"),
        ("token", "BEDDEL-MCP-605"),
        ("timeout", "BEDDEL-PRIM-303"),
        ("server_error", "BEDDEL-MCP-602"),
        ("rejected", "BEDDEL-MCP-603"),
    ],
)
def test_transport_failure_is_absorbed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    code: str,
) -> None:
    repo, records, _ = _shared_recorded(tmp_path, monkeypatch)
    before = _records_snapshot(records)
    kits_dir = _kit_copy(tmp_path)
    _write_fake_protocol_kit(kits_dir)
    log = tmp_path / "mcp.jsonl"
    workflow = kits_dir / "profile-dev-kit/workflows/publish-reverification.yaml"
    if mode == "timeout":
        document = yaml.safe_load(workflow.read_text())
        document["steps"][1]["config"]["timeout"] = 1
        workflow.write_text(yaml.safe_dump(document, sort_keys=False))
    result = _run_json(
        workflow,
        _inputs(repo),
        tmp_path,
        kits_dir,
        FAKE_MCP_LOG=str(log),
        FAKE_MCP_MODE=mode,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["publish"] is None
    assert output.get("_absorbed_errors") == [
        {"step_id": "publish", "error_code": code}
    ]
    assert "copy-destination.invalid" not in result.stdout
    assert "copy-destination.invalid" not in result.stderr
    assert "FAKE-MCP-MARKER" not in result.stdout
    assert "FAKE-MCP-MARKER" not in result.stderr
    assert _records_snapshot(records) == before


def test_composition_error_is_local_to_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, records, _ = _shared_recorded(tmp_path, monkeypatch)
    before = _records_snapshot(records)
    kits_dir = _kit_copy(tmp_path)
    result = _run_json(
        kits_dir / "profile-dev-kit/workflows/publish-reverification.yaml",
        _inputs(repo),
        tmp_path,
        kits_dir,
    )
    assert result.returncode == 1
    assert "Error [BEDDEL-EXEC-050]" in result.stderr
    assert not result.stdout.strip()
    assert "read" not in result.stdout
    assert "publish" not in result.stdout
    assert _records_snapshot(records) == before


def test_removed_publication_composition_leaves_read_report_usable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, _ = _shared_recorded(tmp_path, monkeypatch)
    kits_dir = _kit_copy(tmp_path)
    publish_workflow = (
        kits_dir / "profile-dev-kit/workflows/publish-reverification.yaml"
    )
    document = yaml.safe_load(publish_workflow.read_text())
    document["steps"] = document["steps"][:1]
    del document["mcp_servers"]
    document["allowed_tools"].remove("copy_destination:write_copy")
    publish_workflow.write_text(yaml.safe_dump(document, sort_keys=False))
    result = _run_json(publish_workflow, _inputs(repo), tmp_path, kits_dir)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output.get("read", {}).get("result", {}).get("reverification") is not None
    assert "publish" not in output

    read_workflow = kits_dir / "profile-dev-kit/workflows/read-report.yaml"
    result = _run_json(read_workflow, _inputs(repo), tmp_path, kits_dir)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output.get("read", {}).get("result", {}).get("report") is not None, output


def test_repeated_successful_publication_makes_two_identical_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, records, stored = _shared_recorded(tmp_path, monkeypatch)
    before = _records_snapshot(records)
    kits_dir = _kit_copy(tmp_path)
    _write_fake_protocol_kit(kits_dir)
    log = tmp_path / "mcp.jsonl"
    workflow = kits_dir / "profile-dev-kit/workflows/publish-reverification.yaml"
    for _ in range(2):
        result = _run_json(
            workflow,
            _inputs(repo),
            tmp_path,
            kits_dir,
            FAKE_MCP_LOG=str(log),
            FAKE_MCP_MODE="ok",
        )
        assert result.returncode == 0, result.stderr
    assert _read_log(log) == [
        {"tool": "write_copy", "arguments": {"entry": stored["reverification"]}},
        {"tool": "write_copy", "arguments": {"entry": stored["reverification"]}},
    ]
    assert _records_snapshot(records) == before


def _run_publish(
    tmp_path: Path,
    repo: Path,
    change_id: str = "c1",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    kits_dir = _kit_copy(tmp_path)
    _write_fake_protocol_kit(kits_dir)
    log = tmp_path / "mcp.jsonl"
    result = _run_json(
        kits_dir / "profile-dev-kit/workflows/publish-reverification.yaml",
        {"repo_path": str(repo), "change_id": change_id},
        tmp_path,
        kits_dir,
        FAKE_MCP_LOG=str(log),
        FAKE_MCP_MODE="ok",
    )
    return result, log


def _assert_cli_refusal(
    run: Callable[[], tuple[subprocess.CompletedProcess[str], Path]],
    records: Path,
    reason: str,
) -> None:
    before = _records_snapshot(records)
    result, log = run()
    assert result.returncode == 1
    assert "PROFILE_PUBLICATION_REFUSED" in result.stderr
    assert reason in result.stderr
    assert not log.exists()
    assert _records_snapshot(records) == before


def _shared_prepared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, str]:
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    repo, _, revision = _prepare(tmp_path)
    return repo, records_root(repo, "records/profile-dev"), revision


def test_cli_refuses_invalid_id_without_protocol_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, records, _ = _shared_recorded(tmp_path, monkeypatch)
    _assert_cli_refusal(
        lambda: _run_publish(tmp_path, repo, "not valid"), records, "id.invalid"
    )


def test_cli_refuses_unrecorded_change_without_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    repo, _, _ = change_fixture(tmp_path, lambda path: None)
    records = records_root(repo, "records/profile-dev")
    _assert_cli_refusal(
        lambda: _run_publish(tmp_path, repo), records, "change.unrecorded"
    )
    assert not records.exists()


def test_cli_refuses_absent_report_without_protocol_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, records, _ = _shared_prepared(tmp_path, monkeypatch)
    _assert_cli_refusal(lambda: _run_publish(tmp_path, repo), records, "report.absent")


def test_cli_refuses_not_applicable_entry_without_protocol_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, records, revision = _shared_prepared(tmp_path, monkeypatch)
    profile_record_report(str(repo), "c1", revision)
    _assert_cli_refusal(
        lambda: _run_publish(tmp_path, repo), records, "reverification.not_recorded"
    )


def test_cli_refuses_older_schema_without_protocol_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, records, _ = _shared_prepared(tmp_path, monkeypatch)
    report_dir = records / "changes/c1/report"
    report_dir.mkdir()
    (report_dir / "1.json").write_text(
        json.dumps(
            {
                "schema": "profile-dev/verification-report/1",
                "record": 1,
                "change_id": "c1",
                "revision": "a" * 40,
            }
        )
    )
    _assert_cli_refusal(
        lambda: _run_publish(tmp_path, repo), records, "reverification.not_recorded"
    )


def test_cli_refuses_malformed_report_without_protocol_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, records, _ = _shared_prepared(tmp_path, monkeypatch)
    report_dir = records / "changes/c1/report"
    report_dir.mkdir()
    (report_dir / "1.json").write_text("not json")
    _assert_cli_refusal(
        lambda: _run_publish(tmp_path, repo), records, "report.malformed"
    )


def test_cli_refuses_digest_mismatch_without_protocol_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, records, stored = _shared_recorded(tmp_path, monkeypatch)
    ref = next(
        item["ref"]
        for item in stored["reads"]
        if "/report/" not in item["ref"] and not item["ref"].endswith("change.json")
    )
    (records / ref).write_bytes(b"changed\n")
    _assert_cli_refusal(
        lambda: _run_publish(tmp_path, repo), records, "digest.mismatch"
    )
