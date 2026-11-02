"""
Step 9: Confidence Score Analysis

Calculates 8-factor confidence score to assess valuation reliability.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.routes.valuation.triage.step_registry import register_step
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.routes.valuation.steps.step_9_confidence_score.handlers.step_9_error_handler import (
    Step9ErrorHandler,
)
from src.api.routes.valuation.steps.step_9_confidence_score.orchestrators.step_9_orchestrator import (
    Step9Orchestrator,
)

logger = get_logger(__name__)


@register_step
class Step9ConfidenceScore(CalculationStep):
    """
    Confidence Score Analysis Step.

    8-Factor Confidence Model:
    1. Data Quality (0-100): Completeness of financial data
    2. Historical Data (0-100): Years of historical data available
    3. Methodology Agreement (0-100): DCF vs Multiples alignment
    4. Industry Benchmarks (0-100): Quality of comparable companies
    5. Company Profile (0-100): Business stability and profitability
    6. Market Conditions (0-100): Economic environment stability
    7. Geographic Data (0-100): Country-specific data quality
    8. Business Model Clarity (0-100): Fit to standard approaches

    Overall Score: Weighted average of 8 factors
    """

    def __init__(self):
        """Initialize Step 9 with orchestrator and error handler."""
        super().__init__()
        self.orchestrator = Step9Orchestrator(self.step_name)
        self.error_handler = Step9ErrorHandler(self.step_name)

    @property
    def step_number(self) -> int:
        return 9

    @property
    def step_name(self) -> str:
        return "Confidence Score Analysis"

    @property
    def dependencies(self) -> List[int]:
        # Require Step 0, 1, 2, 7 (Step 8 is optional)
        return [0, 1, 2, 7]

    def should_execute(self, input_data: StepInput) -> bool:
        return True  # Always calculate confidence

    async def execute(self, input_data: StepInput) -> StepOutput:
        """Calculate confidence score."""
        logger.info(
            "▶️  Executing Step 9: Confidence Score Analysis",
            extra={
                "step_number": 9,
                "step_name": self.step_name,
                "company": getattr(input_data.request, "company_name", "N/A"),
            },
        )

        step0 = self.get_previous_step_result(0, input_data.previous_results)
        step1 = self.get_previous_step_result(1, input_data.previous_results)
        step2 = self.get_previous_step_result(2, input_data.previous_results)

        logger.debug(
            "📥 Extracting previous step results",
            extra={
                "step_number": 9,
                "has_step0": bool(step0),
                "has_step1": bool(step1),
                "has_step2": bool(step2),
            },
        )

        # Step 0 and 1 are required, Step 2 is preferred but can use defaults
        if step0 is None or step1 is None:
            missing_steps = [i for i, s in [(0, step0), (1, step1)] if s is None]
            return self.error_handler.handle_missing_required_steps(
                step0 is not None, step1 is not None, missing_steps
            )

        # Try Step 8 first (ownership-adjusted equity), fallback to Step 7, then Step 6 EV
        step8_output = input_data.previous_results.get(8)
        step7_output = input_data.previous_results.get(7)
        step6_output = input_data.previous_results.get(6)

        equity_step = None
        if step8_output and step8_output.status == StepStatus.COMPLETED:
            equity_step = step8_output
            logger.info(
                "✅ Using Step 8 (ownership-adjusted equity) for confidence calculation",
                extra={
                    "step_number": 9,
                    "equity_source": "Step 8 (ownership-adjusted)",
                    "equity_value_mid": (
                        equity_step.result.get("ownership_adjusted_equity_mid")
                        if equity_step.result
                        else None
                    ),
                },
            )
        elif step7_output and step7_output.status == StepStatus.COMPLETED:
            equity_step = step7_output
            logger.debug(
                "✅ Using Step 7 (equity) for confidence calculation (Step 8 not available)",
                extra={
                    "step_number": 9,
                    "equity_source": "Step 7 (equity)",
                    "equity_value_mid": (
                        equity_step.result.get("equity_value_mid") if equity_step.result else None
                    ),
                },
            )
        elif step6_output and step6_output.status == StepStatus.COMPLETED:
            # CRITICAL FIX: Use Step 6 EV values when Step 7/8 unavailable
            # BANK-GRADE: Full audit trail and structured logging
            step6_result = step6_output.result if step6_output.result else {}
            ev_mid = step6_result.get("enterprise_value_mid")
            # BANK-GRADE: Use is not None check to preserve zero values (zero is a valid valuation)
            if ev_mid is not None:
                ev_low = step6_result.get("enterprise_value_low", ev_mid * Decimal("0.8"))
                ev_high = step6_result.get("enterprise_value_high", ev_mid * Decimal("1.2"))
                
                logger.warning(
                    "⚠️ Step 7/8 unavailable, using Step 6 EV as equity approximation for Step 9",
                    extra={
                        "step_number": 9,
                        "step_name": self.step_name,
                        "step7_status": step7_output.status.value if step7_output else "not_found",
                        "step7_error": step7_output.error if step7_output and hasattr(step7_output, "error") else None,
                        "step8_status": step8_output.status.value if step8_output else "not_found",
                        "step8_error": step8_output.error if step8_output and hasattr(step8_output, "error") else None,
                        "step6_ev_low": ev_low,
                        "step6_ev_mid": ev_mid,
                        "step6_ev_high": ev_high,
                        "fallback_reason": "Step 7/8 EV to Equity conversion failed",
                        "fallback_strategy": "Use Step 6 EV as equity approximation",
                        "correlation_id": input_data.context.get("correlation_id") if input_data.context else None,
                        "audit_trail": {
                            "step7_failed": step7_output is None or step7_output.status != StepStatus.COMPLETED,
                            "step8_failed": step8_output is None or step8_output.status != StepStatus.COMPLETED,
                            "step6_fallback_used": True,
                            "value_source": "Step 6 EV",
                            "approximation_note": "EV used as equity approximation (no net debt adjustment)",
                        },
                    },
                )
                # Create a Step 7-like result structure from Step 6 EV values
                # BANK-GRADE: Explicit fallback flag for transparency
                step7_like_result = {
                    "equity_value_low": ev_low,
                    "equity_value_mid": ev_mid,
                    "equity_value_high": ev_high,
                    "fallback_from_step6": True,
                    "fallback_reason": "Step 7/8 EV to Equity conversion failed",
                    "note": "Using Step 6 EV as equity approximation (Step 7/8 failed)",
                    "audit_metadata": {
                        "original_source": "Step 6 EV",
                        "approximation_method": "Direct EV to equity (assumes zero net debt)",
                    },
                }
                # Create a mock StepOutput-like object for orchestrator
                # BANK-GRADE: Clear type annotation and documentation
                class MockStepOutput:
                    """
                    Mock StepOutput for fallback scenarios.
                    
                    The orchestrator expects equity_step.result to be a dict,
                    so we create a lightweight wrapper to maintain compatibility.
                    """
                    def __init__(self, result_dict: Dict[str, Any]):
                        self.result = result_dict
                
                equity_step = MockStepOutput(step7_like_result)
            else:
                return self.error_handler.handle_missing_equity_value(
                    step8_output.status.value if step8_output else None,
                    step7_output.status.value if step7_output else None,
                )
        else:
            return self.error_handler.handle_missing_equity_value(
                step8_output.status.value if step8_output else None,
                step7_output.status.value if step7_output else None,
            )

        # Delegate to orchestrator
        return await self.orchestrator.orchestrate_execution(
            input_data.request, step0, step1, step2, equity_step, input_data.previous_results
        )
