"""Beddel tools-docker-kit — 4 typed async Docker Compose operations.

Wraps the ``docker compose`` CLI via ``asyncio.create_subprocess_exec``
with timeout protection, output truncation, and compose file validation.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool

MAX_OUTPUT_BYTES = 102_400  # 100KB


# ---------------------------------------------------------------------------
# Error Model
# ---------------------------------------------------------------------------


class DockerToolError(RuntimeError):
    """Raised when a docker subprocess exits non-zero or times out."""

    def __init__(self, command: str, exit_code: int, stderr: str) -> None:
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"docker command failed (exit {exit_code}): {stderr[:300]}")


# ---------------------------------------------------------------------------
# Private Helpers
# ---------------------------------------------------------------------------


def _truncate(text: str, max_bytes: int = MAX_OUTPUT_BYTES) -> str:
    """Cap output at max_bytes — tail-preserving (keeps last portion).

    Build errors and test failures appear at the end of output, not the beginning.
    """
    if len(text) <= max_bytes:
        return text
    return "[truncated]\n" + text[-max_bytes:]


def _validate_compose_file(compose_file: str) -> None:
    """Raise FileNotFoundError if compose file does not exist."""
    if not Path(compose_file).exists():
        raise FileNotFoundError(f"Compose file not found: {compose_file}")


async def _run_docker(
    *args: str,
    cwd: str | None = None,
    timeout: int = 1800,
    compose_file: str | None = None,
    service: str | None = None,
) -> tuple[int, str, str]:
    """Run docker command with timeout. Kills process and orphaned container on timeout."""
    proc = await asyncio.create_subprocess_exec(
        "docker",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        # Cleanup: kill orphaned container after timeout
        if compose_file and service:
            cleanup_proc = await asyncio.create_subprocess_exec(
                "docker",
                "compose",
                "-f",
                compose_file,
                "kill",
                service,
                cwd=cwd,
            )
            await cleanup_proc.wait()
        raise DockerToolError(
            command=f"docker {' '.join(args)}", exit_code=-1, stderr="timeout"
        )
    return (
        proc.returncode or 0,
        stdout_b.decode(errors="replace"),
        stderr_b.decode(errors="replace"),
    )


# ---------------------------------------------------------------------------
# Tool Functions
# ---------------------------------------------------------------------------


@beddel_tool(
    name="docker_compose_build",
    description="Build a Docker Compose service image",
    category="docker",
)
async def docker_compose_build(
    compose_file: str,
    service: str,
    *,
    profile: str | None = None,
    no_cache: bool = False,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Build a Docker Compose service image.

    Validates compose file exists before execution. Measures build time.
    Raises DockerToolError on build failure.

    Args:
        compose_file: Path to the docker-compose.yml file.
        service: Name of the service to build.
        profile: Optional Compose profile to activate.
        no_cache: If True, build without cache.
        cwd: Working directory for the command.

    Returns:
        Dict with keys: image_id, service, build_time_ms.
    """
    _validate_compose_file(compose_file)

    args: list[str] = ["compose", "-f", compose_file]
    if profile:
        args.extend(["--profile", profile])
    args.append("build")
    if no_cache:
        args.append("--no-cache")
    args.append(service)

    start = time.monotonic()
    exit_code, stdout, stderr = await _run_docker(*args, cwd=cwd)
    elapsed_ms = (time.monotonic() - start) * 1000

    if exit_code != 0:
        raise DockerToolError(
            command=f"docker {' '.join(args)}", exit_code=exit_code, stderr=stderr
        )

    # Parse image ID from output if available, fallback to service name
    image_id = f"{service}:latest"
    for line in stdout.splitlines():
        if "sha256:" in line.lower():
            parts = line.split("sha256:")
            if len(parts) > 1:
                image_id = f"sha256:{parts[1].strip()[:12]}"
                break

    return {
        "image_id": image_id,
        "service": service,
        "build_time_ms": round(elapsed_ms, 1),
    }


@beddel_tool(
    name="docker_compose_run",
    description="Run a one-off command in a Compose service container",
    category="docker",
)
async def docker_compose_run(
    compose_file: str,
    service: str,
    command: str,
    *,
    env: dict[str, str] | None = None,
    user: str | None = None,
    timeout: int = 1800,
    remove: bool = True,
    tty: bool = False,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Run a one-off command in a Compose service container.

    Does NOT raise on non-zero exit (caller decides). Supports env injection,
    custom user, timeout. Command executed via ``sh -c`` for POSIX compat.
    Output truncated at 100KB (tail-preserving).

    Args:
        compose_file: Path to the docker-compose.yml file.
        service: Name of the service to run in.
        command: Shell command to execute (passed to sh -c).
        env: Optional environment variables to inject.
        user: Optional user to run as inside the container.
        timeout: Maximum execution time in seconds (default 1800 = 30min).
        remove: If True, remove container after exit (--rm).
        tty: If False, disable pseudo-TTY allocation (-T).
        cwd: Working directory for the command.

    Returns:
        Dict with keys: exit_code, stdout, stderr, duration_ms.
    """
    _validate_compose_file(compose_file)

    args: list[str] = ["compose", "-f", compose_file, "run"]
    if remove:
        args.append("--rm")
    if not tty:
        args.append("-T")
    if user:
        args.extend(["--user", user])
    if env:
        for key, value in env.items():
            args.extend(["-e", f"{key}={value}"])
    args.extend([service, "sh", "-c", command])

    start = time.monotonic()
    try:
        exit_code, stdout, stderr = await _run_docker(
            *args,
            cwd=cwd,
            timeout=timeout,
            compose_file=compose_file,
            service=service,
        )
    except DockerToolError:
        # Timeout — return structured result instead of raising
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": "timeout",
            "duration_ms": round(elapsed_ms, 1),
        }
    elapsed_ms = (time.monotonic() - start) * 1000

    return {
        "exit_code": exit_code,
        "stdout": _truncate(stdout),
        "stderr": _truncate(stderr),
        "duration_ms": round(elapsed_ms, 1),
    }


@beddel_tool(
    name="docker_compose_up",
    description="Start Compose services",
    category="docker",
)
async def docker_compose_up(
    compose_file: str,
    *,
    services: list[str] | None = None,
    profile: str | None = None,
    detach: bool = True,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Start Compose services (detached by default).

    Reports which services started vs already running.
    Raises DockerToolError on failure.

    Args:
        compose_file: Path to the docker-compose.yml file.
        services: Optional list of specific services to start.
        profile: Optional Compose profile to activate.
        detach: If True, run in detached mode (-d).
        cwd: Working directory for the command.

    Returns:
        Dict with keys: services_started, already_running.
    """
    _validate_compose_file(compose_file)

    args: list[str] = ["compose", "-f", compose_file]
    if profile:
        args.extend(["--profile", profile])
    args.append("up")
    if detach:
        args.append("-d")
    if services:
        args.extend(services)

    exit_code, stdout, stderr = await _run_docker(*args, cwd=cwd)

    if exit_code != 0:
        raise DockerToolError(
            command=f"docker {' '.join(args)}", exit_code=exit_code, stderr=stderr
        )

    # Parse output for started/running services
    services_started: list[str] = []
    already_running: list[str] = []
    output = stdout + stderr  # docker compose may write to stderr
    for line in output.splitlines():
        lower = line.lower()
        if "started" in lower or "created" in lower:
            # Extract service name from lines like "Container project-web-1  Started"
            parts = line.split()
            if parts:
                services_started.append(parts[0].strip())
        elif "running" in lower:
            parts = line.split()
            if parts:
                already_running.append(parts[0].strip())

    return {
        "services_started": services_started,
        "already_running": already_running,
    }


@beddel_tool(
    name="docker_compose_down",
    description="Stop and remove Compose services",
    category="docker",
)
async def docker_compose_down(
    compose_file: str,
    *,
    profile: str | None = None,
    remove_volumes: bool = False,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Stop and remove Compose services. Optionally remove volumes.

    Raises DockerToolError on failure.

    Args:
        compose_file: Path to the docker-compose.yml file.
        profile: Optional Compose profile to activate.
        remove_volumes: If True, also remove named volumes (--volumes).
        cwd: Working directory for the command.

    Returns:
        Dict with keys: services_stopped, volumes_removed.
    """
    _validate_compose_file(compose_file)

    args: list[str] = ["compose", "-f", compose_file]
    if profile:
        args.extend(["--profile", profile])
    args.append("down")
    if remove_volumes:
        args.append("--volumes")

    exit_code, stdout, stderr = await _run_docker(*args, cwd=cwd)

    if exit_code != 0:
        raise DockerToolError(
            command=f"docker {' '.join(args)}", exit_code=exit_code, stderr=stderr
        )

    # Parse output for stopped services and removed volumes
    services_stopped: list[str] = []
    volumes_removed: list[str] = []
    output = stdout + stderr
    for line in output.splitlines():
        lower = line.lower()
        if "stopped" in lower or "removed" in lower:
            parts = line.split()
            if parts:
                name = parts[0].strip()
                if "volume" in lower:
                    volumes_removed.append(name)
                else:
                    services_stopped.append(name)

    return {
        "services_stopped": services_stopped,
        "volumes_removed": volumes_removed,
    }
