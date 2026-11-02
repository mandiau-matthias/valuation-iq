"""Canonical DCF/market adaptive headline synthesis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN

from src.api.schemas.stateless_response_schemas import MethodResult
from src.domain.methods._shared import dcf_equity_from_ev
from src.domain.financial_arithmetic import FinancialNumber, decimal_number

ADAPTIVE_SYNTHESIS_POLICY_VERSION = "adaptive_equity_synthesis.v2"


@dataclass(frozen=True)
class AdaptiveSynthesisHeadline:
    equity_value_low: Decimal
    equity_value_mid: Decimal
    equity_value_high: Decimal
    enterprise_value_low: Decimal
    enterprise_value_mid: Decimal
    enterprise_value_high: Decimal
    methodology_used: str
    methodology_selection_reason: str
    adaptive_method: MethodResult


def promote_adaptive_methodology_synthesis(
    *,
    valuation_results: Mapping[str, MethodResult],
    dcf_results: Mapping[str, object] | None,
    dcf_weight: Decimal,
    multiples_weight: Decimal,
    multiples_equity_low: Decimal,
    multiples_equity_mid: Decimal,
    multiples_equity_high: Decimal,
    multiples_enterprise_low: Decimal | None,
    multiples_enterprise_mid: Decimal | None,
    multiples_enterprise_high: Decimal | None,
    total_debt: FinancialNumber,
    cash: FinancialNumber,
    nwc_adjustment: FinancialNumber,
    ownership_multiplier: Decimal,
    common_equity_bridge_adjustment: Decimal,
    current_reason: str | None,
    uncertainty_inflation_factor: Decimal = Decimal("1"),
) -> AdaptiveSynthesisHeadline | None:
    """Blend eligible method equities and never pass EV off as equity.

    The market headline already includes the shared post-method equity bridge.
    The DCF method result includes its debt/cash bridge, so only the shared
    real-estate/tax/balance-sheet adjustment is added to that leg before
    weighting. No risk/discount stack is applied a second time.
    """
    dcf_weight = decimal_number(dcf_weight, "DCF weight")
    multiples_weight = decimal_number(multiples_weight, "market weight")
    uncertainty_inflation_factor = decimal_number(
        uncertainty_inflation_factor, "uncertainty factor"
    )
    if dcf_weight < 0 or multiples_weight < 0 or uncertainty_inflation_factor < 1:
        raise ValueError("weights must be nonnegative and uncertainty factor at least one")
    dcf_method = valuation_results.get("dcf")
    if (
        dcf_weight <= 0
        or dcf_method is None
        or not dcf_method.available
        or dcf_method.value is None
        or not dcf_results
    ):
        return None

    total_weight = dcf_weight + max(Decimal("0"), multiples_weight)
    if total_weight <= 0:
        return None
    resolved_dcf_weight = dcf_weight / total_weight
    resolved_multiples_weight = max(Decimal("0"), multiples_weight) / total_weight
    shared_bridge = common_equity_bridge_adjustment * ownership_multiplier

    dcf_equity_mid = decimal_number(dcf_method.value) + shared_bridge
    dcf_ev_mid = decimal_number(dcf_results.get("enterprise_value"))
    dcf_equity_low, dcf_equity_high, dcf_ev_low, dcf_ev_high = _dcf_ranges(
        method=dcf_method,
        dcf_results=dcf_results,
        total_debt=total_debt,
        cash=cash,
        nwc_adjustment=nwc_adjustment,
        ownership_multiplier=ownership_multiplier,
        shared_bridge=shared_bridge,
    )

    if resolved_multiples_weight > 0 and multiples_enterprise_mid is None:
        raise ValueError("market synthesis requires an explicit enterprise midpoint")
    market_ev_mid = (
        multiples_enterprise_mid if multiples_enterprise_mid is not None else Decimal("0")
    )
    market_ev_low = (
        multiples_enterprise_low if multiples_enterprise_low is not None else market_ev_mid
    )
    market_ev_high = (
        multiples_enterprise_high if multiples_enterprise_high is not None else market_ev_mid
    )
    for lower, midpoint, upper in (
        (multiples_equity_low, multiples_equity_mid, multiples_equity_high),
        (market_ev_low, market_ev_mid, market_ev_high),
    ):
        if not decimal_number(lower) <= decimal_number(midpoint) <= decimal_number(upper):
            raise ValueError("market range must satisfy low <= base <= high")
    raw_equity_mid = (
        dcf_equity_mid * resolved_dcf_weight + multiples_equity_mid * resolved_multiples_weight
    )
    raw_equity_low = (
        dcf_equity_low * resolved_dcf_weight + multiples_equity_low * resolved_multiples_weight
    )
    raw_equity_high = (
        dcf_equity_high * resolved_dcf_weight + multiples_equity_high * resolved_multiples_weight
    )
    raw_enterprise_mid = (
        dcf_ev_mid * resolved_dcf_weight + market_ev_mid * resolved_multiples_weight
    )
    raw_enterprise_low = (
        dcf_ev_low * resolved_dcf_weight + market_ev_low * resolved_multiples_weight
    )
    raw_enterprise_high = (
        dcf_ev_high * resolved_dcf_weight + market_ev_high * resolved_multiples_weight
    )
    for lower, midpoint, upper in (
        (raw_equity_low, raw_equity_mid, raw_equity_high),
        (raw_enterprise_low, raw_enterprise_mid, raw_enterprise_high),
    ):
        if not lower <= midpoint <= upper:
            raise ValueError("adaptive range must satisfy low <= base <= high")
    raw_equity_low = (
        raw_equity_mid - (raw_equity_mid - raw_equity_low) * uncertainty_inflation_factor
    )
    raw_equity_high = (
        raw_equity_mid + (raw_equity_high - raw_equity_mid) * uncertainty_inflation_factor
    )
    raw_enterprise_low = (
        raw_enterprise_mid
        - (raw_enterprise_mid - raw_enterprise_low) * uncertainty_inflation_factor
    )
    raw_enterprise_high = (
        raw_enterprise_mid
        + (raw_enterprise_high - raw_enterprise_mid) * uncertainty_inflation_factor
    )
    equity_low, equity_mid, equity_high = (
        max(Decimal("0"), value).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        for value in (raw_equity_low, raw_equity_mid, raw_equity_high)
    )
    enterprise_low, enterprise_mid, enterprise_high = (
        value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        for value in (raw_enterprise_low, raw_enterprise_mid, raw_enterprise_high)
    )

    methodology_used = "DCF" if resolved_multiples_weight == 0 else "HYBRID"
    reason = (
        f"{current_reason or 'Adaptive methodology selected.'} "
        f"Resolved under {ADAPTIVE_SYNTHESIS_POLICY_VERSION}: "
        f"DCF {resolved_dcf_weight:.2%}, market {resolved_multiples_weight:.2%}; "
        "each method is bridged to equity exactly once before synthesis."
    )
    prior_adaptive = valuation_results.get("upswitch_adaptive")
    if methodology_used == "DCF":
        details: dict[str, object] = {
            "description": (
                "Explicit normalized FCFF discounted at the resolved WACC; no "
                "market-multiple benchmark enters the priced result."
            ),
            "primary_basis": "dcf",
            "dcf_method_details": dict(dcf_method.details or {}),
        }
    else:
        details = (
            dict(prior_adaptive.details)
            if prior_adaptive is not None and isinstance(prior_adaptive.details, Mapping)
            else {}
        )
    details["raw_equity_value_low"] = raw_equity_low
    details["raw_equity_value_mid"] = raw_equity_mid
    details["raw_equity_value_high"] = raw_equity_high
    details["debt_overhang"] = max(Decimal("0"), -raw_equity_mid)
    details["range_provenance"] = {
        "kind": "weighted_method_ranges",
        "statistical_coverage": None,
        "uncertainty_factor": uncertainty_inflation_factor,
    }
    details["adaptive_weighting"] = {
        "policy_version": ADAPTIVE_SYNTHESIS_POLICY_VERSION,
        "dcf_weight": resolved_dcf_weight,
        "multiples_weight": resolved_multiples_weight,
        "weight_basis": "eligible_method_equity_values",
        "common_equity_bridge_adjustment": shared_bridge,
        "uncertainty_inflation_factor": uncertainty_inflation_factor,
    }
    adaptive_method = MethodResult(
        value=equity_mid,
        equity_value=equity_mid,
        equity_value_low=equity_low,
        equity_value_high=equity_high,
        enterprise_value=enterprise_mid,
        enterprise_value_low=enterprise_low,
        enterprise_value_high=enterprise_high,
        multiple_used=None,
        wacc=dcf_method.wacc,
        unavailable_reason=None,
        value_low=equity_low,
        value_high=equity_high,
        value_basis="equity_value",
        method_key="upswitch_adaptive",
        label="UpSwitch Adaptive" if methodology_used == "HYBRID" else "Discounted Cash Flow",
        available=True,
        confidence=dcf_method.confidence,
        engine_version=ADAPTIVE_SYNTHESIS_POLICY_VERSION,
        details=details,
    )
    return AdaptiveSynthesisHeadline(
        equity_value_low=equity_low,
        equity_value_mid=equity_mid,
        equity_value_high=equity_high,
        enterprise_value_low=enterprise_low,
        enterprise_value_mid=enterprise_mid,
        enterprise_value_high=enterprise_high,
        methodology_used=methodology_used,
        methodology_selection_reason=reason,
        adaptive_method=adaptive_method,
    )


def _dcf_ranges(
    *,
    method: MethodResult,
    dcf_results: Mapping[str, object],
    total_debt: FinancialNumber,
    cash: FinancialNumber,
    nwc_adjustment: FinancialNumber,
    ownership_multiplier: Decimal,
    shared_bridge: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    mid_equity = decimal_number(method.value) + shared_bridge
    mid_ev = decimal_number(dcf_results.get("enterprise_value"))
    ev_values = _sensitivity_enterprise_values(dcf_results.get("sensitivity_matrix_2d"))
    if not ev_values:
        method_low = decimal_number(method.value_low) if method.value_low is not None else None
        method_high = decimal_number(method.value_high) if method.value_high is not None else None
        return (
            (method_low + shared_bridge) if method_low is not None else mid_equity,
            (method_high + shared_bridge) if method_high is not None else mid_equity,
            mid_ev,
            mid_ev,
        )

    ev_low = min(ev_values)
    ev_high = max(ev_values)
    equity_values = [
        dcf_equity_from_ev(
            ev,
            total_debt=total_debt,
            cash=cash,
            ownership_multiplier=ownership_multiplier,
            nwc_adjustment=nwc_adjustment,
        )
        + shared_bridge
        for ev in (ev_low, ev_high)
    ]
    return min(equity_values), max(equity_values), ev_low, ev_high


def _sensitivity_enterprise_values(value: object) -> list[Decimal]:
    if not isinstance(value, Mapping):
        return []
    matrix = value.get("ev_matrix")
    if not isinstance(matrix, Sequence) or isinstance(matrix, (str, bytes)):
        return []
    values: list[Decimal] = []
    for row in matrix:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
            raise ValueError("sensitivity matrix rows must be sequences")
        for cell in row:
            if cell is None:
                continue  # An unavailable sensitivity cell is not an observed zero.
            values.append(decimal_number(cell, "available sensitivity cell"))
    return values
