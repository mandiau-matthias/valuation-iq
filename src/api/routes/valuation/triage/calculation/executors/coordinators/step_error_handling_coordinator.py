"""
Step Error Handling Coordinator

Handles error handling logic for step execution.
Extracted from step_executor.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- Step 11 fallback guarantee
"""

import time
from typing import Any, Dict

from src.api.routes.valuation.steps.base_step import CalculationStep, StepOutput, StepStatus
from src.api.schemas import ValuationRequest
from src.utils.exceptions import (
    CalculationError,
    DataQualityError,
    ValidationError,
)
from src.utils.valuation_logger import ValuationLogger

from ....business_type_triage import BusinessTypeTriageEngine
from ...handlers.fallback_handler import FallbackHandler

logger = ValuationLogger(__name__)


class StepErrorHandlingCoordinator:
    """
    Coordinates error handling logic for step execution.
    
    Responsibilities:
    - Handle domain exceptions
    - Log errors with context
    - Generate fallback for Step 11
    - Return appropriate StepOutput for failures
    """
    
    def __init__(
        self,
        logger_instance,
        business_type_triage: BusinessTypeTriageEngine,
        fallback_handler: FallbackHandler,
    ):
        """
        Initialize step error handling coordinator.
        
        Args:
            logger_instance: Logger instance
            business_type_triage: BusinessTypeTriageEngine instance
            fallback_handler: FallbackHandler instance
        """
        self.logger = logger_instance
        self.business_type_triage = business_type_triage
        self.fallback_handler = fallback_handler
    
    def handle_step_error(
        self,
        step: CalculationStep,
        request: ValuationRequest,
        previous_results: Dict[int, StepOutput],
        context: Dict[str, Any],
        error: Exception,
        step_start: float,
    ) -> StepOutput:
        """
        Handle error during step execution.
        
        Args:
            step: The step that failed
            request: The valuation request
            previous_results: Results from previous steps
            context: Execution context
            error: The exception that occurred
            step_start: Step start time (for execution time calculation)
            
        Returns:
            StepOutput with FAILED status or fallback for Step 11
        """
        execution_time = (time.time() - step_start) * 1000
        correlation_id = context.get("correlation_id") if context else None
        
        # Get business category for error logging
        business_category = "unknown"
        try:
            business_category = self.business_type_triage.get_business_type_category(
                getattr(request, "business_type_id", None),
                getattr(request, "business_model", None),
                getattr(request, "industry", None),
                category_id=getattr(request, "category_id", None),
            ).value
        except (ValueError, TypeError, AttributeError, KeyError):
            pass  # Don't fail error logging if category lookup fails
        
        # Enhanced exception handler logging
        import traceback
        
        error_traceback = traceback.format_exc()
        
        # Check if there's a result dict that was preserved
        result_dict_exists = False
        result_dict_keys = []
        result_dict_size = 0
        try:
            # Try to get result from local scope if it exists
            if "result" in locals() and isinstance(locals()["result"], dict):
                result_dict_exists = True
                result_dict_keys = list(locals()["result"].keys())
                result_dict_size = len(locals()["result"])
        except (ValueError, TypeError, AttributeError, KeyError):
            pass
        
        self.logger.error(
            f"❌ [DIAG-EXCEPTION] Step {step.step_number} failed with error: {error}",
            extra={
                "step_name": step.step_name,
                "step_number": step.step_number,
                "correlation_id": correlation_id,
                "operation": "exception_handler",
                "error": str(error),
                "error_type": type(error).__name__,
                "error_traceback": error_traceback,
                "business_category": business_category,
                "execution_time_ms": execution_time,
                "result_dict_exists": result_dict_exists,
                "result_dict_keys": result_dict_keys,
                "result_dict_size": result_dict_size,
                "result_preserved": result_dict_exists and result_dict_size > 0,
                "company": request.company_name,
                "execution_time_ms": round(execution_time, 2),
            },
            exc_info=True,
        )
        
        # CRITICAL: For Step 11, never return FAILED - always use fallback
        if step.step_number == 11:
            self.logger.warning(
                "⚠️ Step 11 raised exception in execute, using fallback",
                extra={"error": str(error), "error_type": type(error).__name__},
            )
            # Generate fallback result instead of returning FAILED
            return self.fallback_handler.generate_step11_fallback(
                previous_results, request, context
            )
        
        return StepOutput(
            step_number=step.step_number,
            step_name=step.step_name,
            status=StepStatus.FAILED,
            result={},
            metadata={"error_type": type(error).__name__, "business_category": business_category},
            error=str(error),
            execution_time_ms=round(execution_time, 2),
        )

