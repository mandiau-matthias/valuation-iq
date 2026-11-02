"""
Foundation Step Coordinator

Handles execution of foundation steps (0-3) sequentially.
Extracted from sequential_executor.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed diagnostic logging
- Step 2 validation logic
"""

import traceback
from typing import Any, Dict, Union, TYPE_CHECKING

from src.api.routes.valuation.steps.base_step import StepInput, StepOutput, StepStatus
from src.api.schemas import ValuationRequest
from src.utils.exceptions import (
    CalculationError,
    DataQualityError,
    ValidationError,
)
from src.utils.valuation_logger import ValuationLogger

from .foundation_step_validation import Step2FoundationValidator

# Use TYPE_CHECKING to avoid circular import
if TYPE_CHECKING:
    from ..step_executor import StepExecutor

logger = ValuationLogger(__name__)


class FoundationStepCoordinator:
    """
    Coordinates foundation step execution (steps 0-3, plus Step 2.5).
    
    Responsibilities:
    - Execute steps 0-3 sequentially
    - Execute Step 2.5 (Multiple Calibration) after Step 2 if applicable
    - Handle diagnostic logging
    - Validate Step 2 results
    - Handle errors gracefully (don't break loop)
    """
    
    def __init__(self, step_executor: 'StepExecutor', logger_instance):
        """
        Initialize foundation step coordinator.
        
        Args:
            step_executor: StepExecutor instance
            logger_instance: Logger instance
        """
        self.step_executor = step_executor
        self.logger = logger_instance
        self.step2_validator = Step2FoundationValidator(logger_instance)
    
    async def execute_foundation_steps(
        self,
        steps: Dict[Union[int, float], Any],
        request: ValuationRequest,
        results: Dict[Union[int, float], StepOutput],
        context: Dict[str, Any],
    ) -> None:
        """
        Execute foundation steps (0-3) sequentially, including Step 2.5 (Multiple Calibration).
        
        Args:
            steps: Dictionary of all registered steps (int or float keys)
            request: Valuation request
            results: Results dictionary (will be updated)
            context: Execution context
        """
        # Execute steps 0-3 sequentially (foundation steps)
        # Note: Step 2.5 (Multiple Calibration) is executed after Step 2 via special handling
        for step_num in range(0, 4):
            # Diagnostic logging for Step 0
            if step_num == 0:
                self.logger.debug(
                    "🔍 DIAGNOSTIC: About to execute Step 0 (Data Quality Assessment)",
                    extra={
                        "step_number": 0,
                        "step_in_dict": 0 in steps,
                        "step_object_exists": 0 in steps and steps.get(0) is not None,
                        "step_object_type": (
                            type(steps.get(0)).__name__ if 0 in steps and steps.get(0) else None
                        ),
                        "has_request": request is not None,
                        "request_type": type(request).__name__ if request else None,
                        "correlation_id": context.get("correlation_id"),
                    },
                )
            
            # Diagnostic logging for Step 2
            if step_num == 2:
                self.logger.debug(
                    "🔍 DIAGNOSTIC: About to execute Step 2",
                    extra={
                        "step_in_dict": step_num in steps,
                        "step_object_exists": steps.get(step_num) is not None,
                        "step_object_type": (
                            type(steps.get(step_num)).__name__ if steps.get(step_num) else None
                        ),
                        "correlation_id": context.get("correlation_id"),
                    },
                )
            
            step = steps.get(step_num)
            
            # Logging before Step 0 execution
            if step_num == 0:
                self.logger.debug(
                    "🔍 DIAGNOSTIC: Step 0 execute() method about to be called",
                    extra={
                        "step_number": 0,
                        "step_name": step.step_name if step else None,
                        "step_class": step.__class__.__name__ if step else None,
                        "has_execute_method": hasattr(step, "execute") if step else False,
                        "correlation_id": context.get("correlation_id"),
                    },
                )
            
            if not step:
                # Enhanced logging for Step 2 if not found
                if step_num == 2:
                    self.logger.error(
                        "❌ CRITICAL: Step 2 not found in steps dictionary!",
                        extra={
                            "step_number": step_num,
                            "all_registered_steps": list(steps.keys()),
                            "step_2_in_steps": 2 in steps,
                            "correlation_id": context.get("correlation_id"),
                        },
                    )
                self.logger.warning(
                    f"⚠️ Step {step_num} not registered, skipping",
                    extra={"step_number": step_num},
                )
                continue
            
            # Log dependency status before Step 2 execution
            if step_num == 2:
                self.logger.debug(
                    "🔍 DIAGNOSTIC: Pre-Step 2 dependency check",
                    extra={
                        "step_0_exists": 0 in results,
                        "step_0_status": (
                            results[0].status.value
                            if 0 in results and hasattr(results[0], "status")
                            and hasattr(results[0].status, "value")
                            else str(results[0].status)
                            if 0 in results and hasattr(results[0], "status")
                            else None
                        ),
                        "step_0_completed": (
                            0 in results and results[0].status == StepStatus.COMPLETED
                            if 0 in results
                            else False
                        ),
                        "step_1_exists": 1 in results,
                        "step_1_status": (
                            results[1].status.value
                            if 1 in results and hasattr(results[1], "status")
                            and hasattr(results[1].status, "value")
                            else str(results[1].status)
                            if 1 in results and hasattr(results[1], "status")
                            else None
                        ),
                        "step_1_completed": (
                            1 in results and results[1].status == StepStatus.COMPLETED
                            if 1 in results
                            else False
                        ),
                        "all_completed_steps": [
                            k
                            for k, v in results.items()
                            if hasattr(v, "status") and v.status == StepStatus.COMPLETED
                        ],
                        "correlation_id": context.get("correlation_id"),
                    },
                )
            
            # Execute step with error handling
            try:
                output = await self.step_executor.execute(step, request, results, context)
                
                # Special validation for Step 2
                if step_num == 2:
                    output = self.step2_validator.validate_output(output, step, context)
                
                results[step_num] = output
                
                # Post-execution validation for Step 2
                if step_num == 2:
                    self.step2_validator.validate_storage(output, context)
                    
                    # Execute Step 2.5 (Multiple Calibration) after Step 2 completes
                    await self._execute_step_2_5(steps, request, results, context)
                    # Execute Step 2.7 (SDE Calculation) for micro/small owner-operated businesses
                    await self._execute_step_2_7(steps, request, results, context)
            
            except (
                CalculationError,
                ValidationError,
                DataQualityError,
                ValueError,
                TypeError,
                AttributeError,
            ) as e:
                self._handle_foundation_step_error(
                    step_num, step, e, results, context
                )
            
            # Don't break loop on failure - allow subsequent steps to attempt execution
            if step_num in results and results[step_num].status == StepStatus.FAILED:
                if step_num == 0:
                    self.logger.error(
                        "❌ CRITICAL: Step 0 (Data Quality Assessment) failed",
                        extra={
                            "step_number": 0,
                            "step_name": step.step_name,
                            "error": results[step_num].error,
                            "error_type": (
                                results[step_num].metadata.get("exception_type")
                                if hasattr(results[step_num], "metadata") and results[step_num].metadata
                                else None
                            ),
                            "note": "Loop will continue to attempt Steps 1, 2, 3 (they will be skipped due to missing Step 0 dependency)",
                            "correlation_id": context.get("correlation_id"),
                        },
                    )
                else:
                    self.logger.error(
                        f"❌ Step {step_num} failed",
                        extra={
                            "step_number": step_num,
                            "step_name": step.step_name,
                            "error": results[step_num].error,
                            "error_type": (
                                results[step_num].metadata.get("exception_type")
                                if hasattr(results[step_num], "metadata") and results[step_num].metadata
                                else None
                            ),
                            "note": "Loop will continue to attempt subsequent steps",
                            "correlation_id": (
                                context.get("correlation_id") if step_num == 2 else None
                            ),
                        },
                    )
        
        # Log summary of foundation steps execution
        self.logger.debug(
            "🔍 DIAGNOSTIC: Foundation steps (0-3) execution complete",
            extra={
                "step_0_status": (
                    results[0].status.value
                    if 0 in results and hasattr(results[0], "status")
                    else "missing"
                ),
                "step_1_status": (
                    results[1].status.value
                    if 1 in results and hasattr(results[1], "status")
                    else "missing"
                ),
                "step_2_status": (
                    results[2].status.value
                    if 2 in results and hasattr(results[2], "status")
                    else "missing"
                ),
                "step_3_status": (
                    results[3].status.value
                    if 3 in results and hasattr(results[3], "status")
                    else "missing"
                ),
                "all_foundation_steps": list(results.keys()),
                "completed_foundation_steps": [
                    k
                    for k in [0, 1, 2, 3]
                    if k in results
                    and hasattr(results[k], "status")
                    and results[k].status == StepStatus.COMPLETED
                ],
                "failed_foundation_steps": [
                    k
                    for k in [0, 1, 2, 3]
                    if k in results
                    and hasattr(results[k], "status")
                    and results[k].status == StepStatus.FAILED
                ],
                "skipped_foundation_steps": [
                    k
                    for k in [0, 1, 2, 3]
                    if k in results
                    and hasattr(results[k], "status")
                    and results[k].status == StepStatus.SKIPPED
                ],
                "correlation_id": context.get("correlation_id"),
            },
        )
    
    
    
    def _handle_foundation_step_error(
        self,
        step_num: int,
        step: Any,
        error: Exception,
        results: Dict[int, StepOutput],
        context: Dict[str, Any],
    ) -> None:
        """
        Handle errors during foundation step execution.
        
        Args:
            step_num: Step number
            step: Step object
            error: Exception that occurred
            results: Results dictionary (will be updated)
            context: Execution context
        """
        # Enhanced error logging for Step 0 (most critical)
        if step_num == 0:
            self.logger.error(
                "❌ CRITICAL: Exception executing Step 0 (Data Quality Assessment)",
                extra={
                    "step_number": 0,
                    "step_name": step.step_name if step else "Unknown",
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "error_traceback": traceback.format_exc(),
                    "correlation_id": context.get("correlation_id"),
                },
                exc_info=True,
            )
        # Enhanced error logging for Step 2
        elif step_num == 2:
            # Try to capture any partial result that might exist
            partial_result = None
            partial_result_keys = []
            try:
                # Check if there's a partial result in the exception context
                if hasattr(error, "__traceback__"):
                    import sys
                    
                    tb = sys.exc_info()[2]
                    # Try to extract any local variables from the traceback
                    while tb:
                        if "result" in tb.tb_frame.f_locals:
                            partial_result = tb.tb_frame.f_locals.get("result")
                            if isinstance(partial_result, dict):
                                partial_result_keys = list(partial_result.keys())
                            break
                        tb = tb.tb_next
            except (ValueError, TypeError, AttributeError, KeyError):
                pass  # Ignore errors in diagnostic extraction
            
            self.logger.error(
                "❌ CRITICAL: Exception executing Step 2",
                extra={
                    "step_number": 2,
                    "step_name": step.step_name if step else "Unknown",
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "correlation_id": (
                        context.get("correlation_id") if context else None
                    ),
                    "has_partial_result": partial_result is not None,
                    "partial_result_keys": partial_result_keys,
                    "partial_result_size": (
                        len(partial_result) if isinstance(partial_result, dict) else 0
                    ),
                    "stack_trace_available": hasattr(error, "__traceback__"),
                },
                exc_info=True,
            )
        else:
            self.logger.error(
                f"❌ CRITICAL: Exception executing step {step_num}",
                extra={
                    "step_number": step_num,
                    "step_name": step.step_name if step else "Unknown",
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                },
                exc_info=True,
            )
        
        # Don't fail silently - create failed StepOutput
        failed_output = StepOutput(
            step_number=step_num,
            step_name=step.step_name if step else "Unknown",
            status=StepStatus.FAILED,
            result={},
            error=str(error),
            metadata={
                "exception_type": type(error).__name__,
                "exception_message": str(error),
                "exception_traceback": traceback.format_exc(),
            },
        )
        results[step_num] = failed_output
        
        # Log result preservation status
        correlation_id = context.get("correlation_id") if context else None
        self.logger.warning(
            f"⚠️ [DIAG-EXCEPTION] Step {step_num} result lost due to exception",
            extra={
                "step_number": step_num,
                "step_name": step.step_name if step else "Unknown",
                "correlation_id": correlation_id,
                "operation": "exception_result_lost",
                "result_preserved": False,
                "result_dict_exists": False,
                "result_dict_keys": [],
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )
    
    async def _execute_step_2_5(
        self,
        steps: Dict[Union[int, float], Any],
        request: ValuationRequest,
        results: Dict[Union[int, float], StepOutput],
        context: Dict[str, Any],
    ) -> None:
        """
        Execute Step 2.5 (Multiple Calibration) after Step 2 completes.
        
        Step 2.5 is a special "half-step" that:
        - Runs only if Step 2 (Industry Benchmarking) completed successfully
        - Calibrates the base multiple for quality factors and SME adjustments
        - Critical for bank-grade valuations per ASA BVS-III
        
        Args:
            steps: Dictionary of all registered steps (int or float keys)
            request: Valuation request
            results: Results dictionary (will be updated with Step 2.5 result if executed)
            context: Execution context
        """
        step_2_5 = steps.get(2.5)
        
        if not step_2_5:
            self.logger.debug(
                "ℹ️ Step 2.5 not registered, skipping normalization",
                extra={
                    "step_number": 2.5,
                    "all_registered_steps": list(steps.keys()),
                    "correlation_id": context.get("correlation_id"),
                },
            )
            return
        
        # Check if Step 2.5 should execute
        step_input = StepInput(request=request, previous_results=results)
        should_run = step_2_5.should_execute(step_input)
        
        self.logger.debug(
            "🔍 DIAGNOSTIC: Step 2.5 should_execute check",
            extra={
                "step_number": 2.5,
                "step_name": "Multiple Calibration",
                "should_execute": should_run,
                "step_2_completed": 2 in results and results[2].status == StepStatus.COMPLETED,
                "has_historical_data": bool(getattr(request, "historical_years_data", None)),
                "correlation_id": context.get("correlation_id"),
            },
        )
        
        if not should_run:
            self.logger.info(
                "ℹ️ Step 2.5 skipped per should_execute() logic",
                extra={
                    "step_number": 2.5,
                    "skip_reason": "Conditions not met (see should_execute method)",
                    "correlation_id": context.get("correlation_id"),
                },
            )
            return
        
        # Execute Step 2.5
        try:
            self.logger.debug(
                "🔍 Executing Step 2.5: Multiple Calibration",
                extra={
                    "step_number": 2.5,
                    "step_name": step_2_5.step_name,
                    "correlation_id": context.get("correlation_id"),
                },
            )
            
            output = await self.step_executor.execute(step_2_5, request, results, context)
            results[2.5] = output
            
            self.logger.debug(
                "✅ Step 2.5 completed successfully",
                extra={
                    "step_number": 2.5,
                    "status": output.status.value if hasattr(output, "status") else "unknown",
                    "has_result": bool(output.result if hasattr(output, "result") else False),
                    "normalized_ebitda": (
                        output.result.get("normalized_ebitda")
                        if hasattr(output, "result") and isinstance(output.result, dict)
                        else None
                    ),
                    "correlation_id": context.get("correlation_id"),
                },
            )
        
        except Exception as e:
            self.logger.error(
                "❌ Step 2.5 (Multiple Calibration) failed",
                extra={
                    "step_number": 2.5,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "correlation_id": context.get("correlation_id"),
                },
                exc_info=True,
            )
            
            # Create failed output
            failed_output = StepOutput(
                step_number=2.5,
                step_name="Multiple Calibration",
                status=StepStatus.FAILED,
                result={},
                error=str(e),
                metadata={
                    "exception_type": type(e).__name__,
                    "exception_message": str(e),
                },
            )
            results[2.5] = failed_output

    async def _execute_step_2_7(
        self,
        steps: Dict[Union[int, float], Any],
        request: ValuationRequest,
        results: Dict[Union[int, float], StepOutput],
        context: Dict[str, Any],
    ) -> None:
        """
        Execute Step 2.7 (SDE Calculation) after Step 2.5 (Multiple Calibration) completes.
        
        SDE is the standard methodology for micro/small owner-operated businesses.
        Step 11 blends SDE valuation with EBITDA valuation when revenue < EUR 2M.
        """
        step_2_7 = steps.get(2.7)
        
        if not step_2_7:
            self.logger.debug(
                "ℹ️ Step 2.7 not registered, skipping SDE calculation",
                extra={
                    "step_number": 2.7,
                    "all_registered_steps": list(steps.keys()),
                    "correlation_id": context.get("correlation_id"),
                },
            )
            return
        
        step_input = StepInput(request=request, previous_results=results)
        should_run = step_2_7.should_execute(step_input)
        
        if not should_run:
            self.logger.debug(
                "ℹ️ Step 2.7 skipped per should_execute() (SDE not appropriate)",
                extra={
                    "step_number": 2.7,
                    "correlation_id": context.get("correlation_id"),
                },
            )
            return
        
        try:
            self.logger.debug(
                "🔍 Executing Step 2.7: SDE Calculation",
                extra={
                    "step_number": 2.7,
                    "step_name": step_2_7.step_name,
                    "correlation_id": context.get("correlation_id"),
                },
            )
            
            output = await self.step_executor.execute(step_2_7, request, results, context)
            results[2.7] = output
            
            self.logger.debug(
                "✅ Step 2.7 completed",
                extra={
                    "step_number": 2.7,
                    "status": output.status.value if hasattr(output, "status") else "unknown",
                    "has_sde_valuation": bool(
                        output.result.get("sde_valuation")
                        if (hasattr(output, "result") and isinstance(output.result, dict))
                        else False
                    ),
                    "correlation_id": context.get("correlation_id"),
                },
            )
        
        except Exception as e:
            self.logger.error(
                "❌ Step 2.7 (SDE Calculation) failed",
                extra={
                    "step_number": 2.7,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "correlation_id": context.get("correlation_id"),
                },
                exc_info=True,
            )
            
            failed_output = StepOutput(
                step_number=2.7,
                step_name="SDE Calculation",
                status=StepStatus.FAILED,
                result={},
                error=str(e),
                metadata={
                    "exception_type": type(e).__name__,
                    "exception_message": str(e),
                },
            )
            results[2.7] = failed_output
