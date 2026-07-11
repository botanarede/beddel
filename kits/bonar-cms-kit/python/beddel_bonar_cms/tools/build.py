"""build_site tool — Next.js static export via SafeSubprocessRunner.

Runs `next build` for a given tenant, producing a static HTML/CSS/JS export.
Uses SafeSubprocessRunner for security-hardened subprocess execution.
"""

from __future__ import annotations

import os
from pathlib import Path

from beddel_bonar_cms._errors import (
    CMS_BUILD_FAILED,
    CMSError,
)
from beddel_bonar_cms.tenant_context import get_kit_root, validate_tenant_id
from beddel.utils.subprocess import SafeSubprocessRunner

__all__ = ["build_site"]

_DEFAULT_TIMEOUT = 120


def build_site(
    tenant_id: str,
    *,
    node_env: str = "production",
    studio_path: Path | None = None,
) -> dict:
    """Build a Next.js static export for a tenant.

    Sets ``EXPORT_TENANT_ID`` env var and runs ``next build`` in the studio
    app directory via :class:`SafeSubprocessRunner`. Optionally runs
    ``copy-tenant-assets.sh`` before the build if it exists.

    Args:
        tenant_id: Tenant identifier (validated as kebab-case).
        node_env: NODE_ENV value for the build. Default ``"production"``.
        studio_path: Path to the Next.js studio app. Defaults to
            ``<kit_root>/node/apps/bonar-creator-studio``.

    Returns:
        Dict with keys:
        - ``success`` (bool): Whether the build succeeded.
        - ``output_dir`` (str): Path to the output directory (empty on failure).
        - ``build_log`` (str): Build stdout (or combined stdout+stderr on failure).

    Raises:
        CMSError: With code ``CMS_BUILD_FAILED`` if the studio path does not exist.
    """
    validate_tenant_id(tenant_id)

    kit_root = get_kit_root()
    resolved_studio = studio_path or (
        kit_root / "node" / "apps" / "bonar-creator-studio"
    )

    if not resolved_studio.exists():
        raise CMSError(
            CMS_BUILD_FAILED,
            f"Studio app path does not exist: {resolved_studio}",
            {"studio_path": str(resolved_studio), "tenant_id": tenant_id},
        )

    # Build environment — inherit PATH for node/npx resolution
    env = {
        "EXPORT_TENANT_ID": tenant_id,
        "NODE_ENV": node_env,
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", ""),
    }

    # Run copy-tenant-assets.sh if it exists
    assets_script = kit_root / "node" / "scripts" / "copy-tenant-assets.sh"
    if assets_script.exists():
        SafeSubprocessRunner.run(
            ["bash", str(assets_script)],
            cwd=str(kit_root / "node"),
            env=env,
            timeout=30,
        )

    # Run next build
    result = SafeSubprocessRunner.run(
        ["npx", "next", "build"],
        cwd=str(resolved_studio),
        env=env,
        timeout=_DEFAULT_TIMEOUT,
    )

    if result.timed_out:
        return {
            "success": False,
            "output_dir": "",
            "build_log": f"Build timed out after {_DEFAULT_TIMEOUT}s",
        }

    if result.exit_code != 0:
        combined_log = result.stdout
        if result.stderr:
            combined_log = (
                f"{combined_log}\n{result.stderr}" if combined_log else result.stderr
            )
        return {
            "success": False,
            "output_dir": "",
            "build_log": combined_log,
        }

    # Resolve output directory
    output_dir = kit_root / "node" / "sites" / tenant_id
    return {
        "success": True,
        "output_dir": str(output_dir),
        "build_log": result.stdout,
    }
