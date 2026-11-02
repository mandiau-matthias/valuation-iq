"""Founder Pedigree Multiplier — separates team strength from execution risk.

Bill Payne's Scorecard already has a "management strength" factor and Berkus
counts a "quality management team" milestone — but both blend it into a
single 0–100 slider that conflates *execution-risk-removed-so-far* with
*who the team is on paper*.

Strebulaev (Stanford GSB, "Venture Mindset" 2024) shows the second axis is
real and unforgiving: founder-mafia networks (PayPal mafia, Adyen / Showpad
/ Collibra alumni in Benelux), prior-exit founders, and deep domain experts
command a **1.3×–1.8× peer premium** on pre-seed pre-money valuations
*independent* of how much execution risk they have removed. Solo founders
trade at a discount in the same dataset.

This module computes that pedigree multiplier as a **multiplicative overlay
on the blended pre-money** — applied after :func:`synthesis.blend` produces
its weighted average. The signal is intentionally additive over a small set
of binary qualifications (each with a stated delta) rather than another
free-form 0-100 slider, so the founder cannot self-rate themselves into a
premium without picking a specific, defensible qualification.

All deltas are conservative midpoints calibrated against published Benelux
seed-round data (Atomico SoEU 2024, Dealroom Benelux 2024). The clamp
range ``[0.70, 1.80]`` keeps the multiplier inside the empirical envelope
even if every single delta is checked.

**Evidence gate (April 2026 review).**  A positive pedigree claim is only
applied when the founder also supplies an evidence string for that claim
(LinkedIn URL, KBO incorporation reference, named employer + tenure, etc.).
The negative ``solo_founder`` delta is *never* gated — it is a
self-disclosure that costs the founder, so we trust it on its face.  The
gate is implemented here, not in the schema, so the audit trail can
record exactly which claims were *zeroed* due to missing evidence — that
record drives the defensibility-score's "pedigree evidence" sub-score.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, FrozenSet, List, Mapping

from .money import ONE, ZERO, clamp, q_rate, sum_decimals

if TYPE_CHECKING:
    from .schemas import FounderPedigreeInputs

#: Multiplicative overlay applied to the blended pre-money. ``1.0`` means
#: no pedigree adjustment — the team trades at peer.
PEDIGREE_BASE: Decimal = ONE

#: Empirical floor — even a solo founder with no domain experience and no
#: technical cofounder doesn't trade below 70% of peer in funded Benelux
#: pre-seeds. Below this we'd be modelling unfundable companies, not
#: applying a discount.
PEDIGREE_FLOOR: Decimal = Decimal("0.70")

#: Empirical ceiling — repeat-exit founders with top-mafia + technical
#: cofounder + domain expertise *do* close above 1.8×, but rarely; capping
#: here keeps a Studio user from compounding deltas into a 2.5× premium
#: that won't survive a real diligence call.
PEDIGREE_CEILING: Decimal = Decimal("1.80")


#: Per-qualification multiplier deltas. Sum the active deltas and add to
#: :data:`PEDIGREE_BASE` to derive the raw multiplier (then clamp).
#:
#: Calibration sources:
#:   * +0.30 prior exit — Strebulaev "Venture Mindset" Ch. 6 + Atomico SoEU
#:     2024 seed-round dataset (repeat-exit pre-money median 1.3× peer)
#:   * +0.20 top mafia — Dealroom Benelux 2024 (Adyen / Collibra alumni
#:     command a clear premium, but smaller than a clean exit)
#:   * +0.15 10-yr domain — INSEAD 2023 ("Founder-market fit") + LBS 2024
#:   * +0.10 second-time founder (no exit) — Atomico SoEU 2024
#:   * +0.10 technical cofounder — Bessemer "Anti-Portfolio" notes; pre-seed
#:     SaaS without one closes 12% below peer on average
#:   * −0.20 solo founder — Atomico SoEU 2024 (solo-founder pre-seed median
#:     ~80% of co-founded peer; symmetric with the technical-cofounder lift)
PEDIGREE_DELTAS: Mapping[str, Decimal] = MappingProxyType(
    {
        "prior_exit": Decimal("0.30"),
        "top_unicorn_alumnus": Decimal("0.20"),
        "domain_expert_10y": Decimal("0.15"),
        "second_time_founder": Decimal("0.10"),
        "has_technical_cofounder": Decimal("0.10"),
        "solo_founder": Decimal("-0.20"),
    }
)

PEDIGREE_LABELS: Mapping[str, str] = MappingProxyType(
    {
        "prior_exit": "Prior venture-backed exit (>=€10M)",
        "top_unicorn_alumnus": "Top-tier scaleup alumnus (Adyen / Collibra / Showpad / Bol / Mollie etc.)",
        "domain_expert_10y": "10+ years operating experience in target industry",
        "second_time_founder": "Second-time founder (prior 2+ year venture)",
        "has_technical_cofounder": "Full-time technical cofounder",
        "solo_founder": "Solo founder (no cofounders)",
    }
)

#: Claims for which evidence is REQUIRED before the positive delta is
#: applied.  Effectively the set of positive deltas — the negative
#: ``solo_founder`` claim is excluded because it costs the founder.
EVIDENCE_REQUIRED_CLAIMS: FrozenSet[str] = frozenset(
    {
        "prior_exit",
        "top_unicorn_alumnus",
        "domain_expert_10y",
        "second_time_founder",
        "has_technical_cofounder",
    }
)


@dataclass(frozen=True)
class PedigreeFactor:
    """One row in the pedigree breakdown — what the founder picked and what
    that picked cost or earned them."""

    key: str
    label: str
    applied: bool
    """``True`` ⇒ the founder claimed this qualification."""

    delta: Decimal
    """The headline delta the report shows next to the row.  Equals the
    value in :data:`PEDIGREE_DELTAS` for the matching key, regardless of
    whether the engine ultimately *counted* it (see :attr:`effective_delta`)."""

    effective_delta: Decimal
    """The delta actually summed into the multiplier.  Equals
    :attr:`delta` when the claim is applied AND (for positive claims)
    evidence is present.  Zero otherwise.  This is the value that drives
    the multiplier — :attr:`delta` is purely cosmetic on the report."""

    evidence_required: bool
    """``True`` for positive claims that require a non-empty evidence
    string before the delta is counted.  ``False`` for ``solo_founder``."""

    evidence_provided: bool
    """``True`` when the corresponding key in
    :attr:`FounderPedigreeInputs.pedigree_evidence` carries a non-empty
    string.  Always ``True`` for unclaimed factors and for negative
    claims (no evidence required ⇒ no missing evidence)."""

    evidence_text: str = ""
    """The trimmed evidence string the founder supplied (empty when none)."""


@dataclass(frozen=True)
class FounderPedigreeOutput:
    """Pedigree multiplier + per-qualification breakdown.

    The synthesis blender consumes :attr:`multiplier` and surfaces
    :attr:`breakdown` in the report so the founder can see exactly which
    qualifications drove the lift / penalty.
    """

    multiplier: Decimal
    raw_multiplier: Decimal
    """Pre-clamp sum (``base + Σ effective deltas``). Surfaced separately
    so a founder who maxes out every qualification can see the empirical
    ceiling kicking in instead of silently losing the over-shoot."""

    clamp_floor: Decimal
    clamp_ceiling: Decimal
    breakdown: List[PedigreeFactor]

    positive_claims_count: int
    """Number of positive (non-``solo_founder``) claims the founder
    flagged.  Drives the defensibility score's pedigree sub-score."""

    evidenced_claims_count: int
    """Number of those positive claims that were also evidenced.  Always
    ``<= positive_claims_count``."""


def _evidence_text_for(inputs: "FounderPedigreeInputs", key: str) -> str:
    """Return the trimmed evidence string for ``key`` (empty when missing)."""
    raw = (inputs.pedigree_evidence or {}).get(key, "")
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def calculate_founder_pedigree(
    inputs: "FounderPedigreeInputs",
) -> FounderPedigreeOutput:
    """Compute the founder pedigree multiplier from a set of binary flags.

    Returns ``multiplier == 1.0`` when no flags are set so the synthesis
    blender treats the absence of pedigree data as a no-op (rather than a
    penalty).  Positive deltas are silently zeroed when the corresponding
    evidence string is missing — the audit trail records exactly which
    claims were dropped so the report can render the partial pedigree
    + the missing-evidence warning side by side.

    The multiplier is clamped into ``[PEDIGREE_FLOOR, PEDIGREE_CEILING]``
    to keep the overlay within the empirical envelope.
    """
    breakdown: List[PedigreeFactor] = []
    deltas_active: List[Decimal] = []
    positive_claims = 0
    evidenced_claims = 0

    for key, delta in PEDIGREE_DELTAS.items():
        applied = bool(getattr(inputs, key))
        evidence_required = key in EVIDENCE_REQUIRED_CLAIMS
        evidence_text = _evidence_text_for(inputs, key) if applied else ""
        evidence_provided = bool(evidence_text) if evidence_required else True

        if applied and evidence_required:
            positive_claims += 1
            if evidence_provided:
                evidenced_claims += 1

        # Effective delta: only counts when the claim is applied AND
        # (for positive claims) evidence is present.  Negative claims
        # (solo_founder) bypass the evidence gate.
        if applied and (not evidence_required or evidence_provided):
            effective_delta = delta
            deltas_active.append(delta)
        else:
            effective_delta = ZERO

        breakdown.append(
            PedigreeFactor(
                key=key,
                label=PEDIGREE_LABELS[key],
                applied=applied,
                delta=delta,
                effective_delta=effective_delta,
                evidence_required=evidence_required,
                evidence_provided=evidence_provided,
                evidence_text=evidence_text,
            )
        )

    raw = PEDIGREE_BASE + sum_decimals(deltas_active)
    multiplier = q_rate(clamp(raw, low=PEDIGREE_FLOOR, high=PEDIGREE_CEILING))

    return FounderPedigreeOutput(
        multiplier=multiplier,
        raw_multiplier=q_rate(raw),
        clamp_floor=PEDIGREE_FLOOR,
        clamp_ceiling=PEDIGREE_CEILING,
        breakdown=breakdown,
        positive_claims_count=positive_claims,
        evidenced_claims_count=evidenced_claims,
    )


def pedigree_payload(output: FounderPedigreeOutput) -> dict:
    """Serialize a :class:`FounderPedigreeOutput` for the engine ↔ report
    JSON boundary. Mirrors the convention in :mod:`.payloads` (Decimals
    converted to floats here, never inside the engine)."""
    from .money import safe_float

    return {
        "multiplier": safe_float(output.multiplier),
        "raw_multiplier": safe_float(output.raw_multiplier),
        "clamp_floor": safe_float(output.clamp_floor),
        "clamp_ceiling": safe_float(output.clamp_ceiling),
        "positive_claims_count": output.positive_claims_count,
        "evidenced_claims_count": output.evidenced_claims_count,
        "breakdown": [
            {
                "key": f.key,
                "label": f.label,
                "applied": f.applied,
                "delta": safe_float(f.delta),
                "effective_delta": safe_float(f.effective_delta),
                "evidence_required": f.evidence_required,
                "evidence_provided": f.evidence_provided,
                "evidence_text": f.evidence_text,
            }
            for f in output.breakdown
        ],
    }


__all__ = [
    "EVIDENCE_REQUIRED_CLAIMS",
    "FounderPedigreeOutput",
    "PEDIGREE_BASE",
    "PEDIGREE_CEILING",
    "PEDIGREE_DELTAS",
    "PEDIGREE_FLOOR",
    "PEDIGREE_LABELS",
    "PedigreeFactor",
    "calculate_founder_pedigree",
    "pedigree_payload",
]


# Sanity check on the calibration: every active delta below ceiling, the
# floor catches solo-founder + nothing-else (1.0 - 0.2 = 0.8 > 0.7 floor),
# and the ceiling catches the everything-positive case
# (1.0 + 0.3 + 0.2 + 0.15 + 0.10 + 0.10 = 1.85 > 1.80 ceiling).
_ = ZERO
