"""
Step 2.7: SDE Calculation (CalculationStep wrapper)

Wraps Step27Orchestrator for integration with the valuation pipeline.
SDE cross-check is applied in Step 11 for micro/small businesses.
"""

from typing import Any, Dict, List

from src.api.routes.valuation.triage.step_registry import register_step
from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

from .orchestrators.step_2_7_orchestrator import Step27Orchestrator

logger = get_logger(__name__)


@register_step
class Step27SDECalculation(CalculationStep):
    """
    SDE (Seller's Discretionary Earnings) Calculation Step.

    Calculates SDE-based valuation for small, owner-operated businesses.
    Step 11 blends SDE with EBITDA valuation when revenue < EUR 2M.
    """

    def __init__(self):
        super().__init__()
        self.orchestrator = Step27Orchestrator(self.step_name)

    @property
    def step_number(self) -> float:
        return 2.7

    @property
    def step_name(self) -> str:
        return "SDE Calculation"

    @property
    def dependencies(self) -> List[int]:
        return [1, 2]

    def should_execute(self, input_data: StepInput) -> bool:
        """
        Execute if SDE is appropriate: revenue < EUR 2M and owner-operated.
        Delegates to business-type triage for final decision.
        """
        step1 = self.get_previous_step_result(1, input_data.previous_results)
        step2 = self.get_previous_step_result(2, input_data.previous_results)
        if not step1 or not step2:
            return False

        revenue = to_decimal(step1.get("revenue") or 0)
        ebitda = to_decimal(step1.get("ebitda") or 0)
        if revenue <= 0:
            return False

        num_owners = 1
        if hasattr(input_data.request, "number_of_owners") and input_data.request.number_of_owners:
            num_owners = input_data.request.number_of_owners
        elif hasattr(input_data.request, "business_context") and input_data.request.business_context:
            num_owners = input_data.request.business_context.get("number_of_owners", 1)

        is_appropriate, _ = self.orchestrator.calculator.is_sde_appropriate(
            revenue, num_owners, getattr(input_data.request, "category_id", "other")
        )
        return is_appropriate

    async def execute(self, input_data: StepInput) -> StepOutput:
        """Delegate to Step27Orchestrator."""
        step1 = self.get_previous_step_result(1, input_data.previous_results)
        step2 = self.get_previous_step_result(2, input_data.previous_results)
        if not step1 or not step2:
            from .handlers.step_2_7_error_handler import Step27ErrorHandler
            handler = Step27ErrorHandler(self.step_name)
            return handler.handle_missing_data(["step1_result", "step2_result"])

        correlation_id = input_data.context.get("correlation_id") if input_data.context else None
        return await self.orchestrator.orchestrate_execution(
            input_data.request,
            step1,
            step2,
            correlation_id=correlation_id,
        )
