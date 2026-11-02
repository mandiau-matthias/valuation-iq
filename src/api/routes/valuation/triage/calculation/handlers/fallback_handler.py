"""
Fallback Handler

Handles fallback generation for Step 11 when normal execution fails.
"""

from decimal import Decimal
from typing import Any, Dict

from src.api.routes.valuation.steps.base_step import StepOutput, StepStatus
from src.api.schemas import ValuationRequest

# Built-in exceptions don't need to be imported from src.errors
from src.errors import CalculationError, DataQualityError, ValidationError
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)


class FallbackHandler:
    """
    Handler for generating fallback results.

    Responsibilities:
    - Generate Step 11 fallback when normal execution fails
    - Create emergency valuation ranges
    """

    def __init__(self):
        """Initialize FallbackHandler."""
        self.logger = logger

    def generate_step11_fallback(
        self,
        previous_results: Dict[int, StepOutput],
        request: ValuationRequest,
        context: Dict[str, Any],
    ) -> StepOutput:
        """
        Generate a fallback StepOutput for Step 11 when normal execution fails.

        This method creates a minimal valid valuation range using available equity values
        from Step 7/8 and confidence from Step 9, ensuring Step 11 always returns COMPLETED.

        Args:
            previous_results: Results from previous steps
            request: Valuation request
            context: Execution context

        Returns:
            StepOutput with COMPLETED status and fallback valuation range
        """
        from .fallback import (
            EquityValueExtractor,
            ConfidenceScoreExtractor,
            SpreadCalculator,
            ValuationRangeCalculator,
            Step11OutputBuilder,
        )
        
        self.logger.info("🔄 Generating Step 11 fallback result", extra={"step_number": 11})

        try:
            # Extract equity value and confidence score
            equity_value = EquityValueExtractor.extract(previous_results)
            confidence_score = ConfidenceScoreExtractor.extract(previous_results)
            
            # Calculate spread
            spread_pct = SpreadCalculator.calculate(confidence_score)
            
            # Initialize range calculator
            range_calculator = ValuationRangeCalculator(self.logger)
            
            # Calculate valuation range
            if equity_value and equity_value > 0:
                valuation_low, valuation_mid, valuation_high = (
                    range_calculator.calculate_from_equity(equity_value, spread_pct)
                )
            else:
                self.logger.warning(
                    "⚠️ No valid equity value found for Step 11 fallback, calculating from revenue/EBITDA",
                    extra={"step_number": 11},
                )
                valuation_low, valuation_mid, valuation_high, confidence_score = (
                    range_calculator.calculate_from_revenue_ebitda(request, spread_pct)
                )

            self.logger.info(
                "✅ Step 11 fallback result generated",
                extra={
                    "step_number": 11,
                    "valuation_low": valuation_low,
                    "valuation_mid": valuation_mid,
                    "valuation_high": valuation_high,
                    "confidence_score": confidence_score,
                    "fallback_mode": True,
                },
            )

            return Step11OutputBuilder.build_success(
                valuation_low, valuation_mid, valuation_high, confidence_score, previous_results
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
            # Last resort: return minimal valid result with reasonable minimum
            from .fallback import ValuationRangeCalculator, Step11OutputBuilder
            
            self.logger.error(
                "❌ Step 11 fallback generation failed, using reasonable minimum",
                extra={"step_number": 11, "error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )

            range_calculator = ValuationRangeCalculator(self.logger)
            valuation_low, valuation_mid, valuation_high = (
                range_calculator.calculate_emergency_minimum(request)
            )

            return Step11OutputBuilder.build_emergency(
                valuation_low, valuation_mid, valuation_high, e
            )
