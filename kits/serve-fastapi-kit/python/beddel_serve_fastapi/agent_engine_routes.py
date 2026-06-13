"""Agent Engine API routes for the sidebar chat panel.

Provides endpoints to list deployed agents and chat with them via
Vertex AI Agent Engine stream_query. All external dependencies
(vertexai, google-cloud-aiplatform, beddel_deploy_agent_engine)
are lazy-imported — the module gracefully degrades if they are absent.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)

# --- Lazy dependency loading ---
_AVAILABLE = False
_check_adc = None
_vertexai = None
_agent_engines = None

try:
    from beddel_deploy_agent_engine.adc import check_adc as _check_adc  # type: ignore[import-not-found]
    import vertexai as _vertexai  # type: ignore[import-not-found]
    from vertexai import agent_engines as _agent_engines  # type: ignore[import-not-found]

    _AVAILABLE = True
except ImportError:
    pass


def _check_dependencies() -> JSONResponse | None:
    """Return a 503 response if dependencies are missing or ADC is not configured."""
    if not _AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={
                "error": "deploy-agent-engine-kit not installed. Run: beddel init"
            },
        )
    assert _check_adc is not None  # type narrowing
    adc_status = _check_adc()
    if not adc_status["configured"]:
        return JSONResponse(
            status_code=503,
            content={"error": str(adc_status["error"])},
        )
    return None


def register_agent_engine_routes(app: Any) -> None:
    """Register Agent Engine sidebar API endpoints on the FastAPI app."""

    @app.get("/api/agent-engine/agents")
    async def _list_agents() -> JSONResponse:
        error_response = _check_dependencies()
        if error_response is not None:
            return error_response
        assert _check_adc is not None
        assert _vertexai is not None
        assert _agent_engines is not None

        try:
            adc_status = _check_adc()
            project_id = adc_status.get("project_id", "your-project-id")
            _vertexai.init(project=project_id, location="us-central1")

            agents_list = _agent_engines.list()
            result = []
            for agent in agents_list:
                result.append(
                    {
                        "resource_name": agent.resource_name,
                        "display_name": agent.display_name
                        or agent.resource_name.split("/")[-1],
                    }
                )
            return JSONResponse(content=result)
        except Exception as exc:
            logger.exception("Failed to list Agent Engine agents")
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to list agents: {exc}"},
            )

    @app.post("/api/agent-engine/chat")
    async def _chat(request: Request) -> EventSourceResponse:
        error_response = _check_dependencies()
        if error_response is not None:
            return error_response  # type: ignore[return-value]
        assert _check_adc is not None
        assert _vertexai is not None
        assert _agent_engines is not None

        body = await request.json()
        resource_name: str = body["resource_name"]
        message: str = body["message"]
        session_id: str | None = body.get("session_id")

        try:
            adc_status = _check_adc()
            project_id = adc_status.get("project_id", "your-project-id")
            _vertexai.init(project=project_id, location="us-central1")

            remote_app = _agent_engines.get(resource_name)
            user_id = "sidebar-user"

            if not session_id:
                session = remote_app.create_session(user_id=user_id)
                session_id = session["id"]

        except Exception as exc:
            logger.exception("Failed to initialize chat session")
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to initialize chat: {exc}"},
            )  # type: ignore[return-value]

        async def _event_generator() -> AsyncGenerator[dict[str, str], None]:
            try:
                async for chunk in _stream_query_async(
                    remote_app,
                    user_id,
                    session_id,
                    message,  # type: ignore[arg-type]
                ):
                    yield {
                        "event": "text_chunk",
                        "data": json.dumps({"text": chunk}),
                    }
            except Exception as exc:
                logger.exception("Error during stream_query")
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(exc)}),
                }
            yield {
                "event": "done",
                "data": json.dumps({"session_id": session_id}),
            }

        return EventSourceResponse(_event_generator())


async def _stream_query_async(
    remote_app: Any,
    user_id: str,
    session_id: str,
    message: str,
) -> AsyncGenerator[str, None]:
    """Async generator that bridges sync stream_query() via threadpool + asyncio.Queue."""
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def _run_sync() -> None:
        try:
            for event in remote_app.stream_query(
                user_id=user_id,
                session_id=session_id,
                message=message,
            ):
                if hasattr(event, "content") and event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            queue.put_nowait(part.text)
        except Exception:
            queue.put_nowait(None)
            raise
        queue.put_nowait(None)  # sentinel

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_sync)
    # Small delay to let the executor start
    await asyncio.sleep(0.01)

    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        yield chunk
