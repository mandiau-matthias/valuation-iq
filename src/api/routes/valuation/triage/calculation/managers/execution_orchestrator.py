"""
Execution Orchestrator

Orchestrates the complete calculation execution flow, coordinating between executors
and handling setup, finalization, and error recovery.
"""

import time
from decimal import Decimal
from typing import Any, Dict, Optional

from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus
from src.api.schemas import ValuationRequest

from src.utils.exceptions import (
    CalculationError,
    ConfigurationError,
    DataQualityError,
    DomainError,
    ValidationError,
)
from src.utils.correlation import generate_correlation_id
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

from ...business_type_triage import BusinessTypeTriageEngine
from ..executors.sequential_executor import SequentialExecutor
from ..handlers.fallback_handler import FallbackHandler

logger = ValuationLogger(__name__)


class ExecutionOrchestrator:
    """
    Orchestrator for complete calculation execution.

    Responsibilities:
    - Setup execution (correlation ID, logging)
    - Coordinate sequential execution
    - Handle finalization and Step 11 guarantee
    - Provide error recovery
    """

    def __init__(
        self,
        logger_instance,
        business_type_triage: BusinessTypeTriageEngine,
        sequential_executor: SequentialExecutor,
        fallback_handler: FallbackHandler,
    ):
        """
        Initialize ExecutionOrchestrator.

        Args:
            logger_instance: Logger instance
            business_type_triage: Business type triage engine
            sequential_executor: Sequential executor instance
            fallback_handler: Fallback handler
        """
        self.logger = logger_instance
        self.business_type_triage = business_type_triage
        self.sequential_executor = sequential_executor
        self.fallback_handler = fallback_handler

    async def execute_full_calculation(
        self,
        steps: Dict[int, Any],
        request: ValuationRequest,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[int, StepOutput]:
        """
        Execute the complete calculation with intelligent triage.

        Args:
            steps: Dictionary of all registered steps
            request: The valuation request containing financial data
            context: Additional context and configuration (may include 'correlation_id')

        Returns:
            Dictionary mapping step numbers to their outputs
        """
        start_time = time.time()
        results: Dict[int, StepOutput] = {}
        context = context or {}

        # Extract or generate correlation ID for request tracing
        correlation_id = context.get("correlation_id")
        if not correlation_id:
            # Try to extract from request if available
            if hasattr(request, "correlation_id"):
                correlation_id = request.correlation_id
            else:
                correlation_id = generate_correlation_id()
                context["correlation_id"] = correlation_id

        # DEBUG: layer-internal entry log; the canonical INFO entry is
        # "🚀 Starting full 11-step calculation" below (carries business
        # category and revenue context).
        logger.debug(
            "🎯 Starting full calculation execution",
            extra={
                "correlation_id": correlation_id,
                "company_name": getattr(request, "company_name", "N/A"),
            },
        )

        # Get business category for logging
        business_category = "unknown"
        try:
            business_category = self.business_type_triage.get_business_type_category(
                getattr(request, "business_type_id", None),
                getattr(request, "business_model", None),
                getattr(request, "industry", None),
                category_id=getattr(request, "category_id", None),
            ).value
        except (ValueError, TypeError, AttributeError, KeyError):
            pass  # Don't fail if category lookup fails

        self.logger.info(
            "🚀 Starting full 11-step calculation",
            extra={
                "company": request.company_name,
                "industry": request.industry,
                "business_category": business_category,
                "revenue": (
                    getattr(request.current_year_data, "revenue", 0)
                    if hasattr(request, "current_year_data") and request.current_year_data
                    else 0
                ),
            },
        )

        try:
            # CRITICAL FIX: Add diagnostic logging BEFORE loop to verify Step 2 is registered
            # CRITICAL FIX: Convert to DEBUG level to reduce log volume
            self.logger.debug(
                "🔍 DIAGNOSTIC: Pre-execution step verification",
                extra={
                    "all_registered_steps": list(steps.keys()),
                    "step_2_registered": 2 in steps,
                    "step_2_class": type(steps[2]).__name__ if 2 in steps else None,
                    "step_2_name": steps[2].step_name if 2 in steps else None,
                    "total_steps": len(steps),
                    "correlation_id": context.get("correlation_id"),
                },
            )

            # Delegate to SequentialExecutor for step execution
            results = await self.sequential_executor.execute_sequential_steps(
                steps, request, results, context
            )

            total_time = (time.time() - start_time) * 1000

            # Get business category for final logging
            business_category = "unknown"
            try:
                business_category = self.business_type_triage.get_business_type_category(
                    getattr(request, "business_type_id", None),
                    getattr(request, "business_model", None),
                    getattr(request, "industry", None),
                    category_id=getattr(request, "category_id", None),
                ).value
            except (ValueError, TypeError, AttributeError, KeyError):
                pass

            # Get final equity value if available (prefer Step 8 ownership-adjusted, then Step 7)
            final_equity = None
            if 8 in results and results[8].status == StepStatus.COMPLETED:
                final_equity = results[8].result.get("ownership_adjusted_equity_mid")
            elif 7 in results and results[7].status == StepStatus.COMPLETED:
                final_equity = results[7].result.get("equity_value_mid")

            # CRITICAL: Post-loop guarantee - ensure Step 11 always exists in results
            # This is a defensive check with multiple layers of protection
            try:
                if 11 not in results:
                    self.logger.warning(
                        "⚠️ Step 11 not found in results after loop completion, generating fallback result",
                        extra={
                            "available_steps": list(results.keys()),
                            "completed_steps": [
                                k for k, v in results.items() if v.status == StepStatus.COMPLETED
                            ],
                            "failed_steps": [
                                k for k, v in results.items() if v.status == StepStatus.FAILED
                            ],
                        },
                    )
                    try:
                        fallback_result = self.fallback_handler.generate_step11_fallback(
                            results, request, context
                        )
                        results[11] = fallback_result
                        self.logger.info(
                            "✅ Step 11 fallback generated successfully in post-loop guarantee",
                            extra={"step11_status": fallback_result.status.value},
                        )
                    except (

                        CalculationError,
                        ValidationError,
                        DataQualityError,
                        ValueError,
                        TypeError,
                        AttributeError,
                    ) as e:
                        self.logger.error(
                            "❌ Failed to generate Step 11 fallback in post-loop guarantee",
                            extra={"error": str(e), "error_type": type(e).__name__},
                            exc_info=True,
                        )
                        # Last resort: create minimal valid Step 11 result
                        results[11] = StepOutput(
                            step_number=11,
                            step_name="Final Synthesis",
                            status=StepStatus.COMPLETED,
                            result={
                                "valuation_low": Decimal("10000.0"),
                                "valuation_mid": Decimal("10000.0"),
                                "valuation_high": Decimal("12000.0"),
                                "confidence_score": 0,
                                "methodology": "fallback_minimum",
                            },
                            error=None,
                        )
                elif results[11].status != StepStatus.COMPLETED:
                    # Step 11 exists but is not COMPLETED - replace with fallback
                    self.logger.warning(
                        "⚠️ Step 11 exists but is not COMPLETED, replacing with fallback result",
                        extra={
                            "step11_status": results[11].status.value,
                            "step11_error": (
                                results[11].error if hasattr(results[11], "error") else None
                            ),
                            "available_steps": list(results.keys()),
                        },
                    )
                    try:
                        fallback_result = self.fallback_handler.generate_step11_fallback(
                            results, request, context
                        )
                        results[11] = fallback_result
                        self.logger.info(
                            "✅ Step 11 fallback generated successfully to replace non-COMPLETED status",
                            extra={"step11_status": fallback_result.status.value},
                        )
                    except (
                        CalculationError,
                        ValidationError,
                        DataQualityError,
                        ValueError,
                        TypeError,
                        AttributeError,
                    ) as e:
                        self.logger.error(
                            "❌ Failed to generate Step 11 fallback to replace non-COMPLETED status",
                            extra={"error": str(e), "error_type": type(e).__name__},
                            exc_info=True,
                        )
                        # Last resort: create minimal valid Step 11 result
                        results[11] = StepOutput(
                            step_number=11,
                            step_name="Final Synthesis",
                            status=StepStatus.COMPLETED,
                            result={
                                "valuation_low": Decimal("10000.0"),
                                "valuation_mid": Decimal("10000.0"),
                                "valuation_high": Decimal("12000.0"),
                                "confidence_score": 0,
                                "methodology": "fallback_minimum",
                            },
                            error=None,
                        )

                # Final verification: ensure Step 11 is present and COMPLETED
                if 11 not in results or results[11].status != StepStatus.COMPLETED:
                    self.logger.error(
                        "❌ CRITICAL: Step 11 still missing or not COMPLETED after all fallback attempts",
                        extra={
                            "step11_present": 11 in results,
                            "step11_status": (
                                results[11].status.value if 11 in results else "missing"
                            ),
                        },
                    )
                    # Absolute last resort
                    results[11] = StepOutput(
                        step_number=11,
                        step_name="Final Synthesis",
                        status=StepStatus.COMPLETED,
                        result={
                            "valuation_low": Decimal("10000.0"),
                            "valuation_mid": Decimal("10000.0"),
                            "valuation_high": Decimal("12000.0"),
                            "confidence_score": 0,
                            "methodology": "fallback_absolute_minimum",
                        },
                        error=None,
                    )
            except (

                CalculationError,
                ValidationError,
                DataQualityError,
                ValueError,
                TypeError,
                AttributeError,
                KeyError,
            ) as e:
                self.logger.error(
                    "❌ CRITICAL: Exception in post-loop Step 11 guarantee",
                    extra={"error": str(e), "error_type": type(e).__name__},
                    exc_info=True,
                )
                # Absolute last resort - ensure Step 11 exists no matter what
                results[11] = StepOutput(
                    step_number=11,
                    step_name="Final Synthesis",
                    status=StepStatus.COMPLETED,
                    result={
                        "valuation_low": Decimal("10000.0"),
                        "valuation_mid": Decimal("10000.0"),
                        "valuation_high": Decimal("12000.0"),
                        "confidence_score": 0,
                        "methodology": "fallback_exception_handler",
                    },
                    error=None,
                )

            # DEBUG: same line fires from sequential_executor too — both
            # report a layer-internal "calculation complete". The canonical
            # exit is "🎉 Complete Valuation Calculation Journey Finished".
            self.logger.debug(
                "✅ Full calculation complete",
                extra={
                    "total_steps": len(results),
                    "completed": sum(
                        1 for r in results.values() if r.status == StepStatus.COMPLETED
                    ),
                    "skipped": sum(1 for r in results.values() if r.status == StepStatus.SKIPPED),
                    "failed": sum(1 for r in results.values() if r.status == StepStatus.FAILED),
                    "total_time_ms": round(total_time, 2),
                    "business_category": business_category,
                    "company": request.company_name,
                    "final_equity_value": final_equity,
                    "skipped_steps": [
                        k for k, v in results.items() if v.status == StepStatus.SKIPPED
                    ],
                    "failed_steps": [
                        k for k, v in results.items() if v.status == StepStatus.FAILED
                    ],
                    "step11_status": results[11].status.value if 11 in results else "missing",
                },
            )

        except (

            CalculationError,
            ValidationError,
            DataQualityError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
        ) as e:
            self.logger.error(
                f"💥 Fatal error in calculation triage: {e}",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "available_steps": list(results.keys()) if results else [],
                    "step11_present": 11 in results if results else False,
                    "step11_status": (
                        results[11].status.value if results and 11 in results else "missing"
                    ),
                },
                exc_info=True,
            )
            # CRITICAL: Even if fatal error occurs, ensure Step 11 exists and is COMPLETED
            # This is the last resort protection layer
            try:
                if 11 not in results or (
                    11 in results and results[11].status != StepStatus.COMPLETED
                ):
                    self.logger.warning(
                        "⚠️ Fatal error occurred, ensuring Step 11 exists with COMPLETED status",
                        extra={
                            "error": str(e),
                            "step11_present": 11 in results if results else False,
                            "step11_status": (
                                results[11].status.value if results and 11 in results else "missing"
                            ),
                        },
                    )
                    try:
                        # Try to generate proper fallback
                        fallback_result = self.fallback_handler.generate_step11_fallback(
                            results, request, context
                        )
                        results[11] = fallback_result
                        self.logger.info(
                            "✅ Step 11 fallback generated successfully after fatal error",
                            extra={"step11_status": fallback_result.status.value},
                        )
                    except (
                        CalculationError,
                        ValidationError,
                        DataQualityError,
                        ValueError,
                        TypeError,
                        AttributeError,
                    ) as fallback_error:
                        self.logger.error(
                            "❌ Failed to generate Step 11 fallback after fatal error, using absolute minimum",
                            extra={
                                "original_error": str(e),
                                "fallback_error": str(fallback_error),
                                "fallback_error_type": type(fallback_error).__name__,
                            },
                            exc_info=True,
                        )
                        # Absolute last resort: create minimal valid Step 11 result
                        results[11] = StepOutput(
                            step_number=11,
                            step_name="Final Synthesis",
                            status=StepStatus.COMPLETED,
                            result={
                                "valuation_low": Decimal("10000.0"),
                                "valuation_mid": Decimal("10000.0"),
                                "valuation_high": Decimal("12000.0"),
                                "confidence_score": 0,
                                "methodology": "fallback_fatal_error",
                            },
                            error=None,
                        )
                else:
                    # Step 11 exists and is COMPLETED - verify it's valid
                    step11_result = results[11].result
                    if (
                        not step11_result
                        or not step11_result.get("valuation_mid")
                        or step11_result.get("valuation_mid", 0) <= 0
                    ):
                        self.logger.warning(
                            "⚠️ Step 11 exists but has invalid values, replacing with fallback",
                            extra={"step11_result": step11_result, "original_error": str(e)},
                        )
                        try:
                            fallback_result = self.fallback_handler.generate_step11_fallback(
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
                        ):
                            # Last resort
                            results[11] = StepOutput(
                                step_number=11,
                                step_name="Final Synthesis",
                                status=StepStatus.COMPLETED,
                                result={
                                    "valuation_low": Decimal("10000.0"),
                                    "valuation_mid": Decimal("10000.0"),
                                    "valuation_high": Decimal("12000.0"),
                                    "confidence_score": 0,
                                    "methodology": "fallback_fatal_error_invalid",
                                },
                                error=None,
                            )
            except (
                CalculationError,
                ValidationError,
                DataQualityError,
                ValueError,
                TypeError,
                AttributeError,
                KeyError,
            ) as final_error:
                self.logger.error(
                    "❌ CRITICAL: Exception while ensuring Step 11 in fatal error handler",
                    extra={
                        "original_error": str(e),
                        "final_error": str(final_error),
                        "final_error_type": type(final_error).__name__,
                    },
                    exc_info=True,
                )
                # Absolute last resort - create Step 11 no matter what
                results[11] = StepOutput(
                    step_number=11,
                    step_name="Final Synthesis",
                    status=StepStatus.COMPLETED,
                    result={
                        "valuation_low": Decimal("10000.0"),
                        "valuation_mid": Decimal("10000.0"),
                        "valuation_high": Decimal("12000.0"),
                        "confidence_score": 0,
                        "methodology": "fallback_fatal_error_exception",
                    },
                    error=None,
                )
            raise

        return results
