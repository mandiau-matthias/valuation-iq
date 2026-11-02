"""
Step 11 Error Handler

Handles error scenarios and fallback recovery logic for Step 11.
"""

import traceback
from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class Step11ErrorHandler:
    """Handles error scenarios and fallback recovery logic."""

    def __init__(self, step_name: str):
        """
        Initialize the error handler.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name

    def handle_execution_exception(
        self, e: Exception, request: any, input_data: any, range_calculator: any
    ) -> StepOutput:
        """
        Handle exceptions during Step 11 execution.

        Args:
            e: Exception that occurred
            request: Valuation request
            input_data: StepInput with previous results
            range_calculator: RangeCalculator instance for fallback

        Returns:
            StepOutput with fallback result or minimal result
        """
        error_traceback = traceback.format_exc()
        logger.error(
            "❌ Step 11: Exception during execution",
            extra={
                "step_number": 11,
                "step_name": self.step_name,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "error_traceback": error_traceback,
                "company_name": getattr(request, "company_name", "N/A"),
                "available_previous_steps": (
                    list(input_data.previous_results.keys()) if input_data.previous_results else []
                ),
                "step10_status": (
                    getattr(input_data.previous_results.get(10), "status", None).value
                    if input_data.previous_results.get(10)
                    and hasattr(input_data.previous_results.get(10), "status")
                    else "not_found"
                ),
                "step10_error": (
                    getattr(input_data.previous_results.get(10), "error", None)
                    if input_data.previous_results.get(10)
                    else None
                ),
            },
        )

        # CRITICAL: Even if exception occurs, try to return a valid result using fallback
        logger.warning(
            "⚠️ Step 11 exception occurred, attempting fallback recovery",
            extra={"step_number": 11, "error_type": type(e).__name__, "error_message": str(e)},
        )

        # Try fallback recovery
        try:
            return self.generate_fallback_result(
                range_calculator, input_data.previous_results, request
            )
        except Exception as fallback_error:
            logger.error(
                "❌ Step 11 fallback also failed",
                extra={"step_number": 11, "fallback_error": str(fallback_error)},
            )
            # Last resort: return minimal result
            return self.generate_minimal_result(e)

    def generate_fallback_result(
        self, range_calculator: any, previous_results: Dict[int, Any], request: any
    ) -> StepOutput:
        """
        Generate fallback result using range calculator.

        Args:
            range_calculator: RangeCalculator instance
            previous_results: Dictionary of previous step results
            request: Valuation request

        Returns:
            StepOutput with fallback result
        """
        valuation_low, valuation_mid, valuation_high = range_calculator.generate_fallback_range(
            previous_results, request
        )

        if valuation_mid > 0:
            # Return a minimal valid result
            return StepOutput(
                step_number=11,
                step_name=self.step_name,
                status=StepStatus.COMPLETED,
                result={
                    "valuation_low": valuation_low,
                    "valuation_mid": valuation_mid,
                    "valuation_high": valuation_high,
                    "confidence_score": 50,  # Default low confidence
                    "confidence_level": "LOW",
                    "methodology_statement": "Valuation completed using fallback logic due to processing error",
                    "fallback_mode": True,
                    "error_recovered": True,
                },
                metadata={
                    "fallback_used": True,
                    "fallback_methodology": "Confidence-based spread from Step 7/8 equity values",
                },
            )
        else:
            # Fallback failed, return minimal result
            return self.generate_minimal_result(None)

    def generate_minimal_result(self, original_error: Optional[Exception]) -> StepOutput:
        """
        Generate last resort minimal result.

        Args:
            original_error: Original exception (if any)

        Returns:
            StepOutput with minimal result
        """
        return StepOutput(
            step_number=11,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,  # Always return COMPLETED, never FAILED
            result={
                "valuation_low": Decimal("0.0"),
                "valuation_mid": Decimal("0.01"),  # Minimal non-zero
                "valuation_high": Decimal("0.01"),
                "confidence_score": 0,
                "confidence_level": "LOW",
                "methodology_statement": "Valuation could not be determined - insufficient data",
                "fallback_mode": True,
                "error_recovered": False,
            },
            metadata={
                "fallback_used": True,
                "original_error": str(original_error) if original_error else None,
                "error_type": type(original_error).__name__ if original_error else None,
                "fallback_failed": True,
            },
        )
