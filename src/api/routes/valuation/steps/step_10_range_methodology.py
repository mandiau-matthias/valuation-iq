
"""
Step 10: Range Methodology Selection

Determines final valuation range using either:
1. Multiple Dispersion (if comparables ≥ 5)
2. Enhanced Confidence Spread (with business-type, growth, profitability, data quality adjustments)
3. Asymmetric Range (for SMEs with high downside risk)

World-class implementation following International Valuation Standards (IVS 2017) and academic valuation standards.
"""

from decimal import Decimal
from typing import List, Optional

from src.api.routes.valuation.triage.business_type_triage import (
    BusinessTypeCategory,
    BusinessTypeTriageEngine,
)
from src.api.routes.valuation.triage.step_registry import register_step
from src.domain.range_methodology_calculator import RangeMethodologyCalculator
from src.utils.decimal_helpers import (
    Money,
    bank_round,
    from_decimal,
    money_multiply,
    safe_money_divide,
    to_decimal,
)
from src.utils.logging import get_logger
from src.utils.sole_trader_detector import SoleTraderDetector

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.routes.valuation.steps.step_10_range_methodology.builders import (
    Step10ResultBuilder,
)
from src.api.routes.valuation.steps.step_10_range_methodology.calculators import (
    Step10RangeCalculator,
)
from src.api.routes.valuation.steps.step_10_range_methodology.handlers import (
    Step10ErrorHandler,
)

# Import new modular components
from src.api.routes.valuation.steps.step_10_range_methodology.orchestrators import (
    Step10Orchestrator,
)

logger = get_logger(__name__)


@register_step
class Step10RangeMethodology(CalculationStep):
    """
    Range Methodology Selection Step.

    Three approaches:
    1. Multiple Dispersion: Uses P25/P50/P75 from comparables (preferred)
    2. Enhanced Confidence Spread: Uses confidence score with business-type, growth, profitability, data quality adjustments
    3. Asymmetric Range: For SMEs with high downside risk (unprofitable + professional services)

    Enhanced Confidence Spread includes:
    - Business-type multipliers (SaaS: 0.85x, Professional Services: 1.15x, etc.)
    - Growth rate adjustments (validated vs unvalidated)
    - Profitability adjustments (profitable vs unprofitable)
    - Data quality integration (higher quality = tighter spreads)
    - Multi-tier size adjustments (Micro/Small/Medium/Large/Enterprise)
    """

    def __init__(self):
        """Initialize Step 10 with range calculator and business type triage."""
        self.range_calculator = RangeMethodologyCalculator()
        self.business_type_triage = BusinessTypeTriageEngine()

        # Initialize new modular components
        self.calculator = Step10RangeCalculator()
        self.error_handler = Step10ErrorHandler(step_name=self.step_name)
        self.result_builder = Step10ResultBuilder()
        self.orchestrator = Step10Orchestrator(
            range_calculator=self.range_calculator,
            business_type_triage=self.business_type_triage,
            calculator=self.calculator,
            result_builder=self.result_builder,
            error_handler=self.error_handler,
            step_name=self.step_name,
        )

    @property
    def step_number(self) -> int:
        return 10

    @property
    def step_name(self) -> str:
        return "Range Methodology"

    @property
    def dependencies(self) -> List[int]:
        # Require Step 0, 1, 2, 9 (Step 7 is optional, falls back to Step 6; Step 8 is optional)
        return [0, 1, 2, 9]
    
    @property
    def optional_dependencies(self) -> List[int]:
        """Optional dependencies that enhance the range calculation if available."""
        return [6, 7, 8]  # Step 6 (fallback for Step 7), Step 7 (preferred), Step 8 (ownership-adjusted)

    def should_execute(self, input_data: StepInput) -> bool:
        return True  # Always determine range

    async def execute(self, input_data: StepInput) -> StepOutput:
        """Determine final valuation range with enhanced methodology."""
        logger.info(
            "▶️  Executing Step 10: Range Methodology Selection",
            extra={
                "step_number": 10,
                "step_name": self.step_name,
                "company": getattr(input_data.request, "company_name", "N/A"),
            },
        )

        try:
            # Get previous step results
            request = input_data.request
            step0_result = self.get_previous_step_result(0, input_data.previous_results)
            step1_result = self.get_previous_step_result(1, input_data.previous_results)
            step2_result = self.get_previous_step_result(2, input_data.previous_results)
            
            # Get full StepOutput objects (not just result dicts) for steps 6, 7, 8
            # The orchestrator needs these to check status
            step6_output = input_data.previous_results.get(6)  # Full StepOutput object
            step7_output = input_data.previous_results.get(7)  # Full StepOutput object
            step8_output = input_data.previous_results.get(8)  # Full StepOutput object
            step9_result = self.get_previous_step_result(9, input_data.previous_results)

            # Extract step results as dictionaries
            # Handle both StepOutput objects and dictionaries
            def extract_result(step_result):
                if step_result is None:
                    return None
                if isinstance(step_result, dict):
                    status = step_result.get("status")
                    return (
                        step_result
                        if status in (None, "completed", StepStatus.COMPLETED)
                        else None
                    )
                if hasattr(step_result, 'status') and step_result.status == StepStatus.COMPLETED:
                    return step_result.result if hasattr(step_result, 'result') else None
                return None

            step0_dict = extract_result(step0_result)
            step1_dict = extract_result(step1_result)
            step2_dict = extract_result(step2_result)

            # Call orchestrator
            correlation_id = input_data.context.get("correlation_id") if input_data.context else None
            result_dict, metadata_dict = await self.orchestrator.orchestrate_execution(
                request=request,
                step0=step0_dict,
                step1=step1_dict,
                step2=step2_dict,
                step7_output=step7_output,  # Pass full StepOutput object
                step8_output=step8_output,  # Pass full StepOutput object
                step9_confidence_result=step9_result,  # Already extracted by get_previous_step_result
                step6_output=step6_output,  # Pass full StepOutput object
                correlation_id=correlation_id,
            )

            return StepOutput(
                step_number=10,
                step_name=self.step_name,
                status=StepStatus.COMPLETED,
                result=result_dict,
                metadata=metadata_dict,
            )
        except Exception as e:
            logger.error(
                "❌ Step 10 execution failed",
                extra={
                    "step_number": 10,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            return self.error_handler.handle_execution_error(e)
