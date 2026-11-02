"""
SME growth-history calculations.

Keeps chronology-sensitive revenue CAGR, YoY decline, and growth-risk multiple
adjustments out of the Step 2 orchestration class.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional, Tuple

from src.api.routes.valuation.shared.historical_years import oldest_and_newest_historical_years
from src.utils.decimal_helpers import calculate_decimal_cagr
from src.utils.logging import get_logger

logger = get_logger(__name__)

GrowthRiskResult = Tuple[
    Optional[Decimal], Decimal, Optional[str], Optional[Decimal], Optional[Decimal], Decimal
]

_ZERO = Decimal("0.0")
_ONE = Decimal("1.0")
_GROWTH_MULTIPLE_KEYS = (
    "ev_ebitda_p10",
    "ev_ebitda_p25",
    "ev_ebitda_p50",
    "ev_ebitda_p75",
    "ev_ebitda_p90",
)


@dataclass(frozen=True)
class RevenueHistoryInputs:
    historical: list[object]
    oldest_revenue: Optional[Decimal]
    newest_historical_revenue: Optional[Decimal]
    current_revenue: Optional[Decimal]
    newest_revenue: Optional[Decimal]
    years: int


def ensure_decimal(val: object) -> Optional[Decimal]:
    """Safely convert a value to Decimal; returns None if val is None."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        return None


def _empty_growth_risk_result(ev_ebitda_multiple: Optional[Decimal]) -> GrowthRiskResult:
    return ev_ebitda_multiple, _ZERO, None, None, None, _ZERO


def _revenue_from(candidate: object) -> Optional[Decimal]:
    return ensure_decimal(getattr(candidate, "revenue", None) if candidate is not None else None)


def _current_revenue(request: object) -> Optional[Decimal]:
    current_year_data = getattr(request, "current_year_data", None)
    return _revenue_from(current_year_data)


def _revenue_history_inputs(request: object) -> Optional[RevenueHistoryInputs]:
    historical = list(getattr(request, "historical_years_data", None) or [])
    if not historical:
        return None

    oldest_year, newest_historical_year = oldest_and_newest_historical_years(historical)
    current_revenue = _current_revenue(request)
    newest_historical_revenue = _revenue_from(newest_historical_year)
    newest_revenue = current_revenue if current_revenue is not None else newest_historical_revenue
    return RevenueHistoryInputs(
        historical=historical,
        oldest_revenue=_revenue_from(oldest_year),
        newest_historical_revenue=newest_historical_revenue,
        current_revenue=current_revenue,
        newest_revenue=newest_revenue,
        years=len(historical) + (1 if current_revenue is not None else 0),
    )


def _has_usable_revenue_history(inputs: Optional[RevenueHistoryInputs]) -> bool:
    return bool(
        inputs
        and inputs.oldest_revenue is not None
        and inputs.newest_revenue is not None
        and inputs.oldest_revenue > 0
        and inputs.newest_revenue > 0
        and inputs.years > 0
    )


def _recent_yoy_decline(inputs: RevenueHistoryInputs) -> Optional[Decimal]:
    if inputs.current_revenue is None or not inputs.historical:
        return None
    previous_revenue = inputs.newest_historical_revenue
    if previous_revenue is None or previous_revenue <= 0:
        return None
    recent_yoy_decline = ((inputs.current_revenue - previous_revenue) / previous_revenue) * Decimal(
        "100.0"
    )
    return (
        None
        if recent_yoy_decline.is_nan() or recent_yoy_decline.is_infinite()
        else recent_yoy_decline
    )


def _revenue_growth_indicators(
    inputs: RevenueHistoryInputs,
) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    if not _has_usable_revenue_history(inputs):
        return None, None
    revenue_cagr = calculate_decimal_cagr(
        inputs.oldest_revenue,
        inputs.newest_revenue,
        inputs.years,
        as_percentage=True,
    )
    return revenue_cagr, _recent_yoy_decline(inputs)


def _cagr_adjustment(revenue_cagr: Decimal) -> Tuple[Decimal, Optional[str]]:
    if revenue_cagr > Decimal("15.0"):
        return (
            Decimal("0.08"),
            (
                f"Strong growth premium (CAGR: {revenue_cagr:.1f}% > 15%): +8% multiple premium. "
                "Sustained high growth justifies higher multiples per Damodaran (2012) and McKinsey (2020, Ch. 3)."
            ),
        )
    if revenue_cagr > Decimal("8.0"):
        return (
            Decimal("0.04"),
            (
                f"Moderate growth premium (CAGR: {revenue_cagr:.1f}% > 8%): +4% multiple premium. "
                "Above-average growth supports higher multiples per Damodaran (2012)."
            ),
        )
    if revenue_cagr < Decimal("-30.0"):
        return (
            -Decimal("0.275"),
            f"Severe revenue decline (CAGR: {revenue_cagr:.1f}% < -30%) - growth risk adjustment (-27.5%) applied per academic valuation standards (Koller, Goedhart & Wessels 2020, Ch. 10).",
        )
    if revenue_cagr < Decimal("-20.0"):
        return (
            -Decimal("0.15"),
            f"Significant revenue decline (CAGR: {revenue_cagr:.1f}% < -20%) - growth risk adjustment (-15%) applied per academic valuation standards (Koller, Goedhart & Wessels 2020, Ch. 10).",
        )
    return _ZERO, None


def _moderate_recent_decline_adjustment(
    *,
    cagr_adjustment: Decimal,
    recent_yoy_decline: Decimal,
    log,
) -> Tuple[Decimal, str, Decimal]:
    recent_year_adjustment = -Decimal("0.12")
    if cagr_adjustment < 0:
        total_adjustment = max(cagr_adjustment + recent_year_adjustment, -Decimal("0.30"))
        explanation = (
            f"Dual-factor model: CAGR-based adjustment ({cagr_adjustment*100:.1f}%) + "
            f"Recent YoY decline factor ({recent_year_adjustment*100:.1f}%) = Total ({total_adjustment*100:.1f}%). "
            f"Recent year decline ({recent_yoy_decline:.1f}%) indicates deteriorating performance per Damodaran (2012)."
        )
    else:
        total_adjustment = recent_year_adjustment
        explanation = (
            f"Recent YoY revenue decline ({recent_yoy_decline:.1f}% < -15%) - multiple discount ({recent_year_adjustment*100:.1f}%) "
            "applied per academic valuation standards (Damodaran 2012, Koller 2020). "
            "Declining businesses trade at 15-25% lower multiples due to elevated risk."
        )
    log.warning(
        "⚠️ Moderate YoY revenue decline detected - applying multiple discount",
        extra={
            "recent_yoy_decline_pct": float(recent_yoy_decline),
            "multiple_discount": float(recent_year_adjustment),
            "adjustment_reason": "Declining revenue reduces buyer confidence",
            "academic_source": "Damodaran 2012, Koller 2020",
        },
    )
    return total_adjustment, explanation, recent_year_adjustment


def _severe_recent_decline_adjustment(
    *,
    cagr_adjustment: Decimal,
    recent_yoy_decline: Decimal,
) -> Tuple[Decimal, str, Decimal]:
    recent_year_adjustment = -Decimal("0.075")
    total_adjustment = max(cagr_adjustment + recent_year_adjustment, -Decimal("0.30"))
    explanation = (
        f"Dual-factor model: CAGR-based adjustment ({cagr_adjustment*100:.1f}%) + "
        f"Recent year decline factor ({recent_year_adjustment*100:.1f}%) = Total ({total_adjustment*100:.1f}%). "
        f"Recent year decline ({recent_yoy_decline:.1f}% < -30%) signals accelerating distress per academic valuation standards (Koller, Goedhart & Wessels 2020, Ch. 10)."
    )
    return total_adjustment, explanation, recent_year_adjustment


def _growth_risk_adjustment_policy(
    *,
    revenue_cagr: Decimal,
    recent_yoy_decline: Optional[Decimal],
    log,
) -> Tuple[Decimal, Optional[str], Decimal]:
    growth_adjustment, explanation = _cagr_adjustment(revenue_cagr)
    recent_year_adjustment = _ZERO
    if recent_yoy_decline is None:
        return growth_adjustment, explanation, recent_year_adjustment
    if Decimal("-30.0") <= recent_yoy_decline < Decimal("-15.0"):
        return _moderate_recent_decline_adjustment(
            cagr_adjustment=growth_adjustment,
            recent_yoy_decline=recent_yoy_decline,
            log=log,
        )
    if recent_yoy_decline < Decimal("-30.0"):
        return _severe_recent_decline_adjustment(
            cagr_adjustment=growth_adjustment,
            recent_yoy_decline=recent_yoy_decline,
        )
    return growth_adjustment, explanation, recent_year_adjustment


def _apply_multiple_growth_adjustment(
    *,
    ev_ebitda_multiple: Decimal,
    multiples_data: Dict[str, object],
    growth_risk_adjustment: Decimal,
) -> Decimal:
    if growth_risk_adjustment == _ZERO:
        return ev_ebitda_multiple
    adjustment_factor = _ONE + growth_risk_adjustment
    adjusted_multiple = ev_ebitda_multiple * adjustment_factor
    adjusted_percentiles: dict[str, Decimal] = {}
    for key in _GROWTH_MULTIPLE_KEYS:
        if multiples_data.get(key) is not None:
            percentile_multiple = ensure_decimal(multiples_data[key])
            if percentile_multiple is None:
                raise ValueError(f"Invalid growth multiple for {key}")
            adjusted_percentiles[key] = percentile_multiple * adjustment_factor

    multiples_data["ev_ebitda"] = adjusted_multiple
    multiples_data.update(adjusted_percentiles)
    return adjusted_multiple


def calculate_revenue_decline_indicators(
    request: object,
    *,
    logger_instance=None,
) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """Calculate revenue CAGR and recent YoY decline for margin premium."""
    log = logger_instance or logger
    inputs = _revenue_history_inputs(request)
    if not _has_usable_revenue_history(inputs):
        return None, None
    try:
        return _revenue_growth_indicators(inputs)
    except (ValueError, ZeroDivisionError, OverflowError) as e:
        log.warning("⚠️ CAGR calculation failed", extra={"error": str(e)})
        return None, None


def apply_growth_risk_adjustment(
    request: object,
    ev_ebitda_multiple: Optional[Decimal],
    multiples_data: Dict[str, object],
    *,
    logger_instance=None,
) -> GrowthRiskResult:
    """Apply growth risk adjustment for declining revenue."""
    log = logger_instance or logger
    ev_ebitda_multiple = ensure_decimal(ev_ebitda_multiple)
    log.debug(
        "🔍 [GROWTH-RISK] _apply_growth_risk_adjustment called",
        extra={
            "has_ev_ebitda_multiple": ev_ebitda_multiple is not None,
            "ev_ebitda_multiple": (
                float(ev_ebitda_multiple) if ev_ebitda_multiple is not None else None
            ),
            "has_historical_data": hasattr(request, "historical_years_data")
            and bool(request.historical_years_data),
            "historical_years_count": (
                len(request.historical_years_data)
                if hasattr(request, "historical_years_data") and request.historical_years_data
                else 0
            ),
        },
    )

    if (
        ev_ebitda_multiple is None
        or not hasattr(request, "historical_years_data")
        or not request.historical_years_data
    ):
        log.info(
            "[GROWTH-RISK] Skipping growth risk adjustment - insufficient data",
            extra={
                "has_ev_ebitda_multiple": ev_ebitda_multiple is not None,
                "has_historical_data_attr": hasattr(request, "historical_years_data"),
                "historical_data_exists": (
                    bool(request.historical_years_data)
                    if hasattr(request, "historical_years_data")
                    else False
                ),
            },
        )
        return ev_ebitda_multiple, Decimal("0.0"), None, None, None, Decimal("0.0")

    inputs = _revenue_history_inputs(request)
    if not _has_usable_revenue_history(inputs):
        return _empty_growth_risk_result(ev_ebitda_multiple)

    try:
        assert inputs is not None
        revenue_cagr, recent_yoy_decline = _revenue_growth_indicators(inputs)
        if revenue_cagr is None:
            return _empty_growth_risk_result(ev_ebitda_multiple)
        (
            growth_risk_adjustment,
            growth_risk_adjustment_explanation,
            recent_year_adjustment,
        ) = _growth_risk_adjustment_policy(
            revenue_cagr=revenue_cagr,
            recent_yoy_decline=recent_yoy_decline,
            log=log,
        )
        ev_ebitda_multiple = _apply_multiple_growth_adjustment(
            ev_ebitda_multiple=ev_ebitda_multiple,
            multiples_data=multiples_data,
            growth_risk_adjustment=growth_risk_adjustment,
        )

        return (
            ev_ebitda_multiple,
            growth_risk_adjustment,
            growth_risk_adjustment_explanation,
            revenue_cagr,
            recent_yoy_decline,
            recent_year_adjustment,
        )

    except (TypeError, ValueError, ZeroDivisionError, OverflowError) as e:
        log.warning(
            "⚠️ Step 2: Could not calculate revenue CAGR for growth risk adjustment",
            extra={"error": str(e)},
        )
        return _empty_growth_risk_result(ev_ebitda_multiple)
