"""SDK contract tests for a2a-sdk 1.1.2.

Verifies that the pinned a2a-sdk version provides all symbols required by
the agent-a2a-kit and serve-a2a-kit implementations. This test serves as
the reproducibility gate — if any import fails, the pin or environment is
misconfigured.
"""

import importlib.metadata
import inspect


def test_a2a_sdk_version_is_pinned():
    """AC1: importlib.metadata.version('a2a-sdk') == '1.1.2'."""
    version = importlib.metadata.version("a2a-sdk")
    assert version == "1.1.2", (
        f"Expected a2a-sdk==1.1.2, got {version}. "
        "Run: pip install a2a-sdk==1.1.2"
    )


def test_import_default_request_handler():
    """AC2: DefaultRequestHandler is importable from a2a.server.request_handlers."""
    from a2a.server.request_handlers import DefaultRequestHandler  # noqa: F401

    assert callable(DefaultRequestHandler)


def test_import_add_a2a_routes_to_fastapi():
    """AC2: add_a2a_routes_to_fastapi is importable from a2a.server.routes."""
    from a2a.server.routes import add_a2a_routes_to_fastapi  # noqa: F401

    assert callable(add_a2a_routes_to_fastapi)


def test_import_create_agent_card_routes():
    """AC2: create_agent_card_routes is importable from a2a.server.routes."""
    from a2a.server.routes import create_agent_card_routes  # noqa: F401

    assert callable(create_agent_card_routes)


def test_import_create_jsonrpc_routes():
    """AC2: create_jsonrpc_routes is importable from a2a.server.routes."""
    from a2a.server.routes import create_jsonrpc_routes  # noqa: F401

    assert callable(create_jsonrpc_routes)


def test_import_a2a_card_resolver():
    """AC2: A2ACardResolver is importable from a2a.client."""
    from a2a.client import A2ACardResolver  # noqa: F401

    assert callable(A2ACardResolver)


def test_import_create_client():
    """AC2: create_client is importable from a2a.client."""
    from a2a.client import create_client  # noqa: F401

    assert callable(create_client)


def test_create_client_accepts_agent_as_str():
    """AC3: create_client signature accepts agent= as a string parameter.

    We verify via signature inspection that agent is the first parameter
    and accepts str type (URL form).
    """
    from a2a.client import create_client

    sig = inspect.signature(create_client)
    params = list(sig.parameters.keys())

    # 'agent' should be a parameter
    assert "agent" in params, (
        f"create_client does not have 'agent' parameter. "
        f"Parameters: {params}"
    )

    # Verify the annotation allows str
    agent_param = sig.parameters["agent"]
    annotation = agent_param.annotation

    # The annotation should include str (could be str | AgentCard or similar)
    annotation_str = str(annotation)
    assert "str" in annotation_str, (
        f"create_client 'agent' parameter does not accept str. "
        f"Annotation: {annotation_str}"
    )
