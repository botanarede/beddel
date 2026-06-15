"""Unit tests for A2AAgentAdapter (a2a-sdk 1.x client).

Covers constructor, headers, execute(), stream(), and IAgentAdapter
protocol conformance.  Uses mocked a2a-sdk client responses.
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


# ---------------------------------------------------------------------------
# Helpers — build mock StreamResponse objects
# ---------------------------------------------------------------------------


def _mock_stream_response_task(
    state: int = 3,  # TASK_STATE_COMPLETED
    artifact_text: str = "Hello from agent",
) -> MagicMock:
    """Build a mock StreamResponse with a task payload."""
    # Build artifact part
    part = MagicMock()
    part.text = artifact_text

    artifact = MagicMock()
    artifact.parts = [part]

    # Build task status
    status = MagicMock()
    status.state = state

    # Build task
    task = MagicMock()
    task.status = status
    task.artifacts = [artifact]
    task.history = []

    # Build StreamResponse
    response = MagicMock()
    response.HasField = lambda field: field == "task"
    response.task = task
    return response


def _mock_stream_response_message(text: str = "Agent reply") -> MagicMock:
    """Build a mock StreamResponse with a message payload."""
    part = MagicMock()
    part.text = text

    msg = MagicMock()
    msg.parts = [part]

    response = MagicMock()
    response.HasField = lambda field: field == "message"
    response.message = msg
    return response


def _mock_stream_response_status_update(
    state: int = 2,  # TASK_STATE_WORKING
    message_text: str = "Processing...",
) -> MagicMock:
    """Build a mock StreamResponse with a status_update payload."""
    # Build status message parts
    msg_part = MagicMock()
    msg_part.text = message_text

    status_message = MagicMock()
    status_message.parts = [msg_part]

    status = MagicMock()
    status.state = state
    status.HasField = lambda field: field == "message"
    status.message = status_message

    status_update = MagicMock()
    status_update.status = status

    response = MagicMock()
    response.HasField = lambda field: field == "status_update"
    response.status_update = status_update
    return response


def _mock_stream_response_artifact_update(
    text: str = "Artifact content",
) -> MagicMock:
    """Build a mock StreamResponse with an artifact_update payload."""
    part = MagicMock()
    part.text = text

    artifact = MagicMock()
    artifact.parts = [part]

    artifact_update = MagicMock()
    artifact_update.artifact = artifact

    response = MagicMock()
    response.HasField = lambda field: field == "artifact_update"
    response.artifact_update = artifact_update
    return response


async def _async_iter(items: list[Any]) -> Any:
    """Convert a list to an async iterator."""
    for item in items:
        yield item


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
# execute() tests
# ---------------------------------------------------------------------------


class TestExecute:
    """Tests for A2AAgentAdapter.execute."""

    async def test_completed_task_returns_agent_result(self) -> None:
        """Completed task maps to exit_code=0, output from artifacts."""
        mock_responses = [_mock_stream_response_task(state=3, artifact_text="Hello")]
        mock_client = AsyncMock()
        mock_client.send_message = lambda req, **kw: _async_iter(mock_responses)

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            result = await adapter.execute("Do something")

        assert isinstance(result, AgentResult)
        assert result.exit_code == 0
        assert result.output == "Hello"
        assert result.agent_id == "http://agent.example.com"
        assert result.files_changed == []

    async def test_message_response_returns_agent_result(self) -> None:
        """Message-style response maps to exit_code=0."""
        mock_responses = [_mock_stream_response_message(text="Agent reply")]
        mock_client = AsyncMock()
        mock_client.send_message = lambda req, **kw: _async_iter(mock_responses)

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            result = await adapter.execute("Do something")

        assert result.exit_code == 0
        assert result.output == "Agent reply"

    async def test_failed_task_returns_exit_code_1(self) -> None:
        """Failed task state returns exit_code=1."""
        mock_responses = [_mock_stream_response_task(state=4, artifact_text="Error")]
        mock_client = AsyncMock()
        mock_client.send_message = lambda req, **kw: _async_iter(mock_responses)

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            result = await adapter.execute("Do something")

        assert result.exit_code == 1

    async def test_raises_agent_error_on_timeout(self) -> None:
        """Timeout raises AgentError with BEDDEL-AGENT-722."""
        from a2a.client.errors import A2AClientTimeoutError

        async def _raise_timeout(*args: Any, **kwargs: Any) -> Any:
            raise A2AClientTimeoutError("timed out")
            yield  # noqa: unreachable — makes this an async generator

        mock_client = AsyncMock()
        mock_client.send_message = _raise_timeout

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com", timeout=5.0)
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("Do something")

        assert exc_info.value.code == "BEDDEL-AGENT-722"

    async def test_raises_agent_error_on_client_error(self) -> None:
        """A2AClientError raises AgentError with BEDDEL-AGENT-720."""
        from a2a.client.errors import A2AClientError

        async def _raise_error(*args: Any, **kwargs: Any) -> Any:
            raise A2AClientError("connection refused")
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_error

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("Do something")

        assert exc_info.value.code == "BEDDEL-AGENT-720"

    async def test_raises_agent_error_on_httpx_timeout(self) -> None:
        """httpx.TimeoutException raises AgentError with BEDDEL-AGENT-722."""

        async def _raise_httpx_timeout(*args: Any, **kwargs: Any) -> Any:
            raise httpx.TimeoutException("timed out")
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_httpx_timeout

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com", timeout=5.0)
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("Do something")

        assert exc_info.value.code == "BEDDEL-AGENT-722"

    async def test_raises_agent_error_on_connection_error(self) -> None:
        """Connection error raises AgentError with BEDDEL-AGENT-720."""

        async def _raise_connection(*args: Any, **kwargs: Any) -> Any:
            raise httpx.ConnectError("connection refused")
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_connection

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("Do something")

        assert exc_info.value.code == "BEDDEL-AGENT-720"

    async def test_client_creation_failure_raises_agent_error(self) -> None:
        """Exception during create_client raises AgentError."""
        mock_httpx = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch(
                "beddel_agent_a2a.adapter.create_client",
                side_effect=Exception("card not found"),
            ),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("Do something")

        assert exc_info.value.code == "BEDDEL-AGENT-720"


# ---------------------------------------------------------------------------
# stream() tests
# ---------------------------------------------------------------------------


class TestStream:
    """Tests for A2AAgentAdapter.stream."""

    async def test_yields_status_events(self) -> None:
        """stream() yields status events from status_update responses."""
        mock_responses = [
            _mock_stream_response_status_update(state=3, message_text="Processing...")
        ]
        mock_client = AsyncMock()
        mock_client.send_message = lambda req, **kw: _async_iter(mock_responses)

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
            patch("beddel_agent_a2a.adapter.TaskState") as mock_task_state,
        ):
            mock_task_state.Name = lambda v: "TASK_STATE_WORKING"
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            events = [ev async for ev in adapter.stream("Do something")]

        assert len(events) == 1
        assert events[0]["type"] == "status"
        assert events[0]["state"] == "working"
        assert events[0]["message"] == "Processing..."

    async def test_yields_artifact_events(self) -> None:
        """stream() yields artifact events from artifact_update responses."""
        mock_responses = [_mock_stream_response_artifact_update(text="Result text")]
        mock_client = AsyncMock()
        mock_client.send_message = lambda req, **kw: _async_iter(mock_responses)

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            events = [ev async for ev in adapter.stream("Do something")]

        assert len(events) == 1
        assert events[0]["type"] == "artifact"
        assert events[0]["parts"] == ["Result text"]

    async def test_yields_message_events(self) -> None:
        """stream() yields message events from message responses."""
        mock_responses = [_mock_stream_response_message(text="Agent says hello")]
        mock_client = AsyncMock()
        mock_client.send_message = lambda req, **kw: _async_iter(mock_responses)

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            events = [ev async for ev in adapter.stream("Do something")]

        assert len(events) == 1
        assert events[0]["type"] == "message"
        assert events[0]["text"] == "Agent says hello"

    async def test_raises_agent_error_on_timeout(self) -> None:
        """Timeout in stream raises AgentError with BEDDEL-AGENT-722."""
        from a2a.client.errors import A2AClientTimeoutError

        async def _raise_timeout(*args: Any, **kwargs: Any) -> Any:
            raise A2AClientTimeoutError("stream timed out")
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_timeout

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                async for _ in adapter.stream("Do something"):
                    pass

        assert exc_info.value.code == "BEDDEL-AGENT-722"

    async def test_raises_agent_error_on_client_error(self) -> None:
        """A2AClientError in stream raises AgentError with BEDDEL-AGENT-720."""
        from a2a.client.errors import A2AClientError

        async def _raise_error(*args: Any, **kwargs: Any) -> Any:
            raise A2AClientError("stream error")
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_error

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                async for _ in adapter.stream("Do something"):
                    pass

        assert exc_info.value.code == "BEDDEL-AGENT-720"


# ---------------------------------------------------------------------------
# Protocol conformance test
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Tests for IAgentAdapter protocol conformance."""

    async def test_satisfies_iagent_adapter(self) -> None:
        """A2AAgentAdapter satisfies IAgentAdapter structurally."""
        adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
        assert isinstance(adapter, IAgentAdapter)
