"""Startup-specific response override for OmniCalc enrichment."""

from decimal import Decimal
from typing import Optional, Tuple

from src.api.schemas import ValuationRequest, ValuationResponse
from src.utils.decimal_helpers import to_decimal


def _startup_method(vr: dict[str, object]) -> Optional[object]:
    return vr.get("startup_valuation") if vr else None


def _startup_method_is_usable(method: Optional[object]) -> bool:
    return bool(
        method is not None
        and getattr(method, "available", False)
        and getattr(method, "value", None) is not None
    )


def _startup_value_range(
    details: dict[str, object], startup_mid: Decimal
) -> Tuple[Decimal, Decimal]:
    canonical = details.get("canonical") or {}
    canonical_low_raw = canonical.get("pre_money_low")
    canonical_high_raw = canonical.get("pre_money_high")
    startup_low_raw = (
        canonical_low_raw if canonical_low_raw is not None else details.get("equity_value_low")
    )
    startup_high_raw = (
        canonical_high_raw if canonical_high_raw is not None else details.get("equity_value_high")
    )
    if (
        startup_low_raw is not None
        and startup_high_raw is not None
        and to_decimal(startup_low_raw) > 0
    ):
        return to_decimal(startup_low_raw), to_decimal(startup_high_raw)
    return startup_mid, startup_mid


def _assign_startup_headline(
    response: ValuationResponse,
    *,
    startup_low: Decimal,
    startup_mid: Decimal,
    startup_high: Decimal,
) -> None:
    for field_name, value in (
        ("equity_value_mid", startup_mid),
        ("equity_value_low", startup_low),
        ("equity_value_high", startup_high),
        ("recommended_asking_price", startup_mid),
    ):
        if hasattr(response, field_name):
            setattr(response, field_name, value)


def _apply_startup_valuation_override(
    request: ValuationRequest,
    response: ValuationResponse,
    vr: dict[str, object],
    _logger: object,
) -> None:
    """Replace SME headline equity values with the startup engine's output."""
    if getattr(request, "selected_method", None) != "startup_valuation":
        return

    startup_method = _startup_method(vr)
    if not _startup_method_is_usable(startup_method):
        return

    details = getattr(startup_method, "details", None) or {}
    startup_mid = to_decimal(startup_method.value)
    startup_low, startup_high = _startup_value_range(details, startup_mid)

    _assign_startup_headline(
        response,
        startup_low=startup_low,
        startup_mid=startup_mid,
        startup_high=startup_high,
    )

    narrative = details.get("narrative")
    if narrative and hasattr(response, "methodology_downgrade_reason"):
        response.methodology_downgrade_reason = narrative

    log_info = getattr(_logger, "info", None)
    if callable(log_info):
        log_info(
            "[OmniCalc] Startup valuation override applied: equity_mid=%s",
            startup_mid,
        )
