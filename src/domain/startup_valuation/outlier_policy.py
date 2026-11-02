"""Outlier policy for the startup valuation blend.

When one leg lands far outside the median of the other contributing legs
the weighted blend is no longer a credible mid-point — it becomes a
weighted average of two unrelated answers.  In Benelux pre-seed practice
this almost always shows up on the **VC Method** when the founder anchors
on an aggressive Y5 revenue + a high exit multiple.  A €28M VC backsolve
sitting next to a €1.95M Berkus and a €1.84M Scorecard pulls the 3-leg
"founder triangulation" up to €10M+ even when the qualitative methods
unanimously price the company at €2M.

This module implements a transparent **Tukey-style outlier policy**:

1. Compute the median and inter-quartile range of the contributing legs.
2. Flag any leg whose pre-money sits more than ``k * IQR`` from the
   median (default ``k=1.5``, the canonical Tukey fence).
3. **Cap** the outlier at the fence value (do NOT silently drop it —
   capping preserves directional signal while removing magnitude noise).
4. Surface the cap on the engine output so the report can render
   "VC Method capped from €28.5M to €4.2M (outlier vs Berkus/Scorecard)"
   verbatim.

When fewer than 3 legs contribute the policy is a no-op — IQR has no
defensible meaning for 2 points and the founder is owed the raw legs.
The policy never *adds* a leg, never *changes* the leg key, and never
mutates the leg's own ``unavailable_reason`` — it only caps the
``pre_money`` and emits a structured cap record.

All thresholds live as ``Decimal`` constants below; a future calibration
pass can sweep them without touching call-sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Sequence

from .money import LegResult, ONE, ZERO, q_eur


# ---------------------------------------------------------------------------
# Policy constants — tuned against the Benelux pre-seed dataset documented
# in the consortium spec.  The k=1.5 fence is the canonical Tukey choice;
# k=3.0 would only flag "extreme" outliers and would let the €28M VC pass.
# ---------------------------------------------------------------------------

#: Tukey fence multiplier — values further than ``k * IQR`` from the
#: median are considered outliers and capped at the fence.
TUKEY_K: Decimal = Decimal("1.5")

#: Floor on the cap.  Even with a tight IQR we never cap below 1.5× the
#: median — the goal is to dampen extreme magnitudes, not to flatten
#: legitimate forward-looking optimism into the qualitative floor.
MIN_CAP_VS_MEDIAN: Decimal = Decimal("1.5")

#: Hard cap on the multiplier any single leg can exceed the median by.
#: Ensures that even if the IQR is huge (e.g. only 3 legs with very
#: spread values) the engine still produces a defensible ceiling.
MAX_LEG_VS_MEDIAN: Decimal = Decimal("5.0")

#: Minimum number of contributing legs required before the policy
#: activates.  Below this the outlier test has no statistical meaning.
MIN_LEGS_FOR_POLICY: int = 3


@dataclass(frozen=True)
class CappedLeg:
    """One leg's outlier-policy verdict, surfaced on the engine output."""

    key: str
    """Stable leg key (``berkus`` / ``scorecard`` / ``vc`` / ``saas_forward``)."""

    label: str
    """Human-readable label, mirrored from :class:`LegResult`."""

    original_pre_money: Decimal
    """The leg's raw pre-money before the policy."""

    capped_pre_money: Decimal
    """Post-policy pre-money. Equals ``original_pre_money`` when not capped."""

    was_capped: bool
    """``True`` when the policy actually changed the leg's value."""

    cap_reason: Optional[str] = None
    """Localized one-liner explaining the cap.  ``None`` when not capped.
    Surfaced verbatim in the founder report defensibility section."""


@dataclass(frozen=True)
class OutlierPolicyOutput:
    """Result of applying the outlier policy to a sequence of legs."""

    legs: List[LegResult]
    """The legs after policy application — same shape, possibly capped
    ``pre_money`` values.  Synthesis blender consumes this list directly."""

    median: Decimal
    """Median of the *original* pre-money values (before capping).  Zero
    when fewer than :data:`MIN_LEGS_FOR_POLICY` legs were available."""

    iqr: Decimal
    """Inter-quartile range of the original values.  Zero when policy
    inactive or when all values are identical."""

    upper_fence: Decimal
    """``median + k * IQR`` (or the floor / ceiling, whichever bound).
    Surfaced for transparency — the report can quote it as
    "consortium fence: €X"."""

    cap_records: List[CappedLeg] = field(default_factory=list)
    """One :class:`CappedLeg` per leg the policy considered (capped *or*
    not).  Ordered to match the input sequence so the report can render
    a stable per-leg row."""

    policy_active: bool = False
    """``True`` when the policy actually evaluated (>=3 contributing
    legs).  ``False`` ⇒ the cap_records carry only the original values."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _percentile(sorted_values: Sequence[Decimal], pct: Decimal) -> Decimal:
    """Linear-interpolation percentile for a sorted sequence of Decimals.

    Avoids importing ``statistics`` so we stay inside ``Decimal`` end-to-
    end and don't lose precision on the round-trip through float.
    """
    if not sorted_values:
        return ZERO
    if len(sorted_values) == 1:
        return sorted_values[0]
    n = len(sorted_values)
    # Position in 0..n-1 space
    rank = pct * Decimal(n - 1) / Decimal(100)
    lo_index = int(rank)
    hi_index = min(lo_index + 1, n - 1)
    frac = rank - Decimal(lo_index)
    lo = sorted_values[lo_index]
    hi = sorted_values[hi_index]
    return lo + (hi - lo) * frac


def _build_cap_reason(
    *,
    label: str,
    original: Decimal,
    capped: Decimal,
    median: Decimal,
) -> str:
    """Localized (Dutch) explanation of why a leg was capped.

    Surfaced verbatim in the report defensibility section, so consistency
    matters more than literary flourish — kept as a stable template the
    QA team can grep against.
    """
    return (
        f"{label} gecapt van €{original:,.0f} naar €{capped:,.0f} — "
        f"buiten de Tukey-fence (mediaan €{median:,.0f}, k={TUKEY_K})."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_outlier_policy(
    legs: Sequence[LegResult],
) -> OutlierPolicyOutput:
    """Apply the Tukey-style outlier policy to a sequence of legs.

    Parameters
    ----------
    legs:
        The legs the synthesis blender is about to weight.  Only legs
        with ``available=True`` and ``pre_money > 0`` participate in the
        median / IQR calculation; unavailable legs pass through
        untouched.

    Returns
    -------
    OutlierPolicyOutput
        The capped legs + the policy's audit trail.  The blender reads
        ``output.legs`` for weighting and surfaces ``output.cap_records``
        on the engine output so the founder report can render a per-leg
        "was capped from X to Y" row.
    """
    contributing = [leg for leg in legs if leg.available and leg.pre_money > ZERO]
    cap_records: List[CappedLeg] = []

    # Below the policy threshold: pass through, but still emit cap records
    # so the consumer has a stable shape to render.
    if len(contributing) < MIN_LEGS_FOR_POLICY:
        for leg in legs:
            cap_records.append(
                CappedLeg(
                    key=leg.key,
                    label=leg.label,
                    original_pre_money=leg.pre_money,
                    capped_pre_money=leg.pre_money,
                    was_capped=False,
                )
            )
        return OutlierPolicyOutput(
            legs=list(legs),
            median=ZERO,
            iqr=ZERO,
            upper_fence=ZERO,
            cap_records=cap_records,
            policy_active=False,
        )

    sorted_values = sorted(leg.pre_money for leg in contributing)
    median = _percentile(sorted_values, Decimal(50))
    q1 = _percentile(sorted_values, Decimal(25))
    q3 = _percentile(sorted_values, Decimal(75))
    iqr = q3 - q1

    # Compute the upper fence.  Apply the floor (1.5× median) and the
    # ceiling (5× median) so even pathological IQRs produce a sane cap.
    raw_fence = median + TUKEY_K * iqr
    fence_floor = median * MIN_CAP_VS_MEDIAN
    fence_ceiling = median * MAX_LEG_VS_MEDIAN
    upper_fence = max(raw_fence, fence_floor)
    upper_fence = min(upper_fence, fence_ceiling)
    upper_fence = q_eur(upper_fence)

    # Lower fence — symmetric in principle but in practice the qualitative
    # legs (Berkus / Scorecard) are the ones that drift low, and we never
    # want to *raise* their floor to the median (that would suppress an
    # honest "this team is early" signal).  So lower-fence capping is a
    # no-op today; the dataclass just records the absence.
    lower_fence_floor = max(ZERO, q_eur(median - TUKEY_K * iqr))  # documented; not enforced

    # Apply the cap.  Iterate in input order so cap_records stays stable.
    capped_legs: List[LegResult] = []
    for leg in legs:
        if not (leg.available and leg.pre_money > ZERO):
            cap_records.append(
                CappedLeg(
                    key=leg.key,
                    label=leg.label,
                    original_pre_money=leg.pre_money,
                    capped_pre_money=leg.pre_money,
                    was_capped=False,
                )
            )
            capped_legs.append(leg)
            continue

        if leg.pre_money <= upper_fence:
            cap_records.append(
                CappedLeg(
                    key=leg.key,
                    label=leg.label,
                    original_pre_money=leg.pre_money,
                    capped_pre_money=leg.pre_money,
                    was_capped=False,
                )
            )
            capped_legs.append(leg)
            continue

        # Cap the outlier and rebuild the LegResult with the new amount.
        # The frozen dataclass forces an explicit reconstruction; this
        # is intentional — the audit trail in cap_records carries the
        # original, the blender sees only the capped value.
        capped_value = upper_fence
        cap_records.append(
            CappedLeg(
                key=leg.key,
                label=leg.label,
                original_pre_money=leg.pre_money,
                capped_pre_money=capped_value,
                was_capped=True,
                cap_reason=_build_cap_reason(
                    label=leg.label,
                    original=leg.pre_money,
                    capped=capped_value,
                    median=median,
                ),
            )
        )
        capped_legs.append(
            LegResult(
                key=leg.key,
                label=leg.label,
                pre_money=capped_value,
                available=leg.available,
                unavailable_reason=leg.unavailable_reason,
                confidence=leg.confidence,
                assumptions=leg.assumptions,
            )
        )

    # ``lower_fence_floor`` is computed for transparency / future use;
    # discard with a no-op assignment so linters don't complain and so
    # the next reader sees the value is intentionally not enforced.
    _ = lower_fence_floor

    return OutlierPolicyOutput(
        legs=capped_legs,
        median=q_eur(median),
        iqr=q_eur(iqr),
        upper_fence=upper_fence,
        cap_records=cap_records,
        policy_active=True,
    )


def cap_records_payload(records: Sequence[CappedLeg]) -> List[dict]:
    """Serialize the cap records for the engine ↔ report JSON boundary.

    Mirrors the convention in :mod:`.payloads` (Decimals to floats here
    and only here; engine-internal code never touches floats).
    """
    from .money import safe_float

    return [
        {
            "key": r.key,
            "label": r.label,
            "original_pre_money": safe_float(r.original_pre_money),
            "capped_pre_money": safe_float(r.capped_pre_money),
            "was_capped": r.was_capped,
            "cap_reason": r.cap_reason,
        }
        for r in records
    ]


def policy_payload(output: OutlierPolicyOutput) -> dict:
    """Serialize the full policy output for the engine ↔ report boundary."""
    from .money import safe_float

    return {
        "policy_active": output.policy_active,
        "median": safe_float(output.median),
        "iqr": safe_float(output.iqr),
        "upper_fence": safe_float(output.upper_fence),
        "tukey_k": safe_float(TUKEY_K),
        "min_cap_vs_median": safe_float(MIN_CAP_VS_MEDIAN),
        "max_leg_vs_median": safe_float(MAX_LEG_VS_MEDIAN),
        "cap_records": cap_records_payload(output.cap_records),
        "any_capped": any(r.was_capped for r in output.cap_records),
    }


__all__ = [
    "CappedLeg",
    "MAX_LEG_VS_MEDIAN",
    "MIN_CAP_VS_MEDIAN",
    "MIN_LEGS_FOR_POLICY",
    "OutlierPolicyOutput",
    "TUKEY_K",
    "apply_outlier_policy",
    "cap_records_payload",
    "policy_payload",
]


# Reference: Tukey (1977) "Exploratory Data Analysis", p. 43; the fence
# convention has remained the canonical "outlier" definition for half a
# century and survives partner-level scrutiny in any DD memo.  We keep ONE
# imported so the engine quantum constant stays in scope for any future
# refinement that re-bases the policy on a multiplier of the leg-blend
# baseline rather than absolute median.
_ = ONE
