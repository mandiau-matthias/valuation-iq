"""
Step 5 Error Handler

Handles error scenarios and fallback logic for Step 5.
"""

from decimal import Decimal
from typing import Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class Step5ErrorHandler:
    """Handles error scenarios and fallback logic."""

    def __init__(self, step_name: str):
        """
        Initialize the error handler.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name

    def handle_step1_missing(self, request: object, available_steps: list) -> Optional[StepOutput]:
        """
        Handle missing Step 1 results with fallback to request data.

        Args:
            request: The valuation request
            available_steps: List of available step numbers

        Returns:
            StepOutput with FAILED status if no fallback available, None if fallback successful
        """
        logger.warning(
            "⚠️ Step 5: Step 1 results not available, attempting fallback from request",
            extra={"step_number": 5, "available_steps": available_steps, "required_step": 1},
        )

        # Try to get revenue from request directly
        revenue_from_request = None
        if hasattr(request, "current_year_data") and request.current_year_data:
            revenue_from_request = getattr(request.current_year_data, "revenue", None)

        if revenue_from_request and revenue_from_request > 0:
            logger.info(
                "✅ Step 5: Using revenue from request as fallback",
                extra={"revenue": revenue_from_request},
            )
            return None  # Fallback successful, return None to continue

        logger.error(
            "❌ Step 5 failed: Step 1 results not available and revenue not found in request",
            extra={
                "step_number": 5,
                "available_steps": available_steps,
                "revenue_from_request": revenue_from_request,
            },
        )
        return StepOutput(
            step_number=5,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error="Step 1 results not available and revenue not found in request",
        )

    def handle_no_ev_source(
        self, available_steps: list, step4_available: bool, step3_available: bool
    ) -> StepOutput:
        """
        Handle case where no valid EV source found.

        Args:
            available_steps: List of available step numbers
            step4_available: Whether Step 4 is available
            step3_available: Whether Step 3 is available

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 5 failed: No valid EV source found",
            extra={
                "step_number": 5,
                "available_steps": available_steps,
                "required_steps": [3, 4],
                "step4_available": step4_available,
                "step3_available": step3_available,
            },
        )
        return StepOutput(
            step_number=5,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error="No valid EV source found from Steps 3-4. Step 3 (Base EV) is required.",
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
            "❌ Step 5 failed: Invalid revenue",
            extra={"step_number": 5, "revenue": revenue, "validation": "Revenue must be positive"},
        )
        return StepOutput(
            step_number=5,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error=f"Invalid revenue: {revenue}",
        )

    def handle_step3_missing_for_metric(self, available_steps: list) -> StepOutput:
        """
        Handle missing Step 3 result for metric value.

        Args:
            available_steps: List of available step numbers

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 5 failed: Step 3 result not available for metric_value",
            extra={"step_number": 5, "available_steps": available_steps},
        )
        return StepOutput(
            step_number=5,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error="Step 3 result not available for metric_value",
        )

    def handle_invalid_multiple_or_metric(
        self, current_multiple_mid: Decimal, metric_value: Decimal, ev_source_step: int
    ) -> StepOutput:
        """
        Handle invalid multiple or metric.

        Args:
            current_multiple_mid: Current multiple (mid)
            metric_value: Metric value
            ev_source_step: Source step number

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            f"❌ Step 5 failed: Invalid multiple ({current_multiple_mid}) or metric ({metric_value})",
            extra={
                "step_number": 5,
                "ev_source_step": ev_source_step,
                "current_multiple_mid": current_multiple_mid,
                "metric_value": metric_value,
            },
        )
        return StepOutput(
            step_number=5,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error=f"Invalid multiple ({current_multiple_mid}) or metric ({metric_value}) from Step {ev_source_step}",
        )
