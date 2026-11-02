"""Sellability €-impact computation (BET-204 / A2 chunk 3).

Implements the §7 selection rule from
`docs/product/features/active-development/sellability-mvp.md`:

    1. Per-factor multiple-uplift simulation (close gap to "good" target).
    2. EV delta = current_ev * uplift_pct.
    3. Drop lifts where eur_impact < 5% of current_ev.
    4. High+medium confidence -> top_three_lifts (top 3 by EUR desc).
    5. Low confidence -> tertiary_lifts (no €-numbers, qualitative only).
    6. All-low / cold-cell -> all lifts to tertiary; controller renders
       the upsell empty state per spec §7.3.

Defensibility (spec §4A): score composition can drift; €-impact cannot.
The Delphi multiple is the only source of multiplier truth — passed in
as a parameter, never invented here. Cold-cell (multiple is None) is
handled explicitly: every lift returns eur_impact=None and confidence
demotes to 'low' — they all fall into tertiary.

Pure: same inputs -> same outputs. No I/O. No global state. The only
state is `FACTOR_UPLIFTS` below, which is a calibration constant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

# ---------------------------------------------------------------------
# Calibration — per-factor multiple-uplift heuristics
# ---------------------------------------------------------------------
#
# Each factor has:
#   - max_uplift_pct: the multiple uplift if the factor moves all the way
#       to "good" (e.g., +30% on the EV/EBITDA multiple). Calibrated against
#       SME M&A practitioner heuristics referenced in the founder's 100+
#       conversations Jan-Apr 2026. Conservative — easier to over-deliver.
#   - good_target: the factor value (0-100) at which we consider it "good
#       enough" — past this, no further lift is awarded.
#   - action_template: caregiver-tone action sentence per A0 voice baseline.
#
# Calibration rationale (locked for v1; revisit only with empirical data
# from >=10 attributed deals, same threshold as KEY_MAN_LENS_MAX_EFFECT):
#
#   owner_dependence       (0.30): widely cited 20-40% practitioner discount
#                                  for owner-led SMEs; closing 100% of the
#                                  gap is +30% multiple uplift, conservative.
#   customer_concentration (0.25): top-3 >70% routinely caps deal multiples
#                                  by ~20%; +25% headroom for the cleanest
#                                  diversification path.
#   revenue_quality        (0.20): SaaS-style recurring revenue commands
#                                  ~15-30% multiple premium; conservative end.
#   transferability        (0.20): mirrors owner_dependence ceiling but
#                                  smaller weight in the score itself.
#   financial_cleanliness  (0.15): externally-audited books de-risk DD,
#                                  worth ~10-20% on the final number.
#   growth_trend           (0.15): smallest because growth is already
#                                  reflected in the Delphi median multiple
#                                  for high-growth sectors.

FACTOR_UPLIFTS: dict[str, dict] = {
    "owner_dependence": {
        "max_uplift_pct": 0.30,
        "good_target": 80,
        "action_template": (
            "Reduce owner-dependence by delegating sales-lead and "
            "technical-lead roles within 12 months."
        ),
    },
    "customer_concentration": {
        "max_uplift_pct": 0.25,
        "good_target": 70,
        "action_template": (
            "Reduce top-3 customer concentration to under 40% of revenue."
        ),
    },
    "revenue_quality": {
        "max_uplift_pct": 0.20,
        "good_target": 80,
        "action_template": (
            "Convert one-off revenue to multi-year contracts; aim for "
            ">=60% contracted share."
        ),
    },
    "financial_cleanliness": {
        "max_uplift_pct": 0.15,
        "good_target": 90,
        "action_template": (
            "Move to externally-audited books and separate "
            "personal-from-business expenses."
        ),
    },
    "growth_trend": {
        "max_uplift_pct": 0.15,
        "good_target": 75,
        "action_template": (
            "Sustain double-digit revenue growth alongside healthy "
            "EBITDA margins."
        ),
    },
    "transferability": {
        "max_uplift_pct": 0.20,
        "good_target": 75,
        "action_template": (
            "Document key processes and reduce structural transferability "
            "risk (licences, brand, succession)."
        ),
    },
}

VALID_COUNTRY_BASES = ("native", "aggregate_clone", "aggregate")
CountryBasis = Literal["native", "aggregate_clone", "aggregate"]
LiftConfidence = Literal["high", "med", "low"]

# Selection-rule thresholds (spec §7.1 step 2).
MIN_LIFT_PCT_OF_EV = 0.05  # drop lifts below 5% of current EV
TOP_LIFTS_K = 3            # top-3 panel size
EUR_ROUNDING = 5_000       # round to nearest €5k (spec §7.1)


# ---------------------------------------------------------------------
# Inputs / outputs
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class SellabilityFactorInput:
    """One factor row from the score breakdown."""

    key: str
    value: float            # 0-100, higher = better
    weight: float           # 0-1, contribution weight
    contribution: float     # value * weight (informational; not used here)
    data_available: bool


@dataclass(frozen=True)
class SellabilityLift:
    """One lift entry — top-3 or tertiary."""

    factor: str
    action: str
    eur_impact: Optional[int]    # None on cold-cell or low-confidence path
    confidence: LiftConfidence
    uplift_pct: float            # 0-1, computed multiple uplift


@dataclass(frozen=True)
class SellabilityImpactResult:
    """Output of `compute_sellability_eur_impact`."""

    top_three_lifts: list[SellabilityLift] = field(default_factory=list)
    tertiary_lifts: list[SellabilityLift] = field(default_factory=list)
    # Defensive metadata for the audit log / debug.
    cold_cell: bool = False
    current_ev: Optional[float] = None


# ---------------------------------------------------------------------
# Confidence derivation
# ---------------------------------------------------------------------


def _factor_lift_confidence(
    factor: SellabilityFactorInput,
    country_basis: Optional[CountryBasis],
    has_owner_profile_data: bool,
    has_recent_financials: bool,
) -> LiftConfidence:
    """Derive per-factor lift confidence.

    Rules:
        - factor input missing -> 'low' (always)
        - cold cell (no Delphi multiple, country_basis=None) -> 'low' for all
        - country_basis 'native' AND owner-profile present AND recent
          financials -> 'high'
        - country_basis 'aggregate' -> at most 'med'
        - otherwise 'med'
    """
    if not factor.data_available:
        return "low"
    if country_basis is None:
        return "low"
    if country_basis == "aggregate":
        return "med"
    if country_basis == "native" and has_owner_profile_data and has_recent_financials:
        return "high"
    return "med"


# ---------------------------------------------------------------------
# Per-factor lift computation
# ---------------------------------------------------------------------


def _compute_factor_lift(
    factor: SellabilityFactorInput,
    delphi_multiple: Optional[float],
    current_ebitda: Optional[float],
    country_basis: Optional[CountryBasis],
    has_owner_profile_data: bool,
    has_recent_financials: bool,
) -> Optional[SellabilityLift]:
    """Compute a single factor's lift, or None if the factor is unknown.

    Returns None for unrecognised factor keys (defensive — protects
    against drift between TS scorer and Python uplift table).
    """
    cfg = FACTOR_UPLIFTS.get(factor.key)
    if cfg is None:
        return None

    confidence = _factor_lift_confidence(
        factor=factor,
        country_basis=country_basis,
        has_owner_profile_data=has_owner_profile_data,
        has_recent_financials=has_recent_financials,
    )

    # Gap: how far the factor is below the "good" target. Floor at 0
    # (already at-or-above target -> no lift).
    target = float(cfg["good_target"])
    gap = max(0.0, target - float(factor.value)) / 100.0

    # Uplift: closing the gap proportionally awards a fraction of the
    # max multiple uplift.
    max_uplift = float(cfg["max_uplift_pct"])
    uplift_pct = gap * max_uplift

    # EUR impact: only computable when we have a Delphi multiple AND a
    # current EBITDA. Cold cell -> None (lift falls to tertiary with
    # qualitative action text only, per spec §7.2).
    eur_impact: Optional[int]
    if (
        delphi_multiple is None
        or current_ebitda is None
        or delphi_multiple <= 0
        or current_ebitda <= 0
    ):
        eur_impact = None
    else:
        current_ev = float(current_ebitda) * float(delphi_multiple)
        eur_raw = current_ev * uplift_pct
        eur_impact = _round_to_nearest(eur_raw, EUR_ROUNDING)

    return SellabilityLift(
        factor=factor.key,
        action=str(cfg["action_template"]),
        eur_impact=eur_impact,
        confidence=confidence,
        uplift_pct=round(uplift_pct, 4),
    )


def _round_to_nearest(value: float, step: int) -> int:
    """Round to nearest multiple of `step`. Negative-safe."""
    if step <= 0:
        return int(round(value))
    return int(round(value / step) * step)


# ---------------------------------------------------------------------
# Top-level: compose the result
# ---------------------------------------------------------------------


def compute_sellability_eur_impact(
    factors: list[SellabilityFactorInput],
    delphi_multiple: Optional[float],
    current_ebitda: Optional[float],
    country_basis: Optional[CountryBasis],
    has_owner_profile_data: bool,
    has_recent_financials: bool,
) -> SellabilityImpactResult:
    """Top-level entry point.

    Args:
        factors: 6 factor breakdowns from the Sellability score result.
        delphi_multiple: EV/EBITDA multiple resolved by Titan via Delphi.
            None on cold cell (no Delphi row for entity NACE+country).
        current_ebitda: entity's current EBITDA in €. None when missing.
        country_basis: Delphi tier mapped to spec §7 enum, or None on cold cell.
        has_owner_profile_data: from Sellability score input.
        has_recent_financials: from Sellability score input (>=2y of TitanYearData).

    Returns:
        SellabilityImpactResult with top_three_lifts and tertiary_lifts
        already split per spec §7.1 / §7.2.
    """
    cold_cell = delphi_multiple is None or country_basis is None
    current_ev: Optional[float] = None
    if delphi_multiple is not None and current_ebitda is not None:
        if delphi_multiple > 0 and current_ebitda > 0:
            current_ev = float(current_ebitda) * float(delphi_multiple)

    lifts: list[SellabilityLift] = []
    for f in factors:
        lift = _compute_factor_lift(
            factor=f,
            delphi_multiple=delphi_multiple,
            current_ebitda=current_ebitda,
            country_basis=country_basis,
            has_owner_profile_data=has_owner_profile_data,
            has_recent_financials=has_recent_financials,
        )
        if lift is None:
            continue
        # Spec §7.1 step 2: drop lifts that are too small to be actionable.
        # Only enforced when we have a current_ev to compare against; cold
        # cells skip this filter (they all have eur_impact=None already).
        if current_ev is not None and lift.eur_impact is not None:
            min_eur = current_ev * MIN_LIFT_PCT_OF_EV
            if lift.eur_impact < min_eur:
                # Not actionable enough — drop entirely. Goes to neither
                # panel. The factor's contribution still appears in the
                # score breakdown panel; we just don't claim a € lift.
                continue
        # Skip zero-uplift factors (factor already at-or-above good target).
        if lift.uplift_pct <= 0:
            continue
        lifts.append(lift)

    # Selection rule (spec §7.1 step 3 + §7.2):
    #   - high + med confidence -> ranked, top 3 -> top_three_lifts
    #   - low confidence -> all -> tertiary_lifts (no €-numbers shown UI-side,
    #     but eur_impact may still be populated for audit; UI hides on render)
    high_med = [l for l in lifts if l.confidence in ("high", "med")]
    low = [l for l in lifts if l.confidence == "low"]

    # Stable sort: primary key is eur_impact desc, secondary key is the
    # factor name asc. Without the secondary key two lifts with identical
    # eur_impact (common when both round to the same €5k bucket) would
    # flicker between renders. Determinism contract relies on stability —
    # the persisted top_three_lifts JSON must replay identically.
    high_med_sorted = sorted(
        high_med,
        key=lambda l: (
            -(l.eur_impact if l.eur_impact is not None else 0),
            l.factor,
        ),
    )
    top_three = high_med_sorted[:TOP_LIFTS_K]

    # Anything in high_med beyond top-3 also lands in tertiary (spec §7.2:
    # tertiary holds "low confidence + overflow"). This keeps the page
    # populated when there are more than 3 actionable factors.
    overflow = high_med_sorted[TOP_LIFTS_K:]

    tertiary = list(low) + list(overflow)
    # Stable secondary sort within tertiary: by uplift_pct desc, then by
    # factor key for determinism.
    tertiary.sort(
        key=lambda l: (-l.uplift_pct, l.factor),
    )

    return SellabilityImpactResult(
        top_three_lifts=top_three,
        tertiary_lifts=tertiary,
        cold_cell=cold_cell,
        current_ev=current_ev,
    )
