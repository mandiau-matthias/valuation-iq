"""
Step 4.5: Revenue Trend Adjustment

Applies discount for declining revenue businesses per Damodaran (2012) distressed asset framework.

Academic Support:
- Damodaran (2012): "Investment Valuation" - distressed asset adjustments
- McKinsey (2015): "Valuation" - growth/decline impact on multiples
- Trugman (2017): Revenue trend as key risk factor

AUTOMATIC & MANDATORY: Always executed when historical data available.

UPDATED: 2025-12-20 - Created per comprehensive audit findings
"""

from decimal import Decimal
from typing import List, Optional

from src.api.routes.valuation.triage.step_registry import register_step
from src.domain.risk.correlation_aware_calculator import CorrelationAwareCalculator
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

from .base_step import CalculationStep, StepInput, StepOutput, StepStatus
from .strength_factor_discount_adjustments import (
    annotate_strength_factor_discount_result,
    apply_priced_strength_factor_adjustment,
    strength_factor_discount_adjustment_for_request,
)

logger = get_logger(__name__)


@register_step
class Step45RevenueTrend(CalculationStep):
    """
    Step 4.5: Revenue Trend Adjustment (with Correlation-Aware Calibration)

    Applies multiple discount for declining revenue businesses, with correlation-aware
    calibration to prevent over-conservative valuations when size discount is also applied.

    Positioned after owner concentration (Step 4) and before size discount (Step 5).

    This step addresses a critical gap identified in the comprehensive audit:
    declining revenue businesses trade at significantly lower multiples due to
    sustainability concerns and buyer risk aversion.

    ENHANCED 2025-12-20: Added correlation-aware calibration to account for
    moderate positive correlation (r ≈ 0.40) between size and revenue trend risks.

    Academic Foundation:
    - Damodaran (2012): Distressed asset adjustments for declining businesses
    - McKinsey (2015), Ch. 11: Growth/decline impact on multiples + correlated risk guidance
    - Trugman (2017): Revenue trend as key valuation risk factor
    - RISK_FACTOR_CORRELATION_FRAMEWORK.md: Calibration methodology

    Base Discount Ranges (before calibration):
    - Severe decline (<-20%): -25% discount
    - Moderate decline (-10% to -20%): -18% discount
    - Mild decline (-5% to -10%): -12% discount
    - Flat/slight decline (0% to -5%): -8% discount
    - Growth (>0%): No discount

    Calibration: Base discount is adjusted downward when significant size discount
    is present, to match empirical transaction data and prevent over-discounting.
    """

    def __init__(self):
        """Initialize with correlation-aware calculator."""
        super().__init__()
        self.correlation_calculator = CorrelationAwareCalculator()

    @property
    def step_number(self) -> float:
        """Return step number as float to support decimal step numbers."""
        return 4.5  # Between owner concentration and size discount

    @property
    def step_name(self) -> str:
        return "Revenue Trend Adjustment"

    @property
    def dependencies(self) -> List[int]:
        return [1, 3]  # Requires input validation and base EV

    @property
    def optional_dependencies(self) -> List[int]:
        return [4]  # Prefer owner concentration output, but Step 3 is a valid fallback

    def _historical_year_sort_key(self, year_data: object, index: int) -> tuple[int, int]:
        raw_year = getattr(year_data, "year", None)
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            year = -1
        return (year, index)

    def _get_latest_historical_year(self, request) -> Optional[object]:
        """Return the most recent historical year from an oldest-to-newest series."""
        historical_years = getattr(request, "historical_years_data", None) or []
        if not historical_years:
            return None
        _index, latest = max(
            enumerate(historical_years),
            key=lambda item: self._historical_year_sort_key(item[1], item[0]),
        )
        return latest

    def should_execute(self, input_data: StepInput) -> bool:
        """
        Always execute if historical revenue data available.

        This is an AUTOMATIC & MANDATORY adjustment when we have the data
        to calculate year-over-year revenue growth.
        """
        request = input_data.request

        previous_year_data = self._get_latest_historical_year(request)

        # Check if we have both current and previous year revenue
        has_current_revenue = (
            hasattr(request, "current_year_data")
            and request.current_year_data is not None
            and hasattr(request.current_year_data, "revenue")
            and request.current_year_data.revenue is not None
        )

        has_previous_revenue = (
            previous_year_data is not None
            and hasattr(previous_year_data, "revenue")
            and previous_year_data.revenue is not None
        )

        if not (has_current_revenue and has_previous_revenue):
            if self._has_priced_revenue_trend_evidence(request):
                logger.info(
                    "Revenue trend adjustment will execute from priced strength-factor evidence"
                )
                return True
            # DEBUG: routing decision; "⏭️ Step 4.5 skipped by step logic"
            # at the step orchestrator level carries the canonical INFO.
            logger.debug("Revenue trend adjustment skipped: missing historical revenue data")
            return False

        # Also check that previous revenue is > 0 to avoid division by zero
        prev_revenue = previous_year_data.revenue
        if prev_revenue <= 0:
            if self._has_priced_revenue_trend_evidence(request):
                logger.info(
                    "Revenue trend adjustment will execute from priced strength-factor evidence "
                    "despite invalid previous revenue"
                )
                return True
            logger.warning(
                f"Revenue trend adjustment skipped: invalid previous revenue {prev_revenue}"
            )
            return False

        logger.info(
            f"Revenue trend adjustment will execute: "
            f"previous_year={getattr(previous_year_data, 'year', 'unknown')}, "
            f"revenue_previous={previous_year_data.revenue}, "
            f"revenue_current={request.current_year_data.revenue}"
        )
        return True

    async def execute(self, input_data: StepInput) -> StepOutput:
        """
        Calculate revenue trend adjustment with correlation-aware calibration.

        Process:
        1. Calculate YoY revenue growth rate
        2. Determine base discount based on decline severity
        3. Apply correlation-aware calibration based on size tier
        4. Apply adjusted discount to the current multiple from Step 4 or Step 3
        5. Return adjusted multiple and detailed metadata

        ENHANCED 2025-12-20: Added correlation-aware calibration to prevent
        over-conservative valuations when size discount is also present.
        """
        request = input_data.request

        try:
            previous_year_data = self._get_latest_historical_year(request)

            # Get current multiple from Step 4 (or Step 3 as fallback)
            step_4_output = input_data.previous_results.get(4)
            step_3_output = input_data.previous_results.get(3)

            current_multiple = None
            if step_4_output and step_4_output.result:
                current_multiple = step_4_output.result.get(
                    "current_multiple_mid",
                    step_4_output.result.get(
                        "multiple_after_mid", step_4_output.result.get("adjusted_multiple")
                    ),
                )
            if current_multiple is None and step_3_output and step_3_output.result:
                current_multiple = step_3_output.result.get("current_multiple_mid")
            if current_multiple is None:
                raise ValueError(
                    "Cannot determine current multiple: neither Step 4 nor Step 3 "
                    "provided current_multiple_mid"
                )
            current_multiple = to_decimal(current_multiple)
            if current_multiple <= Decimal("0"):
                raise ValueError(f"current_multiple must be positive, got {current_multiple}")

            (
                strength_factor_adjustment,
                strength_factor_evidence,
            ) = strength_factor_discount_adjustment_for_request(request, "revenue_trend")

            has_historical_pair = self._has_historical_revenue_pair(request, previous_year_data)
            if has_historical_pair:
                # Get current and previous revenue from request structure
                current_revenue = to_decimal(request.current_year_data.revenue)
                previous_revenue = to_decimal(previous_year_data.revenue)
                previous_year = getattr(previous_year_data, "year", None)
                current_year = getattr(request.current_year_data, "year", None)

                # Calculate YoY growth rate
                yoy_growth = (
                    (current_revenue - previous_revenue) / previous_revenue
                    if previous_revenue > 0
                    else Decimal("0.0")
                )

                logger.info(
                    f"Revenue trend analysis: "
                    f"previous_year={previous_year}, "
                    f"current_year={current_year}, "
                    f"revenue_previous={float(previous_revenue):,.0f}, "
                    f"revenue_current={float(current_revenue):,.0f}, "
                    f"YoY growth={float(yoy_growth * 100):.1f}%"
                )

                # Calculate BASE discount based on decline severity
                base_discount = self._calculate_decline_discount(yoy_growth)
                severity = self._get_severity(yoy_growth)

                # Determine size tier for correlation adjustment
                size_tier = self.correlation_calculator.get_size_tier_from_revenue(current_revenue)

                # Apply correlation-aware calibration
                adjusted_discount, calibration_metadata = (
                    self.correlation_calculator.adjust_revenue_trend_discount(
                        base_discount=base_discount,
                        size_tier=size_tier,
                        revenue=current_revenue,
                    )
                )
                rationale = self._get_rationale_with_calibration(
                    yoy_growth,
                    base_discount,
                    adjusted_discount,
                    calibration_metadata,
                )
                adjustment_basis = "Year-over-year revenue growth rate"
                yoy_growth_result = float(yoy_growth)
                yoy_growth_pct_result = float(yoy_growth * 100)
            else:
                if strength_factor_adjustment == 0:
                    raise ValueError("No historical year data available for revenue trend analysis")
                current_revenue = self._current_request_revenue(request)
                previous_revenue = None
                previous_year = None
                current_year = getattr(getattr(request, "current_year_data", None), "year", None)
                base_discount = Decimal("0.0")
                adjusted_discount = Decimal("0.0")
                severity = "maturity_risk"
                size_tier = (
                    self.correlation_calculator.get_size_tier_from_revenue(current_revenue)
                    if current_revenue is not None
                    else "unknown"
                )
                calibration_metadata = {
                    "calibration_applied": False,
                    "size_tier": size_tier,
                    "reduction_percentage": 0.0,
                    "correlation_coefficient": 0.0,
                }
                rationale = (
                    "Revenue trend history is incomplete, but priced growth-maturity evidence "
                    "indicates team capacity is ahead of the revenue base. Applying the bounded "
                    "commercial-efficiency discount from the maturity policy."
                )
                adjustment_basis = "Growth maturity priced evidence"
                yoy_growth_result = None
                yoy_growth_pct_result = None

            discount_before_strength_factor = adjusted_discount
            adjusted_discount = apply_priced_strength_factor_adjustment(
                adjusted_discount,
                strength_factor_adjustment,
                floor=Decimal("-0.30"),
            )
            rationale += self._strength_factor_rationale_suffix(strength_factor_adjustment)

            # Apply ADJUSTED discount to multiple
            adjusted_multiple = current_multiple * (Decimal("1.0") + adjusted_discount)

            # Log the adjustment with calibration details
            if calibration_metadata["calibration_applied"]:
                logger.info(
                    f"Revenue trend adjustment applied WITH correlation calibration: "
                    f"size_tier={size_tier}, "
                    f"base_discount={float(base_discount * 100):.1f}%, "
                    f"adjusted_discount={float(adjusted_discount * 100):.1f}%, "
                    f"multiple {float(current_multiple):.2f}x → {float(adjusted_multiple):.2f}x, "
                    f"severity={severity}"
                )
            else:
                logger.info(
                    f"Revenue trend adjustment applied WITHOUT calibration: "
                    f"discount={float(adjusted_discount * 100):.1f}%, "
                    f"multiple {float(current_multiple):.2f}x → {float(adjusted_multiple):.2f}x, "
                    f"severity={severity}"
                )

            output = StepOutput(
                step_number=self.step_number,
                step_name=self.step_name,
                status=StepStatus.COMPLETED,
                result={
                    "yoy_growth_rate": yoy_growth_result,
                    "yoy_growth_percentage": yoy_growth_pct_result,
                    "base_revenue_trend_adjustment": float(base_discount),
                    "base_revenue_trend_adjustment_percentage": float(base_discount * 100),
                    "revenue_trend_adjustment": float(adjusted_discount),
                    "revenue_trend_adjustment_percentage": float(adjusted_discount * 100),
                    "calibration_applied": calibration_metadata["calibration_applied"],
                    "size_tier": size_tier,
                    "multiple_before": float(current_multiple),
                    "multiple_after": float(adjusted_multiple),
                    "adjusted_multiple": float(adjusted_multiple),
                    "previous_year": previous_year,
                    "current_year": current_year,
                    "revenue_2024": (
                        float(previous_revenue) if previous_revenue is not None else None
                    ),
                    "revenue_2025": (
                        float(current_revenue) if current_revenue is not None else None
                    ),
                    "severity": severity,
                },
                metadata={
                    "academic_source": "Damodaran (2012), McKinsey (2015) Ch. 11, Trugman (2017)",
                    "rationale": rationale,
                    "severity": severity,
                    "severity_description": self._get_severity_description(severity),
                    "adjustment_basis": adjustment_basis,
                    "calculation_method": (
                        "Cascading multiple adjustment with correlation calibration"
                    ),
                    "calibration_metadata": calibration_metadata,
                },
            )
            annotate_strength_factor_discount_result(
                output.result,
                output.metadata,
                discount_key="revenue_trend",
                evidence_rows=strength_factor_evidence,
                adjustment=strength_factor_adjustment,
                discount_before=discount_before_strength_factor,
                discount_after=adjusted_discount,
            )
            return output

        except Exception as e:
            logger.error(f"Error in revenue trend adjustment: {str(e)}", exc_info=True)
            return StepOutput(
                step_number=self.step_number,
                step_name=self.step_name,
                status=StepStatus.FAILED,
                result={
                    "error": str(e),
                    "adjusted_multiple": (
                        float(current_multiple)
                        if "current_multiple" in locals() and current_multiple is not None
                        else None
                    ),
                },
                metadata={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )

    def _calculate_decline_discount(self, yoy_growth: Decimal) -> Decimal:
        """
        Calculate discount based on revenue decline severity.

        Academic Ranges (Damodaran 2012):
        - Severe decline (<-20%): -25% discount
        - Moderate decline (-10% to -20%): -18% discount
        - Mild decline (-5% to -10%): -12% discount
        - Flat/slight decline (0% to -5%): -8% discount
        - Growth (>0%): No discount (or premium handled elsewhere)

        Returns negative Decimal (discount) or zero (no discount)
        """
        if yoy_growth >= Decimal("0.0"):
            # No discount for growth (growth premium handled in Step 5 size discount)
            return Decimal("0.0")
        elif yoy_growth >= Decimal("-0.05"):  # 0% to -5%
            return Decimal("-0.08")  # -8% discount (flat/slight decline)
        elif yoy_growth >= Decimal("-0.10"):  # -5% to -10%
            return Decimal("-0.12")  # -12% discount (mild decline)
        elif yoy_growth >= Decimal("-0.20"):  # -10% to -20%
            return Decimal("-0.18")  # -18% discount (moderate decline)
        else:  # < -20%
            return Decimal("-0.25")  # -25% discount (severe decline)

    def _has_priced_revenue_trend_evidence(self, request: object) -> bool:
        adjustment, evidence = strength_factor_discount_adjustment_for_request(
            request, "revenue_trend"
        )
        return bool(adjustment or evidence)

    def _has_historical_revenue_pair(
        self, request: object, previous_year_data: Optional[object]
    ) -> bool:
        current_year_data = getattr(request, "current_year_data", None)
        current_revenue = getattr(current_year_data, "revenue", None)
        previous_revenue = getattr(previous_year_data, "revenue", None)
        return bool(
            current_revenue is not None
            and previous_revenue is not None
            and to_decimal(previous_revenue) > 0
        )

    def _current_request_revenue(self, request: object) -> Optional[Decimal]:
        for value in (
            getattr(request, "revenue", None),
            getattr(request, "annual_revenue", None),
            getattr(request, "current_revenue", None),
            getattr(getattr(request, "current_year_data", None), "revenue", None),
        ):
            if value is not None and value != "":
                return to_decimal(value)
        return None

    def _get_severity(self, yoy_growth: Decimal) -> str:
        """Get severity label for revenue trend."""
        if yoy_growth >= Decimal("0.0"):
            return "growth"
        elif yoy_growth >= Decimal("-0.05"):
            return "flat"
        elif yoy_growth >= Decimal("-0.10"):
            return "mild_decline"
        elif yoy_growth >= Decimal("-0.20"):
            return "moderate_decline"
        else:
            return "severe_decline"

    def _get_severity_description(self, severity: str) -> str:
        """Get human-readable description of severity level."""
        descriptions = {
            "growth": "Revenue growing or stable",
            "flat": "Slight revenue decline (0% to -5%)",
            "mild_decline": "Mild revenue decline (-5% to -10%)",
            "moderate_decline": "Moderate revenue decline (-10% to -20%)",
            "severe_decline": "Severe revenue decline (>-20%)",
            "maturity_risk": "Growth maturity evidence indicates commercial efficiency risk",
        }
        return descriptions.get(severity, "Unknown severity")

    def _get_rationale(self, yoy_growth: Decimal, adjustment: Decimal) -> str:
        """Generate human-readable rationale for the adjustment (legacy, kept for compatibility)."""
        growth_pct = float(yoy_growth * 100)
        adj_pct = float(adjustment * 100)

        if yoy_growth >= 0:
            return (
                "Revenue growing or stable. No decline discount applied. "
                "Growth premium (if applicable) is handled in the size discount step."
            )
        else:
            return (
                f"Revenue declined {abs(growth_pct):.1f}% year-over-year. "
                f"Applied {abs(adj_pct):.1f}% decline discount per Damodaran (2012). "
                f"Declining revenue businesses trade at lower multiples due to "
                f"sustainability concerns and buyer risk aversion. "
                f"This adjustment reflects the market reality that buyers heavily "
                f"discount businesses with negative revenue trends."
            )

    def _get_rationale_with_calibration(
        self,
        yoy_growth: Decimal,
        base_discount: Decimal,
        adjusted_discount: Decimal,
        calibration_metadata: dict,
    ) -> str:
        """Generate human-readable rationale including calibration details."""
        growth_pct = float(yoy_growth * 100)
        base_pct = float(base_discount * 100)
        adj_pct = float(adjusted_discount * 100)

        if yoy_growth >= 0:
            return (
                "Revenue growing or stable. No decline discount applied. "
                "Growth premium (if applicable) is handled separately."
            )

        # Base rationale
        base_rationale = (
            f"Revenue declined {abs(growth_pct):.1f}% year-over-year. "
            f"Base discount: {abs(base_pct):.1f}% per Damodaran (2012). "
        )

        # Add calibration explanation if applied
        if calibration_metadata["calibration_applied"]:
            reduction_pct = calibration_metadata["reduction_percentage"]
            size_tier = calibration_metadata["size_tier"]
            correlation = calibration_metadata["correlation_coefficient"]

            calibration_rationale = (
                f"Correlation-aware calibration applied: discount reduced by {reduction_pct:.1f}% "
                f"to {abs(adj_pct):.1f}% for {size_tier} company. "
                f"This accounts for moderate positive correlation (r ≈ {correlation:.2f}) between "
                f"size and revenue trend risks, preventing over-conservative valuation. "
                f"Methodology follows McKinsey (2015) Ch. 11 guidance on correlated "
                f"risk adjustments."
            )
        else:
            calibration_rationale = (
                f"Final discount: {abs(adj_pct):.1f}%. No correlation calibration applied "
                f"(no size discount present)."
            )

        return base_rationale + calibration_rationale

    def _strength_factor_rationale_suffix(self, adjustment: Decimal) -> str:
        if adjustment == 0:
            return ""
        return (
            " Priced growth-maturity evidence adjusted the revenue trend by "
            f"{abs(float(adjustment * 100)):.1f}%."
        )
