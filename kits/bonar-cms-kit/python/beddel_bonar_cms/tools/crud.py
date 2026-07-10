"""Tenant CRUD tools — create, read, update, list.

All tools operate on kit-internal ``node/tenants/*.json`` files via
:mod:`beddel_bonar_cms.tenant_context`. Pure filesystem I/O — no Node.js or
subprocess dependencies.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from beddel.tools import beddel_tool
from beddel_bonar_cms._errors import CMS_TENANT_EXISTS, CMSError
from beddel_bonar_cms.tenant_context import (
    get_tenants_dir,
    list_tenant_ids,
    load_tenant,
    save_tenant,
    validate_tenant_id,
)

__all__ = ["create_tenant", "list_tenants", "read_tenant", "update_tenant"]

_logger = logging.getLogger(__name__)


def _deep_merge(base: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``changes`` into a copy of ``base``.

    Nested dicts are merged key-by-key. Any other value type (including
    lists) in ``changes`` fully replaces the corresponding value in
    ``base`` — list items are never merged.

    Args:
        base: Original dict (not mutated).
        changes: Partial dict whose values override/extend ``base``.

    Returns:
        A new dict with ``changes`` merged into ``base``.
    """
    merged = dict(base)
    for key, value in changes.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


@beddel_tool(
    name="create_tenant",
    description="Write new tenant config JSON to kit-internal tenants directory",
    category="crud",
)
def create_tenant(tenant_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """Create a new tenant config.

    Args:
        tenant_id: Desired tenant identifier (strict lowercase kebab-case).
        config: Tenant configuration to persist.

    Returns:
        ``{"success": True, "tenant_id": tenant_id, "path": str}``.

    Raises:
        CMSError: With code ``CMS_INVALID_TENANT_ID`` if the ID is invalid,
            or ``CMS_TENANT_EXISTS`` if a tenant with this ID already exists.
    """
    validate_tenant_id(tenant_id)
    if tenant_id in list_tenant_ids():
        raise CMSError(
            CMS_TENANT_EXISTS,
            f"Tenant already exists: {tenant_id!r}",
            {"tenant_id": tenant_id},
        )
    save_tenant(tenant_id, config)
    path = get_tenants_dir() / f"{tenant_id}.json"
    return {"success": True, "tenant_id": tenant_id, "path": str(path)}


@beddel_tool(
    name="read_tenant",
    description="Load tenant config by ID",
    category="crud",
)
def read_tenant(tenant_id: str) -> dict[str, Any]:
    """Load a tenant's full config by ID.

    Args:
        tenant_id: Tenant identifier.

    Returns:
        The tenant's config dict.

    Raises:
        CMSError: With code ``CMS_INVALID_TENANT_ID`` or
            ``CMS_TENANT_NOT_FOUND``.
    """
    return load_tenant(tenant_id)


@beddel_tool(
    name="update_tenant",
    description="Merge partial updates into existing tenant config",
    category="crud",
)
def update_tenant(tenant_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge partial ``changes`` into an existing tenant config.

    Args:
        tenant_id: Tenant identifier.
        changes: Partial config to merge (nested dicts merge recursively;
            other values, including lists, replace the existing value).

    Returns:
        The full, updated tenant config dict.

    Raises:
        CMSError: With code ``CMS_INVALID_TENANT_ID`` or
            ``CMS_TENANT_NOT_FOUND``.
    """
    existing = load_tenant(tenant_id)
    updated = _deep_merge(existing, changes)
    save_tenant(tenant_id, updated)
    return updated


@beddel_tool(
    name="list_tenants",
    description="List all tenant IDs with metadata",
    category="crud",
)
def list_tenants() -> dict[str, Any]:
    """List all tenants with basic metadata.

    Individual tenant files that fail to load (malformed JSON, etc.) are
    skipped with a logged warning rather than failing the whole listing.

    Returns:
        ``{"tenants": [{"id", "name", "domain", "last_modified"}, ...]}``
        sorted by ``id``.
    """
    tenants_dir = get_tenants_dir()
    entries: list[dict[str, Any]] = []
    for tenant_id in list_tenant_ids():
        path = tenants_dir / f"{tenant_id}.json"
        try:
            config = load_tenant(tenant_id)
        except (CMSError, ValueError, OSError):
            _logger.warning("Skipping unreadable tenant config: %s", tenant_id)
            continue

        site = config.get("site") if isinstance(config.get("site"), dict) else {}
        name = site.get("name", config.get("name", ""))
        domain = site.get("domain", config.get("domain", ""))
        last_modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()

        entries.append(
            {
                "id": tenant_id,
                "name": name,
                "domain": domain,
                "last_modified": last_modified,
            }
        )

    entries.sort(key=lambda entry: entry["id"])
    return {"tenants": entries}
