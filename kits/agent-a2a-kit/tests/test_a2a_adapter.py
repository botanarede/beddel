"""Unit tests for A2AAgentAdapter (a2a-sdk 1.x client).

Covers constructor, headers, execute(), stream(), DataPart mode,
resource cleanup, error mapping, and IAgentAdapter protocol conformance.
Uses mocked a2a-sdk client responses.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from beddel.domain.errors import AgentError
from beddel.domain.models import AgentResult
from beddel.domain.ports import IAgentAdapter
from beddel_agent_a2a.adapter import (
    A2A_AUTH_FAILED,
    A2A_DISCOVERY_FAILED,
    A2A_TASK_FAILED,
    A2A_TIMEOUT,
    A2AAgentAdapter,
)


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
        mock_client.close = AsyncMock()

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
        mock_client.close = AsyncMock()

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
        mock_client.close = AsyncMock()

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
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com", timeout=5.0)
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("Do something")

        assert exc_info.value.code == A2A_TIMEOUT

    async def test_raises_agent_error_on_client_error(self) -> None:
        """A2AClientError raises AgentError with BEDDEL-AGENT-720."""
        from a2a.client.errors import A2AClientError

        async def _raise_error(*args: Any, **kwargs: Any) -> Any:
            raise A2AClientError("connection refused")
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_error
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("Do something")

        assert exc_info.value.code == A2A_TASK_FAILED

    async def test_raises_agent_error_on_httpx_timeout(self) -> None:
        """httpx.TimeoutException raises AgentError with BEDDEL-AGENT-722."""

        async def _raise_httpx_timeout(*args: Any, **kwargs: Any) -> Any:
            raise httpx.TimeoutException("timed out")
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_httpx_timeout
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com", timeout=5.0)
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("Do something")

        assert exc_info.value.code == A2A_TIMEOUT

    async def test_raises_agent_error_on_connection_error(self) -> None:
        """Connection error raises AgentError with BEDDEL-AGENT-720."""

        async def _raise_connection(*args: Any, **kwargs: Any) -> Any:
            raise httpx.ConnectError("connection refused")
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_connection
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("Do something")

        assert exc_info.value.code == A2A_TASK_FAILED

    async def test_client_creation_failure_raises_agent_error(self) -> None:
        """Exception during create_client raises AgentError."""
        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

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

        assert exc_info.value.code == A2A_TASK_FAILED


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
        mock_client.close = AsyncMock()

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
        mock_client.close = AsyncMock()

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
        mock_client.close = AsyncMock()

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
        mock_client.close = AsyncMock()

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

        assert exc_info.value.code == A2A_TIMEOUT

    async def test_raises_agent_error_on_client_error(self) -> None:
        """A2AClientError in stream raises AgentError with BEDDEL-AGENT-720."""
        from a2a.client.errors import A2AClientError

        async def _raise_error(*args: Any, **kwargs: Any) -> Any:
            raise A2AClientError("stream error")
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_error
        mock_client.close = AsyncMock()

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

        assert exc_info.value.code == A2A_TASK_FAILED


# ---------------------------------------------------------------------------
# create_client keyword usage tests (AC1)
# ---------------------------------------------------------------------------


class TestCreateClientKwarg:
    """Tests verifying create_client is called with agent= keyword."""

    async def test_execute_uses_agent_keyword(self) -> None:
        """execute() calls create_client(agent=url, ...)."""
        mock_responses = [_mock_stream_response_task(state=3, artifact_text="OK")]
        mock_client = AsyncMock()
        mock_client.send_message = lambda req, **kw: _async_iter(mock_responses)
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch(
                "beddel_agent_a2a.adapter.create_client", return_value=mock_client
            ) as mock_create,
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            await adapter.execute("test")

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert "agent" in call_kwargs
        assert call_kwargs["agent"] == "http://agent.example.com"

    async def test_stream_uses_agent_keyword(self) -> None:
        """stream() calls create_client(agent=url, ...)."""
        mock_responses = [_mock_stream_response_message(text="OK")]
        mock_client = AsyncMock()
        mock_client.send_message = lambda req, **kw: _async_iter(mock_responses)
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch(
                "beddel_agent_a2a.adapter.create_client", return_value=mock_client
            ) as mock_create,
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            async for _ in adapter.stream("test"):
                pass

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert "agent" in call_kwargs
        assert call_kwargs["agent"] == "http://agent.example.com"


# ---------------------------------------------------------------------------
# Resource cleanup tests (AC2)
# ---------------------------------------------------------------------------


class TestResourceCleanup:
    """Tests verifying client.close() and httpx_client.aclose() on all paths."""

    async def test_execute_closes_both_on_success(self) -> None:
        """execute() closes both client and httpx on success."""
        mock_responses = [_mock_stream_response_task(state=3, artifact_text="OK")]
        mock_client = AsyncMock()
        mock_client.send_message = lambda req, **kw: _async_iter(mock_responses)
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            await adapter.execute("test")

        mock_client.close.assert_awaited_once()
        mock_httpx.aclose.assert_awaited_once()

    async def test_execute_closes_both_on_exception(self) -> None:
        """execute() closes both client and httpx when send_message raises."""
        from a2a.client.errors import A2AClientError

        async def _raise_error(*args: Any, **kwargs: Any) -> Any:
            raise A2AClientError("boom")
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_error
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError):
                await adapter.execute("test")

        mock_client.close.assert_awaited_once()
        mock_httpx.aclose.assert_awaited_once()

    async def test_execute_closes_httpx_on_create_client_failure(self) -> None:
        """execute() closes httpx when create_client itself fails."""
        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch(
                "beddel_agent_a2a.adapter.create_client",
                side_effect=Exception("card not found"),
            ),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError):
                await adapter.execute("test")

        mock_httpx.aclose.assert_awaited_once()

    async def test_stream_closes_both_on_full_iteration(self) -> None:
        """stream() closes both client and httpx after full iteration."""
        mock_responses = [_mock_stream_response_message(text="OK")]
        mock_client = AsyncMock()
        mock_client.send_message = lambda req, **kw: _async_iter(mock_responses)
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            async for _ in adapter.stream("test"):
                pass

        mock_client.close.assert_awaited_once()
        mock_httpx.aclose.assert_awaited_once()

    async def test_stream_closes_both_on_exception(self) -> None:
        """stream() closes both client and httpx when stream raises."""
        from a2a.client.errors import A2AClientError

        async def _raise_error(*args: Any, **kwargs: Any) -> Any:
            raise A2AClientError("stream boom")
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_error
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError):
                async for _ in adapter.stream("test"):
                    pass

        mock_client.close.assert_awaited_once()
        mock_httpx.aclose.assert_awaited_once()

    async def test_stream_closes_both_on_partial_iteration(self) -> None:
        """stream() closes resources even when consumer breaks early."""
        # Produce multiple responses but only consume the first
        mock_responses = [
            _mock_stream_response_message(text="first"),
            _mock_stream_response_message(text="second"),
            _mock_stream_response_message(text="third"),
        ]
        mock_client = AsyncMock()
        mock_client.send_message = lambda req, **kw: _async_iter(mock_responses)
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            gen = adapter.stream("test")
            # Consume one item then close
            async for ev in gen:
                break
            # Explicitly close the generator to trigger GeneratorExit → finally
            await gen.aclose()

        mock_client.close.assert_awaited_once()
        mock_httpx.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# Error mapping tests (AC3)
# ---------------------------------------------------------------------------


class TestErrorMapping:
    """Tests for distinct error code mapping."""

    async def test_card_resolution_error_maps_to_discovery_failed(self) -> None:
        """AgentCardResolutionError (404) maps to BEDDEL-AGENT-721."""
        from a2a.client.errors import AgentCardResolutionError

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch(
                "beddel_agent_a2a.adapter.create_client",
                side_effect=AgentCardResolutionError("not found", status_code=404),
            ),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("test")

        assert exc_info.value.code == A2A_DISCOVERY_FAILED

    async def test_card_resolution_401_maps_to_auth_failed(self) -> None:
        """AgentCardResolutionError with status_code=401 maps to BEDDEL-AGENT-723."""
        from a2a.client.errors import AgentCardResolutionError

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch(
                "beddel_agent_a2a.adapter.create_client",
                side_effect=AgentCardResolutionError("unauthorized", status_code=401),
            ),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("test")

        assert exc_info.value.code == A2A_AUTH_FAILED

    async def test_card_resolution_403_maps_to_auth_failed(self) -> None:
        """AgentCardResolutionError with status_code=403 maps to BEDDEL-AGENT-723."""
        from a2a.client.errors import AgentCardResolutionError

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch(
                "beddel_agent_a2a.adapter.create_client",
                side_effect=AgentCardResolutionError("forbidden", status_code=403),
            ),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("test")

        assert exc_info.value.code == A2A_AUTH_FAILED

    async def test_httpx_status_error_401_maps_to_auth_failed(self) -> None:
        """httpx.HTTPStatusError with 401 maps to BEDDEL-AGENT-723."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        async def _raise_status(*args: Any, **kwargs: Any) -> Any:
            raise httpx.HTTPStatusError(
                "401 Unauthorized", request=MagicMock(), response=mock_response
            )
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_status
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("test")

        assert exc_info.value.code == A2A_AUTH_FAILED

    async def test_httpx_status_error_403_maps_to_auth_failed(self) -> None:
        """httpx.HTTPStatusError with 403 maps to BEDDEL-AGENT-723."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        async def _raise_status(*args: Any, **kwargs: Any) -> Any:
            raise httpx.HTTPStatusError(
                "403 Forbidden", request=MagicMock(), response=mock_response
            )
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_status
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("test")

        assert exc_info.value.code == A2A_AUTH_FAILED

    async def test_httpx_status_error_500_maps_to_task_failed(self) -> None:
        """httpx.HTTPStatusError with 500 maps to BEDDEL-AGENT-720."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        async def _raise_status(*args: Any, **kwargs: Any) -> Any:
            raise httpx.HTTPStatusError(
                "500 Internal Server Error", request=MagicMock(), response=mock_response
            )
            yield  # noqa: unreachable

        mock_client = AsyncMock()
        mock_client.send_message = _raise_status
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                await adapter.execute("test")

        assert exc_info.value.code == A2A_TASK_FAILED

    async def test_stream_card_resolution_error_maps_to_discovery_failed(self) -> None:
        """Stream: AgentCardResolutionError maps to BEDDEL-AGENT-721."""
        from a2a.client.errors import AgentCardResolutionError

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch(
                "beddel_agent_a2a.adapter.create_client",
                side_effect=AgentCardResolutionError("not found", status_code=404),
            ),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                async for _ in adapter.stream("test"):
                    pass

        assert exc_info.value.code == A2A_DISCOVERY_FAILED

    async def test_stream_card_resolution_401_maps_to_auth_failed(self) -> None:
        """Stream: AgentCardResolutionError 401 maps to BEDDEL-AGENT-723."""
        from a2a.client.errors import AgentCardResolutionError

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch(
                "beddel_agent_a2a.adapter.create_client",
                side_effect=AgentCardResolutionError("unauthorized", status_code=401),
            ),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            with pytest.raises(AgentError) as exc_info:
                async for _ in adapter.stream("test"):
                    pass

        assert exc_info.value.code == A2A_AUTH_FAILED


# ---------------------------------------------------------------------------
# DataPart mode tests (AC4, AC5)
# ---------------------------------------------------------------------------


class TestDataPartMode:
    """Tests for workflow-aware DataPart request mode."""

    async def test_workflow_id_produces_data_part(self) -> None:
        """When workflow_id provided, request uses Part with data field."""
        mock_responses = [_mock_stream_response_task(state=3, artifact_text="OK")]
        mock_client = AsyncMock()
        mock_client.send_message = lambda req, **kw: _async_iter(mock_responses)
        mock_client.close = AsyncMock()

        captured_request = None

        async def _capture_create_client(*, agent: str, client_config: Any) -> Any:
            return mock_client

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch(
                "beddel_agent_a2a.adapter.create_client",
                side_effect=_capture_create_client,
            ),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            # Capture the request by patching send_message
            requests_seen: list[Any] = []

            def _capture_send(req: Any, **kw: Any) -> Any:
                requests_seen.append(req)
                return _async_iter(mock_responses)

            mock_client.send_message = _capture_send
            await adapter.execute(
                "ignored prompt",
                workflow_id="my-workflow",
                inputs={"topic": "AI", "depth": "brief"},
            )

        assert len(requests_seen) == 1
        req = requests_seen[0]
        # The message should have a Part with data (not text)
        part = req.message.parts[0]
        assert part.HasField("data")
        assert not part.HasField("text") or part.text == ""
        # Verify the struct content
        data_struct = part.data.struct_value
        assert data_struct.fields["workflow_id"].string_value == "my-workflow"
        inputs_struct = data_struct.fields["inputs"].struct_value
        assert inputs_struct.fields["topic"].string_value == "AI"
        assert inputs_struct.fields["depth"].string_value == "brief"

    async def test_no_workflow_id_uses_text_part(self) -> None:
        """When no workflow_id, request uses Part with text field."""
        mock_responses = [_mock_stream_response_task(state=3, artifact_text="OK")]
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            requests_seen: list[Any] = []

            def _capture_send(req: Any, **kw: Any) -> Any:
                requests_seen.append(req)
                return _async_iter(mock_responses)

            mock_client.send_message = _capture_send
            await adapter.execute("Hello agent")

        assert len(requests_seen) == 1
        req = requests_seen[0]
        part = req.message.parts[0]
        assert part.text == "Hello agent"

    async def test_workflow_id_with_numeric_inputs(self) -> None:
        """DataPart mode handles numeric input values."""
        mock_responses = [_mock_stream_response_task(state=3, artifact_text="OK")]
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            requests_seen: list[Any] = []

            def _capture_send(req: Any, **kw: Any) -> Any:
                requests_seen.append(req)
                return _async_iter(mock_responses)

            mock_client.send_message = _capture_send
            await adapter.execute(
                "test",
                workflow_id="calc-workflow",
                inputs={"count": 5, "ratio": 0.75},
            )

        req = requests_seen[0]
        part = req.message.parts[0]
        inputs_struct = part.data.struct_value.fields["inputs"].struct_value
        assert inputs_struct.fields["count"].number_value == 5.0
        assert inputs_struct.fields["ratio"].number_value == 0.75

    async def test_workflow_id_with_bool_inputs(self) -> None:
        """DataPart mode handles boolean input values."""
        mock_responses = [_mock_stream_response_task(state=3, artifact_text="OK")]
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            requests_seen: list[Any] = []

            def _capture_send(req: Any, **kw: Any) -> Any:
                requests_seen.append(req)
                return _async_iter(mock_responses)

            mock_client.send_message = _capture_send
            await adapter.execute(
                "test",
                workflow_id="bool-workflow",
                inputs={"verbose": True, "dry_run": False},
            )

        req = requests_seen[0]
        part = req.message.parts[0]
        inputs_struct = part.data.struct_value.fields["inputs"].struct_value
        assert inputs_struct.fields["verbose"].bool_value is True
        assert inputs_struct.fields["dry_run"].bool_value is False

    async def test_stream_workflow_id_produces_data_part(self) -> None:
        """stream() with workflow_id uses DataPart."""
        mock_responses = [_mock_stream_response_message(text="OK")]
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            requests_seen: list[Any] = []

            def _capture_send(req: Any, **kw: Any) -> Any:
                requests_seen.append(req)
                return _async_iter(mock_responses)

            mock_client.send_message = _capture_send
            async for _ in adapter.stream(
                "test", workflow_id="stream-wf", inputs={"key": "val"}
            ):
                pass

        req = requests_seen[0]
        part = req.message.parts[0]
        assert part.HasField("data")
        data_struct = part.data.struct_value
        assert data_struct.fields["workflow_id"].string_value == "stream-wf"

    async def test_workflow_id_with_empty_inputs(self) -> None:
        """DataPart mode with workflow_id but no inputs still sets workflow_id."""
        mock_responses = [_mock_stream_response_task(state=3, artifact_text="OK")]
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        mock_httpx = AsyncMock()
        mock_httpx.aclose = AsyncMock()

        with (
            patch("beddel_agent_a2a.adapter.httpx.AsyncClient", return_value=mock_httpx),
            patch("beddel_agent_a2a.adapter.create_client", return_value=mock_client),
        ):
            adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
            requests_seen: list[Any] = []

            def _capture_send(req: Any, **kw: Any) -> Any:
                requests_seen.append(req)
                return _async_iter(mock_responses)

            mock_client.send_message = _capture_send
            await adapter.execute("test", workflow_id="no-inputs-wf")

        req = requests_seen[0]
        part = req.message.parts[0]
        assert part.HasField("data")
        data_struct = part.data.struct_value
        assert data_struct.fields["workflow_id"].string_value == "no-inputs-wf"


# ---------------------------------------------------------------------------
# Protocol conformance test
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Tests for IAgentAdapter protocol conformance."""

    async def test_satisfies_iagent_adapter(self) -> None:
        """A2AAgentAdapter satisfies IAgentAdapter structurally."""
        adapter = A2AAgentAdapter(agent_url="http://agent.example.com")
        assert isinstance(adapter, IAgentAdapter)
