"""Growth metrics payload builder for progressive valuation sections."""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Mapping

from src.services.infrastructure.translations import get_translations, normalize_report_locale
from src.utils.core.data_extraction_helpers import (
    extract_growth_rate_from_collected_data,
    extract_revenue_from_collected_data,
)
from src.utils.decimal_helpers import from_decimal
from src.utils.filing_year_labels import format_year_column_with_filing_role
from src.utils.fiscal_year import get_current_filing_year


def build_growth_metrics_section(
    *,
    context: Mapping[str, object],
    collected_data: Mapping[str, object],
) -> dict[str, object]:
    """Build the progressive growth-metrics section payload."""
    growth_rate_decimal = extract_growth_rate_from_collected_data(collected_data)
    revenue_decimal, _ = extract_revenue_from_collected_data(collected_data)
    revenue = from_decimal(revenue_decimal)
    growth_rate = from_decimal(growth_rate_decimal)

    cagr_3y = growth_rate
    industry_growth = 10.0
    projected_growth_decimal = growth_rate_decimal * Decimal("0.9")
    projected_growth = from_decimal(projected_growth_decimal)

    current_year = get_current_filing_year()
    growth_factor_1_decimal = Decimal("1") + (growth_rate_decimal / Decimal("100"))
    growth_factor_2_decimal = growth_factor_1_decimal ** Decimal("2")
    historical_revenue = [
        {
            "year": current_year - 2,
            "revenue": from_decimal(revenue_decimal / growth_factor_2_decimal),
        },
        {
            "year": current_year - 1,
            "revenue": from_decimal(revenue_decimal / growth_factor_1_decimal),
        },
        {"year": current_year, "revenue": revenue},
    ]

    base_y = max(h["year"] for h in historical_revenue)
    country_code = (
        str(context.get("country_code") or collected_data.get("country_code") or "BE")
        .strip()
        .upper()
        or "BE"
    )
    translations = get_translations(
        normalize_report_locale(str(context.get("locale") or collected_data.get("locale") or "en")),
        country_code=country_code,
    )
    for row in historical_revenue:
        row["year_display"] = format_year_column_with_filing_role(
            row["year"],
            base_y,
            translations,
        )

    if growth_rate > 20:
        growth_impact = (
            "Strong growth trajectory significantly enhances valuation multiples and investor "
            "confidence."
        )
    elif growth_rate > 10:
        growth_impact = (
            "Solid growth rate positively influences valuation and business sustainability."
        )
    else:
        growth_impact = (
            "Moderate growth rate reflects stable business with potential for acceleration."
        )

    return {
        "growth_rate": growth_rate,
        "cagr_3y": cagr_3y,
        "industry_growth": industry_growth,
        "projected_growth": projected_growth,
        "historical_revenue": historical_revenue,
        "years_of_data": len(historical_revenue),
        "growth_drivers": [
            "Market expansion",
            "Product innovation",
            "Customer acquisition",
            "Operational scaling",
        ],
        "growth_impact": growth_impact,
        "confidence": 65,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "phase": 2,
    }
