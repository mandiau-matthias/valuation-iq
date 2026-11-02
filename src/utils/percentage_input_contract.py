"""Versioned units for adaptive inputs, without reinterpreting legacy snapshots.

Only fields consumed by the shared adaptive readers participate. Other contracts
(APV, economic snapshots, ownership, taxes) retain their own explicit units.
"""

import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

CONTRACT_KEY = "percentage_input_contract"
CONTRACT_VERSION = "percentage_inputs.v1"
PERCENTAGE_FIELDS = frozenset(
    {
        "dcf_revenue_growth_pct",
        "dcf_ebitda_margin_pct",
        "dcf_capex_pct",
        "dcf_da_pct",
        "dcf_nwc_pct",
        "dcf_tax_rate_pct",
        "dcf_wacc_pct",
        "dcf_terminal_growth_pct",
        "dcf_risk_free_rate_pct",
        "dcf_equity_risk_premium_pct",
        "dcf_cost_of_debt_pct",
        "dcf_debt_equity_pct",
        "dcf_tax_shield_pct",
        "dcf_size_premium_pct",
        "dcf_company_specific_risk_pct",
        "dcf_sensitivity_wacc_delta_pct",
        "dcf_sensitivity_terminal_growth_min_pct",
        "dcf_sensitivity_terminal_growth_max_pct",
        "dcf_sensitivity_ebitda_margin_min_pct",
        "dcf_sensitivity_ebitda_margin_max_pct",
        "saas_arr_growth_pct",
        "saas_churn_pct",
        "saas_customer_churn_pct",
        "saas_nrr_pct",
        "saas_gross_margin_pct",
        "saas_customer_concentration_pct",
        "saas_expansion_revenue_pct",
        "rev_recurring_pct",
        "rev_top_client_concentration_pct",
        "rev_gross_churn_pct",
    }
)


def percentage_units(context: Mapping[str, object]) -> Mapping[str, str]:
    if CONTRACT_KEY not in context:
        return {}
    contract = context[CONTRACT_KEY]
    if not isinstance(contract, Mapping) or set(contract) != {"schema_version", "units"}:
        raise ValueError("percentage_input_contract requires schema_version and units only")
    if contract["schema_version"] != CONTRACT_VERSION:
        raise ValueError("Unsupported percentage_input_contract schema_version")
    units = contract["units"]
    if not isinstance(units, Mapping) or not units:
        raise ValueError("percentage_input_contract.units must be a non-empty field map")
    for key, unit in units.items():
        if key not in PERCENTAGE_FIELDS or unit not in ("percentage_points", "fraction"):
            raise ValueError(f"Unsupported percentage input field or unit: {key!r}")
    return units


def declared_percentage(context: Mapping[str, object], key: str) -> Decimal | None:
    """Return a fraction for a declared input; untagged/missing inputs return None."""
    unit = percentage_units(context).get(key)
    raw = context.get(key)
    if unit is None or raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float, Decimal)):
        raise ValueError(f"{key} must be a finite numeric scalar with the declared unit")
    text = str(raw).strip()
    if text.endswith(("%", "％")):
        if unit != "percentage_points":
            raise ValueError(f"{key}: percent suffix conflicts with declared fraction unit")
        text = text[:-1].strip()
    if (
        len(text) > 128
        or re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text) is None
    ):
        raise ValueError(f"{key} must be a finite canonical decimal")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"{key} must be a finite canonical decimal") from exc
    if not value.is_finite():
        raise ValueError(f"{key} must be finite")
    if unit == "fraction":
        return value
    sign, digits, exponent = value.as_tuple()
    # Changing the exponent is exact even when a serialized input has more
    # significant digits than the active arithmetic context's precision.
    return Decimal((sign, digits, exponent - 2))


def validate_context_percentage_units(value: object) -> object:
    if isinstance(value, Mapping):
        for key in percentage_units(value):
            declared_percentage(value, key)
    return value


def percentage_input_provenance(context: Mapping[str, object]) -> dict[str, object] | None:
    """Seal raw values, units and exact interpreted fractions into a new run."""
    units = percentage_units(context)
    if not units:
        return None
    fields = {}
    for key, unit in sorted(units.items()):
        fraction = declared_percentage(context, key)
        fields[key] = {
            "input": None if context.get(key) is None else str(context[key]),
            "unit": unit,
            "fraction": None if fraction is None else str(fraction),
        }
    return {"schema_version": CONTRACT_VERSION, "fields": fields}


def with_fraction_inputs(
    context: Mapping[str, object], values: Mapping[str, object]
) -> dict[str, object]:
    """Atomically replace a modeled value and its units, preserving other inputs."""
    result = {
        **context,
        **values,
        CONTRACT_KEY: {
            "schema_version": CONTRACT_VERSION,
            "units": {**percentage_units(context), **{key: "fraction" for key in values}},
        },
    }
    validate_context_percentage_units(result)
    return result
