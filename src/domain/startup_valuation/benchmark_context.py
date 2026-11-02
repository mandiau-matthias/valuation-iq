"""Startup benchmark context and provenance helpers.

Local ecosystem averages are allowed to calibrate the regional reference
anchor. Company-specific rounds, SAFEs, caps, and term sheets are market
evidence only: they are compared with the objective dot but never replace it.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Iterable, Mapping, Optional, cast

from .money import ZERO, q_eur, q_rate, safe_decimal, safe_float
from .regional_data import RegionalReferenceData
from .schemas import StartupBenchmarkInput, StartupInputs

_GEOGRAPHY_PRIORITY: Mapping[str, int] = {
    "city": 0,
    "country": 1,
    "benelux": 2,
    "eu": 3,
    "international": 4,
}


def apply_startup_benchmark_inputs(
    base: RegionalReferenceData,
    inputs: StartupInputs,
) -> RegionalReferenceData:
    """Overlay the best supplied local-average benchmark onto ``base``.

    Comparable rounds and founder-entered caps are deliberately ignored here:
    those belong in the evidence/audit layer, not in the Scorecard anchor.
    """

    benchmark = _best_local_average(inputs.startup_benchmarks, inputs=inputs)
    if benchmark is None or benchmark.average_pre_money_eur is None:
        return base

    exit_multiple = base.comparable_exit_revenue_multiple
    if benchmark.exit_multiple_low is not None and benchmark.exit_multiple_high is not None:
        exit_multiple = q_rate(
            (benchmark.exit_multiple_low + benchmark.exit_multiple_high) / Decimal("2")
        )

    return replace(
        base,
        average_pre_money=q_eur(benchmark.average_pre_money_eur),
        comparable_exit_revenue_multiple=exit_multiple,
        source=benchmark.source,
        methodology_version=benchmark.methodology_version or base.methodology_version,
        published_at=benchmark.observed_at or base.published_at,
        geography_scope=benchmark.geography_scope,
        geography_label=benchmark.geography_label or benchmark.city_name or base.geography_label,
        sample_size=benchmark.sample_size,
        evidence_quality=benchmark.evidence_quality,
        benchmark_source_type=benchmark.source_type,
        source_url=benchmark.source_url,
        source_observed_at=benchmark.observed_at,
    )


def build_startup_benchmark_context(
    *,
    inputs: StartupInputs,
    region_data: RegionalReferenceData,
    round_context: Optional[Mapping[str, object]],
) -> dict[str, object]:
    """Return the benchmark audit payload carried in ``MethodResult.details``."""

    company_evidence = [
        _benchmark_payload(benchmark)
        for benchmark in inputs.startup_benchmarks
        if benchmark.source_type != "local_market_average"
    ]
    if round_context:
        round_evidence = _round_context_payload(round_context)
        if _market_value(round_evidence) > ZERO:
            company_evidence.append(round_evidence)

    local_reference = _local_reference_payload(region_data)
    selected_basis = (
        "company_specific_market_evidence_compared_to_local_average"
        if company_evidence
        else "local_market_average"
    )

    return {
        "selected_basis": selected_basis,
        "local_reference": local_reference,
        "company_specific_evidence": company_evidence,
        "comparison_to_local_average": [
            _compare_to_local_average(local_reference, evidence) for evidence in company_evidence
        ],
        "rules": {
            "local_average_can_calibrate_scorecard_anchor": True,
            "company_specific_evidence_overwrites_objective_dot": False,
            "round_context_is_market_evidence_not_truth": bool(company_evidence),
        },
        "explanation": (
            "Local ecosystem averages calibrate the startup benchmark anchor. "
            "Company-specific rounds, SAFEs, caps, and term sheets are compared "
            "against the objective valuation dot, but they do not overwrite it."
        ),
    }


def _best_local_average(
    benchmarks: Iterable[StartupBenchmarkInput],
    *,
    inputs: StartupInputs,
) -> StartupBenchmarkInput | None:
    candidates = [
        benchmark
        for benchmark in benchmarks
        if benchmark.source_type == "local_market_average"
        and benchmark.average_pre_money_eur is not None
        and _matches_context(benchmark, inputs)
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda benchmark: (
            _GEOGRAPHY_PRIORITY.get(benchmark.geography_scope, 99),
            -(benchmark.sample_size or 0),
        ),
    )[0]


def _matches_context(benchmark: StartupBenchmarkInput, inputs: StartupInputs) -> bool:
    if benchmark.stage is not None and benchmark.stage != inputs.stage:
        return False
    if benchmark.sector is not None and benchmark.sector != inputs.sector:
        return False
    if benchmark.country_code is not None and benchmark.country_code != inputs.country_code:
        return False
    return True


def _local_reference_payload(region_data: RegionalReferenceData) -> dict[str, object]:
    return {
        "source_type": region_data.benchmark_source_type,
        "evidence_quality": region_data.evidence_quality,
        "geography_scope": region_data.geography_scope,
        "geography_label": region_data.geography_label,
        "region_code": region_data.region_code,
        "stage": region_data.stage,
        "average_pre_money_eur": safe_float(region_data.average_pre_money),
        "sample_size": region_data.sample_size,
        "source": region_data.source,
        "source_url": region_data.source_url,
        "observed_at": region_data.source_observed_at or region_data.published_at,
        "methodology_version": region_data.methodology_version,
    }


def _benchmark_payload(benchmark: StartupBenchmarkInput) -> dict[str, object]:
    return {
        "source_type": benchmark.source_type,
        "evidence_quality": benchmark.evidence_quality,
        "value_relationship": benchmark.value_relationship,
        "geography_scope": benchmark.geography_scope,
        "geography_label": benchmark.geography_label,
        "city_name": benchmark.city_name,
        "country_code": benchmark.country_code,
        "region_code": benchmark.region_code,
        "stage": benchmark.stage,
        "sector": benchmark.sector,
        "average_pre_money_eur": safe_float(benchmark.average_pre_money_eur),
        "pre_money_eur": safe_float(benchmark.pre_money_eur),
        "post_money_eur": safe_float(benchmark.post_money_eur),
        "valuation_cap_eur": safe_float(benchmark.valuation_cap_eur),
        "amount_raised_eur": safe_float(benchmark.amount_raised_eur),
        "discount_pct": safe_float(benchmark.discount_pct),
        "sample_size": benchmark.sample_size,
        "source": benchmark.source,
        "source_url": benchmark.source_url,
        "observed_at": benchmark.observed_at,
        "methodology_version": benchmark.methodology_version,
        "overwrites_objective_dot": False,
    }


def _round_context_payload(round_context: Mapping[str, object]) -> dict[str, object]:
    market = round_context.get("market_implied")
    market_map = market if isinstance(market, Mapping) else {}
    provenance = round_context.get("provenance")
    provenance_map = provenance if isinstance(provenance, Mapping) else {}
    source = provenance_map.get("source") or "founder_entered"
    quality = provenance_map.get("quality") or "unverified"
    return {
        "source_type": source,
        "evidence_quality": quality,
        "source_detail": provenance_map.get("source_detail"),
        "value_relationship": round_context.get("value_relationship"),
        "pre_money_eur": safe_float(market_map.get("pre_money")),
        "post_money_eur": safe_float(market_map.get("post_money")),
        "valuation_cap_eur": safe_float(market_map.get("valuation_cap")),
        "amount_raised_eur": safe_float(market_map.get("comparison_amount")),
        "source": source,
        "overwrites_objective_dot": False,
    }


def _compare_to_local_average(
    local_reference: Mapping[str, object],
    evidence: Mapping[str, object],
) -> dict[str, object]:
    local_average = q_eur(safe_decimal(local_reference.get("average_pre_money_eur")))
    market_value = _market_value(evidence)
    delta = q_eur(market_value - local_average) if market_value > ZERO else ZERO
    ratio = (
        q_rate(market_value / local_average)
        if market_value > ZERO and local_average > ZERO
        else None
    )
    return {
        "source_type": evidence.get("source_type"),
        "market_evidence_pre_money_eur": safe_float(market_value),
        "local_average_pre_money_eur": safe_float(local_average),
        "delta_to_local_average_eur": safe_float(delta),
        "ratio_to_local_average": safe_float(ratio),
        "interpretation": (
            "market_evidence_above_local_average"
            if delta > ZERO
            else "market_evidence_at_or_below_local_average"
        ),
        "overwrites_objective_dot": False,
    }


def _market_value(evidence: Mapping[str, object]) -> Decimal:
    for key in ("pre_money_eur", "valuation_cap_eur", "post_money_eur"):
        value = cast(Decimal, q_eur(safe_decimal(evidence.get(key))))
        if value > ZERO:
            return value
    return cast(Decimal, ZERO)
