"""
Step 8 Orchestrator

Orchestrates the main execution flow for Step 8 Ownership Adjustment.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...base_step import StepOutput, StepStatus
from ..builders.step_8_result_builder import Step8ResultBuilder
from ..calculators.step_8_adjustment_calculator import Step8AdjustmentCalculator
from ..handlers.step_8_error_handler import Step8ErrorHandler

logger = get_logger(__name__)


class Step8Orchestrator:
    """Orchestrates the main execution flow for Step 8."""

    def __init__(self, step_name: str, business_types_repo: Optional[object] = None):
        """
        Initialize the orchestrator.

        Args:
            step_name: Step name for StepOutput
            business_types_repo: Business types repository (optional)
        """
        self.step_name = step_name
        self.error_handler = Step8ErrorHandler(step_name)
        self.calculator = Step8AdjustmentCalculator(business_types_repo)
        self.result_builder = Step8ResultBuilder(step_name)

    async def orchestrate_execution(
        self, request: any, step7_result: Dict[str, Any], correlation_id: Optional[str]
    ) -> StepOutput:
        """
        Orchestrate the main execution flow.

        Args:
            request: Valuation request
            step7_result: Step 7 result dictionary
            correlation_id: Correlation ID for tracing

        Returns:
            StepOutput with calculation results
        """
        # Extract equity values from Step 7
        equity_low, equity_mid, equity_high = self.calculator.extract_equity_values(step7_result)

        logger.debug(
            "📥 Step 8 input data extracted",
            extra={
                "step_number": 8,
                "equity_low": to_decimal(equity_low),
                "equity_mid": to_decimal(equity_mid),
                "equity_high": to_decimal(equity_high),
                "source": "Step 7 (EV to Equity Conversion)",
            },
        )

        # Extract ownership data from request
        ownership_data = self.calculator.extract_ownership_data(request)
        shares_for_sale = ownership_data["shares_for_sale"]
        number_of_owners = ownership_data["number_of_owners"]
        business_type_id = ownership_data["business_type_id"]
        revenue = ownership_data["revenue"]

        logger.info(
            "📊 Ownership data extracted",
            extra={
                "step_number": 8,
                "shares_for_sale_pct": shares_for_sale,
                "number_of_owners": number_of_owners,
                "business_type_id": business_type_id,
                "ownership_type": (
                    "Majority (>50%)"
                    if shares_for_sale is not None and shares_for_sale > 50
                    else (
                        "Minority (<50%)"
                        if shares_for_sale is not None and shares_for_sale < 50
                        else "Deadlock (50%)"
                    )
                    if shares_for_sale is not None
                    else "Unknown"
                ),
            },
        )

        # Calculate ownership adjustment
        adjustment_result = self.calculator.calculate_adjustment(
            shares_for_sale, business_type_id, revenue, number_of_owners, request
        )

        # Extract adjustment details
        adjustment_type = adjustment_result["adjustment_type"]
        adjustment_factor = to_decimal(str(adjustment_result["adjustment_factor"]))
        adjustment_percentage = adjustment_result.get("adjustment_percentage", 0)
        ownership_percentage = shares_for_sale / Decimal("100.0")
        ownership_multiplier = ownership_percentage

        # Apply adjustments to equity values
        adjusted_equity_low, adjusted_equity_mid, adjusted_equity_high = (
            self.calculator.apply_adjustments(
                equity_low, equity_mid, equity_high, ownership_percentage * 100, adjustment_factor
            )
        )

        # Convert to float for JSON serialization
        equity_low_float = from_decimal(equity_low, 2)
        equity_mid_float = from_decimal(equity_mid, 2)
        equity_high_float = from_decimal(equity_high, 2)
        adjusted_equity_low_float = from_decimal(adjusted_equity_low, 2)
        adjusted_equity_mid_float = from_decimal(adjusted_equity_mid, 2)
        adjusted_equity_high_float = from_decimal(adjusted_equity_high, 2)

        # Comprehensive summary logging
        logger.info(
            "📊 Step 8: Ownership Adjustment - Calculation Complete",
            extra={
                "step_number": 8,
                "step_name": "Ownership Adjustment",
                "status": "COMPLETED",
                "inputs": {
                    "equity_value_low": equity_low_float,
                    "equity_value_mid": equity_mid_float,
                    "equity_value_high": equity_high_float,
                    "shares_for_sale_pct": shares_for_sale,
                    "ownership_percentage": ownership_percentage,
                },
                "calculation": {
                    "formula": "Adjusted Equity = Equity × (Shares % / 100) × (1 + Adjustment %)",
                    "adjustment_type": adjustment_type,
                    "adjustment_percentage": adjustment_result["adjustment_percentage"],
                    "adjustment_factor": to_decimal(adjustment_factor),
                    "ownership_multiplier": ownership_multiplier,
                    "intermediate_values": {
                        "ownership_multiplier": ownership_multiplier,
                        "adjustment_factor": to_decimal(adjustment_factor),
                    },
                },
                "outputs": {
                    "ownership_adjusted_equity_low": adjusted_equity_low_float,
                    "ownership_adjusted_equity_mid": adjusted_equity_mid_float,
                    "ownership_adjusted_equity_high": adjusted_equity_high_float,
                },
                "adjustments": {
                    "ownership_adjustment_pct": adjustment_result["adjustment_percentage"],
                    "adjustment_type": adjustment_type,
                    "tier": adjustment_result.get("tier", "N/A"),
                },
                "metadata": {
                    "business_type_calibration": adjustment_result.get(
                        "business_type_calibration", {}
                    ),
                    "revenue_adjustment": adjustment_result.get("revenue_adjustment", {}),
                    "rationale": adjustment_result.get("rationale", ""),
                    "precision": "Decimal (bank-grade)",
                    "rounding": "ROUND_HALF_EVEN (banker's rounding)",
                    "academic_reference": "McKinsey Valuation (2015), Bain Private Equity Guide (2020)",
                },
            },
        )

        # CRITICAL: Value chain logging for auditability
        logger.info(
            "🔍 Step 8: VALUE CHAIN AUDIT - Ownership Adjustment Output",
            extra={
                "step_number": 8,
                "step7_equity_value_mid": equity_mid_float,
                "ownership_adjusted_equity_mid": adjusted_equity_mid_float,
                "shares_for_sale_pct": shares_for_sale,
                "adjustment_type": adjustment_type,
                "adjustment_percentage": adjustment_result["adjustment_percentage"],
                "value_chain_step": 8,
                "next_step": "Step 10 (Range Methodology)",
                "correlation_id": correlation_id,
                "note": "Step 8 outputs ownership_adjusted_equity_mid AND preserves original equity_value_mid for reference. Step 10 should use ownership_adjusted_equity_mid if Step 8 executed, otherwise use Step 7 equity_value_mid.",
            },
        )

        logger.info(
            f"✅ Ownership adjustment complete",
            extra={
                "step_number": 8,
                "shares_for_sale_pct": shares_for_sale,
                "ownership_percentage": ownership_percentage,
                "adjustment_type": adjustment_type,
                "adjustment_factor": to_decimal(adjustment_factor),
                "adjustment_percentage": adjustment_result["adjustment_percentage"],
                "equity_low_before": equity_low_float,
                "equity_mid_before": equity_mid_float,
                "equity_high_before": equity_high_float,
                "adjusted_equity_low": adjusted_equity_low_float,
                "adjusted_equity_mid": adjusted_equity_mid_float,
                "adjusted_equity_high": adjusted_equity_high_float,
                "formula_mid": f"{equity_mid_float:,.0f} × {ownership_percentage:.2%} × {to_decimal(adjustment_factor):.4f} = {adjusted_equity_mid_float:,.0f}",
                "formula_low": f"{equity_low_float:,.0f} × {ownership_percentage:.2%} × {to_decimal(adjustment_factor):.4f} = {adjusted_equity_low_float:,.0f}",
                "formula_high": f"{equity_high_float:,.0f} × {ownership_percentage:.2%} × {to_decimal(adjustment_factor):.4f} = {adjusted_equity_high_float:,.0f}",
                "change_mid_pct": (
                    ((adjusted_equity_mid_float - equity_mid_float) / equity_mid_float * 100)
                    if equity_mid_float > 0
                    else 0
                ),
                "precision": "Decimal (bank-grade)",
                "rounding": "ROUND_HALF_EVEN (banker's rounding)",
            },
        )

        # Build result and metadata
        result_dict = self.result_builder.build_result_dict(
            adjusted_equity_low_float,
            adjusted_equity_mid_float,
            adjusted_equity_high_float,
            equity_low_float,
            equity_mid_float,
            equity_high_float,
            shares_for_sale,
            adjustment_type,
            adjustment_percentage,
            to_decimal(adjustment_factor),
            ownership_multiplier,
        )

        metadata_dict = self.result_builder.build_metadata_dict(
            equity_low_float,
            equity_mid_float,
            equity_high_float,
            adjusted_equity_low_float,
            adjusted_equity_mid_float,
            adjusted_equity_high_float,
            shares_for_sale,
            ownership_percentage,
            ownership_multiplier,
            adjustment_type,
            adjustment_percentage,
            to_decimal(adjustment_factor),
            adjustment_result,
        )

        return StepOutput(
            step_number=8,
            step_name=self.step_name,
            status=StepStatus.COMPLETED,
            result=result_dict,
            metadata=metadata_dict,
        )
