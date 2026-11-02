"""Decimal coercion for value-driver metric extraction."""

from __future__ import annotations

from decimal import Decimal


def as_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError):
        return None
