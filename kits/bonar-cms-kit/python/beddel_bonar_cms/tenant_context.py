"""Shared tenant context — kit-internal path resolution and JSON I/O.

All paths resolve relative to the kit installation directory
(``repo/kits/bonar-cms-kit/``), never an external monorepo. This module has
no Node.js or subprocess dependencies — pure filesystem I/O.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from beddel_bonar_cms._errors import (
    CMS_INVALID_TENANT_ID,
    CMS_TENANT_NOT_FOUND,
    CMSError,
)

__all__ = [
    "get_kit_root",
    "get_tenants_dir",
    "list_tenant_ids",
    "load_tenant",
    "save_tenant",
    "validate_tenant_id",
]

# Strict lowercase kebab-case: alphanumeric segments separated by single
# hyphens. No leading/trailing hyphens, no double hyphens, no uppercase.
_TENANT_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

_TEMPLATE_STEM = "template"


def get_kit_root() -> Path:
    """Return the kit's root directory.

    This file lives at ``python/beddel_bonar_cms/tenant_context.py``, so the
    kit root is 3 parents up.

    Returns:
        Absolute path to ``repo/kits/bonar-cms-kit/``.
    """
    return Path(__file__).resolve().parent.parent.parent


def get_tenants_dir() -> Path:
    """Return the kit-internal tenants directory (``node/tenants/``).

    Returns:
        Absolute path to ``<kit_root>/node/tenants/``.
    """
    return get_kit_root() / "node" / "tenants"


def validate_tenant_id(tenant_id: str) -> None:
    """Validate that ``tenant_id`` is strict lowercase kebab-case.

    Args:
        tenant_id: Candidate tenant identifier.

    Raises:
        CMSError: With code ``CMS_INVALID_TENANT_ID`` if ``tenant_id`` does
            not match ``^[a-z0-9]+(-[a-z0-9]+)*$``.
    """
    if not _TENANT_ID_RE.match(tenant_id):
        raise CMSError(
            CMS_INVALID_TENANT_ID,
            f"Invalid tenant_id {tenant_id!r}: must be lowercase kebab-case "
            "(alphanumeric segments separated by single hyphens)",
            {"tenant_id": tenant_id},
        )


def load_tenant(tenant_id: str) -> dict[str, Any]:
    """Load a tenant's JSON config by ID.

    Args:
        tenant_id: Tenant identifier (validated before lookup).

    Returns:
        Parsed tenant config dict.

    Raises:
        CMSError: With code ``CMS_INVALID_TENANT_ID`` if the ID is invalid,
            or ``CMS_TENANT_NOT_FOUND`` if no matching file exists.
    """
    validate_tenant_id(tenant_id)
    path = get_tenants_dir() / f"{tenant_id}.json"
    if not path.exists():
        raise CMSError(
            CMS_TENANT_NOT_FOUND,
            f"Tenant config not found: {tenant_id!r}",
            {"tenant_id": tenant_id, "path": str(path)},
        )
    return json.loads(path.read_text(encoding="utf-8"))


def save_tenant(tenant_id: str, data: dict[str, Any]) -> None:
    """Write a tenant's JSON config, creating the tenants dir if needed.

    Args:
        tenant_id: Tenant identifier (validated before write).
        data: Tenant config to serialize.

    Raises:
        CMSError: With code ``CMS_INVALID_TENANT_ID`` if the ID is invalid.
    """
    validate_tenant_id(tenant_id)
    tenants_dir = get_tenants_dir()
    tenants_dir.mkdir(parents=True, exist_ok=True)
    path = tenants_dir / f"{tenant_id}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def list_tenant_ids() -> list[str]:
    """List all tenant IDs present in the tenants directory.

    The ``template.json`` placeholder is excluded from the result.

    Returns:
        Sorted list of tenant IDs (file stems, excluding ``template``).
    """
    tenants_dir = get_tenants_dir()
    if not tenants_dir.exists():
        return []
    return sorted(
        path.stem for path in tenants_dir.glob("*.json") if path.stem != _TEMPLATE_STEM
    )
