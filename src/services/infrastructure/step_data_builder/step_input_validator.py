"""
Step Input Validator

Validates inputs for step journey building.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.interfaces.request_response_protocol import (
        ValuationRequestProtocol,
        ValuationResponseProtocol,
    )

from src.services.infrastructure.exceptions import MissingDataError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StepInputValidator:
    """Validates inputs for building step journey."""

    @staticmethod
    def validate(
        response: "ValuationResponseProtocol",
        request: "ValuationRequestProtocol",
    ) -> None:
        """
        Validate inputs for step journey building.

        Args:
            response: ValuationResponse containing transparency data
            request: Original ValuationRequest for context

        Raises:
            MissingDataError: If required inputs are missing
        """
        if not response:
            raise MissingDataError(
                "ValuationResponse is required but was None",
                missing_fields=['response']
            )
        if not request:
            raise MissingDataError(
                "ValuationRequest is required but was None",
                missing_fields=['request']
            )
        if not hasattr(response, 'company_name') or not response.company_name:
            raise MissingDataError(
                "ValuationResponse missing required field: company_name",
                missing_fields=['company_name']
            )

