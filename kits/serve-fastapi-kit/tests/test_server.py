"""Tests for the kit-owned Uvicorn server lifecycle."""

from __future__ import annotations

import importlib
import subprocess
import sys
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from beddel_serve_fastapi import BeddelServer, start_beddel_server


class FakeUvicornConfig:
    def __init__(self, app: Any, *, host: str, port: int, log_level: str) -> None:
        self.app = app
        self.host = host
        self.port = port
        self.log_level = log_level


class FakeUvicornServer:
    def __init__(self, config: FakeUvicornConfig) -> None:
        self.config = config
        self.should_exit = False
        self.started = False
        self.run_calls = 0

    def run(self) -> None:
        self.run_calls += 1


class FakeThread:
    instances: list[FakeThread] = []

    def __init__(self, *, target: Callable[[], None], daemon: bool) -> None:
        self.target = target
        self.daemon = daemon
        self.start_calls = 0
        self.join_timeouts: list[float | None] = []
        self.__class__.instances.append(self)

    def start(self) -> None:
        self.start_calls += 1

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)


@pytest.fixture
def fake_uvicorn(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    FakeThread.instances.clear()
    servers: list[FakeUvicornServer] = []

    def server_factory(config: FakeUvicornConfig) -> FakeUvicornServer:
        server = FakeUvicornServer(config)
        servers.append(server)
        return server

    fake_module = types.ModuleType("uvicorn")
    fake_module.Config = FakeUvicornConfig  # type: ignore[attr-defined]
    fake_module.Server = server_factory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "uvicorn", fake_module)

    import threading

    monkeypatch.setattr(threading, "Thread", FakeThread)
    return {"servers": servers}


def test_start_creates_daemon_server_without_exposing_framework_details(
    fake_uvicorn: dict[str, Any],
) -> None:
    app = object()

    server = start_beddel_server(app, host="127.0.0.1", port=8765)

    assert isinstance(server, BeddelServer)
    uvicorn_server = fake_uvicorn["servers"][0]
    assert uvicorn_server.config.app is app
    assert uvicorn_server.config.host == "127.0.0.1"
    assert uvicorn_server.config.port == 8765
    assert uvicorn_server.config.log_level == "info"
    thread = FakeThread.instances[0]
    assert thread.daemon is True
    assert thread.start_calls == 1
    thread.target()
    assert uvicorn_server.run_calls == 1


@pytest.mark.parametrize("started", [False, True])
def test_started_exposes_underlying_server_state(
    fake_uvicorn: dict[str, Any], started: bool
) -> None:
    server = start_beddel_server(object(), host="localhost", port=8000)
    uvicorn_server = fake_uvicorn["servers"][0]
    uvicorn_server.started = started

    assert server.started is started


def test_non_default_log_level_reaches_uvicorn_config(
    fake_uvicorn: dict[str, Any],
) -> None:
    start_beddel_server(
        object(), host="localhost", port=8000, log_level="warning"
    )

    assert fake_uvicorn["servers"][0].config.log_level == "warning"


def test_default_log_level_remains_info(fake_uvicorn: dict[str, Any]) -> None:
    start_beddel_server(object(), host="localhost", port=8000)

    assert fake_uvicorn["servers"][0].config.log_level == "info"


def test_shutdown_requests_exit_and_joins_with_timeout(
    fake_uvicorn: dict[str, Any],
) -> None:
    server = start_beddel_server(object(), host="localhost", port=8000)
    uvicorn_server = fake_uvicorn["servers"][0]

    server.shutdown(timeout=2.5)

    assert uvicorn_server.should_exit is True
    assert FakeThread.instances[0].join_timeouts == [2.5]


def test_wait_exposes_thread_join_for_external_shutdown_wait(
    fake_uvicorn: dict[str, Any],
) -> None:
    server = start_beddel_server(object(), host="localhost", port=8000)

    server.wait(timeout=1.25)

    assert FakeThread.instances[0].join_timeouts == [1.25]


def test_package_import_does_not_import_uvicorn() -> None:
    kit_root = Path(__file__).resolve().parent.parent
    pythonpath = ":".join(
        [
            str(kit_root / "python"),
            str(kit_root.parent.parent.parent.parent / "packages/beddel-py/src"),
        ]
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import beddel_serve_fastapi; assert 'uvicorn' not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": str(Path(sys.executable).parent), "PYTHONPATH": pythonpath},
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "module_name",
    ["beddel_serve_fastapi", "beddel_serve_fastapi.server"],
)
def test_reloadable_imports_remain_available(module_name: str) -> None:
    importlib.import_module(module_name)
