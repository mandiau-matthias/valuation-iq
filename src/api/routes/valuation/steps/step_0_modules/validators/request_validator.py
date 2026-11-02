"""
Request Validator for Step 0 Data Quality

Validates request extraction and basic structure.
"""

from typing import Optional

from src.api.schemas import ValuationRequest
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RequestValidator:
    """
    Validates request extraction and basic structure.
    """

    def __init__(self):
        """Initialize the request validator."""
        pass

    def extract_and_validate_request(self, input_data) -> Optional[ValuationRequest]:
        """
        Extract and validate request from input_data.

        Args:
            input_data: The input data containing the request

        Returns:
            The validated request, or None if validation fails
        """
        # CRITICAL FIX: Validate request exists
        try:
            request = input_data.request
        except AttributeError as e:
            logger.error(
                "❌ CRITICAL: Step 0 input_data.request missing",
                extra={
                    "step_number": 0,
                    "error": str(e),
                    "input_data_attrs": dir(input_data) if input_data else [],
                },
                exc_info=True,
            )
            return None

        if not request:
            logger.error("❌ CRITICAL: Step 0 request is None", extra={"step_number": 0})
            return None

        return request
