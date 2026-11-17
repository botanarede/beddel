"""Kiro CLI agent adapter — subprocess-based agent execution via ``kiro-cli``.

This adapter bridges the Beddel domain core to the Kiro CLI, enabling
agent-style interactions through the ``kiro-cli chat --no-interactive``
command.  It implements the :class:`~beddel.domain.ports.IAgentAdapter`
protocol via structural subtyping (no explicit inheritance).

Each execution inherits the caller's cwd and environment, closes stdin,
and is bounded by the constructor timeout.  Interactive trust maps
``read-only`` to ``--trust-tools=`` and ``workspace-write`` to ``-a``;
headless trust uses ``trust_tools`` or defaults to ``--trust-all-tools``.
The CLI reports no changed-file list, so successful results always use
``files_changed=[]``.

The CLI is discovered from ``~/.local/bin/kiro-cli`` or via
``shutil.which``.  The adapter never installs the CLI during a workflow run.

Headless mode is activated when an ``api_key`` is provided or the
``KIRO_API_KEY`` environment variable is set.  In headless mode, the
sandbox parameter is ignored and tool trust is controlled exclusively
via the ``trust_tools`` constructor parameter.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from beddel.domain.errors import AgentError
from beddel.domain.models import AgentResult
from beddel.error_codes import (
    AGENT_EXECUTION_FAILED,
    AGENT_STREAM_INTERRUPTED,
    AGENT_TIMEOUT,
)

from beddel_agent_kiro import hook
from beddel_agent_kiro.errors import KIRO_AGENT_INVALID, KIRO_CLI_MISSING

__all__ = ["KiroCLIAgentAdapter"]

_DEFAULT_CLI_PATH = Path.home() / ".local" / "bin" / "kiro-cli"


_REAP_GRACE_SECONDS = 2.0


async def _terminate(proc: asyncio.subprocess.Process) -> None:
    """Kill a subprocess during timeout or cancellation and bound the reap.

    ``Process.wait`` only returns after the output pipes close, so a child
    of the CLI that inherited them would otherwise keep a timed-out stage
    waiting.  The direct child is reaped by the event loop either way.
    """
    with contextlib.suppress(ProcessLookupError):
        proc.kill()
    with contextlib.suppress(TimeoutError):
        async with asyncio.timeout(_REAP_GRACE_SECONDS):
            await proc.wait()


class KiroCLIAgentAdapter:
    """Kiro CLI agent adapter using subprocess execution.

    Implements the ``IAgentAdapter`` protocol structurally by exposing
    :meth:`execute` and :meth:`stream` with matching signatures.  All
    interaction with the Kiro CLI happens through
    ``asyncio.create_subprocess_exec``.  The subprocess inherits the
    caller's cwd and environment, receives closed stdin, and is killed and
    reaped on timeout or cancellation.

    Args:
        model: Default model identifier for CLI invocations.
        cli_path: Explicit path to the ``kiro-cli`` binary.  When ``None``,
            auto-discovered from ``~/.local/bin/kiro-cli``, then
            ``shutil.which``.  Missing binaries raise ``KIRO_CLI_MISSING``.
        timeout: Maximum execution time in seconds.  The subprocess is
            terminated and reaped when this bound expires or the caller
            cancels the execution.
        api_key: Optional API key for headless mode.  When provided (or
            when ``KIRO_API_KEY`` env var is set), the adapter operates
            in headless mode where sandbox is ignored and tool trust is
            controlled via ``trust_tools``.
        trust_tools: Optional list of tool names to trust in headless mode.
            When ``None`` and headless is active, ``--trust-all-tools`` is
            appended.  When a list is provided, ``--trust-tools=<csv>`` is
            appended instead.
        agent: Installed Kiro agent name used when ``tools`` is absent.
        pointers_dir: Directory containing cwd-keyed stage policy pointers.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4.6",
        cli_path: Path | None = None,
        timeout: int = 600,
        api_key: str | None = None,
        trust_tools: list[str] | None = None,
        agent: str = "beddel-delivery",
        pointers_dir: Path | None = None,
    ) -> None:
        self._model = model
        self._cli_path = cli_path or self._discover_cli()
        self._timeout = timeout
        self._headless: bool = bool(api_key or os.environ.get("KIRO_API_KEY"))
        self._trust_tools = trust_tools
        self._agent = agent
        self._pointers_dir = pointers_dir or hook.DEFAULT_POINTERS_DIR

    # ------------------------------------------------------------------
    # Binary discovery
    # ------------------------------------------------------------------

    @staticmethod
    def _discover_cli() -> Path:
        """Discover the already-installed ``kiro-cli`` binary.

        Discovery order:
            1. ``~/.local/bin/kiro-cli`` (default install location)
            2. ``shutil.which("kiro-cli")`` (PATH lookup)

        Raises:
            AgentError: ``KIRO_CLI_MISSING`` when neither location resolves.
        """
        if _DEFAULT_CLI_PATH.exists():
            return _DEFAULT_CLI_PATH

        which_result = shutil.which("kiro-cli")
        if which_result is not None:
            return Path(which_result)

        raise AgentError(
            code=KIRO_CLI_MISSING,
            message="kiro-cli is not installed or discoverable",
            details={
                "searched": [str(_DEFAULT_CLI_PATH), "shutil.which('kiro-cli')"],
                "hint": (
                    "Install kiro-cli manually: https://kiro.dev/docs/cli/ "
                    "(for example curl -fsSL https://cli.kiro.dev/install | bash), "
                    "then re-run."
                ),
            },
        )

    # ------------------------------------------------------------------
    # IAgentAdapter.execute
    # ------------------------------------------------------------------

    async def execute(
        self,
        prompt: str,
        *,
        model: str | None = None,
        sandbox: str = "read-only",
        tools: list[str] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Execute a prompt via ``kiro-cli chat --no-interactive``.

        Spawns the CLI as an async subprocess, captures stdout/stderr,
        and returns a structured :class:`AgentResult`.

        Args:
            prompt: The instruction or task to send to the agent.
            model: Optional model override.  Falls back to the adapter's
                configured model when ``None``.
            sandbox: Sandbox access level.  ``"read-only"`` appends
                ``--trust-tools=`` (empty value), ``"workspace-write"``
                and ``"danger-full-access"`` append ``-a``.  Ignored in
                headless mode.
            tools: Optional list of tool/agent config names.  A single
                element overrides the configured agent; an empty or absent
                list uses the configured default agent.
            output_schema: Optional JSON Schema dict (currently unused
                by the CLI backend).

        Returns:
            An :class:`AgentResult` with the CLI's stdout, exit code,
            and execution metadata.  ``files_changed`` is always empty
            because the CLI does not report a file list; callers reconcile
            repository changes separately.

        Raises:
            AgentError: ``BEDDEL-AGENT-702`` on timeout, or
                ``BEDDEL-AGENT-701`` on non-zero exit code.
        """
        model_used = model or self._model
        agent_used = tools[0] if tools else self._agent
        cmd = self._build_command(prompt, model=model_used, sandbox=sandbox, tools=tools)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._timeout,
            )
        except TimeoutError as exc:
            await _terminate(proc)
            raise AgentError(
                code=AGENT_TIMEOUT,
                message=f"Kiro CLI process timed out after {self._timeout}s",
                details={"timeout": self._timeout, "cmd": [str(c) for c in cmd]},
            ) from exc
        except asyncio.CancelledError:
            await _terminate(proc)
            raise

        stdout_text = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr_text = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        if proc.returncode != 0:
            if proc.returncode == 4:
                raise AgentError(
                    code=KIRO_AGENT_INVALID,
                    message=f"Kiro CLI agent is not installed: {agent_used}",
                    details={
                        "exit_code": proc.returncode,
                        "agent": agent_used,
                        "hint": "Install or verify the agent with beddel_agent_kiro.agent_config.",
                    },
                )
            raise AgentError(
                code=AGENT_EXECUTION_FAILED,
                message=f"Kiro CLI exited with code {proc.returncode}",
                details={
                    "exit_code": proc.returncode,
                    "stderr": stderr_text,
                    "cmd": [str(c) for c in cmd],
                },
            )

        return AgentResult(
            exit_code=proc.returncode,
            output=stdout_text,
            events=[hook.summarize(self._pointers_dir, Path.cwd())],
            files_changed=[],
            usage={"model": model_used, "timeout": self._timeout},
            agent_id="kiro-cli",
        )

    # ------------------------------------------------------------------
    # IAgentAdapter.stream
    # ------------------------------------------------------------------

    async def stream(
        self,
        prompt: str,
        *,
        model: str | None = None,
        sandbox: str = "read-only",
        tools: list[str] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream events from the Kiro CLI agent.

        Since the CLI subprocess does not support true streaming, this
        method calls :meth:`execute` internally and yields a single
        ``"complete"`` event with the full output.

        Args:
            prompt: The instruction or task to send to the agent.
            model: Optional model override.  Falls back to the adapter's
                configured model when ``None``.
            sandbox: Sandbox access level for the agent execution.
                Ignored in headless mode.
            tools: Optional list of tool/agent config names.

        Yields:
            A single event dict with keys ``"type"``, ``"output"``, and
            ``"exit_code"``.

        Raises:
            AgentError: ``BEDDEL-AGENT-703`` if the underlying execution
                times out (re-raised from ``BEDDEL-AGENT-702``).

        Note:
            This adapter emits exactly one terminal event per call because
            the CLI subprocess does not support incremental streaming.
            Callers expecting token-level or chunk-level events should be
            aware of this limitation.
        """
        try:
            result = await self.execute(prompt, model=model, sandbox=sandbox, tools=tools)
        except AgentError as exc:
            if exc.code == AGENT_TIMEOUT:
                raise AgentError(
                    code=AGENT_STREAM_INTERRUPTED,
                    message="Kiro CLI stream interrupted due to timeout",
                    details=exc.details,
                ) from exc
            raise
        yield {
            "type": "complete",
            "output": result.output,
            "exit_code": result.exit_code,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_command(
        self,
        prompt: str,
        *,
        model: str,
        sandbox: str,
        tools: list[str] | None,
    ) -> list[str]:
        """Build the CLI argument list for ``kiro-cli chat``.

        In headless mode, the ``sandbox`` parameter is ignored and tool
        trust is controlled via the adapter's ``trust_tools`` setting.
        In interactive mode, the existing sandbox mapping is preserved.

        Args:
            prompt: The prompt text (appended as the final positional arg).
            model: Model identifier to pass via ``--model``.
            sandbox: Sandbox level controlling trust flags (ignored in
                headless mode).
            tools: Optional tool/agent config names.

        Returns:
            A list of string arguments suitable for
            ``asyncio.create_subprocess_exec``.

        Raises:
            AgentError: ``BEDDEL-AGENT-701`` if ``sandbox`` is not a
                recognized value (interactive mode only), or if ``tools``
                contains more than one element (CLI supports at most one
                ``--agent`` flag).
        """
        cmd: list[str] = [str(self._cli_path), "chat", "--no-interactive"]

        if self._headless:
            # Headless mode: sandbox is ignored, trust controlled by constructor
            if self._trust_tools is None:
                cmd.append("--trust-all-tools")
            else:
                cmd.append(f"--trust-tools={','.join(self._trust_tools)}")
        else:
            # Interactive mode: existing sandbox mapping
            if sandbox == "read-only":
                cmd.append("--trust-tools=")
            elif sandbox in ("workspace-write", "danger-full-access"):
                cmd.append("-a")
            else:
                raise AgentError(
                    code=AGENT_EXECUTION_FAILED,
                    message=f"Unsupported sandbox value: {sandbox!r}",
                    details={
                        "sandbox": sandbox,
                        "supported": [
                            "read-only",
                            "workspace-write",
                            "danger-full-access",
                        ],
                    },
                )

        # Model and pinned engine
        cmd.extend(["--agent-engine", "v3", "--model", model])

        # Tools → --agent (CLI supports at most one --agent flag)
        if tools is not None and len(tools) > 1:
            raise AgentError(
                code=AGENT_EXECUTION_FAILED,
                message=f"Kiro CLI supports at most one agent, got {len(tools)}",
                details={"tools": tools},
            )
        agent_name = tools[0] if tools else self._agent
        cmd.extend(["--agent", agent_name])

        # Prompt as final positional arg
        cmd.append(prompt)

        return cmd
