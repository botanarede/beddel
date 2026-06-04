"""Tests for the FastAPI ``firebase_auth_dependency``.

A small FastAPI app mounts the dependency on a protected route and is driven via
``TestClient``. The verification + tenant-resolution functions are patched at
the ``beddel_auth_firebase.middleware`` import site, so no Firebase/Firestore
calls happen.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from beddel_auth_firebase import middleware
from beddel_auth_firebase._types import AuthContext, DecodedToken, TenantMembership


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """A TestClient for an app guarded by ``firebase_auth_dependency``."""
    app = FastAPI()
    # Pre-seed a dummy Firestore client so the dependency never creates a real
    # one (resolve_tenant is patched, so the value is never used).
    app.state.firestore_db = MagicMock()

    @app.get("/protected")
    async def protected(
        ctx: AuthContext = Depends(middleware.firebase_auth_dependency),
    ) -> dict[str, Any]:
        return ctx.model_dump()

    with TestClient(app) as test_client:
        yield test_client


def _decoded(uid: str = "user-1", email: str | None = "a@b.com") -> DecodedToken:
    return DecodedToken(uid=uid, email=email)


def _membership(
    tenant_id: str = "acme", role: str = "owner", uid: str = "user-1"
) -> TenantMembership:
    return TenantMembership(tenant_id=tenant_id, uid=uid, role=role, email="a@b.com")


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_happy_path_without_app_check(client: TestClient) -> None:
    with (
        patch.object(middleware, "verify_id_token", return_value=_decoded()),
        patch.object(
            middleware, "resolve_tenant", new=AsyncMock(return_value=_membership())
        ),
    ):
        resp = client.get(
            "/protected",
            headers={"Authorization": "Bearer good-token", "X-Tenant-Id": "acme"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["uid"] == "user-1"
    assert body["tenant_id"] == "acme"
    assert body["role"] == "owner"
    assert body["app_check_verified"] is False


def test_happy_path_with_valid_app_check(client: TestClient) -> None:
    with (
        patch.object(middleware, "verify_id_token", return_value=_decoded()),
        patch.object(middleware, "verify_app_check", return_value=MagicMock()),
        patch.object(
            middleware, "resolve_tenant", new=AsyncMock(return_value=_membership())
        ),
    ):
        resp = client.get(
            "/protected",
            headers={
                "Authorization": "Bearer good-token",
                "X-Firebase-AppCheck": "app-check-token",
                "X-Tenant-Id": "acme",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["app_check_verified"] is True


def test_happy_path_discovery_without_tenant_header(client: TestClient) -> None:
    resolve = AsyncMock(return_value=_membership(tenant_id="discovered"))
    with (
        patch.object(middleware, "verify_id_token", return_value=_decoded()),
        patch.object(middleware, "resolve_tenant", new=resolve),
    ):
        resp = client.get("/protected", headers={"Authorization": "Bearer good-token"})

    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "discovered"
    # tenant_id passed to resolver must be None (discovery mode).
    assert resolve.await_args is not None
    assert resolve.await_args.args[2] is None


# ---------------------------------------------------------------------------
# 401 — authentication failures
# ---------------------------------------------------------------------------


def test_missing_authorization_header_returns_401(client: TestClient) -> None:
    resp = client.get("/protected")
    assert resp.status_code == 401
    assert "Authorization" in resp.json()["detail"]


def test_malformed_authorization_header_returns_401(client: TestClient) -> None:
    resp = client.get("/protected", headers={"Authorization": "Basic xyz"})
    assert resp.status_code == 401


def test_empty_bearer_token_returns_401(client: TestClient) -> None:
    resp = client.get("/protected", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Empty bearer token"


def test_invalid_id_token_returns_401(client: TestClient) -> None:
    with patch.object(
        middleware, "verify_id_token", side_effect=ValueError("bad token")
    ):
        resp = client.get("/protected", headers={"Authorization": "Bearer bad-token"})

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid Firebase ID token"


def test_invalid_app_check_token_returns_401(client: TestClient) -> None:
    with (
        patch.object(middleware, "verify_id_token", return_value=_decoded()),
        patch.object(
            middleware, "verify_app_check", side_effect=ValueError("bad app check")
        ),
    ):
        resp = client.get(
            "/protected",
            headers={
                "Authorization": "Bearer good-token",
                "X-Firebase-AppCheck": "bad-app-check",
            },
        )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid Firebase App Check token"


# ---------------------------------------------------------------------------
# 403 — tenant authorization failures
# ---------------------------------------------------------------------------


def test_no_tenant_membership_returns_403(client: TestClient) -> None:
    with (
        patch.object(middleware, "verify_id_token", return_value=_decoded()),
        patch.object(
            middleware,
            "resolve_tenant",
            new=AsyncMock(side_effect=PermissionError("not a member of tenant 'x'")),
        ),
    ):
        resp = client.get(
            "/protected",
            headers={"Authorization": "Bearer good-token", "X-Tenant-Id": "x"},
        )

    assert resp.status_code == 403
    assert "not a member" in resp.json()["detail"]


def test_no_tenant_found_returns_403(client: TestClient) -> None:
    with (
        patch.object(middleware, "verify_id_token", return_value=_decoded()),
        patch.object(
            middleware,
            "resolve_tenant",
            new=AsyncMock(side_effect=LookupError("No tenant membership found")),
        ),
    ):
        resp = client.get("/protected", headers={"Authorization": "Bearer good-token"})

    assert resp.status_code == 403
    assert "No tenant membership" in resp.json()["detail"]
