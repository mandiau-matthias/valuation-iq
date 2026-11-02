"""Describe the actual range inputs without upgrading assumptions to observations."""

from collections.abc import Mapping

from src.domain.financial_arithmetic import decimal_number


def benchmark_range_disclosure(
    *,
    resolved: bool,
    contract: Mapping[str, object] | None,
    supplied_low: object,
    supplied_high: object,
    applied_low: object,
    applied_high: object,
    governed_external: bool = False,
    disclosed_external: bool = False,
    composite_price: bool = False,
) -> dict[str, object]:
    empirical = False
    if governed_external:
        basis = "governed_external_market_reference_range_not_empirical"
    elif disclosed_external:
        basis = "advisor_defined_external_reference_range_not_empirical"
    elif not resolved:
        basis = "generic_uncertainty_band_80_120_not_empirical"
    elif supplied_low is None or supplied_high is None:
        basis = "assumed_multiple_spread_not_empirical"
    else:
        evidence = contract or {}
        derived = (
            composite_price
            or any(
                evidence.get(key)
                in {
                    "country_baseline",
                    "weighted_business_type_mix",
                    "composite_business_type_contract",
                }
                for key in ("source", "benchmark_scope", "benchmark_kind", "scope_stage")
                if isinstance(evidence.get(key), str)
            )
            or evidence.get("is_borrowed") is True
        )
        try:
            unchanged = decimal_number(supplied_low) == decimal_number(
                applied_low
            ) and decimal_number(supplied_high) == decimal_number(applied_high)
        except ValueError:
            unchanged = False
        empirical = not derived and unchanged
        basis = (
            "empirical_benchmark_percentiles"
            if empirical
            else "derived_benchmark_range_not_empirical"
        )
    return {
        "valuation_range_basis": basis,
        "p25_ebitda_multiple": applied_low if empirical else None,
        "p75_ebitda_multiple": applied_high if empirical else None,
        "range_low_multiple": applied_low,
        "range_high_multiple": applied_high,
        # Cohort percentiles are not a prediction/confidence interval for this company.
        "range_statistical_coverage": None,
    }
