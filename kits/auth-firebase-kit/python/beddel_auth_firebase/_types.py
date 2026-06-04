"""Pydantic models for the auth-firebase-kit.

These models describe the verified outputs of Firebase Auth ID token
verification, App Check attestation, and Firestore tenant resolution. They are
deliberately decoupled from the Beddel domain core — this kit only depends on
``firebase-admin``, ``google-cloud-firestore``, ``pydantic`` and (optionally)
``fastapi``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = [
    "AppCheckClaims",
    "AuthContext",
    "DecodedToken",
    "TenantMembership",
]


class DecodedToken(BaseModel):
    """Decoded claims from a verified Firebase Auth ID token.

    Mirrors the subset of the Firebase ID token payload that backends commonly
    need. Unknown claims are ignored.

    Attributes:
        uid: Firebase user id (the token ``sub`` / ``uid`` claim).
        email: User email, when present and shared by the provider.
        email_verified: Whether the email has been verified.
        name: Display name, when available.
        picture: Profile picture URL, when available.
        provider_id: Sign-in provider id (e.g. ``google.com``, ``password``).
        iss: Token issuer.
        aud: Token audience (the Firebase project id).
        exp: Expiration time (Unix seconds).
        iat: Issued-at time (Unix seconds).
    """

    uid: str
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    picture: str | None = None
    provider_id: str | None = None
    iss: str = ""
    aud: str = ""
    exp: int = 0
    iat: int = 0


class AppCheckClaims(BaseModel):
    """Decoded claims from a verified Firebase App Check attestation token.

    Attributes:
        sub: Subject — the Firebase project number.
        app_id: The application id the attestation was issued for.
        iss: Token issuer.
        exp: Expiration time (Unix seconds).
    """

    sub: str
    app_id: str
    iss: str = ""
    exp: int = 0


class TenantMembership(BaseModel):
    """A user's membership record within a tenant.

    Resolved from the Firestore document ``tenants/{tenant_id}/members/{uid}``.

    Attributes:
        tenant_id: The tenant the membership belongs to.
        uid: The Firebase user id of the member.
        role: Membership role — one of ``owner``, ``editor`` or ``viewer``.
        email: The member's email as recorded in Firestore.
    """

    tenant_id: str
    uid: str
    role: str
    email: str = ""


class AuthContext(BaseModel):
    """Fully resolved authentication context for a request.

    Produced by :func:`beddel_auth_firebase.middleware.firebase_auth_dependency`
    after verifying the ID token, optionally verifying App Check, and resolving
    tenant membership.

    Attributes:
        uid: Verified Firebase user id.
        email: User email, when present.
        tenant_id: The tenant the request is scoped to.
        role: The user's role within ``tenant_id``.
        app_check_verified: Whether a valid App Check token was presented.
    """

    uid: str
    email: str | None = None
    tenant_id: str
    role: str
    app_check_verified: bool = Field(default=False)
