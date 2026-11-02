"""Confidence scoring rules for DCF valuation outputs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, List

from src.utils.decimal_helpers import from_decimal, to_decimal


@dataclass(frozen=True)
class DCFConfidenceAssessment:
    level: str
    score: Decimal
    factors: List[str]


def assess_dcf_confidence(
    historical_fcf: Any, fcf_projections: List[Any], wacc_components: Any
) -> DCFConfidenceAssessment:
    factors: List[str] = []
    score = Decimal("1.0")

    score += _growth_score_adjustment(historical_fcf, factors)
    score += _volatility_score_adjustment(historical_fcf, factors)
    score += _wacc_score_adjustment(wacc_components, factors)
    score += _projection_period_score_adjustment(fcf_projections, factors)
    score += _historical_fcf_fidelity_score_adjustment(historical_fcf, factors)

    score = _clamp_confidence_score(score)
    return DCFConfidenceAssessment(
        level=_confidence_level_for_score(score),
        score=score,
        factors=factors,
    )


def _growth_score_adjustment(historical_fcf: Any, factors: List[str]) -> Decimal:
    cagr = to_decimal(historical_fcf.cagr)
    if cagr > Decimal("0.1"):
        factors.append("High historical growth rate")
        return Decimal("0.1")
    if cagr < Decimal("-0.1"):
        factors.append("Negative historical growth")
        return Decimal("-0.2")
    return Decimal("0")


def _volatility_score_adjustment(historical_fcf: Any, factors: List[str]) -> Decimal:
    volatility = to_decimal(historical_fcf.volatility)
    if volatility < Decimal("0.2"):
        factors.append("Low historical volatility")
        return Decimal("0.1")
    if volatility > Decimal("0.5"):
        factors.append("High historical volatility")
        return Decimal("-0.2")
    return Decimal("0")


def _wacc_score_adjustment(wacc_components: Any, factors: List[str]) -> Decimal:
    wacc = to_decimal(wacc_components.wacc)
    if Decimal("0.05") <= wacc <= Decimal("0.20"):
        factors.append("WACC within reasonable range")
        return Decimal("0.1")

    factors.append("WACC outside typical range")
    return Decimal("-0.1")


def _projection_period_score_adjustment(fcf_projections: List[Any], factors: List[str]) -> Decimal:
    if len(fcf_projections) >= 5:
        factors.append("Sufficient projection period")
        return Decimal("0.1")
    return Decimal("0")


def _historical_fcf_fidelity_score_adjustment(historical_fcf: Any, factors: List[str]) -> Decimal:
    historical_years = len(getattr(historical_fcf, "years", []) or [])
    if historical_years <= 0:
        return Decimal("0")

    actual_capex_years = int(getattr(historical_fcf, "actual_capex_years", 0) or 0)
    actual_tax_years = int(getattr(historical_fcf, "actual_tax_years", 0) or 0)
    actual_nwc_years = int(getattr(historical_fcf, "actual_nwc_years", 0) or 0)

    if _historical_fcf_is_fully_imported(
        historical_years,
        actual_capex_years,
        actual_tax_years,
        actual_nwc_years,
    ):
        factors.append(
            "Historical FCF is fully backed by imported CapEx, tax, and working-capital inputs"
        )
        return Decimal("0.1")

    if actual_capex_years > 0 or actual_tax_years > 0 or actual_nwc_years > 0:
        factors.append("Historical FCF mixes imported cash-flow inputs with fallback assumptions")
        return Decimal("0")

    factors.append(
        "Historical FCF relies primarily on fallback assumptions rather than imported cash-flow inputs"
    )
    return Decimal("-0.1")


def _historical_fcf_is_fully_imported(
    historical_years: int,
    actual_capex_years: int,
    actual_tax_years: int,
    actual_nwc_years: int,
) -> bool:
    return (
        actual_capex_years >= historical_years
        and actual_tax_years >= historical_years
        and actual_nwc_years >= max(0, historical_years - 1)
    )


def _clamp_confidence_score(score: Decimal) -> Decimal:
    return max(Decimal("0.0"), min(Decimal("1.0"), score))


def _confidence_level_for_score(score: Decimal) -> str:
    rounded_score = from_decimal(score)
    if rounded_score >= Decimal("0.8"):
        return "high"
    if rounded_score >= Decimal("0.6"):
        return "medium"
    if rounded_score >= Decimal("0.4"):
        return "low"
    return "very_low"
