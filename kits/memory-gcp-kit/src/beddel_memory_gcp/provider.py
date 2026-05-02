"""GCP Agent Engine Memory Bank provider implementing IMemoryProvider.

Connects to Google's Vertex AI Agent Engine Memory Bank using
Application Default Credentials (ADC).  Provides key-value get/set,
semantic search via substring matching, and episode listing scoped
by configurable scope dicts.
"""

from __future__ import annotations

import time
from typing import Any

from beddel.domain.errors import MemoryError as MemoryError  # noqa: A004
from beddel.domain.models import Episode, MemoryEntry

# Kit-local error codes (NOT in beddel/error_codes.py)
MEMORY_GCP_CONNECTION_FAILED: str = "BEDDEL-MEMORY-965"
MEMORY_GCP_WRITE_FAILED: str = "BEDDEL-MEMORY-966"
MEMORY_GCP_SEARCH_FAILED: str = "BEDDEL-MEMORY-967"

try:
    import vertexai

    _VERTEXAI_AVAILABLE = True
except ImportError:
    _VERTEXAI_AVAILABLE = False

__all__ = ["GCPMemoryProvider"]


class GCPMemoryProvider:
    """GCP Agent Engine Memory Bank adapter for episodic memory.

    Implements the :class:`~beddel.domain.ports.IMemoryProvider` protocol
    via structural subtyping (no explicit inheritance).

    Authentication uses Application Default Credentials (ADC).
    The ``vertexai.Client`` is lazily initialized on first use.

    Args:
        project: GCP project ID.
        location: GCP region (default ``"us-central1"``).
        agent_engine_name: Full resource name of the Agent Engine
            (e.g. ``"projects/.../locations/.../reasoningEngines/..."``).
        scope: Base scope dict applied to all memory operations.
            Enables agent-level or user-level scoping.
    """

    def __init__(
        self,
        project: str,
        location: str = "us-central1",
        agent_engine_name: str | None = None,
        scope: dict[str, str] | None = None,
    ) -> None:
        if not _VERTEXAI_AVAILABLE:
            raise MemoryError(
                code=MEMORY_GCP_CONNECTION_FAILED,
                message=(
                    "google-cloud-aiplatform is required for memory-gcp-kit. "
                    "Install it with: pip install google-cloud-aiplatform"
                ),
            )
        self._project = project
        self._location = location
        self._agent_engine_name = agent_engine_name
        self._base_scope: dict[str, str] = scope or {}
        self._client: vertexai.Client | None = None

    def _get_client(self) -> vertexai.Client:
        """Lazy-initialize and cache the Vertex AI client.

        Returns:
            The cached ``vertexai.Client`` instance.

        Raises:
            MemoryError: ``BEDDEL-MEMORY-965`` on initialization failure.
        """
        if self._client is not None:
            return self._client
        try:
            self._client = vertexai.Client(
                project=self._project,
                location=self._location,
            )
            return self._client
        except Exception as exc:
            raise MemoryError(
                code=MEMORY_GCP_CONNECTION_FAILED,
                message=f"Failed to initialize Vertex AI client: {exc}",
                details={"project": self._project, "location": self._location},
            ) from exc

    def _get_scope(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Merge base scope with optional extra scope keys.

        Args:
            extra: Additional scope keys to merge on top of the base scope.

        Returns:
            Merged scope dict.
        """
        if extra is None:
            return dict(self._base_scope)
        return {**self._base_scope, **extra}

    async def get(self, key: str) -> Any | None:
        """Retrieve a specific memory entry by key.

        Uses scope-based fetch with ``{"key": key}`` merged into the
        base scope.  Returns the first matching memory's fact, or
        ``None`` if no match is found.

        Args:
            key: The memory key to look up.

        Returns:
            The stored value, or ``None`` if the key does not exist.

        Raises:
            MemoryError: ``BEDDEL-MEMORY-965`` on connection errors.
        """
        try:
            client = self._get_client()
            scope = self._get_scope({"key": key})
            memories = list(
                client.agent_engines.memories.retrieve(
                    name=self._agent_engine_name,
                    scope=scope,
                )
            )
            if not memories:
                return None
            return memories[0].memory.fact
        except MemoryError:
            raise
        except Exception as exc:
            raise MemoryError(
                code=MEMORY_GCP_CONNECTION_FAILED,
                message=f"Failed to get memory key {key!r}: {exc}",
                details={"key": key},
            ) from exc

    async def set(self, key: str, value: Any) -> None:
        """Persist a memory to Agent Engine Memory Bank.

        Creates a memory entry with the given key and value using
        ``memories.create()`` with upsert semantics.

        Args:
            key: The memory key.
            value: The value to store (converted to ``str``).

        Raises:
            MemoryError: ``BEDDEL-MEMORY-966`` on write failure.
        """
        try:
            client = self._get_client()
            scope = self._get_scope({"key": key})
            client.agent_engines.memories.create(
                name=self._agent_engine_name,
                fact=str(value),
                scope=scope,
            )
        except MemoryError:
            raise
        except Exception as exc:
            raise MemoryError(
                code=MEMORY_GCP_WRITE_FAILED,
                message=f"Failed to set memory key {key!r}: {exc}",
                details={"key": key},
            ) from exc

    async def search(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        """Search stored memories using scope-based retrieval with client-side filtering.

        Retrieves all memories by base scope, then performs client-side
        relevance filtering using substring matching.  Results are ranked
        by score and capped at ``top_k``.

        Scoring:
        - query found in fact → score = 1.0
        - query found in scope values → score = 0.8

        Args:
            query: The search query string.
            top_k: Maximum number of results to return.

        Returns:
            List of :class:`~beddel.domain.models.MemoryEntry` ranked
            by relevance score.

        Raises:
            MemoryError: ``BEDDEL-MEMORY-967`` on search failure.
        """
        try:
            client = self._get_client()
            scope = self._get_scope()
            memories = list(
                client.agent_engines.memories.retrieve(
                    name=self._agent_engine_name,
                    scope=scope,
                )
            )

            results: list[MemoryEntry] = []
            query_lower = query.lower()

            for mem in memories:
                fact = mem.memory.fact
                mem_scope = getattr(mem.memory, "scope", {}) or {}
                mem_key = mem_scope.get("key", mem.memory.name)

                in_fact = query_lower in str(fact).lower()
                in_scope = any(
                    query_lower in str(v).lower() for v in mem_scope.values()
                )

                if in_fact or in_scope:
                    score = 1.0 if in_fact else 0.8
                    results.append(
                        MemoryEntry(
                            key=mem_key,
                            value=fact,
                            score=score,
                            metadata={"scope": dict(mem_scope)},
                        )
                    )

            results.sort(key=lambda e: e.score, reverse=True)
            return results[:top_k]
        except MemoryError:
            raise
        except Exception as exc:
            raise MemoryError(
                code=MEMORY_GCP_SEARCH_FAILED,
                message=f"Failed to search memory for {query!r}: {exc}",
                details={"query": query, "top_k": top_k},
            ) from exc

    async def list_episodes(self, workflow_id: str) -> list[Episode]:
        """List recorded episodes for a workflow.

        Retrieves memories scoped to ``{"workflow_id": workflow_id}``
        and maps them to :class:`~beddel.domain.models.Episode` objects.

        Args:
            workflow_id: Identifier of the workflow to list episodes for.

        Returns:
            List of :class:`~beddel.domain.models.Episode` instances.

        Raises:
            MemoryError: ``BEDDEL-MEMORY-965`` on failure.
        """
        try:
            client = self._get_client()
            scope = self._get_scope({"workflow_id": workflow_id})
            memories = list(
                client.agent_engines.memories.retrieve(
                    name=self._agent_engine_name,
                    scope=scope,
                )
            )

            episodes: list[Episode] = []
            for mem in memories:
                mem_scope = getattr(mem.memory, "scope", {}) or {}
                episodes.append(
                    Episode(
                        workflow_id=workflow_id,
                        episode_id=mem.memory.name,
                        inputs={"fact": mem.memory.fact},
                        outputs={},
                        duration_ms=0.0,
                        created_at=time.time(),
                        metadata={"scope": dict(mem_scope)},
                    )
                )
            return episodes
        except MemoryError:
            raise
        except Exception as exc:
            raise MemoryError(
                code=MEMORY_GCP_CONNECTION_FAILED,
                message=f"Failed to list episodes for {workflow_id!r}: {exc}",
                details={"workflow_id": workflow_id},
            ) from exc
