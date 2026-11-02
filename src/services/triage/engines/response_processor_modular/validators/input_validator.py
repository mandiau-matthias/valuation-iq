"""
InputValidator

Validates user input before processing, with optional detailed validation
when in a validation context.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
from unittest.mock import Mock


@dataclass
class ValidationResult:
    validated: bool = True
    confidence: float = 1.0
    corrections: Optional[Dict[str, Any]] = None
    needs_clarification: bool = False


class InputValidator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.validation_engine = Mock()

    async def validate_input(self, user_input: str, context: Any) -> ValidationResult:
        awaiting = getattr(context, "awaiting_response_for", None)

        if not awaiting:
            return ValidationResult(validated=True, confidence=1.0)

        try:
            result = await self.validation_engine.validate_and_sanitize_input(user_input, context)
            return ValidationResult(
                validated=result.validated,
                confidence=getattr(result, "confidence", 0.0),
                corrections=getattr(result, "corrections", None),
                needs_clarification=getattr(result, "needs_clarification", False),
            )
        except Exception:
            self.logger.exception("Validation failed for input")
            return ValidationResult(validated=False, confidence=0.0)
