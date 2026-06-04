"""Tests for Firestore tenant membership resolution.

The async Firestore client is mocked end-to-end: ``AsyncMock`` for the awaited
``document.get()`` call and an async generator for the collection-group
``stream()`` used in discovery mode.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from beddel_auth_firebase._types import TenantMembership
from beddel_auth_firebase.tenant import resolve_tenant


def _scoped_db(*, exists: bool, data: dict[str, Any] | None = None) -> MagicMock:
    """Build a mock Firestore client for the scoped (tenant_id given) path."""
    snapshot = MagicMock()
    snapshot.exists = exists
    snapshot.to_dict.return_value = data or {}

    doc_ref = MagicMock()
    doc_ref.get = AsyncMock(return_value=snapshot)

    db = MagicMock()
    (
        db.collection.return_value.document.return_value.collection.return_value.document.return_value
    ) = doc_ref
    return db


def _member_snapshot(uid: str, tenant_id: str, data: dict[str, Any]) -> MagicMock:
    """Build a member document snapshot whose parent path yields *tenant_id*."""
    snapshot = MagicMock()
    snapshot.id = uid
    snapshot.to_dict.return_value = data
    # reference.parent (members collection).parent (tenant document).id
    snapshot.reference.parent.parent.id = tenant_id
    return snapshot


def _discovery_db(snapshots: list[MagicMock]) -> MagicMock:
    """Build a mock Firestore client for the discovery (tenant_id=None) path."""

    async def _stream() -> Any:
        for snap in snapshots:
            yield snap

    db = MagicMock()
    db.collection_group.return_value.stream.return_value = _stream()
    return db


# ---------------------------------------------------------------------------
# Scoped resolution (tenant_id provided)
# ---------------------------------------------------------------------------


async def test_resolve_tenant_scoped_happy_path() -> None:
    db = _scoped_db(exists=True, data={"role": "owner", "email": "a@b.com"})

    membership = await resolve_tenant("user-1", db, tenant_id="acme")

    assert isinstance(membership, TenantMembership)
    assert membership.tenant_id == "acme"
    assert membership.uid == "user-1"
    assert membership.role == "owner"
    assert membership.email == "a@b.com"


async def test_resolve_tenant_scoped_no_membership_raises_permission_error() -> None:
    db = _scoped_db(exists=False)

    with pytest.raises(PermissionError, match="not a member of tenant 'acme'"):
        await resolve_tenant("user-1", db, tenant_id="acme")


async def test_resolve_tenant_scoped_missing_fields_default_empty() -> None:
    db = _scoped_db(exists=True, data={})

    membership = await resolve_tenant("user-1", db, tenant_id="acme")

    assert membership.role == ""
    assert membership.email == ""


# ---------------------------------------------------------------------------
# Discovery resolution (tenant_id is None)
# ---------------------------------------------------------------------------


async def test_resolve_tenant_discovery_happy_path() -> None:
    snap = _member_snapshot("user-1", "acme", {"role": "editor", "email": "x@y.com"})
    db = _discovery_db([snap])

    membership = await resolve_tenant("user-1", db)

    assert membership.tenant_id == "acme"
    assert membership.role == "editor"


async def test_resolve_tenant_discovery_skips_non_matching_uid() -> None:
    other = _member_snapshot("other-user", "other", {"role": "viewer"})
    mine = _member_snapshot("user-1", "acme", {"role": "owner", "email": "a@b"})
    db = _discovery_db([other, mine])

    membership = await resolve_tenant("user-1", db)

    assert membership.tenant_id == "acme"
    assert membership.role == "owner"


async def test_resolve_tenant_discovery_no_membership_raises_lookup_error() -> None:
    db = _discovery_db([])

    with pytest.raises(LookupError, match="No tenant membership"):
        await resolve_tenant("user-1", db)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def test_resolve_tenant_empty_uid_raises_value_error() -> None:
    db = MagicMock()

    with pytest.raises(ValueError, match="uid must not be empty"):
        await resolve_tenant("", db, tenant_id="acme")
