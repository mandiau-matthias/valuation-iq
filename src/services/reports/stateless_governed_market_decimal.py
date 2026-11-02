"""Exact-cent governed external market-reference method projection."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from typing import MutableMapping

from src.api.schemas.stateless_api import CalculateRequest
from src.api.schemas.stateless_response_schemas import MethodResult

_CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_EVEN)


def replace_governed_external_market_method(
    *,
    request: CalculateRequest,
    valuation_results: MutableMapping[str, MethodResult],
    ebitda_basis: Decimal,
    total_debt: Decimal,
    cash: Decimal,
    nwc_adjustment: Decimal,
    ownership_multiplier: Decimal,
) -> None:
    """Replace only the non-Index governed reference leg with Decimal math.

    Contracted Index methods keep their existing engine path byte-for-byte.
    The advisor reference contract is explicitly non-statistical and carries
    exact low/applied/high multiples, so binary-float rounding has no role in
    either the EV contribution or its one-time equity bridge.
    """

    contract = request.external_market_reference_contract
    if contract is None or ebitda_basis <= 0:
        return

    low_raw = ebitda_basis * contract.range_low_multiple
    mid_raw = ebitda_basis * contract.applied_multiple
    high_raw = ebitda_basis * contract.range_high_multiple
    low_raw, high_raw = min(low_raw, high_raw), max(low_raw, high_raw)
    bridge = -total_debt + cash + nwc_adjustment
    unfloored_low = (low_raw + bridge) * ownership_multiplier
    unfloored_mid = (mid_raw + bridge) * ownership_multiplier
    unfloored_high = (high_raw + bridge) * ownership_multiplier
    eq_low_raw = max(Decimal("0"), unfloored_low)
    eq_mid_raw = max(Decimal("0"), unfloored_mid)
    eq_high_raw = max(Decimal("0"), unfloored_high)

    prior = valuation_results.get("ebitda_multiple")
    details = dict(prior.details or {}) if prior is not None else {}
    details.update(
        {
            "enterprise_value": _money(mid_raw),
            "enterprise_value_low": _money(low_raw),
            "enterprise_value_high": _money(high_raw),
            "enterprise_value_unrounded": mid_raw,
            "raw_equity_value_low": unfloored_low,
            "raw_equity_value_mid": unfloored_mid,
            "raw_equity_value_high": unfloored_high,
            "debt_overhang": _money(max(Decimal("0"), -unfloored_mid)),
            "enterprise_value_low_unrounded": low_raw,
            "enterprise_value_high_unrounded": high_raw,
            "equity_range_low": _money(eq_low_raw),
            "equity_range_high": _money(eq_high_raw),
            "reference_enterprise_value": _money(mid_raw),
            "reference_multiple": contract.applied_multiple,
            "p25_multiple": None,
            "p75_multiple": None,
            "rounding_policy": "decimal_round_half_even_at_method_output",
            "source_contract": "governed_external_market_reference",
            "empirical_percentiles": None,
        }
    )
    valuation_results["ebitda_multiple"] = MethodResult(
        value=_money(eq_mid_raw),
        value_low=_money(eq_low_raw),
        value_high=_money(eq_high_raw),
        equity_value=_money(eq_mid_raw),
        equity_value_low=_money(eq_low_raw),
        equity_value_high=_money(eq_high_raw),
        # Preserve exact method EVs for synthesis. Report/currency formatting
        # rounds only at presentation; rounded controls remain in details.
        enterprise_value=mid_raw,
        enterprise_value_low=low_raw,
        enterprise_value_high=high_raw,
        method_key="ebitda_multiple",
        label=(prior.label if prior is not None else "EBITDA-multiple"),
        multiple_used=contract.applied_multiple,
        available=True,
        confidence=(prior.confidence if prior is not None else "medium"),
        engine_version="governed_external_market_decimal.v1",
        details=details,
    )

    # Weighted Venus dossiers normally assign the market leg to the adaptive
    # key. Before a DCF is blended this row represents the same market method,
    # so replace its float-rounded EV fields as well. The later adaptive DCF
    # synthesizer may overwrite it with a true hybrid row when applicable.
    adaptive = valuation_results.get("upswitch_adaptive")
    if adaptive is not None and adaptive.available:
        adaptive_details = dict(adaptive.details or {})
        adaptive_details.update(details)
        valuation_results["upswitch_adaptive"] = MethodResult(
            value=_money(eq_mid_raw),
            value_low=_money(eq_low_raw),
            value_high=_money(eq_high_raw),
            equity_value=_money(eq_mid_raw),
            equity_value_low=_money(eq_low_raw),
            equity_value_high=_money(eq_high_raw),
            enterprise_value=mid_raw,
            enterprise_value_low=low_raw,
            enterprise_value_high=high_raw,
            method_key="upswitch_adaptive",
            label=adaptive.label,
            multiple_used=contract.applied_multiple,
            available=True,
            confidence=adaptive.confidence,
            engine_version="governed_external_market_decimal.v1",
            details=adaptive_details,
        )
