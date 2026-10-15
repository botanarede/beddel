"""In-process fakes for the remote MCP client tests: no network, no real server.

``FakeServer`` is one ASGI app that plays three roles, selected by the request's
``Host`` header: the MCP server (``MCP_HOST``), an OAuth authorization server
(``AUTH_HOST``) and a second authorization server (``OTHER_AUTH_HOST``) used to
test an issuer change.  It is served to the client through
``httpx2.ASGITransport`` -- there is no socket, no DNS and no real destination.

Every token and code is generated per instance from ``secrets`` -- nothing in
this repository is, or looks like, a credential -- and a request log records
only *whether* and *which fake* credential was presented, never printing one.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs

import httpx2
from beddel_protocol_mcp.credentials import CredentialStore, StoredCredentials
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl

MCP_HOST = "mcp.test"
AUTH_HOST = "auth.test"
OTHER_AUTH_HOST = "other-auth.test"
MCP_URL = f"https://{MCP_HOST}/mcp"


@dataclass
class Seen:
    """One request the fake observed."""

    host: str
    method: str
    path: str
    rpc_method: str | None = None
    authorization: str | None = field(default=None, repr=False)
    content_type: str = ""


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class FakeServer:
    """A fake MCP server plus OAuth authorization server(s)."""

    def __init__(
        self,
        *,
        require_token: bool = False,
        challenge_status: int = 401,
        authorization_server_host: str = AUTH_HOST,
        tools: list[dict[str, Any]] | None = None,
    ) -> None:
        self.require_token = require_token
        self.challenge_status = challenge_status
        self.authorization_server_host = authorization_server_host
        self.tools = (
            tools
            if tools is not None
            else [
                {
                    "name": "echo",
                    "description": "Echo the message",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                    },
                }
            ]
        )
        self.seen: list[Seen] = []
        self.tool_calls = 0
        self.is_error_result = False
        self.silent = False  # accept requests, never answer
        self.initialize_delay = 0.0
        self.call_delay = 0.0
        self.fail_status: int | None = None  # answer every MCP POST with this status
        # OAuth state
        self.access_tokens: set[str] = set()
        self.refresh_tokens: set[str] = set()
        self.codes: dict[str, str] = {}  # code -> PKCE challenge
        self.registrations = 0
        self.token_requests: list[str] = []  # grant types seen
        self.refresh_fails = False
        self.access_lifetime = 3600
        self.issued: list[str] = []  # every fake token ever minted (for leak assertions)

    # -- helpers used by tests -------------------------------------------

    def issue_tokens(self, *, lifetime: int | None = None) -> dict[str, Any]:
        """Mint and remember a fresh token pair; return the RFC 6749 response."""
        access = f"acc-{secrets.token_hex(12)}"
        refresh = f"ref-{secrets.token_hex(12)}"
        self.access_tokens.add(access)
        self.refresh_tokens.add(refresh)
        self.issued.extend([access, refresh])
        return {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": self.access_lifetime if lifetime is None else lifetime,
            "refresh_token": refresh,
        }

    def revoke_all(self) -> None:
        self.access_tokens.clear()
        self.refresh_tokens.clear()

    def new_code(self, challenge: str) -> str:
        code = f"code-{secrets.token_hex(8)}"
        self.codes[code] = challenge
        return code

    def mcp_posts(self) -> list[Seen]:
        return [
            s for s in self.seen if s.host == MCP_HOST and s.path == "/mcp" and s.method == "POST"
        ]

    def transport(self) -> httpx2.ASGITransport:
        return httpx2.ASGITransport(app=self)

    @staticmethod
    def as_metadata(host: str) -> dict[str, Any]:
        """RFC 8414 metadata of the authorization server living at *host*."""
        issuer = f"https://{host}"
        return {
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/authorize",
            "token_endpoint": f"{issuer}/token",
            "registration_endpoint": f"{issuer}/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "authorization_response_iss_parameter_supported": True,
        }

    # -- ASGI -------------------------------------------------------------

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        host = headers.get("host", "").split(":")[0]
        method, path = scope["method"], scope["path"]
        rpc: dict[str, Any] | None = None
        if body and headers.get("content-type", "").startswith("application/json"):
            try:
                parsed = json.loads(body)
                rpc = parsed if isinstance(parsed, dict) else None
            except ValueError:
                rpc = None
        self.seen.append(
            Seen(
                host=host,
                method=method,
                path=path,
                rpc_method=rpc.get("method") if rpc else None,
                authorization=headers.get("authorization"),
                content_type=headers.get("content-type", ""),
            )
        )
        status, out_headers, payload = await self._route(host, method, path, headers, body, rpc)
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(k.encode(), v.encode()) for k, v in out_headers.items()],
            }
        )
        await send({"type": "http.response.body", "body": payload})

    async def _route(
        self,
        host: str,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes,
        rpc: dict[str, Any] | None,
    ) -> tuple[int, dict[str, str], bytes]:
        json_headers = {"content-type": "application/json"}
        if host == MCP_HOST and path == "/mcp":
            return await self._mcp(method, headers, rpc)
        if host == MCP_HOST and path.startswith("/.well-known/oauth-protected-resource"):
            doc = {
                "resource": MCP_URL,
                "authorization_servers": [f"https://{self.authorization_server_host}"],
            }
            return 200, json_headers, json.dumps(doc).encode()
        if host in {AUTH_HOST, OTHER_AUTH_HOST}:
            return self._authorization_server(host, method, path, body)
        return 404, json_headers, b"{}"

    async def _mcp(
        self, method: str, headers: dict[str, str], rpc: dict[str, Any] | None
    ) -> tuple[int, dict[str, str], bytes]:
        if method != "POST":
            return 405, {}, b""
        if self.fail_status is not None:
            return self.fail_status, {}, b""
        if self.require_token:
            presented = headers.get("authorization", "")
            if not presented.startswith("Bearer ") or presented[7:] not in self.access_tokens:
                challenge = (
                    'Bearer resource_metadata="https://'
                    f'{MCP_HOST}/.well-known/oauth-protected-resource/mcp"'
                )
                return self.challenge_status, {"www-authenticate": challenge}, b""
        if rpc is None:
            return 400, {}, b""
        rpc_method = rpc.get("method")
        request_id = rpc.get("id")
        if self.silent:
            await asyncio.sleep(3600)
        if rpc_method == "server/discover":
            return self._rpc_error(request_id, -32601, "Method not found")
        if rpc_method == "initialize":
            if self.initialize_delay:
                await asyncio.sleep(self.initialize_delay)
            result = {
                "protocolVersion": "2025-11-25",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake-mcp", "version": "0"},
            }
            return self._rpc_result(request_id, result)
        if request_id is None:  # notification
            return 202, {}, b""
        if rpc_method == "tools/list":
            return self._rpc_result(request_id, {"tools": self.tools})
        if rpc_method == "tools/call":
            self.tool_calls += 1
            if self.call_delay:
                await asyncio.sleep(self.call_delay)
            args = (rpc.get("params") or {}).get("arguments") or {}
            result = {
                "content": [{"type": "text", "text": str(args.get("message", "ok"))}],
                "isError": self.is_error_result,
            }
            return self._rpc_result(request_id, result)
        return self._rpc_error(request_id, -32601, "Method not found")

    @staticmethod
    def _rpc_result(request_id: Any, result: dict[str, Any]) -> tuple[int, dict[str, str], bytes]:
        doc = {"jsonrpc": "2.0", "id": request_id, "result": result}
        return 200, {"content-type": "application/json"}, json.dumps(doc).encode()

    @staticmethod
    def _rpc_error(request_id: Any, code: int, message: str) -> tuple[int, dict[str, str], bytes]:
        doc = {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
        return 200, {"content-type": "application/json"}, json.dumps(doc).encode()

    def _authorization_server(
        self, host: str, method: str, path: str, body: bytes
    ) -> tuple[int, dict[str, str], bytes]:
        json_headers = {"content-type": "application/json"}
        if path == "/.well-known/oauth-authorization-server":
            return 200, json_headers, json.dumps(self.as_metadata(host)).encode()
        if path == "/register" and method == "POST":
            self.registrations += 1
            request = json.loads(body)
            request["client_id"] = f"client-{secrets.token_hex(6)}"
            request["token_endpoint_auth_method"] = "none"
            return 201, json_headers, json.dumps(request).encode()
        if path == "/token" and method == "POST":
            form = {k: v[0] for k, v in parse_qs(body.decode()).items()}
            grant = form.get("grant_type", "")
            self.token_requests.append(grant)
            if grant == "authorization_code":
                challenge = self.codes.pop(form.get("code", ""), None)
                verifier = form.get("code_verifier", "")
                if challenge is None or _pkce_challenge(verifier) != challenge:
                    return 400, json_headers, b'{"error": "invalid_grant"}'
                return 200, json_headers, json.dumps(self.issue_tokens()).encode()
            if grant == "refresh_token":
                presented = form.get("refresh_token", "")
                if self.refresh_fails or presented not in self.refresh_tokens:
                    return 400, json_headers, b'{"error": "invalid_grant"}'
                self.refresh_tokens.discard(presented)
                return 200, json_headers, json.dumps(self.issue_tokens()).encode()
            return 400, json_headers, b'{"error": "unsupported_grant_type"}'
        return 404, json_headers, b"{}"


def now() -> float:
    """Wall clock, isolated so tests read the same clock the client does."""
    return time.time()


def seed_credentials(
    fake: FakeServer,
    store: CredentialStore,
    *,
    endpoint: str = MCP_URL,
    authorization: str = "oauth",
    expires_at: float | None = None,
    with_refresh: bool = True,
    issuer: str = f"https://{AUTH_HOST}",
) -> dict[str, Any]:
    """Store fake-issued credentials as the operator command would have.

    Returns the token response so a test can compare values it must never see
    in a log or message.
    """
    response = fake.issue_tokens()
    if not with_refresh:
        fake.refresh_tokens.discard(response["refresh_token"])
        del response["refresh_token"]
    tokens = OAuthToken.model_validate(response)
    client_info = OAuthClientInformationFull(
        client_id=f"client-{secrets.token_hex(4)}",
        redirect_uris=[AnyUrl("http://127.0.0.1:9/callback")],
        token_endpoint_auth_method="none",
        issuer=issuer,
    )
    store.write(
        endpoint,
        authorization,
        StoredCredentials(
            tokens=tokens,
            expires_at=expires_at if expires_at is not None else time.time() + 3600,
            client_info=client_info,
            oauth_metadata=FakeServer.as_metadata(issuer.removeprefix("https://")),
            auth_server_url=issuer,
        ),
    )
    return response
