"""Kit-local error type and codes for bonar-cms-kit.

This is a self-contained Solution Kit — its error codes are NOT registered
in the core SDK's centralized error code registry
(``beddel.error_codes``). ``CMSError`` extends :class:`BeddelError` directly
and carries kit-local string codes.
"""

from __future__ import annotations

from typing import Any

from beddel.domain.errors import BeddelError

__all__ = [
    "CMS_BUILD_FAILED",
    "CMS_GENERATION_FAILED",
    "CMS_INVALID_TENANT_ID",
    "CMS_NODE_NOT_FOUND",
    "CMS_SUBPROCESS_TIMEOUT",
    "CMS_TENANT_EXISTS",
    "CMS_TENANT_NOT_FOUND",
    "CMS_VALIDATION_ERROR",
    "CMSError",
]

CMS_BUILD_FAILED = "CMS_BUILD_FAILED"
"""Raised when Next.js static export build fails."""

CMS_TENANT_NOT_FOUND = "CMS_TENANT_NOT_FOUND"
"""Raised when a tenant_id has no corresponding config file."""

CMS_TENANT_EXISTS = "CMS_TENANT_EXISTS"
"""Raised when attempting to create a tenant that already exists."""

CMS_INVALID_TENANT_ID = "CMS_INVALID_TENANT_ID"
"""Raised when a tenant_id fails kebab-case validation."""

CMS_GENERATION_FAILED = "CMS_GENERATION_FAILED"
"""Raised when LLM generation fails after retry."""

CMS_VALIDATION_ERROR = "CMS_VALIDATION_ERROR"
"""Raised when schema validation script fails or returns unexpected output."""

CMS_SUBPROCESS_TIMEOUT = "CMS_SUBPROCESS_TIMEOUT"
"""Raised when a Node.js subprocess exceeds the configured timeout."""

CMS_NODE_NOT_FOUND = "CMS_NODE_NOT_FOUND"
"""Raised when Node.js is not available on PATH."""


class CMSError(BeddelError):
    """Base error for bonar-cms-kit tools.

    Attributes:
        code: Kit-local error code (e.g. ``CMS_TENANT_NOT_FOUND``).
        message: Human-readable description.
        details: Optional dict with machine-consumable context.
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, details)
