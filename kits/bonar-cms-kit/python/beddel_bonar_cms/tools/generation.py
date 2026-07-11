"""generate_tenant tool — LLM delegation for tenant config generation.

Generates a valid TenantConfig JSON from a business briefing by delegating
to a user-provided async LLM function. Validates the output via
validate_tenant (Node.js Zod schema) and retries once on failure with error
feedback. Does NOT write to disk.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

from beddel_bonar_cms._errors import (
    CMS_GENERATION_FAILED,
    CMSError,
)
from beddel_bonar_cms.tools.validation import validate_tenant

__all__ = ["generate_tenant"]

# TenantConfig schema shape description for the LLM prompt
_SCHEMA_DESCRIPTION = """\
TenantConfig JSON Schema (all top-level keys):

{
  "metadata": {
    "id": "string (kebab-case tenant identifier)",
    "name": "string (display name)",
    "status": "active | inactive | suspended",
    "domains": ["string (domain names)"]
  },
  "designTokens": {
    "colors": {"colorName": "#hex" | {"shade": "#hex"}},
    "typography": {
      "fontFamilies": {"name": "font-family"},
      "fontSizes": {"name": "size"},
      "fontWeights": {"name": "weight"},
      "lineHeights": {"name": "height"}
    },
    "spacing": {"name": "value"},
    "breakpoints": {"name": "min-width"},
    "backgroundImage": "string (URL, optional)",
    "custom": {"key": "value"}
  },
  "pages": {
    "pageName": {
      "route": "/path",
      "title": "Page Title",
      "description": "optional description",
      "layoutRef": "layoutId",
      "sections": [
        {
          "type": "component-type",
          "props": {"key": "value"},
          "id": "optional-id",
          "slot": "optional-slot"
        }
      ]
    }
  },
  "layouts": {
    "layoutId": {
      "id": "layoutId",
      "slots": [{"name": "slotName", "description": "optional"}]
    }
  },
  "components": {
    "componentName": {
      "type": "component-type",
      "props": {"key": "value"},
      "children": []
    }
  },
  "navigation": {
    "menus": {
      "menuName": {
        "items": [
          {"label": "Label", "type": "route", "route": "/path"},
          {"label": "Label", "type": "external", "href": "https://..."},
          {"label": "Label", "type": "hash", "hash": "#section"},
          {"label": "Label", "type": "group", "children": [...]}
        ]
      }
    }
  }
}

Optional top-level keys: "features" (record of booleans), "siteDefaults", "cacheConfig".
"""


def _build_prompt(
    briefing: str,
    *,
    template: dict[str, Any] | None = None,
    locale: str = "pt-BR",
) -> str:
    """Build the structured generation prompt for the LLM."""
    parts: list[str] = [
        "You are a web CMS configuration generator. Generate a valid TenantConfig JSON "
        "based on the business briefing below.",
        "",
        f"LANGUAGE/LOCALE: Generate all user-facing text content in {locale}.",
        "",
        "SCHEMA:",
        _SCHEMA_DESCRIPTION,
        "",
        "RULES:",
        "- Output ONLY valid JSON (no markdown fences, no explanation text).",
        "- All required fields must be present: metadata, designTokens, pages, layouts, "
        "components, navigation.",
        "- metadata.status should be 'active'.",
        "- Pages must reference existing layouts via layoutRef.",
        "- Navigation items of type 'route' must reference existing page routes.",
        "- Use realistic, professional content appropriate for the business described.",
        "",
    ]

    if template:
        parts.extend(
            [
                "TEMPLATE (use as starting point / structural reference):",
                json.dumps(template, indent=2, ensure_ascii=False),
                "",
            ]
        )

    parts.extend(
        [
            "BUSINESS BRIEFING:",
            briefing,
            "",
            "Generate the complete TenantConfig JSON now:",
        ]
    )

    return "\n".join(parts)


def _build_retry_prompt(
    briefing: str,
    failed_json: str,
    errors: list[str],
    *,
    locale: str = "pt-BR",
) -> str:
    """Build a retry prompt with validation error feedback."""
    return "\n".join(
        [
            "Your previous output failed schema validation. Fix the errors and output "
            "valid TenantConfig JSON.",
            "",
            f"LANGUAGE/LOCALE: {locale}",
            "",
            "VALIDATION ERRORS:",
            *[f"  - {e}" for e in errors],
            "",
            "YOUR PREVIOUS (INVALID) OUTPUT:",
            failed_json[:4000],  # Truncate to avoid excessive prompt length
            "",
            "ORIGINAL BRIEFING:",
            briefing,
            "",
            "SCHEMA REFERENCE:",
            _SCHEMA_DESCRIPTION,
            "",
            "RULES:",
            "- Output ONLY valid JSON (no markdown fences, no explanation text).",
            "- Fix ALL validation errors listed above.",
            "",
            "Generate the corrected TenantConfig JSON now:",
        ]
    )


def _extract_json(text: str) -> str:
    """Extract JSON from LLM response, stripping markdown fences if present."""
    # Strip markdown code fences
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    # Try to find a JSON object directly
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text.strip()


async def generate_tenant(
    briefing: str,
    *,
    llm_fn: Callable[[str], Awaitable[str]] | None = None,
    template: dict[str, Any] | None = None,
    locale: str = "pt-BR",
) -> dict[str, Any]:
    """Generate a TenantConfig from a business briefing via LLM delegation.

    Builds a structured prompt describing the TenantConfig schema, calls
    ``llm_fn``, parses the JSON response, validates via ``validate_tenant``,
    and retries once on validation failure with error feedback.

    Args:
        briefing: Business description / requirements for the tenant site.
        llm_fn: Async callable that takes a prompt string and returns the LLM
            response as a string. Required — raises if None.
        template: Optional partial dict to include as structural reference in
            the prompt.
        locale: Language/locale for generated content (default: "pt-BR").

    Returns:
        Valid TenantConfig dict.

    Raises:
        CMSError: With code ``CMS_GENERATION_FAILED`` if no llm_fn provided,
            JSON parsing fails on both attempts, or validation fails after retry.
    """
    if llm_fn is None:
        raise CMSError(
            code=CMS_GENERATION_FAILED,
            message="No LLM function provided — generate_tenant requires an async "
            "llm_fn(prompt: str) -> str callable",
        )

    # First attempt
    prompt = _build_prompt(briefing, template=template, locale=locale)
    raw_response = await llm_fn(prompt)

    extracted = _extract_json(raw_response)
    try:
        parsed = json.loads(extracted)
    except (json.JSONDecodeError, ValueError) as exc:
        # JSON parse failure — retry with feedback
        retry_prompt = _build_retry_prompt(
            briefing,
            extracted[:2000],
            [f"JSON parse error: {exc}"],
            locale=locale,
        )
        raw_response_2 = await llm_fn(retry_prompt)
        extracted_2 = _extract_json(raw_response_2)
        try:
            parsed = json.loads(extracted_2)
        except (json.JSONDecodeError, ValueError) as exc2:
            raise CMSError(
                code=CMS_GENERATION_FAILED,
                message=f"LLM output is not valid JSON after retry: {exc2}",
                details={"raw_response": raw_response_2[:1000]},
            ) from exc2

    # Validate against schema
    validation_result = validate_tenant(parsed)

    if validation_result["valid"]:
        return parsed

    # Retry with validation error feedback
    errors: list[str] = validation_result.get("errors", [])
    retry_prompt = _build_retry_prompt(
        briefing,
        json.dumps(parsed, indent=2, ensure_ascii=False)[:4000],
        errors,
        locale=locale,
    )
    raw_response_retry = await llm_fn(retry_prompt)
    extracted_retry = _extract_json(raw_response_retry)

    try:
        parsed_retry = json.loads(extracted_retry)
    except (json.JSONDecodeError, ValueError) as exc:
        raise CMSError(
            code=CMS_GENERATION_FAILED,
            message=f"LLM retry output is not valid JSON: {exc}",
            details={"errors": errors, "raw_response": raw_response_retry[:1000]},
        ) from exc

    validation_retry = validate_tenant(parsed_retry)

    if validation_retry["valid"]:
        return parsed_retry

    raise CMSError(
        code=CMS_GENERATION_FAILED,
        message="LLM generation failed schema validation after retry",
        details={
            "errors": validation_retry.get("errors", []),
            "warnings": validation_retry.get("warnings", []),
        },
    )
