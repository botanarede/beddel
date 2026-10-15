"""Operator authorization for remote MCP servers (not a ``beddel`` command).

Run it **outside any workflow run**, once per endpoint, from a terminal the
operator controls::

    python -m beddel_protocol_mcp.authorize --endpoint https://mcp.example.com/mcp

It performs the OAuth authorization-code flow with the official SDK's
``OAuthClientProvider``: it prints the authorization URL (and tries to open it in
the operator's browser unless ``--no-browser``), receives the redirect on a
callback server bound **explicitly to 127.0.0.1**, and stores the resulting
credentials with owner-only permissions in the kit's credential directory (see
:mod:`beddel_protocol_mcp.credentials`), bound to the canonical endpoint and the
``oauth`` method.  It prints no token, code or secret value.

A workflow run never does any of this: it only reads what was stored here.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
import webbrowser
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qs, urlsplit

from beddel.domain.errors import MCPError
from beddel.error_codes import MCP_AUTHORIZATION_REQUIRED, MCP_CONNECTION_FAILED
from beddel_protocol_mcp.endpoint import canonical_endpoint
from beddel_protocol_mcp.http_client import ADAPTER_NAME, AUTHORIZATION_OAUTH, _leaves

try:
    import httpx2
    from mcp import Client
    from mcp.client.auth import AuthorizationCodeResult, OAuthClientProvider
    from mcp.client.streamable_http import streamable_http_client
    from mcp.shared.auth import OAuthClientMetadata
    from pydantic import AnyUrl

    from beddel_protocol_mcp.credentials import (
        CredentialStore,
        CredentialStoreError,
        FileTokenStorage,
    )

    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

__all__ = ["authorize", "main"]

LOOPBACK_HOST = "127.0.0.1"
CALLBACK_PATH = "/callback"
_CLIENT_NAME = "Beddel MCP protocol kit"
_MAX_REQUEST_BYTES = 16 * 1024
_REQUEST_TIMEOUT = 10.0

_PAGE = (
    "<!doctype html><title>Beddel MCP authorization</title>"
    "<p>Authorization received. You can close this window.</p>"
)


class _CallbackServer:
    """One-shot HTTP receiver for the OAuth redirect, bound to 127.0.0.1 only."""

    def __init__(self, port: int) -> None:
        self._requested_port = port
        self._server: asyncio.Server | None = None
        self._result: asyncio.Future[dict[str, str]] = asyncio.get_running_loop().create_future()

    async def start(self) -> int:
        """Bind and return the port actually bound."""
        self._server = await asyncio.start_server(
            self._handle, host=LOOPBACK_HOST, port=self._requested_port
        )
        sockets = self._server.sockets
        return int(sockets[0].getsockname()[1])

    @property
    def sockname_hosts(self) -> list[str]:
        """Hosts the listening sockets are bound to (for verification)."""
        return [str(s.getsockname()[0]) for s in (self._server.sockets if self._server else [])]

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        status = "404 Not Found"
        body = b""
        try:
            raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=_REQUEST_TIMEOUT)
            if len(raw) <= _MAX_REQUEST_BYTES:
                request_line = raw.split(b"\r\n", 1)[0].decode("ascii", "replace")
                parts = request_line.split(" ")
                if len(parts) == 3 and parts[0] == "GET":
                    target = urlsplit(parts[1])
                    if target.path == CALLBACK_PATH:
                        params = {k: v[0] for k, v in parse_qs(target.query).items()}
                        if ("code" in params or "error" in params) and not self._result.done():
                            self._result.set_result(params)
                        status, body = "200 OK", _PAGE.encode()
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, TimeoutError, OSError):
            status = "400 Bad Request"
        finally:
            with contextlib.suppress(OSError):
                writer.write(
                    f"HTTP/1.1 {status}\r\nContent-Type: text/html\r\n"
                    f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
                await writer.drain()
                writer.close()
                await writer.wait_closed()

    async def wait(self, timeout: float) -> dict[str, str]:
        """Wait for the redirect; raises ``TimeoutError`` after *timeout* seconds."""
        return await asyncio.wait_for(asyncio.shield(self._result), timeout=timeout)

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()


class _FlowDenied(Exception):  # noqa: N818 - internal signal
    """The operator or the authorization server ended the flow."""


def _failure(message: str) -> MCPError:
    return MCPError(code=MCP_AUTHORIZATION_REQUIRED, message=message)


async def authorize(
    endpoint: str,
    *,
    authorization: str = AUTHORIZATION_OAUTH,
    store: CredentialStore | None = None,
    open_url: Callable[[str], Awaitable[None]] | None = None,
    port: int = 0,
    timeout: float = 300.0,
    client_metadata_url: str | None = None,
    allow_insecure_loopback: bool = False,
    httpx_transport: Any = None,
    echo: Callable[[str], None] = print,
) -> None:
    """Run the OAuth flow for *endpoint* and store the credentials.

    Args:
        endpoint: The server's MCP endpoint (HTTPS; same rules as a workflow).
        authorization: Authorization method; only ``oauth`` has a flow to run.
        store: Credential store; defaults to the kit's.
        open_url: Awaitable that sends the operator to the authorization URL.
            Defaults to printing it and opening the system browser.
        port: Callback port on 127.0.0.1; ``0`` picks a free one.
        timeout: Seconds to wait for the operator to finish in the browser.
        client_metadata_url: Optional HTTPS Client ID Metadata Document URL the
            SDK uses as ``client_id`` when the authorization server supports it.
        allow_insecure_loopback: Accept an ``http`` loopback endpoint (tests).
        httpx_transport: Replace the HTTP transport (tests).
        echo: Where progress lines go; they never contain a token.

    Raises:
        MCPError: ``BEDDEL-MCP-600`` for an unusable endpoint or method,
            ``BEDDEL-MCP-605`` when the flow does not complete.
    """
    if not _MCP_AVAILABLE:
        raise MCPError(
            code=MCP_CONNECTION_FAILED,
            message="MCP SDK not installed. Install the kit dependencies (see its README).",
        )
    if authorization != AUTHORIZATION_OAUTH:
        raise MCPError(
            code=MCP_CONNECTION_FAILED,
            message=f"Only the '{AUTHORIZATION_OAUTH}' method has an authorization flow to run.",
        )
    canonical = canonical_endpoint(endpoint, allow_insecure_loopback=allow_insecure_loopback)
    credentials = store or CredentialStore()
    server = _CallbackServer(port)
    bound_port = await server.start()
    redirect_uri = f"http://{LOOPBACK_HOST}:{bound_port}{CALLBACK_PATH}"
    failure: list[str] = []

    async def redirect(url: str) -> None:
        echo(f"Authorize the Beddel MCP client for {canonical} by opening:\n  {url}")
        if open_url is not None:
            await open_url(url)
        else:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(webbrowser.open, url)

    async def callback() -> AuthorizationCodeResult:
        try:
            params = await server.wait(timeout)
        except TimeoutError:
            failure.append("timed out waiting for the browser redirect")
            raise
        if "error" in params or "code" not in params:
            failure.append("the authorization server denied the request")
            raise _FlowDenied
        return AuthorizationCodeResult(
            code=params["code"], state=params.get("state"), iss=params.get("iss")
        )

    storage = FileTokenStorage(credentials, canonical, authorization)
    provider = OAuthClientProvider(
        server_url=canonical,
        client_metadata=OAuthClientMetadata(
            client_name=_CLIENT_NAME,
            redirect_uris=[AnyUrl(redirect_uri)],
            token_endpoint_auth_method="none",
        ),
        storage=storage,
        redirect_handler=redirect,
        callback_handler=callback,
        client_metadata_url=client_metadata_url,
    )
    existing = None
    with contextlib.suppress(Exception):
        existing = credentials.read(canonical, authorization)
    if existing is not None and existing.tokens is not None:
        provider.context.token_expiry_time = existing.expires_at

    kwargs: dict[str, Any] = {}
    if httpx_transport is not None:
        kwargs["transport"] = httpx_transport
    failed_reason: str | None = None
    try:
        async with (
            httpx2.AsyncClient(
                auth=provider, timeout=httpx2.Timeout(30.0, read=60.0), **kwargs
            ) as http,
            asyncio.timeout(timeout + 30.0),
            Client(streamable_http_client(canonical, http_client=http)) as client,
        ):
            await client.list_tools()
    except Exception as exc:
        stored_reasons = [
            leaf.reason for leaf in _leaves(exc) if isinstance(leaf, CredentialStoreError)
        ]
        reason = (
            failure[0]
            if failure
            else stored_reasons[0]
            if stored_reasons
            else f"authorization did not complete ({type(exc).__name__})"
        )
        failed_reason = reason
    finally:
        await server.close()
    if failed_reason is not None:
        # Raised outside the except block: the SDK exception (which can quote a
        # state mismatch or token-exchange text) is not chained to it.
        raise _failure(f"Authorization for {canonical} failed: {failed_reason}.")

    stored = credentials.read(canonical, authorization)
    if stored is None or stored.tokens is None:
        raise _failure(f"Authorization for {canonical} completed without storing credentials.")
    discovered = provider.context.oauth_metadata
    if discovered is not None:
        # Keep the discovered authorization-server metadata so a later run can
        # refresh against the real token endpoint (see StoredCredentials).
        stored.oauth_metadata = discovered.model_dump(mode="json", exclude_none=True)
        stored.auth_server_url = provider.context.auth_server_url
        credentials.write(canonical, authorization, stored)
    echo(f"Authorization stored for {canonical} (method '{authorization}').")


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(
        prog="python -m beddel_protocol_mcp.authorize",
        description="Authorize the Beddel MCP client for a remote server (operator act, "
        "never run inside a workflow).",
    )
    parser.add_argument("--endpoint", required=True, help="the server's MCP endpoint (HTTPS)")
    parser.add_argument(
        "--authorization",
        default=AUTHORIZATION_OAUTH,
        help=f"authorization method (default {AUTHORIZATION_OAUTH!r}); "
        f"transport adapter: {ADAPTER_NAME}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="callback port on 127.0.0.1 (default: a free port; set it when the "
        "authorization server only accepts the registered redirect URI)",
    )
    parser.add_argument(
        "--timeout", type=float, default=300.0, help="seconds to wait for the browser redirect"
    )
    parser.add_argument(
        "--client-metadata-url",
        default=None,
        help="HTTPS Client ID Metadata Document URL to use as client_id when supported",
    )
    parser.add_argument(
        "--credentials-dir",
        default=None,
        help="credential directory (default: $BEDDEL_MCP_CREDENTIALS_DIR or "
        "~/.beddel/mcp-credentials)",
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="print the URL only; do not open a browser"
    )
    args = parser.parse_args(argv)

    async def no_browser(_url: str) -> None:
        return None

    try:
        asyncio.run(
            authorize(
                args.endpoint,
                authorization=args.authorization,
                store=CredentialStore(args.credentials_dir),
                open_url=no_browser if args.no_browser else None,
                port=args.port,
                timeout=args.timeout,
                client_metadata_url=args.client_metadata_url,
            )
        )
    except MCPError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
