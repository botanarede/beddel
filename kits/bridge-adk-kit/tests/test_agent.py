"""Unit tests for ``beddel_bridge_adk.agent.create_adk_agent``."""

from __future__ import annotations

import pytest
from conftest import HAS_REAL_ADK

from beddel_bridge_adk.agent import create_adk_agent
from beddel_bridge_adk.tool import BeddelADKTool

from beddel.domain.executor import WorkflowExecutor
from beddel.domain.registry import PrimitiveRegistry


class TestCreateADKAgent:
    """create_adk_agent() should build an ADK Agent with Beddel tools."""

    def test_returns_agent_with_tools(self, valid_workflow_yaml: str) -> None:
        if HAS_REAL_ADK:
            from google.adk.agents import Agent as AgentClass
        else:
            from conftest import MockAgent as AgentClass  # type: ignore[assignment]

        registry = PrimitiveRegistry()
        executor = WorkflowExecutor(registry)
        # ADK requires Python-identifier names (no hyphens).
        tool_a = BeddelADKTool(valid_workflow_yaml, executor, name="tool_a")
        tool_b = BeddelADKTool(valid_workflow_yaml, executor, name="tool_b")
        agent = create_adk_agent(
            name="test_agent",
            model="gemini-2.0-flash",
            tools=[tool_a, tool_b],
            instruction="You are a test agent.",
        )
        assert isinstance(agent, AgentClass)
        assert agent.name == "test_agent"
        assert agent.model == "gemini-2.0-flash"
        assert len(agent.tools) == 2


class TestCreateADKAgentImportError:
    """create_adk_agent() should raise ImportError when ADK is absent."""

    def test_raises_import_error(self, valid_workflow_yaml: str) -> None:
        import beddel_bridge_adk.agent as agent_mod

        registry = PrimitiveRegistry()
        executor = WorkflowExecutor(registry)
        tool = BeddelADKTool(valid_workflow_yaml, executor, name="tool_a")

        original = agent_mod._HAS_ADK
        try:
            agent_mod._HAS_ADK = False
            with pytest.raises(ImportError, match="google-adk is required"):
                create_adk_agent(
                    name="test_agent",
                    model="gemini-2.0-flash",
                    tools=[tool],
                )
        finally:
            agent_mod._HAS_ADK = original
