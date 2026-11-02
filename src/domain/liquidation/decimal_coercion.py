"""Decimal coercion helpers for liquidation-domain inputs."""

from __future__ import annotations

from decimal import Decimal


def to_decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except Exception:
        return None
