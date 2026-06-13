"""Deploy adapter for Vertex AI Agent Engine."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class DeployResult:
    """Result of a successful Agent Engine deployment."""

    resource_name: str
    display_name: str
    project: str
    region: str
    console_url: str


def _load_workflow_metadata(flow_path: Path) -> dict[str, Any]:
    """Parse workflow YAML and extract metadata for the ADK agent.

    Args:
        flow_path: Path to the Beddel workflow YAML file.

    Returns:
        Dict with id, name, description, model, input_schema, workflow.
    """
    from beddel.domain.parser import WorkflowParser

    yaml_str = flow_path.read_text()
    workflow = WorkflowParser.parse(yaml_str)

    # Extract the model from the first LLM step (the workflow's primary model)
    model = "gemini-2.5-flash"  # fallback
    for step in workflow.steps:
        if step.primitive == "llm" and step.config.get("model"):
            model = step.config["model"]
            break

    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description or f"Beddel flow: {workflow.name}",
        "model": model,
        "input_schema": workflow.input_schema or {},
        "workflow": workflow,
    }


def _run_beddel_flow(flow_path: Path, inputs: dict[str, Any]) -> dict[str, Any]:
    """Execute a Beddel flow programmatically and return step_results.

    Args:
        flow_path: Path to the Beddel workflow YAML file.
        inputs: Input values for the workflow execution.

    Returns:
        Dict of step_id -> step result from workflow execution.
    """
    from beddel.cli.commands import (
        _build_adapter_registries,
        _ensure_kit_paths,
        _resolve_all_kit_paths,
    )
    from beddel.domain.executor import WorkflowExecutor
    from beddel.domain.models import DefaultDependencies
    from beddel.domain.parser import WorkflowParser
    from beddel.domain.registry import PrimitiveRegistry
    from beddel.primitives import register_builtins
    from beddel.tools.kits import discover_kits

    _ensure_kit_paths()

    yaml_str = flow_path.read_text()
    workflow = WorkflowParser.parse(yaml_str)

    registry = PrimitiveRegistry()
    register_builtins(registry)

    discovery_result = discover_kits(_resolve_all_kit_paths(()))
    agent_registry, llm_provider = _build_adapter_registries(discovery_result)

    deps = DefaultDependencies(
        llm_provider=llm_provider,
        agent_registry=agent_registry or None,
        tool_registry={},
        workflow_loader=None,
        registry=registry,
    )
    executor = WorkflowExecutor(registry, deps=deps)

    result = asyncio.run(executor.execute(workflow, inputs))
    return result.get("step_results", {})


def _build_tool_function(flow_path: Path, metadata: dict[str, Any]) -> Callable[..., dict[str, Any]]:
    """Dynamically build the ADK tool function from workflow input_schema.

    Uses exec() to create a function with named parameters that ADK can introspect.

    Args:
        flow_path: Path to the Beddel workflow YAML file.
        metadata: Workflow metadata from _load_workflow_metadata().

    Returns:
        A callable tool function with explicit named parameters.
    """
    properties = metadata["input_schema"].get("properties", {})

    # Build parameter descriptions for the docstring
    param_docs = []
    for name, prop in properties.items():
        desc = prop.get("description", name)
        param_docs.append(f"        {name}: {desc}")

    docstring = (
        f"Execute the '{metadata['name']}' Beddel workflow.\n\n"
        f"    {metadata['description']}\n\n"
        f"    Args:\n" + "\n".join(param_docs) + "\n\n"
        "    Returns:\n"
        "        dict with step results from the workflow execution."
    )

    # Build a proper function with named parameters for ADK
    # ADK needs explicit parameter names (not **kwargs)
    exec_globals: dict[str, Any] = {"_run_beddel_flow": _run_beddel_flow, "flow_path": flow_path}
    func_params = ", ".join(f"{name}: str" for name in properties)
    func_body = (
        f"def {metadata['id']}({func_params}) -> dict:\n"
        f"    \"\"\"{docstring}\"\"\"\n"
        f"    inputs = {{{', '.join(f'\"{name}\": {name}' for name in properties)}}}\n"
        f"    step_results = _run_beddel_flow(flow_path, inputs)\n"
        f"    last_step = list(step_results.values())[-1] if step_results else {{}}\n"
        f"    content = last_step.get('content', str(last_step)) if isinstance(last_step, dict) else str(last_step)\n"
        f"    return {{'result': content, 'all_steps': {{k: str(v)[:500] for k, v in step_results.items()}}}}\n"
    )
    exec(func_body, exec_globals)  # noqa: S102
    return exec_globals[metadata["id"]]


def deploy_flow_to_agent_engine(
    flow_path: Path,
    project: str = "your-project-id",
    region: str = "us-central1",
    staging_bucket: str = "gs://beddel-workflows",
) -> DeployResult:
    """Deploy a Beddel flow YAML to Vertex AI Agent Engine (in-process).

    Follows the in-process build strategy: parse flow YAML, build an LlmAgent
    with a dynamic tool function, and deploy via agent_engines.create().

    Args:
        flow_path: Path to the Beddel workflow YAML file.
        project: GCP project ID.
        region: Vertex AI region.
        staging_bucket: GCS bucket for staging artifacts.

    Returns:
        DeployResult with resource_name, display_name, project, region, console_url.

    Raises:
        ImportError: If google-adk or vertexai are not installed.
        FileNotFoundError: If flow_path does not exist.
    """
    try:
        import vertexai
        from google.adk.agents import LlmAgent
        from vertexai import agent_engines
    except ImportError as exc:
        raise ImportError(
            "Deploy requires google-adk and google-cloud-aiplatform. "
            "Install with: pip install 'google-cloud-aiplatform[adk,agent_engines]' 'google-adk>=2.0.0'"
        ) from exc

    # Load workflow metadata from YAML
    metadata = _load_workflow_metadata(flow_path)

    # Initialize Vertex AI
    vertexai.init(project=project, location=region, staging_bucket=staging_bucket)

    # Build the tool function from the workflow
    tool_fn = _build_tool_function(flow_path, metadata)

    # Create the ADK agent using the same model declared in the workflow
    agent = LlmAgent(
        model=metadata["model"],
        name=metadata["id"],
        instruction=(
            f"You are an agent that executes the '{metadata['name']}' workflow. "
            f"Description: {metadata['description']}. "
            f"Use the {metadata['id']} tool to execute it. "
            f"Report results clearly to the user."
        ),
        tools=[tool_fn],
    )

    # Deploy to Agent Engine
    display_name = f"Beddel: {metadata['name']}"
    remote_app = agent_engines.create(
        agent_engine=agent,
        requirements=[
            "google-cloud-aiplatform[adk,agent_engines]",
            "google-adk>=2.0.0",
            "beddel>=0.1.9",
        ],
        display_name=display_name,
    )

    # Build console URL from resource_name
    resource_name: str = remote_app.resource_name
    engine_id = resource_name.split("/")[-1]
    console_url = (
        f"https://console.cloud.google.com/gen-app-builder/engines/{engine_id}"
        f"?project={project}"
    )

    return DeployResult(
        resource_name=resource_name,
        display_name=display_name,
        project=project,
        region=region,
        console_url=console_url,
    )
