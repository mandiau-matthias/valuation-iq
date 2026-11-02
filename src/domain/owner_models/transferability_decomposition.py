"""Five-factor decomposition for transferability v2."""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


SUB_FACTOR_GROUPS: Dict[str, Tuple[str, ...]] = {
    "planning_continuity": (
        "succession_planning",
        "business_scalability",
    ),
    "relationship_transferability": (
        "client_concentration",
        "sales_relationship",
        "contract_transferability",
    ),
    "operational_independence": (
        "team_capability",
        "decision_making",
        "operational_knowledge",
    ),
    "knowledge_codification": (
        "process_documentation",
        "technical_expertise",
    ),
    "brand_independence": (
        "brand_reputation",
        "industry_network",
    ),
}


SUB_FACTOR_LABELS_EN: Dict[str, str] = {
    "planning_continuity": "Planning & continuity",
    "relationship_transferability": "Relationship transferability",
    "operational_independence": "Operational independence",
    "knowledge_codification": "Knowledge codification",
    "brand_independence": "Brand independence",
}


def _band_for_score(score: Decimal | float | int) -> str:
    s = float(score)
    if s >= 75:
        return "good"
    if s >= 55:
        return "neutral"
    if s >= 35:
        return "caution"
    return "warn"


class SubFactorScore(BaseModel):
    """One of the five advisor-visible sub-factors."""

    key: str
    label: str
    score: Decimal = Field(ge=0, le=100)
    band: str
    contributing_factors: List[str] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)


class TransferabilityDecomposition(BaseModel):
    """Five-factor view plus analytical helpers."""

    sub_factors: List[SubFactorScore]
    weakest_key: Optional[str] = None
    weakest_score: Optional[Decimal] = None
    strongest_key: Optional[str] = None
    strongest_score: Optional[Decimal] = None

    model_config = ConfigDict(use_enum_values=True)


def decompose_factors(factor_scores: dict[str, object]) -> TransferabilityDecomposition:
    """Group the 12 raw factor scores into five advisor-visible sub-factors."""
    sub_factors: List[SubFactorScore] = []
    for key, members in SUB_FACTOR_GROUPS.items():
        present = [factor_scores[m] for m in members if m in factor_scores]
        if not present:
            score = Decimal("50")
            members_present: List[str] = []
        else:
            total = sum(Decimal(str(s)) for s in present)
            score = (total / Decimal(len(present))).quantize(Decimal("0.1"))
            members_present = [m for m in members if m in factor_scores]
        sub_factors.append(
            SubFactorScore(
                key=key,
                label=SUB_FACTOR_LABELS_EN[key],
                score=score,
                band=_band_for_score(score),
                contributing_factors=members_present,
            )
        )

    scored = [sf for sf in sub_factors if sf.contributing_factors]
    if scored:
        weakest = min(scored, key=lambda sf: sf.score)
        strongest = max(scored, key=lambda sf: sf.score)
        weakest_key, weakest_score = weakest.key, weakest.score
        strongest_key, strongest_score = strongest.key, strongest.score
    else:
        weakest_key = strongest_key = None
        weakest_score = strongest_score = None

    return TransferabilityDecomposition(
        sub_factors=sub_factors,
        weakest_key=weakest_key,
        weakest_score=weakest_score,
        strongest_key=strongest_key,
        strongest_score=strongest_score,
    )
