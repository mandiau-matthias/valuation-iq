"""
Step 5: Size Discount Application

Applies size premium discount based on company revenue tier.
ALWAYS executes (all private companies have size risk).
"""

from decimal import Decimal
from typing import Any, Dict, List

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.routes.valuation.steps.step_5_size_discount.builders import Step5ResultBuilder
from src.api.routes.valuation.steps.step_5_size_discount.calculators import Step5DiscountCalculator
from src.api.routes.valuation.steps.step_5_size_discount.handlers import Step5ErrorHandler

# Import new modular components
from src.api.routes.valuation.steps.step_5_size_discount.orchestrators import Step5Orchestrator
from src.api.routes.valuation.triage.business_type_triage import BusinessTypeTriageEngine
from src.api.routes.valuation.triage.step_registry import register_step
from src.config.decimal_constants import DecimalConstants
from src.errors import CalculationError, DataQualityError, ValidationError
from src.utils.decimal_helpers import Money, apply_discount, bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger
from src.utils.sole_trader_detector import SoleTraderDetector

logger = get_logger(__name__)


@register_step
class Step5SizeDiscount(CalculationStep):
    """
    Size Discount Application Step.

    McKinsey Size Premium Tiers:
    - < €1M: -25% to -30% (micro-cap)
    - €1M-€5M: -20% to -25% (small-cap)
    - €5M-€25M: -15% to -20% (lower mid-market)
    - €25M-€100M: -10% to -15% (mid-market)
    - > €100M: -5% to -10% (upper mid-market)

    Cascading Formula: Multiple_adjusted = Multiple_previous × (1 + size_discount)
    Then: EV_adjusted = Metric × Multiple_adjusted
    """

    @property
    def step_number(self) -> int:
        return 5

    @property
    def step_name(self) -> str:
        return "Size Discount"

    def __init__(self):
        self.business_type_triage = BusinessTypeTriageEngine()

        # Initialize new modular components
        self.calculator = Step5DiscountCalculator()
        self.error_handler = Step5ErrorHandler(step_name=self.step_name)
        self.result_builder = Step5ResultBuilder(
            build_pipeline_stage_fn=self._build_size_discount_pipeline_stage
        )
        self.orchestrator = Step5Orchestrator(
            business_type_triage=self.business_type_triage,
            calculator=self.calculator,
            result_builder=self.result_builder,
            error_handler=self.error_handler,
            step_name=self.step_name,
        )

    @property
    def dependencies(self) -> List[int]:
        return [1]  # Needs revenue from Step 1 (can run parallel with Step 4)

    def should_execute(self, input_data: StepInput) -> bool:
        return True  # Always apply size discount (but amount varies by business type)

    def _build_size_discount_pipeline_stage(
        self,
        tier: str,
        discount_pct: Decimal,
        revenue: Decimal,
        multiple_before_low,
        multiple_before_mid,
        multiple_before_high,
        multiple_after_low,
        multiple_after_mid,
        multiple_after_high,
        metric_value,
        ev_mid_before_float: Decimal,
        ev_mid_float: Decimal,
    ) -> Dict[str, Any]:
        """
        Build pipeline stage with detailed discount breakdown for Step 5.

        ENHANCEMENT (2025): Includes component-level breakdown with academic sources.
        """
        from typing import Any, Dict

        # Build discount breakdown based on revenue tier
        components = []
        academic_sources = []

        if discount_pct > 0:
            components = [
                {
                    "name": "Growth Maturity Premium",
                    "percentage": discount_pct,
                    "source": "Upswitch business growth maturity policy",
                    "description": (
                        "Revenue and team maturity are aligned at a buyer-grade stage, "
                        "supporting a modest multiple premium"
                    ),
                }
            ]
            academic_sources = [
                "Upswitch Index: Business growth maturity stage policy",
                "Upswitch Index: Stage-specific operating readiness data points",
            ]
        elif discount_pct == 0.0:
            # Step 5 disabled for SMEs <€5M (handled in Step 2 calibration)
            components = []
            academic_sources = [
                'McKinsey (2015): "Size Premium in Private Markets"',
                'Banz (1981): "The Relationship Between Return and Market Value"',
                'Fama-French (1992): "The Cross-Section of Expected Stock Returns"',
            ]
        elif revenue < 10_000_000:  # €5M-€10M
            components = [
                {
                    "name": "Size Premium Removal",
                    "percentage": discount_pct,
                    "source": "Banz (1981), Fama-French (1992)",
                    "description": "Small-cap companies have higher required returns - size premium removed",
                }
            ]
            academic_sources = [
                'Banz (1981): "The Relationship Between Return and Market Value of Common Stocks"',
                'Fama-French (1992): "The Cross-Section of Expected Stock Returns"',
                'McKinsey (2015): "Valuation: Measuring and Managing the Value of Companies", Chapter 8',
            ]
        elif revenue < 25_000_000:  # €10M-€25M
            components = [
                {
                    "name": "Size Premium Removal",
                    "percentage": discount_pct,
                    "source": "Banz (1981), Fama-French (1992)",
                    "description": "Mid-market companies have moderate size premium",
                }
            ]
            academic_sources = [
                'Banz (1981): "The Relationship Between Return and Market Value of Common Stocks"',
                'Fama-French (1992): "The Cross-Section of Expected Stock Returns"',
                'McKinsey (2015): "Valuation: Measuring and Managing the Value of Companies", Chapter 8',
            ]
        else:  # €25M-€50M
            components = [
                {
                    "name": "Size Premium Removal",
                    "percentage": discount_pct,
                    "source": "Banz (1981), Fama-French (1992)",
                    "description": "Upper mid-market companies have minimal size premium",
                }
            ]
            academic_sources = [
                'Banz (1981): "The Relationship Between Return and Market Value of Common Stocks"',
                'Fama-French (1992): "The Cross-Section of Expected Stock Returns"',
                'McKinsey (2015): "Valuation: Measuring and Managing the Value of Companies", Chapter 8',
            ]

        discount_breakdown = {
            "revenue_tier": tier,
            "revenue": revenue,
            "base_discount": discount_pct,
            "components": components,
            "total": discount_pct,
            "academic_sources": academic_sources,
        }

        return {
            "step_number": 5,
            "step_name": ("Growth Maturity Premium" if discount_pct > 0 else "Size Discount"),
            "discount_type": "growth_maturity" if discount_pct > 0 else "size",
            "discount_percentage": discount_pct,
            # ENHANCEMENT (2025): Include low/mid/high multiples for complete transparency
            "multiple_before_low": to_decimal(multiple_before_low),
            "multiple_before_mid": to_decimal(multiple_before_mid),
            "multiple_before_high": to_decimal(multiple_before_high),
            "multiple_after_low": to_decimal(multiple_after_low),
            "multiple_after_mid": to_decimal(multiple_after_mid),
            "multiple_after_high": to_decimal(multiple_after_high),
            # Legacy fields (for backward compatibility)
            "multiple_before": to_decimal(multiple_before_mid),
            "multiple_after": to_decimal(multiple_after_mid),
            "metric_value": to_decimal(metric_value),
            "ev_before": ev_mid_before_float,
            "ev_after": ev_mid_float,
            "explanation": (
                f"{tier} company - {discount_pct:.1f}% maturity premium"
                if discount_pct > 0
                else f"{tier} company - {abs(discount_pct):.1f}% discount"
            ),
            "description": (
                f"Growth Maturity Premium: {tier} maturity premium applied to multiple"
                if discount_pct > 0
                else f"Size Discount: {tier} company discount applied to multiple"
            ),
            # ENHANCEMENT (2025): Detailed discount breakdown with components and sources
            "discount_breakdown": discount_breakdown,
        }

    async def execute(self, input_data: StepInput) -> StepOutput:
        """
        Apply size discount based on company revenue tier.

        Formula: Multiple_adjusted = Multiple_previous × (1 + size_discount)
        Where size_discount is negative (discount) based on revenue tier.

        McKinsey Size Premium Tiers:
        - < €1M: -25% to -30% (micro-cap)
        - €1M-€5M: -20% to -25% (small-cap)
        - €5M-€25M: -15% to -20% (lower mid-market)
        - €25M-€100M: -10% to -15% (mid-market)
        - > €100M: -5% to -10% (upper mid-market)
        """
        request = input_data.request

        logger.info(
            "🔍 Starting Step 5: Size Discount Application",
            extra={
                "step_number": 5,
                "step_name": self.step_name,
                "company_name": getattr(request, "company_name", "N/A"),
                "dependencies": self.dependencies,
                "available_previous_steps": list(input_data.previous_results.keys()),
                "formula": "Multiple_adjusted = Multiple_previous × (1 + size_discount)",
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

        # Get EV source (Step 4 preferred, Step 3 fallback)
        ev_source_step = None
        ev_data = None
        step3_result = None

        step3_output = input_data.previous_results.get(3)
        if step3_output and step3_output.status == StepStatus.COMPLETED:
            step3_result = step3_output.result

        step4_output = input_data.previous_results.get(4)
        if step4_output and step4_output.status == StepStatus.COMPLETED:
            step4_result = step4_output.result
            if step4_result and "enterprise_value_mid" in step4_result:
                ev_source_step = 4
                ev_data = step4_result
                logger.debug(
                    "✅ Using Step 4 (owner concentration) result as base for size discount",
                    extra={"step_number": 5, "ev_source_step": 4},
                )

        if not ev_data and step3_result and "enterprise_value_mid" in step3_result:
            ev_source_step = 3
            ev_data = step3_result
            logger.info(
                "✅ Using Step 3 (base EV) result as base for size discount",
                extra={"step_number": 5, "ev_source_step": 3},
            )

        if not ev_data:
            return self.error_handler.handle_no_ev_source(
                list(input_data.previous_results.keys()),
                bool(step4_output and step4_output.status == StepStatus.COMPLETED),
                bool(step3_output and step3_output.status == StepStatus.COMPLETED),
            )

        # Apply Step 4.5 (revenue trend) adjusted multiple if available
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
            ev_source_step = 4.5
            logger.info(
                "✅ Using Step 4.5 (revenue trend) adjusted multiple as base for size discount",
                extra={"step_number": 5, "ev_source_step": 4.5},
            )

        # Validate revenue
        revenue = to_decimal(step1.get("revenue", 0) or 0)
        if revenue <= 0:
            return self.error_handler.handle_invalid_revenue(to_decimal(revenue))

        # Get Step 2 result for SME calibration check
        step2_result = self.get_previous_step_result(2, input_data.previous_results)

        # Validate Step 3 result for metric value
        if not step3_result:
            return self.error_handler.handle_step3_missing_for_metric(
                list(input_data.previous_results.keys())
            )

        # Validate multiples and metric
        current_multiple_mid = to_decimal(ev_data.get("current_multiple_mid", 0))
        metric_value = to_decimal(step3_result.get("primary_metric_value", 0))
        if current_multiple_mid <= 0 or metric_value <= 0:
            return self.error_handler.handle_invalid_multiple_or_metric(
                to_decimal(current_multiple_mid), to_decimal(metric_value), ev_source_step
            )

        logger.debug(
            "📥 Step 5 input data extracted",
            extra={
                "step_number": 5,
                "step1_keys": list(step1.keys()) if step1 else [],
                "ev_source_step": ev_source_step,
                "ev_data_keys": list(ev_data.keys()) if ev_data else [],
                "revenue": step1.get("revenue"),
                "ev_mid": ev_data.get("enterprise_value_mid"),
            },
        )

        try:
            # Orchestrate main execution
            result_dict, metadata_dict = await self.orchestrator.orchestrate_execution(
                request=request,
                step1=step1,
                step2_result=step2_result,
                ev_data=ev_data,
                ev_source_step=ev_source_step,
                step3_result=step3_result,
                correlation_id=correlation_id,
            )

            # DEBUG: per-step audit; Step 5 Calculation Complete carries the headline.
            logger.debug(
                "🔍 Step 5: VALUE CHAIN - Size Discount Impact",
                extra={
                    "step_number": 5,
                    "ev_mid_before": result_dict.get("ev_change", 0)
                    + result_dict.get("enterprise_value_mid", 0),
                    "ev_mid_after": result_dict.get("enterprise_value_mid", 0),
                    "size_discount_percentage": result_dict.get("size_discount_percentage", 0),
                    "ev_change": result_dict.get("ev_change", 0),
                    "value_chain_step": 5,
                    "next_step": "Step 6 (Liquidity Discount)",
                    "correlation_id": correlation_id,
                },
            )

            # Create StepOutput
            return StepOutput(
                step_number=5,
                step_name=self.step_name,
                status=StepStatus.COMPLETED,
                result=result_dict,
                metadata=metadata_dict,
            )

        except (
            CalculationError,
            ValidationError,
            DataQualityError,
            ValueError,
            TypeError,
            AttributeError,
        ) as e:
            logger.error(
                f"❌ Step 5 exception occurred: {str(e)}",
                extra={
                    "step_number": 5,
                    "error_type": type(e).__name__,
                    "correlation_id": correlation_id,
                },
                exc_info=True,
            )
            return StepOutput(
                step_number=5,
                step_name=self.step_name,
                status=StepStatus.FAILED,
                result={},
                error=f"Exception during execution: {str(e)}",
            )
