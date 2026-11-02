"""
Sequential Executor

Handles sequential execution of calculation steps in groups (foundation, discount, final).
"""

import time
from decimal import Decimal
from typing import Any, Dict

from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus
from src.api.schemas import ValuationRequest

from src.utils.exceptions import (
    CalculationError,
    ConfigurationError,
    DataQualityError,
    DomainError,
    ValidationError,
)
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

from ...business_type_triage import BusinessTypeTriageEngine
from ..handlers.fallback_handler import FallbackHandler
from .step_executor import StepExecutor
from .coordinators import (
    FoundationStepCoordinator,
    DiscountStepCoordinator,
    FinalStepCoordinator,
    Step11FallbackCoordinator,
)

logger = ValuationLogger(__name__)


class SequentialExecutor:
    """
    Executor for sequential step execution.

    Responsibilities:
    - Execute foundation steps (0-3) sequentially
    - Execute discount steps (4-6) sequentially with cascading
    - Execute final steps (7-11) sequentially
    - Handle error recovery and Step 11 fallback logic
    """

    def __init__(
        self,
        logger_instance,
        business_type_triage: BusinessTypeTriageEngine,
        step_executor: StepExecutor,
        fallback_handler: FallbackHandler,
    ):
        """
        Initialize SequentialExecutor.

        Args:
            logger_instance: Logger instance
            business_type_triage: Business type triage engine
            step_executor: Step executor instance
            fallback_handler: Fallback handler
        """
        self.logger = logger_instance
        self.business_type_triage = business_type_triage
        self.step_executor = step_executor
        self.fallback_handler = fallback_handler
        
        # Initialize coordinators
        self.step11_fallback_coordinator = Step11FallbackCoordinator(
            fallback_handler, logger_instance
        )
        self.foundation_coordinator = FoundationStepCoordinator(
            step_executor, logger_instance
        )
        self.discount_coordinator = DiscountStepCoordinator(
            step_executor, logger_instance
        )
        self.final_coordinator = FinalStepCoordinator(
            step_executor, self.step11_fallback_coordinator, logger_instance
        )

    async def execute_sequential_steps(
        self,
        steps: Dict[int, Any],
        request: ValuationRequest,
        results: Dict[int, StepOutput],
        context: Dict[str, Any],
    ) -> Dict[int, StepOutput]:
        """
        Execute steps sequentially in groups.

        Args:
            steps: Dictionary of all registered steps
            request: The valuation request
            results: Results dictionary (will be updated)
            context: Execution context

        Returns:
            Updated results dictionary
        """
        start_time = time.time()
        try:
            # Execute foundation steps (0-3) via coordinator
            await self.foundation_coordinator.execute_foundation_steps(
                steps, request, results, context
            )
            
            # Execute discount steps (4-6) via coordinator
            await self.discount_coordinator.execute_discount_steps(
                steps, request, results, context
            )
            
            # Execute final steps (7-11) via coordinator
            await self.final_coordinator.execute_final_steps(
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

            # Final Step 11 guarantee (defensive check after all steps complete)
            self.step11_fallback_coordinator.ensure_step11_exists(
                results, request, context
            )

            # DEBUG: layer-internal completion log; canonical exit lives
            # at the Step 11 orchestrator ("Complete Valuation Calculation Journey Finished").
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
            DomainError,
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
            # Use coordinator to handle all fallback scenarios
            self.step11_fallback_coordinator.ensure_step11_after_error(
                results, request, context, e
            )
            raise

        return results
