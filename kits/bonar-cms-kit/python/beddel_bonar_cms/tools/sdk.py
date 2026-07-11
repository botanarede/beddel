"""SDK tools — init_firebase_app, sync_tenant_cache, clear_cache.

Wraps bonarjs-sdk-alpha operations via SafeSubprocessRunner calling Node.js
scripts. Each script imports from @botanarede/bonarjs-sdk-alpha and outputs
JSON to stdout.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool
from beddel.utils.subprocess import SafeSubprocessRunner
from beddel_bonar_cms._errors import (
    CMS_NODE_NOT_FOUND,
    CMS_SDK_ERROR,
    CMS_SUBPROCESS_TIMEOUT,
    CMSError,
)
from beddel_bonar_cms.tenant_context import get_kit_root

__all__ = ["clear_cache", "init_firebase_app", "sync_tenant_cache"]

_DEFAULT_TIMEOUT = 60


def _node_dir() -> Path:
    """Return the Node.js directory within the kit."""
    return get_kit_root() / "node"


def _run_sdk_script(
    script: str,
    args: list[str] | None = None,
    *,
    env_extra: dict[str, str] | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Run a Node.js SDK script and parse its JSON output.

    Args:
        script: Script filename relative to node/scripts/.
        args: Additional CLI arguments.
        env_extra: Extra environment variables to inject.
        timeout: Subprocess timeout in seconds.

    Returns:
        Parsed JSON dict from script stdout.

    Raises:
        CMSError: On Node.js not found, timeout, or script failure.
    """
    node_dir = _node_dir()
    command = ["node", f"scripts/{script}"]
    if args:
        command.extend(args)

    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", ""),
        "NODE_ENV": "production",
    }
    # Pass through Firebase-related env vars
    for key in (
        "GOOGLE_APPLICATION_CREDENTIALS",
        "FIREBASE_PROJECT_ID",
        "FIREBASE_SERVICE_ACCOUNT_JSON",
    ):
        val = os.environ.get(key)
        if val:
            env[key] = val
    if env_extra:
        env.update(env_extra)

    try:
        result = SafeSubprocessRunner.run(
            command,
            cwd=str(node_dir),
            env=env,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise CMSError(
            code=CMS_NODE_NOT_FOUND,
            message="Node.js is not available on PATH",
            details={"error": str(exc)},
        ) from exc

    if result.timed_out:
        raise CMSError(
            code=CMS_SUBPROCESS_TIMEOUT,
            message=f"SDK script '{script}' timed out after {timeout}s",
            details={"script": script, "args": args},
        )

    if result.exit_code != 0:
        # Try to parse error from JSON output
        error_msg = result.stderr or result.stdout or "Unknown error"
        try:
            parsed = json.loads(result.stdout)
            error_msg = parsed.get("error", error_msg)
        except (json.JSONDecodeError, ValueError):
            pass
        raise CMSError(
            code=CMS_SDK_ERROR,
            message=f"SDK script '{script}' failed: {error_msg}",
            details={
                "script": script,
                "exit_code": result.exit_code,
                "stderr": result.stderr,
                "stdout": result.stdout,
            },
        )

    # Parse JSON output
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        raise CMSError(
            code=CMS_SDK_ERROR,
            message=f"Malformed output from SDK script '{script}': {result.stdout[:200]}",
            details={"stdout": result.stdout, "error": str(exc)},
        ) from exc


@beddel_tool(
    name="init_firebase_app",
    description="Initialize Firebase Admin SDK via bonarjs-sdk-alpha bootstrap",
    category="sdk",
)
def init_firebase_app(project_id: str) -> dict[str, Any]:
    """Initialize a Firebase Admin app via the SDK bootstrap script.

    Calls ``sdk-init-firebase.mjs`` which imports from ``@botanarede/bonarjs-sdk-alpha``
    and initializes the Firebase Admin SDK for the given project.

    Args:
        project_id: Firebase project identifier.

    Returns:
        ``{"success": True, "project_id": str, "initialized": True}``.

    Raises:
        CMSError: With code ``CMS_SDK_ERROR`` on script failure.
    """
    return _run_sdk_script("sdk-init-firebase.mjs", [project_id])


@beddel_tool(
    name="sync_tenant_cache",
    description="Sync tenant Firestore data to local JSON cache via SDK",
    category="sdk",
)
def sync_tenant_cache(tenant_id: str) -> dict[str, Any]:
    """Sync tenant data from Firestore to local JSON cache.

    Calls ``sdk-sync-cache.mjs`` which fetches tenant collections from Firestore
    and writes them to ``<kit_root>/node/cache/<tenant_id>/``.

    Args:
        tenant_id: Tenant identifier.

    Returns:
        ``{"success": True, "tenant_id": str, "cached_files": list[str]}``.

    Raises:
        CMSError: With code ``CMS_SDK_ERROR`` if tenant not found or Firestore fails.
    """
    return _run_sdk_script("sdk-sync-cache.mjs", [tenant_id])


@beddel_tool(
    name="clear_cache",
    description="Clear cached JSON files for a tenant or all tenants",
    category="sdk",
)
def clear_cache(tenant_id: str | None = None) -> dict[str, Any]:
    """Clear cached JSON files.

    Calls ``sdk-clear-cache.mjs`` which removes cached files from
    ``<kit_root>/node/cache/``.

    Args:
        tenant_id: Optional tenant identifier. If provided, clears only that
            tenant's cache. If None, clears all cached files.

    Returns:
        ``{"success": True, "cleared_count": int}``.

    Raises:
        CMSError: With code ``CMS_SDK_ERROR`` on script failure.
    """
    args = [tenant_id] if tenant_id else []
    return _run_sdk_script("sdk-clear-cache.mjs", args if args else None)
