"""
Fallback Handler for Step 0 Data Quality

Handles creation of fallback StepOutput when execution fails.
"""

from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class FallbackHandler:
    """Handles fallback StepOutput creation for Step 0."""

    def __init__(self, step_name: str):
        """
        Initialize the fallback handler.

        Args:
            step_name: The name of the step (e.g., "Data Quality Assessment")
        """
        self.step_name = step_name

    def create_fallback_assessment(self, step_number: int = 0) -> dict:
        """
        Create a fallback quality assessment dictionary.

        Args:
            step_number: The step number (default: 0)

        Returns:
            Fallback quality assessment dictionary
        """
        logger.info(
            "🔧 Step 0: Creating fallback assessment",
            extra={"step_number": step_number, "fallback_quality_score": 50},
        )
        return {
            "quality_score": 50,
            "dimension_scores": {
                "completeness": 10,
                "validity": 10,
                "consistency": 10,
                "accuracy": 10,
                "timeliness": 10,
            },
            "warnings": [
                {
                    "severity": "critical",
                    "message": "Quality assessment used fallback values",
                    "category": "system_error",
                }
            ],
            "recommendations": [
                "Review data quality assessment system",
                "Check data quality assessor configuration",
            ],
        }

    def create_fallback_step_output(
        self, error_message: str, error_type: str, step_number: int = 0
    ) -> StepOutput:
        """
        Create a fallback StepOutput for Step 0 when execution fails.

        This ensures Step 0 always returns a valid StepOutput with COMPLETED status,
        allowing subsequent steps to execute.

        Args:
            error_message: The error message
            error_type: The type of error (e.g., 'AttributeError', 'KeyError')
            step_number: The step number (default: 0)

        Returns:
            StepOutput with fallback values
        """
        # BANK-GRADE: Structured logging for fallback creation
        logger.info(
            "🔧 Step 0: Creating fallback StepOutput",
            extra={
                "step_number": step_number,
                "error_type": error_type,
                "error_message": error_message,
                "fallback_quality_score": 50,
            },
        )

        output = StepOutput(
            step_number=step_number,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,  # CRITICAL: Always COMPLETED, never FAILED
            result={
                "quality_score": 50,  # Default score - allows execution to continue
                "dcf_eligible": False,
                "multiples_method": "primary",
                "dimension_scores": {
                    "completeness": 10,
                    "validity": 10,
                    "consistency": 10,
                    "accuracy": 10,
                    "timeliness": 10,
                },
                "warnings": [
                    {
                        "severity": "critical",
                        "message": f"Step 0 execution failed ({error_type}): {error_message}",
                        "category": "system_error",
                    }
                ],
                "recommendations": [
                    "Review Step 0 execution logic",
                    "Check data quality assessor configuration",
                ],
            },
            metadata={
                "fallback_mode": True,
                "error_type": error_type,
                "error_message": error_message,
                "note": "Step 0 completed with fallback data to allow execution to continue",
            },
        )

        # BANK-GRADE: Structured logging for fallback return
        logger.debug(
            "Step 0: Returning fallback StepOutput",
            extra={
                "step_number": step_number,
                "status": output.status.value,
                "fallback_mode": True,
            },
        )

        return output
