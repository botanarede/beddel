"""Beddel deploy-agent-engine-kit — Deploy Beddel flows to Vertex AI Agent Engine.

Re-exports the public API from the kit's modules:

- :func:`check_adc` — Check ADC configuration and return project/error info
- :func:`deploy_flow_to_agent_engine` — Deploy a flow YAML to Agent Engine (in-process)
- :class:`DeployResult` — Dataclass with deployment result metadata
"""

from __future__ import annotations

__all__ = ["check_adc", "deploy_flow_to_agent_engine", "DeployResult"]


def __getattr__(name: str) -> object:
    """Lazy-load kit symbols to avoid import-time side effects."""
    if name == "check_adc":
        from beddel_deploy_agent_engine.adc import check_adc

        return check_adc
    if name == "deploy_flow_to_agent_engine":
        from beddel_deploy_agent_engine.deploy import deploy_flow_to_agent_engine

        return deploy_flow_to_agent_engine
    if name == "DeployResult":
        from beddel_deploy_agent_engine.deploy import DeployResult

        return DeployResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
