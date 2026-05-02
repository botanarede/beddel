"""A2A Protocol agent adapter — JSON-RPC 2.0 over HTTP(S).

This adapter bridges the Beddel domain core to any
`A2A Protocol <https://google.github.io/A2A/>`_ compliant agent,
enabling agent-style interactions through the standard ``tasks/send``
and ``tasks/sendSubscribe`` JSON-RPC methods.  It implements the
:class:`~beddel.domain.ports.IAgentAdapter` protocol via structural
subtyping (no explicit inheritance).

Communication uses ``httpx`` for async HTTP requests and SSE streaming.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from beddel.domain.errors import AgentError
from beddel.domain.models import AgentResult

try:
    import httpx
except ImportError as exc:
    raise ImportError(
        "httpx is required for agent-a2a-kit. Install with: pip install httpx"
    ) from exc

__all__ = ["A2AAgentAdapter"]

# ---------------------------------------------------------------------------
# A2A-specific error codes (AGENT prefix, 700 range)
# ---------------------------------------------------------------------------

A2A_TASK_FAILED: str = "BEDDEL-AGENT-720"
"""A2A task execution failed."""

A2A_DISCOVERY_FAILED: str = "BEDDEL-AGENT-721"
"""A2A agent discovery (Agent Card) failed."""

A2A_TIMEOUT: str = "BEDDEL-AGENT-722"
"""A2A request timed out."""

A2A_AUTH_FAILED: str = "BEDDEL-AGENT-723"
"""A2A authentication failed."""


class A2AAgentAdapter:
    """A2A Protocol agent adapter using JSON-RPC 2.0 over HTTP(S).

    Implements the ``IAgentAdapter`` protocol structurally by exposing
    :meth:`execute` and :meth:`stream` with matching signatures.  All
    interaction with the remote agent happens through standard A2A
    JSON-RPC methods (``tasks/send`` for synchronous execution,
    ``tasks/sendSubscribe`` for SSE streaming).

    Args:
        agent_url: Base URL of the A2A-compliant agent endpoint.
            Trailing slashes are stripped.
        auth_token: Optional Bearer token for authentication.  Falls
            back to the ``A2A_AUTH_TOKEN`` environment variable when
            ``None``.
        timeout: Maximum request time in seconds before aborting.
    """

    def __init__(
        self,
        agent_url: str,
        auth_token: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._agent_url = agent_url.rstrip("/")
        self._auth_token = auth_token or os.environ.get("A2A_AUTH_TOKEN")
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_headers(self) -> dict[str, str]:
        """Build HTTP headers for A2A requests.

        Returns:
            A dict containing ``Content-Type`` and, when an auth token
            is available, an ``Authorization: Bearer`` header.
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        return headers

    def _build_jsonrpc_request(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a JSON-RPC 2.0 request envelope.

        Args:
            method: The JSON-RPC method name (e.g. ``"tasks/send"``).
            params: The method parameters dict.

        Returns:
            A complete JSON-RPC 2.0 request dict.
        """
        return {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": method,
            "params": params,
        }

    @staticmethod
    def _extract_text_from_parts(parts: list[dict[str, Any]]) -> str:
        """Concatenate text from A2A message parts.

        Args:
            parts: List of A2A part dicts.  Only parts with a ``"text"``
                key are included.

        Returns:
            Concatenated text content separated by newlines.
        """
        texts: list[str] = []
        for part in parts:
            if "text" in part:
                texts.append(part["text"])
        return "\n".join(texts)

    # ------------------------------------------------------------------
    # IAgentAdapter.execute
    # ------------------------------------------------------------------

    async def execute(
        self,
        prompt: str,
        *,
        model: str | None = None,
        sandbox: str = "read-only",
        tools: list[str] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Execute a prompt via the A2A ``tasks/send`` JSON-RPC method.

        Builds a JSON-RPC request with a user message containing the
        prompt, sends it to the remote agent, and maps the response to
        an :class:`AgentResult`.

        Args:
            prompt: The instruction or task to send to the agent.
            model: Optional model override (forwarded as metadata;
                ignored by most A2A agents).
            sandbox: Sandbox access level (informational for A2A).
            tools: Optional list of tool names (informational for A2A).
            output_schema: Optional JSON Schema dict (informational for A2A).

        Returns:
            An :class:`AgentResult` with the agent's text output.

        Raises:
            AgentError: ``BEDDEL-AGENT-720`` on HTTP or JSON-RPC errors,
                ``BEDDEL-AGENT-722`` on timeout.
        """
        params: dict[str, Any] = {
            "id": str(uuid4()),
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": prompt}],
            },
        }
        if model is not None:
            params["metadata"] = {"model": model}

        request = self._build_jsonrpc_request("tasks/send", params)
        headers = self._get_headers()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._agent_url,
                    json=request,
                    headers=headers,
                    timeout=self._timeout,
                )
        except httpx.TimeoutException as exc:
            raise AgentError(
                code=A2A_TIMEOUT,
                message=f"A2A request timed out after {self._timeout}s",
                details={"timeout": self._timeout, "url": self._agent_url},
            ) from exc
        except httpx.HTTPError as exc:
            raise AgentError(
                code=A2A_TASK_FAILED,
                message="A2A connection failed",
                details={"error": str(exc), "url": self._agent_url},
            ) from exc

        if response.status_code >= 400:
            raise AgentError(
                code=A2A_TASK_FAILED,
                message=f"A2A HTTP error {response.status_code}",
                details={
                    "status_code": response.status_code,
                    "body": response.text[:500],
                    "url": self._agent_url,
                },
            )

        data = response.json()

        # JSON-RPC error envelope
        if "error" in data:
            err = data["error"]
            raise AgentError(
                code=A2A_TASK_FAILED,
                message=f"A2A JSON-RPC error: {err.get('message', 'unknown')}",
                details={"jsonrpc_error": err},
            )

        result = data.get("result", {})
        task_state = result.get("status", {}).get("state", "unknown")

        # Extract text from artifacts
        output_parts: list[str] = []
        for artifact in result.get("artifacts", []):
            for part in artifact.get("parts", []):
                if "text" in part:
                    output_parts.append(part["text"])

        # Collect status history as events
        events: list[dict[str, Any]] = []
        history = result.get("history", [])
        if isinstance(history, list):
            events = history

        return AgentResult(
            exit_code=0 if task_state == "completed" else 1,
            output="\n".join(output_parts),
            events=events,
            files_changed=[],
            usage={},
            agent_id=self._agent_url,
        )

    # ------------------------------------------------------------------
    # IAgentAdapter.stream
    # ------------------------------------------------------------------

    async def stream(
        self,
        prompt: str,
        *,
        model: str | None = None,
        sandbox: str = "read-only",
        tools: list[str] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream events from the A2A ``tasks/sendSubscribe`` method.

        Builds a JSON-RPC request, sends it via HTTP POST, and reads
        the response as a Server-Sent Events (SSE) stream.  Each
        ``data:`` line is parsed as JSON and mapped to a structured
        event dict.

        Event types yielded:
            - ``"status"``: Task status update with ``state`` and
              optional ``message``.
            - ``"artifact"``: Artifact content with extracted text
              ``parts``.

        Args:
            prompt: The instruction or task to send to the agent.
            model: Optional model override (forwarded as metadata).
            sandbox: Sandbox access level (informational for A2A).
            tools: Optional list of tool names (informational for A2A).

        Yields:
            Structured event dicts from the A2A SSE stream.

        Raises:
            AgentError: ``BEDDEL-AGENT-720`` on connection failure,
                ``BEDDEL-AGENT-722`` on timeout.
        """
        params: dict[str, Any] = {
            "id": str(uuid4()),
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": prompt}],
            },
        }
        if model is not None:
            params["metadata"] = {"model": model}

        request = self._build_jsonrpc_request("tasks/sendSubscribe", params)
        headers = self._get_headers()

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    self._agent_url,
                    json=request,
                    headers=headers,
                    timeout=self._timeout,
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        raise AgentError(
                            code=A2A_TASK_FAILED,
                            message=f"A2A HTTP error {response.status_code}",
                            details={
                                "status_code": response.status_code,
                                "url": self._agent_url,
                            },
                        )

                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue

                        payload = line[len("data:") :].strip()
                        if not payload:
                            continue

                        try:
                            event = json.loads(payload)
                        except json.JSONDecodeError:
                            continue

                        # Map A2A SSE events to structured dicts
                        if "status" in event:
                            status = event["status"]
                            message_text = ""
                            status_message = status.get("message")
                            if status_message and "parts" in status_message:
                                message_text = self._extract_text_from_parts(
                                    status_message["parts"],
                                )
                            yield {
                                "type": "status",
                                "state": status.get("state", "unknown"),
                                "message": message_text,
                            }

                        if "artifact" in event:
                            artifact = event["artifact"]
                            parts_text: list[str] = []
                            for part in artifact.get("parts", []):
                                if "text" in part:
                                    parts_text.append(part["text"])
                            yield {
                                "type": "artifact",
                                "parts": parts_text,
                            }

        except httpx.TimeoutException as exc:
            raise AgentError(
                code=A2A_TIMEOUT,
                message=f"A2A stream timed out after {self._timeout}s",
                details={"timeout": self._timeout, "url": self._agent_url},
            ) from exc
        except httpx.HTTPError as exc:
            raise AgentError(
                code=A2A_TASK_FAILED,
                message="A2A stream connection failed",
                details={"error": str(exc), "url": self._agent_url},
            ) from exc
