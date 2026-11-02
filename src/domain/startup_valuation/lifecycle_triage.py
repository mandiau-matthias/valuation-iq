"""Lifecycle-stage triage contract for startup vs mature-SME routing."""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Optional

from .schemas import (
    LifecycleRevenueState,
    LifecycleSignalProvenance,
    LifecycleStageCandidate,
    LifecycleStageTriage,
    StartupInputs,
)

STARTUP_ROUTING_STAGES: tuple[LifecycleStageCandidate, ...] = (
    "pre_revenue",
    "early_revenue",
    "seed",
    "growth",
    "growth_startup",
)

STARTUP_ROUTING_TAGS: frozenset[str] = frozenset(
    {
        "startup",
        "tech_startup",
        "saas",
        "software",
        "ai",
        "vertical_ai",
        "marketplace",
        "fintech",
        "deeptech",
        "deeptech_ai",
        "biotech_healthtech",
        "tech_services",
        "services_tech",
        "research_development",
    }
)

_SECTOR_TAGS: dict[str, tuple[str, ...]] = {
    "saas": ("startup", "tech_startup", "saas", "software"),
    "marketplace": ("startup", "tech_startup", "marketplace", "software"),
    "fintech": ("startup", "tech_startup", "fintech", "software"),
    "biotech_healthtech": (
        "startup",
        "tech_startup",
        "biotech_healthtech",
        "research_development",
    ),
    "deeptech_ai": ("startup", "tech_startup", "deeptech_ai", "ai"),
    "vertical_ai": ("startup", "tech_startup", "vertical_ai", "ai", "software"),
    "consumer": ("startup", "consumer"),
    "hardware": ("startup", "hardware"),
    "other": ("startup",),
}

_NACE_TECH_PREFIX_TAGS: dict[str, tuple[str, ...]] = {
    "58": ("software",),
    "62": ("software", "tech_services"),
    "63": ("software", "ai"),
    "70.22": ("tech_services",),
    "72": ("research_development", "deeptech"),
}


def coerce_lifecycle_stage_triage(value: object) -> Optional[LifecycleStageTriage]:
    """Return a triage model for Pydantic, dict, or compatible objects."""
    if isinstance(value, LifecycleStageTriage):
        return value
    if isinstance(value, Mapping):
        try:
            return LifecycleStageTriage.model_validate(value)
        except ValueError:
            return None
    return None


def resolve_lifecycle_stage_triage(
    startup_inputs: Optional[StartupInputs],
    lifecycle_stage_triage: object = None,
) -> Optional[LifecycleStageTriage]:
    """Prefer explicit triage, then embedded triage, then deterministic inference."""
    explicit = coerce_lifecycle_stage_triage(lifecycle_stage_triage)
    if explicit is not None:
        return complete_lifecycle_stage_triage(explicit, startup_inputs=startup_inputs)

    embedded = None if startup_inputs is None else startup_inputs.lifecycle_stage_triage
    if embedded is not None:
        return complete_lifecycle_stage_triage(embedded, startup_inputs=startup_inputs)

    if startup_inputs is None:
        return None
    return infer_lifecycle_stage_triage(startup_inputs)


def infer_lifecycle_stage_triage(inputs: StartupInputs) -> LifecycleStageTriage:
    """Infer a conservative stage classification from startup inputs."""
    tags = _business_type_tags(inputs)
    revenue_state = _revenue_state(inputs)
    candidate = _lifecycle_stage_candidate(inputs, revenue_state)
    score = _startup_signal_score(inputs, tags)
    reasons = _classification_reasons(inputs, candidate, revenue_state)
    missing = _missing_evidence_questions(inputs, revenue_state)
    provenance = _signal_provenance(inputs, revenue_state)

    return LifecycleStageTriage(
        business_type_tags=list(tags),
        lifecycle_stage_candidate=candidate,
        startup_signal_confidence=score,
        revenue_state=revenue_state,
        classification_reasons=reasons,
        missing_evidence_questions=missing,
        signal_provenance=provenance,
        geography_cluster=_geography_cluster(inputs.country_code),
    )


def complete_lifecycle_stage_triage(
    triage: LifecycleStageTriage,
    *,
    startup_inputs: Optional[StartupInputs] = None,
) -> LifecycleStageTriage:
    """Backfill omitted triage fields without overwriting explicit evidence."""
    if startup_inputs is None:
        return _dedupe_triage(triage)

    inferred = infer_lifecycle_stage_triage(startup_inputs)
    candidate = triage.lifecycle_stage_candidate
    if candidate == "unknown":
        candidate = inferred.lifecycle_stage_candidate

    revenue_state = triage.revenue_state
    if revenue_state == "unknown":
        revenue_state = inferred.revenue_state

    confidence = triage.startup_signal_confidence or inferred.startup_signal_confidence
    tags = _merge_strings(triage.business_type_tags, inferred.business_type_tags)
    reasons = _merge_strings(triage.classification_reasons, inferred.classification_reasons)
    questions = _merge_strings(
        triage.missing_evidence_questions,
        inferred.missing_evidence_questions,
    )[:8]

    return LifecycleStageTriage(
        business_type_tags=tags,
        lifecycle_stage_candidate=candidate,
        startup_signal_confidence=confidence,
        revenue_state=revenue_state,
        classification_reasons=reasons[:16],
        missing_evidence_questions=questions,
        signal_provenance=_merge_provenance(
            triage.signal_provenance,
            inferred.signal_provenance,
        ),
        geography_cluster=triage.geography_cluster or inferred.geography_cluster,
        manual_override_provenance=dict(triage.manual_override_provenance),
    )


def should_route_to_startup_path(triage: Optional[LifecycleStageTriage]) -> bool:
    """Return True when the mature-SME methods should fail closed."""
    if triage is None:
        return False
    if triage.lifecycle_stage_candidate == "mature":
        return False
    if triage.lifecycle_stage_candidate in STARTUP_ROUTING_STAGES:
        return True
    tags = {tag.lower() for tag in triage.business_type_tags}
    if tags & STARTUP_ROUTING_TAGS and triage.startup_signal_confidence > 0:
        return True
    return triage.lifecycle_stage_candidate == "transition" and (
        triage.startup_signal_confidence >= 35
    )


def requires_founder_clarification(triage: Optional[LifecycleStageTriage]) -> bool:
    """Low-confidence startup-ish classifications must ask before valuing as SME."""
    if triage is None:
        return False
    if triage.startup_signal_confidence < 50:
        return should_route_to_startup_path(triage)
    if triage.lifecycle_stage_candidate in {"transition", "unknown"}:
        return should_route_to_startup_path(triage)
    return False


def _dedupe_triage(triage: LifecycleStageTriage) -> LifecycleStageTriage:
    return LifecycleStageTriage(
        business_type_tags=_merge_strings(triage.business_type_tags, ()),
        lifecycle_stage_candidate=triage.lifecycle_stage_candidate,
        startup_signal_confidence=triage.startup_signal_confidence,
        revenue_state=triage.revenue_state,
        classification_reasons=_merge_strings(triage.classification_reasons, ())[:16],
        missing_evidence_questions=_merge_strings(triage.missing_evidence_questions, ())[:8],
        signal_provenance=_merge_provenance(triage.signal_provenance, ()),
        geography_cluster=triage.geography_cluster,
        manual_override_provenance=dict(triage.manual_override_provenance),
    )


def _business_type_tags(inputs: StartupInputs) -> tuple[str, ...]:
    tags: list[str] = list(_SECTOR_TAGS.get(str(inputs.sector), ("startup",)))
    nace = (inputs.nace_code or "").strip().lower()
    for prefix, prefix_tags in _NACE_TECH_PREFIX_TAGS.items():
        if nace.startswith(prefix):
            tags.extend(prefix_tags)
    studio_text = _studio_text(inputs.studio_v2)
    if _contains_any(studio_text, ("software", "platform", "saas", "api")):
        tags.append("software")
    if _contains_any(studio_text, ("ai", "machine learning", "automation")):
        tags.append("ai")
    return tuple(_merge_strings(tags, ()))


def _revenue_state(inputs: StartupInputs) -> LifecycleRevenueState:
    if _positive(inputs.arr) or _positive(inputs.mrr):
        return "recurring_revenue"
    if inputs.product_rollout > 0:
        return "first_revenue"
    return "none"


def _lifecycle_stage_candidate(
    inputs: StartupInputs,
    revenue_state: LifecycleRevenueState,
) -> LifecycleStageCandidate:
    if inputs.stage == "pre_seed":
        return "early_revenue" if revenue_state != "none" else "pre_revenue"
    if inputs.stage == "seed":
        return "early_revenue" if revenue_state == "recurring_revenue" else "pre_revenue"
    if inputs.stage == "series_a":
        return "growth" if revenue_state != "none" else "seed"
    return "unknown"


def _startup_signal_score(inputs: StartupInputs, tags: tuple[str, ...]) -> int:
    score = 20
    if set(tags) & STARTUP_ROUTING_TAGS:
        score += 20
    if _positive(inputs.arr) or _positive(inputs.mrr):
        score += 20
    elif inputs.product_rollout > 0:
        score += 10
    if _positive(inputs.year5_revenue_projection):
        score += 10
    if _has_round_context(inputs):
        score += 15
    if _strong_milestone_count(inputs) >= 3:
        score += 15
    elif _strong_milestone_count(inputs) > 0:
        score += 8
    if inputs.founder_pedigree.pedigree_evidence:
        score += 5
    return min(score, 95)


def _classification_reasons(
    inputs: StartupInputs,
    candidate: LifecycleStageCandidate,
    revenue_state: LifecycleRevenueState,
) -> list[str]:
    reasons = [
        f"Funding stage '{inputs.stage}' is stored separately from business type.",
        f"Startup sector '{inputs.sector}' provides a category signal, not a mature-SME stage.",
        f"Revenue state '{revenue_state}' maps to lifecycle candidate '{candidate}'.",
    ]
    if inputs.nace_code:
        reasons.append(f"NACE/activity signal '{inputs.nace_code}' contributes category tags.")
    if _has_round_context(inputs):
        reasons.append("Round/cap-table signals support startup-stage routing.")
    return reasons


def _missing_evidence_questions(
    inputs: StartupInputs,
    revenue_state: LifecycleRevenueState,
) -> list[str]:
    questions: list[str] = []
    if revenue_state == "none":
        questions.append("Is the company pre-revenue, first-revenue, or already recurring?")
    if not _has_round_context(inputs):
        questions.append("Is there an active round, valuation cap, target raise, or commitment?")
    if not _positive(inputs.year5_revenue_projection):
        questions.append("What conservative Year-5 revenue scenario should be used?")
    if _strong_milestone_count(inputs) < 3:
        questions.append("Which product, traction, team, or partnership evidence confirms stage?")
    return questions


def _signal_provenance(
    inputs: StartupInputs,
    revenue_state: LifecycleRevenueState,
) -> list[LifecycleSignalProvenance]:
    provenance = [
        LifecycleSignalProvenance(
            signal="funding_stage",
            source="founder_or_advisor_input",
            value=str(inputs.stage),
            reason="Funding stage is distinct from business type.",
            confidence="medium",
        ),
        LifecycleSignalProvenance(
            signal="sector",
            source="founder_or_enriched_company_input",
            value=str(inputs.sector),
            reason="Sector contributes business-type tags.",
            confidence="medium",
        ),
        LifecycleSignalProvenance(
            signal="revenue_state",
            source="startup_inputs",
            value=revenue_state,
            reason="ARR/MRR/product rollout determine lifecycle revenue state.",
            confidence="medium",
        ),
    ]
    if inputs.nace_code:
        provenance.append(
            LifecycleSignalProvenance(
                signal="nace_code",
                source="registry_or_enrichment",
                value=inputs.nace_code,
                reason="Activity code contributes software/tech/R&D tags.",
                confidence="medium",
            )
        )
    if _has_round_context(inputs):
        provenance.append(
            LifecycleSignalProvenance(
                signal="round_context",
                source="round_or_cap_table_inputs",
                value="present",
                reason="Round evidence is startup-stage market context.",
                confidence="medium",
            )
        )
    return provenance


def _geography_cluster(country_code: str) -> str:
    country = (country_code or "").upper()
    if country == "BE":
        return "belgium"
    if country in {"NL", "LU"}:
        return "benelux"
    if country in {"FR", "DE", "ES", "IT", "IE", "SE", "DK", "FI", "NO"}:
        return "eu"
    return "international"


def _merge_strings(primary: object, secondary: object) -> list[str]:
    merged: list[str] = []
    for source in (primary, secondary):
        if not isinstance(source, (list, tuple, set, frozenset)):
            continue
        for item in source:
            text = str(item or "").strip()
            if text and text not in merged:
                merged.append(text)
    return merged


def _merge_provenance(
    primary: object,
    secondary: object,
) -> list[LifecycleSignalProvenance]:
    merged: list[LifecycleSignalProvenance] = []
    seen: set[tuple[str, str, str]] = set()
    for source in (primary, secondary):
        if not isinstance(source, (list, tuple)):
            continue
        for item in source:
            signal = item if isinstance(item, LifecycleSignalProvenance) else None
            if signal is None:
                continue
            key = (signal.signal, signal.source, str(signal.value))
            if key in seen:
                continue
            seen.add(key)
            merged.append(signal)
    return merged[:32]


def _studio_text(value: object) -> str:
    if not isinstance(value, Mapping):
        return ""
    parts: list[str] = []
    for key in ("description", "product_language", "website_language"):
        raw = value.get(key)
        if raw:
            parts.append(str(raw))
    return " ".join(parts).lower()


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _has_round_context(inputs: StartupInputs) -> bool:
    scenario = inputs.round_scenario
    if scenario is not None:
        if _positive(scenario.pre_money) or _positive(scenario.post_money):
            return True
        if _positive(scenario.valuation_cap) or _positive(scenario.target_amount):
            return True
        if _positive(scenario.amount_raised):
            return True
    cap_table = inputs.cap_table
    if _positive(inputs.investment_amount_sought):
        return True
    if _positive(cap_table.pre_money_target):
        return True
    if _positive(cap_table.last_round_amount) or _positive(cap_table.last_round_post_money):
        return True
    return any(
        _positive(note.amount) or _positive(note.valuation_cap) for note in cap_table.safe_notes
    )


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


def _positive(value: Optional[Decimal]) -> bool:
    if value is None:
        return False
    try:
        return Decimal(value) > Decimal("0")
    except (ArithmeticError, TypeError, ValueError):
        return False
