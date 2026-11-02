"""
Error Recovery Coordinator

Handles error recovery with fallback question generation and detailed
error logging for the triage conversation flow.
"""

import logging
import traceback
from typing import Any, Dict, List, Optional, Tuple

from src.services.triage.engines.types import TriageAction, TriageDecision


class ErrorRecoveryCoordinator:

    FALLBACK_PRIORITY: List[Tuple[str, str]] = [
        ("company_name", "Could you tell me about your business? What's the company name?"),
        ("revenue", "What is the annual revenue of your company?"),
        ("industry", "What industry does your company operate in?"),
        ("employees", "How many employees does your company have?"),
    ]

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def generate_fallback_decision(
        self, context: Any, error: Optional[Exception] = None
    ) -> TriageDecision:
        collected = getattr(context, "collected_data", None) or {}

        for field_name, question_text in self.FALLBACK_PRIORITY:
            value = collected.get(field_name)
            if value is None or value == "":
                reasoning = f"Fallback to {field_name}"
                if error is not None:
                    reasoning = f"Fallback due to {type(error).__name__}: {error}"
                return TriageDecision(
                    action=TriageAction.ASK_QUESTION,
                    field_name=field_name,
                    next_question=question_text,
                    confidence=0.5,
                    reasoning=reasoning,
                )

        reasoning = "Ultimate fallback - all priority fields collected"
        if error is not None:
            reasoning = f"Ultimate fallback due to {type(error).__name__}: {error}"
        return TriageDecision(
            action=TriageAction.ASK_QUESTION,
            field_name="company_name",
            next_question=self.FALLBACK_PRIORITY[0][1],
            confidence=0.3,
            reasoning=reasoning,
        )

    def log_detailed_error(
        self, error: Optional[Exception], context: Any, operation: str = "triage processing"
    ) -> None:
        tb_str = traceback.format_exc()
        error_type = type(error).__name__ if error is not None else "NoneType"
        error_msg = str(error) if error is not None else "None"
        session_id = getattr(context, "session_id", "unknown")

        self.logger.error(f"TRIAGE ERROR TRACEBACK:\n{tb_str}")

        self.logger.error(
            f"{error_type} error in {operation}: {error_msg}",
            extra={
                "session_id": session_id,
                "error_type": error_type,
                "error_traceback": tb_str,
                "operation": operation,
                "context_state": self._get_context_state(context),
            },
        )

    def _get_context_state(self, context: Any) -> Dict[str, Any]:
        collected = getattr(context, "collected_data", None)
        if not isinstance(collected, dict):
            collected = {}
        return {
            "has_business_type": bool(getattr(context, "business_type", None)),
            "has_owner_profile": bool(getattr(context, "owner_profile", None)),
            "collected_count": len(collected),
            "has_company_name": "company_name" in collected,
            "has_revenue": "revenue" in collected,
            "has_employees": "employees" in collected,
        }

    def create_fallback_with_error_logging(
        self, error: Exception, context: Any, operation: str = "triage processing"
    ) -> TriageDecision:
        self.log_detailed_error(error, context, operation)
        return self.generate_fallback_decision(context, error)
