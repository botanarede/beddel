"""Unit tests for discover_agent (a2a-sdk 1.x).

Covers Agent Card resolution with primary/fallback path logic,
typed AgentCard response, schema validation, and error handling.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from a2a.client.errors import AgentCardResolutionError
from a2a.types import AgentCard

from beddel.domain.errors import AgentError
from beddel_agent_a2a.discovery import discover_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_agent_card() -> MagicMock:
    """Build a mock AgentCard proto object."""
    card = MagicMock(spec=AgentCard)
    card.name = "Test Agent"
    card.description = "A test agent"
    card.version = "1.0.0"
    card.skills = []
    return card


# ---------------------------------------------------------------------------
# Primary path success
# ---------------------------------------------------------------------------


class TestDiscoverAgentPrimaryPath:
    """Tests for discover_agent with primary path resolution."""

    async def test_fetches_card_from_primary_path(self) -> None:
        """discover_agent() returns typed AgentCard from primary path."""
        mock_card = _mock_agent_card()

        mock_resolver_instance = AsyncMock()
        mock_resolver_instance.get_agent_card = AsyncMock(return_value=mock_card)

        with patch(
            "beddel_agent_a2a.discovery.A2ACardResolver",
            return_value=mock_resolver_instance,
        ) as mock_resolver_cls:
            result = await discover_agent("http://agent.example.com")

        assert result is mock_card
        assert result.name == "Test Agent"
        # Verify resolver was created with primary path
        call_args = mock_resolver_cls.call_args
        assert ".well-known/agent-card.json" in call_args[1]["agent_card_path"]

    async def test_strips_trailing_slash_from_url(self) -> None:
        """URL trailing slash is stripped before resolving."""
        mock_card = _mock_agent_card()

        mock_resolver_instance = AsyncMock()
        mock_resolver_instance.get_agent_card = AsyncMock(return_value=mock_card)

        with patch(
            "beddel_agent_a2a.discovery.A2ACardResolver",
            return_value=mock_resolver_instance,
        ) as mock_resolver_cls:
            await discover_agent("http://agent.example.com/")

        call_args = mock_resolver_cls.call_args
        assert call_args[1]["base_url"] == "http://agent.example.com"

    async def test_includes_bearer_token_in_http_kwargs(self) -> None:
        """Bearer token is passed to resolver via http_kwargs."""
        mock_card = _mock_agent_card()

        mock_resolver_instance = AsyncMock()
        mock_resolver_instance.get_agent_card = AsyncMock(return_value=mock_card)

        with patch(
            "beddel_agent_a2a.discovery.A2ACardResolver",
            return_value=mock_resolver_instance,
        ):
            await discover_agent(
                "http://agent.example.com",
                auth_token="secret-token",
            )

        # Verify http_kwargs were passed to get_agent_card
        get_card_call = mock_resolver_instance.get_agent_card.call_args
        http_kwargs = get_card_call[1]["http_kwargs"]
        assert http_kwargs["headers"]["Authorization"] == "Bearer secret-token"


# ---------------------------------------------------------------------------
# Fallback path
# ---------------------------------------------------------------------------


class TestDiscoverAgentFallback:
    """Tests for discover_agent with fallback to legacy path."""

    async def test_falls_back_to_legacy_path_on_primary_failure(self) -> None:
        """Falls back to /.well-known/agent.json when primary fails."""
        mock_card = _mock_agent_card()

        # Track which resolver instance is which
        call_count = {"n": 0}
        resolvers: list[AsyncMock] = []

        def _create_resolver(**kwargs: Any) -> AsyncMock:
            resolver = AsyncMock()
            call_count["n"] += 1
            if call_count["n"] == 1:
                # Primary path fails
                resolver.get_agent_card = AsyncMock(
                    side_effect=AgentCardResolutionError("404")
                )
            else:
                # Legacy path succeeds
                resolver.get_agent_card = AsyncMock(return_value=mock_card)
            resolvers.append(resolver)
            return resolver

        with patch(
            "beddel_agent_a2a.discovery.A2ACardResolver",
            side_effect=_create_resolver,
        ) as mock_resolver_cls:
            result = await discover_agent("http://agent.example.com")

        assert result is mock_card
        # Verify both resolvers were created
        assert mock_resolver_cls.call_count == 2
        # First call has primary path
        first_call = mock_resolver_cls.call_args_list[0]
        assert "agent-card.json" in first_call[1]["agent_card_path"]
        # Second call has legacy path
        second_call = mock_resolver_cls.call_args_list[1]
        assert "agent.json" in second_call[1]["agent_card_path"]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestDiscoverAgentErrors:
    """Tests for discover_agent error scenarios."""

    async def test_raises_agent_error_when_both_paths_fail(self) -> None:
        """AgentError raised when both primary and fallback paths fail."""
        mock_resolver_instance = AsyncMock()
        mock_resolver_instance.get_agent_card = AsyncMock(
            side_effect=AgentCardResolutionError("not found")
        )

        with patch(
            "beddel_agent_a2a.discovery.A2ACardResolver",
            return_value=mock_resolver_instance,
        ):
            with pytest.raises(AgentError) as exc_info:
                await discover_agent("http://agent.example.com")

        assert exc_info.value.code == "BEDDEL-AGENT-721"
        assert "Failed to fetch Agent Card" in exc_info.value.message

    async def test_raises_agent_error_on_httpx_error(self) -> None:
        """httpx.HTTPError raises AgentError with BEDDEL-AGENT-721."""

        def _create_resolver(**kwargs: Any) -> AsyncMock:
            resolver = AsyncMock()
            # Primary fails with card resolution error
            # Fallback fails with httpx error
            resolver.get_agent_card = AsyncMock(
                side_effect=AgentCardResolutionError("network error")
            )
            return resolver

        calls = {"n": 0}

        def _create_resolver_with_httpx_fallback(**kwargs: Any) -> AsyncMock:
            calls["n"] += 1
            resolver = AsyncMock()
            if calls["n"] == 1:
                resolver.get_agent_card = AsyncMock(
                    side_effect=AgentCardResolutionError("404")
                )
            else:
                resolver.get_agent_card = AsyncMock(
                    side_effect=httpx.ConnectError("connection refused")
                )
            return resolver

        with patch(
            "beddel_agent_a2a.discovery.A2ACardResolver",
            side_effect=_create_resolver_with_httpx_fallback,
        ):
            with pytest.raises(AgentError) as exc_info:
                await discover_agent("http://agent.example.com")

        assert exc_info.value.code == "BEDDEL-AGENT-721"

    async def test_returns_typed_agent_card_not_dict(self) -> None:
        """Verify return type is AgentCard, not raw dict."""
        mock_card = _mock_agent_card()

        mock_resolver_instance = AsyncMock()
        mock_resolver_instance.get_agent_card = AsyncMock(return_value=mock_card)

        with patch(
            "beddel_agent_a2a.discovery.A2ACardResolver",
            return_value=mock_resolver_instance,
        ):
            result = await discover_agent("http://agent.example.com")

        # Should be AgentCard (or mock of it), not a dict
        assert not isinstance(result, dict)
        assert hasattr(result, "name")
        assert hasattr(result, "description")
