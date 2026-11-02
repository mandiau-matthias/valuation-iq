"""
Step 3 Error Handler

Handles error scenarios and fallback logic for Step 3.
"""

from decimal import Decimal
from typing import Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class Step3ErrorHandler:
    """Handles error scenarios and fallback logic."""

    def __init__(self, step_name: str):
        """
        Initialize the error handler.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name

    def handle_missing_steps(
        self, step1_available: bool, step2_available: bool, available_steps: list
    ) -> StepOutput:
        """
        Handle missing Step 1/Step 2 results.

        Args:
            step1_available: Whether Step 1 is available
            step2_available: Whether Step 2 is available
            available_steps: List of available step numbers

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 3 failed: Previous step results not available",
            extra={
                "step_number": 3,
                "step1_available": step1_available,
                "step2_available": step2_available,
                "available_steps": available_steps,
            },
        )
        return StepOutput(
            step_number=3,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error="Previous step results not available",
        )

    def handle_invalid_revenue(
        self, revenue: Decimal, primary_method: str, ebitda: Optional[Decimal]
    ) -> StepOutput:
        """
        Handle invalid revenue (return SKIPPED status for zero revenue).

        Args:
            revenue: Invalid revenue value
            primary_method: Primary method
            ebitda: EBITDA value (optional)

        Returns:
            StepOutput with SKIPPED status
        """
        logger.warning(
            f"⚠️ Step 3: Revenue is zero or negative, skipping calculation",
            extra={
                "step_number": 3,
                "revenue": revenue,
                "validation": "Revenue must be positive for EV calculation",
                "action": "returning_skipped_status",
            },
        )
        return StepOutput(
            step_number=3,
            step_name=self.step_name,
            status=StepStatus.SKIPPED,
            result={
                "enterprise_value_low": Decimal("0.0"),
                "enterprise_value_mid": Decimal("0.0"),
                "enterprise_value_high": Decimal("0.0"),
                "primary_method": primary_method,
                "skip_reason": "Revenue is zero or negative - cannot calculate enterprise value",
                "revenue": revenue,
                "ebitda": ebitda,
            },
            metadata={
                "skip_reason": "Revenue is zero or negative",
                "revenue": revenue,
                "note": "Step 3 requires positive revenue to calculate enterprise value",
            },
        )

    def handle_missing_primary_method(self) -> StepOutput:
        """
        Handle missing primary_method from Step 2.

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 3 failed: Step 2 did not provide primary_method", extra={"step_number": 3}
        )
        return StepOutput(
            step_number=3,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error="Step 2 did not provide primary_method",
        )

    def handle_no_multiples_available(
        self,
        primary_method: str,
        ev_revenue_multiple: Optional[Decimal],
        ev_ebitda_multiple: Optional[Decimal],
        fallback_attempted: bool = False,
    ) -> StepOutput:
        """
        Handle case where no multiples available from Step 2.

        Args:
            primary_method: Primary method ('EV/Revenue' or 'EV/EBITDA')
            ev_revenue_multiple: Revenue multiple from Step 2
            ev_ebitda_multiple: EBITDA multiple from Step 2
            fallback_attempted: Whether fallback was attempted

        Returns:
            StepOutput with FAILED status
        """
        error_msg = f"No multiples available from Step 2 for {primary_method} method"
        if fallback_attempted:
            error_msg += " (fallback attempted)"

        logger.error(
            f"❌ Step 3 failed: {error_msg}",
            extra={
                "step_number": 3,
                "primary_method": primary_method,
                "ev_revenue_multiple": ev_revenue_multiple,
                "ev_ebitda_multiple": ev_ebitda_multiple,
                "fallback_attempted": fallback_attempted,
            },
        )
        return StepOutput(
            step_number=3,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error=error_msg,
        )

    def handle_invalid_multiple(self, multiple: Decimal, primary_method: str) -> StepOutput:
        """
        Handle invalid multiple.

        Args:
            multiple: Invalid multiple value
            primary_method: Primary method

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            f"❌ Step 3 failed: Invalid multiple ({multiple}) for method {primary_method}",
            extra={"step_number": 3, "multiple": multiple, "primary_method": primary_method},
        )
        return StepOutput(
            step_number=3,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error=f"Invalid multiple: {multiple} for method {primary_method}",
        )
