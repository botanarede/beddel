"""Tests for the generic FastAPI application assembly API."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from beddel_serve_fastapi import (
    MiddlewareSpec,
    MountSpec,
    RedirectSpec,
    RouteSpec,
    create_runtime_app,
    run_app,
    serve_app_async,
)


async def _hello() -> dict[str, str]:
    return {"message": "hello"}


async def _created() -> dict[str, str]:
    return {"message": "created"}


def test_route_spec_registers_endpoint() -> None:
    app = create_runtime_app(
        version="1.2.3",
        routes=(RouteSpec("/hello", _hello),),
        static=False,
    )

    with TestClient(app) as client:
        response = client.get("/hello")

    assert response.status_code == 200
    assert response.json() == {"message": "hello"}
    assert app.title == "Beddel"
    assert app.version == "1.2.3"


def test_route_spec_honors_non_get_methods() -> None:
    app = create_runtime_app(
        version="1.0.0",
        routes=(RouteSpec("/created", _created, methods=("POST",)),),
        static=False,
    )

    with TestClient(app) as client:
        assert client.post("/created").status_code == 200
        assert client.get("/created").status_code == 405


def test_cors_is_added_only_for_non_empty_origins() -> None:
    with_cors = create_runtime_app(version="1.0.0", static=False)
    without_cors = create_runtime_app(
        version="1.0.0", cors_origins=(), static=False
    )

    assert any(middleware.cls is CORSMiddleware for middleware in with_cors.user_middleware)
    assert not any(
        middleware.cls is CORSMiddleware
        for middleware in without_cors.user_middleware
    )


def test_mount_spec_uses_prefix() -> None:
    router = APIRouter()

    @router.get("/item")
    async def item() -> dict[str, str]:
        return {"item": "mounted"}

    app = create_runtime_app(
        version="1.0.0",
        routers=(MountSpec(router, prefix="/api"),),
        static=False,
    )

    with TestClient(app) as client:
        response = client.get("/api/item")

    assert response.status_code == 200
    assert response.json() == {"item": "mounted"}


def test_redirect_spec_returns_status_and_location() -> None:
    app = create_runtime_app(
        version="1.0.0",
        redirects=(RedirectSpec("/old", "/new", status_code=307),),
        static=False,
    )

    with TestClient(app) as client:
        response = client.get("/old", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/new"


class _HeaderMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, header_value: str) -> None:
        super().__init__(app)
        self._header_value = header_value

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["X-Kit-Test"] = self._header_value
        return response


def test_middleware_spec_is_applied() -> None:
    app = create_runtime_app(
        version="1.0.0",
        middleware=(
            MiddlewareSpec(_HeaderMiddleware, {"header_value": "applied"}),
        ),
        routes=(RouteSpec("/hello", _hello),),
        static=False,
    )

    with TestClient(app) as client:
        response = client.get("/hello")

    assert response.headers["X-Kit-Test"] == "applied"


def test_static_routes_can_be_enabled_or_disabled() -> None:
    without_static = create_runtime_app(version="1.0.0", static=False)
    with_static = create_runtime_app(version="1.0.0", static=True)

    without_paths = {route.path for route in without_static.routes}
    with_paths = {route.path for route in with_static.routes}
    assert "/" not in without_paths
    assert "/favicon.ico" not in without_paths
    assert "/" in with_paths
    assert "/favicon.ico" in with_paths


def test_shutdown_handlers_run() -> None:
    shutdown_calls: list[str] = []

    async def shutdown() -> None:
        shutdown_calls.append("called")

    app = create_runtime_app(
        version="1.0.0", static=False, on_shutdown=(shutdown,)
    )

    with TestClient(app):
        pass

    assert shutdown_calls == ["called"]


def test_run_app_delegates_to_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Any, str, int, str]] = []

    def fake_run(app: Any, *, host: str, port: int, log_level: str) -> None:
        calls.append((app, host, port, log_level))

    fake_uvicorn = types.ModuleType("uvicorn")
    fake_uvicorn.run = fake_run  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    app = object()

    assert calls == []
    run_app(app, host="127.0.0.1", port=8765, log_level="debug")

    assert calls == [(app, "127.0.0.1", 8765, "debug")]


class _FakeConfig:
    def __init__(self, app: Any, *, host: str, port: int, log_level: str) -> None:
        self.app = app
        self.host = host
        self.port = port
        self.log_level = log_level


class _FakeServer:
    instances: list[_FakeServer] = []

    def __init__(self, config: _FakeConfig) -> None:
        self.config = config
        self.started = False
        self.should_exit = False
        self.__class__.instances.append(self)

    async def serve(self) -> None:
        self.started = True
        # A real uvicorn server keeps running after startup; returning
        # immediately would make callback-ordering tests pass vacuously.
        await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_serve_app_async_invokes_callback_after_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeServer.instances.clear()
    fake_uvicorn = types.ModuleType("uvicorn")
    fake_uvicorn.Config = _FakeConfig  # type: ignore[attr-defined]
    fake_uvicorn.Server = _FakeServer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    started_calls: list[str] = []

    await serve_app_async(
        object(),
        host="127.0.0.1",
        port=8765,
        log_level="warning",
        on_started=lambda: started_calls.append("started"),
    )

    assert started_calls == ["started"]
    assert _FakeServer.instances[0].config.host == "127.0.0.1"
    assert _FakeServer.instances[0].config.port == 8765
    assert _FakeServer.instances[0].config.log_level == "warning"


class _FailingServer(_FakeServer):
    """Raises during serve() before ever setting ``started``."""

    async def serve(self) -> None:
        raise OSError("address already in use")


class _EarlyExitServer(_FakeServer):
    """Returns cleanly without ever setting ``started``."""

    async def serve(self) -> None:
        await asyncio.sleep(0)


class _StartedThenExitedServer(_FakeServer):
    """Sets ``started`` and terminates immediately afterwards."""

    async def serve(self) -> None:
        self.started = True
        await asyncio.sleep(0)


class _PendingServer(_FakeServer):
    """Starts and then stays pending until cancelled, like a real server."""

    def __init__(self, config: _FakeConfig) -> None:
        super().__init__(config)
        self.cancelled = False

    async def serve(self) -> None:
        self.started = True
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


def _patch_uvicorn(
    monkeypatch: pytest.MonkeyPatch, server_class: type
) -> None:
    fake_uvicorn = types.ModuleType("uvicorn")
    fake_uvicorn.Config = _FakeConfig  # type: ignore[attr-defined]
    fake_uvicorn.Server = server_class  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)


@pytest.mark.asyncio
async def test_serve_app_async_propagates_startup_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_uvicorn(monkeypatch, _FailingServer)
    started_calls: list[str] = []

    with pytest.raises(OSError, match="address already in use"):
        await asyncio.wait_for(
            serve_app_async(
                object(),
                host="127.0.0.1",
                port=8765,
                on_started=lambda: started_calls.append("started"),
            ),
            timeout=5,
        )

    assert started_calls == []


@pytest.mark.asyncio
async def test_serve_app_async_raises_when_server_exits_before_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_uvicorn(monkeypatch, _EarlyExitServer)
    started_calls: list[str] = []

    with pytest.raises(RuntimeError, match="before completing startup"):
        await asyncio.wait_for(
            serve_app_async(
                object(),
                host="127.0.0.1",
                port=8765,
                on_started=lambda: started_calls.append("started"),
            ),
            timeout=5,
        )

    assert started_calls == []


@pytest.mark.asyncio
async def test_serve_app_async_skips_callback_when_server_exited_after_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _StartedThenExitedServer.instances.clear()
    _patch_uvicorn(monkeypatch, _StartedThenExitedServer)
    started_calls: list[str] = []

    await asyncio.wait_for(
        serve_app_async(
            object(),
            host="127.0.0.1",
            port=8765,
            on_started=lambda: started_calls.append("started"),
        ),
        timeout=5,
    )

    assert started_calls == []


@pytest.mark.asyncio
async def test_serve_app_async_cancels_pending_server_when_callback_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _PendingServer.instances.clear()
    _patch_uvicorn(monkeypatch, _PendingServer)

    def _boom() -> None:
        raise ValueError("callback failed")

    with pytest.raises(ValueError, match="callback failed"):
        await asyncio.wait_for(
            serve_app_async(
                object(), host="127.0.0.1", port=8765, on_started=_boom
            ),
            timeout=5,
        )

    server = _PendingServer.instances[0]
    assert server.should_exit is True
    assert server.cancelled is True


@pytest.mark.asyncio
async def test_serve_app_async_invokes_callback_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_uvicorn(monkeypatch, _FakeServer)
    started_calls: list[str] = []

    await serve_app_async(
        object(),
        host="127.0.0.1",
        port=8765,
        on_started=lambda: started_calls.append("started"),
    )

    assert started_calls == ["started"]


def test_app_import_does_not_import_frameworks() -> None:
    kit_root = Path(__file__).resolve().parent.parent
    pythonpath = os.pathsep.join(
        [
            str(kit_root / "python"),
            str(kit_root.parent.parent.parent.parent / "packages/beddel-py/src"),
        ]
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import beddel_serve_fastapi.app; "
                "assert 'fastapi' not in sys.modules; "
                "assert 'uvicorn' not in sys.modules; "
                "assert 'starlette' not in sys.modules; "
                "assert 'sse_starlette' not in sys.modules"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": str(Path(sys.executable).parent), "PYTHONPATH": pythonpath},
    )

    assert result.returncode == 0, result.stderr
