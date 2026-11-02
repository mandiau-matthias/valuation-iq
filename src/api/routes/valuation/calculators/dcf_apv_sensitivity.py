"""Add the admitted APV financing stream once to each operating EV scenario."""

from __future__ import annotations

from decimal import Decimal

from src.domain.dcf.apv_inputs import finite_amount
from src.domain.dcf.manual_assumption_validation import require_positive_discount_rate
from src.utils.exceptions import DataQualityError

from .dcf_manual_overrides import discount_to_present


def apv_is_priced(bridge: dict[str, object] | None) -> bool:
    if bridge is None:
        return False
    provenance = bridge.get("apv_bridge_provenance")
    return isinstance(provenance, dict) and provenance.get("included_in_dcf_value") is True


def scenario_tax_shield(bridge: dict[str, object], operating_rate: Decimal) -> Decimal:
    if not apv_is_priced(bridge):
        return Decimal(0)
    provenance = bridge["apv_bridge_provenance"]
    assert isinstance(provenance, dict)
    rate = (
        finite_amount(bridge["apv_discount_rate"], "tax-shield discount rate")
        if provenance.get("discount_rate_source") == "explicit_tax_shield_rate"
        else operating_rate
    )
    require_positive_discount_rate(rate)
    schedule = bridge.get("apv_tax_shield_projections")
    if not isinstance(schedule, list):
        raise DataQualityError("APV scenarios require the complete tax-shield schedule")
    offset = Decimal(".5") if bridge["apv_discounting_convention"] == "mid_year" else Decimal(0)
    return sum(
        (
            discount_to_present(
                finite_amount(value, "tax-shield schedule"), rate, Decimal(i) - offset
            )
            for i, value in enumerate(schedule, 1)
        ),
        Decimal(0),
    )


def apply_apv_sensitivity_basis(
    bridge: dict[str, object] | None,
    sensitivity_wacc: dict[str, object],
    sensitivity_growth: dict[str, object],
    matrix: dict[str, object] | None,
    *,
    base_rate: Decimal,
) -> tuple[dict[str, object], dict[str, object], dict[str, object] | None]:
    if not apv_is_priced(bridge):
        return sensitivity_wacc, sensitivity_growth, matrix
    assert bridge is not None
    # Idempotence at the versioned aggregate boundary; no second admission.
    if matrix is not None and matrix.get("value_basis") == "apv_enterprise_value":
        return sensitivity_wacc, sensitivity_growth, matrix
    base_addition = scenario_tax_shield(bridge, base_rate)
    sw: dict[str, object] = {
        key: finite_amount(value, "scenario value") + scenario_tax_shield(bridge, Decimal(key))
        for key, value in sensitivity_wacc.items()
    }
    sg: dict[str, object] = {
        key: finite_amount(value, "scenario value") + base_addition
        for key, value in sensitivity_growth.items()
    }
    updated_matrix: dict[str, object] | None = None
    if matrix is not None:
        rates, rows = matrix.get("wacc_values"), matrix.get("ev_matrix")
        if not isinstance(rates, list) or not isinstance(rows, list) or len(rates) != len(rows):
            raise DataQualityError("APV scenario axes must match their value rows")
        values = []
        for rate, row in zip(rates, rows):
            if not isinstance(row, list):
                raise DataQualityError("APV scenario matrix requires ordered value rows")
            addition = (
                scenario_tax_shield(bridge, finite_amount(rate, "scenario rate"))
                if any(cell is not None for cell in row)
                else Decimal(0)
            )
            values.append(
                [
                    None if cell is None else finite_amount(cell, "scenario value") + addition
                    for cell in row
                ]
            )
        updated_matrix = {
            **matrix,
            "ev_matrix": values,
            "value_basis": "apv_enterprise_value",
            "apv_contract_version": "apv_tax_shield.v2",
            "apv_discount_rate_source": _rate_source(bridge),
        }
    return sw, sg, updated_matrix


def apply_apv_advisor_range(
    bridge: dict[str, object] | None, sensitivity: dict[str, object] | None, base_rate: Decimal
) -> None:
    if not apv_is_priced(bridge) or sensitivity is None:
        return
    assert bridge is not None
    policy = sensitivity["sensitivity_range_policy"]
    assert isinstance(policy, dict)
    delta = finite_amount(policy["wacc_delta"], "scenario WACC delta")
    for field, rate in (
        ("enterprise_value_low", base_rate + delta),
        ("enterprise_value_high", base_rate - delta),
    ):
        sensitivity[field] = finite_amount(
            sensitivity[field], "scenario value"
        ) + scenario_tax_shield(bridge, rate)
    margins = sensitivity["ebitda_margin_sensitivity"]
    assert isinstance(margins, dict)
    sensitivity["ebitda_margin_sensitivity"] = {
        key: finite_amount(value, "scenario value") + scenario_tax_shield(bridge, base_rate)
        for key, value in margins.items()
    }
    sensitivity["sensitivity_range_policy"] = {
        **policy,
        "policy_version": "advisor_dcf_three_driver.v2",
        "value_basis": "apv_enterprise_value",
        "apv_discount_rate_source": _rate_source(bridge),
    }


def _rate_source(bridge: dict[str, object]) -> object:
    provenance = bridge.get("apv_bridge_provenance")
    return provenance.get("discount_rate_source") if isinstance(provenance, dict) else None
