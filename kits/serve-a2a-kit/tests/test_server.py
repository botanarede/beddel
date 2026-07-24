"""Unit tests for beddel_serve_a2a.server module (serve-a2a-kit).

Tests cover:
    - ``build_agent_card``: Agent Card generation from mock workflows.
    - ``BeddelA2AExecutor.execute``: Event mapping with mock workflow executor.
    - ``BeddelA2AExecutor.cancel``: Task cancellation.
    - ``DefaultRequestHandlerV2`` integration: real handler validation (F4).
    - Exact event sequence assertions (F5).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock

import pytest
from a2a.server.events import EventQueue
from a2a.types import (
    AgentCapabilities,
    AgentCard,
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

from beddel_serve_a2a.server import (
    BeddelA2AExecutor,
    WorkflowRegistry,
    build_agent_card,
)
from beddel.domain.models import (
    BeddelEvent,
    EventType,
    ExecutionStrategy,
    Step,
    StrategyType,
    Workflow,
)

# ---------------------------------------------------------------------------
# Fixtures
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
    wf_id: str = "wf-test",
    name: str = "Test Workflow",
    description: str = "A test workflow",
    steps: list[Step] | None = None,
) -> Workflow:
    """Create a minimal Workflow for testing."""
    return Workflow(
        id=wf_id,
        name=name,
        description=description,
        steps=steps or [_make_step()],
    )


def _make_request_context(
    workflow_id: str = "wf-test",
    inputs: dict[str, Any] | None = None,
    task_id: str | None = None,
    context_id: str | None = None,
) -> MagicMock:
    """Build a mock RequestContext with data Part-based message."""
    from google.protobuf.struct_pb2 import Value
    from google.protobuf import json_format

    ctx = MagicMock()
    ctx.task_id = task_id or str(uuid.uuid4())
    ctx.context_id = context_id or str(uuid.uuid4())

    data: dict[str, Any] = {"workflow_id": workflow_id}
    if inputs is not None:
        data["inputs"] = inputs

    # In a2a-sdk 1.x, Part uses the `data` field (google.protobuf.Value)
    value = Value()
    json_format.ParseDict(data, value)

    ctx.message = Message(
        role=Role.ROLE_USER,
        parts=[Part(data=value)],
        message_id=str(uuid.uuid4()),
    )
    return ctx


# ---------------------------------------------------------------------------
# build_agent_card tests
# ---------------------------------------------------------------------------


class TestBuildAgentCard:
    """Tests for :func:`build_agent_card`."""

    def test_empty_workflows(self) -> None:
        """Card with no workflows has empty skills list."""
        card = build_agent_card({})
        assert card.name == "Beddel Agent"
        assert card.skills == []
        assert card.capabilities is not None
        assert card.capabilities.streaming is True

    def test_single_workflow_becomes_skill(self) -> None:
        """A single workflow maps to one AgentSkill."""
        wf = _make_workflow(wf_id="my-wf", name="My Workflow", description="Does stuff")
        registry: dict[str, tuple[Workflow, Any]] = {"my-wf": (wf, MagicMock())}

        card = build_agent_card(registry)

        assert len(card.skills) == 1
        skill = card.skills[0]
        assert skill.id == "my-wf"
        assert skill.name == "My Workflow"
        assert skill.description == "Does stuff"
        assert "workflow" in skill.tags
        assert "llm" in skill.tags  # first step primitive

    def test_multiple_workflows(self) -> None:
        """Multiple workflows produce multiple skills."""
        wf1 = _make_workflow(
            wf_id="wf-a", name="Alpha", steps=[_make_step(primitive="llm")]
        )
        wf2 = _make_workflow(
            wf_id="wf-b", name="Beta", steps=[_make_step(primitive="tool")]
        )
        registry: dict[str, tuple[Workflow, Any]] = {
            "wf-a": (wf1, MagicMock()),
            "wf-b": (wf2, MagicMock()),
        }

        card = build_agent_card(registry, public_base_url="http://0.0.0.0:9000")

        assert len(card.skills) == 2
        # URL is now in supported_interfaces with /a2a suffix
        # 0.0.0.0 is defensively replaced with 127.0.0.1 in the card
        assert len(card.supported_interfaces) == 1
        assert card.supported_interfaces[0].url == "http://127.0.0.1:9000/a2a"
        assert card.supported_interfaces[0].protocol_binding == "JSONRPC"
        assert card.supported_interfaces[0].protocol_version == "1.0"
        ids = {s.id for s in card.skills}
        assert ids == {"wf-a", "wf-b"}

    def test_workflow_without_description_gets_default(self) -> None:
        """Workflow with empty description gets a generated one."""
        wf = _make_workflow(wf_id="wf-x", name="X Flow", description="")
        registry: dict[str, tuple[Workflow, Any]] = {"wf-x": (wf, MagicMock())}

        card = build_agent_card(registry)
        skill = card.skills[0]
        assert "Execute workflow: X Flow" in skill.description

    def test_card_metadata(self) -> None:
        """Card has correct version and output modes."""
        card = build_agent_card({})
        assert card.version == "1.0.0"
        assert "text/plain" in card.default_input_modes
        assert "text/plain" in card.default_output_modes

    def test_protocol_binding_and_version(self) -> None:
        """Card interface has correct protocol binding and version."""
        card = build_agent_card({})
        iface = card.supported_interfaces[0]
        assert iface.protocol_binding == "JSONRPC"
        assert iface.protocol_version == "1.0"

    def test_interface_url_uses_public_base_url(self) -> None:
        """Interface URL is public_base_url + /a2a."""
        card = build_agent_card({}, public_base_url="http://myhost:9000")
        assert card.supported_interfaces[0].url == "http://myhost:9000/a2a"

    def test_interface_url_strips_trailing_slash(self) -> None:
        """Trailing slash in public_base_url is stripped before /a2a."""
        card = build_agent_card({}, public_base_url="http://example.com/")
        assert card.supported_interfaces[0].url == "http://example.com/a2a"

    def test_provider_field(self) -> None:
        """Card has provider with organization and URL."""
        card = build_agent_card({})
        assert card.provider is not None
        assert card.provider.organization == "Beddel"
        assert card.provider.url == "https://github.com/botanarede/beddel"

    def test_proto_json_serialization_camel_case(self) -> None:
        """ProtoJSON serialization uses camelCase field names."""
        import json

        from google.protobuf.json_format import MessageToJson

        wf = _make_workflow(wf_id="wf-1", name="Test")
        registry: dict[str, tuple[Workflow, Any]] = {"wf-1": (wf, MagicMock())}
        card = build_agent_card(registry)

        json_str = MessageToJson(card)
        data = json.loads(json_str)

        # Check camelCase keys
        assert "supportedInterfaces" in data
        iface = data["supportedInterfaces"][0]
        assert "protocolBinding" in iface
        assert "protocolVersion" in iface
        assert iface["protocolBinding"] == "JSONRPC"
        assert iface["protocolVersion"] == "1.0"

    @pytest.mark.asyncio
    async def test_a2a_card_resolver_parses_card(self) -> None:
        """A2ACardResolver can parse the card served as JSON."""
        import json
        from unittest.mock import AsyncMock

        import httpx
        from a2a.client import A2ACardResolver
        from google.protobuf.json_format import MessageToJson

        wf = _make_workflow(wf_id="wf-resolver", name="Resolver Test")
        registry: dict[str, tuple[Workflow, Any]] = {"wf-resolver": (wf, MagicMock())}
        card = build_agent_card(registry, public_base_url="http://localhost:8000")

        # Serialize to ProtoJSON (camelCase) then parse back as dict
        card_json_str = MessageToJson(card)
        card_dict = json.loads(card_json_str)

        # Mock httpx response with .json() returning the dict
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = card_dict
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        resolver = A2ACardResolver(
            httpx_client=mock_client,
            base_url="http://localhost:8000",
        )
        parsed = await resolver.get_agent_card()

        assert parsed.name == "Beddel Agent"
        assert parsed.supported_interfaces[0].protocol_binding == "JSONRPC"
        assert parsed.supported_interfaces[0].url == "http://localhost:8000/a2a"
        assert len(parsed.skills) == 1
        assert parsed.skills[0].id == "wf-resolver"

    def test_no_secrets_in_card(self) -> None:
        """Card JSON does not contain common secret patterns."""
        from google.protobuf.json_format import MessageToJson

        wf = _make_workflow(wf_id="wf-sec", name="Secure")
        registry: dict[str, tuple[Workflow, Any]] = {"wf-sec": (wf, MagicMock())}
        card = build_agent_card(registry)

        json_str = MessageToJson(card)
        json_lower = json_str.lower()

        for pattern in ["token", "secret", "password", "api_key", "apikey"]:
            assert pattern not in json_lower, f"Found '{pattern}' in card JSON"

    def test_empty_workflow_id_raises_value_error(self) -> None:
        """Empty workflow ID raises ValueError."""
        wf = _make_workflow(wf_id="", name="Valid Name")
        registry: dict[str, tuple[Workflow, Any]] = {"": (wf, MagicMock())}

        with pytest.raises(ValueError, match="workflow ID is empty"):
            build_agent_card(registry)

    def test_whitespace_workflow_id_raises_value_error(self) -> None:
        """Whitespace-only workflow ID raises ValueError."""
        wf = _make_workflow(wf_id="  ", name="Valid Name")
        registry: dict[str, tuple[Workflow, Any]] = {"  ": (wf, MagicMock())}

        with pytest.raises(ValueError, match="workflow ID is empty"):
            build_agent_card(registry)

    def test_empty_workflow_name_raises_value_error(self) -> None:
        """Empty workflow name raises ValueError."""
        wf = _make_workflow(wf_id="wf-valid", name="")
        registry: dict[str, tuple[Workflow, Any]] = {"wf-valid": (wf, MagicMock())}

        with pytest.raises(ValueError, match="workflow name is empty"):
            build_agent_card(registry)

    def test_whitespace_workflow_name_raises_value_error(self) -> None:
        """Whitespace-only workflow name raises ValueError."""
        wf = _make_workflow(wf_id="wf-valid", name="   ")
        registry: dict[str, tuple[Workflow, Any]] = {"wf-valid": (wf, MagicMock())}

        with pytest.raises(ValueError, match="workflow name is empty"):
            build_agent_card(registry)


# ---------------------------------------------------------------------------
# BeddelA2AExecutor tests — direct EventQueue validation
# ---------------------------------------------------------------------------


async def _mock_execute_stream(
    events: list[BeddelEvent],
) -> AsyncGenerator[BeddelEvent, None]:
    """Yield a pre-built list of BeddelEvents as an async generator."""
    for event in events:
        yield event


def _collect_events(eq: EventQueue) -> list[Any]:
    """Drain all events from an EventQueue (non-blocking).

    Accesses the underlying ``asyncio.Queue`` directly via ``get_nowait()``
    to avoid calling the async ``dequeue_event`` method.
    """
    collected: list[Any] = []
    while True:
        try:
            ev = eq.queue.get_nowait()
            collected.append(ev)
        except asyncio.QueueEmpty:
            break
    return collected


class TestBeddelA2AExecutor:
    """Tests for :class:`BeddelA2AExecutor` — direct event queue assertions."""

    @pytest.mark.asyncio
    async def test_execute_happy_path(self) -> None:
        """Full workflow lifecycle: Task → WORKING → artifacts → COMPLETED."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        events = [
            BeddelEvent(
                event_type=EventType.WORKFLOW_START, data={"workflow_id": "wf-test"}
            ),
            BeddelEvent(
                event_type=EventType.STEP_START,
                step_id="step-1",
                data={"primitive": "llm"},
            ),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "Hello "},
            ),
            BeddelEvent(
                event_type=EventType.STEP_END,
                step_id="step-1",
                data={"result": "Hello World"},
            ),
            BeddelEvent(
                event_type=EventType.WORKFLOW_END, data={"workflow_id": "wf-test"}
            ),
        ]
        mock_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        mock_executor.execute_stream.assert_called_once_with(wf, None)

        collected = _collect_events(eq)

        # F1/F5: First event MUST be a Task object with SUBMITTED state
        assert isinstance(collected[0], Task)
        assert collected[0].id == ctx.task_id
        assert collected[0].context_id == ctx.context_id
        assert collected[0].status.state == TaskState.TASK_STATE_SUBMITTED

        # Extract status and artifact events
        status_events = [
            ev for ev in collected[1:] if isinstance(ev, TaskStatusUpdateEvent)
        ]
        artifact_events = [
            ev for ev in collected[1:] if isinstance(ev, TaskArtifactUpdateEvent)
        ]

        # F5: Verify exact status sequence: WORKING, WORKING, COMPLETED
        status_states = [ev.status.state for ev in status_events]
        assert status_states == [
            TaskState.TASK_STATE_WORKING,  # WORKFLOW_START → start_work
            TaskState.TASK_STATE_WORKING,  # STEP_START → update_status(WORKING)
            TaskState.TASK_STATE_COMPLETED,  # WORKFLOW_END → complete
        ]

        # F5: Verify artifacts: TEXT_CHUNK + STEP_END + last_chunk marker
        assert len(artifact_events) == 3
        # TEXT_CHUNK artifact
        assert artifact_events[0].append is False
        # STEP_END artifact has different ID from streaming artifact
        assert (
            artifact_events[1].artifact.artifact_id
            != artifact_events[0].artifact.artifact_id
        )
        assert artifact_events[1].append is False
        # last_chunk marker
        assert artifact_events[2].last_chunk is True
        assert (
            artifact_events[2].artifact.artifact_id
            == artifact_events[0].artifact.artifact_id
        )

        # F5: No events after terminal COMPLETED
        completed_idx = next(
            i
            for i, ev in enumerate(collected)
            if isinstance(ev, TaskStatusUpdateEvent)
            and ev.status.state == TaskState.TASK_STATE_COMPLETED
        )
        assert completed_idx == len(collected) - 1

    @pytest.mark.asyncio
    async def test_execute_missing_workflow_id(self) -> None:
        """Missing workflow_id: Task → FAILED (exactly 2 events)."""
        registry: WorkflowRegistry = {}
        executor = BeddelA2AExecutor(registry)

        ctx = MagicMock()
        ctx.task_id = str(uuid.uuid4())
        ctx.context_id = str(uuid.uuid4())
        ctx.message = Message(
            role=Role.ROLE_USER,
            parts=[Part(text="just text")],
            message_id=str(uuid.uuid4()),
        )

        eq = EventQueue()
        await executor.execute(ctx, eq)

        collected = _collect_events(eq)
        # F5: Exact sequence: Task(SUBMITTED) → TaskStatusUpdateEvent(FAILED)
        assert len(collected) == 2
        assert isinstance(collected[0], Task)
        assert collected[0].status.state == TaskState.TASK_STATE_SUBMITTED
        assert isinstance(collected[1], TaskStatusUpdateEvent)
        assert collected[1].status.state == TaskState.TASK_STATE_FAILED

    @pytest.mark.asyncio
    async def test_execute_unknown_workflow(self) -> None:
        """Unknown workflow_id: Task → FAILED (exactly 2 events)."""
        registry: WorkflowRegistry = {}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="nonexistent")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)
        # F5: Exact sequence: Task(SUBMITTED) → TaskStatusUpdateEvent(FAILED)
        assert len(collected) == 2
        assert isinstance(collected[0], Task)
        assert collected[0].status.state == TaskState.TASK_STATE_SUBMITTED
        assert isinstance(collected[1], TaskStatusUpdateEvent)
        assert collected[1].status.state == TaskState.TASK_STATE_FAILED

    @pytest.mark.asyncio
    async def test_execute_with_inputs(self) -> None:
        """Inputs from DataPart are forwarded to execute_stream."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        events = [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
        ]
        mock_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(
            workflow_id="wf-test",
            inputs={"topic": "AI agents"},
        )
        eq = EventQueue()

        await executor.execute(ctx, eq)

        mock_executor.execute_stream.assert_called_once_with(wf, {"topic": "AI agents"})

        collected = _collect_events(eq)
        assert isinstance(collected[0], Task)
        assert collected[0].status.state == TaskState.TASK_STATE_SUBMITTED

    @pytest.mark.asyncio
    async def test_execute_error_event_is_non_terminal(self) -> None:
        """ERROR event is non-terminal (recoverable); task fails on stream end."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        events = [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.ERROR,
                step_id="step-1",
                data={"error": "LLM timeout"},
            ),
            # Stream exhausts without WORKFLOW_END — fallback fails the task
        ]
        mock_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)
        # Sequence: Task(SUBMITTED) → WORKING → WORKING(diagnostic) → FAILED
        assert len(collected) == 4
        assert isinstance(collected[0], Task)
        assert collected[0].status.state == TaskState.TASK_STATE_SUBMITTED
        assert isinstance(collected[1], TaskStatusUpdateEvent)
        assert collected[1].status.state == TaskState.TASK_STATE_WORKING
        # ERROR diagnostic (non-terminal)
        assert isinstance(collected[2], TaskStatusUpdateEvent)
        assert collected[2].status.state == TaskState.TASK_STATE_WORKING
        # Stream exhaustion fallback
        assert isinstance(collected[3], TaskStatusUpdateEvent)
        assert collected[3].status.state == TaskState.TASK_STATE_FAILED

    @pytest.mark.asyncio
    async def test_execute_exception_in_stream(self) -> None:
        """Exception during streaming: Task → WORKING → FAILED (exact)."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        async def _failing_stream(
            _wf: Any, _inputs: Any
        ) -> AsyncGenerator[BeddelEvent, None]:
            yield BeddelEvent(event_type=EventType.WORKFLOW_START, data={})
            raise RuntimeError("boom")

        mock_executor.execute_stream = MagicMock(
            side_effect=lambda wf, inputs: _failing_stream(wf, inputs),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)
        # F5: Exact sequence: Task(SUBMITTED) → WORKING → FAILED
        assert len(collected) == 3
        assert isinstance(collected[0], Task)
        assert collected[0].status.state == TaskState.TASK_STATE_SUBMITTED
        assert isinstance(collected[1], TaskStatusUpdateEvent)
        assert collected[1].status.state == TaskState.TASK_STATE_WORKING
        assert isinstance(collected[2], TaskStatusUpdateEvent)
        assert collected[2].status.state == TaskState.TASK_STATE_FAILED

    @pytest.mark.asyncio
    async def test_cancel(self) -> None:
        """Cancel emits only CANCELED (no SUBMITTED — task already exists)."""
        registry: WorkflowRegistry = {}
        executor = BeddelA2AExecutor(registry)

        ctx = MagicMock()
        ctx.task_id = str(uuid.uuid4())
        ctx.context_id = str(uuid.uuid4())

        eq = EventQueue()
        await executor.cancel(ctx, eq)

        collected = _collect_events(eq)
        # F3/F5: Cancel emits exactly one event: CANCELED
        assert len(collected) == 1
        assert isinstance(collected[0], TaskStatusUpdateEvent)
        assert collected[0].status.state == TaskState.TASK_STATE_CANCELED

    @pytest.mark.asyncio
    async def test_streaming_stable_artifact_id(self) -> None:
        """All TEXT_CHUNK events share one stable artifact ID with correct flags."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        events = [
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
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "!"},
            ),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
        ]
        mock_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)
        # First event is Task
        assert isinstance(collected[0], Task)
        assert collected[0].status.state == TaskState.TASK_STATE_SUBMITTED

        # Filter artifact events
        artifact_events = [
            ev for ev in collected if isinstance(ev, TaskArtifactUpdateEvent)
        ]
        # F5: Exactly 3 TEXT_CHUNKs + 1 last_chunk marker = 4 artifact events
        assert len(artifact_events) == 4

        # All artifact events share the same artifact_id
        artifact_ids = {ev.artifact.artifact_id for ev in artifact_events}
        assert len(artifact_ids) == 1, (
            f"Expected single stable artifact ID, got {artifact_ids}"
        )

        # F5: First has append=False, middle have append=True, last has last_chunk=True
        assert artifact_events[0].append is False
        assert artifact_events[1].append is True
        assert artifact_events[2].append is True
        assert artifact_events[3].append is True
        assert artifact_events[3].last_chunk is True

        # F5: No events after terminal COMPLETED
        completed_idx = next(
            i
            for i, ev in enumerate(collected)
            if isinstance(ev, TaskStatusUpdateEvent)
            and ev.status.state == TaskState.TASK_STATE_COMPLETED
        )
        assert completed_idx == len(collected) - 1

    @pytest.mark.asyncio
    async def test_workflow_end_emits_last_chunk(self) -> None:
        """WORKFLOW_END emits last_chunk=True marker when streaming was active."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        events = [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "content"},
            ),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
        ]
        mock_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)
        assert isinstance(collected[0], Task)
        assert collected[0].status.state == TaskState.TASK_STATE_SUBMITTED

        artifact_events = [
            ev for ev in collected if isinstance(ev, TaskArtifactUpdateEvent)
        ]
        # F5: Exactly 2 artifacts: initial chunk (append=False) + final marker (last_chunk=True)
        assert len(artifact_events) == 2
        assert artifact_events[0].append is False
        assert artifact_events[1].last_chunk is True
        assert artifact_events[1].append is True

        # Same artifact ID
        assert (
            artifact_events[0].artifact.artifact_id
            == artifact_events[1].artifact.artifact_id
        )

    @pytest.mark.asyncio
    async def test_workflow_end_no_streaming_no_last_chunk(self) -> None:
        """WORKFLOW_END without prior streaming does NOT emit last_chunk artifact."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        events = [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
        ]
        mock_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)
        artifact_events = [
            ev for ev in collected if isinstance(ev, TaskArtifactUpdateEvent)
        ]
        assert len(artifact_events) == 0

    @pytest.mark.asyncio
    async def test_no_events_after_terminal(self) -> None:
        """After WORKFLOW_END (terminal), further events are NOT processed."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        events = [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
            # These should NOT be processed because WORKFLOW_END is terminal
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "ghost"},
            ),
            BeddelEvent(
                event_type=EventType.STEP_END,
                step_id="step-1",
                data={"result": "ghost"},
            ),
        ]
        mock_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)
        # Exact sequence: Task(SUBMITTED) → WORKING → COMPLETED
        assert len(collected) == 3
        assert isinstance(collected[0], Task)
        assert collected[0].status.state == TaskState.TASK_STATE_SUBMITTED
        assert isinstance(collected[1], TaskStatusUpdateEvent)
        assert collected[1].status.state == TaskState.TASK_STATE_WORKING
        assert isinstance(collected[2], TaskStatusUpdateEvent)
        assert collected[2].status.state == TaskState.TASK_STATE_COMPLETED
        # No artifact events from ghost events after terminal
        artifact_events = [
            ev for ev in collected if isinstance(ev, TaskArtifactUpdateEvent)
        ]
        assert len(artifact_events) == 0

    @pytest.mark.asyncio
    async def test_step_end_artifact_distinct_from_streaming(self) -> None:
        """STEP_END artifact ID is distinct from streaming TEXT_CHUNK artifact ID."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        events = [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "streamed text"},
            ),
            BeddelEvent(
                event_type=EventType.STEP_END,
                step_id="step-1",
                data={"result": "step result"},
            ),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
        ]
        mock_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)
        artifact_events = [
            ev for ev in collected if isinstance(ev, TaskArtifactUpdateEvent)
        ]

        # TEXT_CHUNK artifact, STEP_END artifact, last_chunk marker
        assert len(artifact_events) == 3

        stream_id = artifact_events[0].artifact.artifact_id
        step_id = artifact_events[1].artifact.artifact_id
        marker_id = artifact_events[2].artifact.artifact_id

        # STEP_END has distinct ID from streaming
        assert step_id != stream_id
        # last_chunk marker shares the streaming ID
        assert marker_id == stream_id
        # STEP_END artifact has name set to step_id
        assert artifact_events[1].artifact.name == "step-1"

    @pytest.mark.asyncio
    async def test_empty_stream_fails_task(self) -> None:
        """Empty stream (no events) results in FAILED terminal state (F2)."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        events: list[BeddelEvent] = []
        mock_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)
        # F2: Task(SUBMITTED) → FAILED (stream ended without terminal)
        assert len(collected) == 2
        assert isinstance(collected[0], Task)
        assert collected[0].status.state == TaskState.TASK_STATE_SUBMITTED
        assert isinstance(collected[1], TaskStatusUpdateEvent)
        assert collected[1].status.state == TaskState.TASK_STATE_FAILED

    @pytest.mark.asyncio
    async def test_nonterminal_stream_exhaustion_fails_task(self) -> None:
        """Stream with only nonterminal events results in FAILED (F2)."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        events = [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "partial"},
            ),
            # No WORKFLOW_END or ERROR — stream just ends
        ]
        mock_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)
        # Last event must be FAILED
        assert isinstance(collected[-1], TaskStatusUpdateEvent)
        assert collected[-1].status.state == TaskState.TASK_STATE_FAILED

        # Should NOT have COMPLETED
        states = [
            ev.status.state for ev in collected if isinstance(ev, TaskStatusUpdateEvent)
        ]
        assert TaskState.TASK_STATE_COMPLETED not in states

    @pytest.mark.asyncio
    async def test_recoverable_skip_error_continues_to_completion(self) -> None:
        """SKIP strategy: ERROR is non-terminal, workflow completes (F2 regression)."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        # Simulates SKIP strategy: ERROR emitted, then stream continues
        events = [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.STEP_START,
                step_id="skip-step",
                data={"primitive": "llm"},
            ),
            BeddelEvent(
                event_type=EventType.ERROR,
                step_id="skip-step",
                data={"error": "LLM timeout — skipping"},
            ),
            # Stream continues after ERROR (SKIP strategy)
            BeddelEvent(
                event_type=EventType.STEP_START,
                step_id="step-2",
                data={"primitive": "tool"},
            ),
            BeddelEvent(
                event_type=EventType.STEP_END,
                step_id="step-2",
                data={"result": "tool output"},
            ),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
        ]
        mock_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)

        # First event is Task(SUBMITTED)
        assert isinstance(collected[0], Task)
        assert collected[0].status.state == TaskState.TASK_STATE_SUBMITTED

        # Last status event must be COMPLETED (not FAILED)
        status_events = [
            ev for ev in collected if isinstance(ev, TaskStatusUpdateEvent)
        ]
        assert status_events[-1].status.state == TaskState.TASK_STATE_COMPLETED

        # FAILED should NOT appear anywhere
        states = [ev.status.state for ev in status_events]
        assert TaskState.TASK_STATE_FAILED not in states

    @pytest.mark.asyncio
    async def test_recoverable_retry_error_continues_to_completion(self) -> None:
        """RETRY strategy: ERROR+RETRY then success, workflow completes (F2)."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        # Simulates RETRY strategy: ERROR → RETRY → success → WORKFLOW_END
        events = [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.STEP_START,
                step_id="retry-step",
                data={"primitive": "llm"},
            ),
            BeddelEvent(
                event_type=EventType.ERROR,
                step_id="retry-step",
                data={"error": "transient failure attempt 1"},
            ),
            BeddelEvent(
                event_type=EventType.RETRY,
                step_id="retry-step",
                data={"attempt": 2},
            ),
            BeddelEvent(
                event_type=EventType.ERROR,
                step_id="retry-step",
                data={"error": "transient failure attempt 2"},
            ),
            BeddelEvent(
                event_type=EventType.RETRY,
                step_id="retry-step",
                data={"attempt": 3},
            ),
            BeddelEvent(
                event_type=EventType.STEP_END,
                step_id="retry-step",
                data={"result": "success on attempt 3"},
            ),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
        ]
        mock_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)

        # First event is Task(SUBMITTED)
        assert isinstance(collected[0], Task)
        assert collected[0].status.state == TaskState.TASK_STATE_SUBMITTED

        # Last status event must be COMPLETED
        status_events = [
            ev for ev in collected if isinstance(ev, TaskStatusUpdateEvent)
        ]
        assert status_events[-1].status.state == TaskState.TASK_STATE_COMPLETED

        # FAILED should NOT appear
        states = [ev.status.state for ev in status_events]
        assert TaskState.TASK_STATE_FAILED not in states

        # Verify STEP_END artifact is present
        artifact_events = [
            ev for ev in collected if isinstance(ev, TaskArtifactUpdateEvent)
        ]
        assert len(artifact_events) >= 1
        # Step result artifact should contain the success text
        step_artifact = artifact_events[0]
        assert step_artifact.artifact.parts[0].text == "success on attempt 3"

    @pytest.mark.asyncio
    async def test_fatal_exception_after_error_fails_task(self) -> None:
        """FAIL strategy: ERROR emitted then exception raised → FAILED (F2)."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        async def _fail_strategy_stream(
            _wf: Any, _inputs: Any
        ) -> AsyncGenerator[BeddelEvent, None]:
            yield BeddelEvent(event_type=EventType.WORKFLOW_START, data={})
            yield BeddelEvent(
                event_type=EventType.ERROR,
                step_id="fail-step",
                data={"error": "fatal failure"},
            )
            # FAIL strategy raises exception after ERROR event
            from beddel.domain.errors import ExecutionError

            raise ExecutionError("fatal failure")

        mock_executor.execute_stream = MagicMock(
            side_effect=lambda wf, inputs: _fail_strategy_stream(wf, inputs),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)

        # First event is Task(SUBMITTED)
        assert isinstance(collected[0], Task)
        assert collected[0].status.state == TaskState.TASK_STATE_SUBMITTED

        # Last event must be FAILED (from exception handler)
        status_events = [
            ev for ev in collected if isinstance(ev, TaskStatusUpdateEvent)
        ]
        assert status_events[-1].status.state == TaskState.TASK_STATE_FAILED

    @pytest.mark.asyncio
    async def test_text_chunk_uses_text_key(self) -> None:
        """TEXT_CHUNK reads 'text' key from event data (F1 regression)."""
        wf = _make_workflow()
        mock_executor = MagicMock()

        events = [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "real content from executor"},
            ),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
        ]
        mock_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_executor)}
        executor = BeddelA2AExecutor(registry)

        ctx = _make_request_context(workflow_id="wf-test")
        eq = EventQueue()

        await executor.execute(ctx, eq)

        collected = _collect_events(eq)
        artifact_events = [
            ev for ev in collected if isinstance(ev, TaskArtifactUpdateEvent)
        ]
        # First artifact has the actual text content (not empty)
        assert len(artifact_events) >= 1
        first_artifact = artifact_events[0]
        assert first_artifact.artifact.parts[0].text == "real content from executor"


# ---------------------------------------------------------------------------
# DefaultRequestHandlerV2 integration tests (F4)
# ---------------------------------------------------------------------------


def _build_agent_card_for_test() -> AgentCard:
    """Build a minimal AgentCard for handler tests."""
    return AgentCard(
        name="Test Agent",
        description="Test",
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
    )


def _build_send_request(
    workflow_id: str | None = None, text_only: bool = False
) -> SendMessageRequest:
    """Build a SendMessageRequest for handler tests."""
    from google.protobuf.struct_pb2 import Value
    from google.protobuf import json_format as pbjf

    if text_only:
        return SendMessageRequest(
            message=Message(
                role=Role.ROLE_USER,
                parts=[Part(text="no data part")],
                message_id=str(uuid.uuid4()),
            ),
            configuration=SendMessageConfiguration(),
        )

    data_value = Value()
    pbjf.ParseDict({"workflow_id": workflow_id or "wf-test"}, data_value)

    return SendMessageRequest(
        message=Message(
            role=Role.ROLE_USER,
            parts=[Part(data=data_value)],
            message_id=str(uuid.uuid4()),
        ),
        configuration=SendMessageConfiguration(),
    )


class TestExecutorWithDefaultHandler:
    """Integration tests running BeddelA2AExecutor through the real SDK handler.

    These tests verify that the executor's event stream does NOT trigger
    ``InvalidAgentResponseError`` when processed by the SDK's
    ``DefaultRequestHandlerV2`` → ``ActiveTask`` → ``EventConsumer`` pipeline.

    This addresses Sol review finding F4.
    """

    @pytest.mark.asyncio
    async def test_send_message_happy_path_no_invalid_agent_error(self) -> None:
        """Full workflow through DefaultRequestHandlerV2 completes without error."""
        from a2a.server.request_handlers.default_request_handler_v2 import (
            DefaultRequestHandlerV2,
        )
        from a2a.server.tasks import InMemoryTaskStore
        from a2a.server.agent_execution.context import ServerCallContext

        wf = _make_workflow()
        mock_wf_executor = MagicMock()

        events = [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "Hello"},
            ),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
        ]
        mock_wf_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_wf_executor)}
        executor = BeddelA2AExecutor(registry)
        task_store = InMemoryTaskStore()

        handler = DefaultRequestHandlerV2(
            agent_executor=executor,
            task_store=task_store,
            agent_card=_build_agent_card_for_test(),
        )

        request = _build_send_request(workflow_id="wf-test")
        call_context = ServerCallContext()

        # This should NOT raise InvalidAgentResponseError
        result = await handler.on_message_send(request, call_context)

        # Result should be a Task in terminal state
        assert isinstance(result, Task)
        assert result.status.state == TaskState.TASK_STATE_COMPLETED

        # Verify task is persisted in store
        stored_task = await task_store.get(result.id, call_context)
        assert stored_task is not None
        assert stored_task.status.state == TaskState.TASK_STATE_COMPLETED

    @pytest.mark.asyncio
    async def test_send_message_error_path_no_invalid_agent_error(self) -> None:
        """Error workflow through DefaultRequestHandlerV2 reaches FAILED cleanly."""
        from a2a.server.request_handlers.default_request_handler_v2 import (
            DefaultRequestHandlerV2,
        )
        from a2a.server.tasks import InMemoryTaskStore
        from a2a.server.agent_execution.context import ServerCallContext

        wf = _make_workflow()
        mock_wf_executor = MagicMock()

        events = [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.ERROR,
                step_id="step-1",
                data={"error": "timeout"},
            ),
        ]
        mock_wf_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_wf_executor)}
        executor = BeddelA2AExecutor(registry)
        task_store = InMemoryTaskStore()

        handler = DefaultRequestHandlerV2(
            agent_executor=executor,
            task_store=task_store,
            agent_card=_build_agent_card_for_test(),
        )

        request = _build_send_request(workflow_id="wf-test")
        call_context = ServerCallContext()

        result = await handler.on_message_send(request, call_context)

        assert isinstance(result, Task)
        assert result.status.state == TaskState.TASK_STATE_FAILED

    @pytest.mark.asyncio
    async def test_send_message_missing_workflow_no_invalid_agent_error(self) -> None:
        """Missing workflow_id through handler reaches FAILED cleanly."""
        from a2a.server.request_handlers.default_request_handler_v2 import (
            DefaultRequestHandlerV2,
        )
        from a2a.server.tasks import InMemoryTaskStore
        from a2a.server.agent_execution.context import ServerCallContext

        registry: WorkflowRegistry = {}
        executor = BeddelA2AExecutor(registry)
        task_store = InMemoryTaskStore()

        handler = DefaultRequestHandlerV2(
            agent_executor=executor,
            task_store=task_store,
            agent_card=_build_agent_card_for_test(),
        )

        request = _build_send_request(text_only=True)
        call_context = ServerCallContext()

        result = await handler.on_message_send(request, call_context)

        assert isinstance(result, Task)
        assert result.status.state == TaskState.TASK_STATE_FAILED

    @pytest.mark.asyncio
    async def test_send_message_streaming_via_handler(self) -> None:
        """Streaming via on_message_send_stream() validates SSE event sequence."""
        from a2a.server.request_handlers.default_request_handler_v2 import (
            DefaultRequestHandlerV2,
        )
        from a2a.server.tasks import InMemoryTaskStore
        from a2a.server.agent_execution.context import ServerCallContext

        wf = _make_workflow()
        mock_wf_executor = MagicMock()

        events = [
            BeddelEvent(event_type=EventType.WORKFLOW_START, data={}),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "chunk1"},
            ),
            BeddelEvent(
                event_type=EventType.TEXT_CHUNK,
                step_id="step-1",
                data={"text": "chunk2"},
            ),
            BeddelEvent(event_type=EventType.WORKFLOW_END, data={}),
        ]
        mock_wf_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_wf_executor)}
        executor = BeddelA2AExecutor(registry)
        task_store = InMemoryTaskStore()

        handler = DefaultRequestHandlerV2(
            agent_executor=executor,
            task_store=task_store,
            agent_card=_build_agent_card_for_test(),
        )

        request = _build_send_request(workflow_id="wf-test")
        call_context = ServerCallContext()

        # F4: Use on_message_send_stream() — the actual SSE path
        sse_events: list[Any] = []
        async for event in handler.on_message_send_stream(request, call_context):
            sse_events.append(event)

        # First SSE event should be the initial Task (SUBMITTED)
        assert isinstance(sse_events[0], Task)
        assert sse_events[0].status.state == TaskState.TASK_STATE_SUBMITTED

        # Last event should be terminal (Task with COMPLETED state)
        last_event = sse_events[-1]
        assert isinstance(last_event, Task)
        assert last_event.status.state == TaskState.TASK_STATE_COMPLETED

        # Verify artifact events are present with stable IDs
        artifact_events = [
            ev for ev in sse_events if isinstance(ev, TaskArtifactUpdateEvent)
        ]
        assert len(artifact_events) >= 2  # At least 2 chunks + last_chunk marker

        # All artifact events share one stable artifact ID
        artifact_ids = {ev.artifact.artifact_id for ev in artifact_events}
        assert len(artifact_ids) == 1

        # Verify chunk content is actually present (F1 regression)
        text_parts = []
        for aev in artifact_events:
            for part in aev.artifact.parts:
                if part.HasField("text") and part.text:
                    text_parts.append(part.text)
        assert "chunk1" in text_parts
        assert "chunk2" in text_parts

        # Verify stored task also has artifacts
        stored = await task_store.get(sse_events[0].id, call_context)
        assert stored is not None
        assert stored.status.state == TaskState.TASK_STATE_COMPLETED
        assert len(stored.artifacts) >= 1

    @pytest.mark.asyncio
    async def test_empty_stream_via_handler_fails(self) -> None:
        """Empty stream through handler reaches FAILED (F2 regression test)."""
        from a2a.server.request_handlers.default_request_handler_v2 import (
            DefaultRequestHandlerV2,
        )
        from a2a.server.tasks import InMemoryTaskStore
        from a2a.server.agent_execution.context import ServerCallContext

        wf = _make_workflow()
        mock_wf_executor = MagicMock()

        events: list[BeddelEvent] = []
        mock_wf_executor.execute_stream = MagicMock(
            return_value=_mock_execute_stream(events),
        )

        registry: WorkflowRegistry = {"wf-test": (wf, mock_wf_executor)}
        executor = BeddelA2AExecutor(registry)
        task_store = InMemoryTaskStore()

        handler = DefaultRequestHandlerV2(
            agent_executor=executor,
            task_store=task_store,
            agent_card=_build_agent_card_for_test(),
        )

        request = _build_send_request(workflow_id="wf-test")
        call_context = ServerCallContext()

        result = await handler.on_message_send(request, call_context)

        assert isinstance(result, Task)
        assert result.status.state == TaskState.TASK_STATE_FAILED
