"""Forecast-assumption warning policy for DCF response assembly."""

from decimal import Decimal
from typing import NamedTuple, Optional

from src.utils.decimal_helpers import to_decimal


class _HistoricalBaseline(NamedTuple):
    real_historical: list[tuple[Decimal, Decimal]]
    zero_year_present: bool


def build_forecast_assumption_warnings(request: object) -> list[dict[str, object]]:
    """
    Surface material divergences between the user-supplied forecast and the
    company's historical track record, so the report can flag them for advisor
    review.

    Emitted warnings:
    - forecast_margin_expansion: forecast EBITDA margin exceeds the historical
      weighted average by >=5 percentage points.
    - forecast_growth_acceleration: forecast revenue growth exceeds historical
      CAGR by >=10 percentage points.
    - limited_historical_data: fewer than 3 historical years or a zero placeholder
      year weakens the forecast base.

    Best-effort by design: malformed inputs must not block the DCF response.
    """
    warnings: list[dict[str, object]] = []
    try:
        historical_years = list(getattr(request, "historical_years_data", None) or [])
        forecast_years = list(getattr(request, "forecast_years_data", None) or [])
        baseline = _extract_historical_baseline(historical_years)

        if not baseline.real_historical or not forecast_years:
            warning = _limited_history_warning_without_forecast(baseline)
            if warning:
                warnings.append(warning)
            return warnings

        historical_margin = _weighted_historical_margin(baseline.real_historical)
        forecast_margins, forecast_revenues = _forecast_margin_and_revenue_series(forecast_years)

        forecast_margin_warning = _build_forecast_margin_warning(
            forecast_margins=forecast_margins,
            historical_margin=historical_margin,
        )
        if forecast_margin_warning:
            warnings.append(forecast_margin_warning)

        revenue_growth_warning = _build_revenue_growth_warning(
            real_historical=baseline.real_historical,
            forecast_revenues=forecast_revenues,
        )
        if revenue_growth_warning:
            warnings.append(revenue_growth_warning)

        limited_history_warning = _limited_history_warning_with_forecast(baseline)
        if limited_history_warning:
            warnings.append(limited_history_warning)
    except Exception:
        pass
    return warnings


def _extract_historical_baseline(historical_years: list[object]) -> _HistoricalBaseline:
    real_historical: list[tuple[Decimal, Decimal]] = []
    zero_year_present = False
    for year in historical_years:
        if getattr(year, "is_forecast", False):
            continue
        revenue = _decimal_or_none(getattr(year, "revenue", None)) or Decimal("0")
        ebitda = _decimal_or_none(getattr(year, "ebitda", None)) or Decimal("0")
        if revenue <= 0 and ebitda <= 0:
            zero_year_present = True
            continue
        if revenue > 0:
            real_historical.append((revenue, ebitda))
    return _HistoricalBaseline(real_historical, zero_year_present)


def _limited_history_warning_without_forecast(
    baseline: _HistoricalBaseline,
) -> Optional[dict[str, object]]:
    if not (baseline.zero_year_present or len(baseline.real_historical) < 2):
        return None

    message = (
        f"Limited historical data ({len(baseline.real_historical)} usable year(s)"
        + (
            ", with at least one zero-revenue/EBITDA placeholder"
            if baseline.zero_year_present
            else ""
        )
        + "); DCF projections rest on a thin base."
    )
    return _limited_history_warning(
        severity="medium",
        message=message,
        impact="Forecast assumptions cannot be validated against a multi-year track record.",
        recommendation=(
            "Provide >=3 years of historical financials, or weight the result against a multiples cross-check."
        ),
    )


def _limited_history_warning_with_forecast(
    baseline: _HistoricalBaseline,
) -> Optional[dict[str, object]]:
    if not (baseline.zero_year_present or len(baseline.real_historical) < 3):
        return None

    message = (
        f"Only {len(baseline.real_historical)} usable historical year(s) provided"
        + (
            " (a placeholder zero year was excluded from the baseline)"
            if baseline.zero_year_present
            else ""
        )
        + "; the projection has limited statistical support."
    )
    return _limited_history_warning(
        severity="low" if len(baseline.real_historical) >= 2 else "medium",
        message=message,
        impact="Forecast precision is bounded by the available history.",
        recommendation=(
            "Add at least 3 closed years where available before relying on the DCF for negotiation."
        ),
    )


def _decimal_or_none(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        decimal_value = to_decimal(value)
        return decimal_value if decimal_value.is_finite() else None
    except Exception:
        return None


def _weighted_historical_margin(
    real_historical: list[tuple[Decimal, Decimal]],
) -> Optional[Decimal]:
    weights = [Decimal("0.67"), Decimal("0.33")] if len(real_historical) >= 2 else [Decimal("1.0")]
    ordered = real_historical[-len(weights) :]
    weighted_revenue = sum(
        (revenue * weight for (revenue, _), weight in zip(ordered, weights)), Decimal("0")
    )
    weighted_ebitda = sum(
        (ebitda * weight for (_, ebitda), weight in zip(ordered, weights)), Decimal("0")
    )
    if weighted_revenue <= Decimal("0"):
        return None
    return weighted_ebitda / weighted_revenue


def _forecast_margin_and_revenue_series(
    forecast_years: list[object],
) -> tuple[list[Decimal], list[Decimal]]:
    forecast_margins: list[Decimal] = []
    forecast_revenues: list[Decimal] = []
    for year in forecast_years:
        revenue = _decimal_or_none(getattr(year, "revenue", None))
        ebitda = _decimal_or_none(getattr(year, "ebitda", None))
        if revenue and revenue > 0 and ebitda is not None:
            forecast_margins.append(ebitda / revenue)
            forecast_revenues.append(revenue)
    return forecast_margins, forecast_revenues


def _build_forecast_margin_warning(
    *,
    forecast_margins: list[Decimal],
    historical_margin: Optional[Decimal],
) -> Optional[dict[str, object]]:
    if not forecast_margins or historical_margin is None:
        return None

    forecast_margin_avg = sum(forecast_margins) / Decimal(len(forecast_margins))
    margin_gap = forecast_margin_avg - historical_margin
    if margin_gap >= Decimal("0.10"):
        severity = "high"
    elif margin_gap >= Decimal("0.05"):
        severity = "medium"
    else:
        return None

    return {
        "type": "forecast_margin_expansion",
        "severity": severity,
        "message": (
            f"Forecast EBITDA margin ({float(forecast_margin_avg) * 100:.1f}%) "
            f"exceeds historical weighted average ({float(historical_margin) * 100:.1f}%) "
            f"by {float(margin_gap) * 100:.1f}pp without an explicit operational driver."
        ),
        "impact": "Materially raises the FCFF projection — sensitivity to this single assumption is high.",
        "recommendation": (
            "Either (a) anchor the forecast margin to the historical baseline and add a "
            "named expansion driver (pricing, mix shift, scale), or (b) widen the confidence "
            "band in the report disclosure."
        ),
    }


def _build_revenue_growth_warning(
    *,
    real_historical: list[tuple[Decimal, Decimal]],
    forecast_revenues: list[Decimal],
) -> Optional[dict[str, object]]:
    try:
        if len(real_historical) < 2 or len(forecast_revenues) < 1:
            return None
        hist_first_rev, _ = real_historical[0]
        hist_last_rev, _ = real_historical[-1]
        hist_years = max(len(real_historical) - 1, 1)
        forecast_first_rev = forecast_revenues[0]
        forecast_last_rev = forecast_revenues[-1]
        forecast_years_count = max(len(forecast_revenues) - 1, 1)
        if hist_first_rev <= 0 or forecast_first_rev <= 0:
            return None
        hist_cagr = Decimal(str(float(hist_last_rev / hist_first_rev) ** (1.0 / hist_years) - 1.0))
        fwd_cagr = Decimal(
            str(float(forecast_last_rev / forecast_first_rev) ** (1.0 / forecast_years_count) - 1.0)
        )
        growth_gap = fwd_cagr - hist_cagr
        if growth_gap < Decimal("0.10"):
            return None
        return {
            "type": "forecast_growth_acceleration",
            "severity": "medium",
            "message": (
                f"Forecast revenue CAGR ({float(fwd_cagr) * 100:.1f}%) exceeds historical CAGR "
                f"({float(hist_cagr) * 100:.1f}%) by {float(growth_gap) * 100:.1f}pp."
            ),
            "impact": "Sustains the projection on an acceleration the historical record doesn't support.",
            "recommendation": (
                "Document the catalyst (new product, market expansion, pricing) or moderate the "
                "growth trajectory."
            ),
        }
    except Exception:
        return None


def _limited_history_warning(
    *,
    severity: str,
    message: str,
    impact: str,
    recommendation: str,
) -> dict[str, object]:
    return {
        "type": "limited_historical_data",
        "severity": severity,
        "message": message,
        "impact": impact,
        "recommendation": recommendation,
    }
