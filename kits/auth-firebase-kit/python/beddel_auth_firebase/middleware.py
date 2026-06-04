"""FastAPI dependency for Firebase Auth + App Check + tenant scoping.

:func:`firebase_auth_dependency` is meant to be used with ``fastapi.Depends``.
It extracts the relevant headers from the incoming request, verifies the
Firebase Auth ID token (and optionally an App Check token), resolves the
caller's tenant membership, and returns a fully populated
:class:`~beddel_auth_firebase._types.AuthContext`.

Header contract:

==============================  ========  ==================================
Header                          Required  Purpose
==============================  ========  ==================================
``Authorization: Bearer <t>``   yes       Firebase Auth ID token
``X-Firebase-AppCheck: <t>``    no        App Check attestation token
``X-Tenant-Id: <id>``           no        Target tenant (multi-tenant routing)
==============================  ========  ==================================

The async Firestore client is read from ``request.app.state.firestore_db`` when
present; otherwise a client is created lazily (using the resolved project id)
and cached back onto ``app.state`` for reuse.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from google.cloud.firestore_v1 import AsyncClient

from beddel_auth_firebase._types import AuthContext
from beddel_auth_firebase.tenant import resolve_tenant
from beddel_auth_firebase.verify import (
    resolve_project_id,
    verify_app_check,
    verify_id_token,
)

__all__ = ["firebase_auth_dependency"]

_BEARER_PREFIX = "Bearer "
_APP_CHECK_HEADER = "X-Firebase-AppCheck"
_TENANT_HEADER = "X-Tenant-Id"
_FIRESTORE_STATE_ATTR = "firestore_db"


def _get_firestore_db(request: Request) -> AsyncClient:
    """Return the async Firestore client for *request*.

    Prefers ``request.app.state.firestore_db`` when set; otherwise creates a new
    :class:`AsyncClient` (using the resolved project id) and caches it on
    ``app.state`` so subsequent requests reuse the same client.
    """
    state = request.app.state
    db = getattr(state, _FIRESTORE_STATE_ATTR, None)
    if db is None:
        db = AsyncClient(project=resolve_project_id())
        setattr(state, _FIRESTORE_STATE_ATTR, db)
    return db


def _extract_bearer_token(request: Request) -> str:
    """Extract the bearer token from the ``Authorization`` header.

    Raises:
        HTTPException: ``401`` when the header is missing or malformed.
    """
    header = request.headers.get("Authorization", "")
    if not header.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = header[len(_BEARER_PREFIX) :].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


async def firebase_auth_dependency(request: Request) -> AuthContext:
    """Validate a request's Firebase identity and resolve its tenant.

    Intended for use as a FastAPI dependency::

        from fastapi import Depends
        from beddel_auth_firebase import AuthContext, firebase_auth_dependency

        @app.get("/workflows")
        async def handler(ctx: AuthContext = Depends(firebase_auth_dependency)):
            ...

    Args:
        request: The incoming FastAPI/Starlette request.

    Returns:
        A populated :class:`AuthContext`.

    Raises:
        HTTPException: ``401`` if the ID token (or App Check token) is missing
            or invalid; ``403`` if the user has no access to the requested
            tenant.
    """
    id_token = _extract_bearer_token(request)

    try:
        decoded = verify_id_token(id_token)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — surfaced as a 401 to the client
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase ID token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    app_check_verified = False
    app_check_token = request.headers.get(_APP_CHECK_HEADER)
    if app_check_token:
        try:
            verify_app_check(app_check_token)
        except Exception as exc:  # noqa: BLE001 — surfaced as a 401 to the client
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Firebase App Check token",
            ) from exc
        app_check_verified = True

    tenant_id = request.headers.get(_TENANT_HEADER)
    db = _get_firestore_db(request)
    try:
        membership = await resolve_tenant(decoded.uid, db, tenant_id)
    except (PermissionError, LookupError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return AuthContext(
        uid=decoded.uid,
        email=decoded.email,
        tenant_id=membership.tenant_id,
        role=membership.role,
        app_check_verified=app_check_verified,
    )
