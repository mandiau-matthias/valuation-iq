"""Startup methodology recommendation and mature-method gate.

This module is the explicit contract between the venture-stage startup
engine and the broader SME OmniCalc grid. Startup valuation can still show
the full method map for diagnostics, but the default product contract is
fail-closed: mature SME methods are not available for a startup-stage
company unless an advisor supplies override provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Optional, Protocol, TypeVar

from .lifecycle_triage import (
    requires_founder_clarification,
    resolve_lifecycle_stage_triage,
    should_route_to_startup_path,
)
from .money import safe_float
from .schemas import LifecycleStageTriage, StartupInputs

STARTUP_NATIVE_METHOD_KEY = "startup_valuation"
STARTUP_ALLOWED_METHOD_KEYS: tuple[str, ...] = (STARTUP_NATIVE_METHOD_KEY,)
STARTUP_BLOCKED_METHOD_KEYS: tuple[str, ...] = (
    "upswitch_adaptive",
    "ebitda_multiple",
    "dcf",
    "sde_multiple",
    "omzet_multiple",
    "arr_multiple",
    "adjusted_nav",
    "real_estate_yield",
    "fiscal_4x",
    "liquidation_analysis",
)

STARTUP_METHOD_OVERRIDE_CONTEXT_KEYS: tuple[str, ...] = (
    "startup_methodology_override_provenance",
    "startup_mature_method_override_provenance",
    "methodology_override_provenance",
    "advisor_method_override_provenance",
)

STARTUP_METHOD_OVERRIDE_TEXT_KEYS: tuple[str, ...] = (
    "method_override_note",
    "method_override_reason",
)

_METHOD_BLOCK_REASONS: dict[str, str] = {
    "upswitch_adaptive": (
        "Adaptive SME synthesis depends on mature financial history; a startup-stage company "
        "must use the startup valuation path unless an advisor override is documented."
    ),
    "ebitda_multiple": (
        "EV/EBITDA requires stable positive EBITDA and benchmarkable earnings. "
        "Startup-stage companies need venture-stage evidence first."
    ),
    "dcf": (
        "DCF requires forecastable cash flows. Startup-stage companies may expose projections "
        "inside the VC Method, but DCF cannot overwrite the startup valuation dot by default."
    ),
    "sde_multiple": (
        "SDE is a mature owner-operated SME method, not a venture-stage startup method."
    ),
    "omzet_multiple": (
        "Revenue multiples for mature SMEs cannot stand in for pre-seed/seed startup value. "
        "Revenue evidence feeds the startup methodology instead."
    ),
    "arr_multiple": (
        "Standalone ARR multiple is a SaaS specialty method. ARR can inform the startup "
        "SaaS Forward leg, but it must not overwrite the objective startup dot."
    ),
    "adjusted_nav": (
        "Adjusted NAV can be a downside lens, but it is not the current venture-stage "
        "company value for a startup."
    ),
    "real_estate_yield": (
        "Property income capitalisation is a property-specific premise and cannot "
        "replace a venture-stage startup valuation without an advisor override."
    ),
    "fiscal_4x": (
        "The fiscal 4x EBITDA reference is an SME/tax anchor and requires mature EBITDA."
    ),
    "liquidation_analysis": (
        "Liquidation is a separate premise of value, not the current startup valuation dot."
    ),
}

_BLOCKED_METHOD_LABELS: dict[str, str] = {
    "upswitch_adaptive": "UpSwitch Adaptive",
    "ebitda_multiple": "EBITDA multiple",
    "dcf": "DCF",
    "sde_multiple": "SDE multiple",
    "omzet_multiple": "Revenue multiple",
    "arr_multiple": "ARR multiple",
    "adjusted_nav": "Adjusted NAV",
    "real_estate_yield": "Real-estate yield",
    "fiscal_4x": "Fiscal 4x EBITDA",
    "liquidation_analysis": "Liquidation analysis",
}

_STAGE_TO_LIFECYCLE = {
    "pre_seed": "pre_revenue",
    "seed": "early_revenue",
    "series_a": "growth_startup",
}

_MethodResultT = TypeVar("_MethodResultT", bound="_MethodResultLike")


class _MethodResultLike(Protocol):
    value: object
    available: bool
    details: Optional[Mapping[str, object]]

    def model_copy(
        self: _MethodResultT,
        *,
        update: Mapping[str, object],
    ) -> _MethodResultT: ...


@dataclass(frozen=True)
class StartupMethodologyRecommendation:
    """Serializable startup methodology gate for downstream consumers."""

    recommended_methodology: str
    methodology_name: str
    business_type_tags: tuple[str, ...]
    lifecycle_stage_candidate: str
    funding_stage: str
    startup_signal_confidence: int
    startup_signal_confidence_level: str
    confidence_level: str
    confidence_score: int
    confidence_reasons: tuple[str, ...]
    classification_reasons: tuple[str, ...]
    allowed_methods: tuple[str, ...]
    blocked_methods: tuple[dict[str, str], ...]
    missing_evidence_questions: tuple[str, ...]
    lifecycle_stage_triage: dict[str, object]
    clarification_required: bool
    override_required_for_blocked_methods: bool
    override_provenance: Optional[dict[str, object]]

    def to_payload(self) -> dict[str, object]:
        """Return the stable JSON-ready contract consumed by apps."""
        return {
            "recommended_methodology": self.recommended_methodology,
            "methodology_name": self.methodology_name,
            "business_type_tags": list(self.business_type_tags),
            "lifecycle_stage_candidate": self.lifecycle_stage_candidate,
            "funding_stage": self.funding_stage,
            "startup_signal_confidence": {
                "score": self.startup_signal_confidence,
                "level": self.startup_signal_confidence_level,
            },
            "confidence": {
                "level": self.confidence_level,
                "score": self.confidence_score,
                "reasons": list(self.confidence_reasons),
            },
            "classification_reasons": list(self.classification_reasons),
            "allowed_methods": list(self.allowed_methods),
            "blocked_methods": [dict(item) for item in self.blocked_methods],
            "missing_evidence_questions": list(self.missing_evidence_questions),
            "lifecycle_stage_triage": dict(self.lifecycle_stage_triage),
            "clarification_required": self.clarification_required,
            "override_policy": {
                "blocked_methods_require_provenance": self.override_required_for_blocked_methods,
                "accepted_context_keys": list(STARTUP_METHOD_OVERRIDE_CONTEXT_KEYS),
                "accepted_text_keys": list(STARTUP_METHOD_OVERRIDE_TEXT_KEYS),
                "override_provenance": self.override_provenance,
            },
            "graph_contract": {
                "point_kind": "today_dot",
                "value_basis": "pre_money_equity_range",
                "range_fields": [
                    "canonical.pre_money_low",
                    "canonical.pre_money_mid",
                    "canonical.pre_money_high",
                ],
                "confidence_field": "methodology_recommendation.confidence",
                "round_context_layer": (
                    "Market-implied round/cap evidence is a separate layer and does not "
                    "overwrite the objective startup valuation dot."
                ),
                "future_snapshot_ready": True,
            },
        }


def build_startup_methodology_recommendation(
    inputs: Optional[StartupInputs],
    *,
    lifecycle_stage_triage: object = None,
    override_provenance: Optional[Mapping[str, object]] = None,
) -> StartupMethodologyRecommendation:
    """Build the v1 startup methodology recommendation and method gate."""
    triage = resolve_lifecycle_stage_triage(inputs, lifecycle_stage_triage)
    override_payload = _normalize_override_provenance(override_provenance)
    if override_payload is None and triage is not None:
        override_payload = _normalize_override_provenance(triage.manual_override_provenance)
    confidence_score, confidence_level, confidence_reasons = _confidence(inputs)
    lifecycle_stage = _lifecycle_stage_candidate(inputs, triage)
    classification_reasons = _classification_reasons(inputs, lifecycle_stage, triage)
    missing_questions = _missing_evidence_questions(inputs, triage)
    triage_payload = _triage_payload(triage)

    return StartupMethodologyRecommendation(
        recommended_methodology=STARTUP_NATIVE_METHOD_KEY,
        methodology_name=(
            "Startup Valuation v1 (Berkus + Scorecard + VC Method + SaaS Forward when eligible)"
        ),
        business_type_tags=tuple(triage.business_type_tags) if triage is not None else (),
        lifecycle_stage_candidate=lifecycle_stage,
        funding_stage=str(inputs.stage) if inputs is not None else "unknown",
        startup_signal_confidence=(
            triage.startup_signal_confidence if triage is not None else 0
        ),
        startup_signal_confidence_level=triage.confidence_level if triage is not None else "low",
        confidence_level=confidence_level,
        confidence_score=confidence_score,
        confidence_reasons=tuple(confidence_reasons),
        classification_reasons=tuple(classification_reasons),
        allowed_methods=STARTUP_ALLOWED_METHOD_KEYS,
        blocked_methods=tuple(
            {
                "method_key": method_key,
                "label": _BLOCKED_METHOD_LABELS[method_key],
                "reason": _METHOD_BLOCK_REASONS[method_key],
            }
            for method_key in STARTUP_BLOCKED_METHOD_KEYS
        ),
        missing_evidence_questions=tuple(missing_questions),
        lifecycle_stage_triage=triage_payload,
        clarification_required=requires_founder_clarification(triage) or (
            inputs is None and should_route_to_startup_path(triage)
        ),
        override_required_for_blocked_methods=True,
        override_provenance=override_payload,
    )


def resolve_startup_methodology_override_provenance(
    business_context: Optional[Mapping[str, object]],
) -> Optional[dict[str, object]]:
    """Resolve advisor override provenance from open business context."""
    if not isinstance(business_context, Mapping):
        return None

    for key in STARTUP_METHOD_OVERRIDE_CONTEXT_KEYS:
        normalized = _normalize_override_provenance(business_context.get(key))
        if normalized:
            normalized.setdefault("context_key", key)
            return normalized

    text_payload = {
        key: business_context.get(key)
        for key in STARTUP_METHOD_OVERRIDE_TEXT_KEYS
        if _has_text(business_context.get(key))
    }
    if text_payload:
        text_payload.setdefault("source", "advisor_method_override")
        return text_payload
    return None


def apply_startup_methodology_gate(
    results: Mapping[str, _MethodResultT],
    *,
    startup_inputs: Optional[StartupInputs],
    lifecycle_stage_triage: object = None,
    override_provenance: Optional[Mapping[str, object]] = None,
) -> dict[str, _MethodResultT]:
    """Block non-startup MethodResults when startup inputs are active."""
    triage = resolve_lifecycle_stage_triage(startup_inputs, lifecycle_stage_triage)
    if startup_inputs is None and not should_route_to_startup_path(triage):
        return dict(results)

    recommendation = build_startup_methodology_recommendation(
        startup_inputs,
        lifecycle_stage_triage=triage,
        override_provenance=override_provenance,
    )
    payload = recommendation.to_payload()
    override_payload = recommendation.override_provenance

    gated = dict(results)
    startup_result = gated.get(STARTUP_NATIVE_METHOD_KEY)
    if startup_result is not None:
        status = "allowed"
        reason = "Startup valuation is the allowed current-value method for this stage."
        if startup_inputs is None:
            status = "clarification_required"
            reason = (
                "Lifecycle triage indicates startup-stage routing, but startup_inputs "
                "are missing; collect founder evidence before producing a startup dot."
            )
        gated[STARTUP_NATIVE_METHOD_KEY] = _with_gate_details(
            startup_result,
            {
                "status": status,
                "reason": reason,
                "methodology_recommendation": payload,
            },
        )

    for method_key in STARTUP_BLOCKED_METHOD_KEYS:
        method = gated.get(method_key)
        if method is None:
            continue
        reason = _METHOD_BLOCK_REASONS[method_key]
        if override_payload:
            gated[method_key] = _with_gate_details(
                method,
                {
                    "status": "overridden",
                    "default_block_reason": reason,
                    "override_provenance": dict(override_payload),
                    "methodology_recommendation": payload,
                },
            )
            continue
        gated[method_key] = _blocked_method_result(method, method_key=method_key, reason=reason)

    return gated


def _blocked_method_result(
    method: _MethodResultT, *, method_key: str, reason: str
) -> _MethodResultT:
    details = dict(method.details or {})
    details["startup_methodology_gate"] = {
        "status": "blocked",
        "method_key": method_key,
        "reason": reason,
        "diagnostic_value": safe_float(method.value),
        "original_available": bool(method.available),
    }
    return method.model_copy(
        update={
            "value": None,
            "multiple_used": None,
            "wacc": None,
            "available": False,
            "unavailable_reason": f"Startup methodology gate: {reason}",
            "details": details,
            "value_low": None,
            "value_high": None,
        }
    )


def _with_gate_details(
    method: _MethodResultT, gate_payload: Mapping[str, object]
) -> _MethodResultT:
    details = dict(method.details or {})
    details["startup_methodology_gate"] = dict(gate_payload)
    return method.model_copy(update={"details": details})


def _confidence(inputs: Optional[StartupInputs]) -> tuple[int, str, list[str]]:
    if inputs is None:
        return (
            0,
            "low",
            ["Startup lifecycle triage is present, but qualitative startup inputs are missing."],
        )
    score = 25
    reasons: list[str] = []
    if _positive(inputs.arr) or _positive(inputs.mrr):
        score += 20
        reasons.append("Recurring revenue evidence is present.")
    if _positive(inputs.year5_revenue_projection):
        score += 15
        reasons.append("The VC Method has a Year-5 revenue projection.")
    if _has_round_context(inputs):
        score += 15
        reasons.append("Round or cap-table context is available as market evidence.")
    strong_milestones = _strong_milestone_count(inputs)
    if strong_milestones >= 3:
        score += 15
        reasons.append("Multiple qualitative startup milestones are above baseline.")
    elif strong_milestones > 0:
        score += 8
        reasons.append("Some qualitative startup milestones are above baseline.")
    if inputs.founder_pedigree.pedigree_evidence:
        score += 10
        reasons.append("Founder pedigree claims include evidence.")

    if not reasons:
        reasons.append("Only baseline startup inputs are present; keep the valuation band wide.")

    score = min(score, 95)
    if score >= 75:
        return score, "high", reasons
    if score >= 50:
        return score, "medium", reasons
    return score, "low", reasons


def _lifecycle_stage_candidate(
    inputs: Optional[StartupInputs],
    triage: Optional[LifecycleStageTriage],
) -> str:
    if triage is not None and triage.lifecycle_stage_candidate != "unknown":
        return triage.lifecycle_stage_candidate
    if inputs is None:
        return "unknown"
    if inputs.stage == "seed" and not (_positive(inputs.arr) or _positive(inputs.mrr)):
        return "pre_revenue"
    return _STAGE_TO_LIFECYCLE.get(str(inputs.stage), "early_stage_startup")


def _classification_reasons(
    inputs: Optional[StartupInputs],
    lifecycle_stage: str,
    triage: Optional[LifecycleStageTriage],
) -> list[str]:
    reasons: list[str] = []
    if triage is not None:
        reasons.extend(triage.classification_reasons)
    if inputs is None:
        return _dedupe_strings(
            reasons
            + [
                f"Lifecycle stage '{lifecycle_stage}' was received separately from business type.",
                "Founder clarification is required before producing a startup valuation dot.",
            ]
        )
    reasons = [
        f"Funding stage '{inputs.stage}' maps to lifecycle stage '{lifecycle_stage}'.",
        "Startup valuation uses venture-stage evidence rather than mature SME history.",
        f"Sector '{inputs.sector}' is evaluated through startup-sector policy.",
    ] + reasons
    if _has_round_context(inputs):
        reasons.append(
            "Round/cap-table context is present but kept separate from the objective dot."
        )
    if _positive(inputs.arr) or _positive(inputs.mrr):
        reasons.append("ARR/MRR evidence can inform the SaaS Forward leg when sector-compatible.")
    return _dedupe_strings(reasons)


def _missing_evidence_questions(
    inputs: Optional[StartupInputs],
    triage: Optional[LifecycleStageTriage],
) -> list[str]:
    questions: list[str] = []
    if triage is not None:
        questions.extend(triage.missing_evidence_questions)
    if inputs is None:
        return _dedupe_strings(
            questions
            + [
                "Confirm the lifecycle stage: pre-revenue, first revenue, recurring revenue, or mature.",
                "Collect the founder startup inputs before showing a startup valuation dot.",
            ]
        )[:4]
    if not (_positive(inputs.arr) or _positive(inputs.mrr)):
        questions.append("What recurring revenue or first-revenue evidence can be supplied?")
    if not _has_round_context(inputs):
        questions.append(
            "Is there a current pre-money, valuation cap, target raise, or commitment?"
        )
    if _strong_milestone_count(inputs) < 3:
        questions.append("Which prototype, rollout, partnership, or team evidence can be uploaded?")
    if not _positive(inputs.year5_revenue_projection):
        questions.append("What conservative Year-5 revenue scenario should the VC Method use?")
    return _dedupe_strings(questions)[:4]


def _triage_payload(triage: Optional[LifecycleStageTriage]) -> dict[str, object]:
    if triage is None:
        return {}
    payload = triage.model_dump(mode="json")
    return {str(key): value for key, value in payload.items()}


def _dedupe_strings(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    deduped: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in deduped:
            deduped.append(text)
    return deduped


def _strong_milestone_count(inputs: StartupInputs) -> int:
    fields = (
        inputs.sound_idea,
        inputs.prototype_status,
        inputs.management_strength,
        inputs.strategic_relationships,
        inputs.product_rollout,
        inputs.opportunity_size,
        inputs.competitive_environment,
        inputs.sales_marketing_channels,
    )
    return sum(1 for value in fields if int(value or 0) >= 65)


def _has_round_context(inputs: StartupInputs) -> bool:
    cap_table = inputs.cap_table
    scenario = inputs.round_scenario
    if scenario is not None:
        if _positive(scenario.pre_money) or _positive(scenario.post_money):
            return True
        if _positive(scenario.valuation_cap) or _positive(scenario.target_amount):
            return True
        if _positive(scenario.amount_raised):
            return True
    if _positive(inputs.investment_amount_sought):
        return True
    if _positive(cap_table.pre_money_target):
        return True
    if _positive(cap_table.last_round_amount) or _positive(cap_table.last_round_post_money):
        return True
    return any(
        _positive(note.amount) or _positive(note.valuation_cap) for note in cap_table.safe_notes
    )


def _normalize_override_provenance(value: object) -> Optional[dict[str, object]]:
    if isinstance(value, Mapping):
        payload = {str(key): item for key, item in value.items() if item is not None}
        has_reason = any(_has_text(payload.get(key)) for key in ("reason", "note", "source"))
        if has_reason:
            payload.setdefault("source", "advisor_override")
            return payload
        return None
    if _has_text(value):
        return {"source": "advisor_override", "note": str(value).strip()}
    return None


def _has_text(value: object) -> bool:
    return bool(str(value or "").strip())


def _positive(value: Optional[Decimal]) -> bool:
    if value is None:
        return False
    try:
        return Decimal(value) > Decimal("0")
    except (ArithmeticError, TypeError, ValueError):
        return False
