"""Model Armor guardrail strategy for prompt injection defense.

Implements :meth:`validate_input` and :meth:`validate_output` using
Google Cloud Model Armor API for prompt injection detection and
content policy enforcement.

Authentication uses Application Default Credentials (ADC).  On Cloud
Run the service account is used automatically; locally, run
``gcloud auth application-default login``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

# Error code constants (kit-local — kits don't modify beddel/error_codes.py)
MODEL_ARMOR_UNAVAILABLE = "BEDDEL-GUARD-250"
PROMPT_INJECTION_DETECTED = "BEDDEL-GUARD-251"
POLICY_VIOLATION_DETECTED = "BEDDEL-GUARD-252"

logger = logging.getLogger(__name__)

# Import guard for google-cloud-modelarmor
try:
    from google.cloud import modelarmor_v1  # type: ignore[import-untyped]
    from google.cloud.modelarmor_v1 import types as ma_types  # type: ignore[import-untyped]
except ImportError:
    modelarmor_v1 = None  # type: ignore[assignment]
    ma_types = None  # type: ignore[assignment]


@dataclass
class GuardrailResult:
    """Result of a guardrail validation check."""

    passed: bool
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class ModelArmorGuardrailStrategy:
    """Guardrail strategy using Google Cloud Model Armor API.

    Validates inputs and outputs for prompt injection and policy
    violations.  Uses Application Default Credentials (ADC) for
    authentication.

    Args:
        project_id: GCP project ID (required).
        location: GCP region for Model Armor (default ``us-central1``).
        sensitivity: Detection sensitivity — ``low``, ``medium``, or
            ``high`` (default ``medium``).
        check_input: Whether to validate user input (default ``True``).
        check_output: Whether to validate model output (default ``True``).
        fallback_on_error: Behavior when Model Armor API is unavailable —
            ``pass`` (allow through, default) or ``block`` (reject).

    Raises:
        ImportError: If ``google-cloud-modelarmor`` is not installed.
        ValueError: If ``project_id`` is not provided, or ``sensitivity``
            / ``fallback_on_error`` have invalid values.
    """

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        sensitivity: str = "medium",
        check_input: bool = True,
        check_output: bool = True,
        fallback_on_error: str = "pass",
    ) -> None:
        if modelarmor_v1 is None:
            raise ImportError(
                "google-cloud-modelarmor is required for "
                "ModelArmorGuardrailStrategy. "
                "Install it with: pip install google-cloud-modelarmor"
            )
        if sensitivity not in ("low", "medium", "high"):
            raise ValueError(
                f"Invalid sensitivity '{sensitivity}'. Must be: low, medium, high"
            )
        if fallback_on_error not in ("pass", "block"):
            raise ValueError(
                f"Invalid fallback_on_error '{fallback_on_error}'. Must be: pass, block"
            )

        self._project_id = project_id
        self._location = location
        self._sensitivity = sensitivity
        self._check_input = check_input
        self._check_output = check_output
        self._fallback_on_error = fallback_on_error
        self._client: modelarmor_v1.ModelArmorClient | None = None

    def _get_client(self) -> modelarmor_v1.ModelArmorClient:
        """Lazy-initialize the Model Armor client."""
        if self._client is None:
            self._client = modelarmor_v1.ModelArmorClient()
        return self._client

    def _get_template_name(self) -> str:
        """Return the Model Armor template resource name."""
        return (
            f"projects/{self._project_id}/locations/{self._location}/templates/default"
        )

    async def validate_input(
        self,
        text: str,
        config: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        """Validate user input for prompt injection.

        Sends *text* to the Model Armor ``sanitize_user_prompt`` endpoint.
        The synchronous GCP client call is offloaded to a thread so the
        event loop is never blocked.

        Args:
            text: The user prompt to validate.
            config: Optional per-call config overrides (reserved).

        Returns:
            :class:`GuardrailResult` — ``passed=True`` if clean,
            ``passed=False`` with reason if flagged or API unavailable.
        """
        if not self._check_input:
            return GuardrailResult(passed=True, reason="Input check disabled")

        try:
            client = self._get_client()
            request = ma_types.SanitizeUserPromptRequest(
                name=self._get_template_name(),
                user_prompt_data=ma_types.UserPromptData(text=text),
            )
            response = await asyncio.to_thread(
                client.sanitize_user_prompt, request=request
            )

            # Check if the response indicates the input is safe
            sanitization_result = response.sanitization_result
            if (
                sanitization_result
                and sanitization_result.filter_match_state
                == ma_types.FilterMatchState.MATCH_FOUND
            ):
                return GuardrailResult(
                    passed=False,
                    reason="prompt injection detected",
                    details={
                        "code": PROMPT_INJECTION_DETECTED,
                        "filter_results": str(sanitization_result),
                    },
                )
            return GuardrailResult(passed=True)

        except Exception as exc:
            return self._apply_fallback(exc)

    async def validate_output(
        self,
        text: str,
        config: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        """Validate model output for policy violations.

        Sends *text* to the Model Armor ``sanitize_model_response``
        endpoint.  The synchronous GCP client call is offloaded to a
        thread so the event loop is never blocked.

        Args:
            text: The model response to validate.
            config: Optional per-call config overrides (reserved).

        Returns:
            :class:`GuardrailResult` — ``passed=True`` if clean,
            ``passed=False`` with reason if flagged or API unavailable.
        """
        if not self._check_output:
            return GuardrailResult(passed=True, reason="Output check disabled")

        try:
            client = self._get_client()
            request = ma_types.SanitizeModelResponseRequest(
                name=self._get_template_name(),
                model_response_data=ma_types.ModelResponseData(text=text),
            )
            response = await asyncio.to_thread(
                client.sanitize_model_response, request=request
            )

            sanitization_result = response.sanitization_result
            if (
                sanitization_result
                and sanitization_result.filter_match_state
                == ma_types.FilterMatchState.MATCH_FOUND
            ):
                return GuardrailResult(
                    passed=False,
                    reason="policy violation detected",
                    details={
                        "code": POLICY_VIOLATION_DETECTED,
                        "filter_results": str(sanitization_result),
                    },
                )
            return GuardrailResult(passed=True)

        except Exception as exc:
            return self._apply_fallback(exc)

    def _apply_fallback(self, error: Exception) -> GuardrailResult:
        """Apply fallback policy when Model Armor API is unavailable."""
        logger.warning("Model Armor API error: %s", error)

        if self._fallback_on_error == "pass":
            return GuardrailResult(
                passed=True,
                reason="Model Armor unavailable, pass-through applied",
                details={
                    "code": MODEL_ARMOR_UNAVAILABLE,
                    "error": str(error),
                },
            )
        return GuardrailResult(
            passed=False,
            reason="Model Armor unavailable, blocking by policy",
            details={
                "code": MODEL_ARMOR_UNAVAILABLE,
                "error": str(error),
            },
        )
