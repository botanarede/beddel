"""preview_site + stop_preview tools — Dev server lifecycle management.

Starts and stops a long-running Next.js dev server for tenant preview.
Uses ``subprocess.Popen`` directly (NOT SafeSubprocessRunner) because the
dev server is a background process that runs until explicitly stopped.
"""

from __future__ import annotations

import os
import signal
import subprocess

from beddel_solution_cms._errors import (
    CMS_PREVIEW_FAILED,
    CMSError,
)
from beddel_solution_cms.tenant_context import get_kit_root, validate_tenant_id

__all__ = ["preview_site", "stop_preview"]


def preview_site(tenant_id: str, *, port: int = 3000) -> dict:
    """Start a Next.js dev server for a tenant.

    Spawns ``npx next dev -p {port}`` as a background process with
    ``EXPORT_TENANT_ID={tenant_id}`` in the environment. The process runs
    until :func:`stop_preview` is called with the returned PID.

    This is the ONLY non-blocking tool in the kit — all others use
    SafeSubprocessRunner which waits for completion.

    Args:
        tenant_id: Tenant identifier (validated as kebab-case).
        port: Port for the dev server. Default ``3000``.

    Returns:
        Dict with keys:
        - ``success`` (bool): Whether the server started.
        - ``url`` (str): Dev server URL (empty on failure).
        - ``pid`` (int): Process ID (0 on failure).

    Raises:
        CMSError: With code ``CMS_PREVIEW_FAILED`` if the process cannot be
            started (e.g. ``npx`` not found on PATH).
    """
    validate_tenant_id(tenant_id)

    kit_root = get_kit_root()
    cwd = str(kit_root / "node" / "apps" / "bonar-creator-studio")

    command = ["npx", "next", "dev", "-p", str(port)]

    env = {
        "EXPORT_TENANT_ID": tenant_id,
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", ""),
    }

    try:
        proc = subprocess.Popen(  # noqa: S603
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise CMSError(
            CMS_PREVIEW_FAILED,
            f"Failed to start dev server: {exc}",
            {"tenant_id": tenant_id, "port": port},
        )

    return {
        "success": True,
        "url": f"http://localhost:{port}",
        "pid": proc.pid,
    }


def stop_preview(pid: int) -> dict:
    """Stop a running preview dev server by PID.

    Sends ``SIGTERM`` to the process. If the process does not exist,
    returns a failure dict gracefully (no exception raised).

    Args:
        pid: Process ID returned by :func:`preview_site`.

    Returns:
        Dict with keys:
        - ``success`` (bool): Whether the signal was sent.
        - ``message`` (str): Human-readable status.
    """
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        return {
            "success": False,
            "message": "Process not found",
        }

    return {
        "success": True,
        "message": f"Process {pid} terminated",
    }
