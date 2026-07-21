"""Kimi Session lifecycle helpers.

Provides session configuration mapping and utility functions
for the KimiAgentAdapter and KimiSwarmStrategy.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kimi_agent_sdk import Config


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
DEFAULT_MAX_CONTEXT_SIZE: int = 100_000


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
        f"Unknown model tier: {tier!r}. Valid tiers: {list(MODEL_TIER_MAP.keys())}"
    )


def resolve_sandbox(sandbox: str) -> str:
    """Map a Beddel sandbox level to a Kimi KAOS mode string.

    .. deprecated:: 0.0.5
        The returned KAOS mode string is no longer passed to
        ``Session.create()`` since ``kimi-agent-sdk>=0.0.5`` removed
        the ``sandbox_mode`` parameter. This function is retained for
        input validation (ensuring sandbox level is recognized) and
        backward compatibility.

    Args:
        sandbox: Beddel sandbox level.

    Returns:
        KAOS mode string for kimi-agent-sdk.

    Raises:
        ValueError: If the sandbox level is not recognized.
    """
    if sandbox not in SANDBOX_MAP:
        raise ValueError(
            f"Unsupported sandbox: {sandbox!r}. Valid: {list(SANDBOX_MAP.keys())}"
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


def build_kimi_config(
    api_key: str, model: str, *, max_context_size: int = DEFAULT_MAX_CONTEXT_SIZE
) -> "Config":
    """Build a validated kimi-agent-sdk Config object.

    Centralises the provider/model config structure so adapter and swarm
    share the same wiring without duplication.

    Args:
        api_key: Moonshot platform API key.
        model: Resolved Kimi model identifier.
        max_context_size: Maximum context window size in tokens. Must be > 0.

    Returns:
        A validated ``Config`` instance ready for session creation.

    Raises:
        ValueError: If *max_context_size* is not positive.
    """
    from kimi_agent_sdk import Config

    if max_context_size <= 0:
        raise ValueError(f"max_context_size must be > 0, got {max_context_size}")

    return Config(
        default_model=model,
        providers={
            "kimi": {
                "type": "kimi",
                "base_url": "https://api.moonshot.ai/v1",
                "api_key": api_key,
            }
        },
        models={
            model: {
                "provider": "kimi",
                "model": model,
                "max_context_size": max_context_size,
            }
        },
    )
