"""A2A Agent Card discovery using a2a-sdk.

Fetches and parses the Agent Card from a remote A2A-compliant agent
endpoint using the official :class:`~a2a.client.A2ACardResolver`.

Primary path: ``/.well-known/agent-card.json`` (current A2A spec).
Fallback path: ``/.well-known/agent.json`` (legacy compatibility).
"""

from __future__ import annotations

from typing import Any

import httpx
from a2a.client import A2ACardResolver
from a2a.client.errors import AgentCardResolutionError
from a2a.types import AgentCard

from beddel.domain.errors import AgentError

# Re-use error code from adapter module
A2A_DISCOVERY_FAILED: str = "BEDDEL-AGENT-721"

__all__ = ["discover_agent"]

# A2A spec primary path
_PRIMARY_CARD_PATH = "/.well-known/agent-card.json"
# Legacy fallback path
_LEGACY_CARD_PATH = "/.well-known/agent.json"


async def discover_agent(
    url: str,
    auth_token: str | None = None,
    timeout: float = 30.0,
) -> AgentCard:
    """Fetch the A2A Agent Card from a remote agent.

    Uses the a2a-sdk :class:`A2ACardResolver` to fetch and parse the
    Agent Card.  Tries the primary path first
    (``/.well-known/agent-card.json``), then falls back to the legacy
    path (``/.well-known/agent.json``) for backward compatibility.

    Args:
        url: Base URL of the A2A agent (trailing slash stripped).
        auth_token: Optional Bearer token for authenticated endpoints.
        timeout: Request timeout in seconds.

    Returns:
        Typed :class:`AgentCard` proto object with the agent's metadata,
        skills, capabilities, and authentication requirements.

    Raises:
        AgentError: ``BEDDEL-AGENT-721`` on HTTP errors, connection
            failures, or invalid Agent Card responses.
    """
    base_url = url.rstrip("/")

    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    http_kwargs: dict[str, Any] = {}
    if headers:
        http_kwargs["headers"] = headers

    async with httpx.AsyncClient(timeout=timeout) as httpx_client:
        # Try primary path first (current A2A spec)
        resolver = A2ACardResolver(
            httpx_client=httpx_client,
            base_url=base_url,
            agent_card_path=_PRIMARY_CARD_PATH.lstrip("/"),
        )

        try:
            return await resolver.get_agent_card(http_kwargs=http_kwargs)
        except AgentCardResolutionError:
            # Fall back to legacy path
            pass

        # Try legacy path
        resolver_legacy = A2ACardResolver(
            httpx_client=httpx_client,
            base_url=base_url,
            agent_card_path=_LEGACY_CARD_PATH.lstrip("/"),
        )

        try:
            return await resolver_legacy.get_agent_card(http_kwargs=http_kwargs)
        except AgentCardResolutionError as exc:
            raise AgentError(
                code=A2A_DISCOVERY_FAILED,
                message=f"Failed to fetch Agent Card from {base_url}",
                details={
                    "error": str(exc),
                    "url": base_url,
                    "primary_path": _PRIMARY_CARD_PATH,
                    "fallback_path": _LEGACY_CARD_PATH,
                },
            ) from exc
        except httpx.HTTPError as exc:
            raise AgentError(
                code=A2A_DISCOVERY_FAILED,
                message=f"Failed to fetch Agent Card from {base_url}",
                details={"error": str(exc), "url": base_url},
            ) from exc
