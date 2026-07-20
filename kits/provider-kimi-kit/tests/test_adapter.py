"""Unit tests for KimiLLMProvider adapter."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import AuthenticationError, BadRequestError, NotFoundError, RateLimitError

from beddel.domain.errors import AdapterError
from beddel_provider_kimi.adapter import KimiLLMProvider
from beddel_provider_kimi.errors import (
    ADAPT_KIMI_AUTH,
    ADAPT_KIMI_MODEL_UNAVAILABLE,
    ADAPT_KIMI_PARAM_REJECTED,
    ADAPT_KIMI_RATE_LIMIT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _make_response(
    content: str = "Hello",
    reasoning_content: str | None = None,
    model_extra: dict | None = None,
    tool_calls: list | None = None,
    finish_reason: str = "stop",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> MagicMock:
    """Build a mock ChatCompletion response."""
    message = MagicMock()
    message.content = content
    message.reasoning_content = reasoning_content
    message.model_extra = model_extra
    message.tool_calls = tool_calls

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = finish_reason

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_chunk(
    content: str | None = None, reasoning_content: str | None = None
) -> MagicMock:
    """Build a mock streaming chunk."""
    delta = MagicMock()
    delta.content = content
    delta.reasoning_content = reasoning_content

    choice = MagicMock()
    choice.delta = delta

    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client():
    """Patch AsyncOpenAI and return the mock client instance."""
    with patch("beddel_provider_kimi.adapter.AsyncOpenAI") as MockClass:
        client_instance = MagicMock()
        client_instance.chat.completions.create = AsyncMock()
        MockClass.return_value = client_instance
        yield client_instance


@pytest.fixture
def provider(mock_client) -> KimiLLMProvider:
    """Create a KimiLLMProvider with a mocked client."""
    return KimiLLMProvider(api_key="test-key")


# ---------------------------------------------------------------------------
# Tests: complete() happy path
# ---------------------------------------------------------------------------


async def test_complete_happy_path(provider, mock_client):
    """complete() returns dict with expected keys and values."""
    mock_client.chat.completions.create.return_value = _make_response(
        content="Hello world",
        finish_reason="stop",
        prompt_tokens=15,
        completion_tokens=8,
    )

    result = await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    assert result["content"] == "Hello world"
    assert result["model"] == "kimi-k2.7"
    assert result["finish_reason"] == "stop"
    assert result["usage"] == {"prompt_tokens": 15, "completion_tokens": 8}
    assert result["reasoning"] is None
    assert result["tool_calls"] is None


async def test_complete_reasoning_extraction(provider, mock_client):
    """Reasoning content extracted from reasoning_content attribute."""
    mock_client.chat.completions.create.return_value = _make_response(
        content="Answer",
        reasoning_content="I need to think step by step",
    )

    result = await provider.complete(
        "kimi-k2.7", [{"role": "user", "content": "Think"}]
    )

    assert result["reasoning"] == "I need to think step by step"


async def test_complete_reasoning_from_model_extra(provider, mock_client):
    """Reasoning content falls back to model_extra dict."""
    response = _make_response(content="Answer")
    response.choices[0].message.reasoning_content = None
    response.choices[0].message.model_extra = {
        "reasoning_content": "Fallback reasoning"
    }
    mock_client.chat.completions.create.return_value = response

    result = await provider.complete(
        "kimi-k2.7", [{"role": "user", "content": "Think"}]
    )

    assert result["reasoning"] == "Fallback reasoning"


async def test_complete_tool_calls_preserved(provider, mock_client):
    """Tool calls from response are passed through in return dict."""
    tool_call = MagicMock()
    tool_call.id = "call_123"
    tool_call.function.name = "get_weather"
    tool_call.function.arguments = '{"city": "London"}'

    mock_client.chat.completions.create.return_value = _make_response(
        content="",
        tool_calls=[tool_call],
        finish_reason="tool_calls",
    )

    result = await provider.complete(
        "kimi-k2.7",
        [{"role": "user", "content": "Weather?"}],
        tools=[{"type": "function", "function": {"name": "get_weather"}}],
    )

    assert result["tool_calls"] == [tool_call]
    assert result["finish_reason"] == "tool_calls"


# ---------------------------------------------------------------------------
# Tests: stream()
# ---------------------------------------------------------------------------


async def test_stream_happy_path(provider, mock_client):
    """stream() yields only content strings."""
    chunks = [
        _make_chunk(content="Hello"),
        _make_chunk(content=" world"),
        _make_chunk(content="!"),
    ]
    mock_client.chat.completions.create.return_value = MockAsyncStream(chunks)

    collected = []
    async for token in provider.stream(
        "kimi-k2.7", [{"role": "user", "content": "Hi"}]
    ):
        collected.append(token)

    assert collected == ["Hello", " world", "!"]


async def test_stream_no_reasoning_yielded(provider, mock_client):
    """Reasoning content in delta is NOT yielded — only delta.content."""
    # Chunks where content is None but reasoning_content exists
    chunk_reasoning = MagicMock()
    chunk_reasoning.choices = [MagicMock()]
    chunk_reasoning.choices[0].delta = MagicMock()
    chunk_reasoning.choices[0].delta.content = None  # No content to yield

    chunk_content = _make_chunk(content="Final answer")

    mock_client.chat.completions.create.return_value = MockAsyncStream(
        [chunk_reasoning, chunk_content]
    )

    collected = []
    async for token in provider.stream(
        "kimi-k2.7", [{"role": "user", "content": "Think"}]
    ):
        collected.append(token)

    assert collected == ["Final answer"]


# ---------------------------------------------------------------------------
# Tests: K3 parameter normalization
# ---------------------------------------------------------------------------


async def test_k3_param_strip_temperature_matches(provider, mock_client):
    """K3: temperature=1.0 (matches fixed default) is stripped silently."""
    mock_client.chat.completions.create.return_value = _make_response()

    await provider.complete(
        "kimi-k3",
        [{"role": "user", "content": "Hi"}],
        temperature=1.0,
    )

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert "temperature" not in call_kwargs


async def test_k3_param_reject_temperature_conflicts(provider, mock_client):
    """K3: temperature != 1.0 raises ADAPT_KIMI_PARAM_REJECTED."""
    with pytest.raises(AdapterError) as exc_info:
        await provider.complete(
            "kimi-k3",
            [{"role": "user", "content": "Hi"}],
            temperature=0.7,
        )

    assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED
    assert "temperature" in exc_info.value.message


async def test_k3_tool_choice_auto_rejected(provider, mock_client):
    """K3: tool_choice='auto' is rejected."""
    with pytest.raises(AdapterError) as exc_info:
        await provider.complete(
            "kimi-k3",
            [{"role": "user", "content": "Hi"}],
            tool_choice="auto",
        )

    assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED
    assert "tool_choice" in exc_info.value.message


async def test_k3_tool_choice_required_passes(provider, mock_client):
    """K3: tool_choice='required' is accepted."""
    mock_client.chat.completions.create.return_value = _make_response()

    await provider.complete(
        "kimi-k3",
        [{"role": "user", "content": "Hi"}],
        tool_choice="required",
    )

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["tool_choice"] == "required"


async def test_k3_tool_choice_none_passes(provider, mock_client):
    """K3: tool_choice='none' is accepted."""
    mock_client.chat.completions.create.return_value = _make_response()

    await provider.complete(
        "kimi-k3",
        [{"role": "user", "content": "Hi"}],
        tool_choice="none",
    )

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["tool_choice"] == "none"


# ---------------------------------------------------------------------------
# Tests: max_tokens alias
# ---------------------------------------------------------------------------


async def test_max_tokens_alias(provider, mock_client):
    """max_tokens gets aliased to max_completion_tokens."""
    mock_client.chat.completions.create.return_value = _make_response()

    await provider.complete(
        "kimi-k2.7",
        [{"role": "user", "content": "Hi"}],
        max_tokens=1024,
    )

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert "max_tokens" not in call_kwargs
    assert call_kwargs["max_completion_tokens"] == 1024


async def test_max_tokens_conflict(provider, mock_client):
    """Both max_tokens and max_completion_tokens with different values raises."""
    with pytest.raises(AdapterError) as exc_info:
        await provider.complete(
            "kimi-k2.7",
            [{"role": "user", "content": "Hi"}],
            max_tokens=512,
            max_completion_tokens=1024,
        )

    assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED
    assert "max_tokens" in exc_info.value.message


# ---------------------------------------------------------------------------
# Tests: Vision URL validation
# ---------------------------------------------------------------------------


async def test_vision_url_rejected(provider, mock_client):
    """HTTP/HTTPS URL in image_url content part raises error."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/image.png"},
                },
            ],
        }
    ]

    with pytest.raises(AdapterError) as exc_info:
        await provider.complete("kimi-k2.7", messages)

    assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED
    assert "base64" in exc_info.value.message


async def test_vision_base64_passes(provider, mock_client):
    """Base64 data URL in image_url passes validation."""
    mock_client.chat.completions.create.return_value = _make_response(content="A cat")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,iVBORw0KGgo="},
                },
            ],
        }
    ]

    result = await provider.complete("kimi-k2.7", messages)
    assert result["content"] == "A cat"


# ---------------------------------------------------------------------------
# Tests: K2.6 / K2.7 thinking toggle
# ---------------------------------------------------------------------------


async def test_k2_6_thinking_toggle_passes(provider, mock_client):
    """K2.6: extra_body with thinking disabled passes (no restriction on K2.6)."""
    mock_client.chat.completions.create.return_value = _make_response()

    await provider.complete(
        "kimi-k2.6-math",
        [{"role": "user", "content": "Solve x^2=4"}],
        extra_body={"thinking": {"type": "disabled"}},
    )

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["extra_body"]["thinking"]["type"] == "disabled"


async def test_k2_7_thinking_disable_rejected(provider, mock_client):
    """K2.7: extra_body disabling thinking raises ADAPT_KIMI_PARAM_REJECTED."""
    with pytest.raises(AdapterError) as exc_info:
        await provider.complete(
            "kimi-k2.7",
            [{"role": "user", "content": "Think"}],
            extra_body={"thinking": {"type": "disabled"}},
        )

    assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED
    assert "thinking" in exc_info.value.message


# ---------------------------------------------------------------------------
# Tests: Error mapping
# ---------------------------------------------------------------------------


async def test_error_mapping_auth(provider, mock_client):
    """AuthenticationError maps to ADAPT_KIMI_AUTH."""
    mock_client.chat.completions.create.side_effect = AuthenticationError(
        message="Invalid API key",
        response=MagicMock(status_code=401),
        body=None,
    )

    with pytest.raises(AdapterError) as exc_info:
        await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    assert exc_info.value.code == ADAPT_KIMI_AUTH


async def test_error_mapping_rate_limit(provider, mock_client):
    """RateLimitError maps to ADAPT_KIMI_RATE_LIMIT."""
    mock_client.chat.completions.create.side_effect = RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429),
        body=None,
    )

    with pytest.raises(AdapterError) as exc_info:
        await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    assert exc_info.value.code == ADAPT_KIMI_RATE_LIMIT


async def test_error_mapping_not_found(provider, mock_client):
    """NotFoundError maps to ADAPT_KIMI_MODEL_UNAVAILABLE."""
    mock_client.chat.completions.create.side_effect = NotFoundError(
        message="Model not found",
        response=MagicMock(status_code=404),
        body=None,
    )

    with pytest.raises(AdapterError) as exc_info:
        await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    assert exc_info.value.code == ADAPT_KIMI_MODEL_UNAVAILABLE


async def test_error_mapping_bad_request(provider, mock_client):
    """BadRequestError maps to ADAPT_KIMI_PARAM_REJECTED."""
    mock_client.chat.completions.create.side_effect = BadRequestError(
        message="Invalid params",
        response=MagicMock(status_code=400),
        body=None,
    )

    with pytest.raises(AdapterError) as exc_info:
        await provider.complete("kimi-k2.7", [{"role": "user", "content": "Hi"}])

    assert exc_info.value.code == ADAPT_KIMI_PARAM_REJECTED


# ---------------------------------------------------------------------------
# Tests: Auth validation
# ---------------------------------------------------------------------------


async def test_auth_validation_missing_key():
    """No API key and no env var raises ADAPT_KIMI_AUTH on init."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("beddel_provider_kimi.adapter.AsyncOpenAI"):
            with pytest.raises(AdapterError) as exc_info:
                KimiLLMProvider()

    assert exc_info.value.code == ADAPT_KIMI_AUTH
    assert "MOONSHOT_API_KEY" in exc_info.value.message
