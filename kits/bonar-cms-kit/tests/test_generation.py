"""Unit tests for generate_tenant tool (mocked LLM + mocked validate_tenant)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from beddel_bonar_cms._errors import (
    CMS_GENERATION_FAILED,
    CMSError,
)
from beddel_bonar_cms.tools.generation import generate_tenant

_VALID_TENANT = {
    "metadata": {
        "id": "meu-negocio",
        "name": "Meu Negócio",
        "status": "active",
        "domains": ["meunegocio.com.br"],
    },
    "designTokens": {
        "colors": {"primary": "#3b82f6", "secondary": "#10b981"},
    },
    "pages": {
        "home": {
            "route": "/",
            "title": "Início",
            "layoutRef": "default",
            "sections": [
                {"type": "hero", "props": {"title": "Bem-vindo"}},
            ],
        },
    },
    "layouts": {
        "default": {
            "id": "default",
            "slots": [{"name": "main"}],
        },
    },
    "components": {
        "hero": {
            "type": "hero",
            "props": {"title": ""},
        },
    },
    "navigation": {
        "menus": {
            "main": {
                "items": [
                    {"label": "Início", "type": "route", "route": "/"},
                ],
            },
        },
    },
}

_PATCH_VALIDATE = "beddel_bonar_cms.tools.generation.validate_tenant"


class TestGenerateTenantSuccess:
    """Tests for successful generation scenarios."""

    @pytest.mark.asyncio
    @patch(_PATCH_VALIDATE)
    async def test_valid_first_attempt(self, mock_validate: AsyncMock) -> None:
        """LLM returns valid JSON on first attempt — returns dict directly."""
        mock_validate.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_llm = AsyncMock(return_value=json.dumps(_VALID_TENANT))

        result = await generate_tenant("Loja de roupas online", llm_fn=mock_llm)

        assert result == _VALID_TENANT
        mock_llm.assert_called_once()
        mock_validate.assert_called_once_with(_VALID_TENANT)

    @pytest.mark.asyncio
    @patch(_PATCH_VALIDATE)
    async def test_retry_on_validation_failure(self, mock_validate: AsyncMock) -> None:
        """Invalid first attempt, valid second — calls llm_fn twice."""
        # First call: invalid; second call: valid
        mock_validate.side_effect = [
            {"valid": False, "errors": ["metadata: Required"], "warnings": []},
            {"valid": True, "errors": [], "warnings": []},
        ]
        mock_llm = AsyncMock(
            side_effect=[
                json.dumps({"incomplete": True}),
                json.dumps(_VALID_TENANT),
            ]
        )

        result = await generate_tenant("Restaurante japonês", llm_fn=mock_llm)

        assert result == _VALID_TENANT
        assert mock_llm.call_count == 2
        assert mock_validate.call_count == 2

    @pytest.mark.asyncio
    @patch(_PATCH_VALIDATE)
    async def test_json_in_markdown_fences(self, mock_validate: AsyncMock) -> None:
        """LLM wraps JSON in markdown code fences — extracted correctly."""
        mock_validate.return_value = {"valid": True, "errors": [], "warnings": []}
        fenced_response = f"```json\n{json.dumps(_VALID_TENANT)}\n```"
        mock_llm = AsyncMock(return_value=fenced_response)

        result = await generate_tenant("Padaria artesanal", llm_fn=mock_llm)

        assert result == _VALID_TENANT


class TestGenerateTenantFailure:
    """Tests for error scenarios."""

    @pytest.mark.asyncio
    async def test_no_llm_fn_raises(self) -> None:
        """No llm_fn provided — raises CMS_GENERATION_FAILED."""
        with pytest.raises(CMSError) as exc_info:
            await generate_tenant("Some briefing", llm_fn=None)

        assert exc_info.value.code == CMS_GENERATION_FAILED
        assert "no llm function" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    @patch(_PATCH_VALIDATE)
    async def test_both_attempts_invalid(self, mock_validate: AsyncMock) -> None:
        """Both attempts fail validation — raises CMS_GENERATION_FAILED."""
        mock_validate.return_value = {
            "valid": False,
            "errors": ["metadata.id: Required", "navigation: Required"],
            "warnings": [],
        }
        mock_llm = AsyncMock(
            side_effect=[
                json.dumps({"bad": True}),
                json.dumps({"still_bad": True}),
            ]
        )

        with pytest.raises(CMSError) as exc_info:
            await generate_tenant("Salão de beleza", llm_fn=mock_llm)

        assert exc_info.value.code == CMS_GENERATION_FAILED
        assert exc_info.value.details is not None
        assert "errors" in exc_info.value.details
        assert mock_llm.call_count == 2

    @pytest.mark.asyncio
    async def test_json_parse_failure_both_attempts(self) -> None:
        """LLM returns non-JSON on both attempts — raises CMS_GENERATION_FAILED."""
        mock_llm = AsyncMock(
            side_effect=[
                "This is not JSON at all",
                "Still not JSON",
            ]
        )

        with pytest.raises(CMSError) as exc_info:
            await generate_tenant("Consultório médico", llm_fn=mock_llm)

        assert exc_info.value.code == CMS_GENERATION_FAILED
        assert mock_llm.call_count == 2


class TestGenerateTenantPrompt:
    """Tests verifying prompt construction."""

    @pytest.mark.asyncio
    @patch(_PATCH_VALIDATE)
    async def test_template_included_in_prompt(self, mock_validate: AsyncMock) -> None:
        """Custom template is included in the LLM prompt."""
        mock_validate.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_llm = AsyncMock(return_value=json.dumps(_VALID_TENANT))
        custom_template = {"metadata": {"status": "active"}, "designTokens": {}}

        await generate_tenant(
            "Loja virtual",
            llm_fn=mock_llm,
            template=custom_template,
        )

        # Verify the prompt sent to LLM contains the template
        prompt_sent = mock_llm.call_args[0][0]
        assert "TEMPLATE" in prompt_sent
        assert '"active"' in prompt_sent

    @pytest.mark.asyncio
    @patch(_PATCH_VALIDATE)
    async def test_locale_included_in_prompt(self, mock_validate: AsyncMock) -> None:
        """Locale is included as instruction in the prompt."""
        mock_validate.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_llm = AsyncMock(return_value=json.dumps(_VALID_TENANT))

        await generate_tenant(
            "English bakery shop",
            llm_fn=mock_llm,
            locale="en-US",
        )

        prompt_sent = mock_llm.call_args[0][0]
        assert "en-US" in prompt_sent

    @pytest.mark.asyncio
    @patch(_PATCH_VALIDATE)
    async def test_default_locale_pt_br(self, mock_validate: AsyncMock) -> None:
        """Default locale is pt-BR."""
        mock_validate.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_llm = AsyncMock(return_value=json.dumps(_VALID_TENANT))

        await generate_tenant("Padaria", llm_fn=mock_llm)

        prompt_sent = mock_llm.call_args[0][0]
        assert "pt-BR" in prompt_sent

    @pytest.mark.asyncio
    @patch(_PATCH_VALIDATE)
    async def test_retry_prompt_includes_errors(self, mock_validate: AsyncMock) -> None:
        """Retry prompt includes validation errors from first attempt."""
        mock_validate.side_effect = [
            {"valid": False, "errors": ["metadata.id: Required"], "warnings": []},
            {"valid": True, "errors": [], "warnings": []},
        ]
        mock_llm = AsyncMock(
            side_effect=[
                json.dumps({"no_metadata": True}),
                json.dumps(_VALID_TENANT),
            ]
        )

        await generate_tenant("Pizzaria", llm_fn=mock_llm)

        # Second call (retry) should include the error
        retry_prompt = mock_llm.call_args_list[1][0][0]
        assert "metadata.id: Required" in retry_prompt
