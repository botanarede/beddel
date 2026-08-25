"""Uvicorn server lifecycle adapter for Beddel ASGI applications."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, final

__all__ = ["BeddelServer", "start_beddel_server"]


class _UvicornServer(Protocol):
    should_exit: bool
    started: bool

    def run(self) -> None:
        """Run the configured Uvicorn server."""


class _ServerThread(Protocol):
    def join(self, timeout: float | None = None) -> None:
        """Wait for the server thread to finish."""


@final
class BeddelServer:
    """Own a background Uvicorn server and its lifecycle thread."""

    def __init__(self, server: _UvicornServer, thread: _ServerThread) -> None:
        self._server = server
        self._thread = thread

    @property
    def started(self) -> bool:
        """Whether the underlying Uvicorn server has completed startup."""
        return self._server.started

    def shutdown(self, timeout: float = 5.0) -> None:
        """Request graceful shutdown and wait up to ``timeout`` seconds.

        Args:
            timeout: Maximum number of seconds to wait for the server thread
                after requesting shutdown.
        """
        self._server.should_exit = True
        self.wait(timeout)

    def wait(self, timeout: float | None = None) -> None:
        """Wait for the background server thread to finish.

        Args:
            timeout: Maximum number of seconds to wait, or ``None`` to wait
                indefinitely.
        """
        self._thread.join(timeout=timeout)


def start_beddel_server(
    app: Callable[..., Awaitable[None]],
    *,
    host: str,
    port: int,
    log_level: str = "info",
) -> BeddelServer:
    """Start an ASGI application in a daemon-thread Uvicorn server.

    Uvicorn and ``threading`` are imported only when this function is called,
    keeping ``import beddel_serve_fastapi`` free of server startup side effects.

    Args:
        app: ASGI application to serve.
        host: Interface address on which Uvicorn should listen.
        port: TCP port on which Uvicorn should listen.
        log_level: Uvicorn logging level, defaulting to ``"info"``.

    Returns:
        A :class:`BeddelServer` handle for checking readiness, waiting, and
        graceful shutdown.
    """
    import threading

    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level=log_level)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return BeddelServer(server, thread)
