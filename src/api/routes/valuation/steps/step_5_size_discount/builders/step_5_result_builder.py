"""
Step 5 Result Builder

Builds result dictionaries and metadata for Step 5 (Size Discount).

SOURCE TRACING:
- Data Source: TITAN_BUSINESS_TYPES_DB (enriched from the Upswitch Index)
- Academic Foundation: Duff & Phelps (2024), Fama-French (1992), Pepperdine (2024)
- Methodology: Size premium adjustment based on revenue tier

ALIGNMENT WITH UPSWITCH PRIMITIVES:
- Primitive 2: Algorithmic Defensibility - formula and sources fully traceable
"""

from decimal import Decimal
from typing import Any, Dict

from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

from ...source_tracing import build_source_metadata

logger = get_logger(__name__)


class Step5ResultBuilder:
    """Builds result dictionaries and metadata for Step 5."""

    def __init__(self, build_pipeline_stage_fn):
        """
        Initialize the result builder.

        Args:
            build_pipeline_stage_fn: Function to build pipeline stage with breakdown
        """
        self.build_pipeline_stage = build_pipeline_stage_fn

    def build_result_dict(
        self,
        ev_low_float: Decimal,
        ev_mid_float: Decimal,
        ev_high_float: Decimal,
        ev_low_before_float: Decimal,
        ev_mid_before_float: Decimal,
        ev_high_before_float: Decimal,
        tier: str,
        base_discount_float: Decimal,
        adjustment_multiplier: Decimal,
        discount_float: Decimal,
        discount_pct: Decimal,
        business_category: any,
        sme_calibration_applied: bool,
        revenue: Decimal,
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
            tier: Revenue tier string
            base_discount_float: Base discount value
            adjustment_multiplier: Adjustment multiplier
            discount_float: Final discount value
            discount_pct: Discount percentage
            business_category: Business category
            sme_calibration_applied: Whether SME calibration was applied
            revenue: Revenue value
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
        return {
            "enterprise_value_low": ev_low_float,
            "enterprise_value_mid": ev_mid_float,
            "enterprise_value_high": ev_high_float,
            "size_tier": tier,
            "base_discount": base_discount_float,
            "adjustment_multiplier": adjustment_multiplier,
            "size_discount_percentage": discount_float,
            "business_category": (
                getattr(business_category, "value", "unknown") if business_category else "unknown"
            ),
            "ev_change": ev_mid_float - ev_mid_before_float,
            "size_discount_note": self._size_discount_note(
                discount_float=discount_float,
                sme_calibration_applied=sme_calibration_applied,
                revenue=revenue,
            ),
            "multiple_before_low": to_decimal(multiple_before_low),
            "multiple_before_mid": to_decimal(multiple_before_mid),
            "multiple_before_high": to_decimal(multiple_before_high),
            "multiple_after_low": to_decimal(multiple_after_low),
            "multiple_after_mid": to_decimal(multiple_after_mid),
            "multiple_after_high": to_decimal(multiple_after_high),
            "discount_applied_to_multiple": discount_pct,
            "current_multiple_low": to_decimal(multiple_after_low),
            "current_multiple_mid": to_decimal(multiple_after_mid),
            "current_multiple_high": to_decimal(multiple_after_high),
            "pipeline_stage": self.build_pipeline_stage(
                tier=tier,
                discount_pct=discount_pct,
                revenue=to_decimal(revenue),
                multiple_before_low=multiple_before_low,
                multiple_before_mid=multiple_before_mid,
                multiple_before_high=multiple_before_high,
                multiple_after_low=multiple_after_low,
                multiple_after_mid=multiple_after_mid,
                multiple_after_high=multiple_after_high,
                metric_value=metric_value,
                ev_mid_before_float=ev_mid_before_float,
                ev_mid_float=ev_mid_float,
            ),
            # ACADEMIC SOURCES: SME-specific research backing size discount
            "academic_sources": [
                {
                    "source_id": "ibbotson_2024",
                    "author": "Ibbotson SBBI",
                    "year": 2024,
                    "title": "Stocks, Bonds, Bills, and Inflation Yearbook",
                    "publisher": "Duff & Phelps",
                    "relevance": "Empirical size premium data for small-cap companies",
                },
                {
                    "source_id": "duff_phelps_2024",
                    "author": "Duff & Phelps",
                    "year": 2024,
                    "title": "Valuation Handbook: Guide to Cost of Capital",
                    "relevance": "Size premiums for companies under €5M revenue",
                },
                {
                    "source_id": "fama_french_1992",
                    "author": "Fama, E.F. & French, K.R.",
                    "year": 1992,
                    "title": "The Cross-Section of Expected Stock Returns",
                    "journal": "Journal of Finance",
                    "relevance": "Foundational research on size effect in asset pricing",
                },
                {
                    "source_id": "pepperdine_2024",
                    "author": "Pepperdine Private Capital Markets Project",
                    "year": 2024,
                    "title": "Private Capital Markets Report",
                    "relevance": "SME transaction multiples for businesses $1M-$50M",
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
        base_discount_float: Decimal,
        base_discount_pct: Decimal,
        adjustment_multiplier: Decimal,
        discount_float: Decimal,
        discount_pct: Decimal,
        tier: str,
        business_category: any,
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
            base_discount_float: Base discount value
            base_discount_pct: Base discount percentage
            adjustment_multiplier: Adjustment multiplier
            discount_float: Final discount value
            discount_pct: Final discount percentage
            tier: Revenue tier string
            business_category: Business category
            data_source: Data source identifier for tracing

        Returns:
            Metadata dictionary with source tracing
        """
        # Build source tracing metadata
        source_metadata = build_source_metadata(
            step_key="step_5_size_discount",
            data_source=data_source,
        )

        return {
            "formula": "Multiple × (1 + size_discount)",
            "calculation_low": f"{ev_low_before_float:,.0f} × (1 + {discount_pct:.1f}%) = {ev_low_float:,.0f}",
            "calculation_mid": f"{ev_mid_before_float:,.0f} × (1 + {discount_pct:.1f}%) = {ev_mid_float:,.0f}",
            "calculation_high": f"{ev_high_before_float:,.0f} × (1 + {discount_pct:.1f}%) = {ev_high_float:,.0f}",
            "ev_low_before": ev_low_before_float,
            "ev_mid_before": ev_mid_before_float,
            "ev_high_before": ev_high_before_float,
            "ev_low_after": ev_low_float,
            "ev_mid_after": ev_mid_float,
            "ev_high_after": ev_high_float,
            "base_discount": base_discount_float,
            "base_discount_pct": base_discount_pct,
            "adjustment_multiplier": adjustment_multiplier,
            "final_discount": discount_float,
            "final_discount_pct": discount_pct,
            "tier_explanation": (
                f"{tier}: Growth maturity evidence produced a {discount_pct:.1f}% premium"
                if discount_float > 0
                else f'{tier}: Base discount {base_discount_pct:.1f}% adjusted by {adjustment_multiplier:.2f}x multiplier for {getattr(business_category, "value", "unknown")} business type'
            ),
            "range_validated": True,
            "source": "Ibbotson SBBI Yearbook, Fama-French (1992), Duff & Phelps (2024)",
            "note": "Size premium reflects higher risk for smaller companies. Business-type adjustments account for industry-specific risk profiles.",
            "precision": "Decimal (bank-grade)",
            "rounding": "ROUND_HALF_EVEN (banker's rounding)",
            # Source tracing (Primitive 2: Algorithmic Defensibility)
            "data_source": source_metadata["data_source"],
            "data_source_name": source_metadata["data_source_name"],
            "source_confidence": source_metadata["source_confidence"],
            "academic_sources": source_metadata["academic_sources"],
            "primary_citation": source_metadata["primary_citation"],
        }

    @staticmethod
    def _size_discount_note(
        *,
        discount_float: Decimal,
        sme_calibration_applied: bool,
        revenue: Decimal,
    ) -> str:
        if discount_float > 0:
            return "Growth maturity premium applied from priced business-context evidence."
        if sme_calibration_applied and revenue < Decimal("5000000"):
            return (
                "Size discount reduced 50% — SME-calibrated multiples capture partial size risk "
                "(Ibbotson/Duff & Phelps: residual 50% still applies per Koller, "
                "Goedhart & Wessels 2020, Ch. 10)."
            )
        return (
            "Size discount applied based on revenue tier. "
            "This discount reflects company-specific size risk beyond database accuracy."
        )
