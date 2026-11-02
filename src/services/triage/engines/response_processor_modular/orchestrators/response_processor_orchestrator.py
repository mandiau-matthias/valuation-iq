"""
ResponseProcessorOrchestrator

Orchestrates the modular response processing pipeline, coordinating
field extraction, validation, rejection detection, and confirmation handling.
"""

import logging
from typing import Any, Optional


class ResponseProcessorOrchestrator:
    def __init__(self, field_extractor: Any = None):
        self.field_extractor = field_extractor
        self.logger = logging.getLogger(__name__)
        self.input_validator = None
        self.rejection_detector = None
        self.confirmation_handler = None

    async def process_response(self, user_input: str, context: Any) -> Optional[Any]:
        self.logger.debug("Processing response: %s", user_input[:50])

        if self.input_validator:
            validation_result = await self.input_validator.validate_input(user_input, context)
            if not validation_result.validated:
                return validation_result

        if self.rejection_detector:
            is_rejection = self.rejection_detector.detect_rejection(user_input)
            if is_rejection:
                return {"rejected": True}

        if self.confirmation_handler:
            is_confirmed, value = self.confirmation_handler.detect_confirmation(user_input)
            if is_confirmed:
                return {"confirmed": True, "value": value}

        if self.field_extractor:
            value = await self.field_extractor.extract_field_value(user_input, context)
            return {"extracted": True, "value": value}

        return {"processed": True}
