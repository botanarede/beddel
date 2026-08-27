"""Beddel serve-fastapi-kit — FastAPI serving + SSE.

Re-exports the public API from the kit's modules:

- :func:`create_beddel_handler` — one-line workflow-to-endpoint factory
- :class:`BeddelSSEAdapter` — SSE adapter for workflow event streams
- :class:`BeddelServer` — background Uvicorn server lifecycle handle
- :func:`start_beddel_server` — start an ASGI app in a daemon-thread server
- :func:`create_runtime_app` — assemble a configured FastAPI application
- :func:`run_app` — run an application in the foreground
- :func:`serve_app_async` — serve an application on the running loop
"""

from __future__ import annotations

__all__ = [
    "BeddelSSEAdapter",
    "BeddelServer",
    "MiddlewareSpec",
    "MountSpec",
    "RedirectSpec",
    "RouteSpec",
    "create_beddel_handler",
    "create_runtime_app",
    "run_app",
    "serve_app_async",
    "start_beddel_server",
]


def __getattr__(name: str) -> object:
    """Lazy-load kit symbols to avoid import-time side effects."""
    if name == "create_beddel_handler":
        from beddel_serve_fastapi.handler import create_beddel_handler

        return create_beddel_handler
    if name == "BeddelSSEAdapter":
        from beddel_serve_fastapi.sse import BeddelSSEAdapter

        return BeddelSSEAdapter
    if name == "BeddelServer":
        from beddel_serve_fastapi.server import BeddelServer

        return BeddelServer
    if name == "start_beddel_server":
        from beddel_serve_fastapi.server import start_beddel_server

        return start_beddel_server
    if name in {
        "MiddlewareSpec",
        "MountSpec",
        "RedirectSpec",
        "RouteSpec",
        "create_runtime_app",
        "run_app",
        "serve_app_async",
    }:
        from beddel_serve_fastapi import app

        return getattr(app, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
