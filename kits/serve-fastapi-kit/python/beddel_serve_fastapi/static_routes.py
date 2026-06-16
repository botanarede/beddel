"""Static HTML routes — serves the standalone A2UI renderer at ``GET /``.

Registers a zero-dependency HTML renderer (``static/index.html``) that
renders A2UI ``surfaceUpdate`` components in the browser, plus a
``GET /favicon.ico`` handler that returns ``204 No Content`` to suppress
the browser's default favicon request error.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.responses import HTMLResponse, Response

_INDEX_HTML = Path(__file__).parent / "static" / "index.html"


def register_static_routes(app: Any) -> None:
    """Register the A2UI renderer (``GET /``) and ``GET /favicon.ico``.

    Args:
        app: The :class:`fastapi.FastAPI` application to register routes on.
    """

    @app.get("/", response_class=HTMLResponse)
    async def _index() -> HTMLResponse:
        return HTMLResponse(content=_INDEX_HTML.read_text(encoding="utf-8"))

    @app.get("/favicon.ico")
    async def _favicon() -> Response:
        return Response(status_code=204)

    # Agent Engine sidebar routes are now registered by the SDK serve tier
    # (beddel.serve.agent_engine) via _build_runtime_app() injection.
    # This placeholder is intentionally removed — see ADR-0013 and Story K3A.4.
