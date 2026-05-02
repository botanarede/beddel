"""Tests for GCPMCPClient adapter.

All GCP auth and MCP SDK interactions are mocked — no real GCP connections.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from beddel.domain.errors import MCPError
from beddel_protocol_gcp_mcp.client import (
    MCP_GCP_AUTH_FAILED,
    MCP_GCP_CONNECTION_FAILED,
    MCP_GCP_TOOL_INVOCATION_FAILED,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_SERVERS = [
    {
        "name": "bigquery",
        "endpoint": "https://mcp.googleapis.com/v1alpha/projects/test/locations/global/mcpServers/bigquery",
    },
    {
        "name": "maps",
        "endpoint": "https://mcp.googleapis.com/v1alpha/projects/test/locations/global/mcpServers/google-maps",
    },
]


def _make_mock_tool(
    name: str = "test-tool",
    description: str = "A test tool",
    input_schema: dict[str, Any] | None = None,
) -> SimpleNamespace:
    """Create a mock MCP tool object matching the SDK's Tool shape."""
    return SimpleNamespace(
        name=name,
        description=description,
        inputSchema=input_schema or {"type": "object"},
    )


def _make_mock_credentials() -> MagicMock:
    """Create a mock google.auth credentials object."""
    creds = MagicMock()
    creds.token = "fake-bearer-token-123"
    creds.refresh = MagicMock()
    return creds


def _make_mock_session(
    tools: list[SimpleNamespace] | None = None,
    call_result: Any = None,
) -> AsyncMock:
    """Create a mock ClientSession with async context manager support."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.initialize = AsyncMock()
    session.list_tools = AsyncMock(
        return_value=SimpleNamespace(tools=tools or []),
    )
    session.call_tool = AsyncMock(
        return_value=SimpleNamespace(content=call_result or []),
    )
    return session


def _make_mock_sse_cm() -> AsyncMock:
    """Create a mock sse_client context manager yielding (read, write)."""
    mock_read = MagicMock()
    mock_write = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _patch_google_auth(
    credentials: MagicMock | None = None,
    project: str = "test-project",
) -> Any:
    """Patch google.auth.default to return mock credentials."""
    creds = credentials or _make_mock_credentials()
    return patch(
        "beddel_protocol_gcp_mcp.client.google.auth.default",
        return_value=(creds, project),
    )


def _patch_google_auth_request() -> Any:
    """Patch google.auth.transport.requests.Request."""
    return patch(
        "beddel_protocol_gcp_mcp.client.google.auth.transport.requests.Request",
        return_value=MagicMock(),
    )


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    """Verify GCPMCPClient constructor stores config correctly."""

    def test_constructor_accepts_server_list(self) -> None:
        """Constructor stores servers and default config."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        client = GCPMCPClient(servers=SAMPLE_SERVERS)

        assert client._servers == SAMPLE_SERVERS
        assert client._project is None
        assert client._timeout == 30.0
        assert client._sse_read_timeout == 300.0
        assert client._sessions == {}
        assert client._tool_server_map == {}

    def test_constructor_accepts_optional_params(self) -> None:
        """Constructor stores optional project, timeout, sse_read_timeout."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        client = GCPMCPClient(
            servers=SAMPLE_SERVERS,
            project="my-project",
            timeout=60.0,
            sse_read_timeout=600.0,
        )

        assert client._project == "my-project"
        assert client._timeout == 60.0
        assert client._sse_read_timeout == 600.0


# ---------------------------------------------------------------------------
# _get_auth_headers
# ---------------------------------------------------------------------------


class TestGetAuthHeaders:
    """Verify _get_auth_headers returns correct Bearer header."""

    def test_get_auth_headers_returns_bearer_token(self) -> None:
        """_get_auth_headers returns Authorization header with Bearer token."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        mock_creds = _make_mock_credentials()
        mock_creds.token = "my-oauth-token"

        with _patch_google_auth(mock_creds), _patch_google_auth_request():
            client = GCPMCPClient(servers=SAMPLE_SERVERS)
            headers = client._get_auth_headers()

        assert headers == {"Authorization": "Bearer my-oauth-token"}
        mock_creds.refresh.assert_called_once()

    def test_get_auth_headers_raises_mcp_error_on_auth_failure(self) -> None:
        """_get_auth_headers raises MCPError(BEDDEL-MCP-971) on auth failure."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        with patch(
            "beddel_protocol_gcp_mcp.client.google.auth.default",
            side_effect=RuntimeError("No credentials found"),
        ):
            client = GCPMCPClient(servers=SAMPLE_SERVERS)

            with pytest.raises(MCPError) as exc_info:
                client._get_auth_headers()

            assert exc_info.value.code == MCP_GCP_AUTH_FAILED


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------


class TestConnect:
    """Verify connect creates sessions for each configured server."""

    async def test_connect_creates_sessions_for_each_server(self) -> None:
        """connect() establishes sessions for all configured servers."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        mock_session = _make_mock_session()
        mock_sse_cm = _make_mock_sse_cm()

        with (
            _patch_google_auth(),
            _patch_google_auth_request(),
            patch(
                "beddel_protocol_gcp_mcp.client.sse_client",
                return_value=mock_sse_cm,
            ),
            patch(
                "beddel_protocol_gcp_mcp.client.ClientSession",
                return_value=mock_session,
            ),
        ):
            client = GCPMCPClient(servers=SAMPLE_SERVERS)
            await client.connect("ignored://uri")

            # Sessions created for both servers
            assert "bigquery" in client._sessions
            assert "maps" in client._sessions
            assert len(client._sessions) == 2

            # Session was initialized for each server
            assert mock_session.initialize.await_count == 2

    async def test_connect_passes_auth_headers_to_sse_client(self) -> None:
        """connect() passes OAuth2 bearer headers to sse_client."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        mock_creds = _make_mock_credentials()
        mock_creds.token = "test-token-xyz"
        mock_session = _make_mock_session()
        mock_sse_cm = _make_mock_sse_cm()

        with (
            _patch_google_auth(mock_creds),
            _patch_google_auth_request(),
            patch(
                "beddel_protocol_gcp_mcp.client.sse_client",
                return_value=mock_sse_cm,
            ) as mock_sse_fn,
            patch(
                "beddel_protocol_gcp_mcp.client.ClientSession",
                return_value=mock_session,
            ),
        ):
            servers = [SAMPLE_SERVERS[0]]
            client = GCPMCPClient(servers=servers)
            await client.connect("ignored://uri")

            mock_sse_fn.assert_called_once_with(
                servers[0]["endpoint"],
                headers={"Authorization": "Bearer test-token-xyz"},
                timeout=30.0,
                sse_read_timeout=300.0,
            )


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------


class TestListTools:
    """Verify list_tools aggregates tools from multiple servers."""

    async def test_list_tools_aggregates_from_multiple_servers(self) -> None:
        """list_tools returns tools from all servers with server key."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        bq_tools = [
            _make_mock_tool("query", "Run SQL query", {"type": "object"}),
            _make_mock_tool("list_tables", "List tables"),
        ]
        maps_tools = [
            _make_mock_tool("geocode", "Geocode address"),
        ]

        # Create separate sessions for each server
        bq_session = _make_mock_session(tools=bq_tools)
        maps_session = _make_mock_session(tools=maps_tools)

        sessions_iter = iter([bq_session, maps_session])

        mock_sse_cm = _make_mock_sse_cm()

        with (
            _patch_google_auth(),
            _patch_google_auth_request(),
            patch(
                "beddel_protocol_gcp_mcp.client.sse_client",
                return_value=mock_sse_cm,
            ),
            patch(
                "beddel_protocol_gcp_mcp.client.ClientSession",
                side_effect=lambda r, w: next(sessions_iter),
            ),
        ):
            client = GCPMCPClient(servers=SAMPLE_SERVERS)
            await client.connect("ignored://uri")

            tools = await client.list_tools()

        assert len(tools) == 3

        # BigQuery tools have server="bigquery"
        bq_result = [t for t in tools if t["server"] == "bigquery"]
        assert len(bq_result) == 2
        assert bq_result[0]["name"] == "query"
        assert bq_result[1]["name"] == "list_tables"

        # Maps tools have server="maps"
        maps_result = [t for t in tools if t["server"] == "maps"]
        assert len(maps_result) == 1
        assert maps_result[0]["name"] == "geocode"

        # Each tool has required keys
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert "server" in tool

    async def test_list_tools_raises_when_not_connected(self) -> None:
        """list_tools raises MCPError(BEDDEL-MCP-970) when not connected."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        client = GCPMCPClient(servers=SAMPLE_SERVERS)

        with pytest.raises(MCPError) as exc_info:
            await client.list_tools()

        assert exc_info.value.code == MCP_GCP_CONNECTION_FAILED


# ---------------------------------------------------------------------------
# call_tool
# ---------------------------------------------------------------------------


class TestCallTool:
    """Verify call_tool routes to correct server and handles errors."""

    async def test_call_tool_routes_to_correct_server(self) -> None:
        """call_tool routes to the server that provides the named tool."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        bq_tools = [_make_mock_tool("query", "Run SQL")]
        maps_tools = [_make_mock_tool("geocode", "Geocode")]

        bq_session = _make_mock_session(
            tools=bq_tools,
            call_result=[{"type": "text", "text": "query result"}],
        )
        maps_session = _make_mock_session(
            tools=maps_tools,
            call_result=[{"type": "text", "text": "geocode result"}],
        )

        sessions_iter = iter([bq_session, maps_session])
        mock_sse_cm = _make_mock_sse_cm()

        with (
            _patch_google_auth(),
            _patch_google_auth_request(),
            patch(
                "beddel_protocol_gcp_mcp.client.sse_client",
                return_value=mock_sse_cm,
            ),
            patch(
                "beddel_protocol_gcp_mcp.client.ClientSession",
                side_effect=lambda r, w: next(sessions_iter),
            ),
        ):
            client = GCPMCPClient(servers=SAMPLE_SERVERS)
            await client.connect("ignored://uri")

            # Call tool on bigquery server
            result = await client.call_tool("query", {"sql": "SELECT 1"})
            assert result == [{"type": "text", "text": "query result"}]
            bq_session.call_tool.assert_awaited_once_with(
                "query",
                {"sql": "SELECT 1"},
            )

            # Call tool on maps server
            result = await client.call_tool("geocode", {"address": "NYC"})
            assert result == [{"type": "text", "text": "geocode result"}]
            maps_session.call_tool.assert_awaited_once_with(
                "geocode",
                {"address": "NYC"},
            )

    async def test_call_tool_raises_on_unknown_tool(self) -> None:
        """call_tool raises MCPError(BEDDEL-MCP-972) for unknown tool."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        mock_session = _make_mock_session()
        mock_sse_cm = _make_mock_sse_cm()

        with (
            _patch_google_auth(),
            _patch_google_auth_request(),
            patch(
                "beddel_protocol_gcp_mcp.client.sse_client",
                return_value=mock_sse_cm,
            ),
            patch(
                "beddel_protocol_gcp_mcp.client.ClientSession",
                return_value=mock_session,
            ),
        ):
            client = GCPMCPClient(servers=SAMPLE_SERVERS)
            await client.connect("ignored://uri")

            with pytest.raises(MCPError) as exc_info:
                await client.call_tool("nonexistent-tool", {})

            assert exc_info.value.code == MCP_GCP_TOOL_INVOCATION_FAILED

    async def test_call_tool_raises_when_not_connected(self) -> None:
        """call_tool raises MCPError(BEDDEL-MCP-970) when not connected."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        client = GCPMCPClient(servers=SAMPLE_SERVERS)

        with pytest.raises(MCPError) as exc_info:
            await client.call_tool("query", {"sql": "SELECT 1"})

        assert exc_info.value.code == MCP_GCP_CONNECTION_FAILED


# ---------------------------------------------------------------------------
# disconnect
# ---------------------------------------------------------------------------


class TestDisconnect:
    """Verify disconnect cleans up all sessions and context managers."""

    async def test_disconnect_cleans_up_all_sessions(self) -> None:
        """disconnect() exits all sessions and context managers."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        bq_session = _make_mock_session()
        maps_session = _make_mock_session()

        sessions_iter = iter([bq_session, maps_session])
        mock_sse_cm_1 = _make_mock_sse_cm()
        mock_sse_cm_2 = _make_mock_sse_cm()
        sse_cms_iter = iter([mock_sse_cm_1, mock_sse_cm_2])

        with (
            _patch_google_auth(),
            _patch_google_auth_request(),
            patch(
                "beddel_protocol_gcp_mcp.client.sse_client",
                side_effect=lambda *a, **kw: next(sse_cms_iter),
            ),
            patch(
                "beddel_protocol_gcp_mcp.client.ClientSession",
                side_effect=lambda r, w: next(sessions_iter),
            ),
        ):
            client = GCPMCPClient(servers=SAMPLE_SERVERS)
            await client.connect("ignored://uri")

            assert len(client._sessions) == 2

            await client.disconnect()

            # All sessions cleaned up
            assert len(client._sessions) == 0
            assert len(client._context_managers) == 0
            assert len(client._tool_server_map) == 0

            # __aexit__ called on each session and context manager
            bq_session.__aexit__.assert_awaited_once()
            maps_session.__aexit__.assert_awaited_once()
            mock_sse_cm_1.__aexit__.assert_awaited_once()
            mock_sse_cm_2.__aexit__.assert_awaited_once()

    async def test_disconnect_safe_when_not_connected(self) -> None:
        """disconnect() is safe to call when not connected."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        client = GCPMCPClient(servers=SAMPLE_SERVERS)
        # Should not raise
        await client.disconnect()


# ---------------------------------------------------------------------------
# Auth failure
# ---------------------------------------------------------------------------


class TestAuthFailure:
    """Verify auth failure raises MCPError with BEDDEL-MCP-971."""

    async def test_connect_raises_on_auth_failure(self) -> None:
        """connect() raises MCPError(BEDDEL-MCP-971) when ADC fails."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        with patch(
            "beddel_protocol_gcp_mcp.client.google.auth.default",
            side_effect=RuntimeError("ADC not configured"),
        ):
            client = GCPMCPClient(servers=SAMPLE_SERVERS)

            with pytest.raises(MCPError) as exc_info:
                await client.connect("ignored://uri")

            assert exc_info.value.code == MCP_GCP_AUTH_FAILED


# ---------------------------------------------------------------------------
# Connection failure
# ---------------------------------------------------------------------------


class TestConnectionFailure:
    """Verify connection failure raises MCPError with BEDDEL-MCP-970."""

    async def test_connect_raises_on_sse_connection_failure(self) -> None:
        """connect() raises MCPError(BEDDEL-MCP-970) when SSE fails."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        mock_sse_cm = AsyncMock()
        mock_sse_cm.__aenter__ = AsyncMock(
            side_effect=OSError("Connection refused"),
        )
        mock_sse_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            _patch_google_auth(),
            _patch_google_auth_request(),
            patch(
                "beddel_protocol_gcp_mcp.client.sse_client",
                return_value=mock_sse_cm,
            ),
        ):
            client = GCPMCPClient(servers=SAMPLE_SERVERS)

            with pytest.raises(MCPError) as exc_info:
                await client.connect("ignored://uri")

            assert exc_info.value.code == MCP_GCP_CONNECTION_FAILED


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Verify GCPMCPClient satisfies IMCPClient protocol structurally."""

    def test_satisfies_imcp_client_protocol(self) -> None:
        """GCPMCPClient has all required IMCPClient methods."""
        from beddel_protocol_gcp_mcp.client import GCPMCPClient

        for method_name in ("connect", "list_tools", "call_tool", "disconnect"):
            assert hasattr(GCPMCPClient, method_name), (
                f"GCPMCPClient missing {method_name}"
            )

        client = GCPMCPClient(servers=[])
        for method_name in ("connect", "list_tools", "call_tool", "disconnect"):
            assert callable(getattr(client, method_name))
