"""A2A Agent Card discovery.

Fetches and parses the ``.well-known/agent.json`` Agent Card from a
remote A2A-compliant agent endpoint.
"""

from __future__ import annotations

from typing import Any

from beddel.domain.errors import AgentError

try:
    import httpx
except ImportError as exc:
    raise ImportError(
        "httpx is required for agent-a2a-kit. Install with: pip install httpx"
    ) from exc

# Re-use error code from adapter module
A2A_DISCOVERY_FAILED: str = "BEDDEL-AGENT-721"

__all__ = ["discover_agent"]


async def discover_agent(
    url: str,
    auth_token: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Fetch the A2A Agent Card from a remote agent.

    Sends a GET request to ``{url}/.well-known/agent.json`` and returns
    the parsed JSON as a dict containing the agent's metadata, skills,
    capabilities, and authentication requirements.

    Args:
        url: Base URL of the A2A agent (trailing slash stripped).
        auth_token: Optional Bearer token for authenticated endpoints.
        timeout: Request timeout in seconds.

    Returns:
        Parsed Agent Card dict with keys like ``name``, ``description``,
        ``skills``, ``capabilities``, ``url``, ``version``.

    Raises:
        AgentError: ``BEDDEL-AGENT-721`` on HTTP errors, connection
            failures, or invalid JSON responses.
    """
    base_url = url.rstrip("/")
    card_url = f"{base_url}/.well-known/agent.json"

    headers: dict[str, str] = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                card_url,
                headers=headers,
                timeout=timeout,
            )
    except httpx.HTTPError as exc:
        raise AgentError(
            code=A2A_DISCOVERY_FAILED,
            message=f"Failed to fetch Agent Card from {card_url}",
            details={"error": str(exc), "url": card_url},
        ) from exc

    if response.status_code >= 400:
        raise AgentError(
            code=A2A_DISCOVERY_FAILED,
            message=f"Agent Card HTTP error {response.status_code}",
            details={
                "status_code": response.status_code,
                "body": response.text[:500],
                "url": card_url,
            },
        )

    try:
        return response.json()  # type: ignore[no-any-return]
    except Exception as exc:
        raise AgentError(
            code=A2A_DISCOVERY_FAILED,
            message="Invalid JSON in Agent Card response",
            details={"url": card_url, "body": response.text[:500]},
        ) from exc
