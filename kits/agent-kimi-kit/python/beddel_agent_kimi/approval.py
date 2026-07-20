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
from typing import TYPE_CHECKING, Any

from beddel.domain.errors import AgentError
from beddel.domain.models import ApprovalResult, ApprovalStatus, RiskLevel

if TYPE_CHECKING:
    from beddel.domain.ports import IApprovalGate

__all__ = ["KimiApprovalBridge", "KIMI_APPROVAL_DENIED"]

logger = logging.getLogger(__name__)

# Error code for approval denial / timeout
KIMI_APPROVAL_DENIED: str = "BEDDEL-AGENT-805"

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


class KimiApprovalBridge:
    """Bridges kimi-agent-sdk ApprovalRequest to Beddel IApprovalGate.

    Provides risk classification of SDK approval messages and delegates
    approval decisions to an IApprovalGate implementation or applies
    auto-approve policies based on risk level.

    Args:
        gate: IApprovalGate implementation. None enables yolo/auto-approve mode.
        mode: ``"auto"`` (risk-based policy) or ``"manual"`` (always delegate).
        timeout: Seconds before default-deny on approval request. Default 60.
    """

    def __init__(
        self,
        gate: IApprovalGate | None,
        mode: str = "auto",
        timeout: float = 60.0,
    ) -> None:
        self._gate = gate
        self._mode = mode
        self._timeout = timeout

    def should_use_yolo(self) -> bool:
        """Return True if SDK should use yolo=True (auto-approve all).

        yolo mode is appropriate when no gate is configured and mode is auto,
        meaning there is no external approval authority to consult.
        """
        return self._gate is None and self._mode == "auto"

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
        for pattern, level in _RISK_PATTERNS:
            if pattern.search(message):
                return level
        return RiskLevel.MEDIUM

    async def handle_approval(self, request: Any) -> bool:
        """Handle an ApprovalRequest from the kimi-agent-sdk.

        Args:
            request: kimi-agent-sdk ApprovalRequest (has .message and .resolve()).

        Returns:
            True if approved, False if denied.

        Raises:
            AgentError: BEDDEL-AGENT-805 on timeout (after resolving deny).
        """
        message = getattr(request, "message", str(request))
        risk_level = self.classify_risk(message)

        logger.debug(
            "Approval request: message=%r, risk=%s, mode=%s",
            message,
            risk_level.value,
            self._mode,
        )

        # Auto mode without gate: policy-based decision
        if self._mode == "auto" and self._gate is None:
            approved = risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)
            decision = "approve" if approved else "deny"
            request.resolve(decision)
            logger.info(
                "Auto-policy %s for risk=%s: %s",
                decision,
                risk_level.value,
                message,
            )
            return approved

        # Manual mode or gate provided: delegate to gate
        if self._gate is not None:
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

        # Manual mode but no gate: deny by default (conservative)
        request.resolve("deny")
        logger.warning("Manual mode with no gate, denied: %s", message)
        return False
