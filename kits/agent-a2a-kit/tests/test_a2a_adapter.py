"""Unit tests for A2AAgentAdapter and discover_agent.

Covers constructor, headers, JSON-RPC envelope, execute(), stream(),
discover_agent(), and IAgentAdapter protocol conformance.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from beddel.domain.errors import AgentError
from beddel.domain.models import AgentResult
from beddel.domain.ports import IAgentAdapter
from beddel_agent_a2a.adapter import A2AAgentAdapter
from beddel_agent_a2a.discovery import discover_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _completed_jsonrpc_response(
    task_id: str = "task-1",
    text: str = "Hello from agent",
) -> dict[str, Any]:
    """Build a successful JSON-RPC 2.0 response with a completed task."""
    return {
        "jsonrpc": "2.0",
        "id": "test-id",
        "result": {
            "id": task_id,
            "status": {"state": "completed"},
            "artifacts": [
                {"parts": [{"type": "text", "text": text}]},
            ],
        },
    }


def _jsonrpc_error_response(
    code: int = -32600,
    message: str = "Invalid request",
) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 error response."""
    return {
        "jsonrpc": "2.0",
        "id": "test-id",
        "error": {"code": code, "message": message},
    }


class _AsyncLineIterator:
    """Async iterator over a list of strings (simulates aiter_lines)."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._index = 0

    def __aiter__(self) -> _AsyncLineIterator:
        return self

    async def __anext__(self) -> str:
        if self._index >= len(self._lines):
            raise StopAsyncIteration
        line = self._lines[self._index]
        self._index += 1
        return line


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------


class TestConstructor:
    """Tests for A2AAgentAdapter.__init__."""

    async def test_accepts_agent_url_auth_token_timeout(self) -> None:
        """Constructor stores agent_url, auth_token, and timeout."""
        adapter = A2AAgentAdapter(
            agent_url="http://agent.example.com",
            auth_token="tok-123",
            timeout=60.0,
        )
        assert adapter._agent_url == "http://agent.example.com"
        assert adapter._auth_token == "tok-123"
        assert adapter._timeout == 60.0

    async def test_strips_trailing_slash(self) -> None:
        """Constructor strips trailing slash from agent_url."""
        adapter = A2AAgentAdapter(agent_url="http://agent.example.com/")
        assert adapter._agent_url == "http://agent.example.com"

    async def test_strips_multiple_trailing_slashes(self) -> None:
        """Constructor strips multiple trailing slashes."""
        adapter = A2AAgentAdapter(agent_url="http://agent.example.com///")
        assert adapter._agent_url == "http://agent.example.com"

    async def test_falls_back_to_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Constructor reads A2A_AUTH_TOKEN env var when no explicit token."""
        monkeypatch.setenv("A2A_AUTH_TOKEN", "env-token-abc")
        adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
        assert adapter._auth_token == "env-token-abc"

    async def test_explicit_token_overrides_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit auth_token takes precedence over env var."""
        monkeypatch.setenv("A2A_AUTH_TOKEN", "env-token")
        adapter = A2AAgentAdapter(
            agent_url="http://agent.example.com",
            auth_token="explicit-token",
        )
        assert adapter._auth_token == "explicit-token"

    async def test_no_token_at_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No token when neither explicit nor env var is set."""
        monkeypatch.delenv("A2A_AUTH_TOKEN", raising=False)
        adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
        assert adapter._auth_token is None


# ---------------------------------------------------------------------------
# Header tests
# ---------------------------------------------------------------------------


class TestGetHeaders:
    """Tests for A2AAgentAdapter._get_headers."""

    async def test_includes_bearer_token(self) -> None:
        """Headers include Authorization: Bearer when token is provided."""
        adapter = A2AAgentAdapter(
            agent_url="http://agent.example.com",
            auth_token="my-token",
        )
        headers = adapter._get_headers()
        assert headers["Authorization"] == "Bearer my-token"
        assert headers["Content-Type"] == "application/json"

    async def test_reads_token_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Headers include Bearer token from A2A_AUTH_TOKEN env var."""
        monkeypatch.setenv("A2A_AUTH_TOKEN", "env-secret")
        adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
        headers = adapter._get_headers()
        assert headers["Authorization"] == "Bearer env-secret"

    async def test_no_auth_header_without_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No Authorization header when no token is available."""
        monkeypatch.delenv("A2A_AUTH_TOKEN", raising=False)
        adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
        headers = adapter._get_headers()
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# JSON-RPC envelope tests
# ---------------------------------------------------------------------------


class TestBuildJsonrpcRequest:
    """Tests for A2AAgentAdapter._build_jsonrpc_request."""

    async def test_produces_valid_jsonrpc_envelope(self) -> None:
        """Envelope has jsonrpc, id, method, and params fields."""
        adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
        envelope = adapter._build_jsonrpc_request(
            "tasks/send",
            {"message": "hello"},
        )
        assert envelope["jsonrpc"] == "2.0"
        assert isinstance(envelope["id"], str)
        assert len(envelope["id"]) > 0
        assert envelope["method"] == "tasks/send"
        assert envelope["params"] == {"message": "hello"}

    async def test_unique_ids(self) -> None:
        """Each call produces a unique request id."""
        adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
        ids = {adapter._build_jsonrpc_request("m", {})["id"] for _ in range(10)}
        assert len(ids) == 10


# ---------------------------------------------------------------------------
# execute() tests
# ---------------------------------------------------------------------------


class TestExecute:
    """Tests for A2AAgentAdapter.execute."""

    async def test_sends_correct_request_returns_agent_result(self) -> None:
        """execute() sends JSON-RPC to agent URL and returns AgentResult."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _completed_jsonrpc_response()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            result = await adapter.execute("Do something")

        assert isinstance(result, AgentResult)
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://agent.example.com"

    async def test_maps_completed_task_to_agent_result(self) -> None:
        """Completed task maps to exit_code=0, output from artifacts, agent_id=url."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _completed_jsonrpc_response(
            text="Hello from agent",
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            result = await adapter.execute("Do something")

        assert result.exit_code == 0
        assert result.output == "Hello from agent"
        assert result.agent_id == "http://agent.example.com"
        assert result.files_changed == []
        assert isinstance(result.events, list)

    async def test_with_model_parameter_includes_metadata(self) -> None:
        """Model parameter is forwarded as metadata in params."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _completed_jsonrpc_response()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            await adapter.execute("Do something", model="gpt-4")

        call_args = mock_client.post.call_args
        sent_json = call_args[1]["json"]
        assert sent_json["params"]["metadata"] == {"model": "gpt-4"}

    async def test_raises_agent_error_on_http_error(self) -> None:
        """HTTP status >= 400 raises AgentError with BEDDEL-AGENT-720."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("Do something")

        assert exc_info.value.code == "BEDDEL-AGENT-720"

    async def test_raises_agent_error_on_jsonrpc_error(self) -> None:
        """JSON-RPC error response raises AgentError with BEDDEL-AGENT-720."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _jsonrpc_error_response()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("Do something")

        assert exc_info.value.code == "BEDDEL-AGENT-720"

    async def test_raises_agent_error_on_timeout(self) -> None:
        """Timeout raises AgentError with BEDDEL-AGENT-722."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com", timeout=5.0)
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("Do something")

        assert exc_info.value.code == "BEDDEL-AGENT-722"

    async def test_raises_agent_error_on_connection_error(self) -> None:
        """Connection error raises AgentError with BEDDEL-AGENT-720."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("Do something")

        assert exc_info.value.code == "BEDDEL-AGENT-720"

    async def test_non_completed_state_returns_exit_code_1(self) -> None:
        """Non-completed task state returns exit_code=1."""
        response_data = _completed_jsonrpc_response()
        response_data["result"]["status"]["state"] = "failed"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            result = await adapter.execute("Do something")

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# stream() tests
# ---------------------------------------------------------------------------


class TestStream:
    """Tests for A2AAgentAdapter.stream."""

    async def test_yields_status_events(self) -> None:
        """stream() yields status events from SSE stream."""
        sse_lines = [
            'data: {"status": {"state": "working", "message": {"parts": [{"text": "Processing..."}]}}}',
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines.return_value = _AsyncLineIterator(sse_lines)
        mock_response.aread = AsyncMock()

        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_cm)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            events = [ev async for ev in adapter.stream("Do something")]

        assert len(events) == 1
        assert events[0]["type"] == "status"
        assert events[0]["state"] == "working"
        assert events[0]["message"] == "Processing..."

    async def test_yields_artifact_events(self) -> None:
        """stream() yields artifact events from SSE stream."""
        sse_lines = [
            'data: {"artifact": {"parts": [{"type": "text", "text": "Result text"}]}}',
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines.return_value = _AsyncLineIterator(sse_lines)
        mock_response.aread = AsyncMock()

        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_cm)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            events = [ev async for ev in adapter.stream("Do something")]

        assert len(events) == 1
        assert events[0]["type"] == "artifact"
        assert events[0]["parts"] == ["Result text"]

    async def test_handles_mixed_status_and_artifact_events(self) -> None:
        """stream() handles mixed status and artifact events."""
        sse_lines = [
            'data: {"status": {"state": "working", "message": {"parts": [{"text": "Step 1"}]}}}',
            'data: {"artifact": {"parts": [{"type": "text", "text": "Partial result"}]}}',
            'data: {"status": {"state": "completed"}}',
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines.return_value = _AsyncLineIterator(sse_lines)
        mock_response.aread = AsyncMock()

        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_cm)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            events = [ev async for ev in adapter.stream("Do something")]

        assert len(events) == 3
        assert events[0]["type"] == "status"
        assert events[0]["state"] == "working"
        assert events[1]["type"] == "artifact"
        assert events[2]["type"] == "status"
        assert events[2]["state"] == "completed"

    async def test_raises_agent_error_on_http_error(self) -> None:
        """HTTP error in stream raises AgentError with BEDDEL-AGENT-720."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.aread = AsyncMock()

        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_cm)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                async for _ in adapter.stream("Do something"):
                    pass

        assert exc_info.value.code == "BEDDEL-AGENT-720"

    async def test_raises_agent_error_on_timeout(self) -> None:
        """Timeout in stream raises AgentError with BEDDEL-AGENT-722."""
        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(
            side_effect=httpx.TimeoutException("stream timed out"),
        )
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_cm)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                async for _ in adapter.stream("Do something"):
                    pass

        assert exc_info.value.code == "BEDDEL-AGENT-722"

    async def test_skips_non_data_sse_lines_and_empty_payloads(self) -> None:
        """stream() skips non-data SSE lines and empty data payloads."""
        sse_lines = [
            ": comment line",
            "event: ping",
            "data: ",
            "data:",
            "",
            'data: {"status": {"state": "completed"}}',
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines.return_value = _AsyncLineIterator(sse_lines)
        mock_response.aread = AsyncMock()

        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_cm)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            events = [ev async for ev in adapter.stream("Do something")]

        assert len(events) == 1
        assert events[0]["type"] == "status"
        assert events[0]["state"] == "completed"

    async def test_skips_invalid_json_in_sse_data(self) -> None:
        """stream() skips SSE data lines with invalid JSON."""
        sse_lines = [
            "data: {not valid json}",
            "data: <<<broken>>>",
            'data: {"status": {"state": "working"}}',
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines.return_value = _AsyncLineIterator(sse_lines)
        mock_response.aread = AsyncMock()

        mock_stream_cm = MagicMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_cm)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_client
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            events = [ev async for ev in adapter.stream("Do something")]

        assert len(events) == 1
        assert events[0]["type"] == "status"


# ---------------------------------------------------------------------------
# discover_agent() tests
# ---------------------------------------------------------------------------


class TestDiscoverAgent:
    """Tests for discover_agent."""

    async def test_fetches_and_parses_agent_card(self) -> None:
        """discover_agent() fetches and parses Agent Card JSON."""
        card_data = {
            "name": "Test Agent",
            "description": "A test agent",
            "skills": [],
            "capabilities": {"streaming": True},
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = card_data

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.discovery.httpx.AsyncClient", return_value=mock_client
        ):
            result = await discover_agent("http://agent.example.com")

        assert result == card_data
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "http://agent.example.com/.well-known/agent.json"

    async def test_includes_bearer_token_in_request(self) -> None:
        """discover_agent() includes Bearer token in request when provided."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Agent"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.discovery.httpx.AsyncClient", return_value=mock_client
        ):
            await discover_agent(
                "http://agent.example.com",
                auth_token="secret-token",
            )

        call_args = mock_client.get.call_args
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer secret-token"

    async def test_raises_agent_error_on_http_error(self) -> None:
        """HTTP status >= 400 raises AgentError with BEDDEL-AGENT-721."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.discovery.httpx.AsyncClient", return_value=mock_client
        ):
            with pytest.raises(AgentError) as exc_info:
                await discover_agent("http://agent.example.com")

        assert exc_info.value.code == "BEDDEL-AGENT-721"

    async def test_raises_agent_error_on_connection_error(self) -> None:
        """Connection error raises AgentError with BEDDEL-AGENT-721."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.discovery.httpx.AsyncClient", return_value=mock_client
        ):
            with pytest.raises(AgentError) as exc_info:
                await discover_agent("http://agent.example.com")

        assert exc_info.value.code == "BEDDEL-AGENT-721"

    async def test_raises_agent_error_on_invalid_json(self) -> None:
        """Invalid JSON response raises AgentError with BEDDEL-AGENT-721."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "<html>not json</html>"

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "beddel_agent_a2a.discovery.httpx.AsyncClient", return_value=mock_client
        ):
            with pytest.raises(AgentError) as exc_info:
                await discover_agent("http://agent.example.com")

        assert exc_info.value.code == "BEDDEL-AGENT-721"


# ---------------------------------------------------------------------------
# Protocol conformance test
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Tests for IAgentAdapter protocol conformance."""

    async def test_satisfies_iagent_adapter(self) -> None:
        """A2AAgentAdapter satisfies IAgentAdapter structurally."""
        adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
        assert isinstance(adapter, IAgentAdapter)
