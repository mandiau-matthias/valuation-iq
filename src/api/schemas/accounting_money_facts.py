"""Read authoritative signed money without consulting presentation projections."""

import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

_CANONICAL_AMOUNT = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")


def accounting_monetary_facts(reported: Mapping[str, object], currency: str) -> dict[str, Decimal]:
    if "_money_v2" not in reported:
        # Compatible reader for already signed historical packages. Their
        # original content is never rewritten or re-sealed by this projection.
        facts: dict[str, Decimal] = {}
        for key, raw in reported.items():
            if isinstance(raw, bool) or not isinstance(raw, (int, float, str, Decimal)):
                continue
            try:
                amount = Decimal(str(raw))
            except (InvalidOperation, ValueError):
                continue
            if not amount.is_finite():
                raise ValueError("accounting source money must be finite")
            facts[key] = amount
        return facts

    envelope = reported["_money_v2"]
    if not isinstance(envelope, Mapping) or envelope.get("schema_version") != "money-amount.v2":
        raise ValueError("accounting money envelope is invalid or unsupported")
    if (
        not re.fullmatch(r"[A-Z]{3}", currency)
        or currency == "XXX"
        or envelope.get("currency") != currency
    ):
        raise ValueError("accounting money envelope currency does not match its source period")
    scale = envelope.get("scale")
    if type(scale) is not int or not 0 <= scale <= 6:
        raise ValueError("accounting money scale must be an integer between 0 and 6")
    values = envelope.get("values")
    if not isinstance(values, Mapping):
        raise ValueError("accounting money envelope requires authoritative values")
    facts = {}
    for key, entry in values.items():
        if not isinstance(key, str) or not key or not isinstance(entry, Mapping):
            raise ValueError("accounting money entry is invalid")
        if (
            entry.get("currency") != currency
            or type(entry.get("scale")) is not int
            or entry.get("scale") != scale
        ):
            raise ValueError("accounting money entry currency/scale conflicts with its envelope")
        raw_amount = entry.get("amount")
        if not isinstance(raw_amount, str) or not _CANONICAL_AMOUNT.fullmatch(raw_amount):
            raise ValueError("accounting money amount must be a canonical decimal string")
        amount = Decimal(raw_amount)
        if max(0, -int(amount.as_tuple().exponent)) > scale:
            raise ValueError("accounting money amount exceeds its declared source scale")
        facts[key] = amount
    # Flat fields are legacy presentation projections. They cannot supply a
    # missing authoritative amount or override a large exact source amount.
    return facts
