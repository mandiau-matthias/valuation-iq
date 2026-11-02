"""Input-shaping helpers for API-layer DCF calculation orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Mapping

from src.api.schemas import ValuationRequest
from src.utils.decimal_helpers import to_decimal


@dataclass(frozen=True)
class DCFInputMetrics:
    revenue: object
    ebitda: object
    using_weighted_metrics: bool
    weighting_method: object


@dataclass(frozen=True)
class PositiveDCFValues:
    enterprise_value: Decimal
    equity_value: Decimal


def resolve_dcf_input_metrics(
    request: ValuationRequest,
    context_data: Mapping[str, object],
) -> DCFInputMetrics:
    """Resolve the revenue/EBITDA inputs used by DCF from weighted context or current year."""
    current_revenue = request.current_year_data.revenue or Decimal("0.0")
    current_ebitda = request.current_year_data.ebitda or Decimal("0.0")

    raw_weighted_metrics = context_data.get("weighted_metrics")
    if not isinstance(raw_weighted_metrics, dict) or not raw_weighted_metrics:
        return DCFInputMetrics(
            revenue=current_revenue,
            ebitda=current_ebitda,
            using_weighted_metrics=False,
            weighting_method="Current year only",
        )

    weighting_schema = raw_weighted_metrics.get("weighting_schema")
    weighting_method = (
        weighting_schema.get("method", "N/A") if isinstance(weighting_schema, dict) else "N/A"
    )
    return DCFInputMetrics(
        revenue=raw_weighted_metrics.get("weighted_revenue", current_revenue),
        ebitda=raw_weighted_metrics.get("weighted_ebitda", current_ebitda),
        using_weighted_metrics=True,
        weighting_method=weighting_method,
    )


def normalize_projection_years(raw_projection_years: object, default: int = 5) -> int:
    """Coerce request projection years into a positive integer for fallback-safe DCF paths."""
    try:
        projection_years = (
            int(raw_projection_years) if raw_projection_years is not None else default
        )
    except (TypeError, ValueError):
        projection_years = default
    return projection_years if projection_years >= 1 else default


def resolve_adapter_projection_years(
    adapter_forecasts: object,
    request_projection_years: object,
    default: int = 5,
) -> int:
    """Prefer explicit adapter forecasts, then request projection years, then default."""
    if isinstance(adapter_forecasts, list) and adapter_forecasts:
        return len(adapter_forecasts)
    return normalize_projection_years(request_projection_years, default=default)


def resolve_terminal_ebitda_for_sensitivity(
    request: ValuationRequest,
    safe_optional_decimal: Callable[[object], Decimal | None],
) -> Decimal | None:
    """Use the latest fiscal forecast, irrespective of transport row order."""
    explicit_forecast_years = getattr(request, "forecast_years_data", None) or []
    if explicit_forecast_years:
        terminal_forecast = max(
            explicit_forecast_years, key=lambda year_data: getattr(year_data, "year", 0)
        )
        terminal_ebitda = safe_optional_decimal(getattr(terminal_forecast, "ebitda", None))
        if terminal_ebitda is not None:
            return terminal_ebitda
    current_year_data = getattr(request, "current_year_data", None)
    return safe_optional_decimal(getattr(current_year_data, "ebitda", None))


def apply_positive_dcf_value_floors(
    *,
    enterprise_value: object,
    equity_value: object,
    logger: object,
    company: object,
    floor: Decimal = Decimal("1"),
) -> PositiveDCFValues:
    """Floor non-positive EV/equity so downstream range validation keeps a sane minimum."""
    if _needs_positive_floor(equity_value):
        logger.warning(
            "DCF equity missing or non-positive before valuation range; applying floor",
            extra={"equity_value": repr(equity_value), "company": company},
        )
        next_equity_value = floor
    else:
        next_equity_value = to_decimal(equity_value)

    if _needs_positive_floor(enterprise_value):
        logger.warning(
            "DCF enterprise value missing or non-positive before valuation range; applying floor",
            extra={"enterprise_value": repr(enterprise_value), "company": company},
        )
        next_enterprise_value = floor
    else:
        next_enterprise_value = to_decimal(enterprise_value)

    return PositiveDCFValues(
        enterprise_value=next_enterprise_value,
        equity_value=next_equity_value,
    )


def _needs_positive_floor(value: object) -> bool:
    if value is None:
        return True
    try:
        decimal_value = to_decimal(value)
        return not decimal_value.is_finite() or decimal_value <= 0
    except (ValueError, TypeError, ArithmeticError):
        return True
