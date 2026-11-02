"""
Data Quality Telemetry — per-valuation observability fields.

Computes the data-quality signals identified by the Three Towers Capital
defensibility-gate finding (2026-04-29). These get logged on every
successful valuation so we can observe — across our 30-40 demos — how
many would have hit each rung of the gate before the gate itself ships.

Fields produced:
- confidence_score: int (0-100) from the response
- band: "LOW" | "MED" | "HIGH" derived from confidence_score
- triggered_hard_caps: list[str] of cap conditions that would fire
- years_of_data: int — current + historical years
- normalizations_count: int — number of EBITDA adjustments applied
- owner_managed_bool: bool — owner_count >= 1 AND employee_count <= 10
- benchmark_deviation_pct: float | None — |actual - typical| / typical * 100
- methods_used: list[str] — which valuation methods produced output

Pure function, defensive: never raises, never blocks the success path.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from src.api.schemas import ValuationRequest, ValuationResponse


# Band thresholds — single source of truth for downstream gate logic
BAND_HIGH_MIN = 70
BAND_MED_MIN = 40

# Owner-managed heuristic per the defensibility-gate spec
OWNER_MANAGED_FTE_THRESHOLD = 10


def derive_band(confidence_score: Optional[int]) -> str:
    """Map a 0-100 confidence score to LOW / MED / HIGH (or UNKNOWN)."""
    if confidence_score is None:
        return "UNKNOWN"
    if confidence_score >= BAND_HIGH_MIN:
        return "HIGH"
    if confidence_score >= BAND_MED_MIN:
        return "MED"
    return "LOW"


def _years_of_data(request: ValuationRequest) -> int:
    historical = getattr(request, "historical_years_data", None) or []
    return 1 + len(historical)


def _normalizations_count(
    request: ValuationRequest, response: ValuationResponse
) -> int:
    """
    Prefer post-calculation truth (response.financial_metrics.ebitda_adjustments);
    fall back to user-supplied input metadata on the request years.
    """
    metrics = getattr(response, "financial_metrics", None)
    if metrics is not None:
        adjustments = getattr(metrics, "ebitda_adjustments", None)
        if adjustments:
            return len(adjustments)

    count = 0
    years = [request.current_year_data] + (
        getattr(request, "historical_years_data", None) or []
    )
    for year in years:
        meta = getattr(year, "ebitda_normalization_metadata", None) or {}
        adj_list = meta.get("adjustments") if isinstance(meta, dict) else None
        if isinstance(adj_list, list):
            count += len(adj_list)
    return count


def _owner_managed(request: ValuationRequest) -> bool:
    owners = getattr(request, "number_of_owners", None) or 0
    fte = getattr(request, "employee_count", None)
    if owners < 1:
        return False
    # Unknown FTE on a business with owners = treat as owner-managed (small-biz default).
    if fte is None:
        return True
    return fte <= OWNER_MANAGED_FTE_THRESHOLD


def _benchmark_deviation_pct(request: ValuationRequest) -> Optional[float]:
    """
    |actual_margin - typical_margin| / typical_margin * 100 for the current
    year's EBITDA margin. Mirrors business_logic_validator.py:629 so the
    telemetry value matches the warning-channel value.
    """
    benchmarks = getattr(request, "industry_benchmarks", None) or {}
    typical_margin = benchmarks.get("typical_ebitda_margin") or {}
    if not isinstance(typical_margin, dict):
        return None
    median = typical_margin.get("median")
    if median is None:
        return None

    current = getattr(request, "current_year_data", None)
    if current is None:
        return None
    revenue = getattr(current, "revenue", None)
    ebitda = getattr(current, "ebitda", None)
    if revenue is None or ebitda is None:
        return None

    try:
        rev_dec = Decimal(str(revenue))
        if rev_dec <= 0:
            return None
        actual = Decimal(str(ebitda)) / rev_dec
        expected = Decimal(str(median))
        # Same percentage-form normalization as the validator
        if expected > Decimal("1.0"):
            expected = expected / Decimal("100")
        if expected <= 0:
            return None
        return float(abs(actual - expected) / expected * Decimal("100"))
    except (ArithmeticError, TypeError, ValueError):
        return None


def _methods_used(response: ValuationResponse) -> list[str]:
    methods: list[str] = []
    if getattr(response, "dcf_valuation", None) is not None:
        methods.append("DCF")
    if getattr(response, "multiples_valuation", None) is not None:
        methods.append("Multiples")
    return methods


def _hard_caps_triggered(
    years_of_data: int,
    normalizations_count: int,
    owner_managed: bool,
    benchmark_deviation_pct: Optional[float],
) -> list[str]:
    """
    Identify which gate-blocker conditions WOULD trigger.
    Informational only — the gate itself is P1 in the Three Towers Capital plan.
    """
    caps: list[str] = []
    if years_of_data <= 1:
        caps.append("single_year_of_data")
    if owner_managed and normalizations_count == 0:
        caps.append("owner_managed_zero_normalizations")
    if benchmark_deviation_pct is not None and benchmark_deviation_pct > 100:
        caps.append("benchmark_deviation_over_100pct")
    return caps


def build_data_quality_telemetry(
    request: ValuationRequest, response: ValuationResponse
) -> dict[str, Any]:
    """
    Build per-valuation telemetry dict. Never raises — telemetry must not
    break the success path. On derivation failure returns a minimal payload
    with telemetry_error=True so we can spot regressions in logs.
    """
    try:
        years = _years_of_data(request)
        normalizations = _normalizations_count(request, response)
        owner_managed = _owner_managed(request)
        deviation = _benchmark_deviation_pct(request)
        methods = _methods_used(response)

        confidence_score = getattr(response, "confidence_score", None)
        band = derive_band(confidence_score)
        hard_caps = _hard_caps_triggered(
            years, normalizations, owner_managed, deviation
        )

        return {
            "confidence_score": confidence_score,
            "band": band,
            "triggered_hard_caps": hard_caps,
            "years_of_data": years,
            "normalizations_count": normalizations,
            "owner_managed_bool": owner_managed,
            "benchmark_deviation_pct": deviation,
            "methods_used": methods,
        }
    except Exception:
        return {
            "confidence_score": getattr(response, "confidence_score", None),
            "band": "ERROR",
            "telemetry_error": True,
        }
