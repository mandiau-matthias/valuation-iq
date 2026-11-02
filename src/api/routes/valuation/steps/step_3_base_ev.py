"""
Step 3: Base Enterprise Value Calculation

Calculates unadjusted enterprise value using selected multiples before
applying risk adjustments (owner concentration, size, liquidity).
"""

import time
from decimal import Decimal
from typing import Any, Dict, List

from src.api.routes.valuation.triage.step_registry import register_step
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.routes.valuation.steps.step_3_base_ev.handlers.step_3_error_handler import (
    Step3ErrorHandler,
)
from src.api.routes.valuation.steps.step_3_base_ev.orchestrators.step_3_orchestrator import (
    Step3Orchestrator,
)

logger = get_logger(__name__)


@register_step
class Step3BaseEV(CalculationStep):
    """
    Base Enterprise Value Calculation Step.

    Calculates:
    - Enterprise Value = Revenue × Revenue Multiple (if revenue is primary)
    - Enterprise Value = EBITDA × EBITDA Multiple (if EBITDA is primary)
    - Low/Mid/High estimates based on P25/P50/P75 multiples
    """

    def __init__(self):
        """Initialize Step 3 with orchestrator and error handler."""
        super().__init__()
        self.orchestrator = Step3Orchestrator(self.step_name)
        self.error_handler = Step3ErrorHandler(self.step_name)

    @property
    def step_number(self) -> int:
        return 3

    @property
    def step_name(self) -> str:
        return "Base Enterprise Value"

    @property
    def dependencies(self) -> List[int]:
        # NOTE: Step 2.5 is OPTIONAL dependency (not required, graceful degradation)
        return [1, 2]  # Depends on input validation and benchmarking

    def should_execute(self, input_data: StepInput) -> bool:
        return True  # Always calculate base EV

    async def execute(self, input_data: StepInput) -> StepOutput:
        """
        Calculate base enterprise value.

        Formula:
        - EV/Revenue: Enterprise Value = Revenue × Revenue Multiple
        - EV/EBITDA: Enterprise Value = NORMALIZED EBITDA × EBITDA Multiple
          (uses Step 2.5 normalization if available, falls back to reported EBITDA)

        Uses P25/P50/P75 percentiles for low/mid/high estimates.
        """
        execution_start_time = time.time()

        logger.info(
            "🔍 Starting Step 3: Base Enterprise Value Calculation",
            extra={
                "step_number": 3,
                "step_name": self.step_name,
                "company_name": getattr(input_data.request, "company_name", "N/A"),
                "dependencies": self.dependencies,
                "available_previous_steps": list(input_data.previous_results.keys()),
                "has_request_current_year_data": bool(
                    getattr(input_data.request, "current_year_data", None)
                ),
                "request_revenue": (
                    getattr(getattr(input_data.request, "current_year_data", None), "revenue", None)
                    if getattr(input_data.request, "current_year_data", None)
                    else None
                ),
                "request_ebitda": (
                    getattr(getattr(input_data.request, "current_year_data", None), "ebitda", None)
                    if getattr(input_data.request, "current_year_data", None)
                    else None
                ),
            },
        )

        step1 = self.get_previous_step_result(1, input_data.previous_results)
        step2 = self.get_previous_step_result(2, input_data.previous_results)
        
        # CRITICAL: Fetch Step 2.5 (Multiple Calibration) if available
        # This is OPTIONAL - will gracefully degrade to reported EBITDA if not present
        step2_5 = self.get_previous_step_result(2.5, input_data.previous_results)
        
        primary_method_raw = (step2 or {}).get("primary_method") if isinstance(step2, dict) else None
        primary_method = str(primary_method_raw or "").strip().lower().replace("_", "/")
        is_revenue_primary = primary_method in {
            "ev/revenue",
            "revenue",
            "revenue/multiple",
        }

        if step2_5:
            logger.debug(
                "✅ Step 2.5 Multiple Calibration available - will use normalized EBITDA",
                extra={
                    "step_number": 3,
                    "normalized_ebitda": step2_5.get("normalized_ebitda"),
                    "total_adjustments": step2_5.get("total_adjustments"),
                    "compliance": "ASA BVS-III, AICPA BVS-VII",
                }
            )
        elif is_revenue_primary:
            logger.info(
                "ℹ️ Step 2.5 not applicable - primary method is EV/Revenue",
                extra={"step_number": 3, "primary_method": primary_method_raw},
            )
        else:
            logger.warning(
                "⚠️ Step 2.5 not available - using reported EBITDA (may reduce valuation accuracy)",
                extra={"step_number": 3, "primary_method": primary_method_raw}
            )

        if not step1 or not step2:
            return self.error_handler.handle_missing_steps(
                step1 is not None, step2 is not None, list(input_data.previous_results.keys())
            )

        logger.debug(
            "📥 Step 3 input data extracted",
            extra={
                "step_number": 3,
                "step1_keys": list(step1.keys()) if step1 else [],
                "step2_keys": list(step2.keys()) if step2 else [],
                "step2_5_keys": list(step2_5.keys()) if step2_5 else [],
            },
        )

        # Delegate to orchestrator
        correlation_id = input_data.context.get("correlation_id") if input_data.context else None
        return await self.orchestrator.orchestrate_execution(
            input_data.request, step1, step2, correlation_id, execution_start_time, step2_5
        )
