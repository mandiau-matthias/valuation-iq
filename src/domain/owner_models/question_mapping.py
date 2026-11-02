"""
Question → 12-factor mapping (OWNER-PROFILING-1 OP-4).

Implements SPIKE-1 §2.1 verbatim. Pure functions; no I/O. The 9 raw answers
collected by the Mercury wizard project onto the 12 typed
`OwnerDependencyFactors` the engine consumes. Three questions (Q1, Q5, Q7)
each drive two factors — that mapping is *intentional* (see §2.1 coverage
table).

ENGINE SEMANTICS — read before changing any threshold.
The `DependencyLevel` returned for each factor is the level of the **named
noun**, NOT a risk rating. The engine knows which factors are direct (higher
level = more dependency = bad) vs. inverse (higher level = less dependency =
good) via `OwnerDependencyEngine.INVERSE_FACTORS`. So for inverse factors
like `process_documentation`, VERY_HIGH means "lots of documentation" which
the engine scores 95 (good). Reversing that semantic here would silently
invert 5/12 factor scores — see SPIKE-1 risk register R1.

If the SPIKE-1 mapping is changed (e.g., Q4 brackets re-tuned after demo
data), update both this module and `tests/unit/synthesis/
test_question_to_factor_mapping.py` in the same PR. The tests pin the
boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from src.domain.owner_models.owner_dependency import (
    DependencyLevel,
    OwnerDependencyFactors,
)


# ---------------------------------------------------------------------------
# Question-answer types
# ---------------------------------------------------------------------------

SuccessionPlanStatus = Literal["none", "informal", "documented", "executed"]
OwnerRequiredCertifications = Literal["none", "transferable", "personal_only"]
BrandPersonalVsBusiness = Literal["lt_10", "10_30", "30_60", "gt_60"]
BusinessContinuityPeriod = Literal[
    "lt_1week", "1_4weeks", "1_6months", "indefinitely"
]


@dataclass(frozen=True)
class OwnerProfileAnswers:
    """Raw 9-question answer payload from the Mercury wizard.

    All 9 fields required at MVP. Skipping a question is a UX-layer decision;
    if the wizard allows skip-and-default, it must populate the corresponding
    field with its documented default before calling `to_factors`. We do NOT
    silently default here because the engine semantic for "no answer" is
    ambiguous (a defaulted MEDIUM is always wrong in some direction).
    """

    # Q1: hours owner works per week (0..168, slider capped at 80 in UI)
    owner_hours_per_week: int
    # Q2: 1..10 scale of how well the business runs without the owner
    delegation_capability: int
    # Q3: succession-plan status enum
    succession_plan_status: SuccessionPlanStatus
    # Q4: 0..100 percentage of revenue from top-3 customers
    top3_customer_revenue_pct: int
    # Q5: 0..100 percentage of those customer relationships that go through the owner only
    customer_relationships_owner_only_pct: int
    # Q6: 0..100 percentage of core processes documented
    process_documentation_pct: int
    # Q7: certifications/licenses required to run the business
    owner_required_certifications: OwnerRequiredCertifications
    # Q8: bucketed estimate of customer loss if owner exits + business renames
    brand_personal_vs_business: BrandPersonalVsBusiness
    # Q9: bucketed business-continuity period without the owner
    business_continuity_period: BusinessContinuityPeriod

    # Phase 2 quantitative supplements (already on `OwnerDependencyFactors`,
    # populated by Hermes financial-data feed when available).
    owner_fte_ratio: Optional[float] = None
    number_of_owners: Optional[int] = None
    number_of_employees: Optional[int] = None


# ---------------------------------------------------------------------------
# Per-question mappings (engine semantics)
# ---------------------------------------------------------------------------


def _hours_to_level(hours: int) -> DependencyLevel:
    """Q1 → decision_making, operational_knowledge (DIRECT).

    Higher hours = more owner-direct work = HIGHER dependency level.
    """
    if hours <= 20:
        return DependencyLevel.VERY_LOW
    if hours <= 40:
        return DependencyLevel.LOW
    if hours <= 55:
        return DependencyLevel.MEDIUM
    if hours <= 65:
        return DependencyLevel.HIGH
    return DependencyLevel.VERY_HIGH


def _delegation_to_team_capability(score_1_to_10: int) -> DependencyLevel:
    """Q2 → team_capability (INVERSE).

    Higher delegation score = stronger team = HIGHER level of team capability.
    Engine semantic: VERY_HIGH team_capability → score 95 (good).
    """
    if score_1_to_10 <= 2:
        return DependencyLevel.VERY_LOW
    if score_1_to_10 <= 4:
        return DependencyLevel.LOW
    if score_1_to_10 <= 6:
        return DependencyLevel.MEDIUM
    if score_1_to_10 <= 8:
        return DependencyLevel.HIGH
    return DependencyLevel.VERY_HIGH


def _succession_status_to_level(status: SuccessionPlanStatus) -> DependencyLevel:
    """Q3 → succession_planning (INVERSE).

    Higher level = more complete plan = better. Engine: VERY_HIGH → 95.
    `documented` is HIGH and `executed` is VERY_HIGH (a written-but-untested
    plan is materially less robust than one rehearsed end-to-end).
    """
    return {
        "none": DependencyLevel.VERY_LOW,
        "informal": DependencyLevel.LOW,
        "documented": DependencyLevel.HIGH,
        "executed": DependencyLevel.VERY_HIGH,
    }[status]


def _top3_pct_to_client_concentration(pct: int) -> DependencyLevel:
    """Q4 → client_concentration (DIRECT).

    Higher concentration = HIGHER dependency level. Engine: VERY_HIGH → 10 (bad).
    """
    if pct < 30:
        return DependencyLevel.VERY_LOW
    if pct < 50:
        return DependencyLevel.LOW
    if pct < 65:
        return DependencyLevel.MEDIUM
    if pct < 80:
        return DependencyLevel.HIGH
    return DependencyLevel.VERY_HIGH


def _owner_only_pct_to_level(pct: int) -> DependencyLevel:
    """Q5 → sales_relationship + industry_network (DIRECT, mirrored).

    Same bucket drives both factors per SPIKE-1 §2.1 coverage table.
    Higher % owner-only relationships = HIGHER dependency.
    """
    if pct < 10:
        return DependencyLevel.VERY_LOW
    if pct < 25:
        return DependencyLevel.LOW
    if pct < 50:
        return DependencyLevel.MEDIUM
    if pct < 75:
        return DependencyLevel.HIGH
    return DependencyLevel.VERY_HIGH


def _doc_pct_to_process_documentation(pct: int) -> DependencyLevel:
    """Q6 → process_documentation (INVERSE).

    Higher % documented = HIGHER level of documentation = better.
    Engine: VERY_HIGH process_documentation → 95.
    """
    if pct < 15:
        return DependencyLevel.VERY_LOW
    if pct < 35:
        return DependencyLevel.LOW
    if pct < 60:
        return DependencyLevel.MEDIUM
    if pct < 75:
        return DependencyLevel.HIGH
    return DependencyLevel.VERY_HIGH


def _certs_to_technical_expertise(value: OwnerRequiredCertifications) -> DependencyLevel:
    """Q7 → technical_expertise (DIRECT).

    `personal_only` = unique, irreplaceable owner expertise = HIGH dependency.
    `none` = no specialised expertise required = VERY_LOW dependency.
    """
    return {
        "none": DependencyLevel.VERY_LOW,
        "transferable": DependencyLevel.LOW,
        "personal_only": DependencyLevel.HIGH,
    }[value]


def _certs_to_contract_transferability(
    value: OwnerRequiredCertifications,
) -> DependencyLevel:
    """Q7 → contract_transferability (INVERSE, mirrored).

    Same answer drives a second factor with inverted semantics:
    `personal_only` = license tied to person = NOT transferable = VERY_LOW level.
    `none` = nothing to transfer = trivially transferable = VERY_HIGH level.
    """
    return {
        "personal_only": DependencyLevel.VERY_LOW,
        "transferable": DependencyLevel.HIGH,
        "none": DependencyLevel.VERY_HIGH,
    }[value]


def _brand_to_brand_reputation(value: BrandPersonalVsBusiness) -> DependencyLevel:
    """Q8 → brand_reputation (DIRECT).

    Bimodal in practice — SPIKE-1 §2.1 explicitly skips MEDIUM. We respect
    that and jump from LOW to HIGH at the 30% threshold so the discount math
    matches the doc.
    """
    return {
        "lt_10": DependencyLevel.VERY_LOW,
        "10_30": DependencyLevel.LOW,
        "30_60": DependencyLevel.HIGH,  # bimodal — skip MEDIUM intentionally
        "gt_60": DependencyLevel.VERY_HIGH,
    }[value]


def _continuity_to_business_scalability(value: BusinessContinuityPeriod) -> DependencyLevel:
    """Q9 → business_scalability (INVERSE).

    Spec also bimodal: spec maps `1_6months` to HIGH (skip MEDIUM). The
    business that survives a month is materially in a different class from
    the one that survives a week — there's no useful middle band.
    """
    return {
        "lt_1week": DependencyLevel.VERY_LOW,
        "1_4weeks": DependencyLevel.LOW,
        "1_6months": DependencyLevel.HIGH,  # bimodal — skip MEDIUM intentionally
        "indefinitely": DependencyLevel.VERY_HIGH,
    }[value]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def map_answers_to_factors(answers: OwnerProfileAnswers) -> OwnerDependencyFactors:
    """Project the 9-question payload onto the typed 12-factor model.

    Pure function; safe to call from anywhere. The returned
    `OwnerDependencyFactors` is what `OwnerDependencyEngine.calculate_dependency_score`
    consumes.
    """
    hours_level = _hours_to_level(answers.owner_hours_per_week)
    owner_only_level = _owner_only_pct_to_level(
        answers.customer_relationships_owner_only_pct
    )

    return OwnerDependencyFactors(
        # Phase-2 quantitative supplements
        owner_fte_ratio=(
            None if answers.owner_fte_ratio is None else answers.owner_fte_ratio  # type: ignore[arg-type]
        ),
        number_of_owners=answers.number_of_owners,
        number_of_employees=answers.number_of_employees,
        # Direct factors (high level = bad)
        client_concentration=_top3_pct_to_client_concentration(
            answers.top3_customer_revenue_pct
        ),
        operational_knowledge=hours_level,
        sales_relationship=owner_only_level,
        technical_expertise=_certs_to_technical_expertise(
            answers.owner_required_certifications
        ),
        industry_network=owner_only_level,
        decision_making=hours_level,
        brand_reputation=_brand_to_brand_reputation(answers.brand_personal_vs_business),
        # Inverse factors (high level = good)
        process_documentation=_doc_pct_to_process_documentation(
            answers.process_documentation_pct
        ),
        team_capability=_delegation_to_team_capability(answers.delegation_capability),
        succession_planning=_succession_status_to_level(answers.succession_plan_status),
        business_scalability=_continuity_to_business_scalability(
            answers.business_continuity_period
        ),
        contract_transferability=_certs_to_contract_transferability(
            answers.owner_required_certifications
        ),
    )


__all__ = [
    "BrandPersonalVsBusiness",
    "BusinessContinuityPeriod",
    "OwnerProfileAnswers",
    "OwnerRequiredCertifications",
    "SuccessionPlanStatus",
    "map_answers_to_factors",
]
