"""Unit tests for ``beddel_bridge_adk.tool.BeddelADKTool``."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from beddel_bridge_adk.tool import BeddelADKTool

# Grab the mock classes from the patched sys.modules (injected by conftest).
from google.adk.tools import FunctionTool as MockFunctionTool  # type: ignore[import-untyped]
from google.adk.tools import ToolContext as MockToolContext  # type: ignore[import-untyped]

from beddel.domain.errors import BeddelError, ParseError
from beddel.domain.executor import WorkflowExecutor
from beddel.domain.registry import PrimitiveRegistry


class TestConstructionValidYAML:
    """BeddelADKTool should load and parse a valid workflow YAML."""

    def test_name_and_description_set(self, valid_workflow_yaml: str) -> None:
        registry = PrimitiveRegistry()
        executor = WorkflowExecutor(registry)
        tool = BeddelADKTool(valid_workflow_yaml, executor)
        assert tool.name == "test-workflow"
        assert tool.description == "A test workflow for unit tests"


class TestConstructionInvalidYAML:
    """BeddelADKTool should raise ParseError on invalid workflow YAML."""

    def test_raises_parse_error(self, invalid_workflow_yaml: str) -> None:
        registry = PrimitiveRegistry()
        executor = WorkflowExecutor(registry)
        with pytest.raises(ParseError):
            BeddelADKTool(invalid_workflow_yaml, executor)


class TestExecuteReturnsResult:
    """_execute() should delegate to executor and return the result dict."""

    @pytest.mark.asyncio()
    async def test_returns_step_results_and_metadata(self, valid_workflow_yaml: str) -> None:
        registry = PrimitiveRegistry()
        executor = WorkflowExecutor(registry)
        expected: dict[str, Any] = {
            "step_results": {"step-1": {"text": "Hello world"}},
            "metadata": {"duration_ms": 42},
        }
        executor.execute = AsyncMock(return_value=expected)  # type: ignore[method-assign]
        tool = BeddelADKTool(valid_workflow_yaml, executor)
        result = await tool._execute(prompt="Hello")
        assert result == expected
        executor.execute.assert_awaited_once()  # type: ignore[union-attr]


class TestExecuteErrorHandling:
    """_execute() should catch BeddelError and re-raise as ValueError."""

    @pytest.mark.asyncio()
    async def test_beddel_error_surfaces_as_value_error(self, valid_workflow_yaml: str) -> None:
        registry = PrimitiveRegistry()
        executor = WorkflowExecutor(registry)
        executor.execute = AsyncMock(  # type: ignore[method-assign]
            side_effect=BeddelError("BEDDEL-EXEC-001", "Something went wrong"),
        )
        tool = BeddelADKTool(valid_workflow_yaml, executor)
        with pytest.raises(ValueError, match="BEDDEL:BEDDEL-EXEC-001"):
            await tool._execute()


class TestAsADKTool:
    """as_adk_tool() should return a MockFunctionTool instance."""

    def test_returns_function_tool(self, valid_workflow_yaml: str) -> None:
        registry = PrimitiveRegistry()
        executor = WorkflowExecutor(registry)
        tool = BeddelADKTool(valid_workflow_yaml, executor)
        adk_tool = tool.as_adk_tool()
        assert isinstance(adk_tool, MockFunctionTool)
        assert adk_tool.func is not None
        assert callable(adk_tool.func)


class TestADKMetadataPropagation:
    """_execute() should propagate ADK session metadata from ToolContext."""

    @pytest.mark.asyncio()
    async def test_session_metadata_injected(self, valid_workflow_yaml: str) -> None:
        registry = PrimitiveRegistry()
        executor = WorkflowExecutor(registry)
        captured_inputs: dict[str, Any] = {}

        async def _capture_execute(
            workflow: Any, inputs: dict[str, Any] | None = None, **kw: Any
        ) -> dict[str, Any]:
            captured_inputs.update(inputs or {})
            return {"step_results": {}, "metadata": {}}

        executor.execute = _capture_execute  # type: ignore[method-assign]
        tool = BeddelADKTool(valid_workflow_yaml, executor)
        mock_ctx = MockToolContext(state={"session_id": "sess-123", "user_id": "user-456"})
        await tool._execute(tool_context=mock_ctx, prompt="test")
        assert "_adk_metadata" in captured_inputs
        assert captured_inputs["_adk_metadata"]["session_id"] == "sess-123"
        assert captured_inputs["_adk_metadata"]["user_id"] == "user-456"
