"""
Step 6: Liquidity Discount Application

Applies illiquidity discount for private company shares.
ALWAYS executes (all private companies lack liquidity).

This step cascades on top of Steps 4-5 (owner concentration and size discounts),
ensuring all discounts are cumulative:
Multiple_final = Multiple_base × (1 + owner_adj) × (1 + size_adj) × (1 + liquidity_adj)
EV_final = Metric × Multiple_final
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.routes.valuation.steps.step_6_liquidity_discount.builders import Step6ResultBuilder
from src.api.routes.valuation.steps.step_6_liquidity_discount.calculators import (
    Step6DiscountCalculator,
)
from src.api.routes.valuation.steps.step_6_liquidity_discount.handlers import Step6ErrorHandler

# Import new modular components
from src.api.routes.valuation.steps.step_6_liquidity_discount.orchestrators import Step6Orchestrator
from src.api.routes.valuation.triage.business_type_triage import BusinessTypeTriageEngine
from src.api.routes.valuation.triage.step_registry import register_step
from src.config.decimal_constants import DecimalConstants
from src.domain.liquidity_discount_adjuster import LiquidityDiscountAdjuster
from src.utils.decimal_helpers import Money, apply_discount, bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger
from src.utils.sole_trader_detector import SoleTraderDetector

logger = get_logger(__name__)


def _current_year_revenue(request: object) -> Optional[Decimal]:
    current_year_data = getattr(request, "current_year_data", None)
    if not current_year_data:
        return None

    revenue = getattr(current_year_data, "revenue", None)
    return to_decimal(revenue) if revenue is not None else None


@register_step
class Step6LiquidityDiscount(CalculationStep):
    """
    Liquidity Discount Application Step.

    Private Company Illiquidity (McKinsey/Bain Standards):
    - Business-type-specific base discounts: -12% to -18%
    - Adjusted for profitability (EBITDA margin > 20%): +2-3% bonus
    - Adjusted for growth (growth > 15%): +3% bonus
    - Adjusted for recurring revenue (>50% or >70%): +3-5% bonus
    - Adjusted for company size (>€10M or >€25M): +2-3% bonus
    - Floor: -30%, Ceiling: -10%

    Cascading Formula: Multiple_adjusted = Multiple_previous × (1 + liquidity_discount)
    Then: EV_adjusted = Metric × Multiple_adjusted
    """

    @property
    def step_number(self) -> int:
        return 6

    @property
    def step_name(self) -> str:
        return "Liquidity Discount"

    def __init__(self):
        self.business_type_triage = BusinessTypeTriageEngine()
        self.liquidity_adjuster = LiquidityDiscountAdjuster()

        # Initialize new modular components
        self.calculator = Step6DiscountCalculator()
        self.error_handler = Step6ErrorHandler(step_name=self.step_name)
        self.result_builder = Step6ResultBuilder(
            build_discount_breakdown_fn=self._build_liquidity_discount_breakdown
        )
        self.orchestrator = Step6Orchestrator(
            liquidity_adjuster=self.liquidity_adjuster,
            business_type_triage=self.business_type_triage,
            calculator=self.calculator,
            result_builder=self.result_builder,
            error_handler=self.error_handler,
            step_name=self.step_name,
        )

    @property
    def dependencies(self) -> List[int]:
        # Only require Step 1 (always executes)
        # Steps 3-5 are optional (fallback logic handles missing steps)
        return [1]

    def should_execute(self, input_data: StepInput) -> bool:
        return True  # Always apply liquidity discount for private companies (but amount varies by business type)

    def _build_liquidity_discount_breakdown(
        self,
        adjustment_breakdown: Dict[str, Any],
        total_discount_pct: Decimal,
        step6_skipped_for_sme: bool,
        revenue: Decimal,
    ) -> Dict[str, Any]:
        """
        Build detailed discount breakdown for Step 6 liquidity discount.

        ENHANCEMENT (2025): Includes component-level breakdown with academic sources.
        """
        from typing import Any, Dict

        if step6_skipped_for_sme:
            # Step 6 skipped for SMEs - explain why
            return {
                "base_discount": Decimal("0.0"),
                "revenue": revenue,
                "sme_status": "skipped",
                "components": [
                    {
                        "name": "Baseline Market Liquidity",
                        "percentage": Decimal("0.0"),
                        "source": "McKinsey (2015), Duff & Phelps (2024)",
                        "description": "Already captured in Step 2 SME calibration (18-20% baseline liquidity removal)",
                    },
                    {
                        "name": "Incremental Illiquidity",
                        "percentage": Decimal("0.0"),
                        "source": "Koeplin et al. (2000)",
                        "description": "Already captured in Step 4 SOLE_TRADER tier (5-10% incremental illiquidity)",
                    },
                ],
                "total": Decimal("0.0"),
                "academic_sources": [
                    'Koeplin et al. (2000): "The Private Company Discount"',
                    'McKinsey (2015): "Valuation: Measuring and Managing the Value of Companies"',
                    'Damodaran (2012): "The Dark Side of Valuation"',
                ],
                "rationale": "Illiquidity fully captured in Steps 2+4 - applying Step 6 would triple-count",
            }

        # Build components from adjustment_breakdown
        components = []

        def _to_pct(val: Any) -> Any:
            """Convert fraction to percentage if value is a small numeric fraction."""
            if isinstance(val, (float, Decimal)) and abs(val) < 1:
                return val * 100
            return val

        # Base discount
        base_discount = adjustment_breakdown.get("base_discount", Decimal("0.0"))
        if base_discount != 0.0:
            components.append(
                {
                    "name": "Base Illiquidity Discount",
                    "percentage": _to_pct(base_discount),
                    "source": "Damodaran (2012)",
                    "description": f'Business-type-specific base illiquidity discount ({adjustment_breakdown.get("business_category", "unknown")})',
                }
            )

        # Profitability bonus
        margin_bonus = adjustment_breakdown.get("margin_bonus", Decimal("0.0"))
        if margin_bonus != 0.0:
            components.append(
                {
                    "name": "Profitability Bonus",
                    "percentage": _to_pct(margin_bonus),
                    "source": "PwC Restricted Stock Studies",
                    "description": "High EBITDA margin reduces illiquidity discount",
                }
            )

        # Growth bonus
        growth_bonus = adjustment_breakdown.get("growth_bonus", Decimal("0.0"))
        if growth_bonus != 0.0:
            components.append(
                {
                    "name": "Growth Rate Bonus",
                    "percentage": _to_pct(growth_bonus),
                    "source": "Emory & Willamette Studies",
                    "description": "High growth rate reduces illiquidity discount",
                }
            )

        # Recurring revenue bonus
        recurring_revenue_bonus = adjustment_breakdown.get(
            "recurring_revenue_bonus", Decimal("0.0")
        )
        if recurring_revenue_bonus != 0.0:
            components.append(
                {
                    "name": "Recurring Revenue Bonus",
                    "percentage": _to_pct(recurring_revenue_bonus),
                    "source": "Koeplin/Sarin/Shapiro (2000)",
                    "description": "High recurring revenue reduces illiquidity discount",
                }
            )

        # Customer concentration adjustment
        customer_concentration_adjustment = adjustment_breakdown.get(
            "customer_concentration_adjustment", Decimal("0.0")
        )
        if customer_concentration_adjustment != 0.0:
            components.append(
                {
                    "name": "Customer Concentration Adjustment",
                    "percentage": _to_pct(customer_concentration_adjustment),
                    "source": "Koeplin/Sarin/Shapiro (2000)",
                    "description": "High client concentration increases buyer transferability risk",
                }
            )

        # Contracted backlog bonus
        contract_backlog_bonus = adjustment_breakdown.get("contract_backlog_bonus", Decimal("0.0"))
        if contract_backlog_bonus != 0.0:
            components.append(
                {
                    "name": "Contracted Backlog Bonus",
                    "percentage": _to_pct(contract_backlog_bonus),
                    "source": "SME transaction diligence calibration",
                    "description": "Signed backlog reduces near-term revenue visibility risk",
                }
            )

        # Size bonus
        size_bonus = adjustment_breakdown.get("size_bonus", Decimal("0.0"))
        if size_bonus != 0.0:
            components.append(
                {
                    "name": "Company Size Bonus",
                    "percentage": _to_pct(size_bonus),
                    "source": "Duff & Phelps (2024)",
                    "description": "Larger companies have better liquidity",
                }
            )

        academic_sources = [
            'Damodaran (2012): "The Dark Side of Valuation"',
            "PwC/Deloitte Restricted Stock Studies (2020)",
            "Emory & Willamette Studies",
            'Koeplin/Sarin/Shapiro (2000): "The Private Company Discount"',
            "Duff & Phelps Valuation Handbook (2024)",
        ]

        return {
            "base_discount": _to_pct(base_discount),
            "profitability_bonus": _to_pct(margin_bonus),
            "growth_bonus": _to_pct(growth_bonus),
            "recurring_revenue_bonus": _to_pct(recurring_revenue_bonus),
            "customer_concentration_adjustment": _to_pct(customer_concentration_adjustment),
            "contract_backlog_bonus": _to_pct(contract_backlog_bonus),
            "size_bonus": _to_pct(size_bonus),
            "components": components,
            "total": total_discount_pct,
            "academic_sources": academic_sources,
        }

    async def execute(self, input_data: StepInput) -> StepOutput:
        """
        Apply liquidity discount with cascading on Steps 4-5.

        Formula: Multiple_adjusted = Multiple_previous × (1 + liquidity_discount)
        Where Multiple_previous cascades from Step 5 (preferred), Step 4, or Step 3 (fallback).

        This ensures discounts are cumulative:
        Multiple_final = Multiple_base × (1 + owner_adj) × (1 + size_adj) × (1 + liquidity_adj)
        """
        request = input_data.request

        logger.info(
            "🔍 Starting Step 6: Liquidity Discount Application",
            extra={
                "step_number": 6,
                "step_name": self.step_name,
                "company_name": getattr(request, "company_name", "N/A"),
                "dependencies": self.dependencies,
                "available_previous_steps": list(input_data.previous_results.keys()),
                "formula": "Multiple_adjusted = Multiple_previous × (1 + liquidity_discount)",
                "cascading_priority": "Step 5 > Step 4 > Step 3",
            },
        )

        step1 = self.get_previous_step_result(1, input_data.previous_results)
        correlation_id = input_data.context.get("correlation_id") if input_data.context else None

        # Handle Step 1 missing with fallback
        if not step1:
            fallback_result = self.error_handler.handle_step1_missing(
                request, list(input_data.previous_results.keys())
            )
            if fallback_result:
                return fallback_result
            # Fallback successful - create step1 dict from request
            revenue_from_request = None
            if hasattr(request, "current_year_data") and request.current_year_data:
                revenue_from_request = getattr(request.current_year_data, "revenue", None)
            if revenue_from_request and revenue_from_request > 0:
                step1 = {"revenue": revenue_from_request}

        # Extract EV source (Step 5 > Step 4 > Step 3)
        step5_result = self.get_previous_step_result(5, input_data.previous_results)
        step4_result = self.get_previous_step_result(4, input_data.previous_results)
        step3_result = self.get_previous_step_result(3, input_data.previous_results)

        step5_available = (
            5 in input_data.previous_results
            and input_data.previous_results[5].status == StepStatus.COMPLETED
            and step5_result is not None
        )
        step4_available = (
            4 in input_data.previous_results
            and input_data.previous_results[4].status == StepStatus.COMPLETED
            and step4_result is not None
        )
        step3_available = (
            3 in input_data.previous_results
            and input_data.previous_results[3].status == StepStatus.COMPLETED
            and step3_result is not None
        )

        base_step, ev_data = self.orchestrator.extract_ev_source(
            step5_result,
            step4_result,
            step3_result,
            step5_available,
            step4_available,
            step3_available,
        )

        if not base_step or not ev_data:
            return self.error_handler.handle_no_ev_source(list(input_data.previous_results.keys()))

        # Apply Step 4.5 (revenue trend) adjusted multiple if Step 5 didn't already incorporate it
        if base_step is not None and base_step <= 4:
            step45_output = input_data.previous_results.get(4.5)
            if (
                step45_output
                and step45_output.status == StepStatus.COMPLETED
                and step45_output.result
                and "adjusted_multiple" in step45_output.result
            ):
                ev_data = dict(ev_data)
                ev_data["current_multiple_mid"] = step45_output.result["adjusted_multiple"]
                if step3_result and step3_result.get("primary_metric_value"):
                    metric_val = to_decimal(step3_result["primary_metric_value"])
                    adj_mult = to_decimal(step45_output.result["adjusted_multiple"])
                    ev_data["enterprise_value_mid"] = float(adj_mult * metric_val)
                base_step = 4.5
                logger.info(
                    "✅ Using Step 4.5 (revenue trend) adjusted multiple as base for liquidity discount",
                    extra={"step_number": 6, "base_step": 4.5},
                )

        # Validate multiples and metric
        current_multiple_mid = to_decimal(ev_data.get("current_multiple_mid", 0))
        metric_value = to_decimal(step3_result.get("primary_metric_value", 0))
        if current_multiple_mid <= 0 or metric_value <= 0:
            return self.error_handler.handle_invalid_multiple_or_metric(
                to_decimal(current_multiple_mid), to_decimal(metric_value), base_step
            )

        logger.debug(
            "📥 Step 6 input data extracted",
            extra={
                "step_number": 6,
                "base_step": base_step,
                "step1_keys": list(step1.keys()) if step1 else [],
                "ev_mid": ev_data.get("enterprise_value_mid") if ev_data else None,
            },
        )

        # Get Step 2 result for SME calibration check
        step2_result = self.get_previous_step_result(2, input_data.previous_results)

        try:
            # Orchestrate main execution
            result_dict, metadata_dict = await self.orchestrator.orchestrate_execution(
                request=request,
                step1=step1,
                step2_result=step2_result,
                step3_result=step3_result,
                ev_data=ev_data,
                base_step=base_step,
                correlation_id=correlation_id,
            )

            # DEBUG: per-step audit; Step 6 Calculation Complete carries the headline.
            logger.debug(
                "🔍 Step 6: VALUE CHAIN - Liquidity Discount Impact",
                extra={
                    "step_number": 6,
                    "ev_mid_before": result_dict.get("ev_change", 0)
                    + result_dict.get("enterprise_value_mid", 0),
                    "ev_mid_after": result_dict.get("enterprise_value_mid", 0),
                    "total_discount_percentage": result_dict.get("total_discount_percentage", 0),
                    "ev_change": result_dict.get("ev_change", 0),
                    "value_chain_step": 6,
                    "next_step": "Step 7 (EV to Equity Conversion)",
                    "correlation_id": correlation_id,
                },
            )

            # Create StepOutput
            return StepOutput(
                step_number=6,
                step_name=self.step_name,
                status=StepStatus.COMPLETED,
                result=result_dict,
                metadata=metadata_dict,
            )

        except Exception as e:
            logger.error(
                f"❌ Step 6 exception occurred: {str(e)}",
                extra={
                    "step_number": 6,
                    "error_type": type(e).__name__,
                    "correlation_id": correlation_id,
                },
                exc_info=True,
            )
            return StepOutput(
                step_number=6,
                step_name=self.step_name,
                status=StepStatus.FAILED,
                result={},
                error=f"Exception during execution: {str(e)}",
            )

    def _extract_recurring_revenue_pct(self, request) -> Optional[Decimal]:
        """
        Extract recurring revenue percentage from request.

        Checks multiple possible sources:
        1. current_year_data.recurring_revenue_percentage
        2. Calculated from recurring_revenue and revenue

        Args:
            request: Valuation request

        Returns:
            Recurring revenue as percentage (0-100), or None if not available
        """
        return self.calculator.extract_recurring_revenue_pct(
            request,
            _current_year_revenue(request),
        )
