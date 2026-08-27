"""Generic FastAPI application assembly and serving helpers.

The framework-free specifications in this module let core and sibling kits
provide routes, routers, redirects, and middleware without importing web
frameworks themselves.  The existing :func:`start_beddel_server` in
``beddel_serve_fastapi.server`` remains the threaded runner for the ``connect``
case.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

__all__ = [
    "MiddlewareSpec",
    "MountSpec",
    "RedirectSpec",
    "RouteSpec",
    "create_runtime_app",
    "run_app",
    "serve_app_async",
]


@dataclass(frozen=True)
class RouteSpec:
    """Describe an endpoint route without exposing framework types."""

    path: str
    endpoint: Callable[..., Awaitable[Any]]
    methods: Sequence[str] = ("GET",)
    name: str | None = None


@dataclass(frozen=True)
class MountSpec:
    """Describe a router to include under an optional URL prefix."""

    router: Any
    prefix: str = ""


@dataclass(frozen=True)
class RedirectSpec:
    """Describe a GET redirect route."""

    path: str
    target: str
    status_code: int = 301


@dataclass(frozen=True)
class MiddlewareSpec:
    """Describe middleware to add to the assembled application."""

    middleware_class: type
    options: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )


def create_runtime_app(
    *,
    version: str,
    title: str = "Beddel",
    cors_origins: Sequence[str] = ("http://localhost:3000",),
    routes: Sequence[RouteSpec] = (),
    routers: Sequence[MountSpec] = (),
    redirects: Sequence[RedirectSpec] = (),
    middleware: Sequence[MiddlewareSpec] = (),
    static: bool = True,
    on_shutdown: Sequence[Callable[[], Awaitable[None]]] = (),
) -> Any:
    """Assemble a configured FastAPI application."""
    from fastapi import FastAPI

    app = FastAPI(title=title, version=version)

    if cors_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    for spec in middleware:
        app.add_middleware(spec.middleware_class, **dict(spec.options))

    for spec in routes:
        app.add_api_route(
            spec.path,
            spec.endpoint,
            methods=list(spec.methods),
            name=spec.name,
        )

    for spec in routers:
        app.include_router(spec.router, prefix=spec.prefix)

    from starlette.responses import RedirectResponse

    for spec in redirects:
        async def _redirect(spec: RedirectSpec = spec) -> RedirectResponse:
            return RedirectResponse(spec.target, status_code=spec.status_code)

        app.add_api_route(spec.path, _redirect, methods=["GET"])

    if static:
        from beddel_serve_fastapi.static_routes import register_static_routes

        register_static_routes(app)

    for shutdown_handler in on_shutdown:
        app.router.on_shutdown.append(shutdown_handler)

    return app


def run_app(app: Any, *, host: str, port: int, log_level: str = "info") -> None:
    """Run the app in the foreground until it exits."""
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level=log_level)


async def serve_app_async(
    app: Any,
    *,
    host: str,
    port: int,
    log_level: str = "warning",
    on_started: Callable[[], None] | None = None,
) -> None:
    """Serve the app on the running loop, invoking on_started after startup."""
    import asyncio

    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level=log_level)
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    def _fail_if_exited_before_startup() -> None:
        if task.done():
            # Propagate a real startup failure (e.g. port already in use)
            # instead of waiting forever for a flag that will never be set.
            task.result()
            raise RuntimeError(
                f"server exited before completing startup on {host}:{port}"
            )

    try:
        while not server.started:
            _fail_if_exited_before_startup()
            await asyncio.sleep(0.05)
        # The server may have started and already terminated; signalling a
        # caller that the server is ready would be wrong in that case.
        if on_started is not None and not task.done():
            on_started()
        await task
    except BaseException:
        server.should_exit = True
        if not task.done():
            task.cancel()
        try:
            await task
        except BaseException:
            pass
        raise
