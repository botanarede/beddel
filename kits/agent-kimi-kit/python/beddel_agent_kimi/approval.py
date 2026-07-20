"""Kimi Approval Flow Bridge — ApprovalRequest to IApprovalGate.

Bridges the kimi-agent-sdk ApprovalRequest wire message to the Beddel
domain IApprovalGate protocol, enabling risk-based approval policies
and human-on-the-loop (HOTL) workflows.

[Source: docs/architecture §40.8 — Approval Flow Bridge]
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, NamedTuple

from beddel.domain.errors import AgentError
from beddel.domain.models import ApprovalResult, ApprovalStatus, RiskLevel
from beddel_agent_kimi.errors import KIMI_APPROVAL_DENIED

if TYPE_CHECKING:
    from beddel.domain.ports import IApprovalGate

__all__ = ["KimiApprovalBridge", "KIMI_APPROVAL_DENIED"]

logger = logging.getLogger(__name__)

# Valid approval modes
_VALID_MODES = ("auto", "manual", "yolo")

# Risk classification regex patterns (case-insensitive)
_RISK_PATTERNS: list[tuple[re.Pattern[str], RiskLevel]] = [
    (
        re.compile(
            r"(?:shell|bash|command|execute|run\s+command|terminal)", re.IGNORECASE
        ),
        RiskLevel.HIGH,
    ),
    (
        re.compile(r"(?:write|create|new)\s+(?:file|document)", re.IGNORECASE),
        RiskLevel.LOW,
    ),
    (
        re.compile(r"(?:edit|modify|update|change)\s+(?:file|existing)", re.IGNORECASE),
        RiskLevel.MEDIUM,
    ),
]


class _RiskClassification(NamedTuple):
    """Internal risk classification result with recognition flag."""

    level: RiskLevel
    recognized: bool


class KimiApprovalBridge:
    """Bridges kimi-agent-sdk ApprovalRequest to Beddel IApprovalGate.

    Provides risk classification of SDK approval messages and delegates
    approval decisions to an IApprovalGate implementation or applies
    auto-approve policies based on risk level.

    Args:
        gate: IApprovalGate implementation. None disables manual delegation.
        mode: ``"auto"`` (risk-based policy), ``"manual"`` (always delegate),
            or ``"yolo"`` (opt-in unsafe auto-approve all).
        timeout: Seconds before default-deny on approval request. Default 60.

    Raises:
        ValueError: If mode is not one of the valid modes or timeout <= 0.
    """

    def __init__(
        self,
        gate: IApprovalGate | None,
        mode: str = "auto",
        timeout: float = 60.0,
    ) -> None:
        if mode not in _VALID_MODES:
            raise ValueError(
                f"Invalid approval mode {mode!r}. Must be one of: {_VALID_MODES}"
            )
        if timeout <= 0:
            raise ValueError(f"Approval timeout must be > 0, got {timeout}")
        self._gate = gate
        self._mode = mode
        self._timeout = timeout

    def should_use_yolo(self) -> bool:
        """Return True if SDK should use yolo=True (auto-approve all).

        Only returns True for the explicit ``"yolo"`` mode — an opt-in
        unsafe escape hatch. For ``"auto"`` and ``"manual"`` modes, always
        returns False so that ApprovalRequest messages are intercepted.
        """
        return self._mode == "yolo"

    def classify_risk(self, message: str) -> RiskLevel:
        """Classify risk level from an ApprovalRequest message string.

        Uses regex-based best-effort classification:
        - File creation patterns (write new, create file) -> LOW
        - File edit patterns (edit, modify, update file) -> MEDIUM
        - Shell/bash/command patterns (run command, execute, bash) -> HIGH
        - Unknown/unclassifiable -> MEDIUM (conservative default)

        Args:
            message: The approval request message from the SDK.

        Returns:
            Classified RiskLevel.
        """
        return self._classify_with_recognition(message).level

    def _classify_with_recognition(self, message: str) -> _RiskClassification:
        """Classify risk and track whether the pattern was recognized.

        Returns a named tuple of (level, recognized) where recognized=True
        means a known pattern matched, and recognized=False means the message
        fell through to the conservative MEDIUM default.
        """
        for pattern, level in _RISK_PATTERNS:
            if pattern.search(message):
                return _RiskClassification(level=level, recognized=True)
        return _RiskClassification(level=RiskLevel.MEDIUM, recognized=False)

    async def handle_approval(self, request: Any) -> bool:
        """Handle an ApprovalRequest from the kimi-agent-sdk.

        Applies the §40.8 approval policy:
        - ``"auto"`` mode: deterministic risk-based decision regardless of gate.
            LOW/recognized MEDIUM -> approve; unrecognized MEDIUM/HIGH/CRITICAL -> deny.
        - ``"manual"`` mode: delegates to gate (with timeout + exception safety).
        - ``"yolo"`` mode: approve everything (should not normally reach here
            since yolo=True suppresses ApprovalRequests at SDK level).

        Args:
            request: kimi-agent-sdk ApprovalRequest (has .message and .resolve()).

        Returns:
            True if approved, False if denied.

        Raises:
            AgentError: BEDDEL-AGENT-805 on timeout or gate failure
                (after resolving deny).
        """
        message = getattr(request, "message", str(request))
        classification = self._classify_with_recognition(message)
        risk_level = classification.level
        recognized = classification.recognized

        logger.debug(
            "Approval request: message=%r, risk=%s, recognized=%s, mode=%s",
            message,
            risk_level.value,
            recognized,
            self._mode,
        )

        # Yolo mode: approve everything (fallback if SDK still sends requests)
        if self._mode == "yolo":
            request.resolve("approve")
            logger.info("Yolo mode, auto-approved: %s", message)
            return True

        # Auto mode: deterministic risk-based policy (§40.8)
        # Applied REGARDLESS of whether a gate exists.
        if self._mode == "auto":
            approved = self._auto_decision(risk_level, recognized)
            decision = "approve" if approved else "deny"
            request.resolve(decision)
            logger.info(
                "Auto-policy %s for risk=%s (recognized=%s): %s",
                decision,
                risk_level.value,
                recognized,
                message,
            )
            return approved

        # Manual mode: delegate to gate
        if self._gate is not None:
            return await self._delegate_to_gate(request, message, risk_level)

        # Manual mode but no gate: deny by default (conservative)
        request.resolve("deny")
        logger.warning("Manual mode with no gate, denied: %s", message)
        return False

    @staticmethod
    def _auto_decision(risk_level: RiskLevel, recognized: bool) -> bool:
        """Apply the §40.8 auto-mode decision table.

        - LOW + recognized -> approve
        - MEDIUM + recognized (file edit) -> approve
        - MEDIUM + NOT recognized (unknown) -> deny
        - HIGH -> deny
        - CRITICAL -> deny
        """
        if risk_level == RiskLevel.LOW:
            return True
        if risk_level == RiskLevel.MEDIUM:
            return recognized
        # HIGH and CRITICAL always denied
        return False

    async def _delegate_to_gate(
        self, request: Any, message: str, risk_level: RiskLevel
    ) -> bool:
        """Delegate approval to the IApprovalGate with full exception safety.

        Catches TimeoutError, CancelledError, and any other Exception to
        ensure request.resolve("deny") is always called before propagating.
        """
        assert self._gate is not None  # noqa: S101

        try:
            result: ApprovalResult = await asyncio.wait_for(
                self._gate.request_approval(message, risk_level),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            request.resolve("deny")
            logger.warning(
                "Approval timeout after %.1fs, denied: %s",
                self._timeout,
                message,
            )
            raise AgentError(
                code=KIMI_APPROVAL_DENIED,
                message=f"Approval request timed out after {self._timeout}s",
                details={
                    "action": message,
                    "risk_level": risk_level.value,
                    "timeout": self._timeout,
                },
            )
        except asyncio.CancelledError:
            request.resolve("deny")
            logger.warning(
                "Approval cancelled, denied: %s",
                message,
            )
            raise
        except Exception as exc:
            request.resolve("deny")
            logger.exception(
                "Gate exception, denied: %s (error: %s)",
                message,
                exc,
            )
            raise AgentError(
                code=KIMI_APPROVAL_DENIED,
                message=f"Approval gate failed: {exc}",
                details={
                    "action": message,
                    "risk_level": risk_level.value,
                    "error": str(exc),
                },
            ) from exc

        approved = result.status == ApprovalStatus.APPROVED
        decision = "approve" if approved else "deny"
        request.resolve(decision)
        logger.info(
            "Gate %s (status=%s) for risk=%s: %s",
            decision,
            result.status.value,
            risk_level.value,
            message,
        )
        return approved
