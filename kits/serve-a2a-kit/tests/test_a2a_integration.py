"""In-process ASGI conformance tests for serve-a2a-kit (Story K1A.5).

These tests exercise the real a2a-sdk 1.1.2 wiring end-to-end over an
in-process ASGI transport (no real sockets, no mocking of SDK internals):

    FastAPI app
      + create_agent_card_routes()  -> GET /.well-known/agent-card.json
      + create_jsonrpc_routes()     -> POST /a2a (JSON-RPC)
    mounted via add_a2a_routes_to_fastapi()
    backed by a real DefaultRequestHandler(
        agent_executor=BeddelA2AExecutor(registry),
        task_store=InMemoryTaskStore(),
        agent_card=<real AgentCard from build_agent_card()>,
    )

Coverage (see story-k1a-5.md AC1, AC3, AC4):
    - Card discovery: GET /.well-known/agent-card.json round-trips through
      ProtoJSON parsing (A2ACardResolver against the real ASGI transport).
    - Non-streaming completion via handler.on_message_send(): terminal
      result IS a Task snapshot with TASK_STATE_COMPLETED.
    - Streaming via handler.on_message_send_stream(): first event is a
      Task(SUBMITTED); artifact events share one stable artifact_id with
      correct append/last_chunk flags; the LAST event is a
      TaskStatusUpdateEvent(COMPLETED) — NOT a Task. Streaming and
      non-streaming have different terminal event types in a2a-sdk 1.1.2.
    - Unknown workflow_id reaches terminal FAILED.
    - Text-only Part (no workflow_id) reaches terminal FAILED without
      raising out of the handler.

The workflow executor stub used here (``_StubWorkflowExecutor``) is a thin,
real class implementing the same ``execute_stream`` shape as
``beddel.domain.executor.WorkflowExecutor`` — it is not a mock of any
a2a-sdk component. Only the *workflow-side* streaming is stubbed, per the
existing ``test_server.py`` precedent (``_mock_execute_stream``); every
a2a-sdk object (``FastAPI``, ``DefaultRequestHandler``, ``InMemoryTaskStore``,
``AgentCard``, routes, ``httpx.ASGITransport``) is the real SDK component.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncGenerator
from secrets import compare_digest
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from a2a.client import A2ACardResolver
from a2a.server.agent_execution.context import ServerCallContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    Message,
    Part,
    Role,
    SendMessageConfiguration,
    SendMessageRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)
from a2a.utils import constants as a2a_constants
from fastapi import FastAPI
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse as StarletteJSONResponse

from beddel.domain.models import (
    BeddelEvent,
    EventType,
    ExecutionStrategy,
    Step,
    StrategyType,
    Workflow,
)
from beddel_serve_a2a.server import (
    BeddelA2AExecutor,
    WorkflowRegistry,
    build_agent_card,
)

pytestmark = pytest.mark.integration
"""Module-wide ``integration`` marker (Story K1A.5, AC7).

Applied at module scope rather than per function so a newly added test cannot
be forgotten.  ``pytestmark`` composes with per-function decorators such as
``@pytest.mark.asyncio``.
"""

# ---------------------------------------------------------------------------
# Workflow / step builders (mirrors test_server.py helpers)
# ---------------------------------------------------------------------------


def _make_step(step_id: str = "step-1", primitive: str = "llm") -> Step:
    """Create a minimal Step for testing."""
    return Step(
        id=step_id,
        primitive=primitive,
        config={},
        execution_strategy=ExecutionStrategy(type=StrategyType.FAIL),
    )


def _make_workflow(
    wf_id: str = "wf-integration",
    name: str = "Integration Test Workflow",
    description: str = "A workflow used for ASGI conformance testing",
    steps: list[Step] | None = None,
) -> Workflow:
    """Create a minimal Workflow for testing."""
    return Workflow(
        id=wf_id,
        name=name,
        description=description,
        steps=steps or [_make_step()],
    )


async def _mock_execute_stream(
    events: list[BeddelEvent],
) -> AsyncGenerator[BeddelEvent, None]:
    """Yield a pre-built list of BeddelEvents as an async generator."""
    for event in events:
        yield event


class _StubWorkflowExecutor:
    """Minimal workflow-side executor stub with an ``execute_stream`` method.

    This stands in for ``beddel.domain.executor.WorkflowExecutor`` — it is
    not part of the a2a-sdk and is not a mock of SDK internals. It exists
    purely to control which ``BeddelEvent`` sequence the real
    ``BeddelA2AExecutor`` sees, so that streaming/non-streaming/failure
    paths through the REAL SDK request handler can be exercised
    deterministically.
    """

    def __init__(self, events: list[BeddelEvent]) -> None:
        self._events = events

    def execute_stream(
        self, workflow: Workflow, inputs: dict[str, Any] | None
    ) -> AsyncGenerator[BeddelEvent, None]:
        return _mock_execute_stream(self._events)


def _build_send_request(
    workflow_id: str | None = None, *, text_only: bool = False
) -> SendMessageRequest:
    """Build a real SendMessageRequest carrying a DataPart or a text Part."""
    if text_only:
        return SendMessageRequest(
            message=Message(
                role=Role.ROLE_USER,
                parts=[Part(text="hello, no workflow_id here")],
                message_id=str(uuid.uuid4()),
            ),
            configuration=SendMessageConfiguration(),
        )

    data_value = Value()
    json_format.ParseDict({"workflow_id": workflow_id}, data_value)

    return SendMessageRequest(
        message=Message(
            role=Role.ROLE_USER,
            parts=[Part(data=data_value)],
            message_id=str(uuid.uuid4()),
        ),
        configuration=SendMessageConfiguration(),
    )


# ---------------------------------------------------------------------------
# Auth middleware (Story K1A.5 AC6) — test-local reimplementation
# ---------------------------------------------------------------------------


class _TestA2ABearerAuthMiddleware(BaseHTTPMiddleware):
    """Reimplementation of the private ``_A2ABearerAuthMiddleware`` defined
    inside ``beddel.cli.commands._build_runtime_app()``.

    The production class is a nested class local to a function body, so it
    cannot be imported here. This mirrors it exactly: same path-prefix
    check (``/a2a``), same ``Bearer `` prefix check, same
    ``secrets.compare_digest`` comparison, and the same 401 JSON response
    shape (``{"error": "Unauthorized"}``). Only wired into the harness when
    ``auth_token`` is passed to ``_build_harness()`` — mirroring the
    production ``if _a2a_token:`` guard.
    """

    def __init__(self, app: Any, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        if request.url.path.startswith("/a2a"):
            auth = request.headers.get("authorization", "")
            if not auth.startswith("Bearer ") or not compare_digest(
                auth[7:], self._token
            ):
                return StarletteJSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


# ---------------------------------------------------------------------------
# Fixtures — real FastAPI app + real DefaultRequestHandler over ASGI
# ---------------------------------------------------------------------------


class _A2AHarness:
    """Bundle of real a2a-sdk components wired for in-process testing.

    Attributes:
        app: The FastAPI app with real A2A routes mounted.
        handler: The real ``DefaultRequestHandler`` backing the routes.
        client: An ``httpx.AsyncClient`` dispatching over ``ASGITransport``
            (zero real sockets).
        registry: The workflow registry backing the executor.
    """

    def __init__(
        self,
        app: FastAPI,
        handler: DefaultRequestHandler,
        client: httpx.AsyncClient,
        registry: WorkflowRegistry,
    ) -> None:
        self.app = app
        self.handler = handler
        self.client = client
        self.registry = registry


def _build_harness(
    events_by_workflow: dict[str, list[BeddelEvent]],
    *,
    auth_token: str | None = None,
) -> _A2AHarness:
    """Construct a real FastAPI + DefaultRequestHandler harness.

    Args:
        events_by_workflow: Maps workflow_id to the BeddelEvent sequence
            that the stub workflow executor should stream for it.
        auth_token: When provided, wires ``_TestA2ABearerAuthMiddleware``
            onto the FastAPI app — mirroring the production
            ``if _a2a_token:`` guard in
            ``beddel.cli.commands._build_runtime_app()``. Defaults to
            ``None``, preserving the Task 1 harness's unauthenticated
            behavior unchanged.

    Returns:
        A fully wired ``_A2AHarness`` ready for ASGI dispatch.
    """
    registry: WorkflowRegistry = {}
    for wf_id, events in events_by_workflow.items():
        wf = _make_workflow(wf_id=wf_id)
        registry[wf_id] = (wf, _StubWorkflowExecutor(events))  # type: ignore[assignment]

    agent_card = build_agent_card(
        workflows=registry,
        public_base_url="http://test",
    )
    executor = BeddelA2AExecutor(registry)
    task_store = InMemoryTaskStore()
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store,
        agent_card=agent_card,
    )

    app = FastAPI()

    # Bearer auth middleware for A2A routes — only wired when a token is
    # provided, mirroring the production `if _a2a_token:` guard.
    if auth_token:
        app.add_middleware(_TestA2ABearerAuthMiddleware, token=auth_token)

    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card),
        jsonrpc_routes=create_jsonrpc_routes(handler, rpc_url="/a2a"),
    )

    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")

    return _A2AHarness(app=app, handler=handler, client=client, registry=registry)


@pytest_asyncio.fixture
async def a2a_harness() -> AsyncGenerator[_A2AHarness, None]:
    """Pytest fixture yielding an ``_A2AHarness`` with two known workflows.

    ``wf-complete``: streams WORKFLOW_START -> TEXT_CHUNK x2 -> WORKFLOW_END
        (reaches TASK_STATE_COMPLETED).
    ``wf-fail``: streams WORKFLOW_START -> ERROR only, stream exhausts
        without a terminal event (reaches TASK_STATE_FAILED via the
        executor's fallback-to-failed behavior).

    The underlying ``httpx.AsyncClient`` is closed on teardown.
    """
    events_by_workflow = {
        "wf-complete": [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "Hello "},
            ),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "World"},
            ),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
        ],
        "wf-fail": [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.ERROR,
                step_id="step-1",
                data={"error": "fatal for this test"},
            ),
        ],
    }
    harness = _build_harness(events_by_workflow)
    try:
        yield harness
    finally:
        await harness.client.aclose()


_AUTH_TEST_TOKEN = "test-secret-token-123"


@pytest_asyncio.fixture
async def a2a_harness_with_auth() -> AsyncGenerator[_A2AHarness, None]:
    """Pytest fixture yielding an ``_A2AHarness`` with the bearer auth
    middleware active (Story K1A.5 AC6).

    Reuses the same ``wf-complete`` workflow event sequence as
    ``a2a_harness`` for consistency, but builds a standalone registry so
    this fixture has no dependency on the unauthenticated one.

    The underlying ``httpx.AsyncClient`` is closed on teardown.
    """
    events_by_workflow = {
        "wf-complete": [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "Hello "},
            ),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "World"},
            ),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
        ],
    }
    harness = _build_harness(events_by_workflow, auth_token=_AUTH_TEST_TOKEN)
    try:
        yield harness
    finally:
        await harness.client.aclose()


def _build_jsonrpc_send_payload(workflow_id: str) -> dict[str, Any]:
    """Build a raw JSON-RPC 2.0 envelope for a ``SendMessage`` call.

    This is the shape a real A2A client sends over HTTP to ``POST /a2a``
    (as opposed to ``_build_send_request()``, which builds the proto
    request object used by the other tests to call the handler directly
    in-process). The a2a-sdk 1.1.2 JSON-RPC dispatcher routes on the gRPC
    service method name ``"SendMessage"`` (see
    ``JsonRpcDispatcher.METHOD_TO_MODEL``), with ``params`` parsed into a
    ``SendMessageRequest`` proto message via ``ParseDict``.
    """
    data_value = Value()
    json_format.ParseDict({"workflow_id": workflow_id}, data_value)
    request = SendMessageRequest(
        message=Message(
            role=Role.ROLE_USER,
            parts=[Part(data=data_value)],
            message_id=str(uuid.uuid4()),
        ),
        configuration=SendMessageConfiguration(),
    )
    params = json_format.MessageToDict(request)
    return {"jsonrpc": "2.0", "id": 1, "method": "SendMessage", "params": params}


# ---------------------------------------------------------------------------
# AC3: Card discovery at /.well-known/agent-card.json
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_card_discovery_round_trips_via_card_resolver(
    a2a_harness: _A2AHarness,
) -> None:
    """GET /.well-known/agent-card.json returns a card A2ACardResolver can parse.

    Uses the real ``A2ACardResolver`` against the real ASGI-backed
    ``httpx.AsyncClient`` — the fetched JSON round-trips back into a real
    ``AgentCard`` (ProtoJSON parse), proving the served representation is
    spec-conformant, not just "some JSON".
    """
    resolver = A2ACardResolver(
        httpx_client=a2a_harness.client,
        base_url="http://test",
    )

    card = await resolver.get_agent_card()

    assert card.name == "Beddel Agent"
    skill_ids = {skill.id for skill in card.skills}
    assert skill_ids == {"wf-complete", "wf-fail"}
    assert card.capabilities.streaming is True


@pytest.mark.asyncio
async def test_agent_card_get_direct_returns_200(a2a_harness: _A2AHarness) -> None:
    """Direct GET to the well-known card path returns HTTP 200 with JSON body."""
    response = await a2a_harness.client.get("/.well-known/agent-card.json")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Beddel Agent"


# ---------------------------------------------------------------------------
# AC1/AC4: Non-streaming completion via handler.on_message_send()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_streaming_send_returns_task_snapshot_completed(
    a2a_harness: _A2AHarness,
) -> None:
    """on_message_send() (non-streaming) returns a Task snapshot when COMPLETED.

    This is the ONE case where a Task snapshot as the terminal result is
    correct: the non-streaming path replaces status updates with Task
    snapshots before returning.
    """
    request = _build_send_request(workflow_id="wf-complete")
    call_context = ServerCallContext()

    result = await a2a_harness.handler.on_message_send(request, call_context)

    assert isinstance(result, Task)
    assert result.status.state == TaskState.TASK_STATE_COMPLETED


# ---------------------------------------------------------------------------
# AC1/AC4: Streaming via handler.on_message_send_stream()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_send_emits_ordered_events_with_stable_artifact_id(
    a2a_harness: _A2AHarness,
) -> None:
    """on_message_send_stream() yields Task(SUBMITTED) first and a
    TaskStatusUpdateEvent(COMPLETED) last — NOT a Task snapshot.

    Streaming and non-streaming have DIFFERENT terminal event types in
    a2a-sdk 1.1.2: on_message_send_stream() forwards status updates
    unchanged, only on_message_send() (non-streaming) replaces them with
    Task snapshots.
    """
    request = _build_send_request(workflow_id="wf-complete")
    call_context = ServerCallContext()

    events: list[Any] = []
    async for event in a2a_harness.handler.on_message_send_stream(
        request, call_context
    ):
        events.append(event)

    # First event: Task snapshot in SUBMITTED state.
    assert isinstance(events[0], Task)
    assert events[0].status.state == TaskState.TASK_STATE_SUBMITTED

    # Last event: TaskStatusUpdateEvent(COMPLETED) — NOT a Task.
    last_event = events[-1]
    assert isinstance(last_event, TaskStatusUpdateEvent)
    assert not isinstance(last_event, Task)
    assert last_event.status.state == TaskState.TASK_STATE_COMPLETED

    # Artifact events: two TEXT_CHUNKs + one WORKFLOW_END last_chunk marker.
    artifact_events = [ev for ev in events if isinstance(ev, TaskArtifactUpdateEvent)]
    assert len(artifact_events) == 3

    artifact_ids = {ev.artifact.artifact_id for ev in artifact_events}
    assert len(artifact_ids) == 1, (
        f"Expected one stable artifact_id across all chunks, got {artifact_ids}"
    )

    # First chunk creates the artifact (append=False); the second chunk
    # appends (append=True); the final WORKFLOW_END marker appends with
    # last_chunk=True.
    assert artifact_events[0].append is False
    assert artifact_events[0].last_chunk is False
    assert artifact_events[1].append is True
    assert artifact_events[1].last_chunk is False
    assert artifact_events[2].append is True
    assert artifact_events[2].last_chunk is True


# ---------------------------------------------------------------------------
# AC1: Unknown workflow_id reaches terminal FAILED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_workflow_id_reaches_failed_non_streaming(
    a2a_harness: _A2AHarness,
) -> None:
    """A workflow_id absent from the registry reaches TASK_STATE_FAILED
    via the non-streaming handler path.
    """
    request = _build_send_request(workflow_id="does-not-exist")
    call_context = ServerCallContext()

    result = await a2a_harness.handler.on_message_send(request, call_context)

    assert isinstance(result, Task)
    assert result.status.state == TaskState.TASK_STATE_FAILED


@pytest.mark.asyncio
async def test_unknown_workflow_id_reaches_failed_streaming(
    a2a_harness: _A2AHarness,
) -> None:
    """A workflow_id absent from the registry reaches a terminal
    TaskStatusUpdateEvent(FAILED) via the streaming handler path.
    """
    request = _build_send_request(workflow_id="does-not-exist")
    call_context = ServerCallContext()

    events: list[Any] = []
    async for event in a2a_harness.handler.on_message_send_stream(
        request, call_context
    ):
        events.append(event)

    last_event = events[-1]
    assert isinstance(last_event, TaskStatusUpdateEvent)
    assert last_event.status.state == TaskState.TASK_STATE_FAILED


# ---------------------------------------------------------------------------
# AC1: Text-only Part (missing workflow_id) reaches terminal FAILED cleanly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_only_message_missing_workflow_id_fails_cleanly(
    a2a_harness: _A2AHarness,
) -> None:
    """A Message with only a text Part (no DataPart, no workflow_id) does
    not crash the handler — it reaches TASK_STATE_FAILED with an
    informative message about the missing workflow_id.
    """
    request = _build_send_request(text_only=True)
    call_context = ServerCallContext()

    result = await a2a_harness.handler.on_message_send(request, call_context)

    assert isinstance(result, Task)
    assert result.status.state == TaskState.TASK_STATE_FAILED

    # The failure message should mention the missing workflow_id, not be
    # empty or generic — informative per the acceptance criteria.
    history_texts = [
        part.text
        for msg in result.history
        for part in msg.parts
        if part.HasField("text")
    ]
    assert any("workflow_id" in text for text in history_texts), (
        f"Expected an informative message mentioning 'workflow_id', "
        f"got history texts: {history_texts}"
    )


# ---------------------------------------------------------------------------
# AC6: Auth enforcement — 401 for bad/missing token, valid token dispatches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_bearer_token_returns_401(
    a2a_harness_with_auth: _A2AHarness,
) -> None:
    """POST /a2a with no Authorization header is rejected with 401.

    Exercises the ``_TestA2ABearerAuthMiddleware`` path-prefix check on
    ``/a2a`` with an empty/absent ``authorization`` header, mirroring the
    production ``_A2ABearerAuthMiddleware`` guard.
    """
    payload = _build_jsonrpc_send_payload("wf-complete")

    response = await a2a_harness_with_auth.client.post(
        "/a2a",
        json=payload,
        headers={a2a_constants.VERSION_HEADER: a2a_constants.PROTOCOL_VERSION_1_0},
    )

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


@pytest.mark.asyncio
async def test_invalid_bearer_token_returns_401(
    a2a_harness_with_auth: _A2AHarness,
) -> None:
    """POST /a2a with an incorrect bearer token is rejected with 401.

    Uses ``secrets.compare_digest`` under the hood (via the middleware),
    same as production — a token that does not match is always rejected
    regardless of how "close" it is to the real one.
    """
    payload = _build_jsonrpc_send_payload("wf-complete")

    response = await a2a_harness_with_auth.client.post(
        "/a2a",
        json=payload,
        headers={
            "Authorization": "Bearer wrong-token",
            a2a_constants.VERSION_HEADER: a2a_constants.PROTOCOL_VERSION_1_0,
        },
    )

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


@pytest.mark.asyncio
async def test_valid_bearer_token_dispatches_normally(
    a2a_harness_with_auth: _A2AHarness,
) -> None:
    """POST /a2a with the correct bearer token is NOT rejected by auth.

    AC6 requires proving the auth *gate* passes for a valid token — it
    does not require a full successful JSON-RPC round trip. Here we go
    one step further than the minimum bar and perform the full round
    trip: a valid token against a well-formed ``SendMessage`` JSON-RPC
    envelope reaches the real ``DefaultRequestHandler`` and completes the
    stubbed ``wf-complete`` workflow, returning HTTP 200 with a
    ``TASK_STATE_COMPLETED`` task in the JSON-RPC result. A non-401
    status code alone (e.g. 400/422 on a malformed body) would already be
    sufficient proof that the auth gate passed, since AC6 is about auth
    enforcement, not JSON-RPC correctness — but the full round trip is
    achievable here and gives a strictly stronger guarantee.
    """
    payload = _build_jsonrpc_send_payload("wf-complete")

    response = await a2a_harness_with_auth.client.post(
        "/a2a",
        json=payload,
        headers={
            "Authorization": f"Bearer {_AUTH_TEST_TOKEN}",
            a2a_constants.VERSION_HEADER: a2a_constants.PROTOCOL_VERSION_1_0,
        },
    )

    assert response.status_code != 401
    assert response.status_code == 200
    body = response.json()
    assert "error" not in body, f"Expected a JSON-RPC success result, got: {body}"
    assert body["result"]["task"]["status"]["state"] == "TASK_STATE_COMPLETED"


# ---------------------------------------------------------------------------
# AC7: Cancelling an ALREADY-ACTIVE task reaches terminal CANCELED
# ---------------------------------------------------------------------------
#
# Why this lives at the executor level rather than going through the ASGI /
# JSON-RPC layer like the rest of this module: the request handler's
# ``on_message_send`` / ``on_message_send_stream`` drive the executor loop to
# completion internally, so a task cannot be held in a genuinely non-terminal
# state from outside the handler. Cancelling requires an ACTIVE task, so the
# real ``BeddelA2AExecutor.execute()`` is driven directly as an in-flight
# asyncio task and paused mid-stream via ``_GatedWorkflowExecutor``.
#
# This is NOT a duplicate of ``test_server.py::TestBeddelA2AExecutor::
# test_cancel``. That test cancels a task that was never submitted (empty
# registry, no prior ``execute()``), which proves only that the cancel path
# emits CANCELED in isolation. AC7 requires proving that cancelling an
# ALREADY-ACTIVE task reaches terminal CANCELED *without re-submitting* the
# task — which needs a real prior ``execute()`` on the same task_id.


def _make_request_context(workflow_id: str) -> MagicMock:
    """Build a mock ``RequestContext`` carrying a DataPart with ``workflow_id``.

    Mirrors ``_make_request_context()`` in ``test_server.py`` — the proven
    pattern for driving ``BeddelA2AExecutor`` directly. ``RequestContext`` is
    the only mocked object here; the executor, ``EventQueue``, ``TaskUpdater``
    and every emitted event type are real a2a-sdk components.
    """
    ctx = MagicMock()
    ctx.task_id = str(uuid.uuid4())
    ctx.context_id = str(uuid.uuid4())

    data_value = Value()
    json_format.ParseDict({"workflow_id": workflow_id}, data_value)
    ctx.message = Message(
        role=Role.ROLE_USER,
        parts=[Part(data=data_value)],
        message_id=str(uuid.uuid4()),
    )
    return ctx


def _collect_events(event_queue: EventQueue) -> list[Any]:
    """Drain all currently-queued events from an ``EventQueue`` (non-blocking).

    Accesses the underlying ``asyncio.Queue`` via ``get_nowait()`` to avoid
    the blocking async ``dequeue_event`` — same approach as
    ``test_server.py::_collect_events``.
    """
    collected: list[Any] = []
    while True:
        try:
            # ``queue`` is only declared on the concrete EventQueueLegacy that
            # ``EventQueue()`` redirects to, not on the abstract base mypy
            # resolves here — same artifact as test_server.py's baseline.
            collected.append(event_queue.queue.get_nowait())  # type: ignore[attr-defined]
        except asyncio.QueueEmpty:
            break
    return collected


_TERMINAL_TASK_STATES = frozenset(
    {
        TaskState.TASK_STATE_COMPLETED,
        TaskState.TASK_STATE_FAILED,
        TaskState.TASK_STATE_CANCELED,
    }
)


class _GatedWorkflowExecutor:
    """Workflow-side stub whose event stream pauses mid-execution.

    Yields ``WORKFLOW_START``, signals :attr:`started`, then blocks forever on
    :attr:`release`. The pause happens *after* the consumer has processed
    ``WORKFLOW_START`` (an async generator only resumes once the consumer
    loops back around), so when :attr:`started` is set the task is guaranteed
    to be SUBMITTED + WORKING and not yet terminal — a genuinely ACTIVE task.

    Like ``_StubWorkflowExecutor``, this stubs only the *workflow* side; no
    a2a-sdk component is mocked.
    """

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def _stream(self) -> AsyncGenerator[BeddelEvent, None]:
        yield BeddelEvent(event_type=EventType.WORKFLOW_START, data={})
        self.started.set()
        await self.release.wait()
        yield BeddelEvent(event_type=EventType.WORKFLOW_END, data={})

    def execute_stream(
        self, workflow: Workflow, inputs: dict[str, Any] | None
    ) -> AsyncGenerator[BeddelEvent, None]:
        return self._stream()


@pytest.mark.asyncio
async def test_cancel_of_active_task_reaches_canceled_without_resubmitting() -> None:
    """Cancelling an already-active task reaches terminal CANCELED and does
    not re-submit the task (AC7).

    Sequence:
        1. ``execute()`` runs as an in-flight asyncio task and pauses
           mid-stream, leaving the task genuinely ACTIVE.
        2. The first drain proves the task really existed and was active:
           ``Task(SUBMITTED)`` followed by ``TaskStatusUpdateEvent(WORKING)``,
           with no terminal state yet.
        3. ``cancel()`` is called with the SAME context (same task_id /
           context_id) as the in-flight execution.
        4. The second drain proves exactly one new event — a
           ``TaskStatusUpdateEvent(CANCELED)`` addressed to that task — and
           NO second ``Task`` object and NO ``SUBMITTED`` status event, i.e.
           cancellation did not re-submit.
        5. Aborting the paused execution enqueues nothing further, so
           CANCELED stands as the terminal state.
    """
    gated = _GatedWorkflowExecutor()
    workflow = _make_workflow(wf_id="wf-cancel")
    registry: WorkflowRegistry = {"wf-cancel": (workflow, gated)}  # type: ignore[dict-item]
    executor = BeddelA2AExecutor(registry)

    ctx = _make_request_context("wf-cancel")
    # ``EventQueue()`` is typed abstract but redirects to the concrete
    # EventQueueLegacy at runtime (with a DeprecationWarning). This is the
    # established pattern across test_server.py's executor-level tests.
    event_queue = EventQueue()  # type: ignore[abstract]

    execute_task = asyncio.create_task(executor.execute(ctx, event_queue))
    try:
        await asyncio.wait_for(gated.started.wait(), timeout=5)

        # --- Step 2: the task is genuinely ACTIVE (submitted, not terminal).
        first_drain = _collect_events(event_queue)

        assert isinstance(first_drain[0], Task)
        assert first_drain[0].id == ctx.task_id
        assert first_drain[0].context_id == ctx.context_id
        assert first_drain[0].status.state == TaskState.TASK_STATE_SUBMITTED

        status_states = [
            ev.status.state
            for ev in first_drain[1:]
            if isinstance(ev, TaskStatusUpdateEvent)
        ]
        assert status_states == [TaskState.TASK_STATE_WORKING]
        assert not any(state in _TERMINAL_TASK_STATES for state in status_states), (
            f"Task must still be active before cancelling, got {status_states}"
        )

        # --- Step 3: cancel the SAME, still-active task.
        await executor.cancel(ctx, event_queue)

        # --- Step 4: exactly one CANCELED event, and no re-submission.
        second_drain = _collect_events(event_queue)

        assert len(second_drain) == 1, (
            f"cancel() must emit exactly one event, got {second_drain}"
        )
        cancel_event = second_drain[0]
        assert isinstance(cancel_event, TaskStatusUpdateEvent)
        assert cancel_event.status.state == TaskState.TASK_STATE_CANCELED
        assert cancel_event.task_id == ctx.task_id
        assert cancel_event.context_id == ctx.context_id

        # No new Task object: cancel() must not create/re-submit a task.
        assert not any(isinstance(ev, Task) for ev in second_drain)
        assert not any(
            isinstance(ev, TaskStatusUpdateEvent)
            and ev.status.state == TaskState.TASK_STATE_SUBMITTED
            for ev in second_drain
        )
    finally:
        # --- Step 5: abort the paused execution rather than releasing the
        # gate, so the workflow does not run on to COMPLETED after CANCELED —
        # matching real cancellation semantics.
        execute_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await execute_task

    assert _collect_events(event_queue) == [], (
        "Nothing may be enqueued after CANCELED — it is the terminal state"
    )
