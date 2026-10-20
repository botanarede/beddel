"""Kit-local error type and codes for profile-dev-kit.

Codes are NOT registered in the core error registry; ``ProfileError`` extends
:class:`BeddelError` directly, like ``CMSError`` in solution-cms-kit.
"""

from __future__ import annotations

from typing import Any

from beddel.domain.errors import BeddelError

__all__ = [
    "PROFILE_CONFIG_INVALID",
    "PROFILE_INVENTORY_BINDING_CONFLICT",
    "PROFILE_INVENTORY_INTEGRITY_BLOCK",
    "PROFILE_INVENTORY_UNRATIFIED",
    "PROFILE_PREFLIGHT_FAILED",
    "PROFILE_RATIFICATION_REFUSED",
    "PROFILE_REPOSITORY_INVALID",
    "ProfileError",
]

PROFILE_CONFIG_INVALID = "PROFILE_CONFIG_INVALID"
"""Raised when the kit-internal config is missing or malformed."""

PROFILE_PREFLIGHT_FAILED = "PROFILE_PREFLIGHT_FAILED"
"""Raised when one or more preflight checks fail."""

PROFILE_RATIFICATION_REFUSED = "PROFILE_RATIFICATION_REFUSED"
"""Raised when an inventory version cannot be ratified (nothing is written)."""

PROFILE_INVENTORY_UNRATIFIED = "PROFILE_INVENTORY_UNRATIFIED"
"""Raised when no ratified inventory version exists at the Analyzed revision."""

PROFILE_INVENTORY_INTEGRITY_BLOCK = "PROFILE_INVENTORY_INTEGRITY_BLOCK"
"""Raised when a ratified version cannot form or resolve its identities."""

PROFILE_INVENTORY_BINDING_CONFLICT = "PROFILE_INVENTORY_BINDING_CONFLICT"
"""Raised when a revision is already bound to another version or snapshot."""

PROFILE_REPOSITORY_INVALID = "PROFILE_REPOSITORY_INVALID"
"""Raised when the repository path or revision cannot be used."""


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
