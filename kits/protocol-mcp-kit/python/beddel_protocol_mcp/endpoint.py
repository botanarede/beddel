"""Endpoint validation and canonical form for remote MCP servers.

An ``mcp_servers`` entry carries only non-secret connection data.  The core
validates the *shape* of the endpoint; this module is where the kit enforces the
transport-security rules the core deliberately leaves to it:

* HTTPS only.  Plain ``http`` is accepted solely for a loopback host and only
  when the caller opts in explicitly (the kit's own tests do; a workflow cannot).
* No userinfo, no query string and no fragment.  A credential must never travel
  in the URL, and the strictest rule (refuse any query) is used on purpose: a
  deny-list of "credential-looking" parameter names is bypassed by renaming one.

Every error raised here is a fixed message that never interpolates the offending
value, so a credential pasted into an endpoint cannot be echoed back.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from beddel.domain.errors import MCPError
from beddel.error_codes import MCP_CONNECTION_FAILED

__all__ = ["canonical_endpoint", "is_loopback_host"]

_MAX_ENDPOINT_LENGTH = 2048
_DEFAULT_PORTS = {"https": 443, "http": 80}


def _refuse(reason: str) -> MCPError:
    """Build the single error shape used for every refused endpoint."""
    return MCPError(
        code=MCP_CONNECTION_FAILED,
        message=f"MCP endpoint refused before connecting: {reason}.",
    )


def is_loopback_host(host: str) -> bool:
    """Return whether *host* names the loopback interface (no DNS lookup)."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def canonical_endpoint(endpoint: str, *, allow_insecure_loopback: bool = False) -> str:
    """Validate *endpoint* and return its canonical URL.

    The canonical form lower-cases the scheme and host, drops a default port
    and renders an empty path as ``/``.  It is the value credentials are bound
    to, so two spellings of one endpoint share one credential and two different
    endpoints never do.

    Args:
        endpoint: The URL a workflow declared for the server.
        allow_insecure_loopback: Accept ``http`` for a loopback host.  Off by
            default; used by the kit's tests against a local fake server.

    Returns:
        The canonical endpoint URL.

    Raises:
        MCPError: ``BEDDEL-MCP-600`` for any refused endpoint.  The message
            never contains the endpoint text.
    """
    if not isinstance(endpoint, str) or not endpoint:
        raise _refuse("endpoint must be a non-empty string")
    if len(endpoint) > _MAX_ENDPOINT_LENGTH:
        raise _refuse("endpoint is too long")
    if not endpoint.isascii() or not endpoint.isprintable() or " " in endpoint or "\\" in endpoint:
        raise _refuse("endpoint must be an ASCII URL without whitespace or backslashes")
    if "?" in endpoint or "#" in endpoint:
        raise _refuse("endpoint must not carry a query string or a fragment")
    # The refusal is raised after the except block so the ValueError (whose text
    # can quote part of the URL) is not chained to it.
    malformed = False
    port: int | None = None
    try:
        parts = urlsplit(endpoint)
        port = parts.port  # raises ValueError for a malformed or out-of-range port
    except ValueError:
        malformed = True
    if malformed:
        raise _refuse("endpoint is not a well-formed absolute URL")
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if not scheme or not host:
        raise _refuse("endpoint must be an absolute URL with a scheme and a host")
    if "@" in parts.netloc:
        raise _refuse("endpoint must not carry userinfo")
    if (
        scheme == "https"
        or scheme == "http"
        and allow_insecure_loopback
        and is_loopback_host(host)
    ):
        pass
    else:
        raise _refuse("endpoint must use https")

    rendered_host = f"[{host}]" if ":" in host else host
    netloc = rendered_host
    if port is not None and port != _DEFAULT_PORTS[scheme]:
        netloc = f"{rendered_host}:{port}"
    return f"{scheme}://{netloc}{parts.path or '/'}"
