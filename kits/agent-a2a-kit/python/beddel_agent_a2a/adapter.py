"""A2A Protocol agent adapter — SDK client (a2a-sdk 1.x).

This adapter bridges the Beddel domain core to any
`A2A Protocol <https://a2a-protocol.org/latest/specification>`_ compliant
agent, enabling agent-style interactions through the standard
``message/send`` protocol method via the official SDK client.  It implements
the :class:`~beddel.domain.ports.IAgentAdapter` protocol via structural
subtyping (no explicit inheritance).

Communication uses the ``a2a-sdk`` :func:`~a2a.client.create_client` factory
which handles transport selection, Agent Card resolution, and streaming
internally.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import httpx
from a2a.client import ClientConfig, create_client
from a2a.client.errors import (
    A2AClientError,
    A2AClientTimeoutError,
    AgentCardResolutionError,
)
from a2a.types import (
    Message,
    Part,
    Role,
    SendMessageRequest,
    TaskState,
)

from beddel.domain.errors import AgentError
from beddel.domain.models import AgentResult

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


def _extract_http_status_from_cause(exc: BaseException) -> int | None:
    """Walk the exception __cause__ chain looking for httpx.HTTPStatusError.

    The a2a-sdk wraps httpx.HTTPStatusError into A2AClientError via its
    handle_http_exceptions() context manager. This helper recovers the
    original HTTP status code from the chained cause.

    Returns:
        The HTTP status code if found, else ``None``.
    """
    cause: BaseException | None = exc.__cause__
    while cause is not None:
        if isinstance(cause, httpx.HTTPStatusError):
            return cause.response.status_code
        cause = cause.__cause__
    return None


class A2AAgentAdapter:
    """A2A Protocol agent adapter using the official a2a-sdk client.

    Implements the ``IAgentAdapter`` protocol structurally by exposing
    :meth:`execute` and :meth:`stream` with matching signatures.  All
    interaction with the remote agent happens through the SDK client's
    :meth:`send_message` method (``message/send`` protocol method).

    Args:
        agent_url: Base URL of the A2A-compliant agent endpoint.
            Trailing slashes are stripped.  Falls back to the
            ``A2A_AGENT_URL`` environment variable when ``None``.
        auth_token: Optional Bearer token for authentication.  Falls
            back to the ``A2A_AUTH_TOKEN`` environment variable when
            ``None``.
        timeout: Maximum request time in seconds before aborting.
    """

    def __init__(
        self,
        agent_url: str | None = None,
        auth_token: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        resolved_url = agent_url or os.environ.get("A2A_AGENT_URL")
        self._agent_url = resolved_url.rstrip("/") if resolved_url else ""
        self._auth_token = auth_token or os.environ.get("A2A_AUTH_TOKEN")
        self._timeout = timeout
        self._configured = bool(resolved_url)

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

    def _build_send_message_request(
        self,
        prompt: str,
        *,
        model: str | None = None,
        workflow_id: str | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> SendMessageRequest:
        """Build a SendMessageRequest for the a2a-sdk client.

        Args:
            prompt: The user message text.
            model: Optional model hint (forwarded as metadata).
            workflow_id: Optional workflow identifier. When provided,
                a DataPart is used instead of a TextPart.
            inputs: Optional workflow inputs dict (used with workflow_id).

        Returns:
            A :class:`SendMessageRequest` proto message.
        """
        if workflow_id is not None:
            from google.protobuf.json_format import ParseDict
            from google.protobuf.struct_pb2 import Value

            # Build the full payload as a plain dict and let ParseDict
            # handle recursive conversion (nested dicts, lists, nulls).
            payload: dict[str, Any] = {
                "workflow_id": workflow_id,
                "inputs": inputs if inputs is not None else {},
            }
            value = ParseDict(payload, Value())
            part = Part()
            part.data.CopyFrom(value)
        else:
            part = Part(text=prompt)

        message = Message(
            message_id=str(uuid4()),
            role=Role.ROLE_USER,
            parts=[part],
        )

        request = SendMessageRequest(message=message)

        if model is not None:
            from google.protobuf.struct_pb2 import Struct

            metadata = Struct()
            metadata.update({"model": model})
            request.metadata.CopyFrom(metadata)

        return request

    @staticmethod
    def _extract_text_from_parts(parts: Any) -> str:
        """Concatenate text from A2A message parts.

        Args:
            parts: Iterable of A2A Part proto messages.

        Returns:
            Concatenated text content separated by newlines.
        """
        texts: list[str] = []
        for part in parts:
            if part.text:
                texts.append(part.text)
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
        workflow_id: str | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Execute a prompt via the A2A ``message/send`` protocol method.

        Creates an SDK client from the agent URL, sends a message, and
        collects the full response (consuming the stream to completion).

        Args:
            prompt: The instruction or task to send to the agent.
            model: Optional model override (forwarded as metadata;
                ignored by most A2A agents).
            sandbox: Sandbox access level (informational for A2A).
            tools: Optional list of tool names (informational for A2A).
            output_schema: Optional JSON Schema dict (informational for A2A).
            workflow_id: Optional workflow identifier for DataPart mode.
            inputs: Optional workflow inputs dict (used with workflow_id).

        Returns:
            An :class:`AgentResult` with the agent's text output.

        Raises:
            AgentError: ``BEDDEL-AGENT-720`` on protocol or server errors,
                ``BEDDEL-AGENT-721`` on discovery failures,
                ``BEDDEL-AGENT-722`` on timeout,
                ``BEDDEL-AGENT-723`` on auth failures.
        """
        request = self._build_send_message_request(
            prompt, model=model, workflow_id=workflow_id, inputs=inputs
        )

        client = None
        httpx_client = httpx.AsyncClient(
            headers=self._get_headers(),
            timeout=self._timeout,
        )
        try:
            try:
                config = ClientConfig(
                    httpx_client=httpx_client,
                    streaming=False,
                )
                client = await create_client(
                    agent=self._agent_url,
                    client_config=config,
                )
            except AgentCardResolutionError as exc:
                if getattr(exc, "status_code", None) in (401, 403):
                    raise AgentError(
                        code=A2A_AUTH_FAILED,
                        message="A2A authentication failed during discovery",
                        details={
                            "error": str(exc),
                            "url": self._agent_url,
                            "status_code": exc.status_code,
                        },
                    ) from exc
                raise AgentError(
                    code=A2A_DISCOVERY_FAILED,
                    message="A2A agent card resolution failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except A2AClientTimeoutError as exc:
                raise AgentError(
                    code=A2A_TIMEOUT,
                    message=f"A2A client creation timed out after {self._timeout}s",
                    details={"timeout": self._timeout, "url": self._agent_url},
                ) from exc
            except A2AClientError as exc:
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message="A2A client creation failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except httpx.TimeoutException as exc:
                raise AgentError(
                    code=A2A_TIMEOUT,
                    message=f"A2A client creation timed out after {self._timeout}s",
                    details={"timeout": self._timeout, "url": self._agent_url},
                ) from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403):
                    raise AgentError(
                        code=A2A_AUTH_FAILED,
                        message="A2A authentication failed",
                        details={
                            "error": str(exc),
                            "url": self._agent_url,
                            "status_code": exc.response.status_code,
                        },
                    ) from exc
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message="A2A client creation failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except httpx.HTTPError as exc:
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message="A2A client creation failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except Exception as exc:
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message="A2A client creation failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc

            # send_message returns an AsyncIterator[StreamResponse]
            # Collect all responses
            output_parts: list[str] = []
            task_state = TaskState.TASK_STATE_UNSPECIFIED
            events: list[dict[str, Any]] = []

            try:
                async for response in client.send_message(request):
                    # StreamResponse has oneof payload: task, message, status_update, artifact_update
                    if response.HasField("task"):
                        task = response.task
                        task_state = task.status.state
                        for artifact in task.artifacts:
                            for part in artifact.parts:
                                if part.text:
                                    output_parts.append(part.text)
                        # Collect history as events
                        for msg in task.history:
                            events.append(
                                {
                                    "role": "user"
                                    if msg.role == Role.ROLE_USER
                                    else "agent",
                                    "text": self._extract_text_from_parts(msg.parts),
                                }
                            )

                    elif response.HasField("message"):
                        msg = response.message
                        text = self._extract_text_from_parts(msg.parts)
                        if text:
                            output_parts.append(text)
                        # If message arrives, consider it completed
                        task_state = TaskState.TASK_STATE_COMPLETED

                    elif response.HasField("status_update"):
                        status_update = response.status_update
                        task_state = status_update.status.state

                    elif response.HasField("artifact_update"):
                        artifact = response.artifact_update.artifact
                        for part in artifact.parts:
                            if part.text:
                                output_parts.append(part.text)

            except AgentCardResolutionError as exc:
                if getattr(exc, "status_code", None) in (401, 403):
                    raise AgentError(
                        code=A2A_AUTH_FAILED,
                        message="A2A authentication failed",
                        details={
                            "error": str(exc),
                            "url": self._agent_url,
                            "status_code": exc.status_code,
                        },
                    ) from exc
                raise AgentError(
                    code=A2A_DISCOVERY_FAILED,
                    message="A2A agent card resolution failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except A2AClientTimeoutError as exc:
                raise AgentError(
                    code=A2A_TIMEOUT,
                    message=f"A2A request timed out after {self._timeout}s",
                    details={"timeout": self._timeout, "url": self._agent_url},
                ) from exc
            except A2AClientError as exc:
                # SDK wraps httpx.HTTPStatusError — inspect cause chain
                status = _extract_http_status_from_cause(exc)
                if status in (401, 403):
                    raise AgentError(
                        code=A2A_AUTH_FAILED,
                        message="A2A authentication failed",
                        details={
                            "error": str(exc),
                            "url": self._agent_url,
                            "status_code": status,
                        },
                    ) from exc
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message=f"A2A client error: {exc}",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except httpx.TimeoutException as exc:
                raise AgentError(
                    code=A2A_TIMEOUT,
                    message=f"A2A request timed out after {self._timeout}s",
                    details={"timeout": self._timeout, "url": self._agent_url},
                ) from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403):
                    raise AgentError(
                        code=A2A_AUTH_FAILED,
                        message="A2A authentication failed",
                        details={
                            "error": str(exc),
                            "url": self._agent_url,
                            "status_code": exc.response.status_code,
                        },
                    ) from exc
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message="A2A connection failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except httpx.HTTPError as exc:
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message="A2A connection failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc

        finally:
            # F4: nested cleanup — client.close() failure must not skip httpx
            if client is not None:
                try:
                    await client.close()
                except Exception:
                    import logging as _log

                    _log.getLogger(__name__).warning(
                        "A2A client.close() failed", exc_info=True
                    )
            await httpx_client.aclose()

        is_completed = task_state == TaskState.TASK_STATE_COMPLETED

        return AgentResult(
            exit_code=0 if is_completed else 1,
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
        workflow_id: str | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream events from the A2A ``message/send`` method (streaming mode).

        Creates an SDK client with streaming enabled, sends a message,
        and yields structured event dicts as they arrive from the agent.

        Event types yielded:
            - ``"status"``: Task status update with ``state`` and
              optional ``message``.
            - ``"artifact"``: Artifact content with extracted text
              ``parts``.
            - ``"message"``: Agent message with text content.

        Args:
            prompt: The instruction or task to send to the agent.
            model: Optional model override (forwarded as metadata).
            sandbox: Sandbox access level (informational for A2A).
            tools: Optional list of tool names (informational for A2A).
            workflow_id: Optional workflow identifier for DataPart mode.
            inputs: Optional workflow inputs dict (used with workflow_id).

        Yields:
            Structured event dicts from the A2A stream.

        Raises:
            AgentError: ``BEDDEL-AGENT-720`` on connection failure,
                ``BEDDEL-AGENT-721`` on discovery failures,
                ``BEDDEL-AGENT-722`` on timeout,
                ``BEDDEL-AGENT-723`` on auth failures.
        """
        request = self._build_send_message_request(
            prompt, model=model, workflow_id=workflow_id, inputs=inputs
        )

        client = None
        httpx_client = httpx.AsyncClient(
            headers=self._get_headers(),
            timeout=self._timeout,
        )
        try:
            try:
                config = ClientConfig(
                    httpx_client=httpx_client,
                    streaming=True,
                )
                client = await create_client(
                    agent=self._agent_url,
                    client_config=config,
                )
            except AgentCardResolutionError as exc:
                if getattr(exc, "status_code", None) in (401, 403):
                    raise AgentError(
                        code=A2A_AUTH_FAILED,
                        message="A2A authentication failed during discovery",
                        details={
                            "error": str(exc),
                            "url": self._agent_url,
                            "status_code": exc.status_code,
                        },
                    ) from exc
                raise AgentError(
                    code=A2A_DISCOVERY_FAILED,
                    message="A2A agent card resolution failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except A2AClientTimeoutError as exc:
                raise AgentError(
                    code=A2A_TIMEOUT,
                    message=(f"A2A client creation timed out after {self._timeout}s"),
                    details={"timeout": self._timeout, "url": self._agent_url},
                ) from exc
            except A2AClientError as exc:
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message="A2A client creation failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except httpx.TimeoutException as exc:
                raise AgentError(
                    code=A2A_TIMEOUT,
                    message=(f"A2A client creation timed out after {self._timeout}s"),
                    details={"timeout": self._timeout, "url": self._agent_url},
                ) from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403):
                    raise AgentError(
                        code=A2A_AUTH_FAILED,
                        message="A2A authentication failed",
                        details={
                            "error": str(exc),
                            "url": self._agent_url,
                            "status_code": exc.response.status_code,
                        },
                    ) from exc
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message="A2A client creation failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except httpx.HTTPError as exc:
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message="A2A client creation failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except Exception as exc:
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message="A2A client creation failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc

            try:
                async for response in client.send_message(request):
                    if response.HasField("task"):
                        task = response.task
                        state_name = (
                            TaskState.Name(task.status.state)
                            .replace("TASK_STATE_", "")
                            .lower()
                        )
                        yield {
                            "type": "status",
                            "state": state_name,
                            "message": "",
                        }
                        # Also yield artifacts from task
                        for artifact in task.artifacts:
                            parts_text: list[str] = []
                            for part in artifact.parts:
                                if part.text:
                                    parts_text.append(part.text)
                            if parts_text:
                                yield {
                                    "type": "artifact",
                                    "parts": parts_text,
                                }

                    elif response.HasField("message"):
                        msg = response.message
                        text = self._extract_text_from_parts(msg.parts)
                        yield {
                            "type": "message",
                            "text": text,
                        }

                    elif response.HasField("status_update"):
                        status_update = response.status_update
                        state_name = (
                            TaskState.Name(status_update.status.state)
                            .replace("TASK_STATE_", "")
                            .lower()
                        )
                        message_text = ""
                        if status_update.status.HasField("message"):
                            message_text = self._extract_text_from_parts(
                                status_update.status.message.parts
                            )
                        yield {
                            "type": "status",
                            "state": state_name,
                            "message": message_text,
                        }

                    elif response.HasField("artifact_update"):
                        artifact = response.artifact_update.artifact
                        parts_text = []
                        for part in artifact.parts:
                            if part.text:
                                parts_text.append(part.text)
                        if parts_text:
                            yield {
                                "type": "artifact",
                                "parts": parts_text,
                            }

            except AgentCardResolutionError as exc:
                if getattr(exc, "status_code", None) in (401, 403):
                    raise AgentError(
                        code=A2A_AUTH_FAILED,
                        message="A2A authentication failed",
                        details={
                            "error": str(exc),
                            "url": self._agent_url,
                            "status_code": exc.status_code,
                        },
                    ) from exc
                raise AgentError(
                    code=A2A_DISCOVERY_FAILED,
                    message="A2A agent card resolution failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except A2AClientTimeoutError as exc:
                raise AgentError(
                    code=A2A_TIMEOUT,
                    message=f"A2A stream timed out after {self._timeout}s",
                    details={
                        "timeout": self._timeout,
                        "url": self._agent_url,
                    },
                ) from exc
            except A2AClientError as exc:
                # SDK wraps httpx.HTTPStatusError — inspect cause chain
                status = _extract_http_status_from_cause(exc)
                if status in (401, 403):
                    raise AgentError(
                        code=A2A_AUTH_FAILED,
                        message="A2A authentication failed",
                        details={
                            "error": str(exc),
                            "url": self._agent_url,
                            "status_code": status,
                        },
                    ) from exc
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message=f"A2A stream error: {exc}",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except httpx.TimeoutException as exc:
                raise AgentError(
                    code=A2A_TIMEOUT,
                    message=f"A2A stream timed out after {self._timeout}s",
                    details={
                        "timeout": self._timeout,
                        "url": self._agent_url,
                    },
                ) from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403):
                    raise AgentError(
                        code=A2A_AUTH_FAILED,
                        message="A2A authentication failed",
                        details={
                            "error": str(exc),
                            "url": self._agent_url,
                            "status_code": exc.response.status_code,
                        },
                    ) from exc
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message="A2A stream connection failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc
            except httpx.HTTPError as exc:
                raise AgentError(
                    code=A2A_TASK_FAILED,
                    message="A2A stream connection failed",
                    details={"error": str(exc), "url": self._agent_url},
                ) from exc

        finally:
            # F4: nested cleanup — client.close() failure must not skip httpx
            if client is not None:
                try:
                    await client.close()
                except Exception:
                    import logging as _log

                    _log.getLogger(__name__).warning(
                        "A2A client.close() failed", exc_info=True
                    )
            await httpx_client.aclose()
