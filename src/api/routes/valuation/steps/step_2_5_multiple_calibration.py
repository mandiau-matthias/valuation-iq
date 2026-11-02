"""
Step 2.5: Multiple Calibration

Adjusts comparables-derived base multiple for subject company quality factors.

MULTIPLE-FIRST METHODOLOGY:
All quality adjustments are applied to the MULTIPLE, not to EBITDA. This prevents
double-counting when subsequent steps (4-6) also discount the multiple for risk factors.

Academic Compliance:
- Damodaran (2012): "Multiples should be adjusted for fundamental differences"
- Hitchner (2017): "Company-specific multiple reflects quality differences"
- McKinsey (2020): "Multiple adjustment mechanism for quality and risk"
- Big 4 Standard: All adjustments to multiple, not metric

Quality Factors Analyzed:
1. Margin Volatility - Higher volatility → Lower multiple
2. Earnings Quality - Lower quality → Lower multiple
3. Owner Compensation Risk - Above market → Lower multiple

Output:
- quality_multiple_adjustment: Δ to base multiple (e.g., -0.2x for quality discount)
- quality_analysis: Detailed assessment of quality factors
- margin_analysis: Volatility and quality of earnings assessment

Methodology: Multiple-First Approach (Big 4 Standard)
The multiple is the adjustment vehicle, not the EBITDA metric.
"""

import time
from decimal import Decimal
from typing import Any, Dict, List

from src.api.routes.valuation.triage.step_registry import register_step
from src.api.routes.valuation.steps.base_step import CalculationStep, StepInput, StepOutput, StepStatus
from src.api.routes.valuation.steps.step_2_5_multiple_calibration.handlers.step_2_5_error_handler import Step25ErrorHandler
from src.api.routes.valuation.steps.step_2_5_multiple_calibration.orchestrators.step_2_5_orchestrator import Step25Orchestrator
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


@register_step
class Step25MultipleCalibration(CalculationStep):
    """
    Multiple Calibration Step (MULTIPLE-FIRST METHODOLOGY).
    
    Analyzes quality factors and adjusts the base multiple (not EBITDA) to reflect
    subject company quality differences vs. comparables:
    - Margin volatility → Lower multiple if volatile
    - Owner compensation risk → Lower multiple if above market
    - Earnings consistency → Lower multiple if inconsistent
    
    Critical for bank-grade valuations following Big 4 multiple-first approach.
    Prevents double-counting when Steps 4-6 also discount the multiple.
    """
    
    def __init__(self):
        """Initialize Step 2.5 with orchestrator and error handler."""
        super().__init__()
        self.orchestrator = Step25Orchestrator(self.step_name)
        self.error_handler = Step25ErrorHandler(self.step_name)
    
    @property
    def step_number(self) -> int:
        """Step 2.5 - executes between Step 2 (Benchmarking) and Step 3 (Base EV)."""
        return 2.5
    
    @property
    def step_name(self) -> str:
        return "Multiple Calibration"
    
    @property
    def dependencies(self) -> List[int]:
        return [1, 2]  # Depends on input data and benchmarking
    
    def should_execute(self, input_data: StepInput) -> bool:
        """
        Execute normalization if:
        1. EBITDA is available
        2. Revenue > 0 (to calculate margins)
        3. Primary method is EV/EBITDA (from Step 2)
        
        Skip if using pure revenue multiple methodology.
        """
        # Check if Step 1 has EBITDA data
        step1 = self.get_previous_step_result(1, input_data.previous_results)
        if not step1:
            return False
        
        ebitda_raw = step1.get("ebitda")
        ebitda = to_decimal(ebitda_raw) if ebitda_raw is not None else Decimal("0")
        revenue_raw = step1.get("revenue")
        revenue = to_decimal(revenue_raw) if revenue_raw is not None else Decimal("0")
        
        # Must have revenue for margin analysis
        if revenue <= 0:
            logger.warning(
                "⚠️ Step 2.5 skipped: Revenue is zero",
                extra={"step_number": 2.5}
            )
            return False
        
        # Check primary method from Step 2
        step2 = self.get_previous_step_result(2, input_data.previous_results)
        if step2:
            primary_method = step2.get("primary_method")
            if primary_method and "REVENUE" in str(primary_method).upper():
                logger.info(
                    "ℹ️ Step 2.5 skipped: Primary method is EV/Revenue (normalization only applies to EBITDA)",
                    extra={"step_number": 2.5, "primary_method": primary_method}
                )
                return False
        
        # Execute if EBITDA is available (even if negative - need to analyze)
        should_run = ebitda is not None
        
        if not should_run:
            logger.info(
                "ℹ️ Step 2.5 skipped: EBITDA not available",
                extra={"step_number": 2.5}
            )
        
        return should_run
    
    async def execute(self, input_data: StepInput) -> StepOutput:
        """
        Execute EBITDA normalization.
        
        Process:
        1. Extract reported EBITDA and revenue from Step 1
        2. Analyze margin volatility from historical data
        3. Calculate owner compensation adjustment
        4. Estimate one-time expense add-backs
        5. Calculate normalized EBITDA
        6. Build adjustment schedule for report transparency
        
        Returns:
            StepOutput with normalized_ebitda and adjustment details
        """
        execution_start_time = time.time()
        
        logger.info(
            "🔍 Starting Step 2.5: Multiple Calibration",
            extra={
                "step_number": 2.5,
                "step_name": self.step_name,
                "company_name": getattr(input_data.request, "company_name", "N/A"),
                "dependencies": self.dependencies,
                "available_previous_steps": list(input_data.previous_results.keys()),
            }
        )
        
        # Get dependency steps
        step1 = self.get_previous_step_result(1, input_data.previous_results)
        step2 = self.get_previous_step_result(2, input_data.previous_results)
        
        if not step1 or not step2:
            return self.error_handler.handle_missing_steps(
                step1 is not None,
                step2 is not None,
                list(input_data.previous_results.keys())
            )
        
        logger.debug(
            "📥 Step 2.5 input data extracted",
            extra={
                "step_number": 2.5,
                "step1_keys": list(step1.keys()) if step1 else [],
                "step2_keys": list(step2.keys()) if step2 else [],
            }
        )
        
        # Delegate to orchestrator
        correlation_id = input_data.context.get("correlation_id") if input_data.context else None
        return await self.orchestrator.orchestrate_execution(
            input_data.request,
            step1,
            step2,
            correlation_id,
            execution_start_time
        )

