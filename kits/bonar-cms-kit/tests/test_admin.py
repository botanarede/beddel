"""Tests for admin tools — list_users, create_user, update_user_role, get_tenant_stats.

All tests use tmp_path; no subprocess or external calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from beddel_bonar_cms._errors import CMS_ADMIN_ERROR, CMSError
from beddel_bonar_cms.tools.admin import (
    create_user,
    get_tenant_stats,
    list_users,
    update_user_role,
)


@pytest.fixture()
def kit_root(tmp_path: Path) -> Path:
    """Create a temporary kit root with admin data dirs and tenants dir."""
    users_dir = tmp_path / "node" / "apps" / "admin" / "data" / "users"
    users_dir.mkdir(parents=True)
    tenants_dir = tmp_path / "node" / "tenants"
    tenants_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture(autouse=True)
def _patch_kit_root(kit_root: Path) -> None:  # noqa: PT004
    """Patch get_kit_root to return the tmp kit root for all tests."""
    with patch("beddel_bonar_cms.tools.admin.get_kit_root", return_value=kit_root):
        yield


class TestListUsers:
    """Tests for list_users."""

    def test_empty_dir(self) -> None:
        result = list_users()
        assert result == {"users": []}

    def test_with_users(self, kit_root: Path) -> None:
        users_dir = kit_root / "node" / "apps" / "admin" / "data" / "users"
        user1 = {
            "id": "aaa-111",
            "email": "alice@example.com",
            "role": "admin",
            "created_at": "2026-07-11T10:00:00+00:00",
        }
        user2 = {
            "id": "bbb-222",
            "email": "bob@example.com",
            "role": "viewer",
            "created_at": "2026-07-11T11:00:00+00:00",
        }
        (users_dir / "aaa-111.json").write_text(json.dumps(user1))
        (users_dir / "bbb-222.json").write_text(json.dumps(user2))

        result = list_users()
        assert len(result["users"]) == 2
        assert result["users"][0]["id"] == "aaa-111"
        assert result["users"][1]["id"] == "bbb-222"

    def test_skips_malformed_json(self, kit_root: Path) -> None:
        users_dir = kit_root / "node" / "apps" / "admin" / "data" / "users"
        (users_dir / "bad.json").write_text("not json")
        user1 = {
            "id": "good-user",
            "email": "good@example.com",
            "role": "editor",
            "created_at": "2026-07-11T10:00:00+00:00",
        }
        (users_dir / "good-user.json").write_text(json.dumps(user1))

        result = list_users()
        assert len(result["users"]) == 1
        assert result["users"][0]["id"] == "good-user"


class TestCreateUser:
    """Tests for create_user."""

    def test_success(self) -> None:
        result = create_user(email="test@example.com", role="editor")
        assert result["success"] is True
        assert result["email"] == "test@example.com"
        assert result["role"] == "editor"
        assert "user_id" in result

    def test_duplicate_email_raises(self, kit_root: Path) -> None:
        users_dir = kit_root / "node" / "apps" / "admin" / "data" / "users"
        existing = {
            "id": "existing-id",
            "email": "dup@example.com",
            "role": "viewer",
            "created_at": "2026-07-11T10:00:00+00:00",
        }
        (users_dir / "existing-id.json").write_text(json.dumps(existing))

        with pytest.raises(CMSError) as exc_info:
            create_user(email="dup@example.com", role="admin")
        assert exc_info.value.code == CMS_ADMIN_ERROR

    def test_duplicate_email_case_insensitive(self, kit_root: Path) -> None:
        users_dir = kit_root / "node" / "apps" / "admin" / "data" / "users"
        existing = {
            "id": "existing-id",
            "email": "User@Example.COM",
            "role": "viewer",
            "created_at": "2026-07-11T10:00:00+00:00",
        }
        (users_dir / "existing-id.json").write_text(json.dumps(existing))

        with pytest.raises(CMSError) as exc_info:
            create_user(email="user@example.com", role="admin")
        assert exc_info.value.code == CMS_ADMIN_ERROR

    def test_invalid_role_raises(self) -> None:
        with pytest.raises(CMSError) as exc_info:
            create_user(email="test@example.com", role="superuser")
        assert exc_info.value.code == CMS_ADMIN_ERROR

    def test_creates_json_file(self, kit_root: Path) -> None:
        result = create_user(email="file@example.com", role="viewer")
        user_id = result["user_id"]
        users_dir = kit_root / "node" / "apps" / "admin" / "data" / "users"
        path = users_dir / f"{user_id}.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["email"] == "file@example.com"
        assert data["role"] == "viewer"


class TestUpdateUserRole:
    """Tests for update_user_role."""

    def test_success(self, kit_root: Path) -> None:
        users_dir = kit_root / "node" / "apps" / "admin" / "data" / "users"
        user = {
            "id": "uid-123",
            "email": "user@example.com",
            "role": "viewer",
            "created_at": "2026-07-11T10:00:00+00:00",
        }
        (users_dir / "uid-123.json").write_text(json.dumps(user))

        result = update_user_role(user_id="uid-123", role="admin")
        assert result["role"] == "admin"
        assert result["id"] == "uid-123"

        # Verify persisted
        saved = json.loads((users_dir / "uid-123.json").read_text())
        assert saved["role"] == "admin"

    def test_user_not_found_raises(self) -> None:
        with pytest.raises(CMSError) as exc_info:
            update_user_role(user_id="nonexistent", role="editor")
        assert exc_info.value.code == CMS_ADMIN_ERROR

    def test_invalid_role_raises(self, kit_root: Path) -> None:
        users_dir = kit_root / "node" / "apps" / "admin" / "data" / "users"
        user = {
            "id": "uid-456",
            "email": "user@example.com",
            "role": "viewer",
            "created_at": "2026-07-11T10:00:00+00:00",
        }
        (users_dir / "uid-456.json").write_text(json.dumps(user))

        with pytest.raises(CMSError) as exc_info:
            update_user_role(user_id="uid-456", role="superadmin")
        assert exc_info.value.code == CMS_ADMIN_ERROR


class TestGetTenantStats:
    """Tests for get_tenant_stats."""

    def test_success_no_meta(self, kit_root: Path) -> None:
        # Create tenant config
        tenants_dir = kit_root / "node" / "tenants"
        tenant_config = {"site": {"name": "Test Site"}}
        (tenants_dir / "my-tenant.json").write_text(json.dumps(tenant_config))

        result = get_tenant_stats(tenant_id="my-tenant")
        assert result["tenant_id"] == "my-tenant"
        assert result["user_count"] == 0
        assert result["last_build"] is None
        assert result["last_deploy"] is None

    def test_with_users_and_meta(self, kit_root: Path) -> None:
        # Create tenant
        tenants_dir = kit_root / "node" / "tenants"
        (tenants_dir / "acme.json").write_text(json.dumps({"site": {"name": "Acme"}}))

        # Create users assigned to this tenant
        users_dir = kit_root / "node" / "apps" / "admin" / "data" / "users"
        user1 = {"id": "u1", "email": "a@a.com", "role": "admin", "tenant_id": "acme"}
        user2 = {"id": "u2", "email": "b@b.com", "role": "viewer", "tenant_id": "acme"}
        user3 = {"id": "u3", "email": "c@c.com", "role": "editor", "tenant_id": "other"}
        (users_dir / "u1.json").write_text(json.dumps(user1))
        (users_dir / "u2.json").write_text(json.dumps(user2))
        (users_dir / "u3.json").write_text(json.dumps(user3))

        # Create build/deploy meta
        meta_dir = kit_root / "node" / "apps" / "admin" / "data" / "meta"
        meta_dir.mkdir(parents=True)
        (meta_dir / "acme.build.json").write_text(
            json.dumps({"timestamp": "2026-07-11T12:00:00Z"})
        )
        (meta_dir / "acme.deploy.json").write_text(
            json.dumps({"timestamp": "2026-07-11T13:00:00Z"})
        )

        result = get_tenant_stats(tenant_id="acme")
        assert result["tenant_id"] == "acme"
        assert result["user_count"] == 2
        assert result["last_build"] == "2026-07-11T12:00:00Z"
        assert result["last_deploy"] == "2026-07-11T13:00:00Z"

    def test_tenant_not_found_raises(self) -> None:
        with pytest.raises(CMSError) as exc_info:
            get_tenant_stats(tenant_id="nonexistent")
        assert exc_info.value.code == CMS_ADMIN_ERROR
