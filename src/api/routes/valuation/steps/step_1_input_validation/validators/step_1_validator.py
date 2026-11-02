"""
Step 1 Validator

Validates revenue and ensures data completeness.
"""

from decimal import Decimal
from typing import Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step1Validator:
    """Validates input data for Step 1."""

    def __init__(self):
        """Initialize the validator."""
        pass

    def validate_revenue(self, revenue: Decimal, using_weighted: bool) -> None:
        """
        Validate revenue and log warnings if needed.

        Step 1 should not fail if revenue is 0 - let Step 3 handle that decision.

        Args:
            revenue: Revenue value to validate
            using_weighted: Whether weighted metrics were used
        """
        if revenue is None or revenue <= 0:
            logger.warning(
                "⚠️ Step 1: Revenue is zero or negative - downstream steps may skip calculations",
                extra={
                    "step_number": 1,
                    "revenue": revenue,
                    "using_weighted": using_weighted,
                    "validation_warning": "Revenue is zero - Step 3 will handle this appropriately",
                    "note": "Step 1 completes successfully to allow Step 3 to make the decision",
                },
            )
            # Continue execution - don't fail Step 1, let Step 3 decide what to do
