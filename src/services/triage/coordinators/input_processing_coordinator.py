"""
Input Processing Coordinator

Handles input validation, user response processing, and event generation
for the triage conversation flow.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from src.utils.exceptions import DataValidationError


@dataclass
class ProcessingResult:
    validated: bool = False
    error_message: Optional[str] = None
    field: Optional[str] = None
    value: Any = None
    needs_clarification: bool = False
    clarification_message: Optional[str] = None


class InputProcessingCoordinator:
    def __init__(self, validation_engine=None, response_processor=None):
        self.validation_engine = validation_engine
        self.response_processor = response_processor
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def validate_input(self, input_text: str, context: Any) -> ProcessingResult:
        if not input_text or not input_text.strip():
            return ProcessingResult(validated=False, error_message="Please provide a valid input.")

        awaiting = getattr(context, "awaiting_response_for", None)
        if awaiting and self.validation_engine:
            result = await self.validation_engine.validate_and_sanitize_input(input_text, context)
            if not result.validated:
                return ProcessingResult(validated=False, error_message="Please provide valid input")
            return ProcessingResult(validated=True)

        return ProcessingResult(validated=True)

    async def process_user_response(
        self, input_text: str, field_name: str, context: Any
    ) -> ProcessingResult:
        try:
            result = await self.response_processor.process_response(input_text, field_name, context)
            return ProcessingResult(
                validated=result.validated,
                field=result.field,
                value=result.value,
                needs_clarification=getattr(result, "needs_clarification", False),
                clarification_message=getattr(result, "clarification_message", None),
            )
        except DataValidationError as e:
            return ProcessingResult(
                validated=False,
                field=field_name,
                error_message=str(e),
            )
        except Exception as e:
            self.logger.error("Unexpected error processing response: %s", e)
            return ProcessingResult(
                validated=False,
                field=field_name,
                error_message="An error occurred while processing your response.",
            )

    def determine_expected_field(self, context: Any) -> Optional[str]:
        last_asked = getattr(context, "last_asked_field", None)
        if last_asked:
            return last_asked
        awaiting = getattr(context, "awaiting_response_for", None)
        return awaiting

    def should_process_response(self, input_text: str, context: Any) -> bool:
        if not input_text or not input_text.strip():
            return False
        return self.determine_expected_field(context) is not None

    async def generate_error_event(self, message: str, session_id: str) -> Dict[str, Any]:
        return {
            "type": "error",
            "message": message,
            "session_id": session_id,
        }

    async def generate_clarification_event(
        self, message: str, field_name: str, session_id: str
    ) -> Dict[str, Any]:
        return {
            "type": "clarification_needed",
            "field": field_name,
            "message": message,
            "session_id": session_id,
        }
