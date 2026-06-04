"""Firestore tenant membership resolution.

Resolves a user's tenant membership and role from Firestore documents shaped as::

    tenants/{tenantId}/members/{uid} = {
        "role": "owner" | "editor" | "viewer",
        "email": "user@example.com",
        "addedAt": <Timestamp>,
    }

All reads use the async Firestore client
(:class:`google.cloud.firestore_v1.AsyncClient`).
"""

from __future__ import annotations

from typing import Any

from google.cloud.firestore_v1 import AsyncClient

from beddel_auth_firebase._types import TenantMembership

__all__ = ["resolve_tenant"]

_MEMBERS_COLLECTION = "members"
_TENANTS_COLLECTION = "tenants"


def _membership_from_snapshot(
    *,
    tenant_id: str,
    uid: str,
    data: dict[str, Any],
) -> TenantMembership:
    """Build a :class:`TenantMembership` from a Firestore document dict."""
    return TenantMembership(
        tenant_id=tenant_id,
        uid=uid,
        role=str(data.get("role", "")),
        email=str(data.get("email", "")),
    )


async def resolve_tenant(
    uid: str,
    db: AsyncClient,
    tenant_id: str | None = None,
) -> TenantMembership:
    """Resolve a user's tenant membership from Firestore.

    Two modes:

    * **Scoped** — when *tenant_id* is provided, the membership document
      ``tenants/{tenant_id}/members/{uid}`` is read directly. If it does not
      exist, the user has no access to that tenant.
    * **Discovery** — when *tenant_id* is ``None``, a Firestore *collection
      group* query over ``members`` is streamed and the first document whose id
      matches *uid* is returned, with the tenant id derived from the document's
      parent path.

    Args:
        uid: The Firebase user id to look up.
        db: An async Firestore client.
        tenant_id: Optional tenant to scope the lookup to. When ``None``, the
            first tenant the user belongs to is returned.

    Returns:
        The resolved :class:`TenantMembership`.

    Raises:
        ValueError: If *uid* is empty.
        PermissionError: If *tenant_id* is given but the user is not a member.
        LookupError: If *tenant_id* is ``None`` and the user belongs to no
            tenant.

    Note:
        Discovery mode streams the ``members`` collection group and filters by
        document id client-side. For large catalogs prefer passing an explicit
        *tenant_id* (typically from the ``X-Tenant-Id`` header).
    """
    if not uid:
        raise ValueError("uid must not be empty")

    if tenant_id is not None:
        doc_ref = (
            db.collection(_TENANTS_COLLECTION)
            .document(tenant_id)
            .collection(_MEMBERS_COLLECTION)
            .document(uid)
        )
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            raise PermissionError(
                f"User {uid!r} is not a member of tenant {tenant_id!r}"
            )
        return _membership_from_snapshot(
            tenant_id=tenant_id,
            uid=uid,
            data=snapshot.to_dict() or {},
        )

    # Discovery mode: scan the members collection group for this uid.
    query = db.collection_group(_MEMBERS_COLLECTION)
    async for snapshot in query.stream():
        if snapshot.id != uid:
            continue
        resolved_tenant_id = _tenant_id_from_snapshot(snapshot)
        if resolved_tenant_id is None:
            continue
        return _membership_from_snapshot(
            tenant_id=resolved_tenant_id,
            uid=uid,
            data=snapshot.to_dict() or {},
        )

    raise LookupError(f"No tenant membership found for user {uid!r}")


def _tenant_id_from_snapshot(snapshot: Any) -> str | None:
    """Derive the tenant id from a ``members`` document snapshot.

    The document path is ``tenants/{tenant_id}/members/{uid}`` so the tenant id
    is the id of the grandparent document.

    Args:
        snapshot: A Firestore document snapshot from the ``members`` collection
            group.

    Returns:
        The tenant id, or ``None`` when the parent path cannot be resolved.
    """
    reference = getattr(snapshot, "reference", None)
    members_collection = getattr(reference, "parent", None)
    tenant_document = getattr(members_collection, "parent", None)
    tenant_id = getattr(tenant_document, "id", None)
    return tenant_id if isinstance(tenant_id, str) else None
