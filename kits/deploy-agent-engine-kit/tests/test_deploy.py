"""Unit tests for deploy adapter module (deploy.py).

Mocks all GCP/ADK dependencies so tests run without google-adk installed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestDeployFlowSuccess:
    """Tests for the success path of deploy_flow_to_agent_engine."""

    def test_returns_deploy_result_with_correct_fields(self, tmp_path: Path) -> None:
        """deploy_flow_to_agent_engine returns a DeployResult with all fields populated."""
        flow_file = tmp_path / "test-flow.yaml"
        flow_file.write_text("id: test-flow\nname: Test Flow\nsteps: []")

        mock_agent_engines = MagicMock()
        mock_vertexai = MagicMock()
        mock_vertexai.agent_engines = mock_agent_engines
        mock_llm_agent = MagicMock()

        mock_remote_app = MagicMock()
        mock_remote_app.resource_name = (
            "projects/your-project-id/locations/us-central1/agents/agent-123"
        )
        mock_agent_engines.create.return_value = mock_remote_app

        mock_workflow = MagicMock()
        mock_workflow.id = "test_flow"
        mock_workflow.name = "Test Flow"
        mock_workflow.description = "A test flow"
        mock_workflow.input_schema = {"properties": {"topic": {"type": "string", "description": "Topic"}}}
        mock_step = MagicMock()
        mock_step.primitive = "llm"
        mock_step.config = {"model": "gemini-2.5-flash"}
        mock_workflow.steps = [mock_step]

        mock_parser = MagicMock()
        mock_parser.parse.return_value = mock_workflow

        mock_google_adk_agents = MagicMock()
        mock_google_adk_agents.LlmAgent = mock_llm_agent

        fake_modules: dict[str, Any] = {
            "vertexai": mock_vertexai,
            "vertexai.agent_engines": mock_agent_engines,
            "google": MagicMock(),
            "google.adk": MagicMock(),
            "google.adk.agents": mock_google_adk_agents,
            "beddel": MagicMock(),
            "beddel.domain": MagicMock(),
            "beddel.domain.parser": MagicMock(WorkflowParser=mock_parser),
        }

        with patch.dict("sys.modules", fake_modules):
            if "beddel_deploy_agent_engine.deploy" in sys.modules:
                del sys.modules["beddel_deploy_agent_engine.deploy"]

            from beddel_deploy_agent_engine.deploy import deploy_flow_to_agent_engine

            result = deploy_flow_to_agent_engine(
                flow_path=flow_file,
                project="your-project-id",
                region="us-central1",
                staging_bucket="gs://beddel-workflows",
            )

        assert result.resource_name == "projects/your-project-id/locations/us-central1/agents/agent-123"
        assert result.display_name == "Beddel: Test Flow"
        assert result.project == "your-project-id"
        assert result.region == "us-central1"
        assert "agent-123" in result.console_url
        assert "your-project-id" in result.console_url

    def test_vertexai_init_called_with_correct_params(self, tmp_path: Path) -> None:
        """vertexai.init() is called with project, location, and staging_bucket."""
        flow_file = tmp_path / "test-flow.yaml"
        flow_file.write_text("id: my-flow\nname: My Flow\nsteps: []")

        mock_agent_engines = MagicMock()
        mock_vertexai = MagicMock()
        mock_vertexai.agent_engines = mock_agent_engines
        mock_llm_agent = MagicMock()

        mock_remote_app = MagicMock()
        mock_remote_app.resource_name = "projects/p1/locations/us-central1/agents/a1"
        mock_agent_engines.create.return_value = mock_remote_app

        mock_workflow = MagicMock()
        mock_workflow.id = "my_flow"
        mock_workflow.name = "My Flow"
        mock_workflow.description = None
        mock_workflow.input_schema = {"properties": {}}
        mock_workflow.steps = []

        mock_parser = MagicMock()
        mock_parser.parse.return_value = mock_workflow

        fake_modules: dict[str, Any] = {
            "vertexai": mock_vertexai,
            "vertexai.agent_engines": mock_agent_engines,
            "google": MagicMock(),
            "google.adk": MagicMock(),
            "google.adk.agents": MagicMock(LlmAgent=mock_llm_agent),
            "beddel": MagicMock(),
            "beddel.domain": MagicMock(),
            "beddel.domain.parser": MagicMock(WorkflowParser=mock_parser),
        }

        with patch.dict("sys.modules", fake_modules):
            if "beddel_deploy_agent_engine.deploy" in sys.modules:
                del sys.modules["beddel_deploy_agent_engine.deploy"]

            from beddel_deploy_agent_engine.deploy import deploy_flow_to_agent_engine

            deploy_flow_to_agent_engine(
                flow_path=flow_file,
                project="my-project",
                region="europe-west1",
                staging_bucket="gs://my-bucket",
            )

        mock_vertexai.init.assert_called_once_with(
            project="my-project",
            location="europe-west1",
            staging_bucket="gs://my-bucket",
        )

    def test_agent_engines_create_called(self, tmp_path: Path) -> None:
        """agent_engines.create() is called with correct arguments."""
        flow_file = tmp_path / "test-flow.yaml"
        flow_file.write_text("id: deploy-me\nname: Deploy Me\nsteps: []")

        mock_agent_engines = MagicMock()
        mock_vertexai = MagicMock()
        mock_vertexai.agent_engines = mock_agent_engines
        mock_llm_agent_cls = MagicMock()

        mock_remote_app = MagicMock()
        mock_remote_app.resource_name = "projects/p/locations/r/agents/x"
        mock_agent_engines.create.return_value = mock_remote_app

        mock_workflow = MagicMock()
        mock_workflow.id = "deploy_me"
        mock_workflow.name = "Deploy Me"
        mock_workflow.description = "Deploys things"
        mock_workflow.input_schema = {"properties": {"x": {"type": "string", "description": "x"}}}
        mock_workflow.steps = []

        mock_parser = MagicMock()
        mock_parser.parse.return_value = mock_workflow

        fake_modules: dict[str, Any] = {
            "vertexai": mock_vertexai,
            "vertexai.agent_engines": mock_agent_engines,
            "google": MagicMock(),
            "google.adk": MagicMock(),
            "google.adk.agents": MagicMock(LlmAgent=mock_llm_agent_cls),
            "beddel": MagicMock(),
            "beddel.domain": MagicMock(),
            "beddel.domain.parser": MagicMock(WorkflowParser=mock_parser),
        }

        with patch.dict("sys.modules", fake_modules):
            if "beddel_deploy_agent_engine.deploy" in sys.modules:
                del sys.modules["beddel_deploy_agent_engine.deploy"]

            from beddel_deploy_agent_engine.deploy import deploy_flow_to_agent_engine

            deploy_flow_to_agent_engine(flow_path=flow_file)

        mock_agent_engines.create.assert_called_once()
        call_kwargs = mock_agent_engines.create.call_args[1]
        assert call_kwargs["display_name"] == "Beddel: Deploy Me"
        assert "beddel" in call_kwargs["requirements"][2].lower()


class TestDeployFlowImportError:
    """Tests for the ImportError path when google-adk is not installed."""

    def test_raises_import_error_when_google_adk_missing(self, tmp_path: Path) -> None:
        """deploy_flow_to_agent_engine raises ImportError with install instructions."""
        flow_file = tmp_path / "test-flow.yaml"
        flow_file.write_text("id: test\nname: Test\nsteps: []")

        # Ensure vertexai is NOT in sys.modules so the import inside the function fails
        original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__  # type: ignore[union-attr]

        def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name in ("vertexai", "google.adk.agents", "google.adk"):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        # Clear cached module to force re-import
        if "beddel_deploy_agent_engine.deploy" in sys.modules:
            del sys.modules["beddel_deploy_agent_engine.deploy"]

        with patch("builtins.__import__", side_effect=fake_import):
            from beddel_deploy_agent_engine.deploy import deploy_flow_to_agent_engine

            with pytest.raises(ImportError, match="google-adk"):
                deploy_flow_to_agent_engine(flow_path=flow_file)


class TestDeployResult:
    """Tests for the DeployResult dataclass."""

    def test_deploy_result_fields(self) -> None:
        """DeployResult stores all required fields."""
        from beddel_deploy_agent_engine.deploy import DeployResult

        result = DeployResult(
            resource_name="projects/p/locations/r/agents/a",
            display_name="Test",
            project="p",
            region="r",
            console_url="https://console.cloud.google.com/gen-app-builder/engines/a?project=p",
        )
        assert result.resource_name == "projects/p/locations/r/agents/a"
        assert result.display_name == "Test"
        assert result.project == "p"
        assert result.region == "r"
        assert "console.cloud.google.com" in result.console_url
