"""Unit tests for beddel_provider_gemini.adapter module."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from beddel.domain.errors import AdapterError
from beddel.domain.ports import ILLMProvider
from beddel_provider_gemini.adapter import GeminiLLMProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MODEL = "gemini-3.1-pro"
_MESSAGES: list[dict[str, Any]] = [{"role": "user", "content": "Hello!"}]


def _make_response(
    *,
    text: str = "Hello!",
    prompt_tokens: int = 10,
    candidates_tokens: int = 5,
    total_tokens: int = 15,
    finish_reason: str = "STOP",
) -> MagicMock:
    """Build a mock Gemini generate_content response."""
    response = MagicMock()
    response.text = text

    usage = MagicMock()
    usage.prompt_token_count = prompt_tokens
    usage.candidates_token_count = candidates_tokens
    usage.total_token_count = total_tokens
    response.usage_metadata = usage

    candidate = MagicMock()
    candidate.finish_reason = finish_reason
    response.candidates = [candidate]
    return response


def _make_stream_chunks(texts: list[str] | None = None) -> list[MagicMock]:
    """Build a list of mock streaming chunks with .text attribute."""
    chunks = []
    for text in texts or ["He", "llo", "!"]:
        chunk = MagicMock()
        chunk.text = text
        chunks.append(chunk)
    return chunks


async def _async_iter(items: list[Any]) -> Any:
    """Return an async iterator over *items*."""
    for item in items:
        yield item


def _mock_client() -> MagicMock:
    """Create a mock genai.Client with async model methods."""
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=_make_response())
    client.aio.models.generate_content_stream = MagicMock(
        return_value=_async_iter(_make_stream_chunks())
    )
    return client


# ---------------------------------------------------------------------------
# Tests: Construction (subtasks 3.2, 3.3)
# ---------------------------------------------------------------------------


class TestConstruction:
    """GeminiLLMProvider construction and interface compliance."""

    def test_is_subclass_of_illm_provider(self) -> None:
        assert issubclass(GeminiLLMProvider, ILLMProvider)

    @patch("beddel_provider_gemini.adapter.genai")
    def test_construction_with_api_key_env_var(self, mock_genai: MagicMock) -> None:
        """Constructor uses GOOGLE_API_KEY env var when set."""
        mock_genai.Client.return_value = MagicMock()
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key-123"}):
            provider = GeminiLLMProvider()

        assert isinstance(provider, ILLMProvider)
        mock_genai.Client.assert_called_once_with(api_key="test-key-123")

    @patch("beddel_provider_gemini.adapter.genai")
    def test_construction_without_api_key_adc_fallback(self, mock_genai: MagicMock) -> None:
        """Constructor falls back to ADC when no API key is available."""
        mock_genai.Client.return_value = MagicMock()
        with patch.dict("os.environ", {}, clear=True):
            provider = GeminiLLMProvider()

        assert isinstance(provider, ILLMProvider)
        mock_genai.Client.assert_called_once_with(
            vertexai=True,
            project=None,
            location="us-central1",
        )


    @patch("beddel_provider_gemini.adapter.genai")
    def test_construction_with_explicit_api_key(self, mock_genai: MagicMock) -> None:
        """Explicit api_key parameter takes precedence."""
        mock_genai.Client.return_value = MagicMock()
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "env-key"}):
            GeminiLLMProvider(api_key="explicit-key")

        mock_genai.Client.assert_called_once_with(api_key="explicit-key")


# ---------------------------------------------------------------------------
# Tests: complete() (subtask 3.4)
# ---------------------------------------------------------------------------


class TestComplete:
    """Tests for GeminiLLMProvider.complete() — single-turn completion."""

    @patch("beddel_provider_gemini.adapter.genai")
    async def test_complete_returns_correct_shape(self, mock_genai: MagicMock) -> None:
        """complete() returns dict with content, usage, model, finish_reason."""
        client = _mock_client()
        mock_genai.Client.return_value = client

        provider = GeminiLLMProvider(api_key="test-key")
        result = await provider.complete(_MODEL, _MESSAGES)

        assert "content" in result
        assert "usage" in result
        assert "model" in result
        assert "finish_reason" in result
        assert result["content"] == "Hello!"
        assert result["model"] == _MODEL
        assert result["usage"] == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }
        assert result["finish_reason"] == "STOP"

    @patch("beddel_provider_gemini.adapter.genai")
    async def test_complete_calls_generate_content(self, mock_genai: MagicMock) -> None:
        """complete() calls aio.models.generate_content with correct args."""
        client = _mock_client()
        mock_genai.Client.return_value = client

        provider = GeminiLLMProvider(api_key="test-key")
        await provider.complete(_MODEL, _MESSAGES)

        client.aio.models.generate_content.assert_awaited_once()
        call_kwargs = client.aio.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == _MODEL



# ---------------------------------------------------------------------------
# Tests: complete() with safety_settings (subtask 3.5)
# ---------------------------------------------------------------------------


class TestCompleteSafetySettings:
    """Tests for safety_settings kwarg passthrough."""

    @patch("beddel_provider_gemini.adapter.genai")
    @patch("beddel_provider_gemini.adapter.genai_types")
    async def test_safety_settings_passed_to_config(
        self, mock_types: MagicMock, mock_genai: MagicMock
    ) -> None:
        """safety_settings kwarg is forwarded to GenerateContentConfig."""
        client = _mock_client()
        mock_genai.Client.return_value = client
        mock_types.GenerateContentConfig.return_value = MagicMock()

        safety = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]

        provider = GeminiLLMProvider(api_key="test-key")
        await provider.complete(_MODEL, _MESSAGES, safety_settings=safety)

        config_call = mock_types.GenerateContentConfig.call_args
        assert config_call.kwargs["safety_settings"] == safety


# ---------------------------------------------------------------------------
# Tests: stream() (subtask 3.6)
# ---------------------------------------------------------------------------


class TestStream:
    """Tests for GeminiLLMProvider.stream() — streaming completion."""

    @patch("beddel_provider_gemini.adapter.genai")
    async def test_stream_yields_text_chunks(self, mock_genai: MagicMock) -> None:
        """stream() yields string chunks from Gemini streaming response."""
        client = _mock_client()
        chunks = _make_stream_chunks(["He", "llo", " world"])
        client.aio.models.generate_content_stream = MagicMock(
            return_value=_async_iter(chunks)
        )
        mock_genai.Client.return_value = client

        provider = GeminiLLMProvider(api_key="test-key")
        collected: list[str] = []
        async for text in provider.stream(_MODEL, _MESSAGES):
            collected.append(text)

        assert collected == ["He", "llo", " world"]

    @patch("beddel_provider_gemini.adapter.genai")
    async def test_stream_skips_empty_chunks(self, mock_genai: MagicMock) -> None:
        """stream() skips chunks where .text is empty/falsy."""
        client = _mock_client()
        chunk_ok = MagicMock()
        chunk_ok.text = "Hello"
        chunk_empty = MagicMock()
        chunk_empty.text = ""
        chunk_none = MagicMock()
        chunk_none.text = None

        client.aio.models.generate_content_stream = MagicMock(
            return_value=_async_iter([chunk_empty, chunk_ok, chunk_none])
        )
        mock_genai.Client.return_value = client

        provider = GeminiLLMProvider(api_key="test-key")
        collected: list[str] = []
        async for text in provider.stream(_MODEL, _MESSAGES):
            collected.append(text)

        assert collected == ["Hello"]



# ---------------------------------------------------------------------------
# Tests: Error handling (subtasks 3.7, 3.8)
# ---------------------------------------------------------------------------


class TestErrorHandlingComplete:
    """Tests for error wrapping in complete()."""

    @patch("beddel_provider_gemini.adapter.genai")
    async def test_auth_error_raises_adapt_050(self, mock_genai: MagicMock) -> None:
        """Auth error maps to AdapterError with code BEDDEL-ADAPT-050."""
        client = _mock_client()
        client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("401 Unauthorized: invalid API key")
        )
        mock_genai.Client.return_value = client

        provider = GeminiLLMProvider(api_key="bad-key")
        with pytest.raises(AdapterError) as exc_info:
            await provider.complete(_MODEL, _MESSAGES)

        assert exc_info.value.code == "BEDDEL-ADAPT-050"
        assert exc_info.value.details["model"] == _MODEL

    @patch("beddel_provider_gemini.adapter.genai")
    async def test_safety_filter_raises_adapt_053(self, mock_genai: MagicMock) -> None:
        """Safety filter blocked maps to AdapterError with code BEDDEL-ADAPT-053."""
        client = _mock_client()
        client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("Response blocked by safety filter")
        )
        mock_genai.Client.return_value = client

        provider = GeminiLLMProvider(api_key="test-key")
        with pytest.raises(AdapterError) as exc_info:
            await provider.complete(_MODEL, _MESSAGES)

        assert exc_info.value.code == "BEDDEL-ADAPT-053"

    @patch("beddel_provider_gemini.adapter.genai")
    async def test_rate_limit_error_raises_adapt_051(self, mock_genai: MagicMock) -> None:
        """Rate limit error maps to AdapterError with code BEDDEL-ADAPT-051."""
        client = _mock_client()
        client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("429 RESOURCE_EXHAUSTED: rate limit exceeded")
        )
        mock_genai.Client.return_value = client

        provider = GeminiLLMProvider(api_key="test-key")
        with pytest.raises(AdapterError) as exc_info:
            await provider.complete(_MODEL, _MESSAGES)

        assert exc_info.value.code == "BEDDEL-ADAPT-051"

    @patch("beddel_provider_gemini.adapter.genai")
    async def test_model_not_found_raises_adapt_052(self, mock_genai: MagicMock) -> None:
        """Model not found error maps to AdapterError with code BEDDEL-ADAPT-052."""
        client = _mock_client()
        client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("404 NOT_FOUND: model not found")
        )
        mock_genai.Client.return_value = client

        provider = GeminiLLMProvider(api_key="test-key")
        with pytest.raises(AdapterError) as exc_info:
            await provider.complete("nonexistent-model", _MESSAGES)

        assert exc_info.value.code == "BEDDEL-ADAPT-052"

    @patch("beddel_provider_gemini.adapter.genai")
    async def test_error_preserves_original_cause(self, mock_genai: MagicMock) -> None:
        """Wrapped AdapterError preserves original exception via __cause__."""
        client = _mock_client()
        original = Exception("401 auth failure")
        client.aio.models.generate_content = AsyncMock(side_effect=original)
        mock_genai.Client.return_value = client

        provider = GeminiLLMProvider(api_key="test-key")
        with pytest.raises(AdapterError) as exc_info:
            await provider.complete(_MODEL, _MESSAGES)

        assert exc_info.value.__cause__ is original



class TestErrorHandlingStream:
    """Tests for error wrapping in stream()."""

    @patch("beddel_provider_gemini.adapter.genai")
    async def test_stream_auth_error_at_call_time(self, mock_genai: MagicMock) -> None:
        """Auth error at stream call time raises AdapterError BEDDEL-ADAPT-050."""
        client = _mock_client()
        client.aio.models.generate_content_stream = MagicMock(
            side_effect=Exception("403 Permission denied")
        )
        mock_genai.Client.return_value = client

        provider = GeminiLLMProvider(api_key="test-key")
        with pytest.raises(AdapterError) as exc_info:
            async for _ in provider.stream(_MODEL, _MESSAGES):
                pass

        assert exc_info.value.code == "BEDDEL-ADAPT-050"

    @patch("beddel_provider_gemini.adapter.genai")
    async def test_stream_safety_error_during_iteration(
        self, mock_genai: MagicMock
    ) -> None:
        """Safety error during stream iteration raises AdapterError BEDDEL-ADAPT-053."""
        client = _mock_client()

        async def _exploding_iter() -> Any:
            yield MagicMock(text="ok")
            raise Exception("Response blocked by safety settings")

        client.aio.models.generate_content_stream = MagicMock(
            return_value=_exploding_iter()
        )
        mock_genai.Client.return_value = client

        provider = GeminiLLMProvider(api_key="test-key")
        with pytest.raises(AdapterError) as exc_info:
            async for _ in provider.stream(_MODEL, _MESSAGES):
                pass

        assert exc_info.value.code == "BEDDEL-ADAPT-053"


# ---------------------------------------------------------------------------
# Tests: Message conversion (subtask 3.9)
# ---------------------------------------------------------------------------


class TestMessageConversion:
    """Tests for _convert_messages — system extraction and role mapping."""

    def test_system_messages_extracted_as_system_instruction(self) -> None:
        """System messages are extracted and concatenated into system_instruction."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "You are helpful."},
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Hello"},
        ]
        contents, system_instruction = GeminiLLMProvider._convert_messages(messages)

        assert system_instruction == "You are helpful.\nBe concise."
        assert len(contents) == 1
        assert contents[0]["role"] == "user"
        assert contents[0]["parts"] == [{"text": "Hello"}]

    def test_user_and_assistant_roles_mapped(self) -> None:
        """User maps to 'user', assistant maps to 'model'."""
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
            {"role": "user", "content": "How are you?"},
        ]
        contents, system_instruction = GeminiLLMProvider._convert_messages(messages)

        assert system_instruction is None
        assert len(contents) == 3
        assert contents[0]["role"] == "user"
        assert contents[1]["role"] == "model"
        assert contents[2]["role"] == "user"

    def test_no_system_messages_returns_none(self) -> None:
        """When no system messages, system_instruction is None."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": "Hello"}]
        _, system_instruction = GeminiLLMProvider._convert_messages(messages)

        assert system_instruction is None

    def test_empty_messages_list(self) -> None:
        """Empty messages list returns empty contents and None system_instruction."""
        contents, system_instruction = GeminiLLMProvider._convert_messages([])

        assert contents == []
        assert system_instruction is None
