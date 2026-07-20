"""Kimi LLM provider adapter implementing ILLMProvider via OpenAI-compatible API."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

from openai import (
    APIStatusError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    RateLimitError,
)

from beddel.domain.errors import AdapterError
from beddel.domain.ports import ILLMProvider
from beddel_provider_kimi.errors import (
    ADAPT_KIMI_AUTH,
    ADAPT_KIMI_MODEL_UNAVAILABLE,
    ADAPT_KIMI_PARAM_REJECTED,
    ADAPT_KIMI_RATE_LIMIT,
)

logger = logging.getLogger(__name__)


class KimiLLMProvider(ILLMProvider):
    """LLM provider adapter for Moonshot AI's Kimi models.

    Implements the ILLMProvider port using the OpenAI-compatible Moonshot API.
    Supports K2.6, K2.7, and K3 model families with appropriate parameter
    validation and normalization per model constraints.
    """

    _BASE_URL = "https://api.moonshot.ai/v1"

    _K3_FIXED_PARAMS: dict[str, float | int] = {
        "temperature": 1.0,
        "top_p": 1.0,
        "n": 1,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    }

    _K3_VALID_TOOL_CHOICE = {"required", "none"}

    _K2_7_MODELS = ("kimi-k2.7",)

    def __init__(self, api_key: str | None = None) -> None:
        resolved_key = api_key or os.environ.get("MOONSHOT_API_KEY")
        if not resolved_key:
            raise AdapterError(
                code=ADAPT_KIMI_AUTH,
                message="MOONSHOT_API_KEY not set",
                details={"provider": "kimi"},
            )
        self._client = AsyncOpenAI(api_key=resolved_key, base_url=self._BASE_URL)

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

    def _handle_error(self, exc: Exception, model: str) -> AdapterError:
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
                code=ADAPT_KIMI_PARAM_REJECTED,
                message=f"Kimi API error for model '{model}': {exc}",
                details={"model": model},
            )
        return AdapterError(
            code=ADAPT_KIMI_AUTH,
            message=f"Kimi API error for model '{model}': {exc}",
            details={"model": model},
        )

    async def complete(
        self, model: str, messages: list[dict[str, Any]], **kwargs: Any
    ) -> dict[str, Any]:
        """Send a completion request to the Kimi API.

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
        api_kwargs: dict[str, Any] = {"model": model, "messages": messages, **params}

        try:
            response = await self._client.chat.completions.create(**api_kwargs)
        except Exception as exc:
            raise self._handle_error(exc, model) from exc

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
        """Stream completion tokens from the Kimi API.

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
        api_kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            **params,
        }

        try:
            stream = await self._client.chat.completions.create(**api_kwargs)
        except Exception as exc:
            raise self._handle_error(exc, model) from exc

        try:
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
        finally:
            await stream.close()
