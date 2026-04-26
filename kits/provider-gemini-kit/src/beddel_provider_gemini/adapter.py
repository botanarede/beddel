"""Gemini direct adapter — Google Gemini LLM access via the ``ILLMProvider`` port.

This adapter bridges the Beddel domain core to the Google Gemini API using
the ``google-genai`` SDK, enabling direct access to Gemini models without
the LiteLLM intermediary.

Authentication is resolved from the ``GOOGLE_API_KEY`` environment variable
first; if absent, the client falls back to Application Default Credentials
(ADC).

.. _google-genai: https://pypi.org/project/google-genai/
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

try:
    from google import genai
    from google.genai import types as genai_types

    HAS_GENAI = True
except ImportError:  # pragma: no cover
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]
    HAS_GENAI = False

from beddel.domain.errors import AdapterError
from beddel.domain.ports import ILLMProvider
from beddel.error_codes import (
    ADAPT_GEMINI_AUTH,
    ADAPT_GEMINI_MODEL_UNAVAILABLE,
    ADAPT_GEMINI_RATE_LIMIT,
    ADAPT_GEMINI_SAFETY_BLOCKED,
)

__all__ = ["GeminiLLMProvider"]

# Role mapping: Beddel → Gemini
_ROLE_MAP: dict[str, str] = {
    "user": "user",
    "assistant": "model",
}


class GeminiLLMProvider(ILLMProvider):
    """Direct Gemini LLM provider powered by the google-genai SDK.

    Implements :class:`~beddel.domain.ports.ILLMProvider` to provide both
    single-turn completion and streaming access to Google Gemini models.

    Authentication resolution order:

    1. ``GOOGLE_API_KEY`` environment variable — passed as ``api_key``.
    2. Application Default Credentials (ADC) — automatic fallback.

    Args:
        api_key: Optional explicit API key. When ``None``, the constructor
            checks ``GOOGLE_API_KEY`` env var, then falls back to ADC.

    Example::

        provider = GeminiLLMProvider()
        result = await provider.complete(
            model="gemini-3.1-pro",
            messages=[{"role": "user", "content": "Hello!"}],
        )
        print(result["content"])
    """

    def __init__(self, api_key: str | None = None) -> None:
        if genai is None:
            msg = (
                "google-genai is not installed. "
                "Install it with: pip install 'google-genai>=1.0.0'"
            )
            raise ImportError(msg)

        resolved_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if resolved_key:
            self._client = genai.Client(api_key=resolved_key)
        else:
            # Vertex AI / ADC fallback
            project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            self._client = genai.Client(
                vertexai=True,
                project=project,
                location=location,
            )

    # ------------------------------------------------------------------
    # Message conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_messages(
        messages: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Convert Beddel messages to Gemini format.

        System messages are extracted and concatenated into a single
        ``system_instruction`` string.  User and assistant messages are
        converted to Gemini ``Content``-compatible dicts.

        Args:
            messages: Beddel-format message list with ``"role"`` and
                ``"content"`` keys.

        Returns:
            A tuple of ``(contents, system_instruction)`` where
            ``contents`` is a list of role/parts dicts for the Gemini API
            and ``system_instruction`` is the concatenated system text
            (or ``None`` if no system messages were present).
        """
        system_parts: list[str] = []
        contents: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_parts.append(content)
            else:
                gemini_role = _ROLE_MAP.get(role, "user")
                contents.append({"role": gemini_role, "parts": [{"text": content}]})

        system_instruction = "\n".join(system_parts) if system_parts else None
        return contents, system_instruction

    # ------------------------------------------------------------------
    # Config builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_config(
        system_instruction: str | None,
        **kwargs: Any,
    ) -> Any:
        """Build a ``GenerateContentConfig`` from kwargs.

        Extracts recognised Gemini config keys from kwargs and builds
        a typed config object.  Unrecognised keys are silently ignored.

        Args:
            system_instruction: Optional system instruction text.
            **kwargs: Caller-supplied generation parameters.

        Returns:
            A ``genai.types.GenerateContentConfig`` instance.
        """
        config_kwargs: dict[str, Any] = {}
        if system_instruction is not None:
            config_kwargs["system_instruction"] = system_instruction

        # Map recognised kwargs
        for key in ("temperature", "max_output_tokens", "top_p", "top_k", "safety_settings"):
            if key in kwargs:
                config_kwargs[key] = kwargs[key]

        return genai_types.GenerateContentConfig(**config_kwargs)

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_error(exc: Exception, model: str) -> AdapterError:
        """Map a google-genai exception to an ``AdapterError``.

        Args:
            exc: The caught exception from the Gemini API call.
            model: The model identifier used in the request.

        Returns:
            An ``AdapterError`` with the appropriate Beddel error code.
        """
        exc_type = type(exc).__name__
        exc_msg = str(exc).lower()

        # Safety filter blocked
        if "blocked" in exc_msg or "safety" in exc_msg:
            return AdapterError(
                code=ADAPT_GEMINI_SAFETY_BLOCKED,
                message=f"Gemini safety filter blocked response for model '{model}': {exc}",
                details={"model": model, "provider_error": str(exc)},
            )

        # Rate limit
        if "429" in str(exc) or "rate" in exc_msg or "resource_exhausted" in exc_msg:
            return AdapterError(
                code=ADAPT_GEMINI_RATE_LIMIT,
                message=f"Gemini rate limit exceeded for model '{model}': {exc}",
                details={"model": model, "provider_error": str(exc)},
            )

        # Model not found / unavailable
        if "404" in str(exc) or "not found" in exc_msg or "not_found" in exc_msg:
            return AdapterError(
                code=ADAPT_GEMINI_MODEL_UNAVAILABLE,
                message=f"Gemini model '{model}' not available: {exc}",
                details={"model": model, "provider_error": str(exc)},
            )

        # Auth errors
        if (
            "401" in str(exc)
            or "403" in str(exc)
            or "auth" in exc_msg
            or "permission" in exc_msg
            or "unauthenticated" in exc_msg
            or exc_type in ("Unauthorized", "PermissionDenied")
        ):
            return AdapterError(
                code=ADAPT_GEMINI_AUTH,
                message=f"Gemini authentication failure for model '{model}': {exc}",
                details={"model": model, "provider_error": str(exc)},
            )

        # Default: auth error as catch-all for unknown API errors
        return AdapterError(
            code=ADAPT_GEMINI_AUTH,
            message=f"Gemini API error for model '{model}': {exc}",
            details={"model": model, "provider_error": str(exc)},
        )

    # ------------------------------------------------------------------
    # ILLMProvider implementation
    # ------------------------------------------------------------------

    async def complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a completion request to the Gemini API.

        Args:
            model: Gemini model identifier (e.g. ``"gemini-3.1-pro"``).
            messages: Chat-style message list with ``"role"`` and
                ``"content"`` keys.
            **kwargs: Forwarded to Gemini config (e.g.
                ``temperature``, ``max_output_tokens``, ``safety_settings``).

        Returns:
            A dict with keys ``"content"``, ``"model"``, ``"usage"``, and
            ``"finish_reason"``.

        Raises:
            AdapterError: On authentication, rate limit, model, or safety
                failures (codes ``BEDDEL-ADAPT-050`` through ``053``).
        """
        contents, system_instruction = self._convert_messages(messages)
        config = self._build_config(system_instruction, **kwargs)

        try:
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            raise self._handle_error(exc, model) from exc

        # Extract response data
        content = response.text or ""
        usage_meta = response.usage_metadata
        finish_reason = ""
        if response.candidates:
            raw_reason = response.candidates[0].finish_reason
            finish_reason = str(raw_reason) if raw_reason else ""

        return {
            "content": content,
            "model": model,
            "usage": {
                "prompt_tokens": getattr(usage_meta, "prompt_token_count", 0) or 0,
                "completion_tokens": (
                    getattr(usage_meta, "candidates_token_count", 0) or 0
                ),
                "total_tokens": getattr(usage_meta, "total_token_count", 0) or 0,
            },
            "finish_reason": finish_reason,
        }

    async def stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream completion tokens from the Gemini API.

        Args:
            model: Gemini model identifier (e.g. ``"gemini-3-flash"``).
            messages: Chat-style message list with ``"role"`` and
                ``"content"`` keys.
            **kwargs: Forwarded to Gemini config (e.g.
                ``temperature``, ``max_output_tokens``, ``safety_settings``).

        Yields:
            String chunks of the model's response as they arrive.

        Raises:
            AdapterError: On authentication, rate limit, model, or safety
                failures (codes ``BEDDEL-ADAPT-050`` through ``053``).
        """
        contents, system_instruction = self._convert_messages(messages)
        config = self._build_config(system_instruction, **kwargs)

        try:
            response_stream = self._client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            raise self._handle_error(exc, model) from exc

        try:
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            raise self._handle_error(exc, model) from exc
