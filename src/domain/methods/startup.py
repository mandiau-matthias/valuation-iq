"""Startup Valuation method — thin adapter over the isolated package.

The real math lives in ``src.domain.startup_valuation`` so it can be
extended (e.g. with Athena live regional data) without touching the
Omni-Calc dispatcher.  This module exists only to expose the same
``calculate_*_result`` shape every other method in this folder uses.
"""

from decimal import ROUND_HALF_EVEN, localcontext
from typing import Optional

from src.api.schemas.stateless_api import MethodResult
from src.domain.startup_valuation import (
    StartupInputs,
    blend_to_method_result,
    get_regional_reference_data,
)


def calculate_startup_result(
    *,
    startup_inputs: Optional[StartupInputs],
) -> MethodResult:
    """Return a :class:`MethodResult` for the Startup Valuation method.

    When ``startup_inputs`` is missing, returns an unavailable result so
    the Omni-Calc grid still includes the entry without crashing.
    """
    if startup_inputs is None:
        return MethodResult(
            value=None,
            method_key="startup_valuation",
            label="Startup Valuation",
            available=False,
            unavailable_reason=(
                "Startup-waardering vereist kwalitatieve invoer (sliders, traction, "
                "cap-table) — niet beschikbaar voor klassieke KMO-flows."
            ),
        )

    region_data = get_regional_reference_data(
        startup_inputs.country_code, startup_inputs.stage, sector=startup_inputs.sector
    )
    # Startup money helpers inherit the local context; pin the declared policy.
    with localcontext() as context:
        context.rounding = ROUND_HALF_EVEN
        result = blend_to_method_result(startup_inputs, region_data=region_data)
    details = dict(result.details or {})
    details["range_basis"] = {
        "schema_version": "valuation_range_basis.v1",
        "kind": "startup_method_scenarios",
        "empirical_percentiles": False,
        "statistical_coverage": None,
        "basis": "canonical_pre_money_equity",
        "benchmark_source": region_data.source,
        "benchmark_methodology_version": region_data.methodology_version,
    }
    if result.available:
        canonical = dict(details.get("canonical") or {})
        canonical.update(
            pre_money_mid=result.value,
            pre_money_low=result.value_low,
            pre_money_high=result.value_high,
        )
        details["canonical"] = canonical
    result = result.model_copy(
        update={
            "details": details,
            "equity_value": result.value,
            "equity_value_low": result.value_low,
            "equity_value_high": result.value_high,
            "value_basis": "equity_value",
        }
    )
    # The adapter is the contract boundary: guarantee method_key is stamped
    # even when the startup engine's blender leaves it unset.
    if result.method_key is None:
        result = result.model_copy(update={"method_key": "startup_valuation"})
    return result
