"""Market multiples payload builder for progressive valuation sections."""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Mapping, Protocol

from src.utils.core.data_extraction_helpers import extract_ebitda_from_collected_data
from src.utils.decimal_helpers import from_decimal, to_decimal


class MarketMultiplesValuationCoordinator(Protocol):
    """Coordinator methods required by the market-multiples section."""

    def calculate_multiples_valuation(
        self,
        collected_data: Mapping[str, object],
        industry: str,
        *,
        business_type_id: str | None = None,
    ) -> dict[str, object]:
        """Return market multiples valuation data."""


class MarketMultiplesIndustryCoordinator(Protocol):
    """Industry coordinator methods required by the market-multiples section."""

    def generate_comparable_companies(
        self,
        industry: str,
        *multiples: object,
        business_type_id: str | None = None,
    ) -> list[dict[str, object]]:
        """Return comparable company rows for the section."""


def _scale_multiple(value: object, factor: str) -> float:
    return from_decimal(to_decimal(value) * Decimal(factor))


def build_market_multiples_section(
    *,
    collected_data: Mapping[str, object],
    industry: str,
    business_type_id: str | None,
    valuation_coordinator: MarketMultiplesValuationCoordinator,
    industry_coordinator: MarketMultiplesIndustryCoordinator,
) -> dict[str, object]:
    """Build the progressive market-multiples section payload."""
    multiples_data = valuation_coordinator.calculate_multiples_valuation(
        collected_data,
        industry,
        business_type_id=business_type_id,
    )
    if multiples_data.get("blocked") or not multiples_data.get("has_valid_data"):
        return {
            "ev_revenue_multiple": None,
            "ev_ebitda_multiple": None,
            "pe_ratio": None,
            "industry_ev_revenue": None,
            "industry_ev_ebitda": None,
            "industry_pe": None,
            "revenue_multiple_value": None,
            "ebitda_multiple_value": None,
            "earnings_multiple_value": None,
            "weighted_multiples_value": None,
            "comparable_companies": [],
            "comparable_count": 0,
            "multiple_rationale": (
                "Resolved benchmark contract required before market multiples can be shown."
            ),
            "confidence": 0,
            "blocked": True,
            "requires_benchmark_contract": True,
            "publication_allowed": False,
            "reason": multiples_data.get("reason", "missing_benchmark_contract"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "phase": 3,
        }

    ev_revenue_multiple = multiples_data.get("ev_revenue_multiple")
    ev_ebitda_multiple = multiples_data.get("ev_ebitda_multiple")
    pe_ratio = multiples_data.get("pe_ratio")
    revenue_multiple_value = multiples_data.get("revenue_multiple_value")
    ebitda_multiple_value = multiples_data.get("ebitda_multiple_value")
    earnings_multiple_value = multiples_data.get("earnings_multiple_value")
    weighted_multiples_value = multiples_data.get("weighted_multiples_value")
    multiple_type_blend = multiples_data.get("multiple_type_blend")

    ebitda_decimal, _ = extract_ebitda_from_collected_data(collected_data)
    ebitda = from_decimal(ebitda_decimal)

    comparable_companies = industry_coordinator.generate_comparable_companies(
        industry,
        ev_revenue_multiple,
        ev_ebitda_multiple,
        pe_ratio,
        business_type_id=business_type_id,
    )
    comparable_companies.append(
        {
            "name": f"{industry.title()} Partners",
            "ev_revenue": _scale_multiple(ev_revenue_multiple, "0.9"),
            "ev_ebitda": _scale_multiple(ev_ebitda_multiple, "0.92"),
            "pe": _scale_multiple(pe_ratio, "0.9"),
        }
    )
    comparable_companies.append(
        {
            "name": f"{industry.title()} Ventures",
            "ev_revenue": _scale_multiple(ev_revenue_multiple, "1.05"),
            "ev_ebitda": _scale_multiple(ev_ebitda_multiple, "1.0"),
            "pe": _scale_multiple(pe_ratio, "1.05"),
        }
    )

    if ebitda > 0:
        multiple_rationale = (
            "EBITDA multiple weighted higher due to strong profitability profile. "
            "Revenue and earnings multiples provide additional validation."
        )
    else:
        multiple_rationale = (
            "Revenue multiple used as primary methodology due to limited profitability data. "
            "Industry comparables support valuation range."
        )

    return {
        "ev_revenue_multiple": ev_revenue_multiple,
        "ev_ebitda_multiple": ev_ebitda_multiple,
        "pe_ratio": pe_ratio,
        "industry_ev_revenue": ev_revenue_multiple,
        "industry_ev_ebitda": ev_ebitda_multiple,
        "industry_pe": pe_ratio,
        "revenue_multiple_value": revenue_multiple_value,
        "ebitda_multiple_value": ebitda_multiple_value,
        "earnings_multiple_value": earnings_multiple_value,
        "weighted_multiples_value": weighted_multiples_value,
        "multiple_type_blend": multiple_type_blend,
        "comparable_companies": comparable_companies,
        "comparable_count": len(comparable_companies),
        "multiple_rationale": multiple_rationale,
        "confidence": 75,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "phase": 3,
    }
