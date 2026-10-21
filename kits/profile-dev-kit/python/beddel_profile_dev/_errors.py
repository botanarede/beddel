"""Kit-local error type and codes for profile-dev-kit.

Codes are NOT registered in the core error registry; ``ProfileError`` extends
:class:`BeddelError` directly, like ``CMSError`` in solution-cms-kit.
"""

from __future__ import annotations

from typing import Any

from beddel.domain.errors import BeddelError

__all__ = [
    "PROFILE_CHANGE_CONFLICT",
    "PROFILE_CHANGE_INVALID",
    "PROFILE_CONFIG_INVALID",
    "PROFILE_DETERMINATION_REFUSED",
    "PROFILE_GATE_COMMAND_INVALID",
    "PROFILE_GATE_UNSCOPED",
    "PROFILE_IMPACT_CONFLICT",
    "PROFILE_IMPACT_UNBOUND",
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

PROFILE_CHANGE_INVALID = "PROFILE_CHANGE_INVALID"
"""Raised when a Change id is invalid or its base is not an ancestor of the revision."""

PROFILE_CHANGE_CONFLICT = "PROFILE_CHANGE_CONFLICT"
"""Raised when a recorded Change has another base or a stored link differs."""

PROFILE_IMPACT_UNBOUND = "PROFILE_IMPACT_UNBOUND"
"""Raised when the Change, its revision link or the revision binding is missing or inconsistent."""

PROFILE_IMPACT_CONFLICT = "PROFILE_IMPACT_CONFLICT"
"""Raised when a stored impact record differs from the re-derived one."""

PROFILE_DETERMINATION_REFUSED = "PROFILE_DETERMINATION_REFUSED"
"""Raised when a determination of non-applicability cannot be recorded (nothing is written)."""

PROFILE_GATE_COMMAND_INVALID = "PROFILE_GATE_COMMAND_INVALID"
"""Raised when a configured Gate command names an executable outside the allowlist."""

PROFILE_GATE_UNSCOPED = "PROFILE_GATE_UNSCOPED"
"""Raised when the Gate cannot be scoped: the impact record is absent or inconsistent
with the step inputs, or the work tree is not the Analyzed revision."""


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
