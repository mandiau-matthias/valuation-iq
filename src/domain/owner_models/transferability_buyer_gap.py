"""Buyer-profile and owner-vs-buyer gap logic for transferability v2."""

from decimal import Decimal
from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from src.domain.owner_models.transferability_citations import EU_SME_SEGMENT_LABELS
from src.domain.owner_models.transferability_decomposition import TransferabilityDecomposition


class BuyerArchetype(str, Enum):
    """Likely-buyer archetypes for SMB / lower-mid-market deals."""

    INDIVIDUAL_OPERATOR = "individual_operator"
    SEARCH_FUND = "search_fund"
    PE_ADD_ON = "pe_add_on"
    STRATEGIC = "strategic"
    FAMILY_OFFICE = "family_office"


_BUYER_PROFILE_BANDS: Tuple[Tuple[Decimal, Decimal, BuyerArchetype, int, int], ...] = (
    (Decimal("0"), Decimal("500000"), BuyerArchetype.INDIVIDUAL_OPERATOR, 40, 30),
    (Decimal("500000"), Decimal("2000000"), BuyerArchetype.SEARCH_FUND, 50, 50),
    (Decimal("2000000"), Decimal("10000000"), BuyerArchetype.PE_ADD_ON, 30, 80),
    (Decimal("10000000"), Decimal("99999999999"), BuyerArchetype.STRATEGIC, 15, 90),
)


class BuyerProfile(BaseModel):
    """The buyer the discount is being defended against."""

    archetype: BuyerArchetype
    expected_hours_per_week: int = Field(ge=0, le=120)
    expected_skill_match: int = Field(ge=0, le=100)
    is_advisor_override: bool = False
    rationale: str
    eu_sme_segment: Optional[str] = Field(
        default=None,
        description=(
            "Formal EU Recommendation 2003/361/EC SME segment label "
            "(Micro / Small / Medium) keyed off the deal-size band."
        ),
    )

    model_config = ConfigDict(use_enum_values=True)


def derive_buyer_profile(
    equity_value_mid: Optional[Decimal],
    *,
    advisor_override: Optional[BuyerProfile] = None,
) -> BuyerProfile:
    """Pick a buyer archetype from deal size, unless an advisor override exists."""
    if advisor_override is not None:
        return advisor_override

    if equity_value_mid is None or equity_value_mid <= 0:
        return BuyerProfile(
            archetype=BuyerArchetype.SEARCH_FUND,
            expected_hours_per_week=50,
            expected_skill_match=50,
            is_advisor_override=False,
            rationale=(
                "Deal size unavailable; defaulting to a search-fund buyer "
                "(50 hrs/week, mid sector skill) as the median SMB assumption "
                "per Pepperdine PCMI."
            ),
            eu_sme_segment=EU_SME_SEGMENT_LABELS["search_fund"],
        )

    for lo, hi, archetype, hours, skill in _BUYER_PROFILE_BANDS:
        if lo <= equity_value_mid < hi:
            return BuyerProfile(
                archetype=archetype,
                expected_hours_per_week=hours,
                expected_skill_match=skill,
                is_advisor_override=False,
                rationale=_buyer_rationale(archetype, equity_value_mid),
                eu_sme_segment=EU_SME_SEGMENT_LABELS.get(archetype.value),
            )

    return BuyerProfile(
        archetype=BuyerArchetype.STRATEGIC,
        expected_hours_per_week=15,
        expected_skill_match=90,
        is_advisor_override=False,
        rationale=_buyer_rationale(BuyerArchetype.STRATEGIC, equity_value_mid),
        eu_sme_segment=EU_SME_SEGMENT_LABELS.get(BuyerArchetype.STRATEGIC.value),
    )


def _buyer_rationale(archetype: BuyerArchetype, equity_value_mid: Decimal) -> str:
    """One-line, advisor-readable justification for the archetype pick."""
    eur = f"€{int(equity_value_mid):,}".replace(",", ".")
    if archetype is BuyerArchetype.INDIVIDUAL_OPERATOR:
        return (
            f"At {eur} mid equity, the realistic buyer pool is individual "
            "operators buying themselves an owner-operator role (40 hrs/wk, "
            "limited sector skill)."
        )
    if archetype is BuyerArchetype.SEARCH_FUND:
        return (
            f"At {eur} mid equity, the realistic buyer pool is search-fund "
            "principals - first-time operators with high effort but limited "
            "sector depth (50 hrs/wk, mid skill match)."
        )
    if archetype is BuyerArchetype.PE_ADD_ON:
        return (
            f"At {eur} mid equity, the realistic buyer is a PE add-on with "
            "operating infrastructure already in place (30 hrs/wk effective, "
            "high skill match via portfolio playbooks)."
        )
    if archetype is BuyerArchetype.STRATEGIC:
        return (
            f"At {eur} mid equity, the realistic buyer is a strategic "
            "acquirer slotting the asset onto an existing platform "
            "(15 hrs/wk effective, very high skill match)."
        )
    return "Family office assumption applied; check with advisor."


class GapSeverity(str, Enum):
    MINIMAL = "minimal"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"


class TransferabilityGap(BaseModel):
    """Owner-vs-buyer asymmetry, the load-bearing discount input."""

    owner_hours_per_week: Optional[int] = Field(default=None, ge=0, le=120)
    buyer_hours_per_week: int = Field(ge=0, le=120)
    hours_gap: int = Field(ge=0, le=120)

    owner_skill_score: Decimal = Field(ge=0, le=100)
    buyer_skill_score: Decimal = Field(ge=0, le=100)
    skill_gap: Decimal = Field(ge=0, le=100)

    severity: GapSeverity
    severity_tier: int = Field(ge=1, le=4, description="1=minimal, 4=extreme")
    raw_discount_pct: Decimal = Field(le=0, ge=Decimal("-0.40"))
    gap_summary: str

    model_config = ConfigDict(use_enum_values=True)


_SEVERITY_TIERS: dict[GapSeverity, int] = {
    GapSeverity.MINIMAL: 1,
    GapSeverity.MODERATE: 2,
    GapSeverity.SEVERE: 3,
    GapSeverity.EXTREME: 4,
}


def _severity_for_gap(hours_gap: int, skill_gap: Decimal) -> GapSeverity:
    """Map gap magnitudes to a four-tier severity."""
    if hours_gap >= 35 and skill_gap >= Decimal("50"):
        return GapSeverity.EXTREME
    if hours_gap >= 25 or skill_gap >= Decimal("40"):
        return GapSeverity.SEVERE
    if hours_gap >= 10 or skill_gap >= Decimal("20"):
        return GapSeverity.MODERATE
    return GapSeverity.MINIMAL


def _raw_discount_for_severity(severity: GapSeverity) -> Decimal:
    """Map severity to a raw percent discount before caps and incidence."""
    if severity is GapSeverity.MINIMAL:
        return Decimal("-0.05")
    if severity is GapSeverity.MODERATE:
        return Decimal("-0.12")
    if severity is GapSeverity.SEVERE:
        return Decimal("-0.22")
    return Decimal("-0.32")


def compute_transferability_gap(
    decomposition: TransferabilityDecomposition,
    buyer_profile: BuyerProfile,
    *,
    owner_hours_per_week: Optional[int] = None,
    owner_skill_score_override: Optional[Decimal] = None,
) -> TransferabilityGap:
    """Compute the owner-vs-buyer gap from decomposition and buyer profile."""
    knowledge = next(
        (sf for sf in decomposition.sub_factors if sf.key == "knowledge_codification"),
        None,
    )
    if owner_skill_score_override is not None:
        owner_skill = owner_skill_score_override
    elif knowledge is not None:
        owner_skill = Decimal("100") - knowledge.score
    else:
        owner_skill = Decimal("60")

    if owner_hours_per_week is None:
        owner_hours_eff = 60
    else:
        owner_hours_eff = max(0, min(120, int(owner_hours_per_week)))

    hours_gap = max(0, owner_hours_eff - buyer_profile.expected_hours_per_week)
    skill_gap = max(
        Decimal("0"),
        owner_skill - Decimal(str(buyer_profile.expected_skill_match)),
    )

    severity = _severity_for_gap(hours_gap, skill_gap)
    raw_discount = _raw_discount_for_severity(severity)

    summary = (
        f"Owner runs ~{owner_hours_eff} hrs/wk vs. buyer assumption "
        f"~{buyer_profile.expected_hours_per_week} hrs/wk "
        f"(gap: {hours_gap} hrs); skill gap {skill_gap:.0f}/100. "
        f"Severity: {severity.value}; raw discount {float(raw_discount * 100):+.0f}%."
    )

    return TransferabilityGap(
        owner_hours_per_week=owner_hours_per_week,
        buyer_hours_per_week=buyer_profile.expected_hours_per_week,
        hours_gap=hours_gap,
        owner_skill_score=owner_skill,
        buyer_skill_score=Decimal(str(buyer_profile.expected_skill_match)),
        skill_gap=skill_gap,
        severity=severity,
        severity_tier=_SEVERITY_TIERS[severity],
        raw_discount_pct=raw_discount,
        gap_summary=summary,
    )
