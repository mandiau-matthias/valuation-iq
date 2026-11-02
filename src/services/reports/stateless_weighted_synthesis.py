"""Promote a weighted method synthesis at explicit currency boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from src.api.schemas.stateless_response_schemas import MethodResult
from src.api.schemas.weighted_valuation import WeightedMethodContribution, WeightedValuationResult
from src.domain.financial_arithmetic import decimal_number, money

_ENTERPRISE_COMPATIBLE_METHODS = {
    "upswitch_adaptive",
    "ebitda_multiple",
    "dcf",
    "sde_multiple",
    "omzet_multiple",
    "revenue_multiple",
    "arr_multiple",
}
_ZERO = Decimal("0")
_ONE = Decimal("1")


@dataclass(frozen=True)
class WeightedSynthesisHeadline:
    weighted_valuation: WeightedValuationResult
    equity_value_low: Decimal
    equity_value_mid: Decimal
    equity_value_high: Decimal
    enterprise_value_low: Decimal | None
    enterprise_value_mid: Decimal | None
    enterprise_value_high: Decimal | None


def _weight(row: WeightedMethodContribution) -> Decimal:
    value = decimal_number(
        row.weight_decimal if row.weight_decimal is not None else row.weight, "method weight"
    )
    if not _ZERO <= value <= _ONE:
        raise ValueError("method weight must lie between zero and one")
    return value


def _ordered_range(low: object, mid: object, high: object) -> tuple[Decimal, Decimal, Decimal]:
    midpoint = decimal_number(mid, "method midpoint")
    lower = midpoint if low is None else decimal_number(low, "method lower bound")
    upper = midpoint if high is None else decimal_number(high, "method upper bound")
    if not lower <= midpoint <= upper:
        raise ValueError("method range must satisfy low <= base <= high")
    return lower, midpoint, upper


def _widen(
    low: Decimal, mid: Decimal, high: Decimal, factor: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    return mid - (mid - low) * factor, mid, mid + (high - mid) * factor


def promote_weighted_synthesis(
    *,
    weighted_valuation: WeightedValuationResult,
    valuation_results: Mapping[str, MethodResult],
    ownership_multiplier: Decimal,
    total_debt: Decimal,
    cash: Decimal,
    nwc_adjustment: Decimal,
    common_equity_bridge_adjustment: Decimal,
) -> WeightedSynthesisHeadline:
    """Blend unrounded method amounts, bridge once, then round half-even.

    Shareholder values retain their established zero floor. Raw equity and
    debt overhang are saved beside that floor so financial deficits remain
    observable and cannot inflate a reconstructed enterprise value.
    """
    ownership = decimal_number(ownership_multiplier, "ownership multiplier")
    if not _ZERO <= ownership <= _ONE:
        raise ValueError("ownership multiplier must lie between zero and one")
    debt = decimal_number(total_debt, "total debt")
    cash_value = decimal_number(cash, "cash")
    nwc = decimal_number(nwc_adjustment, "working capital adjustment")
    common = decimal_number(common_equity_bridge_adjustment, "common equity bridge")
    factor = decimal_number(weighted_valuation.uncertainty_inflation_factor, "uncertainty factor")
    if factor < _ONE:
        raise ValueError("uncertainty factor cannot be less than one")
    contributions = weighted_valuation.contributions
    if not contributions:
        raise ValueError("weighted synthesis requires contributions")
    total_weight = sum((_weight(row) for row in contributions), _ZERO)
    if abs(total_weight - _ONE) > Decimal("0.000000000000001"):
        raise ValueError("weighted contributions must sum to one")
    # Normalize legacy float display aliases within representational tolerance.
    weights = [_weight(row) / total_weight for row in contributions]
    enterprise_primary = weighted_valuation.value_basis == "enterprise_value"
    if weighted_valuation.value_basis not in {"enterprise_value", "equity_value"}:
        raise ValueError("weighted synthesis requires an explicit valuation basis")
    low = mid = high = _ZERO
    for row, weight in zip(contributions, weights):
        if enterprise_primary:
            if row.enterprise_value is None:
                raise ValueError("enterprise synthesis requires every method enterprise value")
            row_low, row_mid, row_high = _ordered_range(
                row.enterprise_value_low, row.enterprise_value, row.enterprise_value_high
            )
        else:
            method = valuation_results.get(str(row.method_key))
            row_low, row_high = _method_range(method, row.equity_value)
            row_low, row_mid, row_high = _ordered_range(row_low, row.equity_value, row_high)
        low += row_low * weight
        mid += row_mid * weight
        high += row_high * weight

    full_bridge = -debt + cash_value + nwc + common
    pre_bridge_equity: Decimal | None = None
    enterprise_raw: tuple[Decimal, Decimal, Decimal] | None = None
    if enterprise_primary:
        if ownership <= _ZERO:
            raise ValueError("enterprise-value synthesis requires positive ownership")
        enterprise_raw = _widen(low, mid, high, factor)
        equity_raw = tuple((value + full_bridge) * ownership for value in enterprise_raw)
        bridge_correction = full_bridge * ownership
    else:
        pre_bridge_equity = mid
        adaptive_weight = sum(
            (
                weight
                for row, weight in zip(contributions, weights)
                if str(row.method_key) == "upswitch_adaptive"
            ),
            _ZERO,
        )
        bridge_correction = common * ownership * (_ONE - adaptive_weight)
        equity_raw = _widen(
            low + bridge_correction, mid + bridge_correction, high + bridge_correction, factor
        )
        method_keys = {str(row.method_key) for row in contributions}
        if ownership > _ZERO and method_keys <= _ENTERPRISE_COMPATIBLE_METHODS:
            enterprise_raw = (
                equity_raw[0] / ownership - full_bridge,
                equity_raw[1] / ownership - full_bridge,
                equity_raw[2] / ownership - full_bridge,
            )

    raw_low, raw_mid, raw_high = equity_raw
    equity_low, equity_mid, equity_high = (money(max(_ZERO, value)) for value in equity_raw)
    if enterprise_raw is None:
        enterprise_low = enterprise_mid = enterprise_high = None
    else:
        enterprise_low, enterprise_mid, enterprise_high = (money(value) for value in enterprise_raw)
    corrected = weighted_valuation.model_copy(
        update={
            "pre_common_bridge_blended_equity_value": pre_bridge_equity,
            "common_bridge_adjustment": bridge_correction,
            "blended_equity_value": equity_mid,
            "valuation_range_low": equity_low,
            "valuation_range_high": equity_high,
            "enterprise_value_low": enterprise_low,
            "enterprise_value_mid": enterprise_mid,
            "enterprise_value_high": enterprise_high,
            "raw_equity_value_low": raw_low,
            "raw_equity_value_mid": raw_mid,
            "raw_equity_value_high": raw_high,
            "debt_overhang": money(max(_ZERO, -raw_mid)),
        }
    )
    return WeightedSynthesisHeadline(
        corrected,
        equity_low,
        equity_mid,
        equity_high,
        enterprise_low,
        enterprise_mid,
        enterprise_high,
    )


def _method_range(method: MethodResult | None, fallback: Decimal) -> tuple[Decimal, Decimal]:
    if method is None:
        return fallback, fallback
    details = method.details if isinstance(method.details, Mapping) else {}
    low = next(
        (
            value
            for value in (
                method.equity_value_low,
                method.value_low,
                details.get("equity_range_low"),
            )
            if value is not None
        ),
        None,
    )
    high = next(
        (
            value
            for value in (
                method.equity_value_high,
                method.value_high,
                details.get("equity_range_high"),
            )
            if value is not None
        ),
        None,
    )
    lower, _, upper = _ordered_range(low, fallback, high)
    return lower, upper
