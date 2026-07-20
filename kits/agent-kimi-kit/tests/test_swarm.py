"""Unit tests for KimiSwarmStrategy — AgentSwarm coordination bridge.

All tests mock kimi-agent-sdk to avoid live API calls.
Mocks replicate the real SDK lifecycle:
  Session.create(work_dir=..., config=...) -> async context manager
  session.prompt(text) -> async generator of wire messages:
    ToolCall (AgentSwarm invocation)
    SubagentEvent (child progress/completion/failure)
    ToolResult (aggregate report)
    TextPart (parent text)
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from beddel.domain.errors import AgentError
from beddel.domain.models import (
    CoordinationResult,
    CoordinationTask,
    ExecutionContext,
    Step,
    Workflow,
)
from beddel_agent_kimi.swarm import (
    KIMI_AUTH_MISSING,
    KIMI_SESSION_TIMEOUT,
    KIMI_SWARM_ALL_FAILED,
    KIMI_SWARM_NONCOMPLIANT,
    KimiSwarmStrategy,
    _MIN_SUBTASKS,
)


# ---------------------------------------------------------------------------
# Fake wire message types (mimicking kimi-agent-sdk)
# ---------------------------------------------------------------------------


def _make_tool_call(name: str = "AgentSwarm", call_id: str = "tc-001") -> Any:
    """Create a fake ToolCall wire message."""
    # Use dynamic class so type(msg).__name__ == "ToolCall"
    cls = type("ToolCall", (), {})
    obj = cls()
    obj.name = name  # type: ignore[attr-defined]
    obj.id = call_id  # type: ignore[attr-defined]
    return obj


def _make_subagent_event(
    parent_tool_call_id: str = "tc-001",
    agent_id: str = "child-1",
    status: str = "completed",
    output: str = "task done",
) -> Any:
    """Create a fake SubagentEvent wire message."""
    cls = type("SubagentEvent", (), {})
    obj = cls()
    obj.parent_tool_call_id = parent_tool_call_id  # type: ignore[attr-defined]
    event = MagicMock()
    event.agent_id = agent_id
    event.status = status
    event.output = output
    obj.event = event  # type: ignore[attr-defined]
    return obj


def _make_tool_result(text: str = "Aggregate report: all tasks completed") -> Any:
    """Create a fake ToolResult wire message."""
    cls = type("ToolResult", (), {})
    obj = cls()
    obj.text = text  # type: ignore[attr-defined]
    return obj


def _make_text_part(text: str = "Invoking swarm...") -> Any:
    """Create a fake TextPart wire message (has .text attr but type != ToolResult)."""
    cls = type("TextPart", (), {})
    obj = cls()
    obj.text = text  # type: ignore[attr-defined]
    return obj


# ---------------------------------------------------------------------------
# SDK mock helpers
# ---------------------------------------------------------------------------


def _make_fake_session(
    responses: list[Any] | None = None,
    prompt_side_effect: Exception | None = None,
) -> MagicMock:
    """Create a mock session mimicking async context manager + prompt()."""
    if responses is None:
        responses = [
            _make_tool_call("AgentSwarm", "tc-001"),
            _make_subagent_event("tc-001", "child-1", "completed", "result 1"),
            _make_subagent_event("tc-001", "child-2", "completed", "result 2"),
            _make_tool_result("All 2 tasks completed successfully"),
        ]

    session = MagicMock()

    async def _fake_prompt(text: str):  # noqa: ANN202
        if prompt_side_effect:
            raise prompt_side_effect
        for msg in responses:
            yield msg

    session.prompt = _fake_prompt
    return session


def _make_sdk_mock(
    session: MagicMock | None = None,
    create_side_effect: Exception | None = None,
) -> MagicMock:
    """Create a mock kimi_agent_sdk module."""
    if session is None:
        session = _make_fake_session()

    sdk_mock = MagicMock()

    @asynccontextmanager
    async def _fake_create(**kwargs: Any):  # noqa: ANN202
        if create_side_effect:
            raise create_side_effect
        session._create_kwargs = kwargs
        yield session

    async def _awaitable_create(**kwargs: Any):  # noqa: ANN202
        return _fake_create(**kwargs)

    sdk_mock.Session = MagicMock()
    sdk_mock.Session.create = _awaitable_create
    sdk_mock.Config = MagicMock(side_effect=lambda **kwargs: kwargs)

    return sdk_mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set MOONSHOT_API_KEY for strategy instantiation."""
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key-swarm")
    # Clear any pre-existing concurrency env var
    monkeypatch.delenv("KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY", raising=False)


@pytest.fixture()
def strategy(mock_env: None) -> KimiSwarmStrategy:
    """Create a KimiSwarmStrategy with test defaults."""
    return KimiSwarmStrategy(swarm_concurrency=8, timeout=30)


@pytest.fixture()
def task() -> CoordinationTask:
    """Create a standard CoordinationTask with 3 subtasks."""
    return CoordinationTask(
        prompt="Implement feature {{item}}",
        subtasks=["parse config", "validate schema", "write output"],
        context_data={"work_dir": "/tmp/swarm-test"},
        timeout=60.0,
    )


@pytest.fixture()
def context() -> ExecutionContext:
    """Create a minimal ExecutionContext for testing."""
    return ExecutionContext(
        workflow_id="wf-test",
        workflow=Workflow(
            id="wf-test",
            name="test-workflow",
            steps=[Step(id="s1", primitive="noop", config={})],
        ),
        variables={},
    )


# ---------------------------------------------------------------------------
# Test: Initialization & Validation
# ---------------------------------------------------------------------------


class TestInitialization:
    """Test KimiSwarmStrategy constructor validation."""

    def test_missing_api_key_raises_agent_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BEDDEL-AGENT-800 on missing MOONSHOT_API_KEY."""
        monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
        with pytest.raises(AgentError) as exc_info:
            KimiSwarmStrategy()
        assert exc_info.value.code == KIMI_AUTH_MISSING

    def test_explicit_api_key_bypasses_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit api_key skips env lookup."""
        monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
        strategy = KimiSwarmStrategy(api_key="explicit-key")
        assert strategy._api_key == "explicit-key"

    def test_concurrency_below_min_raises(self, mock_env: None) -> None:
        """Concurrency < 1 raises ValueError."""
        with pytest.raises(ValueError, match="1–128"):
            KimiSwarmStrategy(swarm_concurrency=0)

    def test_concurrency_above_max_raises(self, mock_env: None) -> None:
        """Concurrency > 128 raises ValueError."""
        with pytest.raises(ValueError, match="1–128"):
            KimiSwarmStrategy(swarm_concurrency=129)

    def test_valid_concurrency_accepted(self, mock_env: None) -> None:
        """Valid concurrency values are accepted."""
        s = KimiSwarmStrategy(swarm_concurrency=64)
        assert s._concurrency == 64


# ---------------------------------------------------------------------------
# Test: Subtask Validation
# ---------------------------------------------------------------------------


class TestSubtaskValidation:
    """Test minimum subtask enforcement."""

    @pytest.mark.asyncio
    async def test_zero_subtasks_raises(
        self, strategy: KimiSwarmStrategy, context: ExecutionContext
    ) -> None:
        """0 subtasks raises BEDDEL-AGENT-804."""
        empty_task = CoordinationTask(prompt="Do stuff", subtasks=[])
        with pytest.raises(AgentError) as exc_info:
            await strategy.coordinate({}, empty_task, context)
        assert exc_info.value.code == KIMI_SWARM_ALL_FAILED
        assert f"at least {_MIN_SUBTASKS}" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_one_subtask_raises(
        self, strategy: KimiSwarmStrategy, context: ExecutionContext
    ) -> None:
        """1 subtask raises BEDDEL-AGENT-804."""
        single_task = CoordinationTask(prompt="Do stuff", subtasks=["only one"])
        with pytest.raises(AgentError) as exc_info:
            await strategy.coordinate({}, single_task, context)
        assert exc_info.value.code == KIMI_SWARM_ALL_FAILED


# ---------------------------------------------------------------------------
# Test: Happy Path — Full Swarm Lifecycle
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Test successful swarm coordination flow."""

    @pytest.mark.asyncio
    async def test_returns_coordination_result(
        self,
        strategy: KimiSwarmStrategy,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """Successful swarm returns CoordinationResult with aggregate output."""
        session = _make_fake_session()
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            result = await strategy.coordinate({}, task, context)

        assert isinstance(result, CoordinationResult)
        assert result.strategy_name == "kimi-agent-swarm"
        assert result.output == "All 2 tasks completed successfully"

    @pytest.mark.asyncio
    async def test_agent_results_populated(
        self,
        strategy: KimiSwarmStrategy,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """Completed child events produce AgentResult entries."""
        session = _make_fake_session()
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            result = await strategy.coordinate({}, task, context)

        assert "child-1" in result.agent_results
        assert "child-2" in result.agent_results
        assert result.agent_results["child-1"].output == "result 1"
        assert result.agent_results["child-2"].output == "result 2"

    @pytest.mark.asyncio
    async def test_metadata_populated(
        self,
        strategy: KimiSwarmStrategy,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """Metadata includes item count, child count, concurrency, model."""
        session = _make_fake_session()
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            result = await strategy.coordinate({}, task, context)

        assert result.metadata["item_count"] == 3
        assert result.metadata["child_count"] == 2
        assert result.metadata["succeeded"] == 2
        assert result.metadata["failed"] == 0
        assert result.metadata["concurrency"] == 8

    @pytest.mark.asyncio
    async def test_concurrency_env_var_set_and_restored(
        self,
        strategy: KimiSwarmStrategy,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY is set during execution and restored."""
        session = _make_fake_session()
        sdk_mock = _make_sdk_mock(session)

        # Ensure env var is not set before
        assert "KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY" not in os.environ

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            await strategy.coordinate({}, task, context)

        # Env var should be cleaned up after
        assert "KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY" not in os.environ

    @pytest.mark.asyncio
    async def test_uses_task_timeout(
        self,
        mock_env: None,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """Task.timeout overrides strategy default."""
        strategy = KimiSwarmStrategy(timeout=300)

        async def _slow_prompt(text: str):  # noqa: ANN202
            await asyncio.sleep(999)
            yield _make_text_part("never")  # noqa: RUF029

        session = MagicMock()
        session.prompt = _slow_prompt
        sdk_mock = _make_sdk_mock(session)

        # Task timeout is 60 but we'll use 0 to trigger immediately
        fast_task = CoordinationTask(
            prompt="test",
            subtasks=["a", "b"],
            context_data={"work_dir": "/tmp"},
            timeout=0.0,
        )

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            with pytest.raises(AgentError) as exc_info:
                await strategy.coordinate({}, fast_task, context)
            assert exc_info.value.code == KIMI_SESSION_TIMEOUT


# ---------------------------------------------------------------------------
# Test: Model Noncompliance
# ---------------------------------------------------------------------------


class TestNoncompliance:
    """Test that model must invoke AgentSwarm tool."""

    @pytest.mark.asyncio
    async def test_no_tool_call_raises_noncompliant(
        self,
        strategy: KimiSwarmStrategy,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """BEDDEL-AGENT-804 when model responds with text only."""
        # Session returns only text, no ToolCall for AgentSwarm
        session = _make_fake_session(
            [
                _make_text_part("I'll help you with that..."),
                _make_text_part("Here's my analysis."),
            ]
        )
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            with pytest.raises(AgentError) as exc_info:
                await strategy.coordinate({}, task, context)
            assert exc_info.value.code == KIMI_SWARM_NONCOMPLIANT
            assert "noncompliance" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_wrong_tool_call_raises_noncompliant(
        self,
        strategy: KimiSwarmStrategy,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """BEDDEL-AGENT-804 when model calls a different tool."""
        session = _make_fake_session(
            [
                _make_tool_call("ReadFile", "tc-wrong"),
                _make_text_part("Done reading."),
            ]
        )
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            with pytest.raises(AgentError) as exc_info:
                await strategy.coordinate({}, task, context)
            assert exc_info.value.code == KIMI_SWARM_NONCOMPLIANT


# ---------------------------------------------------------------------------
# Test: Partial Failure (some children fail)
# ---------------------------------------------------------------------------


class TestPartialFailure:
    """Test failure isolation — some children fail, result still returned."""

    @pytest.mark.asyncio
    async def test_partial_failure_returns_result(
        self,
        strategy: KimiSwarmStrategy,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """When some children fail, result includes succeeded + failed metadata."""
        session = _make_fake_session(
            [
                _make_tool_call("AgentSwarm", "tc-001"),
                _make_subagent_event("tc-001", "child-1", "completed", "ok"),
                _make_subagent_event("tc-001", "child-2", "failed", ""),
                _make_subagent_event("tc-001", "child-3", "completed", "ok too"),
                _make_tool_result("Partial results: 2/3 succeeded"),
            ]
        )
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            result = await strategy.coordinate({}, task, context)

        assert result.metadata["succeeded"] == 2
        assert result.metadata["failed"] == 1
        assert "child-2" in result.metadata["failed_agents"]
        assert "child-1" in result.agent_results
        assert "child-3" in result.agent_results
        assert "child-2" not in result.agent_results


# ---------------------------------------------------------------------------
# Test: Total Failure (all children fail)
# ---------------------------------------------------------------------------


class TestTotalFailure:
    """Test all-children-fail raises BEDDEL-AGENT-804."""

    @pytest.mark.asyncio
    async def test_all_children_fail_raises(
        self,
        strategy: KimiSwarmStrategy,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """BEDDEL-AGENT-804 when every child agent fails."""
        session = _make_fake_session(
            [
                _make_tool_call("AgentSwarm", "tc-001"),
                _make_subagent_event("tc-001", "child-1", "failed", ""),
                _make_subagent_event("tc-001", "child-2", "failed", ""),
                _make_tool_result("All tasks failed"),
            ]
        )
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            with pytest.raises(AgentError) as exc_info:
                await strategy.coordinate({}, task, context)
            assert exc_info.value.code == KIMI_SWARM_ALL_FAILED
            assert "All swarm sub-agents failed" in exc_info.value.message


# ---------------------------------------------------------------------------
# Test: Timeout
# ---------------------------------------------------------------------------


class TestTimeout:
    """Test session timeout behavior."""

    @pytest.mark.asyncio
    async def test_timeout_raises_agent_error(
        self,
        mock_env: None,
        context: ExecutionContext,
    ) -> None:
        """BEDDEL-AGENT-801 on session timeout."""

        async def _slow_prompt(text: str):  # noqa: ANN202
            await asyncio.sleep(999)
            yield _make_tool_call("AgentSwarm")  # noqa: RUF029

        session = MagicMock()
        session.prompt = _slow_prompt
        sdk_mock = _make_sdk_mock(session)

        strategy = KimiSwarmStrategy(timeout=0)
        task = CoordinationTask(
            prompt="slow",
            subtasks=["a", "b"],
            context_data={"work_dir": "/tmp"},
            timeout=0.0,
        )

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            with pytest.raises(AgentError) as exc_info:
                await strategy.coordinate({}, task, context)
            assert exc_info.value.code == KIMI_SESSION_TIMEOUT


# ---------------------------------------------------------------------------
# Test: SDK Exception Handling
# ---------------------------------------------------------------------------


class TestSDKErrors:
    """Test SDK exception wrapping."""

    @pytest.mark.asyncio
    async def test_session_create_error_wrapped(
        self,
        strategy: KimiSwarmStrategy,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """Exception from Session.create() is wrapped as BEDDEL-AGENT-804."""
        sdk_mock = _make_sdk_mock(create_side_effect=ConnectionError("Network down"))

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            with pytest.raises(AgentError) as exc_info:
                await strategy.coordinate({}, task, context)
            assert exc_info.value.code == KIMI_SWARM_ALL_FAILED
            assert "Network down" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_prompt_exception_wrapped(
        self,
        strategy: KimiSwarmStrategy,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """Exception during session.prompt() is wrapped as BEDDEL-AGENT-804."""
        session = _make_fake_session(
            prompt_side_effect=RuntimeError("Internal SDK error")
        )
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            with pytest.raises(AgentError) as exc_info:
                await strategy.coordinate({}, task, context)
            assert exc_info.value.code == KIMI_SWARM_ALL_FAILED
            assert "Internal SDK error" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_import_error_wrapped(
        self,
        strategy: KimiSwarmStrategy,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """Missing kimi-agent-sdk raises BEDDEL-AGENT-804."""
        with patch.dict("sys.modules", {"kimi_agent_sdk": None}):
            with pytest.raises((AgentError, ModuleNotFoundError)):
                await strategy.coordinate({}, task, context)


# ---------------------------------------------------------------------------
# Test: Concurrency Conflict
# ---------------------------------------------------------------------------


class TestConcurrencyConflict:
    """Test process-global env var conflict detection."""

    @pytest.mark.asyncio
    async def test_conflicting_env_var_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """BEDDEL-AGENT-804 when env var already set to different value."""
        monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
        monkeypatch.setenv("KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY", "16")

        strategy = KimiSwarmStrategy(swarm_concurrency=8)

        with pytest.raises(AgentError) as exc_info:
            await strategy.coordinate({}, task, context)
        assert exc_info.value.code == KIMI_SWARM_ALL_FAILED
        assert "Conflicting" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_matching_env_var_accepted(
        self,
        monkeypatch: pytest.MonkeyPatch,
        task: CoordinationTask,
        context: ExecutionContext,
    ) -> None:
        """No error when env var matches requested concurrency."""
        monkeypatch.setenv("MOONSHOT_API_KEY", "test-key")
        monkeypatch.setenv("KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY", "8")

        strategy = KimiSwarmStrategy(swarm_concurrency=8)
        session = _make_fake_session()
        sdk_mock = _make_sdk_mock(session)

        with patch.dict("sys.modules", {"kimi_agent_sdk": sdk_mock}):
            result = await strategy.coordinate({}, task, context)

        assert isinstance(result, CoordinationResult)


# ---------------------------------------------------------------------------
# Test: Prompt Construction
# ---------------------------------------------------------------------------


class TestPromptConstruction:
    """Test the swarm instruction prompt is well-formed."""

    def test_prompt_includes_subtasks(self) -> None:
        """Built prompt contains all subtask items."""
        task = CoordinationTask(
            prompt="Do {{item}}",
            subtasks=["task-a", "task-b", "task-c"],
        )
        prompt = KimiSwarmStrategy._build_swarm_prompt(task)
        assert "task-a" in prompt
        assert "task-b" in prompt
        assert "task-c" in prompt

    def test_prompt_forces_tool_invocation(self) -> None:
        """Built prompt contains mandatory tool invocation instruction."""
        task = CoordinationTask(prompt="template", subtasks=["x", "y"])
        prompt = KimiSwarmStrategy._build_swarm_prompt(task)
        assert "MUST invoke the AgentSwarm tool" in prompt
        assert "ONLY invoke the tool" in prompt

    def test_prompt_includes_template(self) -> None:
        """Built prompt includes the prompt_template from task."""
        task = CoordinationTask(
            prompt="Analyze {{item}} deeply",
            subtasks=["code", "tests"],
        )
        prompt = KimiSwarmStrategy._build_swarm_prompt(task)
        assert "Analyze {{item}} deeply" in prompt
