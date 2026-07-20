"""Kimi LLM provider adapter implementing ILLMProvider via OpenAI-compatible API."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

from openai import (
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    RateLimitError,
)

from beddel.domain.errors import AdapterError
from beddel.domain.ports import ILLMProvider
from beddel_provider_kimi.caching import stable_prefix_messages
from beddel_provider_kimi.errors import (
    ADAPT_KIMI_AUTH,
    ADAPT_KIMI_MODEL_UNAVAILABLE,
    ADAPT_KIMI_PARAM_REJECTED,
    ADAPT_KIMI_RATE_LIMIT,
    ADAPT_PROVIDER_ERROR,
    ADAPT_TIMEOUT,
)

logger = logging.getLogger(__name__)

# Retry configuration
_MAX_RETRIES = 3
_BASE_BACKOFF_S = 2.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}


class KimiLLMProvider(ILLMProvider):
    """LLM provider adapter for Moonshot AI's Kimi models.

    Implements the ILLMProvider port using the OpenAI-compatible Moonshot API.
    Supports K2.6, K2.7, and K3 model families with appropriate parameter
    validation and normalization per model constraints.

    Args:
        api_key: Moonshot API key. Falls back to MOONSHOT_API_KEY env var.
        base_url: API base URL. Defaults to "https://api.moonshot.ai/v1".
        timeout: Request timeout in seconds. Defaults to 120.
    """

    _DEFAULT_BASE_URL = "https://api.moonshot.ai/v1"
    _DEFAULT_TIMEOUT = 120

    _K3_FIXED_PARAMS: dict[str, float | int] = {
        "temperature": 1.0,
        "top_p": 1.0,
        "n": 1,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    }

    _K3_VALID_TOOL_CHOICE = {"required", "none"}

    _K2_7_MODELS = ("kimi-k2.7",)

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        resolved_key = api_key or os.environ.get("MOONSHOT_API_KEY")
        if not resolved_key:
            raise AdapterError(
                code=ADAPT_KIMI_AUTH,
                message="MOONSHOT_API_KEY not set",
                details={"provider": "kimi"},
            )
        self._base_url = base_url or self._DEFAULT_BASE_URL
        self._timeout = timeout if timeout is not None else self._DEFAULT_TIMEOUT
        self._client = AsyncOpenAI(
            api_key=resolved_key,
            base_url=self._base_url,
            timeout=self._timeout,
            max_retries=0,  # We handle retries ourselves
        )

    @staticmethod
    def _is_k3(model: str) -> bool:
        return model == "kimi-k3"

    @staticmethod
    def _is_k2_7(model: str) -> bool:
        return model.startswith("kimi-k2.7")

    @staticmethod
    def _is_k2_6(model: str) -> bool:
        return model.startswith("kimi-k2.6")

    @staticmethod
    def _validate_messages(messages: list[dict[str, Any]]) -> None:
        for message in messages:
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if part.get("type") != "image_url":
                    continue
                image_url = part.get("image_url")
                if not isinstance(image_url, dict):
                    continue
                url = image_url.get("url", "")
                if url.startswith("http://") or url.startswith("https://"):
                    raise AdapterError(
                        code=ADAPT_KIMI_PARAM_REJECTED,
                        message="Kimi vision requires base64 content parts only, URL references not supported",
                        details={"url_prefix": url[:50]},
                    )

    def _normalize_params(self, model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        # Handle max_tokens alias
        if "max_tokens" in kwargs and "max_completion_tokens" not in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
        elif "max_tokens" in kwargs and "max_completion_tokens" in kwargs:
            if kwargs["max_tokens"] != kwargs["max_completion_tokens"]:
                raise AdapterError(
                    code=ADAPT_KIMI_PARAM_REJECTED,
                    message=(
                        f"max_tokens ({kwargs['max_tokens']}) conflicts with "
                        f"max_completion_tokens ({kwargs['max_completion_tokens']})"
                    ),
                )
            del kwargs["max_tokens"]

        # K3 fixed params
        if self._is_k3(model):
            for param, fixed_value in self._K3_FIXED_PARAMS.items():
                if param in kwargs:
                    if kwargs[param] == fixed_value:
                        logger.debug(
                            "Stripped K3 fixed param '%s=%s' (matches default)",
                            param,
                            kwargs[param],
                        )
                        del kwargs[param]
                    else:
                        raise AdapterError(
                            code=ADAPT_KIMI_PARAM_REJECTED,
                            message=(
                                f"K3 model has fixed {param}={fixed_value}, "
                                f"cannot override with {param}={kwargs[param]}"
                            ),
                        )

        # K3 tool_choice validation
        if self._is_k3(model) and "tool_choice" in kwargs:
            if kwargs["tool_choice"] not in self._K3_VALID_TOOL_CHOICE:
                raise AdapterError(
                    code=ADAPT_KIMI_PARAM_REJECTED,
                    message=(
                        f"K3 tool_choice must be 'required' or 'none', "
                        f"got '{kwargs['tool_choice']}'"
                    ),
                )

        # K2.7 thinking disable rejection
        if self._is_k2_7(model) and "extra_body" in kwargs:
            extra_body = kwargs["extra_body"]
            if isinstance(extra_body, dict):
                thinking = extra_body.get("thinking", {})
                if isinstance(thinking, dict) and thinking.get("type") == "disabled":
                    raise AdapterError(
                        code=ADAPT_KIMI_PARAM_REJECTED,
                        message="K2.7 thinking is always on, cannot disable",
                    )

        return kwargs

    @staticmethod
    def _get_retry_after(exc: APIStatusError) -> float | None:
        """Extract Retry-After header value from an API error response."""
        response = getattr(exc, "response", None)
        if response is None:
            return None
        headers = getattr(response, "headers", None)
        if headers is None:
            return None
        retry_after = headers.get("retry-after")
        if retry_after is None:
            return None
        try:
            return float(retry_after)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Check if an exception is retryable (429/500/502/503)."""
        if isinstance(exc, APIStatusError):
            return exc.status_code in _RETRYABLE_STATUS_CODES
        if isinstance(exc, RateLimitError):
            return True
        return False

    def _handle_error(self, exc: Exception, model: str) -> AdapterError:
        if isinstance(exc, APITimeoutError):
            return AdapterError(
                code=ADAPT_TIMEOUT,
                message=f"Kimi request timed out for model '{model}'",
                details={"model": model, "timeout": self._timeout},
            )
        if isinstance(exc, AuthenticationError):
            return AdapterError(
                code=ADAPT_KIMI_AUTH,
                message=f"Kimi auth failure for model '{model}': {exc}",
                details={"model": model},
            )
        if isinstance(exc, RateLimitError):
            return AdapterError(
                code=ADAPT_KIMI_RATE_LIMIT,
                message=f"Kimi rate limit for model '{model}': {exc}",
                details={"model": model},
            )
        if isinstance(exc, NotFoundError):
            return AdapterError(
                code=ADAPT_KIMI_MODEL_UNAVAILABLE,
                message=f"Kimi model '{model}' not found: {exc}",
                details={"model": model},
            )
        if isinstance(exc, BadRequestError):
            return AdapterError(
                code=ADAPT_KIMI_PARAM_REJECTED,
                message=f"Kimi bad request for model '{model}': {exc}",
                details={"model": model},
            )
        if isinstance(exc, APIStatusError):
            status = exc.status_code
            if status in (401, 403):
                return AdapterError(
                    code=ADAPT_KIMI_AUTH,
                    message=f"Kimi auth failure for model '{model}': {exc}",
                    details={"model": model},
                )
            if status == 429:
                return AdapterError(
                    code=ADAPT_KIMI_RATE_LIMIT,
                    message=f"Kimi rate limit for model '{model}': {exc}",
                    details={"model": model},
                )
            if status == 404:
                return AdapterError(
                    code=ADAPT_KIMI_MODEL_UNAVAILABLE,
                    message=f"Kimi model '{model}' not found: {exc}",
                    details={"model": model},
                )
            return AdapterError(
                code=ADAPT_PROVIDER_ERROR,
                message=f"Kimi API error for model '{model}': {exc}",
                details={"model": model, "status_code": status},
            )
        return AdapterError(
            code=ADAPT_PROVIDER_ERROR,
            message=f"Kimi unexpected error for model '{model}': {exc}",
            details={"model": model},
        )

    async def complete(
        self, model: str, messages: list[dict[str, Any]], **kwargs: Any
    ) -> dict[str, Any]:
        """Send a completion request to the Kimi API with retry.

        Args:
            model: Model identifier (e.g. "kimi-k3", "kimi-k2.7", "kimi-k2.6-math").
            messages: List of chat messages in OpenAI format.
            **kwargs: Additional parameters forwarded to the API.

        Returns:
            Dict with keys: content, reasoning, usage, model, finish_reason, tool_calls.

        Raises:
            AdapterError: On authentication, rate limit, model, or parameter errors.
        """
        self._validate_messages(messages)
        params = dict(kwargs)
        params = self._normalize_params(model, params)

        # Apply context caching — separate system prefix from dynamic content
        cached_messages = stable_prefix_messages(messages)

        api_kwargs: dict[str, Any] = {
            "model": model,
            "messages": cached_messages,
            **params,
        }

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._client.chat.completions.create(**api_kwargs)
                break
            except Exception as exc:
                if attempt < _MAX_RETRIES and self._is_retryable(exc):
                    last_exc = exc
                    backoff = _BASE_BACKOFF_S * (2**attempt)
                    # Honor Retry-After header if present
                    if isinstance(exc, APIStatusError):
                        retry_after = self._get_retry_after(exc)
                        if retry_after is not None:
                            backoff = max(backoff, retry_after)
                    logger.warning(
                        "Kimi API retryable error (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        _MAX_RETRIES,
                        backoff,
                        exc,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise self._handle_error(exc, model) from exc
        else:
            # All retries exhausted
            raise self._handle_error(last_exc, model) from last_exc  # type: ignore[arg-type]

        choice = response.choices[0]
        content = choice.message.content or ""

        # Extract reasoning content (extended thinking)
        reasoning: str | None = getattr(choice.message, "reasoning_content", None)
        if reasoning is None:
            model_extra = getattr(choice.message, "model_extra", None) or {}
            reasoning = model_extra.get("reasoning_content")

        tool_calls = choice.message.tool_calls

        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
        else:
            usage = {"prompt_tokens": 0, "completion_tokens": 0}

        finish_reason = choice.finish_reason or ""

        return {
            "content": content,
            "reasoning": reasoning,
            "usage": usage,
            "model": model,
            "finish_reason": finish_reason,
            "tool_calls": tool_calls,
        }

    async def stream(
        self, model: str, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream completion tokens from the Kimi API with retry.

        Yields only content tokens (not reasoning_content) per the port contract.

        Args:
            model: Model identifier (e.g. "kimi-k3", "kimi-k2.7", "kimi-k2.6-math").
            messages: List of chat messages in OpenAI format.
            **kwargs: Additional parameters forwarded to the API.

        Yields:
            Content token strings as they arrive.

        Raises:
            AdapterError: On authentication, rate limit, model, or parameter errors.
        """
        self._validate_messages(messages)
        params = dict(kwargs)
        params = self._normalize_params(model, params)

        # Apply context caching — separate system prefix from dynamic content
        cached_messages = stable_prefix_messages(messages)

        api_kwargs: dict[str, Any] = {
            "model": model,
            "messages": cached_messages,
            "stream": True,
            **params,
        }

        last_exc: Exception | None = None
        stream = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                stream = await self._client.chat.completions.create(**api_kwargs)
                break
            except Exception as exc:
                if attempt < _MAX_RETRIES and self._is_retryable(exc):
                    last_exc = exc
                    backoff = _BASE_BACKOFF_S * (2**attempt)
                    if isinstance(exc, APIStatusError):
                        retry_after = self._get_retry_after(exc)
                        if retry_after is not None:
                            backoff = max(backoff, retry_after)
                    logger.warning(
                        "Kimi stream retryable error (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        _MAX_RETRIES,
                        backoff,
                        exc,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise self._handle_error(exc, model) from exc
        else:
            raise self._handle_error(last_exc, model) from last_exc  # type: ignore[arg-type]

        try:
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
        finally:
            await stream.close()
