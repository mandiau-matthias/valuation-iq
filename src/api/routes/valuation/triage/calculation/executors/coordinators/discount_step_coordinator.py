"""
Discount Step Coordinator

Handles execution of discount steps (4-6) sequentially with cascading discounts.
Extracted from sequential_executor.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Cascading discount logic
"""

from typing import Any, Dict, Union

from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus
from src.api.schemas import ValuationRequest
from src.utils.valuation_logger import ValuationLogger
from typing import TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular import
if TYPE_CHECKING:
    from ..step_executor import StepExecutor

logger = ValuationLogger(__name__)


class DiscountStepCoordinator:
    """
    Coordinates discount step execution (steps 4-6).

    Responsibilities:
    - Execute steps 4-6 sequentially with cascading
    - Ensure cumulative discounting:
      Multiple_final = Multiple_base × owner × size × liquidity
    """

    def __init__(self, step_executor: "StepExecutor", logger_instance):
        """
        Initialize discount step coordinator.

        Args:
            step_executor: StepExecutor instance
            logger_instance: Logger instance
        """
        self.step_executor = step_executor
        self.logger = logger_instance

    def _latest_completed_cascade_step(self, results: Dict[Union[int, float], StepOutput]) -> str:
        """Return the latest completed discount cascade source for diagnostics."""
        for step_number in (4.5, 4, 3):
            output = results.get(step_number)
            if output and output.status == StepStatus.COMPLETED:
                return f"Step {step_number:g}"
        return "Step 3"

    async def execute_discount_steps(
        self,
        steps: Dict[Union[int, float], Any],
        request: ValuationRequest,
        results: Dict[Union[int, float], StepOutput],
        context: Dict[str, Any],
    ) -> None:
        """
        Execute discount steps (4-6) sequentially with cascading.

        UPDATED 2025-12-20: Added Step 4.5 (Revenue Trend Adjustment) execution.
        UPDATED 2025-12-20 (PM): Fixed type hints to support float step numbers (4.5).

        Args:
            steps: Dictionary of all registered steps (int or float keys)
            request: Valuation request
            results: Results dictionary (will be updated)
            context: Execution context
        """
        # Execute steps 4, 4.5, 5, 6 SEQUENTIALLY to ensure cumulative discounting
        # Step 4 applies owner concentration discount to Step 3's base EV
        # Step 4.5 applies revenue trend discount to Step 4, or Step 3 if Step 4 skipped
        # Step 5 applies size discount to the latest completed cascade source
        # Step 6 applies liquidity discount to Step 5's adjusted EV (cumulative)
        if 3 in results and results[3].status == StepStatus.COMPLETED:
            # Execute Step 4 first (owner concentration)
            step4 = steps.get(4)
            if step4:
                output = await self.step_executor.execute(step4, request, results, context)
                if output:
                    results[4] = output
                    if output.status == StepStatus.COMPLETED:
                        self.logger.debug("✓ Step 4 (owner concentration) complete")
                    elif output.status == StepStatus.SKIPPED:
                        self.logger.debug("ℹ️ Step 4 skipped (no owner data)")
                    else:
                        self.logger.warning(
                            "⚠️ Step 4 failed, continuing with previous step results"
                        )

            # ADDED 2025-12-20: Execute Step 4.5 (Revenue Trend Adjustment)
            # This step applies a discount for declining year-over-year revenue
            step45 = steps.get(4.5)
            if step45:
                self.logger.debug("🔍 [Step 4.5] About to execute revenue trend adjustment")
                output_45 = await self.step_executor.execute(step45, request, results, context)
                if output_45:
                    results[4.5] = output_45
                    if output_45.status == StepStatus.COMPLETED:
                        base_step = (
                            "Step 4"
                            if (results.get(4) and results[4].status == StepStatus.COMPLETED)
                            else "Step 3"
                        )
                        self.logger.debug(
                            f"✓ Step 4.5 (revenue trend) complete with cascading on {base_step}"
                        )
                    elif output_45.status == StepStatus.SKIPPED:
                        self.logger.debug("ℹ️ Step 4.5 skipped (revenue stable/growing)")
                    else:
                        self.logger.warning(
                            "⚠️ Step 4.5 failed, continuing with previous step results"
                        )
            else:
                self.logger.warning(
                    "⚠️ Step 4.5 (Revenue Trend) not found in steps registry. "
                    "This may indicate a registration issue."
                )

            # Execute Step 5 sequentially after Step 4.5. It cascades on the
            # latest completed source: Step 4.5, Step 4, or Step 3.
            step5 = steps.get(5)
            if step5:
                output = await self.step_executor.execute(step5, request, results, context)
                if output:
                    results[5] = output
                    if output.status == StepStatus.COMPLETED:
                        base_step = self._latest_completed_cascade_step(results)
                        self.logger.debug(
                            f"✓ Step 5 (size discount) complete with cascading on {base_step}"
                        )
                    elif output.status == StepStatus.SKIPPED:
                        self.logger.debug("ℹ️ Step 5 skipped")
                    else:
                        self.logger.warning(
                            "⚠️ Step 5 failed, continuing with previous step results"
                        )

        # Execute Step 6 SEQUENTIALLY after Steps 4-5 (cascading discount)
        # Step 6 cascades on top of Steps 4-5 results to ensure cumulative discounts
        # Priority: Step 5 > Step 4 > Step 3
        if 3 in results and results[3].status == StepStatus.COMPLETED:
            step6 = steps.get(6)
            if step6:
                output = await self.step_executor.execute(step6, request, results, context)
                results[6] = output

                if output.status == StepStatus.COMPLETED:
                    self.logger.debug(
                        "✓ Step 6 (liquidity discount) complete with cascading",
                        extra={"base_step_used": output.result.get("base_step", "unknown")},
                    )
                elif output.status == StepStatus.FAILED:
                    self.logger.warning(
                        "⚠️ Step 6 failed, continuing with previous step results",
                        extra={"error": output.error},
                    )
