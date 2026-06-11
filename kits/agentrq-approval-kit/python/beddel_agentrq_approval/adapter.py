"""AgentRQ approval gate adapter for Beddel workflows.

Implements IApprovalGate using AgentRQ's MCP server for human-in-the-loop
approval of high-risk workflow steps.

Uses the ``mcp`` library's :class:`ClientSession` with SSE transport
(via httpx-sse) to communicate with the AgentRQ workspace MCP server.
The adapter satisfies :class:`~beddel.domain.ports.IApprovalGate` via
structural subtyping (Protocol compliance, no inheritance).

MCP connection is lazy — created on first use via :meth:`_ensure_connected`,
disconnected on explicit :meth:`close` or ``__aexit__``.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import AsyncExitStack
from typing import Any

from beddel.domain.models import (
    ApprovalPolicy,
    ApprovalResult,
    ApprovalStatus,
    RiskLevel,
)

try:
    from mcp import ClientSession
except ImportError:  # pragma: no cover
    ClientSession = None  # type: ignore[assignment, misc]

__all__ = ["AdapterError", "AgentRQApprovalGate"]

logger = logging.getLogger(__name__)


class AdapterError(Exception):
    """Kit-local exception for MCP transport and adapter errors.

    Attributes:
        code: Structured error code (e.g. ``BEDDEL-ADAPT-003``).
        details: Optional context dict for debugging.
    """

    def __init__(
        self, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class AgentRQApprovalGate:
    """Approval gate adapter that creates tasks in AgentRQ for human review.

    Uses the MCP protocol (SSE transport) to communicate with an AgentRQ
    workspace server. Maps AgentRQ task statuses to Beddel ApprovalStatus.

    Satisfies :class:`~beddel.domain.ports.IApprovalGate` via structural
    subtyping — no inheritance required.

    Args:
        workspace_url: Full AgentRQ MCP endpoint URL (includes auth token).
        timeout_seconds: Client-side timeout in seconds for approval requests.
            Defaults to 300 (5 minutes).
        policy: Optional :class:`ApprovalPolicy` for risk-based auto-approve
            rules. Defaults to ``ApprovalPolicy()`` when ``None``.

    Example::

        async with AgentRQApprovalGate("https://agentrq.dev/mcp/ws123?token=abc") as gate:
            result = await gate.request_approval("delete_db", RiskLevel.HIGH)
            status = await gate.check_status(result.request_id)
    """

    _STATUS_MAP: dict[str, ApprovalStatus] = {
        "notstarted": ApprovalStatus.PENDING,
        "ongoing": ApprovalStatus.PENDING,
        "cron": ApprovalStatus.PENDING,
        "completed": ApprovalStatus.APPROVED,
        "rejected": ApprovalStatus.DENIED,
        "blocked": ApprovalStatus.ESCALATED,
    }

    def __init__(
        self,
        workspace_url: str,
        timeout_seconds: int = 300,
        policy: ApprovalPolicy | None = None,
    ) -> None:
        """Initialize the AgentRQ approval gate adapter.

        Args:
            workspace_url: Full AgentRQ MCP endpoint URL (includes token).
            timeout_seconds: Client-side timeout for approval requests.
            policy: Optional ApprovalPolicy for auto-approve rules.
        """
        self._workspace_url = workspace_url
        self._timeout_seconds = timeout_seconds
        self._policy = policy or ApprovalPolicy()
        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._pending_requests: dict[str, float] = {}

    @property
    def policy(self) -> ApprovalPolicy:
        """Return the configured approval policy."""
        return self._policy

    @property
    def timeout_seconds(self) -> int:
        """Return the configured client-side timeout in seconds."""
        return self._timeout_seconds

    @property
    def workspace_url(self) -> str:
        """Return the AgentRQ MCP endpoint URL."""
        return self._workspace_url

    async def _ensure_connected(self) -> ClientSession:
        """Ensure MCP session is connected, creating it lazily on first use.

        Returns:
            The active :class:`ClientSession` instance.

        Raises:
            RuntimeError: If the ``mcp`` library is not installed.
        """
        if self._session is not None:
            return self._session

        if ClientSession is None:
            raise RuntimeError(
                "The 'mcp' package is required for AgentRQApprovalGate. "
                "Install it with: pip install mcp httpx-sse"
            )

        logger.info("Connecting to AgentRQ MCP server at %s", self._workspace_url)

        self._session = await self._create_session()
        return self._session

    async def _create_session(self) -> ClientSession:
        """Create and initialize the MCP client session with SSE transport.

        This is separated from _ensure_connected to allow easier testing
        and mocking of the transport layer.

        Returns:
            An initialized MCP ClientSession.
        """
        from mcp.client.sse import sse_client

        self._exit_stack = AsyncExitStack()
        transport = await self._exit_stack.enter_async_context(
            sse_client(self._workspace_url)
        )
        read_stream, write_stream = transport
        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()
        return session

    async def request_approval(
        self, action: str, risk_level: RiskLevel
    ) -> ApprovalResult:
        """Request human approval for an agent action via AgentRQ.

        If ``risk_level`` is in ``policy.auto_approve_levels``, the request
        is auto-approved immediately without creating an AgentRQ task.
        Otherwise, creates a task in AgentRQ for human review.

        Args:
            action: Description of the action requiring approval.
            risk_level: The classified risk level of the action.

        Returns:
            An :class:`ApprovalResult` with the approval decision.
        """
        # Auto-approve path: no MCP traffic (AC 4, 10)
        if risk_level in self._policy.auto_approve_levels:
            return ApprovalResult(
                request_id=uuid.uuid4().hex,
                status=ApprovalStatus.APPROVED,
                approver="policy",
                timestamp=time.time(),
                metadata={"action": action, "risk_level": risk_level.value},
            )

        # MCP task creation path (AC 3, 8)
        session = await self._ensure_connected()

        # Create task in AgentRQ
        create_result = await session.call_tool(
            "createTask",
            arguments={
                "title": f"[Beddel Approval] {action}",
                "description": f"Risk: {risk_level.value}\nAction: {action}",
            },
        )
        task_id: str = getattr(create_result.content[0], "text", "")

        # Post workflow context for human reviewer (AC 8)
        await session.call_tool(
            "reply",
            arguments={
                "taskId": task_id,
                "message": (
                    f"Workflow context: action='{action}', "
                    f"risk_level='{risk_level.value}'"
                ),
            },
        )

        # Persist created_at for timeout tracking in check_status
        self._pending_requests[task_id] = time.time()

        return ApprovalResult(
            request_id=task_id,
            status=ApprovalStatus.PENDING,
            timestamp=time.time(),
            metadata={"action": action, "risk_level": risk_level.value},
        )

    async def check_status(self, request_id: str) -> ApprovalStatus:
        """Check the current status of a pending approval request.

        Polls the AgentRQ task status and maps it to Beddel's
        :class:`ApprovalStatus`. Timeout is derived client-side by
        comparing ``now - created_at > timeout_seconds``.

        Args:
            request_id: The unique identifier (AgentRQ task_id) from a
                prior approval result.

        Returns:
            The current :class:`ApprovalStatus` of the request.

        Raises:
            AdapterError: On MCP transport errors (code ``BEDDEL-ADAPT-003``).
        """
        # Unknown request_id → PENDING (AC 9, consistent with InMemoryApprovalGate)
        if request_id not in self._pending_requests:
            return ApprovalStatus.PENDING

        # Client-side timeout derivation (AC 5)
        created_at = self._pending_requests[request_id]
        if time.time() - created_at > self._timeout_seconds:
            return ApprovalStatus.TIMEOUT

        # Poll AgentRQ via MCP
        try:
            session = await self._ensure_connected()
            result = await session.call_tool(
                "getTaskMessages",
                arguments={"taskId": request_id, "cursor": ""},
            )
        except Exception as exc:
            raise AdapterError(
                code="BEDDEL-ADAPT-003",
                message=f"MCP transport error while polling task status: {exc}",
                details={"request_id": request_id, "original_error": str(exc)},
            ) from exc

        # Parse response to extract task status
        try:
            content_text = getattr(result.content[0], "text", "")
            data = json.loads(content_text)

            # Extract status from response — may be top-level or nested
            if isinstance(data, dict):
                raw_status = data.get("status", "").lower()
            elif isinstance(data, list) and data:
                # If response is a list, check last entry for status
                last_entry = data[-1] if isinstance(data[-1], dict) else {}
                raw_status = last_entry.get("status", "").lower()
            else:
                raw_status = ""
        except (json.JSONDecodeError, IndexError, AttributeError):
            # Cannot parse response — default to PENDING
            logger.warning(
                "Could not parse AgentRQ response for task %s, defaulting to PENDING",
                request_id,
            )
            return ApprovalStatus.PENDING

        # Map AgentRQ status to ApprovalStatus
        if raw_status in self._STATUS_MAP:
            return self._STATUS_MAP[raw_status]

        # Unknown status → PENDING + warning (safe default)
        if raw_status:
            logger.warning(
                "Unknown AgentRQ task status '%s' for request %s, defaulting to PENDING",
                raw_status,
                request_id,
            )
        return ApprovalStatus.PENDING

    async def request_approval_async(self, action: str, risk_level: RiskLevel) -> str:
        """Request approval asynchronously using the CIBA pattern.

        Submits the request and returns the ``request_id`` (AgentRQ task_id)
        immediately without waiting for human response.

        Args:
            action: Description of the action requiring approval.
            risk_level: The classified risk level of the action.

        Returns:
            The ``request_id`` for subsequent polling via :meth:`check_status`.
        """
        result = await self.request_approval(action, risk_level)
        return result.request_id

    async def close(self) -> None:
        """Explicitly close the MCP connection and clean up resources.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._session is not None:
            logger.info("Closing AgentRQ MCP connection")
            try:
                if self._exit_stack is not None:
                    await self._exit_stack.aclose()
            except Exception:
                logger.warning("Error closing MCP session", exc_info=True)
            finally:
                self._session = None
                self._exit_stack = None

    async def __aenter__(self) -> AgentRQApprovalGate:
        """Enter async context manager.

        Does NOT eagerly connect — connection is lazy on first use.

        Returns:
            The gate instance.
        """
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager, closing the MCP connection."""
        await self.close()
