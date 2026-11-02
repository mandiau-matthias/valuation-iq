"""
Owner Dependency Analysis Models

This module defines the data models for assessing key person risk in SME valuations.
The 12-factor assessment quantifies how dependent a business is on its owner, resulting
in valuation adjustments from -40% (critical dependency) to 0% (minimal dependency).

Based on:
- Damodaran (2012): Investment Valuation, Chapter 12
- Small Business Valuation Standards (SBVS)
- Key Person Risk Assessment frameworks
"""

from decimal import Decimal
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# Lift the engine-band constants from the dedicated constants module
# (NOT from src.domain.models) so the Pydantic Fields below have a
# single source of truth without triggering a circular import via
# `src.domain.models/__init__.py`. `models.py` re-exports these for
# back-compat with existing callers.
from src.domain.owner_dependency_constants import (
    OWNER_DEPENDENCY_ENGINE_CEILING,
    OWNER_DEPENDENCY_ENGINE_FLOOR,
)


class DependencyLevel(str, Enum):
    """
    Five-tier dependency scoring system

    Maps to numeric scores:
    - VERY_LOW: 90-100 (minimal risk)
    - LOW: 70-89 (manageable risk)
    - MEDIUM: 40-69 (moderate risk)
    - HIGH: 20-39 (significant risk)
    - VERY_HIGH: 0-19 (critical risk)
    """

    VERY_LOW = "very_low"  # 0-10% dependency
    LOW = "low"  # 10-20% dependency
    MEDIUM = "medium"  # 20-35% dependency
    HIGH = "high"  # 35-50% dependency
    VERY_HIGH = "very_high"  # 50%+ dependency


class OwnerDependencyFactors(BaseModel):
    """
    12-factor owner dependency assessment.

    SEMANTIC CONTRACT — read before populating any factor.
    `DependencyLevel` represents the **level of the named noun**, not "risk".
    The engine (`OwnerDependencyEngine.INVERSE_FACTORS` at
    `domain/owner_dependency_engine.py:57-63`) knows which factors are direct
    (higher level → worse) vs. inverse (higher level → better) and scores
    accordingly:

      Direct factors  (7) — HIGHER level of the noun = MORE owner dependency
        client_concentration, operational_knowledge, sales_relationship,
        technical_expertise, industry_network, decision_making, brand_reputation
        → engine maps level via DEPENDENCY_SCORES (VERY_HIGH → 10, VERY_LOW → 95)

      Inverse factors (5) — HIGHER level of the noun = LESS owner dependency
        process_documentation, team_capability, succession_planning,
        business_scalability, contract_transferability
        → engine maps level via INVERSE_DEPENDENCY_SCORES (VERY_HIGH → 95, VERY_LOW → 10)

    Example: a fully-documented business has `process_documentation=VERY_HIGH`
    (lots of documentation) and the engine scores 95 (good). Setting it to
    `VERY_LOW` here means "almost no documentation" and scores 10 (bad).
    Do NOT use risk-language ("fully documented = VERY_LOW risk") — that
    inverts the meaning and produces wrong scores.

    All factors are weighted equally (8.33% each) to produce the overall
    score. PHASE 2 ENHANCEMENT: optional quantitative owner/FTE ratio
    supplements the qualitative factors.
    """

    # Quantitative supplementary data (Phase 2)
    owner_fte_ratio: Optional[Decimal] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Ratio of operational owners to total employees (quantitative metric that supplements qualitative factors)",
    )
    number_of_owners: Optional[int] = Field(None, ge=1, description="Number of operational owners")
    number_of_employees: Optional[int] = Field(None, ge=0, description="Total employees")

    # ----- Direct factors: HIGHER level = MORE owner dependency -----
    client_concentration: DependencyLevel = Field(
        description="Level of revenue concentration in top clients. VERY_HIGH = >75% revenue from top 3."
    )
    operational_knowledge: DependencyLevel = Field(
        description="Level of operational knowledge sitting only with the owner. VERY_HIGH = only owner knows."
    )
    sales_relationship: DependencyLevel = Field(
        description="Level of owner's personal involvement in client/sales relationships. VERY_HIGH = owner is sole contact."
    )
    technical_expertise: DependencyLevel = Field(
        description="Level of unique technical/professional skill held by the owner. VERY_HIGH = irreplaceable owner-only expertise."
    )
    industry_network: DependencyLevel = Field(
        description="Level of business dependence on the owner's personal industry network. VERY_HIGH = all relationships through owner."
    )
    decision_making: DependencyLevel = Field(
        description="Level of decision-making centralisation on the owner. VERY_HIGH = all decisions made by owner."
    )
    brand_reputation: DependencyLevel = Field(
        description="Level of personal-brand exposure (vs. business brand). VERY_HIGH = personal brand dominates business brand."
    )

    # ----- Inverse factors: HIGHER level = LESS owner dependency -----
    process_documentation: DependencyLevel = Field(
        description="Level of documentation of processes and procedures. VERY_HIGH = fully documented (good); VERY_LOW = nothing written down (bad)."
    )
    team_capability: DependencyLevel = Field(
        description="Level of management-team capability without the owner. VERY_HIGH = strong independent team (good); VERY_LOW = no team (bad)."
    )
    succession_planning: DependencyLevel = Field(
        description="Level of succession-plan completeness. VERY_HIGH = transition plan executed (good); VERY_LOW = no plan (bad)."
    )
    business_scalability: DependencyLevel = Field(
        description="Level of business-model scalability without the owner. VERY_HIGH = runs indefinitely without owner (good); VERY_LOW = stops within a week (bad)."
    )
    contract_transferability: DependencyLevel = Field(
        description="Level of transferability of contracts and licenses to a new owner. VERY_HIGH = fully transferable (good); VERY_LOW = tied to the person (bad)."
    )

    model_config = ConfigDict(use_enum_values=True)


class OwnerDependencyResult(BaseModel):
    """
    Result of owner dependency assessment

    Includes:
    - 12-factor breakdown
    - Overall score (0-100)
    - Risk level categorization
    - Valuation adjustment (-40% to 0%)
    - Detailed explanation
    - Key transition risks
    """

    factors: OwnerDependencyFactors = Field(description="Individual scores for all 12 factors")

    overall_score: Decimal = Field(
        ge=0,
        le=100,
        description="Overall dependency score (0=critical dependency, 100=no dependency)",
    )

    risk_level: str = Field(
        description="Risk categorization: MINIMAL, LOW, MEDIUM, HIGH, or CRITICAL"
    )

    valuation_adjustment: Decimal = Field(
        ge=OWNER_DEPENDENCY_ENGINE_FLOOR,
        le=OWNER_DEPENDENCY_ENGINE_CEILING,
        description=(
            "Valuation adjustment factor — lifecycle-dependent. The engine "
            "emits in the full engine band; "
            "`OwnerDependencyProcessor.process_owner_dependency` then clamps "
            "this to MVP_OWNER_ADJUSTMENT_FLOOR before scaling equity "
            "values. The unclamped engine output is preserved on "
            "`raw_adjustment` for analytics. Bound to the engine band, not "
            "the MVP band, so engine-level construction in tests / fixtures "
            "works without a separate pre-cap model."
        ),
    )

    raw_adjustment: Optional[Decimal] = Field(
        default=None,
        ge=OWNER_DEPENDENCY_ENGINE_FLOOR,
        le=OWNER_DEPENDENCY_ENGINE_CEILING,
        description=(
            "Engine-emitted (uncapped) adjustment, preserved for analytics. "
            "Identical to `valuation_adjustment` when the MVP cap was not "
            "binding. May be more negative than `valuation_adjustment` when "
            "the cap clamped the headline figure. NEVER surface to clients "
            "without the 'cap applied' framing — see SPIKE-1 §3.2 and §5.4."
        ),
    )

    explanation: str = Field(description="Detailed explanation of the assessment and adjustment")

    key_risks: List[str] = Field(
        default_factory=list, description="List of primary transition risks identified"
    )

    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations to reduce owner dependency"
    )

    # ── Transferability v2 (BET-180 follow-up) ─────────────────────────
    # Optional, additive metadata. The engine fills this when factor
    # scores are available; back-compat callers (tests, fixtures, the
    # legacy stateless path) leave it None and the renderer falls back
    # to the v1 single-index view. The forward-ref string lets us
    # type-bind to `TransferabilityProfile` without a module-level
    # circular import (transferability.py imports from this module's
    # siblings); the import below the class plus the
    # `model_rebuild()` call wires it up at module load.
    transferability_profile: Optional["TransferabilityProfile"] = Field(
        default=None,
        description=(
            "v2 decomposition: 5 sub-factors + buyer profile + gap + "
            "per-method incidence + narrative cascade + confidence + "
            "methodology citations. See "
            "`src/domain/owner_models/transferability.py`."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall_score": 65.0,
                "risk_level": "MEDIUM",
                "valuation_adjustment": -0.15,
                "explanation": "Moderate owner dependency detected. Business has some documented processes but owner remains critical for client relationships and technical expertise.",
                "key_risks": [
                    "Owner manages all top 5 client relationships personally",
                    "Technical expertise not fully documented",
                    "No formal succession plan in place",
                ],
                "recommendations": [
                    "Document technical processes and create knowledge base",
                    "Introduce clients to other team members",
                    "Develop formal succession plan with timeline",
                ],
            }
        }
    )


class OwnerDependencyQuestion(BaseModel):
    """
    Question model for owner dependency assessment

    Used to generate dynamic questions in the frontend
    """

    factor: str = Field(description="Which of the 12 factors this question assesses")
    question_text: str = Field(description="Question to ask the user")
    question_type: str = Field(description="single_select, multiple_select, or text")
    options: List[str] = Field(description="Answer options")
    scoring_map: dict = Field(description="Map options to DependencyLevel")
    help_text: Optional[str] = Field(default=None, description="Additional guidance")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "factor": "client_concentration",
                "question_text": "What percentage of your revenue comes from your top 3 clients?",
                "question_type": "single_select",
                "options": ["<10%", "10-25%", "25-50%", "50-75%", ">75%"],
                "scoring_map": {
                    "<10%": "very_low",
                    "10-25%": "low",
                    "25-50%": "medium",
                    "50-75%": "high",
                    ">75%": "very_high",
                },
                "help_text": "Higher client concentration increases risk if the owner leaves",
            }
        }
    )

# Resolve the forward reference on `OwnerDependencyResult.transferability_profile`.
# Imported here, after both classes are defined, to avoid a circular import:
# transferability.py imports BaseModel/etc. but does NOT import from this module.
from src.domain.owner_models.transferability import TransferabilityProfile  # noqa: E402

OwnerDependencyResult.model_rebuild()
