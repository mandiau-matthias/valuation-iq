"""DCF-only response bridge helpers for comprehensive valuation responses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional

from src.utils.decimal_helpers import to_decimal


def decimal_from_dict(data: Dict[str, object], key: str) -> Optional[Decimal]:
    value = data.get(key)
    if value is None:
        return None
    try:
        dec = to_decimal(value)
        return dec if dec.is_finite() else None
    except Exception:
        return None


@dataclass(frozen=True)
class DcfBridgeInputs:
    enterprise_value_mid: Optional[Decimal]
    enterprise_value_low: Optional[Decimal]
    enterprise_value_high: Optional[Decimal]
    equity_value_mid: Optional[Decimal]
    equity_value_low: Optional[Decimal]
    equity_value_high: Optional[Decimal]


@dataclass(frozen=True)
class EquityBridgeValues:
    equity_value_low: Decimal
    equity_value_mid: Decimal
    equity_value_high: Decimal


def _positive(value: Optional[Decimal]) -> bool:
    return value is not None and value > 0


def _extract_bridge_inputs(raw_dcf_result: Dict[str, object]) -> DcfBridgeInputs:
    return DcfBridgeInputs(
        enterprise_value_mid=decimal_from_dict(raw_dcf_result, "enterprise_value"),
        enterprise_value_low=decimal_from_dict(raw_dcf_result, "enterprise_value_low"),
        enterprise_value_high=decimal_from_dict(raw_dcf_result, "enterprise_value_high"),
        equity_value_mid=decimal_from_dict(raw_dcf_result, "equity_value"),
        equity_value_low=decimal_from_dict(raw_dcf_result, "equity_value_low"),
        equity_value_high=decimal_from_dict(raw_dcf_result, "equity_value_high"),
    )


def _equity_from_enterprise_value(
    inputs: DcfBridgeInputs,
    net_debt: Decimal,
) -> EquityBridgeValues:
    enterprise_value_mid = inputs.enterprise_value_mid
    if enterprise_value_mid is None:
        raise ValueError("enterprise_value_mid is required for DCF EV bridge")

    equity_value_mid = enterprise_value_mid - net_debt
    bridge_correction = (
        equity_value_mid - inputs.equity_value_mid
        if _positive(inputs.equity_value_mid)
        else Decimal("0")
    )
    return EquityBridgeValues(
        equity_value_low=(
            inputs.equity_value_low + bridge_correction
            if _positive(inputs.equity_value_low)
            else equity_value_mid * Decimal("0.85")
        ),
        equity_value_mid=equity_value_mid,
        equity_value_high=(
            inputs.equity_value_high + bridge_correction
            if _positive(inputs.equity_value_high)
            else equity_value_mid * Decimal("1.15")
        ),
    )


def _equity_from_legacy_payload(inputs: DcfBridgeInputs) -> Optional[EquityBridgeValues]:
    equity_value_mid = inputs.equity_value_mid
    if not _positive(equity_value_mid) or equity_value_mid is None:
        return None
    return EquityBridgeValues(
        equity_value_low=(
            inputs.equity_value_low
            if _positive(inputs.equity_value_low)
            else equity_value_mid * Decimal("0.85")
        ),
        equity_value_mid=equity_value_mid,
        equity_value_high=(
            inputs.equity_value_high
            if _positive(inputs.equity_value_high)
            else equity_value_mid * Decimal("1.15")
        ),
    )


def _resolve_equity_bridge_values(
    inputs: DcfBridgeInputs,
    net_debt: Decimal,
) -> Optional[EquityBridgeValues]:
    if _positive(inputs.enterprise_value_mid):
        return _equity_from_enterprise_value(inputs, net_debt)
    return _equity_from_legacy_payload(inputs)


def _canonicalized_dcf_payload(
    raw_dcf_result: Dict[str, object],
    inputs: DcfBridgeInputs,
    equity_values: EquityBridgeValues,
    net_debt: Decimal,
) -> Dict[str, object]:
    updated_dcf = dict(raw_dcf_result)
    updated_dcf["equity_value"] = equity_values.equity_value_mid
    updated_dcf["equity_value_mid"] = equity_values.equity_value_mid
    updated_dcf["equity_value_low"] = equity_values.equity_value_low
    updated_dcf["equity_value_high"] = equity_values.equity_value_high

    enterprise_value_mid = inputs.enterprise_value_mid
    if _positive(enterprise_value_mid) and enterprise_value_mid is not None:
        updated_dcf["enterprise_value"] = enterprise_value_mid
        updated_dcf["enterprise_value_mid"] = enterprise_value_mid
        updated_dcf["enterprise_value_low"] = (
            inputs.enterprise_value_low
            if _positive(inputs.enterprise_value_low)
            else equity_values.equity_value_low + net_debt
        )
        updated_dcf["enterprise_value_high"] = (
            inputs.enterprise_value_high
            if _positive(inputs.enterprise_value_high)
            else equity_values.equity_value_high + net_debt
        )
    return updated_dcf


def canonicalize_dcf_only_bridge(
    raw_dcf_result: Dict[str, object],
    net_debt: Decimal,
) -> Optional[Dict[str, object]]:
    """
    Canonicalize DCF-only EV/equity fields in one place.

    FCFF DCF produces enterprise value directly. Equity must be the DCF EV
    minus net debt using the response builder's balance-sheet view, because
    filings/bootstrap cash can arrive outside the DCF engine's
    current_year_data. The nested dcf_valuation payload is updated too so
    report rendering and Titan persistence cannot drift back to the
    pre-bridge equity range.
    """
    inputs = _extract_bridge_inputs(raw_dcf_result)
    equity_values = _resolve_equity_bridge_values(inputs, net_debt)
    if equity_values is None:
        return None

    return {
        "equity_value_low": equity_values.equity_value_low,
        "equity_value_mid": equity_values.equity_value_mid,
        "equity_value_high": equity_values.equity_value_high,
        "dcf_valuation": _canonicalized_dcf_payload(
            raw_dcf_result,
            inputs,
            equity_values,
            net_debt,
        ),
    }


def is_requested_dcf_only(methodology: object) -> bool:
    normalized = str(methodology or "").strip().lower()
    snake = normalized.replace("-", "_").replace(" ", "_")
    is_discounted_cash_flow_alias = bool(
        re.fullmatch(r"discounted cash flow(?:\s*\(dcf\))?", normalized)
        or re.fullmatch(r"discounted_cash_flow_?\(?dcf\)?", snake)
    )
    return snake in {"dcf", "dcf_analysis", "discounted_cash_flow"} or is_discounted_cash_flow_alias


def requested_method_signal(request: object) -> object:
    for attr in (
        "selected_method",
        "selected_valuation_method",
        "method_override_selected_method",
        "primary_method_key",
        "methodology",
    ):
        value = getattr(request, attr, None)
        if value:
            return value
    metadata = getattr(request, "metadata", None)
    if isinstance(metadata, dict):
        for key in ("selected_method", "selected_valuation_method", "methodology"):
            value = metadata.get(key)
            if value:
                return value
    return None
