"""ADK agent factory helper for Beddel workflow tools.

Provides :func:`create_adk_agent`, a convenience factory that creates an ADK
``Agent`` pre-configured with one or more :class:`BeddelADKTool` instances.

Example::

    from beddel_bridge_adk import BeddelADKTool, create_adk_agent

    agent = create_adk_agent(
        name="my_agent",
        model="gemini-2.0-flash",
        tools=[tool_a, tool_b],
        instruction="You are a helpful assistant.",
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from beddel_bridge_adk.tool import BeddelADKTool

if TYPE_CHECKING:
    from google.adk.agents import Agent

__all__ = ["create_adk_agent"]

try:
    from google.adk.agents import Agent as _Agent

    _HAS_ADK = True
except ImportError:
    _HAS_ADK = False


def create_adk_agent(
    name: str,
    model: str,
    tools: list[BeddelADKTool],
    instruction: str | None = None,
) -> Any:
    """Create an ADK ``Agent`` with Beddel workflow tools.

    Each :class:`BeddelADKTool` is converted to an ADK ``FunctionTool``
    via :meth:`~BeddelADKTool.as_adk_tool` and registered with the agent.

    Args:
        name: Agent name.
        model: Model identifier (e.g. ``"gemini-2.0-flash"``).
        tools: List of :class:`BeddelADKTool` instances to register.
        instruction: Optional system instruction for the agent.

    Returns:
        A configured ADK ``Agent`` instance.

    Raises:
        ImportError: When ``google-adk`` is not installed.
    """
    if not _HAS_ADK:
        raise ImportError(
            "google-adk is required for create_adk_agent(). "
            "Install it with: pip install beddel[bridge-adk]"
        )

    adk_tools = [t.as_adk_tool() for t in tools]

    kwargs: dict[str, Any] = {
        "name": name,
        "model": model,
        "tools": adk_tools,
    }
    if instruction is not None:
        kwargs["instruction"] = instruction

    return _Agent(**kwargs)
