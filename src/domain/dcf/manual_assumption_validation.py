"""Mathematical admission of advisor-supplied DCF assumptions.

An invalid requested model cannot be repaired by inventing a discount spread.
These guards impose mathematical constraints, not a market-calibrated rate cap.
"""

from collections.abc import Sequence
from decimal import Decimal

from src.utils.decimal_helpers import optional_decimal
from src.utils.exceptions import DataQualityError


def require_positive_discount_rate(wacc: Decimal) -> None:
    if not wacc.is_finite() or wacc <= 0:
        raise DataQualityError("DCF discount rate must be finite and positive")


def require_valid_gordon_growth(wacc: Decimal, growth: Decimal) -> None:
    require_positive_discount_rate(wacc)
    if not growth.is_finite() or growth <= -1 or growth >= wacc:
        raise DataQualityError(
            "DCF terminal growth must be finite, greater than -100%, and below WACC"
        )


def require_override_cash_flows(raw_values: Sequence[object]) -> list[Decimal]:
    """Never relabel an old EV or shift discount periods by dropping missing rows."""
    if not raw_values:
        raise DataQualityError("DCF overrides require a nonempty cash-flow forecast")
    values: list[Decimal] = []
    for raw in raw_values:
        value = optional_decimal(raw)
        if value is None:
            raise DataQualityError("DCF overrides require finite cash flows for every period")
        values.append(value)
    return values
