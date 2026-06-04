"""Tests for Firebase Auth ID token + App Check verification.

The Firebase Admin SDK is never contacted: ``_ensure_app`` is patched to a
sentinel and the underlying ``firebase_admin.auth.verify_id_token`` /
``firebase_admin.app_check.verify_token`` calls are mocked.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from firebase_admin import app_check, auth  # type: ignore[import-untyped]

from beddel_auth_firebase import verify
from beddel_auth_firebase._types import AppCheckClaims, DecodedToken

_VALID_ID_CLAIMS: dict[str, Any] = {
    "uid": "user-123",
    "email": "alice@example.com",
    "email_verified": True,
    "name": "Alice",
    "picture": "https://example.com/a.png",
    "iss": "https://securetoken.google.com/beddel-test",
    "aud": "beddel-test",
    "exp": 2000000000,
    "iat": 1999999000,
    "firebase": {"sign_in_provider": "google.com"},
}

_VALID_APP_CHECK_CLAIMS: dict[str, Any] = {
    "sub": "1234567890",
    "app_id": "1:1234567890:web:abcdef",
    "iss": "https://firebaseappcheck.googleapis.com/1234567890",
    "exp": 2000000000,
}


@pytest.fixture()
def _sentinel_app() -> Any:
    """Patch ``_ensure_app`` so no real Firebase app is initialized."""
    with patch.object(verify, "_ensure_app", return_value=object()):
        yield


# ---------------------------------------------------------------------------
# verify_id_token
# ---------------------------------------------------------------------------


def test_verify_id_token_happy_path(_sentinel_app: Any) -> None:
    with patch.object(auth, "verify_id_token", return_value=_VALID_ID_CLAIMS):
        decoded = verify.verify_id_token("an-id-token")

    assert isinstance(decoded, DecodedToken)
    assert decoded.uid == "user-123"
    assert decoded.email == "alice@example.com"
    assert decoded.email_verified is True
    assert decoded.name == "Alice"
    assert decoded.provider_id == "google.com"
    assert decoded.aud == "beddel-test"
    assert decoded.exp == 2000000000


def test_verify_id_token_uses_sub_when_uid_absent(_sentinel_app: Any) -> None:
    claims = {"sub": "sub-only-uid", "email": "bob@example.com"}
    with patch.object(auth, "verify_id_token", return_value=claims):
        decoded = verify.verify_id_token("an-id-token")

    assert decoded.uid == "sub-only-uid"
    assert decoded.provider_id is None


def test_verify_id_token_empty_raises_value_error() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        verify.verify_id_token("")


def test_verify_id_token_invalid_propagates(_sentinel_app: Any) -> None:
    with patch.object(
        auth,
        "verify_id_token",
        side_effect=auth.InvalidIdTokenError("malformed token"),
    ):
        with pytest.raises(auth.InvalidIdTokenError):
            verify.verify_id_token("bad-token")


def test_verify_id_token_expired_propagates(_sentinel_app: Any) -> None:
    with patch.object(
        auth,
        "verify_id_token",
        side_effect=auth.ExpiredIdTokenError("expired", cause=None),
    ):
        with pytest.raises(auth.ExpiredIdTokenError):
            verify.verify_id_token("expired-token")


def test_verify_id_token_passes_app_to_sdk(_sentinel_app: Any) -> None:
    with patch.object(
        auth, "verify_id_token", return_value=_VALID_ID_CLAIMS
    ) as mock_verify:
        verify.verify_id_token("an-id-token")

    # The wrapper must forward the initialized app to the SDK.
    assert mock_verify.call_count == 1
    _, kwargs = mock_verify.call_args
    assert "app" in kwargs


# ---------------------------------------------------------------------------
# verify_app_check
# ---------------------------------------------------------------------------


def test_verify_app_check_happy_path(_sentinel_app: Any) -> None:
    with patch.object(app_check, "verify_token", return_value=_VALID_APP_CHECK_CLAIMS):
        claims = verify.verify_app_check("an-app-check-token")

    assert isinstance(claims, AppCheckClaims)
    assert claims.sub == "1234567890"
    assert claims.app_id == "1:1234567890:web:abcdef"
    assert claims.exp == 2000000000


def test_verify_app_check_empty_raises_value_error() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        verify.verify_app_check("")


def test_verify_app_check_invalid_propagates(_sentinel_app: Any) -> None:
    with patch.object(
        app_check, "verify_token", side_effect=ValueError("invalid app check token")
    ):
        with pytest.raises(ValueError, match="invalid app check token"):
            verify.verify_app_check("bad-token")


# ---------------------------------------------------------------------------
# resolve_project_id
# ---------------------------------------------------------------------------


def test_resolve_project_id_prefers_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "from-env")
    assert verify.resolve_project_id("explicit") == "explicit"


def test_resolve_project_id_falls_back_to_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "from-env")
    assert verify.resolve_project_id() == "from-env"


def test_resolve_project_id_none_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    assert verify.resolve_project_id() is None
