"""Top-level transferability profile assembly."""

from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.domain.owner_models.transferability_buyer_gap import (
    BuyerProfile,
    TransferabilityGap,
    compute_transferability_gap,
    derive_buyer_profile,
)
from src.domain.owner_models.transferability_citations import (
    METHODOLOGY_CITATIONS,
    MethodologyCitation,
)
from src.domain.owner_models.transferability_decomposition import (
    TransferabilityDecomposition,
    decompose_factors,
)
from src.domain.owner_models.transferability_incidence import (
    CascadeLineData,
    MethodIncidence,
    blended_incidence,
    build_cascade_data,
    build_narrative_cascade,
    method_incidence_table,
)


class ConfidenceTier(str, Enum):
    """Renderer-visible confidence in the headline adjustment."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConfidenceAssessment(BaseModel):
    """Confidence chip surfaced next to the headline adjustment."""

    tier: ConfidenceTier
    coverage_pct: int = Field(ge=0, le=100)
    rationale: str
    cap_binding: bool

    model_config = ConfigDict(use_enum_values=True)


def derive_confidence_tier(
    decomposition: TransferabilityDecomposition,
    *,
    owner_hours_supplied: bool,
    cap_binding: bool,
) -> ConfidenceAssessment:
    """Pick a confidence tier from data coverage and cap-binding state."""
    contributing = sum(1 for sf in decomposition.sub_factors for _ in sf.contributing_factors)
    coverage_pct = int(round((contributing / 12.0) * 100))
    coverage_pct = max(0, min(100, coverage_pct))

    if coverage_pct <= 50:
        tier = ConfidenceTier.LOW
        rationale = (
            f"Low confidence: only {coverage_pct}% of the 12 factors "
            "had usable data; v2 panels are indicative only."
        )
    elif cap_binding:
        tier = ConfidenceTier.MEDIUM
        rationale = (
            "Medium confidence: cap is binding (the engine wanted a "
            "deeper discount but the MVP -15% cap is holding the "
            "headline)."
        )
    elif not owner_hours_supplied:
        tier = ConfidenceTier.MEDIUM
        rationale = (
            f"Medium confidence: {coverage_pct}% factor coverage but "
            "owner-hours not supplied; gap uses a pessimistic 60 hrs/wk "
            "default."
        )
    elif coverage_pct < 80:
        tier = ConfidenceTier.MEDIUM
        rationale = (
            f"Medium confidence: {coverage_pct}% factor coverage; some "
            "sub-factors filled with neutral defaults."
        )
    else:
        tier = ConfidenceTier.HIGH
        rationale = (
            f"High confidence: {coverage_pct}% factor coverage, owner "
            "hours supplied, and the headline figure is not cap-bound."
        )

    return ConfidenceAssessment(
        tier=tier,
        coverage_pct=coverage_pct,
        rationale=rationale,
        cap_binding=cap_binding,
    )


class TransferabilityProfile(BaseModel):
    """The full v2 metadata bundle attached to OwnerDependencyResult."""

    decomposition: TransferabilityDecomposition
    buyer_profile: BuyerProfile
    gap: TransferabilityGap
    method_incidence: List[MethodIncidence]
    narrative_cascade: List[str]
    cascade_data: List[CascadeLineData] = Field(default_factory=list)
    blended_applied_pct: Decimal
    confidence: ConfidenceAssessment
    methodology_citations: List[MethodologyCitation] = Field(
        default_factory=lambda: list(METHODOLOGY_CITATIONS)
    )

    model_config = ConfigDict(use_enum_values=True)


def build_transferability_profile(
    factor_scores: dict[str, object],
    *,
    equity_value_mid: Optional[Decimal],
    headline_adjustment_pct: Decimal,
    raw_engine_adjustment_pct: Optional[Decimal] = None,
    owner_hours_per_week: Optional[int] = None,
    advisor_buyer_override: Optional[BuyerProfile] = None,
    eligible_methods: Optional[List[str]] = None,
) -> TransferabilityProfile:
    """Compose the full transferability profile in one pure pass."""
    decomposition = decompose_factors(factor_scores)
    buyer_profile = derive_buyer_profile(equity_value_mid, advisor_override=advisor_buyer_override)
    gap = compute_transferability_gap(
        decomposition,
        buyer_profile,
        owner_hours_per_week=owner_hours_per_week,
    )
    method_table = method_incidence_table(headline_adjustment_pct)
    cascade = build_narrative_cascade(
        decomposition,
        buyer_profile,
        gap,
        headline_adjustment_pct,
        raw_engine_adjustment_pct,
        eligible_methods,
    )
    blended_pct = blended_incidence(headline_adjustment_pct, eligible_methods)

    cap_binding = raw_engine_adjustment_pct is not None and Decimal(
        str(raw_engine_adjustment_pct)
    ) < Decimal(str(headline_adjustment_pct))
    confidence = derive_confidence_tier(
        decomposition,
        owner_hours_supplied=owner_hours_per_week is not None,
        cap_binding=cap_binding,
    )

    cascade_data = build_cascade_data(
        decomposition,
        buyer_profile,
        gap,
        headline_adjustment_pct,
        raw_engine_adjustment_pct,
        eligible_methods,
    )

    return TransferabilityProfile(
        decomposition=decomposition,
        buyer_profile=buyer_profile,
        gap=gap,
        method_incidence=method_table,
        narrative_cascade=cascade,
        cascade_data=cascade_data,
        blended_applied_pct=blended_pct,
        confidence=confidence,
        methodology_citations=list(METHODOLOGY_CITATIONS),
    )
