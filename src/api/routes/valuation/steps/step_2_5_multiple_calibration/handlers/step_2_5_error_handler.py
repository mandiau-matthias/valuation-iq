"""
Step 2.5 Error Handler

Handles errors and edge cases for EBITDA normalization.
"""

from typing import List, Optional

from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus

logger = get_logger(__name__)


class Step25ErrorHandler:
    """Handles errors for Step 2.5."""
    
    def __init__(self, step_name: str):
        """Initialize error handler with step name."""
        self.step_name = step_name
    
    def handle_missing_steps(
        self,
        has_step1: bool,
        has_step2: bool,
        available_steps: List[int]
    ) -> StepOutput:
        """
        Handle missing dependency steps.
        
        Args:
            has_step1: Whether Step 1 is available
            has_step2: Whether Step 2 is available
            available_steps: List of available step numbers
            
        Returns:
            Failed StepOutput
        """
        missing = []
        if not has_step1:
            missing.append("Step 1 (Input Data)")
        if not has_step2:
            missing.append("Step 2 (Benchmarking)")
        
        error_msg = f"Missing dependencies: {', '.join(missing)}"
        
        logger.error(
            f"❌ Step 2.5 failed: {error_msg}",
            extra={
                "step_number": 2.5,
                "available_steps": available_steps,
                "has_step1": has_step1,
                "has_step2": has_step2,
            }
        )
        
        return StepOutput(
            step_number=2,
            step_name=self.step_name,
            status=StepStatus.FAILED,
            result={
                "error": error_msg,
                "normalized_ebitda": None,
                "fallback_mode": True,
            },
            metadata={"error_type": "missing_dependencies"}
        )
    
    def handle_invalid_data(
        self,
        reason: str,
        reported_ebitda: Optional[float] = None,
        revenue: Optional[float] = None
    ) -> StepOutput:
        """
        Handle invalid input data.
        
        Args:
            reason: Reason for invalid data
            reported_ebitda: Reported EBITDA (if available)
            revenue: Revenue (if available)
            
        Returns:
            Failed StepOutput with fallback
        """
        logger.error(
            f"❌ Step 2.5 invalid data: {reason}",
            extra={
                "step_number": 2.5,
                "reason": reason,
                "reported_ebitda": reported_ebitda,
                "revenue": revenue,
            }
        )
        
        # Return fallback: use reported EBITDA (no normalization)
        return StepOutput(
            step_number=2,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,  # Don't fail the pipeline
            result={
                "normalized_ebitda": reported_ebitda,
                "reported_ebitda": reported_ebitda,
                "total_adjustments": 0,
                "adjustment_percentage": 0,
                "adjustments": [],
                "fallback_mode": True,
                "fallback_reason": reason,
            },
            metadata={"error_type": "invalid_data", "fallback_used": True}
        )

