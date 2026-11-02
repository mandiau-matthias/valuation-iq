"""Project the saved revenue method onto its report page without repricing."""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import cast

from src.services.reports.protocol_adapter import _unwrap


def _field(value: object, name: str) -> object:
    value = _unwrap(value)
    return (
        value.get(name) if isinstance(value, Mapping) else cast(object, getattr(value, name, None))
    )


def _number(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def apply_revenue_method_context(context: dict[str, object]) -> None:
    method = context.get("revenue_method")
    if method is None or _field(method, "available") is not True:
        return
    details = _field(method, "details")
    revenue = _number(_field(details, "revenue"))
    applied = _number(_field(method, "multiple_used"))
    if revenue is None or revenue <= 0 or applied is None or applied <= 0:
        return
    context["revenue_valuation_basis"] = revenue
    context["revenue_multiple_applied"] = applied
    for suffix in ("", "_low", "_high"):
        field = f"enterprise_value{suffix}"
        raw = _field(method, field)
        if raw is None:
            raw = _field(details, field)
        value = _number(raw)
        if value is None:
            continue
        context[f"ev_revenue_enterprise_value{suffix}"] = value
        if not suffix:
            context["revenue_sensitivity_base_multiple"] = value / revenue
        if suffix:
            # Bounds belong to this priced method, never to EBITDA or equity.
            context[f"revenue_multiple{suffix}"] = value / revenue
