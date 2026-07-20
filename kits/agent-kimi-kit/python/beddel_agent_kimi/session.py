"""Kimi Session lifecycle helpers.

Provides session creation, configuration mapping, and cleanup utilities
for the KimiAgentAdapter.
"""

from __future__ import annotations

import os
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_TIER_MAP: dict[str, str] = {
    "fast": "kimi-k2.6",
    "balanced": "kimi-k2.7-code-highspeed",
    "code": "kimi-k2.7-code",
    "powerful": "kimi-k3",
}

SANDBOX_MAP: dict[str, str] = {
    "read-only": "read_only",
    "workspace-write": "workspace",
    "danger-full-access": "unrestricted",
}

DEFAULT_TIMEOUT: int = 300


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def resolve_model(tier: str | None) -> str:
    """Map a Beddel model tier to a Kimi model identifier.

    Args:
        tier: Beddel tier string or None (defaults to 'balanced').

    Returns:
        Kimi model identifier string.

    Raises:
        ValueError: If the tier is not recognized.
    """
    if tier is None:
        return MODEL_TIER_MAP["balanced"]
    if tier in MODEL_TIER_MAP:
        return MODEL_TIER_MAP[tier]
    # Check if it's already a raw kimi model name (passthrough)
    if tier.startswith("kimi-"):
        return tier
    raise ValueError(
        f"Unknown model tier: {tier!r}. "
        f"Valid tiers: {list(MODEL_TIER_MAP.keys())}"
    )


def resolve_sandbox(sandbox: str) -> str:
    """Map a Beddel sandbox level to a Kimi KAOS mode string.

    Args:
        sandbox: Beddel sandbox level.

    Returns:
        KAOS mode string for kimi-agent-sdk.

    Raises:
        ValueError: If the sandbox level is not recognized.
    """
    if sandbox not in SANDBOX_MAP:
        raise ValueError(
            f"Unsupported sandbox: {sandbox!r}. "
            f"Valid: {list(SANDBOX_MAP.keys())}"
        )
    return SANDBOX_MAP[sandbox]


def get_api_key() -> str:
    """Read MOONSHOT_API_KEY from environment.

    Returns:
        The API key string.

    Raises:
        ValueError: If the key is not set or empty.
    """
    key = os.environ.get("MOONSHOT_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "MOONSHOT_API_KEY environment variable is not set or empty. "
            "Set it to your Moonshot platform API key."
        )
    return key
