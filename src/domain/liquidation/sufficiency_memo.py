"""Sufficiency Memo — the lawyer's first question, answered.

Why this module exists
----------------------
Every restructuring lawyer asking about a distressed estate opens with
the same question: **"Can we pay each creditor tier in full?"** The
answer drives every subsequent decision — secured-creditor settlement
strategy, employee severance funding, fiscus negotiation posture,
shareholder-loan write-down acceptance.

The priority cascade already produces per-tier `recovery_amount` and
`shortfall`. This module distills that into a yes/no/partial verdict
per tier + a single executive summary line + a "deepest covered tier"
cutoff. That's exactly the artifact a Boek-XX-WER curator or
Faillissementswet trustee writes on the first page of their report
to creditors.

Output contract
---------------
A typed `SufficiencyMemo` carrying:
- One `TierVerdict` per cascade tier (PAID_IN_FULL / PARTIAL /
  UNCOVERED).
- The deepest tier that was paid in full (the "coverage cutoff").
- Headline coverage ratio = total_recovered / total_claims.
- Headline rationale auditor-readable.

References
----------
- Boek XX WER §XX.99 — boedelschulden first.
- Faillissementswet Art. 26 — pari-passu within tier.
- AICPA SSVS No. 1 §47 — sufficiency analysis as part of the
  Statement of Affairs.
- KPMG (2022) "Restructuring Sufficiency Analysis Memo Template."
- EY (2023) "Estate Coverage Analysis — Standard Format."
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from .priority_cascade import CascadeTier, CascadeTierCode, PriorityCascade


SUFFICIENCY_MEMO_SOURCES: tuple[str, ...] = (
    "Boek XX WER §XX.99 + Art. XX.155 — distribution rules (BE)",
    "Faillissementswet Art. 26 — pari-passu rule (NL)",
    "AICPA SSVS No. 1 §47 — sufficiency analysis",
    "KPMG (2022) Restructuring Sufficiency Analysis Memo Template",
    "EY (2023) Estate Coverage Analysis — Standard Format",
)


class CoverageVerdict(str, Enum):
    """Per-tier coverage verdict — stable codes, surfaced to UI."""

    PAID_IN_FULL = "paid_in_full"  # recovery == claim (within rounding)
    PARTIAL = "partial"  # recovery > 0 but < claim
    UNCOVERED = "uncovered"  # recovery == 0 (estate exhausted before this tier)


@dataclass(frozen=True)
class TierVerdict:
    """One row in the sufficiency memo."""

    code: str
    label: str
    statutory_anchor: str
    claim_amount: Decimal
    recovery_amount: Decimal
    shortfall: Decimal
    coverage_pct: Decimal  # 0..1
    verdict: CoverageVerdict
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "statutory_anchor": self.statutory_anchor,
            "claim_amount": float(self.claim_amount),
            "recovery_amount": float(self.recovery_amount),
            "shortfall": float(self.shortfall),
            "coverage_pct": float(self.coverage_pct),
            "verdict": self.verdict.value,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class SufficiencyMemo:
    """Executive verdict on the estate's ability to pay each tier."""

    scenario: str  # "orderly" | "forced"
    jurisdiction: str  # "BE" | "NL"
    verdicts: tuple[TierVerdict, ...]
    deepest_tier_paid_in_full: Optional[CascadeTierCode]
    deepest_tier_label: Optional[str]
    headline_coverage_ratio: Decimal  # total_recovered / total_claims
    estate_exhausted_at_tier: Optional[CascadeTierCode]
    rationale: str
    sources: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "jurisdiction": self.jurisdiction,
            "verdicts": [v.to_dict() for v in self.verdicts],
            "deepest_tier_paid_in_full": (
                self.deepest_tier_paid_in_full.value
                if self.deepest_tier_paid_in_full is not None
                else None
            ),
            "deepest_tier_label": self.deepest_tier_label,
            "headline_coverage_ratio": float(self.headline_coverage_ratio),
            "estate_exhausted_at_tier": (
                self.estate_exhausted_at_tier.value
                if self.estate_exhausted_at_tier is not None
                else None
            ),
            "rationale": self.rationale,
            "sources": list(self.sources),
        }


_FULL_PAYMENT_TOLERANCE: Decimal = Decimal("0.01")  # cumulative-decimal noise


def _verdict_for(tier: CascadeTier) -> CoverageVerdict:
    if tier.claim_amount <= 0:
        # No claim in this tier → trivially paid (vacuous case).
        return CoverageVerdict.PAID_IN_FULL
    if tier.recovery_amount <= 0:
        return CoverageVerdict.UNCOVERED
    if abs(tier.claim_amount - tier.recovery_amount) <= _FULL_PAYMENT_TOLERANCE:
        return CoverageVerdict.PAID_IN_FULL
    return CoverageVerdict.PARTIAL


def _rationale_for(verdict: CoverageVerdict, tier: CascadeTier) -> str:
    pct = float(tier.recovery_rate * 100)
    if verdict is CoverageVerdict.PAID_IN_FULL:
        if tier.claim_amount <= 0:
            return "Geen vorderingen in deze tranche — vacuously gedekt."
        return f"Volledig voldaan: 100% dekking ({tier.statutory_anchor})."
    if verdict is CoverageVerdict.PARTIAL:
        return (
            f"Slechts {pct:.1f}% gedekt — boedel uitgeput. "
            f"Tekort €{float(tier.shortfall):,.0f} ({tier.statutory_anchor})."
        )
    return (
        f"Niet gedekt — boedel volledig uitgeput vóór deze tranche. "
        f"Tekort €{float(tier.shortfall):,.0f} ({tier.statutory_anchor})."
    )


def build_sufficiency_memo(
    *,
    cascade: PriorityCascade,
    scenario: str,  # "orderly" | "forced"
) -> SufficiencyMemo:
    """Distill a cascade into the sufficiency memo.

    The math is a thin reduction over `cascade.tiers`; this module's
    value is the *framing* — surfacing the verdict, the cutoff, and
    the headline coverage ratio in the format a curator/trustee uses.
    """
    verdicts: List[TierVerdict] = []
    deepest_in_full: Optional[CascadeTierCode] = None
    exhausted_at: Optional[CascadeTierCode] = None

    for tier in cascade.tiers:
        v = _verdict_for(tier)
        verdicts.append(
            TierVerdict(
                code=tier.code.value,
                label=tier.label,
                statutory_anchor=tier.statutory_anchor,
                claim_amount=tier.claim_amount,
                recovery_amount=tier.recovery_amount,
                shortfall=tier.shortfall,
                coverage_pct=tier.recovery_rate,
                verdict=v,
                rationale=_rationale_for(v, tier),
            )
        )
        if v is CoverageVerdict.PAID_IN_FULL and tier.claim_amount > 0:
            deepest_in_full = tier.code
        if v is CoverageVerdict.UNCOVERED and exhausted_at is None and tier.claim_amount > 0:
            exhausted_at = tier.code

    deepest_label: Optional[str] = None
    if deepest_in_full is not None:
        deepest_label = next(
            (v.label for v in verdicts if v.code == deepest_in_full.value), None
        )

    if cascade.total_claims > 0:
        coverage_ratio = (cascade.total_recovered / cascade.total_claims).quantize(
            Decimal("0.0001")
        )
    else:
        coverage_ratio = Decimal("1.0000")

    if exhausted_at is None:
        rationale = (
            f"De boedel dekt alle aangemelde vorderingen volledig "
            f"(coverage {float(coverage_ratio) * 100:.1f}%). "
            f"Aandeelhouders ontvangen residueel: "
            f"€{float(cascade.equity_to_shareholders):,.0f}."
        )
    elif deepest_in_full is None:
        rationale = (
            "De boedel kan zelfs de eerste tranche niet voldoen. "
            "Onmiddellijk overleg met preferentiële schuldeisers + "
            "curator vereist."
        )
    else:
        rationale = (
            f"De boedel dekt vorderingen tot en met '{deepest_label}'. "
            f"Vanaf '{exhausted_at.value}' loopt de uitkering vast op "
            f"{float(verdicts[len(verdicts) - 1 if exhausted_at == verdicts[-1].code else next(i for i, v in enumerate(verdicts) if v.code == exhausted_at.value)].coverage_pct) * 100:.1f}% "
            "of minder. Lagere tranches blijven onbetaald."
        )

    return SufficiencyMemo(
        scenario=scenario,
        jurisdiction=cascade.jurisdiction.value,
        verdicts=tuple(verdicts),
        deepest_tier_paid_in_full=deepest_in_full,
        deepest_tier_label=deepest_label,
        headline_coverage_ratio=coverage_ratio,
        estate_exhausted_at_tier=exhausted_at,
        rationale=rationale,
        sources=SUFFICIENCY_MEMO_SOURCES,
    )


__all__ = [
    "SUFFICIENCY_MEMO_SOURCES",
    "CoverageVerdict",
    "SufficiencyMemo",
    "TierVerdict",
    "build_sufficiency_memo",
]
