"""Forward valuation series builder for the prognose cone.

This module owns the adaptive-forward part of BET-640: it does not invent a DCF
forecast, and it does not extrapolate today's blended number. For each horizon,
method-specific adapters provide low/mid/high values; this engine re-gates the
present blend against the forwardability registry, drops methods without
defensible evidence or value output, renormalizes the surviving weights, and
returns one future-date equity-value distribution.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

from src.domain.forward_method_registry import (
    FUTURE_VALUATION_DATE_CONVENTION,
    AssumptionEvidence,
    AssumptionSourceKind,
    AssumptionUseKind,
    ForwardBlendDecision,
    ForwardEvidenceConfidence,
    ForwardMethodEvidence,
    ForwardMethodExclusion,
    ForwardMethodWeight,
    select_forward_methods_for_horizon,
)
from src.domain.method_keys import normalize_method_key
from src.domain.structure_scenario_provenance import evaluate_structure_scenario_provenance


@dataclass(frozen=True)
class ForwardValueDistribution:
    """Low/mid/high equity-value distribution for one method or blend."""

    p10: Decimal
    p50: Decimal
    p90: Decimal

    def __post_init__(self) -> None:
        p10 = _coerce_decimal(self.p10, field_name="p10")
        p50 = _coerce_decimal(self.p50, field_name="p50")
        p90 = _coerce_decimal(self.p90, field_name="p90")
        if p10 > p50 or p50 > p90:
            raise ValueError("Forward value distribution must satisfy p10 <= p50 <= p90")
        object.__setattr__(self, "p10", p10)
        object.__setattr__(self, "p50", p50)
        object.__setattr__(self, "p90", p90)

    @property
    def is_bare_line(self) -> bool:
        return self.p10 == self.p50 == self.p90


@dataclass(frozen=True)
class ForwardHorizonInput:
    """Adapter outputs and evidence for one forecast valuation date."""

    fiscal_year: int
    horizon_years: int
    method_evidence: Mapping[str, ForwardMethodEvidence]
    method_value_distributions: Mapping[str, ForwardValueDistribution]
    stage_floor_width: Decimal = Decimal("0")
    horizon_floor_width: Decimal | None = None
    assumptions: tuple[AssumptionEvidence, ...] = ()
    warnings: tuple[str, ...] = ()


SUPPORTED_SCENARIO_DRIVER_GROUPS: tuple[str, ...] = (
    "forecast_revenue",
    "forecast_revenue_or_fcff",
    "revenue_growth",
    "forecast_ebitda",
    "ebitda_margin",
    "forecast_margin_or_fcff",
    "margin_quality_forecast",
    "owner_dependency",
    "forecast_owner_benefit",
    "recurring_revenue_share",
    "forecast_arr",
    "retention_forecast",
    "churn_retention",
    "capex_forecast",
    "working_capital_forecast",
    "wacc",
    "wacc_risk",
    "ev_ebitda_multiple_distribution",
    "ev_revenue_multiple_distribution",
    "arr_multiple_distribution",
    "multiple_range",
    "stage_forecast",
    "milestone_probabilities",
    "stage_benchmark_distribution",
    "dilution_or_funding_assumptions",
)

_BASE_SCENARIO_STATUS = "base"
_PLANNED_SCENARIO_STATUS = "planned"
_KNOWN_SCENARIO_STATUSES = (
    _BASE_SCENARIO_STATUS,
    _PLANNED_SCENARIO_STATUS,
    "committed",
    "verified",
    "downside",
)


@dataclass(frozen=True)
class ForwardScenarioDriverDelta:
    """One explicit driver change behind a scenario path."""

    driver_group: str
    delta: Decimal
    evidence: AssumptionEvidence
    unit: str = "relative"
    label: str | None = None
    direction: str = "increase"
    action_status: str = _PLANNED_SCENARIO_STATUS
    method_keys: tuple[str, ...] = ()
    value_up_action_id: str | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        driver_group = str(self.driver_group).strip()
        if not driver_group:
            raise ValueError("Scenario driver delta must name a driver_group")

        warnings = list(self.warnings)
        if self.evidence.use_kind != AssumptionUseKind.SCENARIO_DELTA:
            warnings.append("scenario_delta_evidence_wrong_use_kind")
        if driver_group not in SUPPORTED_SCENARIO_DRIVER_GROUPS:
            warnings.append("unsupported_scenario_driver_group")
        if self.action_status not in _KNOWN_SCENARIO_STATUSES:
            warnings.append("unknown_scenario_action_status")

        object.__setattr__(self, "driver_group", driver_group)
        object.__setattr__(self, "delta", _coerce_decimal(self.delta, field_name="delta"))
        object.__setattr__(self, "warnings", tuple(dict.fromkeys(warnings)))


@dataclass(frozen=True)
class ForwardScenarioInput:
    """Pre-blend adapter outputs for one named scenario path."""

    key: str
    label: str
    horizon_inputs: tuple[ForwardHorizonInput, ...]
    driver_deltas: tuple[ForwardScenarioDriverDelta, ...]
    action_status: str = _PLANNED_SCENARIO_STATUS
    provenance: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        key = str(self.key).strip()
        label = str(self.label).strip()
        if not key:
            raise ValueError("Forward scenario must have a key")
        if not label:
            raise ValueError("Forward scenario must have a label")
        warnings = list(self.warnings)
        if self.action_status not in _KNOWN_SCENARIO_STATUSES:
            warnings.append("unknown_scenario_action_status")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "horizon_inputs", tuple(self.horizon_inputs))
        object.__setattr__(self, "driver_deltas", tuple(self.driver_deltas))
        object.__setattr__(self, "warnings", tuple(dict.fromkeys(warnings)))


@dataclass(frozen=True)
class ForwardProjectionMethod:
    """One method that survived re-gating and contributed to a horizon."""

    method_key: str
    present_weight: float
    forward_weight: float
    value_distribution: ForwardValueDistribution
    requires_equity_bridge: bool
    uncertainty_family: str
    correlation_bucket: str
    assumptions: tuple[AssumptionEvidence, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ForwardProjectionPoint:
    """Blended future-date equity value for one forecast year."""

    fiscal_year: int
    horizon_years: int
    valuation_date_convention: str
    method_weights: tuple[ForwardProjectionMethod, ...]
    blended_equity_value: ForwardValueDistribution | None
    excluded_methods: tuple[ForwardMethodExclusion, ...]
    uncertainty_provenance: tuple[str, ...]
    assumptions: tuple[AssumptionEvidence, ...]
    warnings: tuple[str, ...]
    gate_status: str
    audit_events: tuple[str, ...]

    @property
    def has_forward_value(self) -> bool:
        return self.blended_equity_value is not None

    @property
    def is_bare_line(self) -> bool:
        return self.blended_equity_value.is_bare_line if self.blended_equity_value else False


@dataclass(frozen=True)
class ForwardScenarioPath:
    """Named scenario path with its driver deltas and blended points."""

    key: str
    label: str
    action_status: str
    driver_deltas: tuple[ForwardScenarioDriverDelta, ...]
    points: tuple[ForwardProjectionPoint, ...]
    confidence: ForwardEvidenceConfidence
    gate_status: str
    provenance: tuple[str, ...]
    warnings: tuple[str, ...]
    audit_events: tuple[str, ...]


@dataclass(frozen=True)
class ForwardProjectionCone:
    """Base forward cone plus named scenario paths."""

    points: tuple[ForwardProjectionPoint, ...]
    scenario_paths: tuple[ForwardScenarioPath, ...] = ()

    @property
    def scenario_paths_by_key(self) -> dict[str, ForwardScenarioPath]:
        return {path.key: path for path in self.scenario_paths}


def build_forward_projection_series(
    present_weights: Mapping[str, object],
    horizons: Iterable[ForwardHorizonInput],
) -> tuple[ForwardProjectionPoint, ...]:
    """Build an auditable forward valuation series from adapter outputs."""

    return tuple(
        _build_forward_projection_point(present_weights=present_weights, horizon=horizon)
        for horizon in horizons
    )


def build_forward_projection_cone(
    present_weights: Mapping[str, object],
    horizons: Iterable[ForwardHorizonInput],
    *,
    scenarios: Iterable[ForwardScenarioInput] = (),
    include_base_scenario_path: bool = True,
) -> ForwardProjectionCone:
    """Build a base cone and driver-linked scenario paths.

    Scenario horizon inputs must already reflect the explicit driver deltas.
    This engine then re-runs the normal method gating/blending per scenario so
    paths bend from driver-level adapter output, not from final-value repainting.
    """

    base_points = build_forward_projection_series(present_weights, horizons)
    scenario_paths: list[ForwardScenarioPath] = []
    if include_base_scenario_path:
        scenario_paths.append(_base_scenario_path(base_points))
    scenario_paths.extend(
        _build_forward_scenario_path(
            present_weights=present_weights,
            scenario=scenario,
            base_points=base_points,
        )
        for scenario in scenarios
    )
    return ForwardProjectionCone(points=base_points, scenario_paths=tuple(scenario_paths))


def _build_forward_projection_point(
    *,
    present_weights: Mapping[str, object],
    horizon: ForwardHorizonInput,
) -> ForwardProjectionPoint:
    gate_decision = select_forward_methods_for_horizon(
        present_weights,
        horizon_years=horizon.horizon_years,
        evidence_by_method=horizon.method_evidence,
    )
    methods, value_exclusions = _projection_methods_with_values(
        gate_decision,
        horizon.method_value_distributions,
        horizon.method_evidence,
    )
    audit_events = list(gate_decision.audit_events)
    if value_exclusions:
        audit_events.extend(
            f"excluded:{exclusion.method_key}:{','.join(exclusion.reasons)}"
            for exclusion in value_exclusions
        )
    if methods and (gate_decision.excluded_methods or value_exclusions):
        audit_events.append("renormalized_forward_values_after_adapter_outputs")
    if not methods:
        audit_events.append("no_method_value_distributions")
    blended_equity_value, uncertainty_provenance = (
        _blend_distributions(
            methods,
            stage_floor_width=horizon.stage_floor_width,
            horizon_floor_width=_horizon_floor_width(horizon),
        )
        if methods
        else (None, ("no_forward_value",))
    )
    assumptions = _point_assumptions(horizon, methods)
    warnings = _point_warnings(
        horizon=horizon,
        methods=methods,
        excluded_methods=gate_decision.excluded_methods + value_exclusions,
        blended_equity_value=blended_equity_value,
    )

    return ForwardProjectionPoint(
        fiscal_year=horizon.fiscal_year,
        horizon_years=horizon.horizon_years,
        valuation_date_convention=FUTURE_VALUATION_DATE_CONVENTION,
        method_weights=methods,
        blended_equity_value=blended_equity_value,
        excluded_methods=gate_decision.excluded_methods + value_exclusions,
        uncertainty_provenance=uncertainty_provenance,
        assumptions=assumptions,
        warnings=warnings,
        gate_status=_gate_status(blended_equity_value, warnings),
        audit_events=tuple(dict.fromkeys(audit_events)),
    )


def _base_scenario_path(
    base_points: tuple[ForwardProjectionPoint, ...],
) -> ForwardScenarioPath:
    warnings = tuple(dict.fromkeys(warning for point in base_points for warning in point.warnings))
    return ForwardScenarioPath(
        key="base",
        label="Base",
        action_status=_BASE_SCENARIO_STATUS,
        driver_deltas=(),
        points=base_points,
        confidence=_scenario_points_confidence(base_points),
        gate_status=_scenario_gate_status(
            action_status=_BASE_SCENARIO_STATUS,
            driver_deltas=(),
            points=base_points,
            warnings=warnings,
        ),
        provenance=("base_forward_projection",),
        warnings=warnings,
        audit_events=("scenario_path:base",),
    )


def _build_forward_scenario_path(
    *,
    present_weights: Mapping[str, object],
    scenario: ForwardScenarioInput,
    base_points: tuple[ForwardProjectionPoint, ...],
) -> ForwardScenarioPath:
    scenario_gate = evaluate_structure_scenario_provenance(
        scenario.driver_deltas, scenario.provenance
    )
    if not scenario_gate.allowed:
        scenario_points = ()
    else:
        scenario_points = build_forward_projection_series(present_weights, scenario.horizon_inputs)
        scenario_points = _apply_scenario_uncertainty_policy(
            scenario=scenario,
            scenario_points=scenario_points,
            base_points=base_points,
        )
    warnings = tuple(
        dict.fromkeys((*_scenario_path_warnings(scenario, scenario_points), *scenario_gate.reasons))
    )
    return ForwardScenarioPath(
        key=scenario.key,
        label=scenario.label,
        action_status=scenario.action_status,
        driver_deltas=scenario.driver_deltas,
        points=scenario_points,
        confidence=_scenario_confidence(scenario),
        gate_status=_scenario_gate_status(
            action_status=scenario.action_status,
            driver_deltas=scenario.driver_deltas,
            points=scenario_points,
            warnings=warnings,
        ),
        provenance=tuple(
            dict.fromkeys(
                (
                    *scenario.provenance,
                    *(
                        f"driver_delta:{delta.driver_group}:{delta.delta}:{delta.unit}"
                        for delta in scenario.driver_deltas
                    ),
                )
            )
        ),
        warnings=warnings,
        audit_events=tuple(
            dict.fromkeys(
                (
                    f"scenario_path:{scenario.key}",
                    *(
                        f"scenario_delta:{delta.driver_group}:{delta.action_status}"
                        for delta in scenario.driver_deltas
                    ),
                    *(event for point in scenario_points for event in point.audit_events),
                )
            )
        ),
    )


def _projection_methods_with_values(
    gate_decision: ForwardBlendDecision,
    method_value_distributions: Mapping[str, ForwardValueDistribution],
    method_evidence: Mapping[str, ForwardMethodEvidence],
) -> tuple[tuple[ForwardProjectionMethod, ...], tuple[ForwardMethodExclusion, ...]]:
    weighted_methods: list[
        tuple[ForwardMethodWeight, ForwardValueDistribution, ForwardMethodEvidence]
    ] = []
    value_exclusions: list[ForwardMethodExclusion] = []
    for method_weight in gate_decision.eligible_method_weights:
        value_distribution = _distribution_for_method(
            method_value_distributions,
            method_weight.method_key,
        )
        evidence = _evidence_for_method(method_evidence, method_weight.method_key)
        if value_distribution is None:
            value_exclusions.append(
                ForwardMethodExclusion(
                    method_key=method_weight.method_key,
                    present_weight=method_weight.present_weight,
                    reasons=("missing_method_value_distribution",),
                    missing_driver_groups=(),
                    missing_pricing_inputs=(),
                    remediation=(
                        "Run the method-specific forward adapter before emitting this horizon.",
                    ),
                )
            )
            continue
        weighted_methods.append((method_weight, value_distribution, evidence))

    present_total = sum(method_weight.present_weight for method_weight, _, _ in weighted_methods)
    if present_total <= 0:
        return (), tuple(value_exclusions)

    return (
        tuple(
            ForwardProjectionMethod(
                method_key=method_weight.method_key,
                present_weight=method_weight.present_weight,
                forward_weight=method_weight.present_weight / present_total,
                value_distribution=value_distribution,
                requires_equity_bridge=method_weight.requires_equity_bridge,
                uncertainty_family=method_weight.uncertainty_family,
                correlation_bucket=method_weight.correlation_bucket,
                assumptions=evidence.assumptions,
                warnings=evidence.warnings,
            )
            for method_weight, value_distribution, evidence in weighted_methods
        ),
        tuple(value_exclusions),
    )


def _evidence_for_method(
    evidence_by_method: Mapping[str, ForwardMethodEvidence],
    method_key: str,
) -> ForwardMethodEvidence:
    direct = evidence_by_method.get(method_key)
    if direct is not None:
        return direct
    for raw_key, evidence in evidence_by_method.items():
        if normalize_method_key(raw_key) == method_key:
            return evidence
    return ForwardMethodEvidence()


def _point_assumptions(
    horizon: ForwardHorizonInput,
    methods: tuple[ForwardProjectionMethod, ...],
) -> tuple[AssumptionEvidence, ...]:
    assumptions = [
        *horizon.assumptions,
        *(
            assumption
            for evidence in horizon.method_evidence.values()
            for assumption in evidence.assumptions
        ),
        *(assumption for method in methods for assumption in method.assumptions),
    ]
    if assumptions:
        return tuple(dict.fromkeys(assumptions))
    return (_missing_provenance_assumption(),)


def _missing_provenance_assumption() -> AssumptionEvidence:
    return AssumptionEvidence(
        field_key="forward_assumption_provenance",
        source_kind=AssumptionSourceKind.SYSTEM_FALLBACK,
        use_kind=AssumptionUseKind.FORWARD_DRIVER_INPUT,
        confidence=ForwardEvidenceConfidence.LOW,
        source="valuation_iq_missing_adapter_provenance",
        responsible_surface="valuation_iq_forward_projection_engine",
        fallback=True,
        warnings=("missing_assumption_provenance",),
    )


def _point_warnings(
    *,
    horizon: ForwardHorizonInput,
    methods: tuple[ForwardProjectionMethod, ...],
    excluded_methods: tuple[ForwardMethodExclusion, ...],
    blended_equity_value: ForwardValueDistribution | None,
) -> tuple[str, ...]:
    warnings = [
        "forward_value_is_forecast_not_current_market_value",
        *horizon.warnings,
        *(
            warning
            for evidence in horizon.method_evidence.values()
            for warning in evidence.warnings
        ),
        *(warning for method in methods for warning in method.warnings),
        *(f"excluded:{item.method_key}:{','.join(item.reasons)}" for item in excluded_methods),
    ]
    assumptions = _point_assumptions(horizon, methods)
    for assumption in assumptions:
        warnings.extend(assumption.warnings)
        if assumption.fallback or assumption.source_kind == AssumptionSourceKind.SYSTEM_FALLBACK:
            warnings.append(f"fallback_assumption:{assumption.field_key}")
    if blended_equity_value is None:
        warnings.append("forward_value_blocked_no_admissible_methods")
    return tuple(dict.fromkeys(warnings))


def _gate_status(
    blended_equity_value: ForwardValueDistribution | None,
    warnings: tuple[str, ...],
) -> str:
    if blended_equity_value is None:
        return "blocked"
    if any(
        warning.startswith("fallback_assumption:") or warning == "missing_assumption_provenance"
        for warning in warnings
    ):
        return "degraded"
    return "emitted"


def _apply_scenario_uncertainty_policy(
    *,
    scenario: ForwardScenarioInput,
    scenario_points: tuple[ForwardProjectionPoint, ...],
    base_points: tuple[ForwardProjectionPoint, ...],
) -> tuple[ForwardProjectionPoint, ...]:
    if scenario.action_status != _PLANNED_SCENARIO_STATUS:
        return scenario_points

    base_by_horizon = {(point.fiscal_year, point.horizon_years): point for point in base_points}
    adjusted: list[ForwardProjectionPoint] = []
    for point in scenario_points:
        base_point = base_by_horizon.get((point.fiscal_year, point.horizon_years))
        if (
            base_point is None
            or base_point.blended_equity_value is None
            or point.blended_equity_value is None
        ):
            adjusted.append(point)
            continue

        base_half_width = _half_width_ratio(base_point.blended_equity_value)
        scenario_half_width = _half_width_ratio(point.blended_equity_value)
        if scenario_half_width >= base_half_width:
            adjusted.append(point)
            continue

        widened = _widen_distribution_to_floor(point.blended_equity_value, base_half_width)
        adjusted.append(
            replace(
                point,
                blended_equity_value=widened,
                uncertainty_provenance=tuple(
                    dict.fromkeys(
                        (
                            *point.uncertainty_provenance,
                            f"planned_action_floor_from_base:{base_half_width}",
                        )
                    )
                ),
                warnings=tuple(
                    dict.fromkeys(
                        (
                            *point.warnings,
                            "planned_value_up_action_does_not_narrow_uncertainty",
                        )
                    )
                ),
                audit_events=tuple(
                    dict.fromkeys(
                        (
                            *point.audit_events,
                            "widened_planned_scenario_to_base_uncertainty",
                        )
                    )
                ),
            )
        )
    return tuple(adjusted)


def _scenario_path_warnings(
    scenario: ForwardScenarioInput,
    points: tuple[ForwardProjectionPoint, ...],
) -> tuple[str, ...]:
    warnings = list(scenario.warnings)
    if scenario.action_status == _PLANNED_SCENARIO_STATUS:
        warnings.append("planned_value_up_action_not_verified")
    if scenario.action_status != _BASE_SCENARIO_STATUS and not scenario.driver_deltas:
        warnings.append("scenario_path_missing_driver_deltas")
    for delta in scenario.driver_deltas:
        warnings.extend(delta.warnings)
        warnings.extend(delta.evidence.warnings)
        if (
            delta.evidence.fallback
            or delta.evidence.source_kind == AssumptionSourceKind.SYSTEM_FALLBACK
        ):
            warnings.append(f"fallback_assumption:{delta.evidence.field_key}")
        if not delta.evidence.is_forward_defensible:
            warnings.append(f"low_confidence_scenario_delta:{delta.driver_group}")
    warnings.extend(warning for point in points for warning in point.warnings)
    return tuple(dict.fromkeys(warnings))


_CONFIDENCE_RANK = {
    ForwardEvidenceConfidence.LOW: 0,
    ForwardEvidenceConfidence.MEDIUM: 1,
    ForwardEvidenceConfidence.HIGH: 2,
}


def _scenario_confidence(scenario: ForwardScenarioInput) -> ForwardEvidenceConfidence:
    if scenario.action_status != _BASE_SCENARIO_STATUS and not scenario.driver_deltas:
        return ForwardEvidenceConfidence.LOW
    if not scenario.driver_deltas:
        return ForwardEvidenceConfidence.HIGH
    confidence = min(
        (delta.evidence.confidence for delta in scenario.driver_deltas),
        key=_CONFIDENCE_RANK.get,
    )
    if scenario.action_status == _PLANNED_SCENARIO_STATUS:
        return (
            ForwardEvidenceConfidence.MEDIUM
            if confidence == ForwardEvidenceConfidence.HIGH
            else confidence
        )
    return confidence


def _scenario_points_confidence(
    points: tuple[ForwardProjectionPoint, ...],
) -> ForwardEvidenceConfidence:
    if not points or any(point.gate_status == "blocked" for point in points):
        return ForwardEvidenceConfidence.LOW
    if any(point.gate_status == "degraded" for point in points):
        return ForwardEvidenceConfidence.MEDIUM
    return ForwardEvidenceConfidence.HIGH


def _scenario_gate_status(
    *,
    action_status: str,
    driver_deltas: tuple[ForwardScenarioDriverDelta, ...],
    points: tuple[ForwardProjectionPoint, ...],
    warnings: tuple[str, ...],
) -> str:
    if action_status != _BASE_SCENARIO_STATUS and not driver_deltas:
        return "blocked"
    if not points or any(point.gate_status == "blocked" for point in points):
        return "blocked"
    if any(point.gate_status == "degraded" for point in points):
        return "degraded"
    if any(
        warning.startswith("fallback_assumption:")
        or warning.startswith("low_confidence_scenario_delta:")
        or warning == "scenario_delta_evidence_wrong_use_kind"
        for warning in warnings
    ):
        return "degraded"
    return "emitted"


def _blend_distributions(
    methods: tuple[ForwardProjectionMethod, ...],
    *,
    stage_floor_width: Decimal,
    horizon_floor_width: Decimal,
) -> tuple[ForwardValueDistribution, tuple[str, ...]]:
    raw = ForwardValueDistribution(
        p10=sum(_weighted(method.value_distribution.p10, method) for method in methods),
        p50=sum(_weighted(method.value_distribution.p50, method) for method in methods),
        p90=sum(_weighted(method.value_distribution.p90, method) for method in methods),
    )
    correlation_floor, correlation_events = _correlation_floor_width(methods)
    floors = {
        "stage_floor": _coerce_decimal(stage_floor_width, field_name="stage_floor_width"),
        "horizon_floor": _coerce_decimal(horizon_floor_width, field_name="horizon_floor_width"),
        "correlation_floor": correlation_floor,
    }
    applied_floor = max(floors.values())
    widened = _widen_distribution_to_floor(raw, applied_floor)
    provenance = [
        f"raw_half_width:{_half_width_ratio(raw)}",
        *(f"{name}:{value}" for name, value in floors.items() if value > 0),
        *correlation_events,
    ]
    if widened != raw:
        provenance.append(f"widened_to_half_width:{applied_floor}")
    return widened, tuple(provenance)


def _horizon_floor_width(horizon: ForwardHorizonInput) -> Decimal:
    if horizon.horizon_floor_width is not None:
        return _coerce_decimal(horizon.horizon_floor_width, field_name="horizon_floor_width")
    return Decimal("0.05") * Decimal(str(max(horizon.horizon_years, 0)))


def _weighted(value: Decimal, method: ForwardProjectionMethod) -> Decimal:
    return value * Decimal(str(method.forward_weight))


def _widen_distribution_to_floor(
    distribution: ForwardValueDistribution,
    minimum_half_width: Decimal,
) -> ForwardValueDistribution:
    if distribution.p50 <= 0 or minimum_half_width <= 0:
        return distribution
    floor_amount = distribution.p50 * minimum_half_width
    return ForwardValueDistribution(
        p10=max(Decimal("0"), min(distribution.p10, distribution.p50 - floor_amount)),
        p50=distribution.p50,
        p90=max(distribution.p90, distribution.p50 + floor_amount),
    )


def _half_width_ratio(distribution: ForwardValueDistribution) -> Decimal:
    if distribution.p50 <= 0:
        return Decimal("0")
    low_width = (distribution.p50 - distribution.p10) / distribution.p50
    high_width = (distribution.p90 - distribution.p50) / distribution.p50
    return max(low_width, high_width)


def _correlation_floor_width(
    methods: tuple[ForwardProjectionMethod, ...],
) -> tuple[Decimal, tuple[str, ...]]:
    floors: list[Decimal] = []
    events: list[str] = []
    buckets = sorted({method.correlation_bucket for method in methods})
    for bucket in buckets:
        bucket_methods = [method for method in methods if method.correlation_bucket == bucket]
        if len(bucket_methods) < 2:
            continue
        bucket_floor = max(
            _half_width_ratio(method.value_distribution) for method in bucket_methods
        )
        floors.append(bucket_floor)
        events.append(f"correlation_bucket:{bucket}:{bucket_floor}")
    return (max(floors) if floors else Decimal("0"), tuple(events))


def _distribution_for_method(
    method_value_distributions: Mapping[str, ForwardValueDistribution],
    method_key: str,
) -> ForwardValueDistribution | None:
    direct = method_value_distributions.get(method_key)
    if direct is not None:
        return direct
    for raw_key, distribution in method_value_distributions.items():
        if normalize_method_key(raw_key) == method_key:
            return distribution
    return None


def _coerce_decimal(value: object, *, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid forward value distribution {field_name}: {value!r}") from exc
