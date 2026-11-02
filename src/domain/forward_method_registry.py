"""Forward-prognosis contract for valuation methods.

This module deliberately does not calculate the future valuation cone. It is the
governance layer the cone engine can depend on: every canonical valuation method
declares whether it can be projected forward, which forecast drivers it needs,
which pricing inputs make the projection defensible, and why it must abstain.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum

from src.domain.forward_method_contract import (
    ForecastFamily,
    ForwardMethodSpec,
    ForwardRole,
    ForwardValueBasis,
)
from src.domain.forward_method_specs import FORWARD_METHOD_SPECS
from src.domain.method_keys import CANONICAL_METHOD_KEYS, normalize_method_key

FUTURE_VALUATION_DATE_CONVENTION = "future_equity_value_as_of_forecast_valuation_date"
METHODOLOGY_REFERENCE_DOCUMENTS = (
    "Prognose Cone — Methodology Audit & Build Contract",
    "Prognose Cone — Mathematical Spec v0",
)


class ForwardEvidenceConfidence(str, Enum):
    """Confidence grade for a forward driver or pricing assumption."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AssumptionSourceKind(str, Enum):
    """Where a forward assumption came from."""

    ADVISOR_ENTERED = "advisor_entered"
    INTEGRATION_OBSERVED = "integration_observed"
    HISTORY_INFERRED = "history_inferred"
    SECTOR_DEFAULT = "sector_default"
    SYSTEM_FALLBACK = "system_fallback"


class AssumptionUseKind(str, Enum):
    """How a captured assumption is allowed to be used."""

    CURRENT_REPORT_INPUT = "current_report_input"
    FORWARD_DRIVER_INPUT = "forward_driver_input"
    SCENARIO_DELTA = "scenario_delta"


@dataclass(frozen=True)
class AssumptionEvidence:
    """Auditable provenance for one forward driver or pricing assumption."""

    field_key: str
    source_kind: AssumptionSourceKind
    use_kind: AssumptionUseKind
    confidence: ForwardEvidenceConfidence
    source: str
    responsible_surface: str
    freshness_days: int | None = None
    transformation: str | None = None
    override_reason: str | None = None
    fallback: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def is_forward_defensible(self) -> bool:
        return (
            not self.fallback
            and self.source_kind != AssumptionSourceKind.SYSTEM_FALLBACK
            and _confidence_at_least(self.confidence, ForwardEvidenceConfidence.MEDIUM)
        )


@dataclass(frozen=True)
class ForwardDriverValue:
    """One forecast driver value mapped to a method driver group."""

    driver_group: str
    value: object
    evidence: AssumptionEvidence


@dataclass(frozen=True)
class ForwardDriverRow:
    """Forecast-year driver row before it is admitted to method adapters."""

    fiscal_year: int
    drivers: tuple[ForwardDriverValue, ...]
    pricing_inputs: tuple[ForwardDriverValue, ...] = ()
    closed_year_financials_available: bool = False
    contains_open_ytd_inputs: bool = False
    warnings: tuple[str, ...] = ()

    def method_evidence(self, method_key: object) -> "ForwardMethodEvidence":
        """Build method evidence from defensible row values only."""

        spec = get_forward_method_spec(method_key)
        driver_groups = tuple(
            dict.fromkeys(
                value.driver_group
                for value in self.drivers
                if value.driver_group in spec.required_driver_groups
                and value.evidence.is_forward_defensible
            )
        )
        pricing_inputs = tuple(
            dict.fromkeys(
                value.driver_group
                for value in self.pricing_inputs
                if value.driver_group in spec.pricing_inputs
                and value.evidence.is_forward_defensible
            )
        )
        assumptions = tuple(value.evidence for value in (*self.drivers, *self.pricing_inputs))
        return ForwardMethodEvidence(
            available_driver_groups=driver_groups,
            available_pricing_inputs=pricing_inputs,
            assumptions=assumptions,
            warnings=self.warnings,
            confidence=_minimum_assumption_confidence(assumptions),
            closed_year_financials_available=self.closed_year_financials_available,
            contains_open_ytd_inputs=self.contains_open_ytd_inputs,
        )


@dataclass(frozen=True)
class ForwardabilityGate:
    """Result of checking one method against available forecast evidence."""

    method_key: str
    role: ForwardRole
    forwardable: bool
    horizon_years: int
    value_basis: ForwardValueBasis
    requires_equity_bridge: bool
    missing_driver_groups: tuple[str, ...]
    missing_pricing_inputs: tuple[str, ...]
    exclusion_reasons: tuple[str, ...]
    exclusion_rules: tuple[str, ...]
    warnings: tuple[str, ...]
    assumptions: tuple[AssumptionEvidence, ...]
    valuation_date_convention: str = FUTURE_VALUATION_DATE_CONVENTION


@dataclass(frozen=True)
class ForwardMethodEvidence:
    """Available evidence for one method adapter in one forecast horizon."""

    available_driver_groups: tuple[str, ...] = ()
    available_pricing_inputs: tuple[str, ...] = ()
    assumptions: tuple[AssumptionEvidence, ...] = ()
    warnings: tuple[str, ...] = ()
    confidence: ForwardEvidenceConfidence = ForwardEvidenceConfidence.HIGH
    closed_year_financials_available: bool = True
    contains_open_ytd_inputs: bool = False


@dataclass(frozen=True)
class ForwardMethodWeight:
    """A present blend method after horizon-specific forward re-gating."""

    method_key: str
    present_weight: float
    forward_weight: float
    value_basis: ForwardValueBasis
    requires_equity_bridge: bool
    uncertainty_family: str
    correlation_bucket: str


@dataclass(frozen=True)
class ForwardMethodExclusion:
    """Why a present blend method abstained from the forward cone for a horizon."""

    method_key: str
    present_weight: float
    reasons: tuple[str, ...]
    missing_driver_groups: tuple[str, ...]
    missing_pricing_inputs: tuple[str, ...]
    remediation: tuple[str, ...] = ()


@dataclass(frozen=True)
class ForwardBlendDecision:
    """Re-gated method participation for one forecast horizon."""

    horizon_years: int
    valuation_date_convention: str
    eligible_method_weights: tuple[ForwardMethodWeight, ...]
    excluded_methods: tuple[ForwardMethodExclusion, ...]
    audit_events: tuple[str, ...]


def get_forward_method_spec(method_key: object) -> ForwardMethodSpec:
    """Return the forwardability specification for a canonical method key."""

    normalized = normalize_method_key(method_key)
    try:
        return FORWARD_METHOD_SPECS[normalized]
    except KeyError as exc:
        raise KeyError(f"No forwardability specification for method key: {method_key!r}") from exc


def list_forward_method_specs() -> tuple[ForwardMethodSpec, ...]:
    """Return specs in canonical method order."""

    return tuple(FORWARD_METHOD_SPECS[key] for key in CANONICAL_METHOD_KEYS)


def _horizon_exclusion_reasons(spec: ForwardMethodSpec, horizon_years: int) -> tuple[str, ...]:
    if horizon_years <= 0:
        return ("invalid_forward_horizon",)
    if spec.horizon_cap_years is not None and horizon_years > spec.horizon_cap_years:
        return ("horizon_cap_exceeded",)
    return ()


def _role_exclusion_reasons(spec: ForwardMethodSpec) -> tuple[str, ...]:
    if spec.is_directly_forwardable:
        return ()
    if spec.role == ForwardRole.AGGREGATOR:
        return ("aggregator_reconciles_child_methods_only",)
    if spec.role == ForwardRole.STATIC_ANCHOR:
        return ("static_anchor_not_commercial_forward_prognosis",)
    if spec.role == ForwardRole.DOWNSIDE_ONLY:
        return ("downside_only_not_going_concern_forward_line",)
    return ("not_directly_forwardable",)


def _missing_evidence_reasons(
    *,
    missing_driver_groups: tuple[str, ...],
    missing_pricing_inputs: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if missing_driver_groups:
        reasons.append("missing_required_forward_drivers")
    if missing_pricing_inputs:
        reasons.append("missing_required_pricing_inputs")
    if "net_debt_cash_roll_forward" in missing_driver_groups:
        reasons.append("missing_equity_bridge_inputs")
    return tuple(reasons)


_CONFIDENCE_RANK = {
    ForwardEvidenceConfidence.LOW: 0,
    ForwardEvidenceConfidence.MEDIUM: 1,
    ForwardEvidenceConfidence.HIGH: 2,
}

_PRICING_INPUT_ASSUMPTION_ALIASES: Mapping[str, tuple[str, ...]] = {
    "wacc": ("wacc", "dcf_wacc_pct"),
    "terminal_value_assumption": (
        "terminal_value_assumption",
        "dcf_terminal_value_method",
        "dcf_terminal_growth_pct",
        "dcf_exit_multiple",
    ),
}

_WACC_BUILDUP_ASSUMPTION_KEYS = (
    "dcf_risk_free_rate_pct",
    "dcf_equity_risk_premium_pct",
    "dcf_beta",
    "dcf_cost_of_debt_pct",
    "dcf_debt_equity_pct",
    "dcf_tax_shield_pct",
)

_REMEDIATION_BY_REASON: Mapping[str, str] = {
    "missing_closed_year_financials": "Import or verify the latest closed fiscal year before emitting a forward cone.",
    "open_ytd_not_closed_year_basis": "Separate open-YTD context from closed-year valuation drivers.",
    "forward_evidence_below_confidence_threshold": "Raise driver evidence to medium confidence or higher.",
    "missing_required_forward_drivers": "Provide the forecast driver groups required by the method.",
    "missing_required_pricing_inputs": "Provide defensible pricing inputs with provenance.",
    "missing_equity_bridge_inputs": "Provide a net-debt/cash roll-forward for enterprise-to-equity conversion.",
    "horizon_cap_exceeded": "Shorten the forecast horizon or exclude the method for that year.",
    "invalid_forward_horizon": "Use a strictly positive forecast horizon.",
}


def _coerce_confidence(value: ForwardEvidenceConfidence | str) -> ForwardEvidenceConfidence:
    if isinstance(value, ForwardEvidenceConfidence):
        return value
    try:
        return ForwardEvidenceConfidence(str(value))
    except ValueError:
        return ForwardEvidenceConfidence.LOW


def _confidence_at_least(
    have: ForwardEvidenceConfidence | str,
    need: ForwardEvidenceConfidence,
) -> bool:
    return _CONFIDENCE_RANK[_coerce_confidence(have)] >= _CONFIDENCE_RANK[need]


def _minimum_assumption_confidence(
    assumptions: tuple[AssumptionEvidence, ...],
) -> ForwardEvidenceConfidence:
    if not assumptions:
        return ForwardEvidenceConfidence.LOW
    return min(
        (_coerce_confidence(item.confidence) for item in assumptions), key=_CONFIDENCE_RANK.get
    )


def _evidence_defensibility_reasons(
    *,
    confidence: ForwardEvidenceConfidence | str,
    closed_year_financials_available: bool,
    contains_open_ytd_inputs: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not closed_year_financials_available:
        reasons.append("missing_closed_year_financials")
    if contains_open_ytd_inputs:
        reasons.append("open_ytd_not_closed_year_basis")
    if not _confidence_at_least(confidence, ForwardEvidenceConfidence.MEDIUM):
        reasons.append("forward_evidence_below_confidence_threshold")
    return tuple(reasons)


def _has_defensible_assumption(
    pricing_input: str,
    assumptions: tuple[AssumptionEvidence, ...],
) -> bool:
    defensible_keys = {
        assumption.field_key for assumption in assumptions if assumption.is_forward_defensible
    }
    if pricing_input == "wacc":
        return bool({"wacc", "dcf_wacc_pct"} & defensible_keys) or all(
            key in defensible_keys for key in _WACC_BUILDUP_ASSUMPTION_KEYS
        )
    accepted_keys = _PRICING_INPUT_ASSUMPTION_ALIASES.get(pricing_input, (pricing_input,))
    return any(key in accepted_keys for key in defensible_keys)


def _pricing_inputs_after_provenance_filter(
    *,
    method_key: str,
    available_pricing_inputs: Iterable[str],
    assumptions: tuple[AssumptionEvidence, ...],
) -> set[str]:
    available_pricing = set(available_pricing_inputs)
    if method_key != "dcf" or not assumptions:
        return available_pricing
    return {
        pricing_input
        for pricing_input in available_pricing
        if _has_defensible_assumption(pricing_input, assumptions)
    }


def _remediation_for_reasons(reasons: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            _REMEDIATION_BY_REASON[reason] for reason in reasons if reason in _REMEDIATION_BY_REASON
        )
    )


def _evidence_warnings(
    *,
    warnings: Iterable[str],
    assumptions: tuple[AssumptionEvidence, ...],
    contains_open_ytd_inputs: bool,
) -> tuple[str, ...]:
    derived = list(warnings)
    for assumption in assumptions:
        derived.extend(assumption.warnings)
        if assumption.fallback or assumption.source_kind == AssumptionSourceKind.SYSTEM_FALLBACK:
            derived.append(f"fallback_assumption:{assumption.field_key}")
    if not assumptions:
        derived.append("missing_assumption_provenance")
    if contains_open_ytd_inputs:
        derived.append("open_ytd_inputs_excluded_from_forward_basis")
    return tuple(dict.fromkeys(derived))


def evaluate_forwardability(
    method_key: object,
    *,
    available_driver_groups: Iterable[str],
    available_pricing_inputs: Iterable[str],
    horizon_years: int = 1,
    assumptions: Iterable[AssumptionEvidence] = (),
    warnings: Iterable[str] = (),
    confidence: ForwardEvidenceConfidence | str = ForwardEvidenceConfidence.HIGH,
    closed_year_financials_available: bool = True,
    contains_open_ytd_inputs: bool = False,
) -> ForwardabilityGate:
    """Check whether a method has enough evidence to join a forward cone."""

    spec = get_forward_method_spec(method_key)
    assumption_tuple = tuple(assumptions)
    available_drivers = set(available_driver_groups)
    available_pricing = _pricing_inputs_after_provenance_filter(
        method_key=spec.method_key,
        available_pricing_inputs=available_pricing_inputs,
        assumptions=assumption_tuple,
    )
    missing_drivers = tuple(
        driver for driver in spec.required_driver_groups if driver not in available_drivers
    )
    missing_pricing = tuple(
        pricing_input
        for pricing_input in spec.pricing_inputs
        if pricing_input not in available_pricing
    )
    exclusion_reasons = (
        _role_exclusion_reasons(spec)
        + _horizon_exclusion_reasons(spec, horizon_years)
        + _evidence_defensibility_reasons(
            confidence=confidence,
            closed_year_financials_available=closed_year_financials_available,
            contains_open_ytd_inputs=contains_open_ytd_inputs,
        )
        + _missing_evidence_reasons(
            missing_driver_groups=missing_drivers,
            missing_pricing_inputs=missing_pricing,
        )
    )
    forwardable = not exclusion_reasons
    exclusion_rules = (
        tuple(dict.fromkeys((*spec.exclusion_rules, *exclusion_reasons))) if not forwardable else ()
    )
    return ForwardabilityGate(
        method_key=spec.method_key,
        role=spec.role,
        forwardable=forwardable,
        horizon_years=horizon_years,
        value_basis=spec.value_basis,
        requires_equity_bridge=spec.requires_equity_bridge,
        missing_driver_groups=missing_drivers,
        missing_pricing_inputs=missing_pricing,
        exclusion_reasons=exclusion_reasons,
        exclusion_rules=exclusion_rules,
        warnings=_evidence_warnings(
            warnings=warnings,
            assumptions=assumption_tuple,
            contains_open_ytd_inputs=contains_open_ytd_inputs,
        ),
        assumptions=assumption_tuple,
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


def _normalize_positive_weights(present_weights: Mapping[str, object]) -> dict[str, float]:
    normalized_weights: dict[str, float] = {}
    for raw_key, raw_weight in present_weights.items():
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError):
            continue
        if weight <= 0:
            continue
        method_key = normalize_method_key(raw_key)
        if method_key not in FORWARD_METHOD_SPECS:
            continue
        normalized_weights[method_key] = normalized_weights.get(method_key, 0.0) + weight
    return normalized_weights


def select_forward_methods_for_horizon(
    present_weights: Mapping[str, object],
    *,
    horizon_years: int,
    evidence_by_method: Mapping[str, ForwardMethodEvidence],
) -> ForwardBlendDecision:
    """Re-gate a present blend into forwardable method weights for one horizon.

    This is intentionally not a valuation calculator. It answers the governance
    question the forward cone needs first: which present methods can be rolled to
    future valuation date `t`, and how should surviving weights be normalized?
    """

    normalized_weights = _normalize_positive_weights(present_weights)
    eligible: list[tuple[str, float, ForwardabilityGate]] = []
    excluded: list[ForwardMethodExclusion] = []

    for method_key in CANONICAL_METHOD_KEYS:
        present_weight = normalized_weights.get(method_key)
        if present_weight is None:
            continue
        evidence = _evidence_for_method(evidence_by_method, method_key)
        gate = evaluate_forwardability(
            method_key,
            available_driver_groups=evidence.available_driver_groups,
            available_pricing_inputs=evidence.available_pricing_inputs,
            horizon_years=horizon_years,
            assumptions=evidence.assumptions,
            warnings=evidence.warnings,
            confidence=evidence.confidence,
            closed_year_financials_available=evidence.closed_year_financials_available,
            contains_open_ytd_inputs=evidence.contains_open_ytd_inputs,
        )
        if gate.forwardable:
            eligible.append((method_key, present_weight, gate))
            continue
        excluded.append(
            ForwardMethodExclusion(
                method_key=method_key,
                present_weight=present_weight,
                reasons=gate.exclusion_reasons,
                missing_driver_groups=gate.missing_driver_groups,
                missing_pricing_inputs=gate.missing_pricing_inputs,
                remediation=_remediation_for_reasons(gate.exclusion_reasons),
            )
        )

    eligible_total = sum(weight for _, weight, _ in eligible)
    eligible_weights: list[ForwardMethodWeight] = []
    if eligible_total > 0:
        for method_key, present_weight, gate in eligible:
            eligible_weights.append(
                ForwardMethodWeight(
                    method_key=method_key,
                    present_weight=present_weight,
                    forward_weight=present_weight / eligible_total,
                    value_basis=gate.value_basis,
                    requires_equity_bridge=gate.requires_equity_bridge,
                    uncertainty_family=get_forward_method_spec(method_key).uncertainty_family,
                    correlation_bucket=get_forward_method_spec(method_key).correlation_bucket,
                )
            )

    audit_events: list[str] = [
        f"valuation_date_convention:{FUTURE_VALUATION_DATE_CONVENTION}",
    ]
    if excluded:
        audit_events.extend(
            f"excluded:{exclusion.method_key}:{','.join(exclusion.reasons)}"
            for exclusion in excluded
        )
    if excluded and eligible_weights:
        audit_events.append("renormalized_forward_weights_after_re_gating")
    if not eligible_weights:
        audit_events.append("no_forwardable_child_methods")

    return ForwardBlendDecision(
        horizon_years=horizon_years,
        valuation_date_convention=FUTURE_VALUATION_DATE_CONVENTION,
        eligible_method_weights=tuple(eligible_weights),
        excluded_methods=tuple(excluded),
        audit_events=tuple(audit_events),
    )
