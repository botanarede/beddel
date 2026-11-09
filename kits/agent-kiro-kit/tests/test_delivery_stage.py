"""Real-subprocess tests for Delivery-stage Kiro adapter behavior."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

import beddel_agent_kiro.adapter as adapter_module
import pytest
from beddel.domain.errors import AgentError, BeddelError
from beddel.domain.executor import WorkflowExecutor
from beddel.domain.models import DefaultDependencies, Workflow
from beddel.domain.parser import WorkflowParser
from beddel.domain.registry import PrimitiveRegistry
from beddel.error_codes import (
    AGENT_EXECUTION_FAILED,
    AGENT_TIMEOUT,
    EXEC_STEP_FAILED,
    EXEC_TIMEOUT,
)
from beddel.primitives import register_builtins
from beddel.tools.kits import discover_kits, load_kit_adapters
from beddel_agent_kiro.adapter import KiroCLIAgentAdapter


@pytest.fixture
def fake_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Create an executable fake CLI that records its process context."""
    cli_path = tmp_path / "fake-kiro-cli"
    log_path = tmp_path / "fake-kiro-log.json"
    cli_path.write_text(
        f"""#!{sys.executable}
import json
import os
import sys
import time

record = {{
    "pid": os.getpid(),
    "cwd": os.getcwd(),
    "argv": sys.argv,
    "mark": os.environ.get("FAKE_KIRO_MARK"),
}}
with open(os.environ["FAKE_KIRO_LOG"], "w") as log_file:
    json.dump(record, log_file)

mode = os.environ.get("FAKE_KIRO_MODE", "ok")
if mode == "ok":
    sys.stdout.write("ok")
elif mode == "fail":
    sys.exit(3)
elif mode == "sleep":
    time.sleep(60)
elif mode == "grandchild":
    import subprocess

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(8)"])
    with open(os.environ["FAKE_KIRO_CHILD_LOG"], "w") as child_log:
        child_log.write(str(child.pid))
    time.sleep(60)
"""
    )
    cli_path.chmod(0o755)
    monkeypatch.setenv("FAKE_KIRO_LOG", str(log_path))
    monkeypatch.setenv("FAKE_KIRO_MODE", "ok")
    monkeypatch.delenv("KIRO_API_KEY", raising=False)
    return cli_path, log_path


def _read_record(log_path: Path) -> dict[str, object]:
    """Read the fake CLI record after the process has started."""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if log_path.exists():
            return json.loads(log_path.read_text())
        time.sleep(0.01)
    raise AssertionError("fake CLI did not write its process record")


def _assert_pid_gone(pid: int) -> None:
    """Assert that a recorded process exits within the stage cleanup bound."""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.01)
    raise AssertionError(f"process {pid} is still running")


@pytest.mark.asyncio
async def test_success_returns_structured_result(fake_cli: tuple[Path, Path]) -> None:
    cli_path, _log_path = fake_cli
    adapter = KiroCLIAgentAdapter(cli_path=cli_path, model="model-default", timeout=17)

    result = await adapter.execute("prompt")

    assert result.exit_code == 0
    assert result.output == "ok"
    assert result.events == []
    assert result.files_changed == []
    assert result.usage == {"model": "model-default", "timeout": 17}
    assert result.agent_id == "kiro-cli"


@pytest.mark.asyncio
async def test_argv_uses_model_agent_and_read_only_trust(
    fake_cli: tuple[Path, Path],
) -> None:
    cli_path, log_path = fake_cli
    adapter = KiroCLIAgentAdapter(cli_path=cli_path)

    await adapter.execute("prompt", model="m-x", sandbox="read-only", tools=["dev"])

    record = _read_record(log_path)
    assert record["argv"] == [
        str(cli_path),
        "chat",
        "--no-interactive",
        "--trust-tools=",
        "--model",
        "m-x",
        "--agent",
        "dev",
        "prompt",
    ]


@pytest.mark.asyncio
async def test_workspace_write_uses_declared_trust(fake_cli: tuple[Path, Path]) -> None:
    cli_path, log_path = fake_cli
    adapter = KiroCLIAgentAdapter(cli_path=cli_path)

    await adapter.execute("prompt", sandbox="workspace-write")

    assert "-a" in _read_record(log_path)["argv"]


@pytest.mark.asyncio
async def test_headless_default_uses_trust_all_without_api_key_argv(
    fake_cli: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cli_path, log_path = fake_cli
    dummy_key = "dummy-test-key"
    monkeypatch.setenv("KIRO_API_KEY", dummy_key)
    adapter = KiroCLIAgentAdapter(cli_path=cli_path)

    await adapter.execute("prompt", sandbox="read-only")

    argv = _read_record(log_path)["argv"]
    assert "--trust-all-tools" in argv
    assert dummy_key not in argv


@pytest.mark.asyncio
async def test_cwd_and_environment_are_inherited(
    fake_cli: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cli_path, log_path = fake_cli
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("FAKE_KIRO_MARK", "m")
    adapter = KiroCLIAgentAdapter(cli_path=cli_path)

    await adapter.execute("prompt")

    record = _read_record(log_path)
    assert record["cwd"] == str(repo)
    assert record["mark"] == "m"


@pytest.mark.asyncio
async def test_non_zero_exit_raises_agent_error(
    fake_cli: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cli_path, _log_path = fake_cli
    monkeypatch.setenv("FAKE_KIRO_MODE", "fail")
    adapter = KiroCLIAgentAdapter(cli_path=cli_path)

    with pytest.raises(AgentError) as exc_info:
        await adapter.execute("prompt")

    assert exc_info.value.code == AGENT_EXECUTION_FAILED
    assert exc_info.value.details["exit_code"] == 3


@pytest.mark.asyncio
async def test_adapter_timeout_kills_and_reaps_cli(
    fake_cli: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cli_path, log_path = fake_cli
    monkeypatch.setenv("FAKE_KIRO_MODE", "sleep")
    adapter = KiroCLIAgentAdapter(cli_path=cli_path, timeout=1)

    with pytest.raises(AgentError) as exc_info:
        await adapter.execute("prompt")

    assert exc_info.value.code == AGENT_TIMEOUT
    assert exc_info.value.details["timeout"] == 1
    _assert_pid_gone(int(_read_record(log_path)["pid"]))


def _delivery_executor(
    cli_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[WorkflowExecutor, Workflow]:
    """Build an executor and a one-step Delivery workflow with a no-arg adapter."""
    monkeypatch.setattr(adapter_module, "_DEFAULT_CLI_PATH", cli_path)
    adapter = KiroCLIAgentAdapter()
    workflow = WorkflowParser.parse(
        """
        id: delivery-stage
        name: Delivery stage
        steps:
          - id: deliver
            primitive: agent-exec
            config:
              adapter: kiro-cli
              prompt: implement the story
              sandbox: workspace-write
            timeout: 1
        """
    )
    registry = PrimitiveRegistry()
    register_builtins(registry)
    executor = WorkflowExecutor(
        registry,
        deps=DefaultDependencies(agent_registry={"kiro-cli": adapter}),
    )
    return executor, workflow


@pytest.mark.asyncio
async def test_timeout_does_not_wait_for_a_child_holding_the_pipes(
    fake_cli: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cli_path, log_path = fake_cli
    child_log = log_path.with_name("fake-kiro-child.pid")
    monkeypatch.setenv("FAKE_KIRO_MODE", "grandchild")
    monkeypatch.setenv("FAKE_KIRO_CHILD_LOG", str(child_log))
    adapter = KiroCLIAgentAdapter(cli_path=cli_path, timeout=1)

    started = time.monotonic()
    try:
        with pytest.raises(AgentError) as exc_info:
            await adapter.execute("prompt")
        elapsed = time.monotonic() - started
    finally:
        # Release the pipes held by the grandchild so the loop can close them.
        if child_log.exists():
            os.kill(int(child_log.read_text()), signal.SIGKILL)
        await asyncio.sleep(0.3)

    assert exc_info.value.code == AGENT_TIMEOUT
    assert elapsed < 6, "the reap must be bounded, the grandchild lives 8 s"
    _assert_pid_gone(int(_read_record(log_path)["pid"]))


@pytest.mark.asyncio
async def test_agent_exec_step_result_has_the_three_adapter_keys(
    fake_cli: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cli_path, _log_path = fake_cli
    executor, workflow = _delivery_executor(cli_path, monkeypatch)

    result = await executor.execute(workflow, {})

    step_result = result["step_results"]["deliver"]
    assert set(step_result) == {"output", "files_changed", "usage"}
    assert step_result["output"] == "ok"
    assert step_result["files_changed"] == []


@pytest.mark.asyncio
async def test_step_timeout_kills_cli_before_executor_returns(
    fake_cli: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    cli_path, log_path = fake_cli
    monkeypatch.setenv("FAKE_KIRO_MODE", "sleep")
    executor, workflow = _delivery_executor(cli_path, monkeypatch)

    with pytest.raises(BeddelError) as exc_info:
        await executor.execute(workflow, {})

    # The executor's default FAIL strategy wraps the step timeout in a step failure.
    assert exc_info.value.code == EXEC_STEP_FAILED
    cause = exc_info.value.__cause__
    assert isinstance(cause, BeddelError)
    assert cause.code == EXEC_TIMEOUT
    _assert_pid_gone(int(_read_record(log_path)["pid"]))


def test_no_arg_build_loads_manifest_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kit_root = Path(__file__).resolve().parent.parent
    monkeypatch.delenv("KIRO_API_KEY", raising=False)
    monkeypatch.setattr(adapter_module, "_DEFAULT_CLI_PATH", Path(sys.executable))

    discovery = discover_kits([kit_root.parent])
    manifest = next(
        item for item in discovery.manifests if item.kit.name == "agent-kiro-kit"
    )
    adapters = load_kit_adapters(manifest)

    adapter = adapters[("IAgentAdapter", "kiro-cli")]
    assert isinstance(adapter, KiroCLIAgentAdapter)
    assert adapter._timeout == 600
    assert adapter._trust_tools is None
