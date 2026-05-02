"""GCP Managed MCP Server client adapter.

Connects to Google's remote MCP servers via SSE transport with ADC auth.
Manages multiple server connections simultaneously.
"""

from __future__ import annotations

import contextlib
from typing import Any

from beddel.domain.errors import MCPError

# GCP-specific error codes (kit-local, not in beddel/error_codes.py)
MCP_GCP_CONNECTION_FAILED: str = "BEDDEL-MCP-970"
MCP_GCP_AUTH_FAILED: str = "BEDDEL-MCP-971"
MCP_GCP_TOOL_INVOCATION_FAILED: str = "BEDDEL-MCP-972"

try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

try:
    import google.auth
    import google.auth.transport.requests

    _GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    _GOOGLE_AUTH_AVAILABLE = False

__all__ = ["GCPMCPClient"]


class GCPMCPClient:
    """Multi-server MCP client for Google Managed MCP Servers.

    Implements the :class:`~beddel.domain.ports.IMCPClient` protocol
    structurally (no explicit inheritance).  Manages multiple SSE
    connections to Google's remote MCP servers with ADC authentication.

    Args:
        servers: List of server configs, each with 'name' and 'endpoint' keys.
        project: GCP project ID (optional, used for endpoint URL construction).
        timeout: Connection timeout in seconds.
        sse_read_timeout: SSE read timeout in seconds.
    """

    def __init__(
        self,
        servers: list[dict[str, str]],
        project: str | None = None,
        timeout: float = 30.0,
        sse_read_timeout: float = 300.0,
    ) -> None:
        if not _MCP_AVAILABLE:
            raise MCPError(
                code=MCP_GCP_CONNECTION_FAILED,
                message="MCP SDK not installed. Install with: pip install mcp",
            )
        if not _GOOGLE_AUTH_AVAILABLE:
            raise MCPError(
                code=MCP_GCP_AUTH_FAILED,
                message="google-auth not installed. Install with: pip install google-auth",
            )
        self._servers = servers
        self._project = project
        self._timeout = timeout
        self._sse_read_timeout = sse_read_timeout
        # Per-server state
        self._sessions: dict[str, ClientSession] = {}
        self._context_managers: dict[str, Any] = {}
        # Tool routing: tool_name -> server_name
        self._tool_server_map: dict[str, str] = {}

    def _get_auth_headers(self) -> dict[str, str]:
        """Get OAuth2 bearer token headers via ADC.

        Returns:
            Dict with Authorization header.

        Raises:
            MCPError: BEDDEL-MCP-971 on auth failure.
        """
        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            credentials.refresh(google.auth.transport.requests.Request())
            return {"Authorization": f"Bearer {credentials.token}"}
        except Exception as exc:
            raise MCPError(
                code=MCP_GCP_AUTH_FAILED,
                message=f"GCP authentication failed: {exc}",
            ) from exc

    async def connect(self, server_uri: str) -> None:
        """Connect to all configured GCP MCP servers.

        The *server_uri* parameter is accepted for
        :class:`~beddel.domain.ports.IMCPClient` interface compliance
        but is ignored — server endpoints come from the constructor's
        servers list.

        Raises:
            MCPError: BEDDEL-MCP-971 on auth failure.
            MCPError: BEDDEL-MCP-970 on connection failure.
        """
        headers = self._get_auth_headers()

        for server_config in self._servers:
            name = server_config["name"]
            endpoint = server_config["endpoint"]
            try:
                cm = sse_client(
                    endpoint,
                    headers=headers,
                    timeout=self._timeout,
                    sse_read_timeout=self._sse_read_timeout,
                )
                read, write = await cm.__aenter__()
                session = ClientSession(read, write)
                await session.__aenter__()
                await session.initialize()
                self._sessions[name] = session
                self._context_managers[name] = cm
            except MCPError:
                raise
            except Exception as exc:
                await self._cleanup()
                raise MCPError(
                    code=MCP_GCP_CONNECTION_FAILED,
                    message=(f"Failed to connect to GCP MCP server '{name}': {exc}"),
                    details={"server": name, "endpoint": endpoint},
                ) from exc

        # Build tool routing map after all connections established
        await self._build_tool_map()

    async def _build_tool_map(self) -> None:
        """Build the tool-to-server routing map from all connected servers."""
        self._tool_server_map.clear()
        for server_name, session in self._sessions.items():
            try:
                result = await session.list_tools()
                for tool in result.tools:
                    self._tool_server_map[tool.name] = server_name
            except Exception:
                pass  # Skip servers that fail tool listing

    async def list_tools(self) -> list[dict[str, Any]]:
        """List tools from all connected GCP MCP servers.

        Returns:
            Aggregated list of tool descriptors with server provenance.

        Raises:
            MCPError: BEDDEL-MCP-970 if not connected.
            MCPError: BEDDEL-MCP-972 on listing failure.
        """
        self._ensure_connected()
        tools: list[dict[str, Any]] = []
        for server_name, session in self._sessions.items():
            try:
                result = await session.list_tools()
                for tool in result.tools:
                    tools.append(
                        {
                            "name": tool.name,
                            "description": getattr(tool, "description", None) or "",
                            "inputSchema": getattr(tool, "inputSchema", None) or {},
                            "server": server_name,
                        }
                    )
            except MCPError:
                raise
            except Exception as exc:
                raise MCPError(
                    code=MCP_GCP_TOOL_INVOCATION_FAILED,
                    message=(
                        f"Failed to list tools from server '{server_name}': {exc}"
                    ),
                    details={"server": server_name},
                ) from exc
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool on the appropriate GCP MCP server.

        Routes the call to the server that provides the named tool.

        Raises:
            MCPError: BEDDEL-MCP-970 if not connected.
            MCPError: BEDDEL-MCP-972 if tool not found or invocation fails.
        """
        self._ensure_connected()
        server_name = self._tool_server_map.get(name)
        if server_name is None:
            raise MCPError(
                code=MCP_GCP_TOOL_INVOCATION_FAILED,
                message=(f"Tool '{name}' not found on any connected GCP MCP server"),
                details={
                    "tool": name,
                    "available_servers": list(self._sessions.keys()),
                },
            )
        session = self._sessions[server_name]
        try:
            result = await session.call_tool(name, arguments)
            return result.content
        except MCPError:
            raise
        except Exception as exc:
            raise MCPError(
                code=MCP_GCP_TOOL_INVOCATION_FAILED,
                message=(
                    f"GCP MCP tool '{name}' invocation failed on server "
                    f"'{server_name}': {exc}"
                ),
                details={
                    "tool": name,
                    "server": server_name,
                    "arguments": arguments,
                },
            ) from exc

    async def disconnect(self) -> None:
        """Disconnect from all GCP MCP servers."""
        await self._cleanup()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        """Raise if no servers are connected."""
        if not self._sessions:
            raise MCPError(
                code=MCP_GCP_CONNECTION_FAILED,
                message=("Not connected to any GCP MCP server. Call connect() first."),
            )

    async def _cleanup(self) -> None:
        """Clean up all sessions and context managers."""
        for name in list(self._sessions.keys()):
            session = self._sessions.pop(name, None)
            if session is not None:
                with contextlib.suppress(Exception):
                    await session.__aexit__(None, None, None)
            cm = self._context_managers.pop(name, None)
            if cm is not None:
                with contextlib.suppress(Exception):
                    await cm.__aexit__(None, None, None)
        self._tool_server_map.clear()
