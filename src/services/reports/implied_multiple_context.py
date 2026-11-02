"""Implied EBITDA-multiple display policy for report aggregation."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

NumberLike = Decimal | float | int | str | None

LOW_MARGIN_OUTLIER_REASON = "implied_ebitda_multiple_low_margin_outlier"
MAX_DEFENSIBLE_IMPLIED_EBITDA_MULTIPLE = Decimal("25.0")
LOW_MARGIN_SUPPRESSION_THRESHOLD = Decimal("0.08")


def _to_decimal(value: NumberLike) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def build_implied_ebitda_multiple_context(
    *,
    metric_type: str,
    enterprise_value_mid: NumberLike,
    sustainable_ebitda: NumberLike,
    revenue_value: NumberLike,
) -> dict[str, float | str | None]:
    """Build the report-facing implied EBITDA-multiple context.

    The implied multiple is useful only when EV was primarily derived from a
    revenue multiple and EBITDA is positive. Thin-margin businesses can produce
    formally correct but commercially misleading cross-checks, so those are
    suppressed with a stable reason key for templates.
    """
    if metric_type != "REVENUE":
        return {
            "implied_ebitda_multiple": None,
            "implied_ebitda_multiple_suppressed_reason": None,
        }

    ev_mid = _to_decimal(enterprise_value_mid)
    ebitda = _to_decimal(sustainable_ebitda)
    revenue = _to_decimal(revenue_value)

    if ev_mid <= 0 or ebitda <= 0:
        return {
            "implied_ebitda_multiple": None,
            "implied_ebitda_multiple_suppressed_reason": None,
        }

    implied_multiple = ev_mid / ebitda
    margin = ebitda / revenue if revenue > 0 else None
    is_low_margin_outlier = (
        margin is not None
        and implied_multiple > MAX_DEFENSIBLE_IMPLIED_EBITDA_MULTIPLE
        and margin < LOW_MARGIN_SUPPRESSION_THRESHOLD
    )
    if is_low_margin_outlier:
        return {
            "implied_ebitda_multiple": None,
            "implied_ebitda_multiple_suppressed_reason": LOW_MARGIN_OUTLIER_REASON,
        }

    return {
        "implied_ebitda_multiple": round(float(implied_multiple), 1),
        "implied_ebitda_multiple_suppressed_reason": None,
    }
