"""Unit tests for ``beddel_bridge_adk.tool.BeddelADKTool``."""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import HAS_REAL_ADK

from beddel_bridge_adk.tool import BeddelADKTool

from beddel.domain.errors import BeddelError, ParseError
from beddel.domain.executor import WorkflowExecutor
from beddel.domain.registry import PrimitiveRegistry


def _make_tool_context(state: dict[str, Any]) -> Any:
    """Create a ToolContext (real or mock) with the given state."""
    if HAS_REAL_ADK:
        # Real ADK ToolContext — build a minimal mock that passes isinstance check.
        from google.adk.tools import ToolContext

        ctx = MagicMock(spec=ToolContext)
        ctx.state = state
        return ctx
    else:
        from conftest import MockToolContext

        return MockToolContext(state=state)


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
    """execute() should delegate to executor and return the result dict."""

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
        result = await tool.execute(inputs={"prompt": "Hello"})
        assert result == expected
        executor.execute.assert_awaited_once()  # type: ignore[union-attr]


class TestExecuteErrorHandling:
    """execute() should catch BeddelError and re-raise as ValueError."""

    @pytest.mark.asyncio()
    async def test_beddel_error_surfaces_as_value_error(self, valid_workflow_yaml: str) -> None:
        registry = PrimitiveRegistry()
        executor = WorkflowExecutor(registry)
        executor.execute = AsyncMock(  # type: ignore[method-assign]
            side_effect=BeddelError("BEDDEL-EXEC-001", "Something went wrong"),
        )
        tool = BeddelADKTool(valid_workflow_yaml, executor)
        with pytest.raises(ValueError, match="BEDDEL:BEDDEL-EXEC-001"):
            await tool.execute()


class TestAsADKTool:
    """as_adk_tool() should return a FunctionTool instance."""

    def test_returns_function_tool(self, valid_workflow_yaml: str) -> None:
        if HAS_REAL_ADK:
            from google.adk.tools import FunctionTool
        else:
            from conftest import MockFunctionTool as FunctionTool  # type: ignore[assignment]

        registry = PrimitiveRegistry()
        executor = WorkflowExecutor(registry)
        tool = BeddelADKTool(valid_workflow_yaml, executor)
        adk_tool = tool.as_adk_tool()
        assert isinstance(adk_tool, FunctionTool)

    def test_tool_func_has_typed_signature(self, valid_workflow_yaml: str) -> None:
        """The generated tool function should have typed parameters for ADK schema."""
        registry = PrimitiveRegistry()
        executor = WorkflowExecutor(registry)
        tool = BeddelADKTool(valid_workflow_yaml, executor)
        adk_tool = tool.as_adk_tool()
        sig = inspect.signature(adk_tool.func)
        param_names = list(sig.parameters.keys())
        # Must have 'inputs' and 'tool_context' — NOT **kwargs
        assert "inputs" in param_names
        assert "tool_context" in param_names
        # Must NOT have **kwargs (VAR_KEYWORD)
        for p in sig.parameters.values():
            assert p.kind != inspect.Parameter.VAR_KEYWORD, (
                f"Parameter {p.name} is **kwargs — ADK cannot generate schema"
            )


class TestADKMetadataPropagation:
    """execute() should propagate ADK session metadata from ToolContext."""

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
        mock_ctx = _make_tool_context({"session_id": "sess-123", "user_id": "user-456"})
        await tool.execute(inputs={"prompt": "test"}, tool_context=mock_ctx)
        # Uses namespaced key to avoid collision with user inputs (M2 fix)
        assert BeddelADKTool._ADK_SESSION_KEY in captured_inputs
        meta = captured_inputs[BeddelADKTool._ADK_SESSION_KEY]
        assert meta["session_id"] == "sess-123"
        assert meta["user_id"] == "user-456"

    @pytest.mark.asyncio()
    async def test_no_metadata_without_tool_context(self, valid_workflow_yaml: str) -> None:
        """When tool_context is None, no session metadata is injected."""
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
        await tool.execute(inputs={"prompt": "test"})
        assert BeddelADKTool._ADK_SESSION_KEY not in captured_inputs


class TestImportErrorPath:
    """as_adk_tool() should raise ImportError when _HAS_ADK is False."""

    def test_as_adk_tool_raises_import_error(self, valid_workflow_yaml: str) -> None:
        import beddel_bridge_adk.tool as tool_mod

        registry = PrimitiveRegistry()
        executor = WorkflowExecutor(registry)
        tool = BeddelADKTool(valid_workflow_yaml, executor)

        # Temporarily patch both the module-level flag AND the closure reference.
        original_flag = tool_mod._HAS_ADK
        original_ft = tool_mod._FunctionTool
        try:
            tool_mod._HAS_ADK = False
            with pytest.raises(ImportError, match="google-adk is required"):
                tool.as_adk_tool()
        finally:
            tool_mod._HAS_ADK = original_flag
            tool_mod._FunctionTool = original_ft


class TestReadWorkflowSourceLocal:
    """_read_workflow_source() should read local files unchanged."""

    def test_reads_local_file(self, valid_workflow_yaml: str) -> None:
        from beddel_bridge_adk.tool import _read_workflow_source

        content = _read_workflow_source(valid_workflow_yaml)
        assert "id: test-workflow" in content
        assert "primitive: llm" in content


class TestReadWorkflowSourceGCS:
    """_read_workflow_source() should load YAML from GCS URIs via mocked Client."""

    _GCS_YAML = (
        "id: test-workflow\n"
        "name: Test Workflow\n"
        "description: A test workflow for unit tests\n"
        'version: "1.0"\n'
        "steps:\n"
        "  - id: step-1\n"
        "    primitive: llm\n"
        "    config:\n"
        "      model: gpt-4o-mini\n"
        '      prompt: "Hello"\n'
    )

    def test_gcs_uri_loads_via_client(self) -> None:
        """When workflow_path is gs://bucket/path, use GCS Client."""
        import beddel_bridge_adk.tool as tool_mod

        mock_blob = MagicMock()
        mock_blob.download_as_text.return_value = self._GCS_YAML

        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        mock_gcs_module = MagicMock()
        mock_gcs_module.Client.return_value = mock_client

        original_has_gcs = tool_mod._HAS_GCS
        original_gcs_storage = getattr(tool_mod, "_gcs_storage", None)
        try:
            tool_mod._HAS_GCS = True
            tool_mod._gcs_storage = mock_gcs_module

            result = tool_mod._read_workflow_source(
                "gs://my-bucket/workflows/test.yaml"
            )

            assert result == self._GCS_YAML
            mock_gcs_module.Client.assert_called_once()
            mock_client.bucket.assert_called_once_with("my-bucket")
            mock_bucket.blob.assert_called_once_with("workflows/test.yaml")
            mock_blob.download_as_text.assert_called_once()
        finally:
            tool_mod._HAS_GCS = original_has_gcs
            if original_gcs_storage is not None:
                tool_mod._gcs_storage = original_gcs_storage

    def test_gcs_uri_nested_path(self) -> None:
        """GCS URIs with deeply nested blob paths are parsed correctly."""
        import beddel_bridge_adk.tool as tool_mod

        mock_blob = MagicMock()
        mock_blob.download_as_text.return_value = self._GCS_YAML

        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        mock_gcs_module = MagicMock()
        mock_gcs_module.Client.return_value = mock_client

        original_has_gcs = tool_mod._HAS_GCS
        original_gcs_storage = getattr(tool_mod, "_gcs_storage", None)
        try:
            tool_mod._HAS_GCS = True
            tool_mod._gcs_storage = mock_gcs_module

            tool_mod._read_workflow_source(
                "gs://beddel-workflows/v1/prod/workflows/summarize.yaml"
            )

            mock_client.bucket.assert_called_once_with("beddel-workflows")
            mock_bucket.blob.assert_called_once_with(
                "v1/prod/workflows/summarize.yaml"
            )
        finally:
            tool_mod._HAS_GCS = original_has_gcs
            if original_gcs_storage is not None:
                tool_mod._gcs_storage = original_gcs_storage

    def test_gcs_uri_raises_import_error_when_no_gcs(self) -> None:
        """When _HAS_GCS is False, a helpful ImportError is raised."""
        import beddel_bridge_adk.tool as tool_mod

        original_has_gcs = tool_mod._HAS_GCS
        try:
            tool_mod._HAS_GCS = False
            with pytest.raises(ImportError, match="google-cloud-storage"):
                tool_mod._read_workflow_source("gs://bucket/path.yaml")
        finally:
            tool_mod._HAS_GCS = original_has_gcs

    def test_beddel_adk_tool_init_with_gcs_uri(self) -> None:
        """BeddelADKTool.__init__ works end-to-end with a GCS URI."""
        import beddel_bridge_adk.tool as tool_mod

        mock_blob = MagicMock()
        mock_blob.download_as_text.return_value = self._GCS_YAML

        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        mock_gcs_module = MagicMock()
        mock_gcs_module.Client.return_value = mock_client

        original_has_gcs = tool_mod._HAS_GCS
        original_gcs_storage = getattr(tool_mod, "_gcs_storage", None)
        try:
            tool_mod._HAS_GCS = True
            tool_mod._gcs_storage = mock_gcs_module

            registry = PrimitiveRegistry()
            executor = WorkflowExecutor(registry)
            tool = BeddelADKTool(
                "gs://my-bucket/workflows/test.yaml", executor
            )

            assert tool.name == "test-workflow"
            assert tool.description == "A test workflow for unit tests"
        finally:
            tool_mod._HAS_GCS = original_has_gcs
            if original_gcs_storage is not None:
                tool_mod._gcs_storage = original_gcs_storage
