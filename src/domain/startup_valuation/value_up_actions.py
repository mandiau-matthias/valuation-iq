"""Action contract for moving a startup valuation dot.

The startup graph should never end at "you are worth X". These actions
translate the methodology into founder-visible next steps, explicitly separating
actions that can increase the objective value from actions that increase
confidence/proof around the current value.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Literal, TypedDict

from .schemas import StartupInputs
from .sector_policy import is_saas_forward_compatible

StartupValueImpactType = Literal["increase_value", "increase_confidence"]
StartupActionTiming = Literal["immediate", "scheduled"]
StartupActionReminderType = Literal[
    "revenue_evidence_update",
    "traction_evidence_update",
    "round_status_update",
    "moat_evidence_review",
    "team_credibility_review",
]


class StartupValueUpAction(TypedDict):
    id: str
    title: str
    why_it_matters: str
    evidence_requested: List[str]
    expected_impact_direction: StartupValueImpactType
    confidence: Literal["low", "medium", "high"]
    valuation_factor: str
    methodology_factor: str
    methodology_methods: List[str]
    action_timing: StartupActionTiming
    suggested_target_offset_days: Literal[7, 14]
    reminder_type: StartupActionReminderType


def build_startup_value_up_actions(inputs: StartupInputs) -> List[StartupValueUpAction]:
    """Return deterministic methodology-tied actions for the founder."""

    # ARR is a governed driver only when the SaaS Forward method is applicable.
    # A marketplace, hardware or unknown-sector startup must not be told to
    # manufacture recurring-revenue evidence for a method the engine excludes.
    actions: List[StartupValueUpAction] = []
    if is_saas_forward_compatible(inputs.sector):
        actions.append(_arr_action(inputs))

    if inputs.product_rollout < 65 or inputs.strategic_relationships < 65:
        actions.append(_traction_contracts_action(inputs))

    if inputs.round_scenario is None or inputs.round_scenario.evidence_quality in {
        "unverified",
        "founder_asserted",
    }:
        actions.append(_round_context_action())

    if inputs.competitive_environment < 70:
        actions.append(_moat_action(inputs))

    if inputs.management_strength < 80 or _positive_pedigree_without_evidence(inputs):
        actions.append(_team_credibility_action(inputs))

    return actions[:5]


def _arr_action(inputs: StartupInputs) -> StartupValueUpAction:
    arr = inputs.arr or Decimal("0")
    mrr = inputs.mrr or Decimal("0")
    if arr <= 0 and mrr > 0:
        arr = mrr * Decimal("12")

    if arr <= 0:
        return {
            "id": "arr_revenue_evidence",
            "title": "Add ARR or revenue evidence",
            "why_it_matters": (
                "The SaaS Forward leg is unavailable until recurring revenue is evidenced, "
                "so the range stays wider and relies more on milestone methods."
            ),
            "evidence_requested": [
                "MRR/ARR export",
                "recent invoices or bank proof",
                "customer list with active contract dates",
            ],
            "expected_impact_direction": "increase_confidence",
            "confidence": "high",
            "valuation_factor": "saas_forward.arr_evidence",
            "methodology_factor": "SaaS Forward: current ARR evidence",
            "methodology_methods": ["saas_forward"],
            "action_timing": "immediate",
            "suggested_target_offset_days": 7,
            "reminder_type": "revenue_evidence_update",
        }

    return {
        "id": "arr_growth_retention",
        "title": "Prove ARR growth and retention",
        "why_it_matters": (
            "The SaaS Forward leg capitalises forward ARR after growth and churn risk; "
            "better growth/retention can move the objective dot upward."
        ),
        "evidence_requested": [
            "monthly MRR bridge",
            "logo or revenue churn",
            "cohort retention or renewal evidence",
        ],
        "expected_impact_direction": "increase_value",
        "confidence": "medium",
        "valuation_factor": "saas_forward.forward_arr",
        "methodology_factor": "SaaS Forward: forward ARR and churn risk",
        "methodology_methods": ["saas_forward"],
        "action_timing": "immediate",
        "suggested_target_offset_days": 7,
        "reminder_type": "revenue_evidence_update",
    }


def _traction_contracts_action(inputs: StartupInputs) -> StartupValueUpAction:
    confidence: Literal["low", "medium", "high"] = (
        "high" if inputs.product_rollout < 45 else "medium"
    )
    return {
        "id": "traction_contracts",
        "title": "Upload signed LOIs, pilots, or launch proof",
        "why_it_matters": (
            "Berkus product rollout and strategic relationships price execution and market "
            "risk directly; real commitments can raise those milestone contributions."
        ),
        "evidence_requested": [
            "signed LOIs or pilot contracts",
            "launch metrics",
            "named channel or partner agreements",
        ],
        "expected_impact_direction": "increase_value",
        "confidence": confidence,
        "valuation_factor": "berkus.product_rollout",
        "methodology_factor": "Berkus: product rollout and strategic relationships",
        "methodology_methods": ["berkus"],
        "action_timing": "immediate",
        "suggested_target_offset_days": 7,
        "reminder_type": "traction_evidence_update",
    }


def _round_context_action() -> StartupValueUpAction:
    return {
        "id": "round_context_terms",
        "title": "Document round terms or investor interest",
        "why_it_matters": (
            "The VC Method can compare the engine-derived value with market-implied "
            "evidence, but only if caps, pre-money, or commitments are sourced."
        ),
        "evidence_requested": [
            "term sheet or SAFE cap",
            "committed amount",
            "investor email or advisor-entered round note",
        ],
        "expected_impact_direction": "increase_confidence",
        "confidence": "high",
        "valuation_factor": "vc_method.round_context",
        "methodology_factor": "VC Method: market-implied round context",
        "methodology_methods": ["vc"],
        "action_timing": "immediate",
        "suggested_target_offset_days": 7,
        "reminder_type": "round_status_update",
    }


def _moat_action(inputs: StartupInputs) -> StartupValueUpAction:
    confidence: Literal["low", "medium", "high"] = (
        "high" if inputs.competitive_environment < 45 else "medium"
    )
    return {
        "id": "moat_ip_data_advantage",
        "title": "Clarify moat, IP, or proprietary data advantage",
        "why_it_matters": (
            "The Scorecard competitive-environment factor moves the company against "
            "regional peers before revenue is mature."
        ),
        "evidence_requested": [
            "IP assignment or patent note",
            "data advantage proof",
            "competitor comparison",
        ],
        "expected_impact_direction": "increase_value",
        "confidence": confidence,
        "valuation_factor": "scorecard.competitive_environment",
        "methodology_factor": "Scorecard: competitive environment",
        "methodology_methods": ["scorecard"],
        "action_timing": "scheduled",
        "suggested_target_offset_days": 14,
        "reminder_type": "moat_evidence_review",
    }


def _team_credibility_action(inputs: StartupInputs) -> StartupValueUpAction:
    impact: StartupValueImpactType = (
        "increase_confidence" if _positive_pedigree_without_evidence(inputs) else "increase_value"
    )
    return {
        "id": "team_credibility",
        "title": "Evidence founder-team credibility",
        "why_it_matters": (
            "Management strength and founder pedigree affect execution risk; unsupported "
            "pedigree claims increase uncertainty even when the story sounds strong."
        ),
        "evidence_requested": [
            "founder LinkedIn or CV",
            "prior exit/company reference",
            "technical cofounder ownership proof",
        ],
        "expected_impact_direction": impact,
        "confidence": "medium",
        "valuation_factor": "berkus.management_strength",
        "methodology_factor": "Berkus: management strength and founder pedigree",
        "methodology_methods": ["berkus", "founder_pedigree"],
        "action_timing": "scheduled",
        "suggested_target_offset_days": 14,
        "reminder_type": "team_credibility_review",
    }


def _positive_pedigree_without_evidence(inputs: StartupInputs) -> bool:
    pedigree = inputs.founder_pedigree
    evidence = pedigree.pedigree_evidence or {}
    positive_claims: Dict[str, bool] = {
        "prior_exit": pedigree.prior_exit,
        "top_unicorn_alumnus": pedigree.top_unicorn_alumnus,
        "domain_expert_10y": pedigree.domain_expert_10y,
        "second_time_founder": pedigree.second_time_founder,
        "has_technical_cofounder": pedigree.has_technical_cofounder,
    }
    return any(claimed and not evidence.get(key) for key, claimed in positive_claims.items())
