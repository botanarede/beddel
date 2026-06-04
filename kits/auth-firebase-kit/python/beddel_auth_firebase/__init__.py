"""Beddel auth-firebase-kit — Firebase Auth + App Check + tenant resolution.

Public API:

- :class:`DecodedToken`, :class:`AppCheckClaims`, :class:`TenantMembership`,
  :class:`AuthContext` — Pydantic result models.
- :func:`verify_id_token` — verify a Firebase Auth ID token.
- :func:`verify_app_check` — verify a Firebase App Check attestation token.
- :func:`resolve_tenant` — resolve tenant membership from Firestore (async).
- :func:`firebase_auth_dependency` — FastAPI dependency wiring it all together.

Heavier symbols (``verify_*``, ``resolve_tenant``, ``firebase_auth_dependency``)
are lazy-loaded via :pep:`562` ``__getattr__`` so that importing the package
does not eagerly import ``firebase_admin`` / ``fastapi`` until they are used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from beddel_auth_firebase._types import (
    AppCheckClaims,
    AuthContext,
    DecodedToken,
    TenantMembership,
)

if TYPE_CHECKING:
    from beddel_auth_firebase.middleware import firebase_auth_dependency
    from beddel_auth_firebase.tenant import resolve_tenant
    from beddel_auth_firebase.verify import verify_app_check, verify_id_token

__all__ = [
    "AppCheckClaims",
    "AuthContext",
    "DecodedToken",
    "TenantMembership",
    "firebase_auth_dependency",
    "resolve_tenant",
    "verify_app_check",
    "verify_id_token",
]


def __getattr__(name: str) -> object:
    """Lazy-load callable symbols to defer heavy third-party imports."""
    if name in ("verify_id_token", "verify_app_check"):
        from beddel_auth_firebase import verify

        return getattr(verify, name)
    if name == "resolve_tenant":
        from beddel_auth_firebase.tenant import resolve_tenant

        return resolve_tenant
    if name == "firebase_auth_dependency":
        from beddel_auth_firebase.middleware import firebase_auth_dependency

        return firebase_auth_dependency
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
