"""Startup forward-value cone assembly for stateless valuation responses."""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping, cast

from src.api.schemas.stateless_api import CalculateRequest
from src.api.schemas.stateless_response_schemas import (
    ForwardConeAssumptionEvidence,
    ForwardConeMethodContribution,
    ForwardConeMethodExclusion,
)
from src.api.schemas.stateless_response_schemas import (
    ForwardScenarioPath as ResponseForwardScenarioPath,
)
from src.api.schemas.stateless_response_schemas import (
    ForwardValueCone,
    ForwardValueConePoint,
    MethodResult,
)
from src.domain.forward_method_registry import (
    AssumptionEvidence,
    AssumptionSourceKind,
    AssumptionUseKind,
    ForwardEvidenceConfidence,
    ForwardMethodEvidence,
    ForwardMethodExclusion,
)
from src.domain.forward_projection_engine import (
    ForwardHorizonInput,
    ForwardProjectionCone,
    ForwardProjectionMethod,
    ForwardProjectionPoint,
    ForwardScenarioPath,
    ForwardValueDistribution,
    build_forward_projection_cone,
)
from src.domain.startup_valuation.money import ONE, ZERO, q_eur, q_rate, safe_decimal
from src.domain.startup_valuation.schemas import StartupInputs

STARTUP_METHOD_KEY = "startup_valuation"
STARTUP_FORWARD_HORIZONS = (1, 2, 3)

_STAGE_ANNUAL_UPLIFT: Mapping[str, Decimal] = {
    "pre_seed": Decimal("0.04"),
    "seed": Decimal("0.06"),
    "series_a": Decimal("0.08"),
}

_STAGE_FLOOR_WIDTH: Mapping[str, Decimal] = {
    "pre_seed": Decimal("0.45"),
    "seed": Decimal("0.35"),
    "series_a": Decimal("0.28"),
}

def build_startup_forward_value_cone(
    *,
    request: CalculateRequest,
    valuation_results: Mapping[str, MethodResult] | None,
    headline_equity_low: Decimal,
    headline_equity_mid: Decimal,
    headline_equity_high: Decimal,
) -> ForwardValueCone | None:
    """Return a defensible startup forward cone, or ``None`` for non-startup runs."""

    if getattr(request, "selected_method", None) != STARTUP_METHOD_KEY:
        return None
    inputs = getattr(request, "startup_inputs", None)
    if not isinstance(inputs, StartupInputs):
        return None

    startup_result = (valuation_results or {}).get(STARTUP_METHOD_KEY)
    if startup_result is None or not startup_result.available:
        return None

    current_range = _canonical_range(
        startup_result,
        fallback_low=headline_equity_low,
        fallback_mid=headline_equity_mid,
        fallback_high=headline_equity_high,
    )
    if current_range is None:
        return None

    confidence = _forward_confidence(startup_result)
    base_horizons = tuple(
        _horizon_input(
            request=request,
            inputs=inputs,
            startup_result=startup_result,
            current_range=current_range,
            horizon_years=horizon,
            confidence=confidence,
        )
        for horizon in STARTUP_FORWARD_HORIZONS
    )

    domain_cone = build_forward_projection_cone(
        {STARTUP_METHOD_KEY: 1.0},
        base_horizons,
        # Engine-generated recommendations remain ranking metadata. They do
        # not bend a valuation path; a future action overlay must arrive as an
        # explicit, versioned scenario contract with disclosed driver deltas.
        scenarios=(),
        include_base_scenario_path=True,
    )
    return _to_response_cone(domain_cone)


def _canonical_range(
    result: MethodResult,
    *,
    fallback_low: Decimal,
    fallback_mid: Decimal,
    fallback_high: Decimal,
) -> tuple[Decimal, Decimal, Decimal] | None:
    details = result.details if isinstance(result.details, dict) else {}
    raw_canonical = details.get("canonical")
    canonical: Mapping[str, object] = raw_canonical if isinstance(raw_canonical, dict) else {}
    mid = safe_decimal(result.value, default=safe_decimal(canonical.get("pre_money_mid")))
    low = safe_decimal(result.value_low, default=safe_decimal(canonical.get("pre_money_low")))
    high = safe_decimal(result.value_high, default=safe_decimal(canonical.get("pre_money_high")))

    if mid <= ZERO:
        mid = safe_decimal(fallback_mid)
    if low <= ZERO:
        low = safe_decimal(fallback_low, default=mid)
    if high <= ZERO:
        high = safe_decimal(fallback_high, default=mid)
    low = min(low, mid, high)
    high = max(low, mid, high)
    if mid <= ZERO or high <= ZERO:
        return None
    return (q_eur(low), q_eur(mid), q_eur(high))


def _forward_confidence(result: MethodResult) -> ForwardEvidenceConfidence:
    score = _defensibility_score(result)
    if score >= Decimal("7.5"):
        return ForwardEvidenceConfidence.HIGH
    if score >= Decimal("5.0"):
        return ForwardEvidenceConfidence.MEDIUM
    return ForwardEvidenceConfidence.LOW


def _defensibility_score(result: MethodResult) -> Decimal:
    details = result.details if isinstance(result.details, dict) else {}
    defensibility = details.get("defensibility")
    if not isinstance(defensibility, dict):
        return Decimal("5.0")
    return cast(Decimal, safe_decimal(defensibility.get("score_0_10"), default=Decimal("5.0")))


def _horizon_input(
    *,
    request: CalculateRequest,
    inputs: StartupInputs,
    startup_result: MethodResult,
    current_range: tuple[Decimal, Decimal, Decimal],
    horizon_years: int,
    confidence: ForwardEvidenceConfidence,
) -> ForwardHorizonInput:
    distribution = _startup_distribution(
        inputs=inputs,
        startup_result=startup_result,
        current_range=current_range,
        horizon_years=horizon_years,
    )
    evidence = ForwardMethodEvidence(
        available_driver_groups=("stage_forecast", "milestone_probabilities"),
        available_pricing_inputs=(
            "stage_benchmark_distribution",
            "dilution_or_funding_assumptions",
        ),
        assumptions=_startup_forward_assumptions(inputs, startup_result),
        warnings=_startup_forward_warnings(startup_result),
        confidence=confidence,
        closed_year_financials_available=True,
        contains_open_ytd_inputs=False,
    )
    return ForwardHorizonInput(
        fiscal_year=request.current_year.year + horizon_years,
        horizon_years=horizon_years,
        method_evidence={STARTUP_METHOD_KEY: evidence},
        method_value_distributions={STARTUP_METHOD_KEY: distribution},
        stage_floor_width=_STAGE_FLOOR_WIDTH.get(inputs.stage, Decimal("0.35")),
        horizon_floor_width=_horizon_floor_width(inputs, horizon_years),
        assumptions=_startup_forward_assumptions(inputs, startup_result),
        warnings=_startup_forward_warnings(startup_result),
    )


def _startup_distribution(
    *,
    inputs: StartupInputs,
    startup_result: MethodResult,
    current_range: tuple[Decimal, Decimal, Decimal],
    horizon_years: int,
) -> ForwardValueDistribution:
    low, mid, high = current_range
    multiplier = _compound(ONE + _annual_uplift(inputs, startup_result), horizon_years)
    return ForwardValueDistribution(
        p10=q_eur(low * multiplier),
        p50=q_eur(mid * multiplier),
        p90=q_eur(high * multiplier),
    )


def _annual_uplift(inputs: StartupInputs, startup_result: MethodResult) -> Decimal:
    base = _STAGE_ANNUAL_UPLIFT.get(inputs.stage, Decimal("0.05"))
    defensibility = _defensibility_score(startup_result) / Decimal("10")
    defensibility_lift = Decimal("0.03") * max(ZERO, min(ONE, defensibility))
    traction_lift = _traction_lift(inputs)
    return cast(Decimal, min(Decimal("0.18"), base + defensibility_lift + traction_lift))


def _traction_lift(inputs: StartupInputs) -> Decimal:
    lift = ZERO
    if (inputs.arr or ZERO) > ZERO or (inputs.mrr or ZERO) > ZERO:
        lift += Decimal("0.02")
    if inputs.mrr_growth_rate_pct is not None and inputs.mrr_growth_rate_pct > ZERO:
        lift += min(Decimal("0.04"), safe_decimal(inputs.mrr_growth_rate_pct) / Decimal("500"))
    if inputs.active_users is not None and inputs.active_users >= 100:
        lift += Decimal("0.01")
    return cast(Decimal, lift)


def _compound(multiplier: Decimal, periods: int) -> Decimal:
    value = ONE
    for _ in range(max(0, periods)):
        value *= multiplier
    return cast(Decimal, q_rate(value))


def _horizon_floor_width(inputs: StartupInputs, horizon_years: int) -> Decimal:
    stage_floor = _STAGE_FLOOR_WIDTH.get(inputs.stage, Decimal("0.35"))
    horizon_add = Decimal("0.05") * Decimal(str(max(0, horizon_years - 1)))
    return min(Decimal("0.65"), stage_floor + horizon_add)


def _startup_forward_assumptions(
    inputs: StartupInputs,
    startup_result: MethodResult,
) -> tuple[AssumptionEvidence, ...]:
    confidence = _forward_confidence(startup_result)
    return (
        AssumptionEvidence(
            field_key="stage_forecast",
            source_kind=AssumptionSourceKind.ADVISOR_ENTERED,
            use_kind=AssumptionUseKind.FORWARD_DRIVER_INPUT,
            confidence=confidence,
            source=f"startup_inputs.stage:{inputs.stage}",
            responsible_surface="valuation_iq_startup_valuation",
        ),
        AssumptionEvidence(
            field_key="milestone_probabilities",
            source_kind=AssumptionSourceKind.ADVISOR_ENTERED,
            use_kind=AssumptionUseKind.FORWARD_DRIVER_INPUT,
            confidence=confidence,
            source="startup_inputs.qualitative_factor_scores",
            responsible_surface="valuation_iq_startup_valuation",
        ),
        AssumptionEvidence(
            field_key="stage_benchmark_distribution",
            source_kind=AssumptionSourceKind.SECTOR_DEFAULT,
            use_kind=AssumptionUseKind.FORWARD_DRIVER_INPUT,
            confidence=confidence,
            source=_regional_reference_source(startup_result),
            responsible_surface="valuation_iq_startup_valuation",
        ),
        AssumptionEvidence(
            field_key="dilution_or_funding_assumptions",
            source_kind=_funding_assumption_source_kind(inputs),
            use_kind=AssumptionUseKind.FORWARD_DRIVER_INPUT,
            confidence=confidence,
            source=_funding_assumption_source(inputs),
            responsible_surface="valuation_iq_startup_valuation",
        ),
    )


def _regional_reference_source(result: MethodResult) -> str:
    details = result.details if isinstance(result.details, dict) else {}
    reference = details.get("regional_reference")
    if not isinstance(reference, dict):
        return "startup_valuation.regional_reference"
    source = reference.get("source") or reference.get("methodology_version")
    return str(source or "startup_valuation.regional_reference")


def _funding_assumption_source_kind(inputs: StartupInputs) -> AssumptionSourceKind:
    if inputs.round_scenario is not None or inputs.investment_amount_sought is not None:
        return AssumptionSourceKind.ADVISOR_ENTERED
    if (
        inputs.cap_table.pre_money_target is not None
        or inputs.cap_table.last_round_post_money is not None
    ):
        return AssumptionSourceKind.ADVISOR_ENTERED
    return AssumptionSourceKind.SECTOR_DEFAULT


def _funding_assumption_source(inputs: StartupInputs) -> str:
    if inputs.round_scenario is not None:
        return "startup_inputs.round_scenario"
    if inputs.investment_amount_sought is not None:
        return "startup_inputs.investment_amount_sought"
    if inputs.cap_table.pre_money_target is not None:
        return "startup_inputs.cap_table.pre_money_target"
    if inputs.cap_table.last_round_post_money is not None:
        return "startup_inputs.cap_table.last_round_post_money"
    return "startup_valuation.regional_default_dilution"


def _startup_forward_warnings(result: MethodResult) -> tuple[str, ...]:
    warnings = ["forward_value_is_forecast_not_current_market_value"]
    if _forward_confidence(result) == ForwardEvidenceConfidence.LOW:
        warnings.append("startup_forward_defensibility_below_medium")
    return tuple(warnings)


def _to_response_cone(cone: ForwardProjectionCone) -> ForwardValueCone:
    return ForwardValueCone(
        points=[_to_response_point(point) for point in cone.points],
        scenario_paths={path.key: _to_response_scenario_path(path) for path in cone.scenario_paths},
    )


def _to_response_scenario_path(path: ForwardScenarioPath) -> ResponseForwardScenarioPath:
    return ResponseForwardScenarioPath(
        key=path.key,
        label=path.label,
        action_status=path.action_status,
        driver_deltas=[],
        points=[_to_response_point(point) for point in path.points],
        confidence=path.confidence.value,
        gate_status=path.gate_status,
        provenance=list(path.provenance),
        warnings=list(path.warnings),
        audit_events=list(path.audit_events),
    )


def _to_response_point(point: ForwardProjectionPoint) -> ForwardValueConePoint:
    value = point.blended_equity_value or ForwardValueDistribution(p10=ZERO, p50=ZERO, p90=ZERO)
    return ForwardValueConePoint(
        fiscal_year=point.fiscal_year,
        horizon_years=point.horizon_years,
        equity_low=value.p10,
        equity_mid=value.p50,
        equity_high=value.p90,
        valuation_date_convention=point.valuation_date_convention,
        method_mix=[_to_response_method(method) for method in point.method_weights],
        uncertainty_provenance=list(point.uncertainty_provenance),
        assumptions=[_to_response_assumption(item) for item in point.assumptions],
        gate_status=point.gate_status,
        excluded_methods=[_to_response_exclusion(item) for item in point.excluded_methods],
        audit_events=list(point.audit_events),
        confidence_level=_point_confidence(point),
        warnings=list(point.warnings),
    )


def _point_confidence(point: ForwardProjectionPoint) -> str | None:
    if not point.method_weights:
        return None
    confidence_values = [
        assumption.confidence.value
        for method in point.method_weights
        for assumption in method.assumptions
    ]
    if not confidence_values:
        return None
    if "low" in confidence_values:
        return "low"
    if "medium" in confidence_values:
        return "medium"
    return "high"


def _to_response_method(method: ForwardProjectionMethod) -> ForwardConeMethodContribution:
    return ForwardConeMethodContribution(
        method_key=method.method_key,
        weight=Decimal(str(method.forward_weight)),
        equity_low=method.value_distribution.p10,
        equity_mid=method.value_distribution.p50,
        equity_high=method.value_distribution.p90,
        uncertainty_family=method.uncertainty_family,
        correlation_bucket=method.correlation_bucket,
        assumptions=[_to_response_assumption(item) for item in method.assumptions],
        warnings=list(method.warnings),
    )


def _to_response_assumption(item: AssumptionEvidence) -> ForwardConeAssumptionEvidence:
    return ForwardConeAssumptionEvidence(
        field_key=item.field_key,
        source_kind=item.source_kind.value,
        use_kind=item.use_kind.value,
        confidence=item.confidence.value,
        source=item.source,
        responsible_surface=item.responsible_surface,
        freshness_days=item.freshness_days,
        transformation=item.transformation,
        override_reason=item.override_reason,
        fallback=item.fallback,
        warnings=list(item.warnings),
    )


def _to_response_exclusion(item: ForwardMethodExclusion) -> ForwardConeMethodExclusion:
    return ForwardConeMethodExclusion(
        method_key=item.method_key,
        reasons=list(item.reasons),
        missing_driver_groups=list(item.missing_driver_groups),
        missing_pricing_inputs=list(item.missing_pricing_inputs),
        remediation=list(item.remediation),
    )
