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
        Kimi model identifier string. Unknown values are passed through
        as-is so the downstream SDK or provider can reject them with its
        own error.
    """
    if tier is None:
        return MODEL_TIER_MAP["balanced"]
    if tier in MODEL_TIER_MAP:
        return MODEL_TIER_MAP[tier]
    # Check if a recognised well-known kimi-* model name
    if tier.startswith("kimi-"):
        return tier
    # Pass through anything else (e.g. "provider/model" or unknown)
    return tier


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

    The provider configuration is resolved from the local Kimi CLI config
    (``kimi_cli.config.load_config()``) by matching the resolved *model*
    against the configured ``LLMModel.model`` fields. If no match is found
    the builder falls back to the Moonshot provider.

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

    # ------------------------------------------------------------------
    # 1) Try to match the resolved model to a provider via kimi_cli.config
    # ------------------------------------------------------------------
    provider_name: str | None = None
    provider_base_url: str | None = None
    provider_type: str = "kimi"

    try:
        from kimi_cli.config import load_config

        config = load_config()
        for key, m in (config.models or {}).items():
            if m.model == model:
                # key format: "provider/model"
                provider_name = key.split("/", 1)[0]
                if provider_name in (config.providers or {}):
                    p = config.providers[provider_name]
                    provider_base_url = str(p.base_url) if p.base_url else None
                    provider_type = p.type.value if hasattr(p.type, "value") else str(p.type)
                break
    except Exception:
        pass  # Fall through to Moonshot default

    # ------------------------------------------------------------------
    # 2) Fallback: Moonshot provider
    # ------------------------------------------------------------------
    if provider_name is None or provider_base_url is None:
        provider_name = "moonshot"
        provider_base_url = "https://api.moonshot.cn/v1"
        provider_type = "kimi"

    provider_dict = {
        "type": provider_type,
        "base_url": provider_base_url,
        "api_key": api_key,
    }

    return Config(
        default_model=model,
        providers={provider_name: provider_dict},
        models={
            model: {
                "provider": provider_name,
                "model": model,
                "max_context_size": max_context_size,
            }
        },
    )
