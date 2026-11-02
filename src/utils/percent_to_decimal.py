"""Normalize sovereign yields and similar rates to 0–1 decimal fractions."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Union

Number = Union[int, float, Decimal]


def percentage_points_to_decimal_decimal(raw: Optional[Number]) -> Optional[Decimal]:
    """Convert a source explicitly denominated in percent, without guessing units.

    Delphi's country-context API declares these fields as percentage points.
    Low rates, deflation and zero have the same unit as rates above one percent.
    Request-level decimal fractions and legacy ambiguous inputs use other paths.
    """
    if raw is None:
        return None
    return Decimal(str(raw)) / Decimal("100")


def percentage_points_to_decimal(raw: Optional[Number]) -> Optional[float]:
    """Float result for known percentage-point sources."""
    value = percentage_points_to_decimal_decimal(raw)
    return float(value) if value is not None else None


def percent_to_decimal(raw: Optional[Number]) -> Optional[float]:
    """
    Legacy magnitude-based compatibility for inputs with ambiguous units.

    Never use this for a source with declared units, such as country-context.

    Storage conventions:
    - Percent points (e.g. 3.1 for 3.1%) when value > 1
    - Decimal fraction (e.g. 0.031 for 3.1%) when 0.005 <= value <= 1
    - Double-divided artifacts (e.g. 0.00031) recover via ×100 when < 0.005
    """
    if raw is None:
        return None
    value = float(raw)
    if value > 1.0:
        return value / 100.0
    if value >= 0.005:
        return value
    if value > 0.0:
        recovered = value * 100.0
        if recovered >= 0.005:
            return recovered
    return value


def percent_to_decimal_decimal(raw: Optional[Number]) -> Optional[Decimal]:
    """Decimal variant for DCF adapters."""
    if raw is None:
        return None
    value = Decimal(str(raw))
    if value > Decimal("1.0"):
        return value / Decimal("100.0")
    if value >= Decimal("0.005"):
        return value
    if value > Decimal("0.0"):
        recovered = value * Decimal("100.0")
        if recovered >= Decimal("0.005"):
            return recovered
    return value
