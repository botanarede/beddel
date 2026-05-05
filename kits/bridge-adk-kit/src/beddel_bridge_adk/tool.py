"""BeddelADKTool — wraps a Beddel YAML workflow as an ADK FunctionTool.

This module provides the bridge between Beddel's declarative workflow engine
and Google's Agent Development Kit (ADK).  A :class:`BeddelADKTool` loads a
workflow YAML at construction time and exposes it as an ADK ``FunctionTool``
via :meth:`as_adk_tool`.

ADK session metadata (``session_id``, ``user_id``) is propagated into the
Beddel ``ExecutionContext.metadata`` when an ADK ``ToolContext`` is available.

Example::

    from beddel.domain.executor import WorkflowExecutor
    from beddel.domain.registry import PrimitiveRegistry
    from beddel_bridge_adk.tool import BeddelADKTool

    executor = WorkflowExecutor(PrimitiveRegistry())
    tool = BeddelADKTool("workflows/summarize.yaml", executor)
    adk_tool = tool.as_adk_tool()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from beddel.domain.errors import BeddelError
from beddel.domain.executor import WorkflowExecutor
from beddel.domain.models import Workflow
from beddel.domain.parser import WorkflowParser

if TYPE_CHECKING:
    from google.adk.tools import FunctionTool, ToolContext

__all__ = ["BeddelADKTool"]

logger = logging.getLogger(__name__)

try:
    from google.adk.tools import FunctionTool as _FunctionTool
    from google.adk.tools import ToolContext as _ToolContext

    _HAS_ADK = True
except ImportError:
    _HAS_ADK = False

try:
    from google.cloud import storage as _gcs_storage

    _HAS_GCS = True
except ImportError:
    _HAS_GCS = False


def _read_workflow_source(workflow_path: str) -> str:
    """Read workflow YAML from a local path or a ``gs://`` URI.

    When *workflow_path* starts with ``gs://``, the YAML is downloaded via
    :class:`google.cloud.storage.Client` using Application Default
    Credentials.  Otherwise the path is treated as a local file and read
    with :meth:`pathlib.Path.read_text`.

    Args:
        workflow_path: Local file path **or** ``gs://bucket/blob`` URI.

    Returns:
        The raw YAML string.

    Raises:
        ImportError: When a ``gs://`` URI is given but
            ``google-cloud-storage`` is not installed.
    """
    if workflow_path.startswith("gs://"):
        if not _HAS_GCS:
            raise ImportError(
                "google-cloud-storage is required to load workflows from GCS. "
                "Install it with: pip install google-cloud-storage"
            )
        # Parse gs://bucket/path/to/blob
        without_scheme = workflow_path[len("gs://"):]
        bucket_name, _, blob_path = without_scheme.partition("/")
        client = _gcs_storage.Client()
        blob = client.bucket(bucket_name).blob(blob_path)
        return blob.download_as_text()

    return Path(workflow_path).read_text(encoding="utf-8")


class BeddelADKTool:
    """Wraps a Beddel YAML workflow as an ADK ``FunctionTool``.

    The constructor loads and parses the workflow YAML from the given file
    path at init time (fail-fast on invalid YAML).  The :meth:`as_adk_tool`
    method returns an ADK ``FunctionTool`` that delegates to the Beddel
    :class:`~beddel.domain.executor.WorkflowExecutor`.

    Args:
        workflow_path: Local file path **or** ``gs://bucket/blob`` URI.
        executor: A configured :class:`WorkflowExecutor` instance.
        name: Optional tool name override.  Defaults to the workflow id.
        description: Optional tool description override.  Defaults to the
            workflow description or a generic message.
    """

    def __init__(
        self,
        workflow_path: str,
        executor: WorkflowExecutor,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        yaml_str = _read_workflow_source(workflow_path)
        self._workflow: Workflow = WorkflowParser.parse(yaml_str)
        self._executor = executor
        self._name = name or self._workflow.id
        self._description = (
            description or self._workflow.description or f"Beddel workflow: {self._name}"
        )

    @property
    def name(self) -> str:
        """Tool name derived from the workflow id or constructor override."""
        return self._name

    @property
    def description(self) -> str:
        """Tool description derived from the workflow or constructor override."""
        return self._description

    # Key used to inject ADK session metadata into the workflow inputs dict.
    # Double-underscore prefix avoids collision with user-defined workflow inputs.
    _ADK_SESSION_KEY: str = "__beddel_adk_session__"

    async def execute(
        self,
        inputs: dict[str, Any] | None = None,
        tool_context: Any = None,
    ) -> dict[str, Any]:
        """Execute the wrapped Beddel workflow.

        When an ADK ``ToolContext`` is available, session metadata
        (``session_id`` and ``user_id``) is extracted from
        ``tool_context.state`` and injected into the executor's
        ``ExecutionContext.metadata`` via the inputs dict under the
        ``__beddel_adk_session__`` key.

        Args:
            inputs: Workflow input parameters as a dict.  Defaults to an
                empty dict when ``None``.
            tool_context: ADK ``ToolContext`` injected by the ADK runtime
                (optional — ``None`` when called outside ADK).

        Returns:
            A dict with ``"step_results"`` and ``"metadata"`` keys.

        Raises:
            ValueError: When the underlying workflow raises a
                :class:`~beddel.domain.errors.BeddelError`.
        """
        effective_inputs: dict[str, Any] = dict(inputs or {})

        # Propagate ADK session metadata when ToolContext is available.
        if tool_context is not None and _HAS_ADK and isinstance(tool_context, _ToolContext):
            state = getattr(tool_context, "state", {}) or {}
            adk_metadata: dict[str, Any] = {}
            if "session_id" in state:
                adk_metadata["session_id"] = state["session_id"]
            if "user_id" in state:
                adk_metadata["user_id"] = state["user_id"]
            if adk_metadata:
                effective_inputs[self._ADK_SESSION_KEY] = adk_metadata

        try:
            return await self._executor.execute(self._workflow, effective_inputs)
        except BeddelError as exc:
            raise ValueError(f"BEDDEL:{exc.code}: {exc.message}") from exc

    def as_adk_tool(self) -> FunctionTool:
        """Return an ADK ``FunctionTool`` wrapping this Beddel workflow.

        The returned tool accepts a single ``inputs`` parameter (JSON-style
        dict) so that ADK can generate a proper schema for the model.
        ``tool_context`` is injected by the ADK runtime automatically when
        the function signature includes a ``ToolContext``-typed parameter.

        Raises:
            ImportError: When ``google-adk`` is not installed.
        """
        if not _HAS_ADK:
            raise ImportError(
                "google-adk is required for as_adk_tool(). "
                "Install it with: pip install beddel[bridge-adk]"
            )

        # Capture self for the closure.
        bridge = self

        async def _tool_func(
            inputs: dict[str, Any] | None = None,
            tool_context: Any = None,
        ) -> dict[str, Any]:
            """Execute a Beddel workflow with the given inputs.

            Args:
                inputs: Workflow input parameters as a dict.
                tool_context: ADK ToolContext (injected by runtime).

            Returns:
                Workflow result with step_results and metadata.
            """
            return await bridge.execute(inputs=inputs, tool_context=tool_context)

        _tool_func.__name__ = self._name
        _tool_func.__doc__ = self._description

        return _FunctionTool(func=_tool_func)
