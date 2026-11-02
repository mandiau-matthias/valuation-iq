"""
Step 10 Error Handler

Handles error scenarios and fallback logic for Step 10.
"""

from decimal import Decimal
from typing import Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class Step10ErrorHandler:
    """Handles error scenarios and fallback logic."""

    def __init__(self, step_name: str):
        """
        Initialize the error handler.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name

    def handle_step1_missing(self) -> StepOutput:
        """
        Handle missing Step 1 results.

        Returns:
            StepOutput with FAILED status
        """
        logger.error("❌ Step 10 failed: Step 1 results not available", extra={"step_number": 10})
        return StepOutput(
            step_number=10,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error="Step 1 results not available",
        )

    def handle_no_equity_source(
        self, step8_status: Optional[str], step7_status: Optional[str]
    ) -> StepOutput:
        """
        Handle case where no equity value available from Step 8 or Step 7.

        Args:
            step8_status: Step 8 status
            step7_status: Step 7 status

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 10 failed: No equity value available from Step 8 or Step 7",
            extra={"step_number": 10, "step8_status": step8_status, "step7_status": step7_status},
        )
        return StepOutput(
            step_number=10,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error="No equity value available from Step 8 or Step 7",
        )

    def handle_invalid_revenue(self, revenue: Decimal) -> StepOutput:
        """
        Handle invalid revenue.

        Args:
            revenue: Invalid revenue value

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 10 failed: Invalid revenue",
            extra={
                "step_number": 10,
                "revenue": revenue,
                "validation_failed": "Revenue must be positive",
            },
        )
        return StepOutput(
            step_number=10,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error=f"Invalid revenue: {revenue}",
        )

    def handle_invalid_equity(self, equity_mid: Decimal) -> StepOutput:
        """
        Handle invalid equity value.

        Args:
            equity_mid: Invalid equity value

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 10 failed: Invalid equity value",
            extra={
                "step_number": 10,
                "equity_mid": equity_mid,
                "validation_failed": "Equity value must be positive",
            },
        )
        return StepOutput(
            step_number=10,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error=f"Invalid equity value: {equity_mid}",
        )

    def handle_invalid_range_ordering(
        self, equity_low: Decimal, equity_mid: Decimal, equity_high: Decimal
    ) -> StepOutput:
        """
        Handle invalid range ordering.

        Args:
            equity_low: Equity low value
            equity_mid: Equity mid value
            equity_high: Equity high value

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 10: Invalid range ordering detected",
            extra={
                "equity_low": equity_low,
                "equity_mid": equity_mid,
                "equity_high": equity_high,
                "low_lt_mid": equity_low < equity_mid,
                "mid_lt_high": equity_mid < equity_high,
            },
        )
        return StepOutput(
            step_number=10,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error=f"Invalid range ordering: low ({equity_low}) must be < mid ({equity_mid}) < high ({equity_high})",
        )

    def handle_execution_error(self, error: Exception) -> StepOutput:
        """
        Handle general execution errors.

        Args:
            error: Exception that occurred during execution

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 10 execution failed",
            extra={
                "step_number": 10,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            exc_info=True,
        )
        return StepOutput(
            step_number=10,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error=f"Step 10 execution failed: {str(error)}",
        )
