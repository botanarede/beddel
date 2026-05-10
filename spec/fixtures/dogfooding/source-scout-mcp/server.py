"""Source Scout MCP Server.

Exposes a single tool `scout_sources` that discovers, validates, and ranks
RSS/API sources for any given theme. Each call runs the full beddel workflow
pipeline and returns a JSON array of ranked sources.

Usage:
    python server.py                    # stdio mode (for MCP clients)
    python server.py --test "samba"     # quick test without MCP client

MCP config (add to ~/.kiro/settings/mcp.json):
    "source-scout": {
        "command": "python",
        "args": ["spec/fixtures/dogfooding/source-scout-mcp/server.py"],
        "autoApprove": ["scout_sources"]
    }

Requirements:
    pip install mcp beddel
    GROQ_API_KEY must be set in environment.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Source Scout",
    instructions=(
        "Source Scout discovers RSS feeds, APIs, and blogs for any topic. "
        "Call scout_sources with a theme like 'cultura negra', 'jazz', "
        "'gastronomia africana', etc. Returns a ranked JSON array of sources "
        "with feed URLs, scores, and priorities."
    ),
)

# Resolve workflow path relative to this file
WORKFLOW_PATH = Path(__file__).parent / "workflow.yaml"


async def _run_workflow(theme: str, max_sources: str = "8", lang: str = "any") -> str:
    """Execute the beddel source-scout workflow and return the final output."""
    from beddel.domain.executor import WorkflowExecutor
    from beddel.domain.models import ExecutionDependencies
    from beddel.domain.parser import WorkflowParser
    from beddel.domain.registry import PrimitiveRegistry, register_builtins
    from beddel.domain.resolver import VariableResolver

    # Parse workflow
    yaml_str = WORKFLOW_PATH.read_text()
    workflow = WorkflowParser.parse(yaml_str)

    # Build registry with builtins (llm, tool, output-generator)
    registry = PrimitiveRegistry()
    register_builtins(registry)

    # Register http_request tool from kit
    try:
        from beddel.kits import discover_kits

        for kit in discover_kits():
            kit.register(registry)
    except Exception:
        # Fallback: register http_request directly
        try:
            from beddel_tools_http.http import http_request

            registry.register_tool("http_request", http_request)
        except ImportError:
            pass

    # Build dependencies
    try:
        from beddel_provider_litellm.adapter import LiteLLMAdapter

        provider = LiteLLMAdapter()
    except ImportError:
        from beddel.adapters.litellm_adapter import LiteLLMAdapter

        provider = LiteLLMAdapter()

    deps = ExecutionDependencies(
        llm_provider=provider,
        registry=registry,
    )

    # Execute
    resolver = VariableResolver()
    executor = WorkflowExecutor(
        registry=registry,
        resolver=resolver,
        deps=deps,
    )

    inputs = {"theme": theme, "max": max_sources, "lang": lang}
    result = await executor.execute(workflow, inputs=inputs)

    # Extract the final step output
    if hasattr(result, "step_results"):
        # Get the last step's content
        for step_id in ["output", "rank", "discover"]:
            if step_id in result.step_results:
                step_result = result.step_results[step_id]
                if hasattr(step_result, "content"):
                    return step_result.content
                return str(step_result)

    return json.dumps({"error": "No output from workflow", "raw": str(result)})


@mcp.tool()
async def scout_sources(
    theme: str,
    max_sources: str = "8",
    lang: str = "any",
) -> str:
    """Discover, validate, and rank RSS/API/blog sources for a given theme.

    Args:
        theme: Topic to find sources for (e.g. "cultura negra", "jazz brasileiro",
               "gastronomia africana", "samba e pagode").
        max_sources: Maximum number of sources to return (default: "8").
        lang: Preferred language — "pt-br", "en", or "any" (default: "any").

    Returns:
        JSON array of ranked sources. Each source has:
        - name: Source name
        - url: Website URL
        - feed_url: RSS/Atom feed URL (or null)
        - type: rss, api, blog, news, magazine
        - lang: Content language
        - desc: Brief description
        - score: Quality score 0.0-1.0
        - priority: high, medium, or low
    """
    return await _run_workflow(theme, max_sources, lang)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Quick test mode: run workflow directly
        theme = sys.argv[2] if len(sys.argv) > 2 else "cultura negra brasileira"
        print(f"Testing source scout for: {theme}")
        print("---")
        result = asyncio.run(_run_workflow(theme, "5", "pt-br"))
        try:
            parsed = json.loads(result)
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(result)
    else:
        # MCP server mode (stdio)
        mcp.run()
