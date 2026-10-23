"""Review route resolution (AD-16, AD-18) — the single seam to the agent adapter.

A static, kit-local map from the configured ``REVIEW_AGENT`` name to the adapter
that implements it. It is never core discovery: no core port, registry or
mechanism is added. ``tools/review.py`` obtains its adapter only through
:func:`get_review_adapter`, which is what tests replace with a fake.

The factory never passes an ``api_key`` (so the route runs in SSO/OAuth mode),
never lets the adapter auto-install anything (the binary is located here and
handed over explicitly) and never reads or writes the route's session store.
"""

from __future__ import annotations

import importlib
import os
import shutil
from pathlib import Path

from beddel.domain.errors import AgentError
from beddel.domain.ports import IAgentAdapter
from beddel.error_codes import AGENT_EXECUTION_FAILED

from beddel_profile_dev._errors import PROFILE_REVIEW_UNSCOPED, ProfileError

__all__ = ["REVIEW_ADAPTERS", "get_review_adapter"]

# REVIEW_AGENT -> (module, class). Resolved lazily: the adapter kit is on
# ``sys.path`` only when its kit directory is configured, and a route that
# cannot be loaded is a recorded ``errored`` outcome, not an import-time crash.
REVIEW_ADAPTERS: dict[str, tuple[str, str]] = {
    "kiro": ("beddel_agent_kiro", "KiroCLIAgentAdapter"),
}

# The default install location of the route's binary (a binary, not a session).
_KIRO_CLI_NAME = "kiro-cli"


def _locate_cli() -> Path | None:
    """Return the route's binary if it is already installed; never install it."""
    default = Path.home() / ".local" / "bin" / _KIRO_CLI_NAME
    if default.is_file() and os.access(default, os.X_OK):
        return default
    found = shutil.which(_KIRO_CLI_NAME)
    return Path(found) if found else None


def _unavailable(agent_name: str) -> AgentError:
    return AgentError(
        code=AGENT_EXECUTION_FAILED,
        message="review agent route is not available",
        details={"agent": agent_name},
    )


def get_review_adapter(agent_name: str, *, timeout_seconds: int) -> IAgentAdapter:
    """Return the adapter of the configured review route.

    Raises:
        ProfileError: ``PROFILE_REVIEW_UNSCOPED`` for a name outside the map.
        AgentError: ``AGENT_EXECUTION_FAILED`` when the route cannot be loaded or
            its binary is absent. The caller records it as an ``errored``
            outcome; the route is never installed or authenticated from here.
    """
    entry = REVIEW_ADAPTERS.get(agent_name)
    if entry is None:
        raise ProfileError(PROFILE_REVIEW_UNSCOPED, "review agent is not a known route")
    module_name, class_name = entry
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, class_name)
    except (ImportError, AttributeError) as error:
        raise _unavailable(agent_name) from error
    cli_path = _locate_cli()
    if cli_path is None:
        raise _unavailable(agent_name)
    # No ``api_key``: with ``KIRO_API_KEY`` also absent the route is not headless.
    adapter: IAgentAdapter = factory(cli_path=cli_path, timeout=timeout_seconds)
    return adapter
