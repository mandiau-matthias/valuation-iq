"""Strict Decimal arithmetic shared by monetary method boundaries.

Legacy JSON numbers remain accepted, but calculations use their decimal text.
Unknown or invalid money is never a zero. Round only at output boundaries.
"""

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

FinancialNumber = Decimal | float | int | str


def decimal_number(value: object, field: str = "financial value") -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, float, int, str)):
        raise ValueError(f"{field} must be a finite decimal number")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be a finite decimal number") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be a finite decimal number")
    return result


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal(".01"), rounding=ROUND_HALF_EVEN)


def multiple_bounds(
    median: Decimal, low: object, high: object, *, spread: Decimal = Decimal(".20")
) -> tuple[Decimal, Decimal, dict[str, object]]:
    """Preserve supplied bounds and identify assumptions without claiming coverage."""
    median = decimal_number(median, "median multiple")
    lower = median * (1 - spread) if low is None else decimal_number(low, "lower multiple")
    upper = median * (1 + spread) if high is None else decimal_number(high, "upper multiple")
    if not Decimal(0) <= lower <= median <= upper:
        raise ValueError("multiple bounds must satisfy 0 <= lower <= median <= upper")
    assumed = low is None or high is None
    return (
        lower,
        upper,
        {
            "schema_version": "valuation_range_basis.v1",
            "kind": "assumed_multiple_spread" if assumed else "supplied_multiple_bounds",
            "empirical_percentiles": False,
            "lower_bound_supplied": low is not None,
            "upper_bound_supplied": high is not None,
            "assumed_spread": spread if assumed else None,
            "statistical_coverage": None,
        },
    )
