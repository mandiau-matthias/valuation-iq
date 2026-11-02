"""Response-safety helpers for API-layer DCF payload assembly."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Optional, Protocol, cast

from src.utils.decimal_helpers import to_decimal

DecimalInput = str | int | float | Decimal | None


class WarningLogger(Protocol):
    def warning(
        self,
        msg: object,
        *args: object,
        extra: Mapping[str, object] | None = None,
        exc_info: object = None,
    ) -> None: ...


def fallback_equity_range_band(equity_value: Decimal) -> dict[str, Decimal]:
    """Symmetric +/-15% band when range calculation fails."""
    eq = to_decimal(equity_value)
    if not eq.is_finite() or eq <= 0:
        eq = Decimal("1")
    spread = eq * Decimal("0.15")
    low = max(eq - spread, Decimal("1"))
    high = eq + spread
    return {
        "equity_value_low": low,
        "equity_value_mid": eq,
        "equity_value_high": high,
    }


def normalize_valuation_range_for_response(
    valuation_range: object,
    equity_mid: Decimal,
    logger: WarningLogger,
    *,
    correlation_id: object = None,
    company: object = None,
) -> dict[str, Decimal]:
    """
    Last-line guard before response merge.

    Range calculators must not leave missing keys, non-finite values, or
    inverted bands after otherwise successful DCF math.
    """
    if not isinstance(valuation_range, dict):
        logger.warning(
            "DCF valuation_range not a dict; using symmetric fallback band",
            extra={
                "correlation_id": correlation_id,
                "company": company,
                "valuation_range_type": type(valuation_range).__name__,
            },
        )
        return fallback_equity_range_band(equity_mid)
    try:
        d_low = to_decimal(valuation_range.get("equity_value_low"))
        d_mid = to_decimal(valuation_range.get("equity_value_mid"))
        d_high = to_decimal(valuation_range.get("equity_value_high"))
    except Exception:
        logger.warning(
            "DCF valuation_range keys not coercible to Decimal; using fallback band",
            extra={"correlation_id": correlation_id, "company": company},
            exc_info=True,
        )
        return fallback_equity_range_band(equity_mid)
    if not all(x.is_finite() and x > 0 for x in (d_low, d_mid, d_high)):
        logger.warning(
            "DCF valuation_range has non-finite or non-positive values; using fallback band",
            extra={
                "correlation_id": correlation_id,
                "company": company,
                "low": repr(valuation_range.get("equity_value_low")),
                "mid": repr(valuation_range.get("equity_value_mid")),
                "high": repr(valuation_range.get("equity_value_high")),
            },
        )
        return fallback_equity_range_band(equity_mid)
    if not (d_low <= d_mid <= d_high):
        logger.warning(
            "DCF valuation_range not ordered low<=mid<=high; using fallback band",
            extra={"correlation_id": correlation_id, "company": company},
        )
        return fallback_equity_range_band(equity_mid)
    return {
        "equity_value_low": d_low,
        "equity_value_mid": d_mid,
        "equity_value_high": d_high,
    }


def safe_monte_carlo_decimal(value: object, fallback: Decimal) -> Decimal:
    """Coerce WACC / growth for Monte Carlo; never raise."""
    try:
        d = cast(Decimal, to_decimal(cast(DecimalInput, value)))
        if not d.is_finite():
            return fallback
        return d
    except Exception:
        return fallback


def safe_optional_decimal(value: object) -> Optional[Decimal]:
    """Coerce optional numerics for API-layer payloads."""
    if value is None:
        return None
    try:
        d = cast(Decimal, to_decimal(cast(DecimalInput, value)))
        if not d.is_finite():
            return None
        return d
    except Exception:
        return None


def safe_monte_carlo_optional_fcf(first_projection: object) -> Optional[Decimal]:
    """First explicit FCF for MC override; None if missing or not coercible."""
    return safe_optional_decimal(first_projection)


def coerce_engine_sensitivity_1d_map(raw: object) -> dict[str, Decimal]:
    """
    Normalize engine 1D sensitivity maps to string keys and finite Decimals.

    Bad cells become zero so a corrupt snapshot cannot force simplified-DCF fallback.
    """
    if raw is None or not isinstance(raw, dict):
        return {}
    out: dict[str, Decimal] = {}
    for key, value in raw.items():
        out_key = str(key)
        if value is None:
            out[out_key] = Decimal("0")
            continue
        try:
            d = to_decimal(value)
            out[out_key] = d if d.is_finite() else Decimal("0")
        except Exception:
            out[out_key] = Decimal("0")
    return out


def serialize_projection_detail(dcf_result: object) -> Optional[list[dict[str, float | int]]]:
    """Serialize CashFlowProjection objects to dicts for report templates."""
    if dcf_result is None:
        return None
    detail = getattr(dcf_result, "projection_detail", None)
    if not detail:
        return None
    rows: list[dict[str, float | int]] = []
    for projection in detail[:5]:
        rows.append(
            {
                "year": int(getattr(projection, "year", 0)),
                "revenue": float(getattr(projection, "revenue", 0)),
                "ebitda": float(getattr(projection, "ebitda", 0)),
                "ebit": float(getattr(projection, "ebit", 0)),
                "taxes": float(getattr(projection, "taxes", 0)),
                "capex": float(getattr(projection, "capex", 0)),
                "nwc_change": float(getattr(projection, "nwc_change", 0)),
                "free_cash_flow": float(getattr(projection, "free_cash_flow", 0)),
                "growth_rate": float(getattr(projection, "growth_rate", 0)),
            }
        )
    return rows
