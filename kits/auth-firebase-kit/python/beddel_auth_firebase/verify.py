"""Firebase Auth ID token + App Check attestation verification.

Thin wrappers over the Firebase Admin SDK:

- :func:`verify_id_token` wraps ``firebase_admin.auth.verify_id_token``.
- :func:`verify_app_check` wraps ``firebase_admin.app_check.verify_token``.

The Firebase Admin app is initialized lazily (and only once) using Application
Default Credentials. ``project_id`` is never hard-coded — it is resolved from an
explicit argument, the ``GOOGLE_CLOUD_PROJECT`` environment variable, or the
default initialized app.
"""

from __future__ import annotations

import os
from typing import Any

import firebase_admin  # type: ignore[import-untyped]
from firebase_admin import app_check, auth  # type: ignore[import-untyped]

from beddel_auth_firebase._types import AppCheckClaims, DecodedToken

__all__ = ["resolve_project_id", "verify_app_check", "verify_id_token"]


def resolve_project_id(project_id: str | None = None) -> str | None:
    """Resolve the Firebase/GCP project id.

    Resolution order:

    1. The explicit *project_id* argument.
    2. The ``GOOGLE_CLOUD_PROJECT`` environment variable.
    3. ``None`` — letting the Firebase Admin default app / ADC decide.

    Args:
        project_id: Explicit project id, or ``None`` to fall back to the
            environment.

    Returns:
        The resolved project id, or ``None`` when it cannot be determined
        without the default app.
    """
    return project_id or os.environ.get("GOOGLE_CLOUD_PROJECT") or None


def _ensure_app(project_id: str | None = None) -> firebase_admin.App:
    """Return the default Firebase Admin app, initializing it if needed.

    Initialization is idempotent: if a default app already exists it is reused.
    Credentials come from Application Default Credentials (ADC); only the
    project id is passed through when known.

    Args:
        project_id: Optional project id to attach to a newly initialized app.

    Returns:
        The default :class:`firebase_admin.App` instance.
    """
    try:
        return firebase_admin.get_app()
    except ValueError:
        resolved = resolve_project_id(project_id)
        options = {"projectId": resolved} if resolved else None
        return firebase_admin.initialize_app(options=options)


def verify_id_token(token: str, project_id: str | None = None) -> DecodedToken:
    """Verify a Firebase Auth ID token (JWT).

    Uses ``firebase_admin.auth.verify_id_token`` under the hood and initializes
    the Firebase Admin SDK if it has not been initialized yet.

    Args:
        token: The Firebase Auth ID token (JWT) to verify.
        project_id: Optional project id override. Defaults to the
            ``GOOGLE_CLOUD_PROJECT`` environment variable.

    Returns:
        A :class:`DecodedToken` with the verified claims.

    Raises:
        ValueError: If *token* is empty.
        firebase_admin.auth.InvalidIdTokenError: If the token is malformed or
            its signature is invalid.
        firebase_admin.auth.ExpiredIdTokenError: If the token has expired.
    """
    if not token:
        raise ValueError("ID token must not be empty")

    app = _ensure_app(project_id)
    claims: dict[str, Any] = auth.verify_id_token(token, app=app)

    firebase_info = claims.get("firebase", {}) or {}
    return DecodedToken(
        uid=claims.get("uid") or claims.get("sub", ""),
        email=claims.get("email"),
        email_verified=bool(claims.get("email_verified", False)),
        name=claims.get("name"),
        picture=claims.get("picture"),
        provider_id=firebase_info.get("sign_in_provider"),
        iss=claims.get("iss", ""),
        aud=claims.get("aud", ""),
        exp=int(claims.get("exp", 0) or 0),
        iat=int(claims.get("iat", 0) or 0),
    )


def verify_app_check(token: str, project_id: str | None = None) -> AppCheckClaims:
    """Verify a Firebase App Check attestation token.

    Uses ``firebase_admin.app_check.verify_token`` under the hood and
    initializes the Firebase Admin SDK if it has not been initialized yet.

    Args:
        token: The App Check attestation token to verify.
        project_id: Optional project id override. Defaults to the
            ``GOOGLE_CLOUD_PROJECT`` environment variable.

    Returns:
        An :class:`AppCheckClaims` with the verified attestation claims.

    Raises:
        ValueError: If *token* is empty or verification fails (the Firebase
            Admin SDK raises ``ValueError`` on invalid App Check tokens).
    """
    if not token:
        raise ValueError("App Check token must not be empty")

    app = _ensure_app(project_id)
    claims: dict[str, Any] = app_check.verify_token(token, app=app)

    return AppCheckClaims(
        sub=claims.get("sub", ""),
        app_id=claims.get("app_id") or claims.get("sub", ""),
        iss=claims.get("iss", ""),
        exp=int(claims.get("exp", 0) or 0),
    )
