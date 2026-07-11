"""Admin tools — list_users, create_user, update_user_role, get_tenant_stats.

CRUD operations on JSON files in the admin data directory. No subprocess or
external service calls — pure filesystem I/O.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool
from beddel_bonar_cms._errors import CMS_ADMIN_ERROR, CMSError
from beddel_bonar_cms.tenant_context import get_kit_root

__all__ = ["create_user", "get_tenant_stats", "list_users", "update_user_role"]

_logger = logging.getLogger(__name__)

VALID_ROLES = {"admin", "editor", "viewer"}


def _get_users_dir() -> Path:
    """Return the admin users data directory, creating it if needed."""
    users_dir = get_kit_root() / "node" / "apps" / "admin" / "data" / "users"
    users_dir.mkdir(parents=True, exist_ok=True)
    return users_dir


def _load_user(user_id: str) -> dict[str, Any]:
    """Load a user JSON by ID."""
    path = _get_users_dir() / f"{user_id}.json"
    if not path.exists():
        raise CMSError(
            CMS_ADMIN_ERROR,
            f"User not found: {user_id!r}",
            {"user_id": user_id},
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _save_user(user_id: str, data: dict[str, Any]) -> None:
    """Save a user JSON by ID."""
    path = _get_users_dir() / f"{user_id}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _find_user_by_email(email: str) -> dict[str, Any] | None:
    """Find a user by email (case-insensitive). Returns None if not found."""
    users_dir = _get_users_dir()
    for path in users_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("email", "").lower() == email.lower():
                return data
        except (json.JSONDecodeError, OSError):
            _logger.warning("Skipping unreadable user file: %s", path.name)
    return None


@beddel_tool(
    name="list_users",
    description="List all admin users with metadata",
    category="admin",
)
def list_users() -> dict[str, Any]:
    """List all users from the admin data directory.

    Returns:
        ``{"users": [{"id", "email", "role", "created_at"}, ...]}``
        sorted by id.
    """
    users_dir = _get_users_dir()
    entries: list[dict[str, Any]] = []

    for path in users_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entries.append(
                {
                    "id": data.get("id", path.stem),
                    "email": data.get("email", ""),
                    "role": data.get("role", ""),
                    "created_at": data.get("created_at", ""),
                }
            )
        except (json.JSONDecodeError, OSError):
            _logger.warning("Skipping unreadable user file: %s", path.name)

    entries.sort(key=lambda e: e["id"])
    return {"users": entries}


@beddel_tool(
    name="create_user",
    description="Create a new admin user in the data directory",
    category="admin",
)
def create_user(email: str, role: str) -> dict[str, Any]:
    """Create a new user.

    Args:
        email: User email address.
        role: One of ``admin``, ``editor``, ``viewer``.

    Returns:
        ``{"success": True, "user_id": str, "email": str, "role": str}``.

    Raises:
        CMSError: With code ``CMS_ADMIN_ERROR`` if email already exists
            or role is invalid.
    """
    if role not in VALID_ROLES:
        raise CMSError(
            CMS_ADMIN_ERROR,
            f"Invalid role: {role!r}. Must be one of: {', '.join(sorted(VALID_ROLES))}",
            {"role": role},
        )

    existing = _find_user_by_email(email)
    if existing is not None:
        raise CMSError(
            CMS_ADMIN_ERROR,
            f"User with email already exists: {email!r}",
            {"email": email, "existing_user_id": existing.get("id")},
        )

    user_id = str(uuid.uuid4())
    now = datetime.now(tz=UTC).isoformat()
    user_data = {
        "id": user_id,
        "email": email,
        "role": role,
        "created_at": now,
    }
    _save_user(user_id, user_data)

    return {"success": True, "user_id": user_id, "email": email, "role": role}


@beddel_tool(
    name="update_user_role",
    description="Update an existing user's role",
    category="admin",
)
def update_user_role(user_id: str, role: str) -> dict[str, Any]:
    """Update a user's role.

    Args:
        user_id: User identifier.
        role: New role (``admin``, ``editor``, or ``viewer``).

    Returns:
        The full, updated user dict.

    Raises:
        CMSError: With code ``CMS_ADMIN_ERROR`` if user not found or
            role is invalid.
    """
    if role not in VALID_ROLES:
        raise CMSError(
            CMS_ADMIN_ERROR,
            f"Invalid role: {role!r}. Must be one of: {', '.join(sorted(VALID_ROLES))}",
            {"role": role},
        )

    user_data = _load_user(user_id)
    user_data["role"] = role
    _save_user(user_id, user_data)
    return user_data


@beddel_tool(
    name="get_tenant_stats",
    description="Get statistics for a tenant (user count, last build/deploy)",
    category="admin",
)
def get_tenant_stats(tenant_id: str) -> dict[str, Any]:
    """Get stats for a tenant.

    Counts users assigned to the tenant and reads build/deploy metadata.

    Args:
        tenant_id: Tenant identifier.

    Returns:
        ``{"tenant_id": str, "user_count": int,
          "last_build": str | None, "last_deploy": str | None}``.

    Raises:
        CMSError: With code ``CMS_ADMIN_ERROR`` if tenant does not exist.
    """
    kit_root = get_kit_root()
    tenant_path = kit_root / "node" / "tenants" / f"{tenant_id}.json"
    if not tenant_path.exists():
        raise CMSError(
            CMS_ADMIN_ERROR,
            f"Tenant not found: {tenant_id!r}",
            {"tenant_id": tenant_id},
        )

    # Count users assigned to this tenant
    users_dir = _get_users_dir()
    user_count = 0
    for path in users_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("tenant_id") == tenant_id:
                user_count += 1
        except (json.JSONDecodeError, OSError):
            continue

    # Read build/deploy metadata if available
    meta_dir = kit_root / "node" / "apps" / "admin" / "data" / "meta"
    last_build: str | None = None
    last_deploy: str | None = None

    build_meta = meta_dir / f"{tenant_id}.build.json"
    if build_meta.exists():
        try:
            build_data = json.loads(build_meta.read_text(encoding="utf-8"))
            last_build = build_data.get("timestamp")
        except (json.JSONDecodeError, OSError):
            pass

    deploy_meta = meta_dir / f"{tenant_id}.deploy.json"
    if deploy_meta.exists():
        try:
            deploy_data = json.loads(deploy_meta.read_text(encoding="utf-8"))
            last_deploy = deploy_data.get("timestamp")
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "tenant_id": tenant_id,
        "user_count": user_count,
        "last_build": last_build,
        "last_deploy": last_deploy,
    }
