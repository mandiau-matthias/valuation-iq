"""
Step 8 Error Handler

Handles error scenarios and fallback logic for Step 8.
"""

from typing import Optional

from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class Step8ErrorHandler:
    """Handles error scenarios and fallback logic."""

    def __init__(self, step_name: str):
        """
        Initialize the error handler.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name

    def handle_missing_step7(
        self, step7_status: Optional[str], available_steps: list
    ) -> StepOutput:
        """
        Handle missing or incomplete Step 7.

        Args:
            step7_status: Step 7 status
            available_steps: List of available step numbers

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 8 failed: Step 7 not completed",
            extra={
                "step_number": 8,
                "step7_status": step7_status,
                "available_steps": available_steps,
            },
        )
        return StepOutput(
            step_number=8,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error="Step 7 (EV to Equity Conversion) not completed",
        )
