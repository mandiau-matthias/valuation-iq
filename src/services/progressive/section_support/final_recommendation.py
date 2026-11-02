"""Final recommendation helpers for progressive valuation sections."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol

from src.utils.decimal_helpers import from_decimal, to_decimal


class MultiplesValuationCoordinator(Protocol):
    def calculate_multiples_valuation(
        self,
        collected_data: Mapping[str, object],
        industry: str,
    ) -> Mapping[str, object]: ...


def calculate_dcf_value(revenue_decimal: Decimal, growth_rate_decimal: Decimal) -> float:
    """Calculate DCF-based valuation component."""
    dcf_value_decimal = (
        revenue_decimal * Decimal("3.5") * (Decimal("1") + (growth_rate_decimal / Decimal("100")))
    )
    return from_decimal(dcf_value_decimal)


def calculate_multiples_value(
    valuation_coordinator: MultiplesValuationCoordinator,
    collected_data: Mapping[str, object],
    industry: str,
    revenue_decimal: Decimal,
    ebitda_decimal: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Calculate multiples-based valuation component and methodology weights."""
    multiples_data = valuation_coordinator.calculate_multiples_valuation(
        collected_data,
        industry,
    )
    if multiples_data.get("blocked") or not multiples_data.get("has_valid_data"):
        return Decimal("0"), Decimal("100"), Decimal("0")

    revenue_multiple_decimal = to_decimal(multiples_data.get("ev_revenue_multiple", 1.0))
    ebitda_multiple_decimal = to_decimal(multiples_data.get("ev_ebitda_multiple", 1.0))

    if ebitda_decimal > Decimal("0"):
        multiples_value_decimal = revenue_decimal * revenue_multiple_decimal * Decimal(
            "0.4"
        ) + ebitda_decimal * ebitda_multiple_decimal * Decimal("0.6")
        return multiples_value_decimal, Decimal("60"), Decimal("40")

    multiples_value_decimal = revenue_decimal * revenue_multiple_decimal
    return multiples_value_decimal, Decimal("50"), Decimal("50")


def calculate_blended_valuation(
    dcf_value_decimal: Decimal,
    multiples_value_decimal: Decimal,
    dcf_weight_decimal: Decimal,
    multiples_weight_decimal: Decimal,
) -> tuple[float, float, float]:
    """Calculate final blended valuation with low/mid/high range."""
    final_value_mid_decimal = dcf_value_decimal * dcf_weight_decimal / Decimal(
        "100"
    ) + multiples_value_decimal * multiples_weight_decimal / Decimal("100")
    final_value_mid = from_decimal(final_value_mid_decimal)
    final_value_low = from_decimal(final_value_mid_decimal * Decimal("0.80"))
    final_value_high = from_decimal(final_value_mid_decimal * Decimal("1.20"))
    return final_value_low, final_value_mid, final_value_high


def build_methodology_rationale(
    ebitda: float,
    dcf_weight: float,
    multiples_weight: float,
) -> str:
    """Build methodology rationale text."""
    if ebitda > 0:
        return (
            f"Blended approach using {dcf_weight}% DCF and {multiples_weight}% "
            "market multiples. Strong profitability supports DCF weighting."
        )
    return (
        f"Balanced approach using {dcf_weight}% DCF and {multiples_weight}% "
        "market multiples. Revenue multiples provide market validation."
    )


def build_executive_summary(
    company_name: str,
    revenue: float,
    ebitda: float,
    growth_rate: float,
) -> str:
    """Build executive summary text."""
    growth_desc = "strong" if growth_rate > 15 else "solid"
    profitability_desc = (
        (
            "excellent"
            if ebitda / revenue > 0.2
            else "healthy" if ebitda / revenue > 0.1 else "developing"
        )
        if revenue > 0
        else "developing"
    )
    conclusion = (
        "Strong growth trajectory and market position support premium valuation."
        if growth_rate > 15
        else "Stable performance with opportunities for value enhancement through operational improvements."
    )
    return (
        f"{company_name} demonstrates {growth_desc} fundamentals with revenue of €{revenue:,.0f} "
        f"and {profitability_desc} profitability. The valuation reflects industry positioning, "
        f"growth potential, and operational metrics. {conclusion}"
    )


def get_strategic_recommendations() -> list[dict[str, str]]:
    """Get standard strategic recommendations."""
    return [
        {
            "title": "Accelerate Growth",
            "description": "Focus on market expansion and new customer acquisition to drive revenue growth",
            "impact": "+15-20% valuation increase",
        },
        {
            "title": "Improve Profitability",
            "description": "Optimize operations and cost structure to enhance EBITDA margins",
            "impact": "+10-15% valuation increase",
        },
        {
            "title": "Reduce Owner Dependency",
            "description": "Build management team and document processes for smoother transition",
            "impact": "+20-25% valuation increase",
        },
        {
            "title": "Strengthen Market Position",
            "description": "Invest in differentiation, brand building, and competitive advantages",
            "impact": "+10-12% valuation increase",
        },
    ]
