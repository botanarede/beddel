"""Integration tests for Vertex AI ADC (Application Default Credentials) flow.

Tests verify that when Vertex AI is configured (via constructor params or env vars),
the full execute()/stream() flow propagates the correct environment variables to the
``ClaudeAgentOptions`` passed to ``query()``.

These tests exercise the integration between _build_options() and execute()/stream(),
mocking ``claude_agent_sdk.query()`` at the SDK boundary.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Mock claude_agent_sdk — reuse existing mock or create a compatible one.
#
# The adapter dispatches on type(message).__name__, so our dataclasses MUST
# have the exact names: AssistantMessage, TextBlock, ResultMessage, etc.
# To coexist with test_claude_adapter.py (which registers its own mock), we
# only install our definitions when no mock exists yet.
# ---------------------------------------------------------------------------


@dataclass
class TextBlock:
    """Mock for ``claude_agent_sdk.TextBlock``."""

    text: str


@dataclass
class AssistantMessage:
    """Mock for ``claude_agent_sdk.AssistantMessage``."""

    content: list[Any]


@dataclass
class ResultMessage:
    """Mock for ``claude_agent_sdk.ResultMessage``."""

    subtype: str = "success"
    is_error: bool = False
    result: str | None = None
    total_cost_usd: float | None = None
    usage: dict[str, Any] | None = None
    num_turns: int = 1
    session_id: str = "test-session"
    duration_ms: int = 1000
    duration_api_ms: int = 900
    cost_usd: float | None = None
    exit_code: int = 0
    text: str = ""


class CLINotFoundError(Exception):
    """Mock for ``claude_agent_sdk.CLINotFoundError``."""


class ProcessError(Exception):
    """Mock for ``claude_agent_sdk.ProcessError``."""

    def __init__(
        self,
        message: str = "",
        exit_code: int | None = None,
        stderr: str | None = None,
    ):
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr


class ClaudeAgentOptions:
    """Mock that records instantiation kwargs for assertion."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class ThinkingConfig:
    """Mock for ``claude_agent_sdk.ThinkingConfig``."""

    ADAPTIVE = "adaptive"
    ENABLED = "enabled"
    DISABLED = "disabled"


class EffortLevel:
    """Mock for ``claude_agent_sdk.EffortLevel``."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Only inject if no mock is registered yet (test_claude_adapter.py may load first).
if "claude_agent_sdk" not in sys.modules or sys.modules["claude_agent_sdk"] is None:
    _mock_sdk = MagicMock()
    _mock_sdk.ClaudeAgentOptions = ClaudeAgentOptions
    _mock_sdk.CLINotFoundError = CLINotFoundError
    _mock_sdk.ProcessError = ProcessError
    _mock_sdk.ThinkingConfig = ThinkingConfig
    _mock_sdk.EffortLevel = EffortLevel
    sys.modules["claude_agent_sdk"] = _mock_sdk

from beddel_agent_claude.adapter import ClaudeAgentAdapter  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — resolve the mock SDK at call time so cross-file ordering is safe.
# ---------------------------------------------------------------------------

_PROMPT = "Analyze the codebase with Vertex AI"


def _get_sdk() -> Any:
    """Get the current mock SDK module from sys.modules."""
    return sys.modules["claude_agent_sdk"]


async def _async_gen(*messages: Any) -> Any:
    """Yield *messages* as an async generator (simulates ``query()``)."""
    for msg in messages:
        yield msg


def _patch_query(*messages: Any) -> None:
    """Patch ``query`` on the live mock module to yield *messages*."""
    sdk = _get_sdk()
    sdk.query = MagicMock(return_value=_async_gen(*messages))


def _get_options_from_query_call() -> Any:
    """Extract the ClaudeAgentOptions instance from the last query() call."""
    sdk = _get_sdk()
    call_args = sdk.query.call_args
    return call_args.kwargs.get("options") or call_args[1]["options"]


def _make_assistant(text: str) -> Any:
    """Create an AssistantMessage using the mock SDK's class (correct __name__)."""
    sdk = _get_sdk()
    # If loaded from test_claude_adapter.py, use its classes for __name__ compat.
    if hasattr(sdk, "AssistantMessage") and not isinstance(
        sdk.AssistantMessage, MagicMock
    ):
        text_cls = sdk.TextBlock if hasattr(sdk, "TextBlock") else TextBlock
        return sdk.AssistantMessage(content=[text_cls(text=text)])
    # Otherwise use our local definitions (same __name__).
    return AssistantMessage(content=[TextBlock(text=text)])


def _make_result(**kwargs: Any) -> Any:
    """Create a ResultMessage using the mock SDK's class (correct __name__)."""
    sdk = _get_sdk()
    if hasattr(sdk, "ResultMessage") and not isinstance(sdk.ResultMessage, MagicMock):
        return sdk.ResultMessage(**kwargs)
    return ResultMessage(**kwargs)


# ===================================================================
# execute() — Vertex AI from constructor params
# ===================================================================


class TestExecuteWithVertexConstructorParams:
    """Integration: execute() passes correct env when Vertex is configured via ctor."""

    async def test_env_vars_propagated_to_options(self) -> None:
        adapter = ClaudeAgentAdapter(
            vertex_project="my-project",
            vertex_region="us-east5",
        )
        _patch_query(
            _make_result(
                usage={"prompt_tokens": 10, "completion_tokens": 5},
                cost_usd=0.01,
            )
        )

        await adapter.execute(_PROMPT)

        options = _get_options_from_query_call()
        assert hasattr(options, "env")
        assert options.env == {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": "my-project",
            "CLOUD_ML_REGION": "us-east5",
        }

    async def test_custom_region_propagated(self) -> None:
        adapter = ClaudeAgentAdapter(
            vertex_project="gcp-prod",
            vertex_region="europe-west4",
        )
        _patch_query(_make_result())

        await adapter.execute(_PROMPT)

        options = _get_options_from_query_call()
        assert options.env["CLOUD_ML_REGION"] == "europe-west4"
        assert options.env["ANTHROPIC_VERTEX_PROJECT_ID"] == "gcp-prod"

    async def test_vertex_flag_always_set_to_one(self) -> None:
        adapter = ClaudeAgentAdapter(
            vertex_project="any-project",
            vertex_region="us-central1",
        )
        _patch_query(_make_result())

        await adapter.execute(_PROMPT)

        options = _get_options_from_query_call()
        assert options.env["CLAUDE_CODE_USE_VERTEX"] == "1"


# ===================================================================
# execute() — Vertex AI from environment variables only
# ===================================================================


class TestExecuteWithVertexEnvVars:
    """Integration: execute() propagates env vars when only env is set (no ctor)."""

    async def test_env_vars_from_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_VERTEX_PROJECT_ID", "env-project")
        monkeypatch.setenv("CLOUD_ML_REGION", "us-west1")

        adapter = ClaudeAgentAdapter()
        _patch_query(_make_result())

        await adapter.execute(_PROMPT)

        options = _get_options_from_query_call()
        assert hasattr(options, "env")
        assert options.env == {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": "env-project",
            "CLOUD_ML_REGION": "us-west1",
        }

    async def test_defaults_region_to_us_east5_when_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_VERTEX_PROJECT_ID", "fallback-project")
        monkeypatch.delenv("CLOUD_ML_REGION", raising=False)

        adapter = ClaudeAgentAdapter()
        _patch_query(_make_result())

        await adapter.execute(_PROMPT)

        options = _get_options_from_query_call()
        assert options.env["CLOUD_ML_REGION"] == "us-east5"

    async def test_no_env_when_vertex_not_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_VERTEX_PROJECT_ID", raising=False)
        monkeypatch.delenv("CLOUD_ML_REGION", raising=False)

        adapter = ClaudeAgentAdapter()
        _patch_query(_make_result())

        await adapter.execute(_PROMPT)

        options = _get_options_from_query_call()
        assert not hasattr(options, "env")


# ===================================================================
# execute() — Full flow returns AgentResult with Vertex configured
# ===================================================================


class TestExecuteFullFlowWithVertex:
    """Integration: full execute() flow returns correct AgentResult structure."""

    async def test_agent_result_structure(self) -> None:
        adapter = ClaudeAgentAdapter(
            vertex_project="my-project",
            vertex_region="us-east5",
        )
        _patch_query(
            _make_assistant("Vertex response"),
            _make_result(
                usage={"prompt_tokens": 20, "completion_tokens": 10},
                cost_usd=0.02,
                exit_code=0,
            ),
        )

        result = await adapter.execute(_PROMPT)

        assert result.exit_code == 0
        assert result.output == "Vertex response"
        assert result.events == []
        assert result.files_changed == []
        assert result.usage["prompt_tokens"] == 20
        assert result.usage["completion_tokens"] == 10
        assert result.usage["cost_usd"] == 0.02
        assert result.agent_id == "claude-agent-sdk"

    async def test_query_receives_prompt_and_options(self) -> None:
        adapter = ClaudeAgentAdapter(
            vertex_project="my-project",
            vertex_region="us-east5",
        )
        _patch_query(_make_result())

        await adapter.execute(_PROMPT)

        sdk = _get_sdk()
        call_kwargs = sdk.query.call_args.kwargs
        assert call_kwargs["prompt"] == _PROMPT
        options = call_kwargs["options"]
        assert options.env["CLAUDE_CODE_USE_VERTEX"] == "1"

    async def test_model_passed_correctly_with_vertex(self) -> None:
        adapter = ClaudeAgentAdapter(
            model="claude-opus-4",
            vertex_project="my-project",
            vertex_region="us-east5",
        )
        _patch_query(_make_result())

        await adapter.execute(_PROMPT)

        options = _get_options_from_query_call()
        assert options.model == "claude-opus-4"
        assert options.env["ANTHROPIC_VERTEX_PROJECT_ID"] == "my-project"


# ===================================================================
# stream() — Vertex AI env propagation
# ===================================================================


class TestStreamWithVertexEnvPropagation:
    """Integration: stream() also propagates Vertex env vars correctly."""

    async def test_stream_passes_vertex_env_from_constructor(self) -> None:
        adapter = ClaudeAgentAdapter(
            vertex_project="stream-project",
            vertex_region="asia-southeast1",
        )
        _patch_query(_make_assistant("streaming vertex"))

        events: list[dict[str, Any]] = []
        async for event in adapter.stream(_PROMPT):
            events.append(event)

        # Verify stream yields events
        assert len(events) == 1
        assert events[0]["type"] == "text"
        assert events[0]["text"] == "streaming vertex"

        # Verify options passed to query()
        options = _get_options_from_query_call()
        assert options.env == {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": "stream-project",
            "CLOUD_ML_REGION": "asia-southeast1",
        }

    async def test_stream_passes_vertex_env_from_environ(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_VERTEX_PROJECT_ID", "env-stream-project")
        monkeypatch.setenv("CLOUD_ML_REGION", "us-east4")

        adapter = ClaudeAgentAdapter()
        _patch_query(_make_result(text="done", exit_code=0))

        events: list[dict[str, Any]] = []
        async for event in adapter.stream(_PROMPT):
            events.append(event)

        # Verify options passed to query()
        options = _get_options_from_query_call()
        assert options.env == {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": "env-stream-project",
            "CLOUD_ML_REGION": "us-east4",
        }

    async def test_stream_no_env_when_vertex_not_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_VERTEX_PROJECT_ID", raising=False)
        monkeypatch.delenv("CLOUD_ML_REGION", raising=False)

        adapter = ClaudeAgentAdapter()
        _patch_query(_make_result())

        events: list[dict[str, Any]] = []
        async for event in adapter.stream(_PROMPT):
            events.append(event)

        options = _get_options_from_query_call()
        assert not hasattr(options, "env")

    async def test_stream_complete_event_with_vertex(self) -> None:
        adapter = ClaudeAgentAdapter(
            vertex_project="my-project",
            vertex_region="us-east5",
        )
        _patch_query(
            _make_result(
                text="finished",
                exit_code=0,
                usage={"prompt_tokens": 15},
                cost_usd=0.005,
            )
        )

        events: list[dict[str, Any]] = []
        async for event in adapter.stream(_PROMPT):
            events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == "complete"
        assert events[0]["output"] == "finished"
        assert events[0]["exit_code"] == 0
