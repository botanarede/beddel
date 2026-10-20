"""Kit-local error type and codes for profile-dev-kit.

Codes are NOT registered in the core error registry; ``ProfileError`` extends
:class:`BeddelError` directly, like ``CMSError`` in solution-cms-kit.
"""

from __future__ import annotations

from typing import Any

from beddel.domain.errors import BeddelError

__all__ = [
    "PROFILE_CONFIG_INVALID",
    "PROFILE_PREFLIGHT_FAILED",
    "ProfileError",
]

PROFILE_CONFIG_INVALID = "PROFILE_CONFIG_INVALID"
"""Raised when the kit-internal config is missing or malformed."""

PROFILE_PREFLIGHT_FAILED = "PROFILE_PREFLIGHT_FAILED"
"""Raised when one or more preflight checks fail."""


class ProfileError(BeddelError):
    """Base error for profile-dev-kit tools.

    Attributes:
        code: Kit-local error code.
        message: Fixed, secret-free description.
        details: Optional machine-consumable context (identifiers only).
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, details)
