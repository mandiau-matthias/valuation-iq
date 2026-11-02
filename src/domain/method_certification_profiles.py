"""Versioned evidence and jurisdiction requirements for certifiable methods."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Mapping

METHOD_CERTIFICATION_PROFILE_VERSION = "method_certification_profile.v1"
CERTIFICATION_COUNTRIES = ("BE", "EE", "FR", "IE", "LT", "SK")


@dataclass(frozen=True)
class MethodCertificationProfile:
    schema_version: Literal["method_certification_profile.v1"]
    method_key: str
    value_basis: Literal["enterprise_value", "equity_value", "mixed"]
    supported_countries: tuple[str, ...]
    required_evidence: tuple[str, ...]
    required_invariants: tuple[str, ...]
    benchmark_requirement: Literal[
        "metric_matched_market_sample",
        "governed_non_sample_inputs",
        "child_method_profiles",
        "statutory_reference",
    ]
    review_scope: str
    required_review_state: Literal["accepted_governed_calculation_review"]
    effective_from: date
    effective_to: date | None = None
    combinable: bool = True
    implementation_state: Literal["canonical_runtime", "unsupported"] = "canonical_runtime"
    implementation_limitation: str | None = None

    def supports(self, country_code: str, valuation_date: date) -> bool:
        code = str(country_code or "").strip().upper()
        return (
            self.implementation_state == "canonical_runtime"
            and code in self.supported_countries
            and valuation_date >= self.effective_from
            and (self.effective_to is None or valuation_date <= self.effective_to)
        )


def _profile(
    method_key: str,
    *,
    value_basis: Literal["enterprise_value", "equity_value", "mixed"],
    required_evidence: tuple[str, ...],
    required_invariants: tuple[str, ...],
    benchmark_requirement: Literal[
        "metric_matched_market_sample",
        "governed_non_sample_inputs",
        "child_method_profiles",
        "statutory_reference",
    ],
    review_scope: str,
    countries: tuple[str, ...] = CERTIFICATION_COUNTRIES,
    combinable: bool = True,
    implementation_state: Literal["canonical_runtime", "unsupported"] = "canonical_runtime",
    implementation_limitation: str | None = None,
) -> MethodCertificationProfile:
    return MethodCertificationProfile(
        schema_version=METHOD_CERTIFICATION_PROFILE_VERSION,
        method_key=method_key,
        value_basis=value_basis,
        supported_countries=countries,
        required_evidence=required_evidence,
        required_invariants=required_invariants,
        benchmark_requirement=benchmark_requirement,
        review_scope=review_scope,
        required_review_state="accepted_governed_calculation_review",
        effective_from=date(2026, 1, 1),
        combinable=combinable,
        implementation_state=implementation_state,
        implementation_limitation=implementation_limitation,
    )


METHOD_CERTIFICATION_PROFILES: Mapping[str, MethodCertificationProfile] = {
    "upswitch_adaptive": _profile(
        "upswitch_adaptive",
        value_basis="mixed",
        required_evidence=("every_positive_weight_child_profile",),
        required_invariants=("eligible_weights_sum_to_one", "no_ineligible_child_method"),
        benchmark_requirement="child_method_profiles",
        review_scope="adaptive_synthesis_and_every_positive_weight_child",
    ),
    "ebitda_multiple": _profile(
        "ebitda_multiple",
        value_basis="enterprise_value",
        required_evidence=("normalized_annual_ebitda", "metric_matched_benchmark_snapshot"),
        required_invariants=("normalization_before_weighting", "single_ev_equity_bridge"),
        benchmark_requirement="metric_matched_market_sample",
        review_scope="earnings_basis_multiple_and_bridge",
    ),
    "omzet_multiple": _profile(
        "omzet_multiple",
        value_basis="enterprise_value",
        required_evidence=(
            "ltm_or_ntm_revenue",
            "margin_quality",
            "metric_matched_benchmark_snapshot",
        ),
        required_invariants=("no_historical_revenue_averaging", "single_ev_equity_bridge"),
        benchmark_requirement="metric_matched_market_sample",
        review_scope="revenue_basis_multiple_and_bridge",
    ),
    "arr_multiple": _profile(
        "arr_multiple",
        value_basis="enterprise_value",
        required_evidence=(
            "arr",
            "retention_and_margin_quality",
            "metric_matched_benchmark_snapshot",
        ),
        required_invariants=("arr_definition_reconciled", "single_ev_equity_bridge"),
        benchmark_requirement="metric_matched_market_sample",
        review_scope="arr_quality_multiple_and_bridge",
    ),
    "sde_multiple": _profile(
        "sde_multiple",
        # The runtime first calculates an SDE-derived enterprise value and
        # then deducts net debt.  Calling this an equity-premise method hid a
        # real EV-to-equity bridge and made a double bridge impossible to
        # detect in certification.
        value_basis="enterprise_value",
        required_evidence=(
            "annual_owner_compensation",
            "replacement_compensation",
            "sde_benchmark_snapshot",
        ),
        required_invariants=(
            "annual_sde_weighted_exactly_once",
            "no_fabricated_owner_compensation",
            "single_ev_equity_bridge",
        ),
        benchmark_requirement="metric_matched_market_sample",
        review_scope="owner_earnings_transferability_and_equity_value",
    ),
    "dcf": _profile(
        "dcf",
        value_basis="enterprise_value",
        required_evidence=(
            "explicit_fcff_forecast",
            "economic_snapshot",
            "wacc",
            "terminal_assumption",
            "forecast_review",
        ),
        required_invariants=("fcff_only", "terminal_policy_consistency", "single_ev_equity_bridge"),
        benchmark_requirement="governed_non_sample_inputs",
        review_scope="forecast_wacc_terminal_value_and_bridge",
    ),
    "adjusted_nav": _profile(
        "adjusted_nav",
        value_basis="equity_value",
        required_evidence=(
            "dated_assets",
            "dated_liabilities",
            "appraisals",
            "title",
            "tax_effects",
        ),
        required_invariants=("measurement_date_basis", "enterprise_value_not_applicable"),
        benchmark_requirement="governed_non_sample_inputs",
        review_scope="asset_liability_revaluation_and_tax",
    ),
    "real_estate_yield": _profile(
        "real_estate_yield",
        value_basis="enterprise_value",
        required_evidence=(
            "property_title_or_appraisal",
            "dated_noi",
            "occupancy",
            "yield_snapshot",
            "property_debt",
        ),
        required_invariants=(
            "market_rent_exactly_once",
            "single_property_debt_bridge",
            "nav_floor_like_for_like",
        ),
        benchmark_requirement="metric_matched_market_sample",
        review_scope="property_income_yield_and_debt_bridge",
    ),
    "holding_sotp": _profile(
        "holding_sotp",
        value_basis="mixed",
        required_evidence=(
            "trusted_child_runs",
            "ownership",
            "eliminations",
            "entity_tax",
            "source_dated_fx",
        ),
        required_invariants=(
            "intercompany_elimination",
            "minority_ownership",
            "no_child_bridge_replay",
        ),
        benchmark_requirement="child_method_profiles",
        review_scope="entity_runs_ownership_eliminations_tax_and_fx",
    ),
    "startup_valuation": _profile(
        "startup_valuation",
        value_basis="equity_value",
        required_evidence=("stage", "scenarios", "cap_table", "dated_startup_benchmarks"),
        required_invariants=("dilution_reconciled", "enterprise_value_not_applicable"),
        benchmark_requirement="metric_matched_market_sample",
        review_scope="stage_scenarios_cap_table_and_pre_money_value",
        combinable=False,
    ),
    "fiscal_4x": _profile(
        "fiscal_4x",
        value_basis="equity_value",
        required_evidence=("belgian_statutory_inputs",),
        required_invariants=(
            "labelled_reference_not_market_value",
            "enterprise_value_not_applicable",
        ),
        benchmark_requirement="statutory_reference",
        review_scope="belgian_statutory_reference_calculation",
        countries=("BE",),
        combinable=False,
    ),
    "liquidation_analysis": _profile(
        "liquidation_analysis",
        value_basis="equity_value",
        required_evidence=(
            "realisation_schedule",
            "claim_priority",
            "tax_leakage",
            "wind_down_costs",
        ),
        required_invariants=("jurisdiction_priority_applied", "enterprise_value_not_applicable"),
        benchmark_requirement="governed_non_sample_inputs",
        review_scope="liquidation_premise_realisations_priorities_and_leakage",
        # FR/IE remain deliberately unsupported until their priority and tax
        # implementations and jurisdiction copy receive qualified review.
        countries=("BE",),
        combinable=False,
    ),
}

METHOD_CERTIFICATION_PROFILE_KEYS = tuple(METHOD_CERTIFICATION_PROFILES)
CERTIFIABLE_METHOD_KEYS = tuple(
    key
    for key, profile in METHOD_CERTIFICATION_PROFILES.items()
    if profile.implementation_state == "canonical_runtime"
)


def method_certification_profile(method_key: str) -> MethodCertificationProfile | None:
    normalized = str(method_key or "").strip().lower()
    if normalized == "revenue_multiple":
        normalized = "omzet_multiple"
    return METHOD_CERTIFICATION_PROFILES.get(normalized)


def supported_certification_methods(country_code: str) -> tuple[str, ...]:
    code = str(country_code or "").strip().upper()
    return tuple(
        key
        for key, profile in METHOD_CERTIFICATION_PROFILES.items()
        if profile.implementation_state == "canonical_runtime"
        and code in profile.supported_countries
    )
