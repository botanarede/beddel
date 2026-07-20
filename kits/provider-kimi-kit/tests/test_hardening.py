"""Tests for provider hardening: base_url, timeout, retry, new error codes."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIStatusError, APITimeoutError, RateLimitError

from beddel.domain.errors import AdapterError
from beddel_provider_kimi.adapter import KimiLLMProvider
from beddel_provider_kimi.errors import (
    ADAPT_KIMI_PARAM_REJECTED,
    ADAPT_KIMI_RATE_LIMIT,
    ADAPT_PROVIDER_ERROR,
    ADAPT_TIMEOUT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(content: str = "Hello") -> MagicMock:
    """Build a minimal mock ChatCompletion response."""
    message = MagicMock()
    message.content = content
    message.reasoning_content = None
    message.model_extra = None
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_api_status_error(
    status_code: int, headers: dict | None = None
) -> APIStatusError:
    """Create a real APIStatusError with given status code and optional headers."""
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    return APIStatusError(message=f"Error {status_code}", response=response, body=None)


class MockAsyncStream:
    """Async iterator that simulates openai streaming response."""

    def __init__(self, chunks: list) -> None:
        self._chunks = chunks
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk

    async def close(self):
        pass


def _make_chunk(content: str | None = None) -> MagicMock:
    """Build a mock streaming chunk."""
    delta = MagicMock()
    delta.content = content

    choice = MagicMock()
    choice.delta = delta

    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_openai_class():
    """Patch AsyncOpenAI class and return (MockClass, client_instance)."""
    with patch("beddel_provider_kimi.adapter.AsyncOpenAI") as MockClass:
        client_instance = MagicMock()
        client_instance.chat.completions.create = AsyncMock()
        MockClass.return_value = client_instance
        yield MockClass, client_instance


# ---------------------------------------------------------------------------
# Tests: base_url and timeout params
# ---------------------------------------------------------------------------


async def test_custom_base_url_passed_to_client(mock_openai_class):
    """Custom base_url is forwarded to AsyncOpenAI constructor."""
    MockClass, _ = mock_openai_class
    KimiLLMProvider(api_key="test", base_url="https://custom.ai/v1")
    MockClass.assert_called_once_with(
        api_key="test",
        base_url="https://custom.ai/v1",
        timeout=120,
        max_retries=0,
    )


async def test_default_base_url(mock_openai_class):
    """Default base_url is api.moonshot.ai/v1."""
    MockClass, _ = mock_openai_class
    KimiLLMProvider(api_key="test")
    MockClass.assert_called_once_with(
        api_key="test",
        base_url="https://api.moonshot.ai/v1",
        timeout=120,
        max_retries=0,
    )


async def test_custom_timeout_passed_to_client(mock_openai_class):
    """Custom timeout is forwarded to AsyncOpenAI constructor."""
    MockClass, _ = mock_openai_class
    KimiLLMProvider(api_key="test", timeout=60)
    MockClass.assert_called_once_with(
        api_key="test",
        base_url="https://api.moonshot.ai/v1",
        timeout=60,
        max_retries=0,
    )


# ---------------------------------------------------------------------------
# Tests: Retry on retryable errors
# ---------------------------------------------------------------------------


async def test_retry_on_429_succeeds(mock_openai_class, monkeypatch):
    """429 error triggers retry; succeeds on second attempt."""
    _, client = mock_openai_class
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    rate_limit_exc = RateLimitError(
        message="Rate limit",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )
    client.chat.completions.create.side_effect = [
        rate_limit_exc,
        _make_response("Success after retry"),
    ]

    provider = KimiLLMProvider(api_key="test")
    result = await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    assert result["content"] == "Success after retry"
    assert client.chat.completions.create.call_count == 2


async def test_retry_on_500(mock_openai_class, monkeypatch):
    """500 error triggers retry."""
    _, client = mock_openai_class
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    err_500 = _make_api_status_error(500)
    client.chat.completions.create.side_effect = [
        err_500,
        _make_response("OK"),
    ]

    provider = KimiLLMProvider(api_key="test")
    result = await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    assert result["content"] == "OK"
    assert client.chat.completions.create.call_count == 2


async def test_retry_on_502(mock_openai_class, monkeypatch):
    """502 error triggers retry."""
    _, client = mock_openai_class
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    err_502 = _make_api_status_error(502)
    client.chat.completions.create.side_effect = [
        err_502,
        _make_response("OK"),
    ]

    provider = KimiLLMProvider(api_key="test")
    result = await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    assert result["content"] == "OK"


async def test_retry_on_503(mock_openai_class, monkeypatch):
    """503 error triggers retry."""
    _, client = mock_openai_class
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    err_503 = _make_api_status_error(503)
    client.chat.completions.create.side_effect = [
        err_503,
        _make_response("OK"),
    ]

    provider = KimiLLMProvider(api_key="test")
    result = await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    assert result["content"] == "OK"


async def test_retry_after_header_honored(mock_openai_class, monkeypatch):
    """Retry-After header value is used when larger than calculated backoff."""
    _, client = mock_openai_class
    sleep_mock = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep_mock)

    # Create error with Retry-After: 10 (larger than first backoff of 2.0s)
    err = _make_api_status_error(429, headers={"retry-after": "10"})
    client.chat.completions.create.side_effect = [
        err,
        _make_response("OK"),
    ]

    provider = KimiLLMProvider(api_key="test")
    await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    # First attempt (attempt=0): backoff = max(2.0 * 2^0, 10.0) = max(2.0, 10.0) = 10.0
    sleep_mock.assert_called_once_with(10.0)


async def test_retry_exhausted_raises_rate_limit(mock_openai_class, monkeypatch):
    """All retries exhausted on 429 raises ADAPT_KIMI_RATE_LIMIT."""
    _, client = mock_openai_class
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    rate_limit_exc = RateLimitError(
        message="Rate limit",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )
    # Fail all 4 attempts (1 initial + 3 retries)
    client.chat.completions.create.side_effect = [
        rate_limit_exc,
        rate_limit_exc,
        rate_limit_exc,
        rate_limit_exc,
    ]

    provider = KimiLLMProvider(api_key="test")
    with pytest.raises(AdapterError) as exc_info:
        await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    assert exc_info.value.code == ADAPT_KIMI_RATE_LIMIT
    assert client.chat.completions.create.call_count == 4


# ---------------------------------------------------------------------------
# Tests: ADAPT_TIMEOUT error code
# ---------------------------------------------------------------------------


async def test_timeout_error_maps_to_adapt_timeout(mock_openai_class):
    """APITimeoutError maps to ADAPT_TIMEOUT (BEDDEL-ADAPT-064)."""
    _, client = mock_openai_class

    timeout_exc = APITimeoutError(request=MagicMock())
    client.chat.completions.create.side_effect = timeout_exc

    provider = KimiLLMProvider(api_key="test")
    with pytest.raises(AdapterError) as exc_info:
        await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    assert exc_info.value.code == ADAPT_TIMEOUT


# ---------------------------------------------------------------------------
# Tests: ADAPT_PROVIDER_ERROR (catch-all)
# ---------------------------------------------------------------------------


async def test_unexpected_error_maps_to_provider_error(mock_openai_class):
    """Unexpected non-API exception maps to ADAPT_PROVIDER_ERROR."""
    _, client = mock_openai_class

    client.chat.completions.create.side_effect = RuntimeError("Something unexpected")

    provider = KimiLLMProvider(api_key="test")
    with pytest.raises(AdapterError) as exc_info:
        await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    assert exc_info.value.code == ADAPT_PROVIDER_ERROR


async def test_unknown_status_code_maps_to_provider_error(mock_openai_class):
    """APIStatusError with non-retryable/non-standard status maps to ADAPT_PROVIDER_ERROR."""
    _, client = mock_openai_class

    err = _make_api_status_error(418)  # I'm a teapot — not retryable
    client.chat.completions.create.side_effect = err

    provider = KimiLLMProvider(api_key="test")
    with pytest.raises(AdapterError) as exc_info:
        await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    assert exc_info.value.code == ADAPT_PROVIDER_ERROR


# ---------------------------------------------------------------------------
# Tests: K3 fixed params (top_p, n, frequency_penalty, presence_penalty)
# ---------------------------------------------------------------------------


async def test_k3_top_p_stripped(mock_openai_class):
    """K3: top_p=1.0 (fixed default) is stripped."""
    _, client = mock_openai_class
    client.chat.completions.create.return_value = _make_response()

    provider = KimiLLMProvider(api_key="test")
    await provider.complete("kimi-k3", [{"role": "user", "content": "Hi"}], top_p=1.0)

    call_kwargs = client.chat.completions.create.call_args[1]
    assert "top_p" not in call_kwargs


async def test_k3_top_p_rejected(mock_openai_class):
    """K3: top_p != 1.0 raises ADAPT_KIMI_PARAM_REJECTED."""
    _, client = mock_openai_class

    provider = KimiLLMProvider(api_key="test")
    with pytest.raises(AdapterError) as exc_info:
        await provider.complete(
            "kimi-k3", [{"role": "user", "content": "Hi"}], top_p=0.9
        )

    assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED


async def test_k3_n_stripped(mock_openai_class):
    """K3: n=1 (fixed default) is stripped."""
    _, client = mock_openai_class
    client.chat.completions.create.return_value = _make_response()

    provider = KimiLLMProvider(api_key="test")
    await provider.complete("kimi-k3", [{"role": "user", "content": "Hi"}], n=1)

    call_kwargs = client.chat.completions.create.call_args[1]
    assert "n" not in call_kwargs


async def test_k3_n_rejected(mock_openai_class):
    """K3: n != 1 raises ADAPT_KIMI_PARAM_REJECTED."""
    _, client = mock_openai_class

    provider = KimiLLMProvider(api_key="test")
    with pytest.raises(AdapterError) as exc_info:
        await provider.complete("kimi-k3", [{"role": "user", "content": "Hi"}], n=3)

    assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED


async def test_k3_frequency_penalty_stripped(mock_openai_class):
    """K3: frequency_penalty=0.0 (fixed default) is stripped."""
    _, client = mock_openai_class
    client.chat.completions.create.return_value = _make_response()

    provider = KimiLLMProvider(api_key="test")
    await provider.complete(
        "kimi-k3", [{"role": "user", "content": "Hi"}], frequency_penalty=0.0
    )

    call_kwargs = client.chat.completions.create.call_args[1]
    assert "frequency_penalty" not in call_kwargs


async def test_k3_frequency_penalty_rejected(mock_openai_class):
    """K3: frequency_penalty != 0.0 raises ADAPT_KIMI_PARAM_REJECTED."""
    _, client = mock_openai_class

    provider = KimiLLMProvider(api_key="test")
    with pytest.raises(AdapterError) as exc_info:
        await provider.complete(
            "kimi-k3", [{"role": "user", "content": "Hi"}], frequency_penalty=0.5
        )

    assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED


async def test_k3_presence_penalty_stripped(mock_openai_class):
    """K3: presence_penalty=0.0 (fixed default) is stripped."""
    _, client = mock_openai_class
    client.chat.completions.create.return_value = _make_response()

    provider = KimiLLMProvider(api_key="test")
    await provider.complete(
        "kimi-k3", [{"role": "user", "content": "Hi"}], presence_penalty=0.0
    )

    call_kwargs = client.chat.completions.create.call_args[1]
    assert "presence_penalty" not in call_kwargs


async def test_k3_presence_penalty_rejected(mock_openai_class):
    """K3: presence_penalty != 0.0 raises ADAPT_KIMI_PARAM_REJECTED."""
    _, client = mock_openai_class

    provider = KimiLLMProvider(api_key="test")
    with pytest.raises(AdapterError) as exc_info:
        await provider.complete(
            "kimi-k3", [{"role": "user", "content": "Hi"}], presence_penalty=0.5
        )

    assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED


# ---------------------------------------------------------------------------
# Tests: Stream error handling
# ---------------------------------------------------------------------------


async def test_stream_timeout_error(mock_openai_class):
    """Stream: APITimeoutError maps to ADAPT_TIMEOUT."""
    _, client = mock_openai_class

    timeout_exc = APITimeoutError(request=MagicMock())
    client.chat.completions.create.side_effect = timeout_exc

    provider = KimiLLMProvider(api_key="test")
    with pytest.raises(AdapterError) as exc_info:
        async for _ in provider.stream(
            "kimi-k2.7", [{"role": "user", "content": "Hi"}]
        ):
            pass

    assert exc_info.value.code == ADAPT_TIMEOUT


async def test_stream_retry_on_429(mock_openai_class, monkeypatch):
    """Stream: 429 triggers retry; succeeds on second attempt."""
    _, client = mock_openai_class
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    rate_limit_exc = RateLimitError(
        message="Rate limit",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )
    chunks = [_make_chunk("Hello"), _make_chunk(" world")]
    client.chat.completions.create.side_effect = [
        rate_limit_exc,
        MockAsyncStream(chunks),
    ]

    provider = KimiLLMProvider(api_key="test")
    collected = []
    async for token in provider.stream(
        "kimi-k2.7", [{"role": "user", "content": "Hi"}]
    ):
        collected.append(token)

    assert collected == ["Hello", " world"]
    assert client.chat.completions.create.call_count == 2


# ---------------------------------------------------------------------------
# Tests: Context caching integration
# ---------------------------------------------------------------------------


async def test_caching_system_prefix_annotated(mock_openai_class):
    """Last system message in prefix gets cache_control annotation."""
    _, client = mock_openai_class
    client.chat.completions.create.return_value = _make_response()

    provider = KimiLLMProvider(api_key="test")
    messages = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hi"},
    ]
    await provider.complete("kimi-k2.7", messages)

    call_kwargs = client.chat.completions.create.call_args[1]
    sent_messages = call_kwargs["messages"]
    # Last (and only) system message should have cache_control
    assert sent_messages[0]["cache_control"] == {"type": "ephemeral"}
    # User message unchanged
    assert "cache_control" not in sent_messages[1]


async def test_caching_no_system_messages_unchanged(mock_openai_class):
    """Messages without system prefix pass through unchanged."""
    _, client = mock_openai_class
    client.chat.completions.create.return_value = _make_response()

    provider = KimiLLMProvider(api_key="test")
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]
    await provider.complete("kimi-k2.7", messages)

    call_kwargs = client.chat.completions.create.call_args[1]
    sent_messages = call_kwargs["messages"]
    # No annotations added
    for msg in sent_messages:
        assert "cache_control" not in msg
