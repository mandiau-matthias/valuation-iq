"""
Final Step Coordinator

Handles execution of final steps (7-11) sequentially.
Extracted from sequential_executor.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Step 11 fallback guarantee
- Critical step validation
"""

from typing import Any, Dict, Union

from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus
from src.api.schemas import ValuationRequest
from src.utils.exceptions import (
    CalculationError,
    DataQualityError,
    ValidationError,
)
from src.utils.valuation_logger import ValuationLogger
from typing import TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular import
if TYPE_CHECKING:
    from ..step_executor import StepExecutor
from .step11_fallback_coordinator import Step11FallbackCoordinator

logger = ValuationLogger(__name__)


class FinalStepCoordinator:
    """
    Coordinates final step execution (steps 7-11).
    
    Responsibilities:
    - Execute steps 7-11 sequentially
    - Handle critical step failures (Step 7)
    - Ensure Step 11 always completes (with fallback)
    - Handle optional steps gracefully
    """
    
    def __init__(
        self,
        step_executor: 'StepExecutor',
        step11_fallback_coordinator: Step11FallbackCoordinator,
        logger_instance,
    ):
        """
        Initialize final step coordinator.
        
        Args:
            step_executor: StepExecutor instance
            step11_fallback_coordinator: Step11FallbackCoordinator instance
            logger_instance: Logger instance
        """
        self.step_executor = step_executor
        self.step11_fallback = step11_fallback_coordinator
        self.logger = logger_instance
    
    async def execute_final_steps(
        self,
        steps: Dict[Union[int, float], Any],
        request: ValuationRequest,
        results: Dict[Union[int, float], StepOutput],
        context: Dict[str, Any],
    ) -> None:
        """
        Execute final steps (7-11) sequentially.
        
        Args:
            steps: Dictionary of all registered steps (int or float keys)
            request: Valuation request
            results: Results dictionary (will be updated)
            context: Execution context
        """
        # Execute remaining steps sequentially (7-10)
        # Step 7 depends on Step 3 (base EV) minimum, prefers Step 6
        # Step 8 (ownership adjustment) depends on Step 7 (conditional), can use Step 6 EV as fallback
        # Step 9 (confidence) depends on Step 7 minimum, prefers Step 8, can use Step 6 EV as fallback
        # Step 10 (range methodology) depends on Step 7 and Step 9 minimum, prefers Step 8, can use Step 6 EV as fallback
        # Step 11 (final synthesis) MUST always execute (moved outside loop to guarantee execution)
        
        step7_failed = False
        
        for step_num in range(7, 11):  # Execute steps 7-10 only
            step = steps.get(step_num)
            if not step:
                self.logger.warning(
                    f"⚠️ Step {step_num} not registered, skipping",
                    extra={"step_number": step_num},
                )
                continue
            
            # For Step 7, ensure Step 3 completed (required minimum)
            if step_num == 7:
                if not self._validate_step7_prerequisites(results, step):
                    step7_failed = True
                    # BANK-GRADE FIX: Set context flag so Step 11 can detect Step 7 prerequisite failure
                    # This is critical because Step 7 won't be in results if prerequisites fail,
                    # so Step 11 needs the context flag to activate Step 6 EV fallback
                    context["step7_failed"] = True
                    context["step7_failure_reason"] = "Prerequisites validation failed"
                    self.logger.warning(
                        "⚠️ Step 7 prerequisites failed, Step 11 will use Step 6 EV fallback",
                        extra={
                            "step_number": 7,
                            "step7_failed": True,
                            "failure_reason": "Prerequisites validation failed",
                            "step6_available": (
                                6 in results
                                and results[6].status == StepStatus.COMPLETED
                                and results[6].result
                                and results[6].result.get("enterprise_value_mid")
                            ),
                            "correlation_id": context.get("correlation_id"),
                            "audit_trail": {
                                "step7_prerequisites_failed": True,
                                "step7_not_executed": True,
                                "fallback_strategy": "Step 6 EV",
                            },
                        },
                    )
                    # Continue to allow Steps 8-10 to execute with Step 6 EV fallback
                    continue
            
            # Execute step
            output = await self.step_executor.execute(step, request, results, context)
            results[step_num] = output
            
            # Handle step failures with bank-grade error tracking
            if output.status == StepStatus.FAILED:
                if step_num == 7:  # Step 7 failed - mark for fallback handling
                    step7_failed = True
                    step6_available = (
                        6 in results
                        and results[6].status == StepStatus.COMPLETED
                        and results[6].result
                        and results[6].result.get("enterprise_value_mid")
                    )
                    self.logger.warning(
                        f"⚠️ Step {step_num} failed, Steps 8-10 will use Step 6 EV as fallback",
                        extra={
                            "step_number": step_num,
                            "step_name": step.step_name,
                            "error": output.error,
                            "fallback_strategy": "Step 6 EV approximation",
                            "step6_available": step6_available,
                            "step6_ev_mid": (
                                results[6].result.get("enterprise_value_mid")
                                if step6_available
                                else None
                            ),
                            "correlation_id": context.get("correlation_id"),
                            "audit_trail": {
                                "step_failed": step_num,
                                "fallback_triggered": True,
                                "fallback_source": "Step 6 EV",
                            },
                        },
                    )
                    # Continue execution - Steps 8-10 can use Step 6 EV values
                elif step_num == 8:  # Optional step (ownership adjustment)
                    self.logger.info(
                        f"⏭️ Step {step_num} (ownership adjustment) failed, continuing without it",
                        extra={"step_name": step.step_name, "error": output.error},
                    )
                    # Continue execution (Step 9/10 will use Step 7 or Step 6 as fallback)
                else:
                    self.logger.warning(
                        f"⚠️ Step {step_num} failed, continuing with warning",
                        extra={"step_name": step.step_name, "error": output.error},
                    )
                    # Continue execution for non-critical steps
        
        # CRITICAL: Step 11 MUST always execute, regardless of previous step failures
        # This is moved outside the loop to guarantee execution even if Step 7 fails
        step11 = steps.get(11)
        self.logger.debug(
            "🔍 About to execute Step 11 (Final Synthesis)",
            extra={
                "step_11_registered": step11 is not None,
                "step_11_type": type(step11).__name__ if step11 else None,
                "correlation_id": context.get("correlation_id"),
            },
        )
        if step11:
            try:
                self.logger.debug(
                    "🔍 Calling _execute_step11",
                    extra={"correlation_id": context.get("correlation_id")},
                )
                await self._execute_step11(step11, request, results, context)
                self.logger.debug(
                    "✅ _execute_step11 completed",
                    extra={"correlation_id": context.get("correlation_id")},
                )
            except Exception as e:
                self.logger.error(
                    "❌ _execute_step11 raised exception",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "correlation_id": context.get("correlation_id"),
                    },
                    exc_info=True,
                )
                # Ensure Step 11 exists via fallback even if execution fails
                self.step11_fallback.ensure_step11_exists(results, request, context)
        else:
            self.logger.error(
                "❌ Step 11 not registered, generating fallback result",
                extra={"step_number": 11},
            )
            # Ensure Step 11 exists via fallback
            self.step11_fallback.ensure_step11_exists(results, request, context)
    
    async def _execute_step11(
        self,
        step: Any,
        request: ValuationRequest,
        results: Dict[int, StepOutput],
        context: Dict[str, Any],
    ) -> None:
        """
        Execute Step 11 with fallback guarantee.
        
        Args:
            step: Step 11 object
            request: Valuation request
            results: Results dictionary (will be updated)
            context: Execution context
        """
        # BANK-GRADE: Log entry point immediately for audit trail
        self.logger.debug(
            "🚀 [STEP-11-ENTRY] _execute_step11 method called",
            extra={
                "step_name": step.step_name if hasattr(step, "step_name") else "Unknown",
                "step_type": type(step).__name__,
                "has_results": results is not None,
                "results_keys": list(results.keys()) if results else [],
                "correlation_id": context.get("correlation_id"),
            },
        )
        self.logger.debug(
            "🚀 Executing Step 11 (Final Synthesis)",
            extra={
                "step_name": step.step_name if hasattr(step, "step_name") else "Unknown",
                "correlation_id": context.get("correlation_id"),
            },
        )
        # Check Step 7 status - if failed, Step 11 should use Step 6 EV values
        # BANK-GRADE FIX: Check both context flag (for prerequisite failures) and results (for execution failures)
        # This ensures Step 11 can detect Step 7 failure even when prerequisites prevent execution
        step7_in_results = 7 in results
        step7_status = None
        step7_failed = context.get("step7_failed", False)  # Check context flag first (for prerequisite failures)
        
        if step7_in_results:
            step7_output = results.get(7)
            step7_status = step7_output.status if step7_output else None
            # If Step 7 was executed but failed, update the flag
            if step7_status == StepStatus.FAILED:
                step7_failed = True
                context["step7_failed"] = True
                context["step7_failure_reason"] = step7_output.error if hasattr(step7_output, "error") else "Execution failed"
        
        # BANK-GRADE: Log Step 7 status for audit trail
        if not step7_in_results and not step7_failed:
            # Step 7 was skipped but not due to failure - log for transparency
            self.logger.debug(
                "Step 7 not in results and no failure flag set",
                extra={
                    "step_number": 11,
                    "step7_in_results": False,
                    "step7_failed_flag": context.get("step7_failed", False),
                },
            )
        
        # Check Step 10 status to inform Step 11 whether to use fallback
        step10_in_results = 10 in results
        step10_status = None
        if step10_in_results:
            step10_output = results.get(10)
            step10_status = step10_output.status if step10_output else None
        
        # Set context flags for Step 11's fallback logic with full audit trail
        if step7_failed:
            context["step7_failed"] = True
            step6_available = (
                6 in results
                and results[6].status == StepStatus.COMPLETED
                and results[6].result
                and results[6].result.get("enterprise_value_mid")
            )
            step6_ev_mid = (
                results[6].result.get("enterprise_value_mid")
                if step6_available
                else None
            )
            self.logger.info(
                "ℹ️ Step 11 will use Step 6 EV values as fallback (Step 7 failed)",
                extra={
                    "step_number": 11,
                    "step7_status": step7_status.value if step7_status else "not_found",
                    "step6_available": step6_available,
                    "step6_ev_mid": step6_ev_mid,
                    "fallback_reason": "Step 7 EV to Equity conversion failed",
                    "fallback_strategy": "Use Step 6 EV as equity approximation",
                    "correlation_id": context.get("correlation_id"),
                    "audit_trail": {
                        "step7_failed": True,
                        "step6_fallback_used": step6_available,
                        "value_source": "Step 6 EV" if step6_available else "Revenue fallback",
                    },
                },
            )
        
        if not step10_in_results or (
            step10_status and step10_status != StepStatus.COMPLETED
        ):
            context["step10_failed"] = True
            self.logger.info(
                "ℹ️ Step 11 will execute with fallback logic (Step 10 not completed)",
                extra={
                    "step10_in_results": step10_in_results,
                    "step10_status": (
                        step10_status.value if step10_status else "not_found"
                    ),
                },
            )
        else:
            context["step10_failed"] = False
        
        # CRITICAL: Wrap Step 11 execution in try-except to ensure it always completes
        try:
            self.logger.debug(
                "🔍 [STEP-11] About to call step_executor.execute()",
                extra={
                    "correlation_id": context.get("correlation_id"),
                    "step_name": step.step_name if hasattr(step, "step_name") else "Unknown",
                },
            )
            output = await self.step_executor.execute(step, request, results, context)
            self.logger.debug(
                "✅ [STEP-11] step_executor.execute() returned",
                extra={
                    "correlation_id": context.get("correlation_id"),
                    "output_status": output.status.value if output else "None",
                    "has_result": output.result is not None if output else False,
                },
            )
            results[11] = output
            self.logger.debug(
                "✅ [STEP-11] Results stored in results[11]",
                extra={
                    "correlation_id": context.get("correlation_id"),
                    "step_11_in_results": 11 in results,
                    "stored_status": results[11].status.value if 11 in results else "not_stored",
                },
            )
            
            # If Step 11 failed, use fallback logic directly
            if (
                output.status == StepStatus.FAILED
                or output.status == StepStatus.SKIPPED
            ):
                self.logger.warning(
                    "⚠️ Step 11 returned non-COMPLETED status, using fallback logic",
                    extra={
                        "step_status": output.status.value,
                        "error": output.error if hasattr(output, "error") else None,
                    },
                )
                # Generate fallback result
                fallback_result = self.step11_fallback.fallback_handler.generate_step11_fallback(
                    results, request, context
                )
                results[11] = fallback_result
        except (
            CalculationError,
            ValidationError,
            DataQualityError,
            ValueError,
            TypeError,
            AttributeError,
        ) as e:
            self.logger.error(
                "❌ Step 11 execution raised exception, using fallback logic",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            # Generate fallback result
            fallback_result = self.step11_fallback.fallback_handler.generate_step11_fallback(
                results, request, context
            )
            results[11] = fallback_result
    
    def _validate_step7_prerequisites(
        self, results: Dict[int, StepOutput], step: Any
    ) -> bool:
        """
        Validate Step 7 prerequisites.
        
        Args:
            results: Results dictionary
            step: Step 7 object
            
        Returns:
            True if prerequisites met, False otherwise
        """
        if 3 not in results or results[3].status != StepStatus.COMPLETED:
            self.logger.error(
                "❌ Step 3 (base EV) required for Step 7, cannot continue",
                extra={
                    "step3_status": (
                        results.get(3, {}).status if 3 in results else "missing"
                    )
                },
            )
            results[7] = StepOutput(
                step_number=7,
                step_name=step.step_name,
                status=StepStatus.FAILED,
                result={},
                error="Step 3 (base EV) required for Step 7",
            )
            return False
        
        # Find the latest step with EV values (6, 5, 4, or 3)
        ev_source_step = None
        for candidate_step in [6, 5, 4, 3]:
            if candidate_step in results:
                candidate_result = results[candidate_step]
                if candidate_result.status == StepStatus.COMPLETED:
                    if "enterprise_value_mid" in candidate_result.result:
                        ev_source_step = candidate_step
                        break
        
        if ev_source_step is None:
            self.logger.error(
                "❌ No valid EV source found for Step 7, cannot continue",
                extra={"available_steps": list(results.keys())},
            )
            results[7] = StepOutput(
                step_number=7,
                step_name=step.step_name,
                status=StepStatus.FAILED,
                result={},
                error="No valid EV source found from steps 3-6",
            )
            return False
        
        self.logger.info(
            f"📊 Step 7 will use EV from Step {ev_source_step}",
            extra={"ev_source_step": ev_source_step},
        )
        return True

