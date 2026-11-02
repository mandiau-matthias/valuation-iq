"""
EventGenerator

Generates SSE events for data collection and clarification flows.
"""

import logging
from typing import Any, Dict


class EventGenerator:
    def __init__(
        self,
        sanitizer: Any = None,
        field_display_helpers: Any = None,
        completeness_scorer: Any = None,
    ):
        self.sanitizer = sanitizer
        self.field_display_helpers = field_display_helpers
        self.completeness_scorer = completeness_scorer
        self.logger = logging.getLogger(__name__)

    def generate_clarification_event(self, result: Any, context: Any) -> Dict[str, Any]:
        return {
            "type": "clarification_needed",
            "field": result.field,
            "message": getattr(result, "clarification_message", "Please clarify"),
            "value": str(result.value) if result.value is not None else None,
            "confidence": float(result.confidence),
            "session_id": getattr(context, "session_id", None),
        }

    def generate_data_collected_event(self, result: Any, context: Any) -> Dict[str, Any]:
        return {
            "type": "data_collected",
            "field": result.field,
            "value": str(result.value) if result.value is not None else None,
            "validated": result.validated,
            "confidence": float(result.confidence),
            "session_id": getattr(context, "session_id", None),
        }
