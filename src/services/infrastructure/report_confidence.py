"""Report-facing confidence score normalization.

Valuation engines in this codebase emit confidence as both ratios (0-1) and
percent scores (0-100). Report templates and report transformers expect
percent scores, so normalize at the report boundary.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from src.utils.decimal_helpers import to_decimal


def confidence_score_percent(
    value: Any,
    default: Optional[Decimal] = None,
) -> Optional[Decimal]:
    """Return confidence as a clamped ``0-100`` Decimal percent score."""
    if value is None:
        return default

    try:
        score = to_decimal(value)
    except (TypeError, ValueError):
        return default

    if Decimal("0") <= score <= Decimal("1"):
        score *= Decimal("100")

    if score < Decimal("0"):
        score = Decimal("0")
    elif score > Decimal("100"):
        score = Decimal("100")

    if score == score.to_integral_value():
        return score.quantize(Decimal("1"))
    return score


def confidence_score_fraction(value: Any, default: float = 0.0) -> float:
    """Return confidence as a ``0-1`` float for chart/template contracts."""
    score = confidence_score_percent(value)
    if score is None:
        return default
    return float(score / Decimal("100"))


def confidence_score_display(value: Any, default: str = "0") -> str:
    """Return a whole-number confidence percent string for report copy."""
    score = confidence_score_percent(value)
    if score is None:
        return default
    return str(score.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
