"""
Step 2.7 Error Handler

Handles error scenarios for SDE calculation step.
"""

from src.utils.logging import get_logger
from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class Step27ErrorHandler:
    """Handles error scenarios for Step 2.7 SDE Calculation."""

    def __init__(self, step_name: str):
        """Initialize error handler."""
        self.step_name = step_name
        self.step_number = 2.7

    def handle_not_applicable(self, reason: str, revenue: float) -> StepOutput:
        """
        Handle case where SDE is not applicable for this business.
        
        Args:
            reason: Reason why SDE is not applicable
            revenue: Business revenue
            
        Returns:
            StepOutput with SKIPPED status
        """
        logger.info(
            f"⏭️ Step 2.7 (SDE) skipped: {reason}",
            extra={
                "step_number": self.step_number,
                "reason": reason,
                "revenue": revenue,
            },
        )
        
        return StepOutput(
            step_number=self.step_number,
            step_name=self.step_name,
            status=StepStatus.SKIPPED,
            execution_time_ms=0,
            result={
                "skipped": True,
                "reason": reason,
                "recommendation": "Use EBITDA multiples instead",
            },
            metadata={
                "skip_reason": reason,
                "revenue": revenue,
            },
        )

    def handle_negative_sde(self, sde: float) -> StepOutput:
        """
        Handle case where SDE is negative.
        
        Args:
            sde: Calculated SDE (negative)
            
        Returns:
            StepOutput with WARNING status
        """
        logger.warning(
            f"⚠️ Step 2.7: Negative SDE calculated: {sde}",
            extra={
                "step_number": self.step_number,
                "sde": sde,
            },
        )
        
        return StepOutput(
            step_number=self.step_number,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,
            execution_time_ms=0,
            result={
                "sde": sde,
                "sde_valuation": 0,
                "warning": "Negative SDE - business may not be viable for sale",
                "methodology": "SDE",
            },
            metadata={
                "warning": "negative_sde",
                "sde_value": sde,
            },
        )

    def handle_missing_data(self, missing_fields: list) -> StepOutput:
        """
        Handle case where required data is missing.
        
        Args:
            missing_fields: List of missing field names
            
        Returns:
            StepOutput with SKIPPED status
        """
        logger.warning(
            f"⚠️ Step 2.7: Missing required data: {missing_fields}",
            extra={
                "step_number": self.step_number,
                "missing_fields": missing_fields,
            },
        )
        
        return StepOutput(
            step_number=self.step_number,
            step_name=self.step_name,
            status=StepStatus.SKIPPED,
            execution_time_ms=0,
            result={
                "skipped": True,
                "reason": f"Missing required data: {', '.join(missing_fields)}",
            },
            metadata={
                "missing_fields": missing_fields,
            },
        )

    def handle_calculation_error(self, error: Exception) -> StepOutput:
        """
        Handle calculation errors.
        
        Args:
            error: The exception that occurred
            
        Returns:
            StepOutput with ERROR status
        """
        logger.error(
            f"❌ Step 2.7: Calculation error: {error}",
            extra={
                "step_number": self.step_number,
                "error": str(error),
                "error_type": type(error).__name__,
            },
            exc_info=True,
        )
        
        return StepOutput(
            step_number=self.step_number,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            execution_time_ms=0,
            result={
                "error": str(error),
                "error_type": type(error).__name__,
            },
            metadata={
                "error": str(error),
            },
        )
