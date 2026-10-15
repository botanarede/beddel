"""Remote MCP client over Streamable HTTP, with OAuth through the official SDK.

This adapter implements the structural ``IMCPClient`` port for a remote MCP
server declared by an ``mcp_servers`` entry (``transport``, ``endpoint``,
``authorization``).  Transports, OAuth and token storage live here, in the kit,
and never in the core (AD-21).

Contract (the one the composition root and the fake adapter of the integration
stories follow):

* **Constructor from the entry's fields, no I/O.**  ``StreamableHTTPMCPClient(
  transport=..., endpoint=..., authorization=...)`` validates its arguments and
  nothing else: no socket, no file, no directory, no SDK object.  An unknown
  authorization method, a transport name that is not this adapter's, or a
  refused endpoint raises a Beddel ``MCPError`` here.
* **Connection on first call.**  The first ``list_tools`` or ``call_tool``
  connects.  The core never calls ``connect``; calling it is accepted only for
  the same endpoint.
* **Safe disconnect.**  ``disconnect`` works whether or not a connection was
  made, and after a cancelled call.

Authorization methods (resolved by this kit; the core enumerates none):

* ``none`` -- the server needs no authentication.  The method is explicit, never
  a default.  It never bypasses authentication a server requires: if the server
  answers 401 or 403, the call fails with ``MCP_AUTHORIZATION_REQUIRED``; no
  login is started and nothing is retried with other credentials.
* ``oauth`` -- OAuth through the SDK's ``OAuthClientProvider``, with credentials
  the operator stored beforehand (``python -m beddel_protocol_mcp.authorize``).
  A workflow run never opens a browser, prompts or registers a client: missing,
  expired-and-not-refreshable or revoked credentials fail the call with
  ``MCP_AUTHORIZATION_REQUIRED`` and a message naming the operator action.

Failure semantics: only connection establishment is retried (bounded); a tool
call is never retried.  Timeouts raise ``MCP_SERVER_TIMEOUT``, connection
failures ``MCP_CONNECTION_FAILED``, a server ``isError`` result
``MCP_TOOL_INVOCATION_FAILED``.  No message carries SDK or transport text, a
token, or a secret: errors are built from fixed sentences, the endpoint (which
carries no userinfo or query) and the exception class name.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar
from urllib.parse import parse_qs, urlsplit

import anyio

from beddel.domain.errors import MCPError
from beddel.error_codes import (
    MCP_AUTHORIZATION_REQUIRED,
    MCP_CONNECTION_FAILED,
    MCP_SERVER_TIMEOUT,
    MCP_TOOL_INVOCATION_FAILED,
)
from beddel_protocol_mcp.endpoint import canonical_endpoint

try:
    import httpx2
    from mcp import Client
    from mcp import MCPError as SDKMCPError
    from mcp.client.auth import AuthorizationCodeResult, OAuthClientProvider, OAuthFlowError
    from mcp.client.streamable_http import streamable_http_client
    from mcp.shared.auth import OAuthClientMetadata, OAuthMetadata
    from mcp_types import REQUEST_TIMEOUT
    from pydantic import AnyUrl

    from beddel_protocol_mcp.credentials import (
        CredentialStore,
        CredentialStoreError,
        FileTokenStorage,
    )

    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

__all__ = [
    "ADAPTER_NAME",
    "AUTHORIZATION_METHODS",
    "AUTHORIZATION_NONE",
    "AUTHORIZATION_OAUTH",
    "MCP_SPECIFICATION_REVISION",
    "StreamableHTTPMCPClient",
]

_LOG = logging.getLogger(__name__)

#: Registration key of this adapter: the value a workflow writes as ``transport``.
ADAPTER_NAME = "mcp-streamable-http"
AUTHORIZATION_NONE = "none"
AUTHORIZATION_OAUTH = "oauth"
#: Authorization method names this kit resolves.
AUTHORIZATION_METHODS = (AUTHORIZATION_NONE, AUTHORIZATION_OAUTH)
#: MCP specification revision whose transport and authorization the kit implements.
MCP_SPECIFICATION_REVISION = "2026-07-28"

OPERATOR_COMMAND = "python -m beddel_protocol_mcp.authorize"
_CLIENT_NAME = "Beddel MCP protocol kit"
_MAX_LIST_PAGES = 100
_CLOSE_TIMEOUT = 5.0
_MAX_BACKOFF = 4.0
_AUTH_CHALLENGE_STATUSES = frozenset({401, 403})

_T = TypeVar("_T")


class _AuthorizationNeeded(Exception):  # noqa: N818 - internal signal, not a public error
    """Raised inside SDK callbacks to abort a request that needs authorization.

    Carries no text on purpose: the public error is built from fixed sentences.
    """


@dataclass
class _ConnectionState:
    """What one connection attempt observed; classification reads it."""

    challenged: bool = False
    #: A ``grant_type=refresh_token`` request was sent during this attempt.  The
    #: refresh token may have been consumed (rotation), so the attempt is never
    #: repeated.
    refresh_sent: bool = False

    def demand(self) -> _AuthorizationNeeded:
        """Record that authorization is required and return the signal to raise."""
        self.challenged = True
        return _AuthorizationNeeded()


class _ConnectFailure(Exception):  # noqa: N818 - internal control flow
    """A classified failure of one connection attempt."""

    def __init__(self, kind: str, error_type: str, retryable: bool) -> None:
        super().__init__(kind)
        self.kind = kind
        self.error_type = error_type
        self.retryable = retryable


def _leaves(exc: BaseException) -> list[BaseException]:
    """Flatten (nested) exception groups into their leaf exceptions."""
    if isinstance(exc, BaseExceptionGroup):
        found: list[BaseException] = []
        for inner in exc.exceptions:
            found.extend(_leaves(inner))
        return found
    return [exc]


def _classify(exc: BaseException, state: _ConnectionState) -> tuple[str, str]:
    """Map an SDK/transport exception to ``(kind, exception class name)``.

    Kinds: ``auth``, ``timeout``, ``connection``, ``rpc`` (a JSON-RPC error the
    server answered) and ``other``.  Order matters: ``TimeoutError`` is an
    ``OSError``, and a recorded authorization demand outranks whatever the SDK
    surfaced after tearing down the request that triggered it.
    """
    leaves = _leaves(exc)
    first = type(leaves[0]).__name__ if leaves else type(exc).__name__
    if state.challenged or any(
        isinstance(leaf, _AuthorizationNeeded | OAuthFlowError | CredentialStoreError)
        for leaf in leaves
    ):
        return "auth", first
    if any(
        isinstance(leaf, TimeoutError | httpx2.TimeoutException)
        or (isinstance(leaf, SDKMCPError) and leaf.code == REQUEST_TIMEOUT)
        for leaf in leaves
    ):
        return "timeout", first
    if any(
        isinstance(
            leaf,
            httpx2.TransportError
            | OSError
            | anyio.ClosedResourceError
            | anyio.BrokenResourceError
            | anyio.EndOfStream,
        )
        for leaf in leaves
    ):
        return "connection", first
    if any(isinstance(leaf, SDKMCPError) for leaf in leaves):
        return "rpc", first
    return "other", first


def _same_resource(url: httpx2.URL, endpoint: str) -> bool:
    """Whether *url* is the declared MCP endpoint itself."""
    target = urlsplit(endpoint)
    default_port = 443 if target.scheme == "https" else 80
    return (
        url.scheme == target.scheme
        and url.host == target.hostname
        and (url.port or default_port) == (target.port or default_port)
        and url.path == (target.path or "/")
    )


class StreamableHTTPMCPClient:
    """MCP client for a remote server reached over Streamable HTTP.

    Implements :class:`~beddel.domain.ports.IMCPClient` structurally.  See the
    module docstring for the construction-and-lifecycle contract.

    Args:
        transport: The entry's ``transport`` field; must equal
            :data:`ADAPTER_NAME`.
        endpoint: The entry's ``endpoint`` field: an HTTPS URL without userinfo,
            query or fragment.
        authorization: The entry's ``authorization`` field: ``none`` or
            ``oauth``.  Required; there is no default.
        connect_timeout: Seconds allowed for one connection-establishment
            attempt (including the MCP handshake).
        request_timeout: Seconds allowed for one MCP request.
        sse_read_timeout: Seconds a response stream may stay silent.
        max_connect_retries: Extra attempts after a failed connection
            establishment (never applied to a tool call).
        retry_backoff: Seconds before the first retry; doubles, capped.
        credentials_dir: Credential directory for ``oauth``; defaults to
            ``$BEDDEL_MCP_CREDENTIALS_DIR`` or ``~/.beddel/mcp-credentials``.
        allow_insecure_loopback: Accept ``http`` for a loopback endpoint.  Off by
            default; for tests against a local fake server only.
        httpx_transport: Replace the HTTP transport (an ``httpx2`` async
            transport).  A seam for tests that serve an ASGI fake in-process.
    """

    def __init__(
        self,
        transport: str,
        endpoint: str,
        authorization: str,
        *,
        connect_timeout: float = 10.0,
        request_timeout: float = 30.0,
        sse_read_timeout: float = 300.0,
        max_connect_retries: int = 2,
        retry_backoff: float = 0.5,
        credentials_dir: str | os.PathLike[str] | None = None,
        allow_insecure_loopback: bool = False,
        httpx_transport: Any = None,
    ) -> None:
        if not _MCP_AVAILABLE:
            raise MCPError(
                code=MCP_CONNECTION_FAILED,
                message="MCP SDK not installed. Install the kit dependencies (see its README).",
            )
        if transport != ADAPTER_NAME:
            raise MCPError(
                code=MCP_CONNECTION_FAILED,
                message=f"This adapter serves transport '{ADAPTER_NAME}' only.",
            )
        if authorization not in AUTHORIZATION_METHODS:
            raise MCPError(
                code=MCP_CONNECTION_FAILED,
                message=(
                    "Unknown authorization method; the MCP protocol kit resolves: "
                    f"{', '.join(AUTHORIZATION_METHODS)}."
                ),
            )
        for value in (connect_timeout, request_timeout, sse_read_timeout):
            if not isinstance(value, int | float) or not 0 < value < float("inf"):
                raise MCPError(
                    code=MCP_CONNECTION_FAILED,
                    message="Timeouts must be finite positive numbers of seconds.",
                )
        if max_connect_retries < 0 or retry_backoff < 0:
            raise MCPError(
                code=MCP_CONNECTION_FAILED,
                message="Retry settings must not be negative.",
            )
        self._endpoint = canonical_endpoint(
            endpoint, allow_insecure_loopback=allow_insecure_loopback
        )
        self._authorization = authorization
        self._connect_timeout = float(connect_timeout)
        self._request_timeout = float(request_timeout)
        self._sse_read_timeout = float(sse_read_timeout)
        self._max_connect_retries = max_connect_retries
        self._retry_backoff = retry_backoff
        self._store = CredentialStore(credentials_dir)
        self._httpx_transport = httpx_transport

        self._lock = asyncio.Lock()
        self._client: Any = None
        self._runner: asyncio.Task[None] | None = None
        self._stop: asyncio.Event | None = None
        self._state: _ConnectionState | None = None

    def __repr__(self) -> str:
        return (
            f"StreamableHTTPMCPClient(endpoint={self._endpoint!r}, "
            f"authorization={self._authorization!r})"
        )

    # ------------------------------------------------------------------
    # IMCPClient port
    # ------------------------------------------------------------------

    async def connect(self, server_uri: str) -> None:
        """Connect now; accepted only for the endpoint this client was built for.

        The core never calls this -- the client connects on its first call.

        Raises:
            MCPError: ``BEDDEL-MCP-600`` for any other endpoint, plus the errors
                of a first call.
        """
        requested = canonical_endpoint(
            server_uri,
            allow_insecure_loopback=self._endpoint.startswith("http://"),
        )
        if requested != self._endpoint:
            raise MCPError(
                code=MCP_CONNECTION_FAILED,
                message="connect() accepts only the endpoint this client was declared with.",
            )
        await self._ensure_connected()

    async def list_tools(self) -> list[dict[str, Any]]:
        """Discover the server's tools.

        Returns:
            Descriptors with ``name``, ``description`` and ``inputSchema`` -- the
            key the tool primitive reads.
        """

        async def operation(client: Any) -> list[dict[str, Any]]:
            descriptors: list[dict[str, Any]] = []
            cursor: str | None = None
            for _ in range(_MAX_LIST_PAGES):
                page = await client.list_tools(cursor=cursor)
                descriptors.extend(
                    {
                        "name": tool.name,
                        "description": tool.description or "",
                        "inputSchema": tool.input_schema or {},
                    }
                    for tool in page.tools
                )
                cursor = page.next_cursor
                if not cursor:
                    break
            return descriptors

        return await self._request(operation, what="list tools")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Invoke a tool.  A result the server marks as an error raises.

        Raises:
            MCPError: ``BEDDEL-MCP-602`` when the server reports an error result;
                ``BEDDEL-MCP-605`` when authorization is required;
                ``BEDDEL-MCP-604`` / ``BEDDEL-MCP-600`` on timeout / connection
                failure.  A tool call is never retried.
        """

        async def operation(client: Any) -> Any:
            result = await client.call_tool(
                name, arguments, read_timeout_seconds=self._request_timeout
            )
            if result.is_error:
                raise MCPError(
                    code=MCP_TOOL_INVOCATION_FAILED,
                    message=f"MCP tool '{name}' reported an error result.",
                    details={"tool": name, "endpoint": self._endpoint},
                )
            return result.content

        return await self._request(operation, what=f"call tool '{name}'")

    async def disconnect(self) -> None:
        """Close the connection.  Safe whether or not one was made."""
        async with self._lock:
            await self._teardown()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connection_alive(self) -> bool:
        return self._client is not None and self._runner is not None and not self._runner.done()

    async def _ensure_connected(self) -> Any:
        if self._connection_alive():
            return self._client
        async with self._lock:
            if self._connection_alive():
                return self._client
            await self._teardown()
            await self._connect_with_retries()
            return self._client

    async def _connect_with_retries(self) -> None:
        delay = self._retry_backoff
        attempts = self._max_connect_retries + 1
        failure: _ConnectFailure | None = None
        for attempt in range(1, attempts + 1):
            try:
                await self._open_once()
                return
            except _ConnectFailure as caught:
                failure = caught
            if not failure.retryable or attempt == attempts:
                break
            _LOG.debug("MCP connect attempt %d failed (%s); retrying", attempt, failure.kind)
            await asyncio.sleep(delay)
            delay = min(delay * 2, _MAX_BACKOFF)
        assert failure is not None  # the loop ran at least once and did not return
        # Raised outside any except block: no SDK or transport exception (which
        # may carry response text) stays reachable through __context__.
        raise self._connect_error(failure)

    async def _open_once(self) -> None:
        """One bounded connection-establishment attempt."""
        loop = asyncio.get_running_loop()
        ready: asyncio.Future[Any] = loop.create_future()
        stop = asyncio.Event()
        state = _ConnectionState()
        runner = asyncio.create_task(self._run(ready, stop, state), name="beddel-mcp-connection")
        failure: _ConnectFailure | None = None
        try:
            client = await ready
        except asyncio.CancelledError:
            await self._abort_runner(runner)
            raise
        except Exception as exc:
            await self._abort_runner(runner)
            kind, error_type = _classify(exc, state)
            # Never repeat an attempt that already spent a refresh token.
            retryable = kind in {"timeout", "connection"} and not state.refresh_sent
            failure = _ConnectFailure(kind, error_type, retryable)
        if failure is not None:
            raise failure  # outside the except block: nothing chained to it
        self._client = client
        self._runner = runner
        self._stop = stop
        self._state = state

    async def _run(
        self,
        ready: asyncio.Future[Any],
        stop: asyncio.Event,
        state: _ConnectionState,
    ) -> None:
        """Own the SDK connection for its whole life, in this one task.

        anyio cancel scopes must be entered and exited by the same task; the
        core may call from different tasks (``asyncio.wait_for`` wraps a call in
        its own task on Python 3.11), so the connection is held here and callers
        only use the ``Client`` object.
        """
        try:
            async with contextlib.AsyncExitStack() as stack:
                auth = self._build_auth(state)
                http = await stack.enter_async_context(self._build_http_client(auth, state))
                client = Client(
                    streamable_http_client(self._endpoint, http_client=http),
                    read_timeout_seconds=self._request_timeout,
                )
                # asyncio.timeout, not anyio.fail_after: the contexts entered here
                # outlive this block, and an anyio cancel scope may not close
                # before the scopes opened inside it.
                async with asyncio.timeout(self._connect_timeout):
                    await stack.enter_async_context(client)
                if not ready.done():
                    ready.set_result(client)
                await stop.wait()
        except asyncio.CancelledError:
            if not ready.done():
                ready.cancel()
            raise
        except BaseException as exc:
            if not ready.done():
                ready.set_exception(exc)
            else:
                _LOG.debug("MCP connection ended with %s", type(exc).__name__)

    async def _abort_runner(self, runner: asyncio.Task[None]) -> None:
        """Cancel a connection task that never became ready, and wait for it."""
        runner.cancel()
        with contextlib.suppress(Exception, asyncio.CancelledError):
            await runner

    async def _stop_runner(self, runner: asyncio.Task[None], stop: asyncio.Event) -> None:
        """Close an established connection: graceful first, then forced."""
        stop.set()
        try:
            await asyncio.wait_for(asyncio.shield(runner), timeout=_CLOSE_TIMEOUT)
        except (TimeoutError, Exception):
            await self._abort_runner(runner)

    async def _teardown(self) -> None:
        runner, stop = self._runner, self._stop
        self._client = self._runner = self._stop = self._state = None
        if runner is not None and stop is not None:
            await self._stop_runner(runner, stop)

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    def _build_auth(self, state: _ConnectionState) -> Any:
        """Return the ``httpx2.Auth`` for this connection (``None`` for ``none``)."""
        if self._authorization == AUTHORIZATION_NONE:
            return None

        async def refuse_redirect(_url: str) -> None:
            raise state.demand()

        async def refuse_callback() -> AuthorizationCodeResult:
            raise state.demand()

        # Fail before any I/O toward the server when the operator has not
        # authorized this endpoint: a run never starts a login.
        stored = None
        unusable = False
        try:
            stored = self._store.read(self._endpoint, self._authorization)
        except CredentialStoreError:
            unusable = True
        if unusable or stored is None or stored.tokens is None or stored.client_info is None:
            raise state.demand()

        provider = OAuthClientProvider(
            server_url=self._endpoint,
            client_metadata=OAuthClientMetadata(
                client_name=_CLIENT_NAME,
                redirect_uris=[AnyUrl("http://127.0.0.1/callback")],
                token_endpoint_auth_method="none",
            ),
            storage=FileTokenStorage(self._store, self._endpoint, self._authorization),
            redirect_handler=refuse_redirect,
            callback_handler=refuse_callback,
        )
        # The SDK does not know when a persisted token expires; tell it, so an
        # expired access token is refreshed (when a refresh token is held)
        # instead of being presented to the server first.
        provider.context.token_expiry_time = stored.expires_at
        # Likewise hand it the authorization-server metadata the operator flow
        # discovered, so the refresh goes to the real token endpoint; ignored
        # unless it names the issuer the stored registration is bound to.
        if stored.oauth_metadata and stored.client_info.issuer:
            try:
                metadata = OAuthMetadata.model_validate(stored.oauth_metadata)
            except ValueError:
                metadata = None
            if metadata is not None and str(metadata.issuer).rstrip("/") == str(
                stored.client_info.issuer
            ).rstrip("/"):
                provider.context.oauth_metadata = metadata
                provider.context.auth_server_url = stored.auth_server_url
        return provider

    def _build_http_client(self, auth: Any, state: _ConnectionState) -> Any:
        hooks: dict[str, list[Callable[..., Awaitable[None]]]] = {"request": [], "response": []}
        if self._authorization == AUTHORIZATION_NONE:

            async def on_response(response: httpx2.Response) -> None:
                if response.status_code in _AUTH_CHALLENGE_STATUSES:
                    raise state.demand()

            hooks["response"].append(on_response)
        else:

            async def on_request(request: httpx2.Request) -> None:
                content_type = request.headers.get("content-type", "")
                # A run must not register a client at an authorization server:
                # the SDK would do so (a JSON POST that is not the MCP endpoint)
                # if the stored registration no longer matches the issuer.
                if (
                    request.method == "POST"
                    and content_type.startswith("application/json")
                    and not _same_resource(request.url, self._endpoint)
                ):
                    raise state.demand()
                # A refresh request may consume a rotating refresh token, so an
                # attempt that sent one is never repeated (see _open_once).
                if request.method == "POST" and content_type.startswith(
                    "application/x-www-form-urlencoded"
                ):
                    grant = parse_qs(request.content.decode("ascii", "replace")).get(
                        "grant_type", [""]
                    )
                    if grant[0] == "refresh_token":
                        state.refresh_sent = True

            hooks["request"].append(on_request)

        kwargs: dict[str, Any] = {}
        if self._httpx_transport is not None:
            kwargs["transport"] = self._httpx_transport
        return httpx2.AsyncClient(
            auth=auth,
            event_hooks=hooks,
            timeout=httpx2.Timeout(
                connect=self._connect_timeout,
                read=self._sse_read_timeout,
                write=self._request_timeout,
                pool=self._connect_timeout,
            ),
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Requests and error mapping
    # ------------------------------------------------------------------

    async def _request(self, operation: Callable[[Any], Awaitable[_T]], *, what: str) -> _T:
        client = await self._ensure_connected()
        state = self._state or _ConnectionState()
        try:
            return await operation(client)
        except (MCPError, asyncio.CancelledError):
            raise
        except Exception as exc:
            kind, error_type = _classify(exc, state)
            if kind in {"auth", "connection"}:
                # The transport behind this client is gone or was torn down; the
                # next call reconnects (and re-reads the credentials).
                async with self._lock:
                    if self._client is client:
                        await self._teardown()
        # Raised outside the except block: no SDK or transport exception (which
        # may carry response text) stays reachable through __context__.
        raise self._call_error(kind, error_type, what)

    def _authorization_error(self) -> MCPError:
        if self._authorization == AUTHORIZATION_NONE:
            message = (
                f"MCP server at {self._endpoint} requires authentication, but its entry "
                f"declares authorization '{AUTHORIZATION_NONE}'. Operator action: declare the "
                "authorization "
                "method the server requires in the workflow's mcp_servers entry and, for an "
                f"interactive method, run `{OPERATOR_COMMAND} --endpoint {self._endpoint}` "
                "outside the workflow run."
            )
        else:
            message = (
                f"MCP server at {self._endpoint} requires authorization this client does not hold "
                "(credentials missing, expired, revoked or insufficient). Operator action: run "
                f"`{OPERATOR_COMMAND} --endpoint {self._endpoint}` outside the workflow run, "
                "then retry."
            )
        return MCPError(
            code=MCP_AUTHORIZATION_REQUIRED,
            message=message,
            details={"endpoint": self._endpoint, "authorization": self._authorization},
        )

    def _connect_error(self, failure: _ConnectFailure) -> MCPError:
        if failure.kind == "auth":
            return self._authorization_error()
        details = {"endpoint": self._endpoint, "error_type": failure.error_type}
        if failure.kind == "timeout":
            return MCPError(
                code=MCP_SERVER_TIMEOUT,
                message=(
                    f"MCP server did not complete the connection within {self._connect_timeout}s "
                    f"after {self._max_connect_retries + 1} attempt(s)."
                ),
                details=details,
            )
        return MCPError(
            code=MCP_CONNECTION_FAILED,
            message=f"Could not connect to the MCP server ({failure.error_type}).",
            details=details,
        )

    def _call_error(self, kind: str, error_type: str, what: str) -> MCPError:
        if kind == "auth":
            return self._authorization_error()
        details = {"endpoint": self._endpoint, "error_type": error_type}
        if kind == "timeout":
            return MCPError(
                code=MCP_SERVER_TIMEOUT,
                message=f"MCP server did not respond within {self._request_timeout}s to {what}.",
                details=details,
            )
        if kind == "connection":
            return MCPError(
                code=MCP_CONNECTION_FAILED,
                message=f"Connection to the MCP server was lost while trying to {what}.",
                details=details,
            )
        return MCPError(
            code=MCP_TOOL_INVOCATION_FAILED,
            message=f"MCP server reported an error while trying to {what}.",
            details=details,
        )
