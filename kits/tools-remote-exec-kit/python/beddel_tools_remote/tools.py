"""Beddel tools-remote-exec-kit — 3 typed async remote/VM execution tools.

Wraps the ``multipass`` CLI via ``asyncio.create_subprocess_exec``
with timeout protection, output truncation, and VM existence validation.
V1 backend: Multipass. Future: SSH, Docker exec.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from beddel.tools import beddel_tool

MAX_OUTPUT_BYTES = 102_400  # 100KB


# ---------------------------------------------------------------------------
# Error Model
# ---------------------------------------------------------------------------


class RemoteToolError(RuntimeError):
    """Raised when a remote command fails or times out."""

    def __init__(self, command: str, exit_code: int, stderr: str, vm: str) -> None:
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        self.vm = vm
        super().__init__(f"Remote exec failed on {vm} (exit {exit_code}): {stderr[:300]}")


class VMNotFoundError(RemoteToolError):
    """Raised when the target VM does not exist."""

    pass


# ---------------------------------------------------------------------------
# Private Helpers
# ---------------------------------------------------------------------------


def _validate_backend(backend: str) -> None:
    """Validate backend parameter. Only 'multipass' supported in v1."""
    if backend != "multipass":
        raise NotImplementedError(
            f"Backend '{backend}' not implemented. Supported in v1: multipass"
        )


def _truncate(text: str, max_bytes: int = MAX_OUTPUT_BYTES) -> str:
    """Cap output at max_bytes — tail-preserving (keeps last portion)."""
    if len(text) <= max_bytes:
        return text
    return "[truncated]\n" + text[-max_bytes:]


async def _run_multipass(
    vm: str, command: str, workdir: str | None = None, timeout: int = 600
) -> tuple[int, str, str]:
    """Execute command on Multipass VM with timeout.

    Returns (exit_code, stdout, stderr). Raises RemoteToolError on timeout,
    VMNotFoundError when VM doesn't exist.
    """
    args = ["multipass", "exec", vm]
    if workdir:
        args += ["--working-directory", workdir]
    args += ["--", "bash", "-c", command]

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RemoteToolError(
            command=command, exit_code=-1, stderr="timeout", vm=vm
        )

    code = proc.returncode or 0
    stdout_s = stdout_b.decode(errors="replace")
    stderr_s = stderr_b.decode(errors="replace")

    # Detect nonexistent VM for fast-fail diagnostics
    if code != 0 and "instance does not exist" in stderr_s.lower():
        raise VMNotFoundError(
            command=command, exit_code=code, stderr=stderr_s, vm=vm
        )

    return code, stdout_s, stderr_s


# ---------------------------------------------------------------------------
# Tool Functions
# ---------------------------------------------------------------------------


@beddel_tool(
    name="remote_exec",
    description="Execute a command on a remote VM or container",
    category="remote",
)
async def remote_exec(
    vm: str,
    command: str,
    *,
    workdir: str | None = None,
    timeout: int = 600,
    backend: str = "multipass",
) -> dict[str, Any]:
    """Execute a command on a remote VM.

    Does NOT raise on non-zero exit (caller decides). Supports working
    directory, timeout, backend selection. Output truncated at 100KB.

    Args:
        vm: Name of the target VM.
        command: Shell command string to execute (passed to bash -c).
        workdir: Optional working directory on the remote VM.
        timeout: Maximum execution time in seconds (default 600 = 10min).
        backend: Execution backend (v1: only "multipass" supported).

    Returns:
        Dict with keys: exit_code, stdout, stderr, duration_ms, vm.

    Raises:
        NotImplementedError: If backend is not "multipass".
        VMNotFoundError: If the VM does not exist.
        RemoteToolError: On timeout (exit_code=-1, stderr="timeout").
    """
    _validate_backend(backend)

    start = time.monotonic()
    code, stdout, stderr = await _run_multipass(vm, command, workdir, timeout)
    elapsed_ms = (time.monotonic() - start) * 1000

    return {
        "exit_code": code,
        "stdout": _truncate(stdout),
        "stderr": _truncate(stderr),
        "duration_ms": round(elapsed_ms, 1),
        "vm": vm,
    }


@beddel_tool(
    name="remote_health_check",
    description="Check if a remote VM is reachable and test file existence",
    category="remote",
)
async def remote_health_check(
    vm: str,
    *,
    test_files: list[str] | None = None,
    backend: str = "multipass",
) -> dict[str, Any]:
    """Check if a remote VM is reachable and optionally test file existence.

    Uses ``multipass info`` (JSON format) to check VM state. If not Running,
    returns reachable=False without testing files.

    Args:
        vm: Name of the target VM.
        test_files: Optional list of file paths to test for existence.
        backend: Execution backend (v1: only "multipass" supported).

    Returns:
        Dict with keys: reachable, files_readable, files_missing, vm_status.

    Raises:
        NotImplementedError: If backend is not "multipass".
    """
    _validate_backend(backend)

    # Check VM state via multipass info
    proc = await asyncio.create_subprocess_exec(
        "multipass", "info", vm, "--format", "json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await proc.communicate()

    if proc.returncode != 0:
        stderr_s = stderr_b.decode(errors="replace")
        if "instance does not exist" in stderr_s.lower():
            raise VMNotFoundError(
                command=f"multipass info {vm}",
                exit_code=proc.returncode or 1,
                stderr=stderr_s,
                vm=vm,
            )
        return {
            "reachable": False,
            "files_readable": [],
            "files_missing": test_files or [],
            "vm_status": "Unknown",
        }

    # Parse JSON to get state
    try:
        info = json.loads(stdout_b.decode(errors="replace"))
        vm_status = info.get("info", {}).get(vm, {}).get("state", "Unknown")
    except (json.JSONDecodeError, KeyError):
        vm_status = "Unknown"

    if vm_status != "Running":
        return {
            "reachable": False,
            "files_readable": [],
            "files_missing": test_files or [],
            "vm_status": vm_status,
        }

    # Test file existence
    files_readable: list[str] = []
    files_missing: list[str] = []

    if test_files:
        for file_path in test_files:
            test_proc = await asyncio.create_subprocess_exec(
                "multipass", "exec", vm, "--", "test", "-r", file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await test_proc.communicate()
            if test_proc.returncode == 0:
                files_readable.append(file_path)
            else:
                files_missing.append(file_path)

    return {
        "reachable": True,
        "files_readable": files_readable,
        "files_missing": files_missing,
        "vm_status": vm_status,
    }


@beddel_tool(
    name="remote_file_read",
    description="Read a file from a remote VM",
    category="remote",
)
async def remote_file_read(
    vm: str,
    path: str,
    *,
    workdir: str | None = None,
    max_bytes: int = 65_536,
    backend: str = "multipass",
) -> dict[str, Any]:
    """Read a file from a remote VM with size cap.

    Uses ``head -c max_bytes`` for server-side truncation — the full file
    is never transferred even if enormous.

    Args:
        vm: Name of the target VM.
        path: Absolute path to the file on the remote VM.
        workdir: Optional working directory (unused for file reads, kept for API consistency).
        max_bytes: Maximum bytes to read (default 65536 = 64KB).
        backend: Execution backend (v1: only "multipass" supported).

    Returns:
        Dict with keys: content, size_bytes, truncated, path.

    Raises:
        NotImplementedError: If backend is not "multipass".
        VMNotFoundError: If the VM does not exist.
        RemoteToolError: If the file does not exist on the VM.
    """
    _validate_backend(backend)

    command = f"head -c {max_bytes} {path}"
    args = ["multipass", "exec", vm, "--", "bash", "-c", command]

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await proc.communicate()

    code = proc.returncode or 0
    stdout_s = stdout_b.decode(errors="replace")
    stderr_s = stderr_b.decode(errors="replace")

    # Detect nonexistent VM
    if code != 0 and "instance does not exist" in stderr_s.lower():
        raise VMNotFoundError(
            command=command, exit_code=code, stderr=stderr_s, vm=vm
        )

    # Detect file not found
    if code != 0:
        raise RemoteToolError(
            command=command, exit_code=code, stderr=stderr_s, vm=vm
        )

    size_bytes = len(stdout_s.encode("utf-8"))
    truncated = size_bytes >= max_bytes

    return {
        "content": stdout_s,
        "size_bytes": size_bytes,
        "truncated": truncated,
        "path": path,
    }
