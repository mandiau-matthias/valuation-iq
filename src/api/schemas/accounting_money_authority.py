"""Read exact money controls before any legacy numeric summary."""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
import re

SUPPORTED_CURRENCY_SCALES = {
    code: 2
    for code in ("EUR", "GBP", "USD", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK", "DKK", "PLN", "CZK")
}


def authoritative_reported_values(
    reported: Mapping[str, object], currency: str
) -> dict[str, object]:
    values = dict(reported)
    control = reported.get("_money_v2")
    if control is None:
        return values  # Immutable historical contracts retain their original reader.
    if not isinstance(control, Mapping) or control.get("schema_version") != "money-amount.v2":
        raise ValueError("Invalid money-amount.v2 control")
    scale = SUPPORTED_CURRENCY_SCALES.get(currency)
    if scale is None or control.get("currency") != currency or control.get("scale") != scale:
        raise ValueError("Money control currency/scale mismatch")
    money = control.get("values")
    if not isinstance(money, Mapping):
        raise ValueError("Missing authoritative money values")
    for field, item in money.items():
        if (
            not isinstance(item, Mapping)
            or item.get("currency") != currency
            or item.get("scale") != scale
        ):
            raise ValueError(f"Money control currency/scale mismatch: {field}")
        raw = item.get("amount")
        if (
            not isinstance(raw, str)
            or re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", raw) is None
        ):
            raise ValueError("Money amount must be a decimal string")
        try:
            value = Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError("Invalid money decimal") from exc
        if not value.is_finite():
            raise ValueError("Non-finite money amount")
        exponent = value.as_tuple().exponent
        if not isinstance(exponent, int) or exponent < -scale:
            raise ValueError("Money amount exceeds supported currency scale")
        values[field] = raw
    return values
