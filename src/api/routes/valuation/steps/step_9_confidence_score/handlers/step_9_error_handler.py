"""
Step 9 Error Handler

Handles error scenarios and fallback logic for Step 9.
"""

from typing import Optional

from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class Step9ErrorHandler:
    """Handles error scenarios and fallback logic."""

    def __init__(self, step_name: str):
        """
        Initialize the error handler.

        Args:
            step_name: Step name for StepOutput
        """
        self.step_name = step_name

    def handle_missing_required_steps(
        self, step0_available: bool, step1_available: bool, missing_steps: list
    ) -> StepOutput:
        """
        Handle missing required Step 0 or Step 1 results.

        Args:
            step0_available: Whether Step 0 is available
            step1_available: Whether Step 1 is available
            missing_steps: List of missing step numbers

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 9 failed: Required step results not available",
            extra={
                "step_number": 9,
                "has_step0": step0_available,
                "has_step1": step1_available,
                "missing_steps": missing_steps,
            },
        )
        return StepOutput(
            step_number=9,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error="Required step results (0 or 1) not available",
        )

    def handle_missing_equity_value(
        self, step8_status: Optional[str], step7_status: Optional[str]
    ) -> StepOutput:
        """
        Handle missing equity value from Step 8 or Step 7.

        Args:
            step8_status: Step 8 status
            step7_status: Step 7 status

        Returns:
            StepOutput with FAILED status
        """
        logger.error(
            "❌ Step 9 failed: No equity value available from Step 8 or Step 7",
            extra={"step_number": 9, "step8_status": step8_status, "step7_status": step7_status},
        )
        return StepOutput(
            step_number=9,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={},
            error="No equity value available from Step 8 or Step 7",
        )
