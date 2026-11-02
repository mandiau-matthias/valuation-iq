"""Exact, period-preserving admission of explicit APV monetary schedules."""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from src.utils.exceptions import DataQualityError

SCHEDULE_KEYS = (
    "dcf_tax_shield_projections",
    "dcf_tax_shield_projections_5y",
    "apv_tax_shield_projections",
    "apv_tax_shield_projections_5y",
)
UNLEVERED_KINDS = {
    "unlevered_cost_of_capital",
    "unlevered_required_return",
    "asset_cost_of_capital",
}


def finite_amount(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise DataQualityError(f"APV {field} must contain finite decimal amounts")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DataQualityError(f"APV {field} must contain finite decimal amounts") from exc
    if not amount.is_finite():
        raise DataQualityError(f"APV {field} must contain finite decimal amounts")
    return amount


def _schedule(raw: object) -> list[Decimal]:
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("["):
            try:
                raw = json.loads(text, parse_float=Decimal, parse_int=Decimal)
            except (ValueError, TypeError) as exc:
                raise DataQualityError("APV tax-shield schedule must be valid JSON") from exc
        else:
            text = text.replace("\n", ";").replace("\t", ";")
            raw = text.split(";" if ";" in text else ",")
    if not isinstance(raw, (list, tuple)):
        raise DataQualityError("APV tax-shield schedule must be an ordered list")
    # A supplied empty list explicitly means no schedule. Missing entries in a
    # nonempty list are errors; dropping them would move the discount periods.
    return [finite_amount(value, "tax-shield schedule") for value in raw]


def tax_shield_schedule(context: Mapping[str, object]) -> list[Decimal]:
    schedules = [
        _schedule(context[key])
        for key in SCHEDULE_KEYS
        if key in context and not key.endswith("_5y")
    ]
    previews = [
        _schedule(context[key]) for key in SCHEDULE_KEYS if key in context and key.endswith("_5y")
    ]
    if not schedules:
        schedules = previews
    if not schedules:
        return []
    if any(values != schedules[0] for values in schedules[1:]):
        raise DataQualityError("APV tax-shield schedule aliases contain conflicting periods")
    if any(values != schedules[0][:5] or len(values) > 5 for values in previews):
        raise DataQualityError("APV tax-shield previews contain conflicting periods")
    return schedules[0]


def explicit_rate(context: Mapping[str, object], key: str) -> Decimal | None:
    """An unsuffixed field is a fraction; its _pct alias is percentage points."""
    rates = [
        finite_amount(context[name], name) / divisor
        for name, divisor in ((key, Decimal(1)), (key + "_pct", Decimal(100)))
        if name in context
    ]
    if not rates:
        return None
    if any(rate <= 0 for rate in rates):
        raise DataQualityError(f"APV {key} must be positive")
    if any(rate != rates[0] for rate in rates[1:]):
        raise DataQualityError(f"APV {key} aliases contain conflicting rates")
    return rates[0]


def unlevered_base_contract(
    context: Mapping[str, object], discount_rate: Decimal
) -> tuple[bool, str, Decimal | None]:
    kind = str(context.get("apv_base_discount_rate_kind") or "").strip().lower()
    rate = explicit_rate(context, "apv_unlevered_discount_rate")
    if kind in UNLEVERED_KINDS:
        if rate is None or rate != discount_rate:
            raise DataQualityError(
                "APV unlevered discount rate must match the rate pricing the operating base"
            )
        return True, kind, rate
    return False, kind or "wacc_after_tax", rate
