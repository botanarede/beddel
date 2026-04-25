"""Unit tests for ``beddel_bridge_adk.agent.create_adk_agent``."""

from __future__ import annotations

from beddel_bridge_adk.agent import create_adk_agent
from beddel_bridge_adk.tool import BeddelADKTool

# Grab mock classes from the patched sys.modules (injected by conftest).
from google.adk.agents import Agent as MockAgent  # type: ignore[import-untyped]
from google.adk.tools import FunctionTool as MockFunctionTool  # type: ignore[import-untyped]

from beddel.domain.executor import WorkflowExecutor
from beddel.domain.registry import PrimitiveRegistry


class TestCreateADKAgent:
    """create_adk_agent() should build an ADK Agent with Beddel tools."""

    def test_returns_agent_with_tools(self, valid_workflow_yaml: str) -> None:
        registry = PrimitiveRegistry()
        executor = WorkflowExecutor(registry)
        tool_a = BeddelADKTool(valid_workflow_yaml, executor, name="tool_a")
        tool_b = BeddelADKTool(valid_workflow_yaml, executor, name="tool_b")
        agent = create_adk_agent(
            name="test-agent",
            model="gemini-2.0-flash",
            tools=[tool_a, tool_b],
            instruction="You are a test agent.",
        )
        assert isinstance(agent, MockAgent)
        assert agent.name == "test-agent"
        assert agent.model == "gemini-2.0-flash"
        assert agent.instruction == "You are a test agent."
        assert len(agent.tools) == 2
        assert all(isinstance(t, MockFunctionTool) for t in agent.tools)
