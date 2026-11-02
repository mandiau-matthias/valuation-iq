"""
Step 6 Error Handler

Handles error scenarios and fallback logic for Step 6.
"""

from decimal import Decimal
from typing import Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class Step6ErrorHandler:
    """Handles error scenarios and fallback logic."""

    def __init__(self, step_name: str):
        """
        Initialize the error handler.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name

    def handle_no_ev_source(self, available_steps: list) -> StepOutput:
        """
        Handle case where no valid EV source found.

        Args:
            available_steps: List of available step numbers

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 6 failed: No valid EV source found",
            extra={
                "step_number": 6,
                "available_steps": available_steps,
                "required_steps": [3, 4, 5],
            },
        )
        return StepOutput(
            step_number=6,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error="No valid EV source found from steps 3-5. At least one of steps 3, 4, or 5 must complete.",
        )

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
            "⚠️ Step 6: Step 1 results not available, attempting fallback from request",
            extra={"step_number": 6, "available_steps": available_steps, "required_step": 1},
        )

        # Try to get revenue from request directly
        revenue_from_request = None
        if hasattr(request, "current_year_data") and request.current_year_data:
            revenue_from_request = getattr(request.current_year_data, "revenue", None)

        if revenue_from_request and revenue_from_request > 0:
            logger.info(
                "✅ Step 6: Using revenue from request as fallback",
                extra={"revenue": revenue_from_request},
            )
            return None  # Fallback successful, return None to continue

        logger.error(
            "❌ Step 6 failed: Step 1 results not available and revenue not found in request",
            extra={
                "step_number": 6,
                "available_steps": available_steps,
                "revenue_from_request": revenue_from_request,
            },
        )
        return StepOutput(
            step_number=6,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error="Step 1 results not available and revenue not found in request",
        )

    def handle_invalid_multiple_or_metric(
        self, current_multiple_mid: Decimal, metric_value: Decimal, base_step: int
    ) -> StepOutput:
        """
        Handle invalid multiple or metric.

        Args:
            current_multiple_mid: Current multiple (mid)
            metric_value: Metric value
            base_step: Base step number

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            f"❌ Step 6 failed: Invalid multiple ({current_multiple_mid}) or metric ({metric_value})",
            extra={
                "step_number": 6,
                "base_step": base_step,
                "current_multiple_mid": current_multiple_mid,
                "metric_value": metric_value,
            },
        )
        return StepOutput(
            step_number=6,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error=f"Invalid multiple ({current_multiple_mid}) or metric ({metric_value}) from Step {base_step}",
        )
