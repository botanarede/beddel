"""Tests for GCPMemoryProvider.

All GCP Vertex AI interactions are mocked — no real GCP connections.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from beddel.domain.errors import MemoryError as BeddelMemoryError
from beddel.domain.models import Episode, MemoryEntry
from beddel_memory_gcp.provider import (
    MEMORY_GCP_CONNECTION_FAILED,
    MEMORY_GCP_SEARCH_FAILED,
    MEMORY_GCP_WRITE_FAILED,
    GCPMemoryProvider,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_memory_result(
    fact: str = "some fact",
    name: str = "projects/p/locations/l/memories/123",
    scope: dict[str, str] | None = None,
) -> SimpleNamespace:
    """Create a mock memory result matching the Vertex AI SDK shape.

    Each item returned by ``memories.retrieve()`` has a nested
    ``memory`` attribute with ``fact``, ``name``, and ``scope``.
    """
    return SimpleNamespace(
        memory=SimpleNamespace(
            fact=fact,
            name=name,
            scope=scope or {},
        ),
    )


def _make_mock_client(
    retrieve_result: list[Any] | None = None,
    retrieve_side_effect: Exception | None = None,
    create_side_effect: Exception | None = None,
) -> MagicMock:
    """Create a mock ``vertexai.Client`` with chained attribute access.

    Mocks ``client.agent_engines.memories.retrieve`` and
    ``client.agent_engines.memories.create``.
    """
    client = MagicMock()
    memories = client.agent_engines.memories

    if retrieve_side_effect is not None:
        memories.retrieve.side_effect = retrieve_side_effect
    else:
        memories.retrieve.return_value = retrieve_result or []

    if create_side_effect is not None:
        memories.create.side_effect = create_side_effect

    return client


def _patch_vertexai_client(client: MagicMock) -> Any:
    """Patch ``vertexai.Client`` to return a pre-built mock."""
    return patch(
        "beddel_memory_gcp.provider.vertexai.Client",
        return_value=client,
    )


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    """Verify GCPMemoryProvider constructor stores config correctly."""

    def test_constructor_accepts_required_params(self) -> None:
        """Constructor stores project and defaults."""
        provider = GCPMemoryProvider(project="my-project")

        assert provider._project == "my-project"
        assert provider._location == "us-central1"
        assert provider._agent_engine_name is None
        assert provider._base_scope == {}
        assert provider._client is None

    def test_constructor_accepts_all_optional_params(self) -> None:
        """Constructor stores project, location, agent_engine_name, scope."""
        scope = {"user_id": "u-123"}
        provider = GCPMemoryProvider(
            project="proj",
            location="europe-west1",
            agent_engine_name="projects/p/locations/l/reasoningEngines/re-1",
            scope=scope,
        )

        assert provider._project == "proj"
        assert provider._location == "europe-west1"
        assert provider._agent_engine_name == (
            "projects/p/locations/l/reasoningEngines/re-1"
        )
        assert provider._base_scope == {"user_id": "u-123"}


# ---------------------------------------------------------------------------
# _get_client
# ---------------------------------------------------------------------------


class TestGetClient:
    """Verify _get_client creates and caches the Vertex AI client."""

    def test_get_client_creates_vertexai_client(self) -> None:
        """_get_client creates vertexai.Client with correct project/location."""
        mock_client = MagicMock()
        with patch(
            "beddel_memory_gcp.provider.vertexai.Client",
            return_value=mock_client,
        ) as mock_cls:
            provider = GCPMemoryProvider(
                project="test-proj",
                location="asia-east1",
            )
            result = provider._get_client()

            mock_cls.assert_called_once_with(
                project="test-proj",
                location="asia-east1",
            )
            assert result is mock_client

    def test_get_client_caches_instance(self) -> None:
        """_get_client returns the same cached client on subsequent calls."""
        mock_client = MagicMock()
        with patch(
            "beddel_memory_gcp.provider.vertexai.Client",
            return_value=mock_client,
        ) as mock_cls:
            provider = GCPMemoryProvider(project="proj")
            first = provider._get_client()
            second = provider._get_client()

            assert first is second
            mock_cls.assert_called_once()  # Only created once


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


class TestGet:
    """Verify get() retrieves memory entries by key."""

    async def test_get_returns_value_when_found(self) -> None:
        """get() returns the fact from the first matching memory."""
        mem = _make_memory_result(fact="hello world", scope={"key": "greet"})
        mock_client = _make_mock_client(retrieve_result=[mem])

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(
                project="proj",
                agent_engine_name="projects/p/locations/l/re/1",
            )
            result = await provider.get("greet")

        assert result == "hello world"
        mock_client.agent_engines.memories.retrieve.assert_called_once_with(
            name="projects/p/locations/l/re/1",
            scope={"key": "greet"},
        )

    async def test_get_returns_none_when_not_found(self) -> None:
        """get() returns None when no memories match the key."""
        mock_client = _make_mock_client(retrieve_result=[])

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(project="proj")
            result = await provider.get("missing-key")

        assert result is None

    async def test_get_merges_base_scope(self) -> None:
        """get() merges base scope with the key scope."""
        mock_client = _make_mock_client(retrieve_result=[])

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(
                project="proj",
                scope={"user_id": "u-1"},
            )
            await provider.get("my-key")

        mock_client.agent_engines.memories.retrieve.assert_called_once_with(
            name=None,
            scope={"user_id": "u-1", "key": "my-key"},
        )


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------


class TestSet:
    """Verify set() persists memory entries."""

    async def test_set_calls_create_with_correct_args(self) -> None:
        """set() calls memories.create with fact and scope."""
        mock_client = _make_mock_client()

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(
                project="proj",
                agent_engine_name="projects/p/locations/l/re/1",
            )
            await provider.set("color", "blue")

        mock_client.agent_engines.memories.create.assert_called_once_with(
            name="projects/p/locations/l/re/1",
            fact="blue",
            scope={"key": "color"},
        )

    async def test_set_converts_value_to_string(self) -> None:
        """set() converts non-string values to str."""
        mock_client = _make_mock_client()

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(project="proj")
            await provider.set("count", 42)

        mock_client.agent_engines.memories.create.assert_called_once_with(
            name=None,
            fact="42",
            scope={"key": "count"},
        )

    async def test_set_merges_base_scope(self) -> None:
        """set() merges base scope with the key scope."""
        mock_client = _make_mock_client()

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(
                project="proj",
                scope={"agent_id": "a-1"},
            )
            await provider.set("status", "active")

        mock_client.agent_engines.memories.create.assert_called_once_with(
            name=None,
            fact="active",
            scope={"agent_id": "a-1", "key": "status"},
        )


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    """Verify search() returns filtered MemoryEntry results."""

    async def test_search_returns_matching_entries(self) -> None:
        """search() returns MemoryEntry list for matching facts."""
        memories = [
            _make_memory_result(
                fact="Python is great",
                name="mem-1",
                scope={"key": "lang"},
            ),
            _make_memory_result(
                fact="Java is verbose",
                name="mem-2",
                scope={"key": "lang2"},
            ),
        ]
        mock_client = _make_mock_client(retrieve_result=memories)

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(project="proj")
            results = await provider.search("python")

        assert len(results) == 1
        assert isinstance(results[0], MemoryEntry)
        assert results[0].key == "lang"
        assert results[0].value == "Python is great"
        assert results[0].score == 1.0

    async def test_search_caps_at_top_k(self) -> None:
        """search() returns at most top_k results."""
        memories = [
            _make_memory_result(
                fact=f"fact about topic {i}",
                name=f"mem-{i}",
                scope={"key": f"k-{i}"},
            )
            for i in range(10)
        ]
        mock_client = _make_mock_client(retrieve_result=memories)

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(project="proj")
            results = await provider.search("topic", top_k=3)

        assert len(results) == 3

    async def test_search_scores_scope_match_lower(self) -> None:
        """search() scores scope-only matches at 0.8 (below fact matches)."""
        memories = [
            _make_memory_result(
                fact="unrelated fact",
                name="mem-1",
                scope={"key": "python-config"},
            ),
        ]
        mock_client = _make_mock_client(retrieve_result=memories)

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(project="proj")
            results = await provider.search("python")

        assert len(results) == 1
        assert results[0].score == 0.8

    async def test_search_returns_empty_for_no_match(self) -> None:
        """search() returns empty list when nothing matches."""
        memories = [
            _make_memory_result(fact="unrelated", scope={"key": "other"}),
        ]
        mock_client = _make_mock_client(retrieve_result=memories)

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(project="proj")
            results = await provider.search("nonexistent")

        assert results == []


# ---------------------------------------------------------------------------
# list_episodes
# ---------------------------------------------------------------------------


class TestListEpisodes:
    """Verify list_episodes() returns Episode objects."""

    async def test_list_episodes_returns_episode_list(self) -> None:
        """list_episodes() maps memory results to Episode objects."""
        memories = [
            _make_memory_result(
                fact="step 1 completed",
                name="ep-001",
                scope={"workflow_id": "wf-1"},
            ),
            _make_memory_result(
                fact="step 2 completed",
                name="ep-002",
                scope={"workflow_id": "wf-1"},
            ),
        ]
        mock_client = _make_mock_client(retrieve_result=memories)

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(project="proj")
            episodes = await provider.list_episodes("wf-1")

        assert len(episodes) == 2
        assert all(isinstance(ep, Episode) for ep in episodes)
        assert episodes[0].workflow_id == "wf-1"
        assert episodes[0].episode_id == "ep-001"
        assert episodes[0].inputs == {"fact": "step 1 completed"}
        assert episodes[1].episode_id == "ep-002"

    async def test_list_episodes_passes_workflow_scope(self) -> None:
        """list_episodes() merges workflow_id into scope."""
        mock_client = _make_mock_client(retrieve_result=[])

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(
                project="proj",
                scope={"agent_id": "a-1"},
            )
            await provider.list_episodes("wf-42")

        mock_client.agent_engines.memories.retrieve.assert_called_once_with(
            name=None,
            scope={"agent_id": "a-1", "workflow_id": "wf-42"},
        )

    async def test_list_episodes_returns_empty_for_no_memories(self) -> None:
        """list_episodes() returns empty list when no memories exist."""
        mock_client = _make_mock_client(retrieve_result=[])

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(project="proj")
            episodes = await provider.list_episodes("wf-empty")

        assert episodes == []


# ---------------------------------------------------------------------------
# Scope configuration
# ---------------------------------------------------------------------------


class TestScopeConfiguration:
    """Verify agent-level vs user-level scope configuration."""

    async def test_agent_level_scope(self) -> None:
        """Agent-level scope applies agent_id to all operations."""
        mock_client = _make_mock_client(retrieve_result=[])

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(
                project="proj",
                scope={"agent_id": "agent-007"},
            )
            await provider.get("key1")

        mock_client.agent_engines.memories.retrieve.assert_called_once_with(
            name=None,
            scope={"agent_id": "agent-007", "key": "key1"},
        )

    async def test_user_level_scope(self) -> None:
        """User-level scope applies user_id to all operations."""
        mock_client = _make_mock_client(retrieve_result=[])

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(
                project="proj",
                scope={"user_id": "user-42", "session_id": "sess-1"},
            )
            await provider.get("pref")

        mock_client.agent_engines.memories.retrieve.assert_called_once_with(
            name=None,
            scope={"user_id": "user-42", "session_id": "sess-1", "key": "pref"},
        )


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestConnectionFailure:
    """Verify connection failure raises MemoryError(BEDDEL-MEMORY-965)."""

    def test_get_client_raises_on_init_failure(self) -> None:
        """_get_client raises MemoryError(965) when Client() fails."""
        with patch(
            "beddel_memory_gcp.provider.vertexai.Client",
            side_effect=RuntimeError("ADC not configured"),
        ):
            provider = GCPMemoryProvider(project="proj")

            with pytest.raises(BeddelMemoryError) as exc_info:
                provider._get_client()

            assert exc_info.value.code == MEMORY_GCP_CONNECTION_FAILED

    async def test_get_raises_on_retrieve_failure(self) -> None:
        """get() raises MemoryError(965) on unexpected retrieve error."""
        mock_client = _make_mock_client(
            retrieve_side_effect=OSError("Network unreachable"),
        )

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(project="proj")

            with pytest.raises(BeddelMemoryError) as exc_info:
                await provider.get("key")

            assert exc_info.value.code == MEMORY_GCP_CONNECTION_FAILED


class TestWriteFailure:
    """Verify write failure raises MemoryError(BEDDEL-MEMORY-966)."""

    async def test_set_raises_on_create_failure(self) -> None:
        """set() raises MemoryError(966) when memories.create fails."""
        mock_client = _make_mock_client(
            create_side_effect=RuntimeError("Quota exceeded"),
        )

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(project="proj")

            with pytest.raises(BeddelMemoryError) as exc_info:
                await provider.set("key", "value")

            assert exc_info.value.code == MEMORY_GCP_WRITE_FAILED


class TestSearchFailure:
    """Verify search failure raises MemoryError(BEDDEL-MEMORY-967)."""

    async def test_search_raises_on_retrieve_failure(self) -> None:
        """search() raises MemoryError(967) when retrieve fails."""
        mock_client = _make_mock_client(
            retrieve_side_effect=RuntimeError("Service unavailable"),
        )

        with _patch_vertexai_client(mock_client):
            provider = GCPMemoryProvider(project="proj")

            with pytest.raises(BeddelMemoryError) as exc_info:
                await provider.search("query")

            assert exc_info.value.code == MEMORY_GCP_SEARCH_FAILED


# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------


class TestImportGuard:
    """Verify import guard raises MemoryError when vertexai not installed."""

    def test_raises_when_vertexai_not_available(self) -> None:
        """Constructor raises MemoryError when _VERTEXAI_AVAILABLE is False."""
        with patch(
            "beddel_memory_gcp.provider._VERTEXAI_AVAILABLE",
            False,
        ):
            with pytest.raises(BeddelMemoryError) as exc_info:
                GCPMemoryProvider(project="proj")

            assert exc_info.value.code == MEMORY_GCP_CONNECTION_FAILED
            assert "google-cloud-aiplatform" in exc_info.value.message


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Verify GCPMemoryProvider satisfies IMemoryProvider structurally."""

    def test_has_all_required_methods(self) -> None:
        """GCPMemoryProvider has all IMemoryProvider methods."""
        from beddel.domain.ports import IMemoryProvider  # noqa: F401

        for method_name in ("get", "set", "search", "list_episodes"):
            assert hasattr(GCPMemoryProvider, method_name), (
                f"GCPMemoryProvider missing {method_name}"
            )

    def test_methods_are_callable(self) -> None:
        """All protocol methods are callable on an instance."""
        provider = GCPMemoryProvider(project="proj")

        for method_name in ("get", "set", "search", "list_episodes"):
            assert callable(getattr(provider, method_name))
