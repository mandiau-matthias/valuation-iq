"""Industry comparison payload builder for progressive valuation sections."""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Mapping, Protocol

from src.utils.core.data_extraction_helpers import (
    extract_growth_rate_from_collected_data,
    extract_revenue_from_collected_data,
)
from src.utils.decimal_helpers import from_decimal, to_decimal


class IndustryComparisonCoordinator(Protocol):
    """Coordinator methods required by the industry-comparison section."""

    def get_industry_multiples(
        self,
        collected_data: Mapping[str, object],
        industry: str,
        *,
        business_type_id: str | None = None,
    ) -> dict[str, object]:
        """Return industry multiple data for the current business."""

    def get_industry_benchmarks(
        self,
        collected_data: Mapping[str, object],
        industry: str,
    ) -> dict[str, object]:
        """Return industry benchmark data for the current business."""

    def generate_comparable_companies(
        self,
        industry: str,
        *multiples: object,
        business_type_id: str | None = None,
    ) -> list[dict[str, object]]:
        """Return comparable company rows for the section."""

    def determine_market_position(
        self,
        your_multiple: float,
        industry_avg_multiple: float,
    ) -> str:
        """Return display copy for market position."""


def build_industry_comparison_section(
    *,
    collected_data: Mapping[str, object],
    industry: str,
    business_type_id: str | None,
    industry_coordinator: IndustryComparisonCoordinator,
) -> dict[str, object]:
    """Build the progressive industry-comparison section payload."""
    revenue_decimal, has_revenue = extract_revenue_from_collected_data(collected_data)
    growth_rate = extract_growth_rate_from_collected_data(collected_data)

    if not has_revenue:
        return {
            "industry": industry,
            "your_multiple": None,
            "industry_avg_multiple": None,
            "industry_max_multiple": None,
            "growth_rate": growth_rate,
            "industry_avg_growth": None,
            "ebitda_margin": None,
            "industry_avg_margin": None,
            "comparable_companies": [],
            "comparable_count": 0,
            "market_position": "Provide revenue data to see industry comparison",
            "competitive_advantages": [],
            "has_valid_data": False,
            "confidence": 0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "phase": 1,
        }

    multiples_data = industry_coordinator.get_industry_multiples(
        collected_data,
        industry,
        business_type_id=business_type_id,
    )
    your_multiple = multiples_data.get("your_multiple")
    industry_avg_multiple = multiples_data.get("industry_avg_multiple")
    industry_max_multiple = multiples_data.get("industry_max_multiple")

    benchmarks_data = industry_coordinator.get_industry_benchmarks(collected_data, industry)
    industry_avg_growth = benchmarks_data.get("industry_avg_growth")
    industry_avg_margin = benchmarks_data.get("industry_avg_margin")
    ebitda_margin = benchmarks_data.get("ebitda_margin")

    revenue_multiple_decimal = (
        to_decimal(industry_avg_multiple) if industry_avg_multiple else Decimal("1.0")
    )
    revenue_multiple_float = from_decimal(revenue_multiple_decimal)
    comparable_companies = industry_coordinator.generate_comparable_companies(
        industry,
        revenue_multiple_float,
        business_type_id=business_type_id,
    )

    your_multiple_decimal = to_decimal(your_multiple) if your_multiple else Decimal("0")
    industry_avg_multiple_decimal = (
        to_decimal(industry_avg_multiple) if industry_avg_multiple else Decimal("0")
    )
    market_position = industry_coordinator.determine_market_position(
        from_decimal(your_multiple_decimal),
        from_decimal(industry_avg_multiple_decimal),
    )

    return {
        "industry": industry,
        "your_multiple": your_multiple,
        "industry_avg_multiple": industry_avg_multiple,
        "industry_max_multiple": industry_max_multiple,
        "growth_rate": growth_rate,
        "industry_avg_growth": industry_avg_growth,
        "ebitda_margin": ebitda_margin,
        "industry_avg_margin": industry_avg_margin,
        "comparable_companies": comparable_companies,
        "comparable_count": len(comparable_companies),
        "market_position": market_position,
        "competitive_advantages": [
            "Established market presence",
            "Strong customer relationships",
            "Proven business model",
        ],
        "has_valid_data": True,
        "confidence": 50,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "phase": 1,
    }
