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


class BeddelADKTool:
    """Wraps a Beddel YAML workflow as an ADK ``FunctionTool``.

    The constructor loads and parses the workflow YAML from the given file
    path at init time (fail-fast on invalid YAML).  The :meth:`as_adk_tool`
    method returns an ADK ``FunctionTool`` that delegates to the Beddel
    :class:`~beddel.domain.executor.WorkflowExecutor`.

    Args:
        workflow_path: Path to the workflow YAML file.
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
        yaml_str = Path(workflow_path).read_text(encoding="utf-8")
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

    async def _execute(self, tool_context: Any = None, **kwargs: Any) -> dict[str, Any]:
        """Execute the wrapped Beddel workflow.

        When an ADK ``ToolContext`` is available, session metadata
        (``session_id`` and ``user_id``) is extracted from
        ``tool_context.state`` and injected into the executor's
        ``ExecutionContext.metadata`` via the inputs dict.

        Args:
            tool_context: ADK ``ToolContext`` injected by the ADK runtime
                (optional — ``None`` when called outside ADK).
            **kwargs: Workflow input parameters.

        Returns:
            A dict with ``"step_results"`` and ``"metadata"`` keys.

        Raises:
            ValueError: When the underlying workflow raises a
                :class:`~beddel.domain.errors.BeddelError`.
        """
        inputs: dict[str, Any] = dict(kwargs)

        # Propagate ADK session metadata when ToolContext is available.
        if tool_context is not None and _HAS_ADK and isinstance(tool_context, _ToolContext):
            state = getattr(tool_context, "state", {}) or {}
            adk_metadata: dict[str, Any] = {}
            if "session_id" in state:
                adk_metadata["session_id"] = state["session_id"]
            if "user_id" in state:
                adk_metadata["user_id"] = state["user_id"]
            if adk_metadata:
                inputs["_adk_metadata"] = adk_metadata

        try:
            return await self._executor.execute(self._workflow, inputs)
        except BeddelError as exc:
            raise ValueError(f"BEDDEL:{exc.code}: {exc.message}") from exc

    def as_adk_tool(self) -> FunctionTool:
        """Return an ADK ``FunctionTool`` wrapping this Beddel workflow.

        Raises:
            ImportError: When ``google-adk`` is not installed.
        """
        if not _HAS_ADK:
            raise ImportError(
                "google-adk is required for as_adk_tool(). "
                "Install it with: pip install beddel[bridge-adk]"
            )

        # Build the tool function with proper name and docstring for ADK
        # schema generation.
        async def _tool_func(tool_context: Any = None, **kwargs: Any) -> dict[str, Any]:
            return await self._execute(tool_context=tool_context, **kwargs)

        _tool_func.__name__ = self._name
        _tool_func.__doc__ = self._description

        return _FunctionTool(func=_tool_func)
