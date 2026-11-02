"""Equity post-processing helpers for stateless valuation calculation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.services.reports.stateless_bridge_adjustments import (
    resolve_stateless_bridge_adjustments,
)
from src.services.reports.stateless_completion_accounts import explicit_nwc_normalization


@dataclass(frozen=True)
class EquityAdjustmentState:
    equity_value_low: Decimal
    equity_value_mid: Decimal
    equity_value_high: Decimal
    equity_value_low_full: Decimal
    equity_value_mid_full: Decimal
    equity_value_high_full: Decimal
    ownership_percentage: Decimal
    ownership_multiplier: Decimal
    nwc_normalization_data: dict[str, object] | None
    bridge_adjustment_data: dict[str, object]
    bridge_adjustment_flags: list[object]


def apply_shareholding_to_equity(
    equity_value_low: Decimal,
    equity_value_mid: Decimal,
    equity_value_high: Decimal,
    shares_for_sale: Decimal | None,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    """Apply a 0-100 ownership stake to equity outputs."""
    ownership_percentage = shares_for_sale if shares_for_sale is not None else Decimal("100")
    ownership_multiplier = ownership_percentage / Decimal("100")

    adjusted_low = max(Decimal("0"), equity_value_low * ownership_multiplier).quantize(
        Decimal("0.01")
    )
    adjusted_mid = max(Decimal("0"), equity_value_mid * ownership_multiplier).quantize(
        Decimal("0.01")
    )
    adjusted_high = max(Decimal("0"), equity_value_high * ownership_multiplier).quantize(
        Decimal("0.01")
    )

    return adjusted_low, adjusted_mid, adjusted_high, ownership_percentage, ownership_multiplier


def apply_stateless_equity_adjustments(
    *,
    request,
    historical_data,
    current_year_data,
    equity_value_low: Decimal,
    equity_value_mid: Decimal,
    equity_value_high: Decimal,
    real_estate_surplus: Decimal,
    logger,
) -> EquityAdjustmentState:
    """Apply NWC, surplus assets, explicit bridge rows, then shareholding."""
    nwc_normalization_data = None
    try:
        explicit_nwc = explicit_nwc_normalization(request)
        if explicit_nwc is not None:
            nwc_adj = Decimal(str(explicit_nwc["surplus_deficit"]))
            equity_value_low += nwc_adj
            equity_value_mid += nwc_adj
            equity_value_high += nwc_adj
            nwc_normalization_data = explicit_nwc
        elif (
            not getattr(request, "completion_account_inputs_provided", False)
            and len(historical_data) >= 1
        ):
            from src.domain.nwc_normalizer import NWCNormalizer

            normalizer = NWCNormalizer()
            nwc_result = normalizer.normalize(historical_data, current_year_data)
            if nwc_result is not None:
                nwc_adj = nwc_result.surplus_deficit
                equity_value_low += nwc_adj
                equity_value_mid += nwc_adj
                equity_value_high += nwc_adj
                nwc_normalization_data = nwc_result.to_dict()
    except Exception as exc:
        logger.warning(
            "Stateless NWC normalization failed",
            extra={
                "valuation_id": request.valuation_id,
                "company_name": request.company_name,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
        nwc_normalization_data = {
            "available": False,
            "computation_error": True,
        }

    if real_estate_surplus != Decimal("0"):
        equity_value_low += real_estate_surplus
        equity_value_mid += real_estate_surplus
        equity_value_high += real_estate_surplus

    bridge_ledger = resolve_stateless_bridge_adjustments(request)
    if bridge_ledger.total != Decimal("0"):
        equity_value_low += bridge_ledger.total
        equity_value_mid += bridge_ledger.total
        equity_value_high += bridge_ledger.total

    equity_value_low_full = equity_value_low
    equity_value_mid_full = equity_value_mid
    equity_value_high_full = equity_value_high

    (
        equity_value_low,
        equity_value_mid,
        equity_value_high,
        ownership_percentage,
        ownership_multiplier,
    ) = apply_shareholding_to_equity(
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
        shares_for_sale=request.shares_for_sale,
    )

    return EquityAdjustmentState(
        equity_value_low=equity_value_low,
        equity_value_mid=equity_value_mid,
        equity_value_high=equity_value_high,
        equity_value_low_full=equity_value_low_full,
        equity_value_mid_full=equity_value_mid_full,
        equity_value_high_full=equity_value_high_full,
        ownership_percentage=ownership_percentage,
        ownership_multiplier=ownership_multiplier,
        nwc_normalization_data=nwc_normalization_data,
        bridge_adjustment_data=bridge_ledger.to_payload(),
        bridge_adjustment_flags=list(bridge_ledger.triage_flags),
    )
