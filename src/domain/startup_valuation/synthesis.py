"""Synthesis blender — combines Berkus + Scorecard + VC + SaaS Forward into one equity range.

Two complementary blends live here:

* :func:`blend` — the **advisor / power-user** blend.  Weighted across all
  four legs with a stage-aware weight matrix.  Used inside Venus's advisor
  mode and the back-end SME pipeline.
* :func:`blend_founder_view` — the **founder triangulation**.  Three legs
  only (Berkus, SaaS Forward, VC Method) per the consortium / academic
  blueprint.  Scorecard stays computed and surfaced under the
  defensibility breakdown but doesn't drive the headline triangulation.

Both flow through :func:`blend_to_method_result` which is the single
adapter the rest of ValuationIQ consumes.

**Policies applied in this order (April 2026 hardening):**

1. **Sector consistency** — the SaaS Forward leg is hard-disabled when
   the founder-picked sector isn't recurring-revenue compatible (see
   :mod:`.sector_policy`).  Prevents a hardware company getting a SaaS
   multiple just because the leg silently defaulted ARR to zero.
2. **Outlier policy** — Tukey-style cap (see :mod:`.outlier_policy`).
   When the VC method anchors on an aggressive Y5 projection it can
   land 10× above the qualitative floor; the cap dampens the magnitude
   while preserving the directional signal.
3. **Founder pedigree** — multiplicative overlay, now with evidence-gated
   positive deltas (see :mod:`.founder_pedigree`).
4. **Inception lens** — opt-in lift / band-widening for momentum-driven
   and inception-bet founders (unchanged).
5. **Canonical headline** — a single defensible pre-money number that
   the report surfaces on EVERY page.  The advisor 4-leg blend remains
   the primary, the founder 3-leg view remains a sanity check, and the
   ``canonical`` block is the median of the two — picked specifically so
   the report cannot show two different headlines on adjacent pages.
6. **Defensibility score** — composite 0–10 score on the cover (see
   :mod:`.defensibility`).

When a leg returns ``available=False`` (e.g. SaaS forward without ARR),
its weight is dropped and the remainder is re-normalised to sum to 1.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Mapping, Optional, Sequence

from src.utils.decimal_helpers import pin_band_monotone as _pin_decimal_band

from .benchmark_context import apply_startup_benchmark_inputs, build_startup_benchmark_context
from .berkus import BerkusOutput, calculate_berkus
from .cap_table import build_round_context_payload, simulate_round
from .defensibility import DefensibilityScore, calculate_defensibility, defensibility_payload
from .founder_pedigree import FounderPedigreeOutput, calculate_founder_pedigree, pedigree_payload
from .inception_lens import InceptionLensOutput, apply_inception_lens, lens_payload
from .methodology_gate import build_startup_methodology_recommendation
from .money import ONE, Q_RATE, ZERO, LegResult, q_eur, q_rate, safe_float, sum_decimals
from .outlier_policy import OutlierPolicyOutput, apply_outlier_policy, policy_payload
from .payloads import berkus_payload, saas_forward_payload, scorecard_payload, vc_payload
from .regional_data import RegionalReferenceData
from .saas_forward import SaasForwardOutput, calculate_saas_forward
from .schemas import StartupInputs, StartupStage
from .scorecard import ScorecardOutput, calculate_scorecard
from .sector_policy import is_saas_forward_compatible, saas_forward_skip_reason
from .synthesis_constants import CANONICAL_BASIS_EN as _CANONICAL_BASIS_EN
from .synthesis_constants import (
    CANONICAL_BASIS_KEY_ADVISOR_ONLY,
    CANONICAL_BASIS_KEY_BLENDED,
    CANONICAL_BASIS_KEY_FOUNDER_ONLY,
    CANONICAL_BASIS_KEY_INSUFFICIENT,
)
from .synthesis_constants import FOUNDER_STAGE_WEIGHTS as _FOUNDER_STAGE_WEIGHTS
from .synthesis_constants import LEG_DISPLAY_NAMES
from .synthesis_constants import STAGE_WEIGHTS as _STAGE_WEIGHTS
from .value_up_actions import build_startup_value_up_actions
from .vc_method import VcOutput, calculate_vc

if TYPE_CHECKING:
    from src.api.schemas.stateless_api import MethodResult


@dataclass(frozen=True)
class StartupBlendOutput:
    """Synthesis output: blended pre-money + per-method legs + audit trail."""

    # ---- Advisor 4-leg blend (primary) -----------------------------------
    equity_mid: Decimal
    equity_low: Decimal
    equity_high: Decimal
    weights: Dict[str, Decimal]
    contributors: List[str]
    narrative: str

    # ---- Per-leg outputs (raw, pre-policy) -------------------------------
    berkus: BerkusOutput
    scorecard: ScorecardOutput
    vc: VcOutput
    saas_forward: SaasForwardOutput

    # ---- Founder 3-leg triangulation -------------------------------------
    founder_weights: Dict[str, Decimal]
    """Weight map used for the 3-leg founder triangulation (Berkus +
    SaaS Forward + VC).  Always populated; consumers can ignore it on
    the advisor flow but the report's 'football field for founders' row
    needs it."""
    founder_equity_mid: Decimal
    """Blended pre-money under the 3-leg founder weighting (consortium
    spec).  Sanity-check companion to the advisor 4-leg headline; both
    feed into the canonical headline below."""
    founder_equity_low: Decimal
    founder_equity_high: Decimal
    founder_contributors: List[str]

    # ---- Pedigree + lens overlays ---------------------------------------
    pedigree: FounderPedigreeOutput
    """Founder pedigree multiplier + breakdown. Already applied to all
    ``equity_*`` and ``founder_equity_*`` fields above; surfaced here so
    the report can show the founder which qualifications produced the lift
    (or penalty) on top of the leg-blend baseline."""
    inception_lens: InceptionLensOutput
    """Inception-lens overlay output (multiplier + band widening +
    rationale).  Already applied to all ``equity_*`` and
    ``founder_equity_*`` fields above; surfaced here so the report can
    explain *why* the band is wider on momentum_driven / inception_bet
    payloads.  No-op for the default ``milestones_driven`` lens."""

    # ---- Pre-pedigree baselines (transparency) --------------------------
    pre_pedigree_equity_mid: Decimal
    """Blended pre-money *before* the pedigree overlay. Surfaced so the
    report's 'football field' can show the leg blend baseline next to
    the post-pedigree headline."""
    pre_pedigree_equity_low: Decimal
    pre_pedigree_equity_high: Decimal
    pre_pedigree_founder_equity_mid: Decimal
    pre_pedigree_founder_equity_low: Decimal
    pre_pedigree_founder_equity_high: Decimal

    # ---- April 2026 hardening: outlier policy + canonical + defensibility -
    outlier_policy: OutlierPolicyOutput
    """Tukey-style outlier policy applied to the 4-leg blend BEFORE
    weighting.  Surfaced verbatim so the report can render the per-leg
    cap audit trail.  When ``policy_active=False`` the policy was a
    no-op (fewer than 3 legs contributed)."""

    canonical_pre_money_mid: Decimal
    """The single defensible pre-money number the report shows on the
    cover, the one-pager, and the executive summary.  Computed as the
    median of (advisor 4-leg mid, founder 3-leg mid) AFTER the outlier
    policy + sector consistency + pedigree + lens overlays.  Fixes the
    "two headline numbers on adjacent pages" failure mode the consortium
    flagged in April 2026."""
    canonical_pre_money_low: Decimal
    canonical_pre_money_high: Decimal
    canonical_basis: str
    """English one-liner the report renders next to the canonical number
    when no locale-aware translation is available. Defensive default —
    NL/EN renders go through ``canonical_basis_key`` (see below) at the
    report layer."""

    canonical_basis_key: str
    """Stable enum-style identifier for the canonical-basis sentence:
    one of ``canonical_basis_blended`` / ``canonical_basis_advisor_only``
    / ``canonical_basis_founder_only`` / ``canonical_basis_insufficient``.
    The report layer translates this to NL or EN."""

    saas_forward_sector_skipped: bool
    """``True`` when the SaaS Forward leg was hard-disabled because the
    founder-picked sector isn't recurring-revenue compatible.  Drives
    the defensibility-score sector-consistency factor."""

    defensibility: DefensibilityScore
    """Composite 0–10 defensibility score for the cover badge."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_weights(
    stage: StartupStage,
    *,
    active_keys: Sequence[str],
    matrix: Mapping[StartupStage, Mapping[str, Decimal]],
) -> Dict[str, Decimal]:
    """Return the active weight map, dropping any leg not in ``active_keys``
    and re-normalising the remaining weights to sum to 1."""
    base: Dict[str, Decimal] = {key: Decimal(value) for key, value in matrix[stage].items()}
    active_set = set(active_keys)
    for key in list(base.keys()):
        if key not in active_set:
            base[key] = ZERO
    total = sum_decimals(base.values()) or ONE
    return {k: q_rate(v / total) for k, v in base.items()}


def _blend_legs(
    legs: Sequence[LegResult],
    *,
    weights: Mapping[str, Decimal],
) -> tuple[Decimal, Decimal, Decimal, List[str]]:
    """Return ``(mid, low, high, contributors)`` for a sequence of legs.

    Mid is the weighted average over *contributing* legs; low/high are
    the literal min/max so the founder can defend either end of the
    range without revisiting the math.
    """
    contributing: List[LegResult] = [leg for leg in legs if leg.available and leg.pre_money > ZERO]
    if not contributing:
        return ZERO, ZERO, ZERO, []
    contributors = [leg.key for leg in contributing]
    weighted_sum = sum_decimals(leg.pre_money * weights.get(leg.key, ZERO) for leg in contributing)
    leg_values = [leg.pre_money for leg in contributing]
    blend_mid = q_eur(weighted_sum)
    blend_low = q_eur(min(leg_values))
    blend_high = q_eur(max(leg_values))
    # The weighted_sum is within [min, max] only when weights sum to 1.0
    # across contributing legs. When weights re-normalise around dropped
    # legs (or a sector-policy skip leaves a contributing leg at weight 0),
    # the mid can drift outside the [min, max] band. Pin so callers never
    # see an inverted (low, mid, high). Mid is authoritative; squeeze the
    # min/max bound that's on the wrong side.
    blend_low, blend_mid, blend_high = _pin_decimal_band(blend_low, blend_mid, blend_high)
    return (blend_mid, blend_low, blend_high, contributors)


def _disable_saas_forward_for_sector(
    saas_forward: SaasForwardOutput,
    *,
    sector: str,
) -> SaasForwardOutput:
    """Hard-disable the SaaS Forward leg for non-recurring-revenue sectors.

    Returns the leg unchanged when (a) it was already unavailable for
    other reasons (no ARR), or (b) the sector is in the compatible
    set.  Otherwise returns a fresh :class:`SaasForwardOutput` with
    ``available=False`` and a localized skip reason that surfaces in
    the report.

    Centralising the policy here (rather than inside ``calculate_saas_
    forward``) keeps the leg-level helper sector-blind — easier to test,
    easier to swap in a different methodology later.
    """
    if not saas_forward.available:
        return saas_forward
    if is_saas_forward_compatible(sector):
        return saas_forward
    # Rebuild with the policy decision recorded in unavailable_reason.
    return SaasForwardOutput(
        pre_money=ZERO,
        current_arr=saas_forward.current_arr,
        forward_arr=saas_forward.forward_arr,
        forward_mom_growth_pct=saas_forward.forward_mom_growth_pct,
        forward_months=saas_forward.forward_months,
        base_multiple=saas_forward.base_multiple,
        applied_multiple=ZERO,
        risk_discount=saas_forward.risk_discount,
        churn_drag=saas_forward.churn_drag,
        available=False,
        unavailable_reason=saas_forward_skip_reason(sector),
    )


def _canonical_band(
    *,
    advisor_mid: Decimal,
    advisor_low: Decimal,
    advisor_high: Decimal,
    founder_mid: Decimal,
    founder_low: Decimal,
    founder_high: Decimal,
) -> tuple[Decimal, Decimal, Decimal, str, str]:
    """Compute the canonical pre-money triple + a one-line basis.

    The canonical mid is the median of the two blends — explicitly NOT
    the average, because we want the *more conservative* of the two when
    they disagree.  When only one blend produced a number we use it
    verbatim (no manufactured confidence).

    Returns ``(mid, low, high, basis_key, basis_en)``. ``basis_key`` is a
    stable enum-style identifier the report layer can localise; ``basis_en``
    is the English default string surfaced as ``canonical.basis`` for
    backwards-compatible (non-localising) consumers.
    """
    advisor_active = advisor_mid > ZERO
    founder_active = founder_mid > ZERO

    if advisor_active and founder_active:
        # Median of two Decimals = their arithmetic mean (only two points).
        # We deliberately use the mean here rather than min — taking the
        # min would silently devalue every founder report, which is too
        # aggressive a default.  Mean is the principled middle-ground.
        canonical_mid = q_eur((advisor_mid + founder_mid) / Decimal(2))
        # Low/high band wraps both blends, not just the canonical mid —
        # the report should show the full uncertainty.
        canonical_low = q_eur(min(advisor_low, founder_low))
        canonical_high = q_eur(max(advisor_high, founder_high))
        basis_key = CANONICAL_BASIS_KEY_BLENDED
    elif advisor_active:
        canonical_mid, canonical_low, canonical_high = advisor_mid, advisor_low, advisor_high
        basis_key = CANONICAL_BASIS_KEY_ADVISOR_ONLY
    elif founder_active:
        canonical_mid, canonical_low, canonical_high = founder_mid, founder_low, founder_high
        basis_key = CANONICAL_BASIS_KEY_FOUNDER_ONLY
    else:
        canonical_mid = canonical_low = canonical_high = ZERO
        basis_key = CANONICAL_BASIS_KEY_INSUFFICIENT
    return canonical_mid, canonical_low, canonical_high, basis_key, _CANONICAL_BASIS_EN[basis_key]


def _narrative(
    stage: StartupStage,
    weights: Mapping[str, Decimal],
    contributors: Sequence[str],
    *,
    pedigree_multiplier: Decimal = ONE,
    canonical_basis: str = "",
) -> str:
    """One-sentence explanation rendered into the report."""
    pretty_stage = {"pre_seed": "pre-seed", "seed": "seed", "series_a": "Series A"}[stage]
    parts = [
        f"{LEG_DISPLAY_NAMES[key]} ({weights[key] * 100:.0f}%)"
        for key in ("berkus", "scorecard", "vc", "saas_forward")
        if weights.get(key, ZERO) > ZERO
    ]
    method_list = ", ".join(parts) if parts else "Berkus + Scorecard"
    pedigree_clause = ""
    if pedigree_multiplier != ONE:
        direction = "lift" if pedigree_multiplier > ONE else "discount"
        pedigree_clause = (
            f" Founder pedigree {direction}: {pedigree_multiplier:.2f}× on the leg-blend baseline."
        )
    canonical_clause = f" {canonical_basis}" if canonical_basis else ""
    return (
        f"Stage-aware {pretty_stage} blend: {method_list}. "
        f"Active legs: {', '.join(contributors) or 'Berkus'}."
        f"{pedigree_clause}{canonical_clause}"
    )


def _augment_narrative_with_lens(narrative: str, lens_output: InceptionLensOutput) -> str:
    """Append a one-sentence lens clause when the lens is non-trivial.

    Honest about what the lens does: it both lifts the mid AND widens
    the band, so we mention both directions.  The default ``milestones_
    driven`` lens leaves the narrative unchanged.
    """
    if lens_output.lens == "milestones_driven":
        return narrative
    cal = lens_output.calibration
    return (
        f"{narrative} Inception lens: {cal.label_en.lower()} — "
        f"{lens_output.multiplier:.2f}× lift, ±{lens_output.band_widen_pct * 100:.0f}% "
        f"variance band."
    )


# ---------------------------------------------------------------------------
# Public blend functions
# ---------------------------------------------------------------------------


def blend(
    inputs: StartupInputs,
    *,
    region_data: RegionalReferenceData,
) -> StartupBlendOutput:
    """Run the four helpers and blend their pre-money equities into a single range.

    Produces *both* the advisor 4-leg blend and the founder 3-leg
    triangulation in a single pass — calling code picks which to surface.
    Both pass through the April 2026 hardening: sector consistency,
    outlier capping, evidence-gated pedigree, lens overlay.
    """
    berkus = calculate_berkus(inputs, max_per_milestone=region_data.berkus_max_per_milestone)
    scorecard = calculate_scorecard(inputs, average_pre_money=region_data.average_pre_money)
    vc = calculate_vc(inputs, region_data=region_data)
    saas_forward_raw = calculate_saas_forward(inputs, region_data=region_data)

    # --- Sector consistency policy --------------------------------------
    # The SaaS Forward leg only contributes to sectors where the
    # forward-ARR construct is defensible.  Centralised in sector_policy.
    sector_str = inputs.sector
    saas_forward_was_available_pre_policy = saas_forward_raw.available
    saas_forward = _disable_saas_forward_for_sector(saas_forward_raw, sector=sector_str)
    saas_forward_sector_skipped = (
        saas_forward_was_available_pre_policy and not saas_forward.available
    )

    raw_legs: List[LegResult] = [
        berkus.to_leg_result(),
        scorecard.to_leg_result(),
        vc.to_leg_result(),
        saas_forward.to_leg_result(),
    ]

    # --- Outlier policy --------------------------------------------------
    # Tukey-style cap on the 4-leg input.  The capped legs are reused
    # for both the advisor and founder blends so the two views can never
    # disagree on what value the VC method is allowed to contribute.
    outlier = apply_outlier_policy(raw_legs)
    capped_legs = outlier.legs
    leg_by_key = {leg.key: leg for leg in capped_legs}

    # --- Advisor 4-leg blend --------------------------------------------
    advisor_active = [leg.key for leg in capped_legs if leg.available and leg.pre_money > ZERO]
    advisor_weights = _resolve_weights(
        inputs.stage, active_keys=advisor_active, matrix=_STAGE_WEIGHTS
    )
    equity_mid, equity_low, equity_high, advisor_contributors = _blend_legs(
        capped_legs, weights=advisor_weights
    )

    # --- Founder 3-leg triangulation ------------------------------------
    founder_keys = ("berkus", "vc", "saas_forward")
    founder_legs = [leg_by_key[k] for k in founder_keys if k in leg_by_key]
    founder_active = [leg.key for leg in founder_legs if leg.available and leg.pre_money > ZERO]
    founder_weights = _resolve_weights(
        inputs.stage, active_keys=founder_active, matrix=_FOUNDER_STAGE_WEIGHTS
    )
    founder_mid, founder_low, founder_high, founder_contributors = _blend_legs(
        founder_legs, weights=founder_weights
    )

    # --- Founder pedigree overlay ---------------------------------------
    # Multiplicative on the blend output (advisor + founder views). The
    # pre-pedigree baseline is preserved on the result so the report can
    # render "leg blend €X → with pedigree €Y" transparently.
    pedigree = calculate_founder_pedigree(inputs.founder_pedigree)
    multiplier = pedigree.multiplier

    pre_pedigree_equity_mid = equity_mid
    pre_pedigree_equity_low = equity_low
    pre_pedigree_equity_high = equity_high
    pre_pedigree_founder_mid = founder_mid
    pre_pedigree_founder_low = founder_low
    pre_pedigree_founder_high = founder_high

    equity_mid = q_eur(equity_mid * multiplier)
    equity_low = q_eur(equity_low * multiplier)
    equity_high = q_eur(equity_high * multiplier)
    founder_mid = q_eur(founder_mid * multiplier)
    founder_low = q_eur(founder_low * multiplier)
    founder_high = q_eur(founder_high * multiplier)

    # --- Inception lens overlay ----------------------------------------
    # Applied AFTER pedigree.  Multiplier lifts the mid; band-widening
    # opens the low/high band around the lifted mid so the engine reports
    # honest variance for momentum-driven / inception-bet founders.
    # No-op for the default ``milestones_driven`` lens, so every payload
    # that pre-dates this field round-trips bit-for-bit.
    lens_output = apply_inception_lens(
        lens=inputs.inception_lens,
        equity_mid=equity_mid,
        equity_low=equity_low,
        equity_high=equity_high,
    )
    equity_mid = lens_output.equity_mid
    equity_low = lens_output.equity_low
    equity_high = lens_output.equity_high

    # Apply the same lens overlay to the founder triangulation so both
    # the advisor blend and the 3-leg founder view stay in lockstep.
    founder_lens = apply_inception_lens(
        lens=inputs.inception_lens,
        equity_mid=founder_mid,
        equity_low=founder_low,
        equity_high=founder_high,
    )
    founder_mid = founder_lens.equity_mid
    founder_low = founder_lens.equity_low
    founder_high = founder_lens.equity_high

    # --- Canonical headline ---------------------------------------------
    (
        canonical_mid,
        canonical_low,
        canonical_high,
        canonical_basis_key,
        canonical_basis,
    ) = _canonical_band(
        advisor_mid=equity_mid,
        advisor_low=equity_low,
        advisor_high=equity_high,
        founder_mid=founder_mid,
        founder_low=founder_low,
        founder_high=founder_high,
    )

    # --- Defensibility score --------------------------------------------
    # Compute AFTER all overlays so sub-scores reflect the final state
    # the report will render.
    contributing_count = len([r for r in outlier.cap_records if r.original_pre_money > ZERO])
    defensibility = calculate_defensibility(
        median=outlier.median,
        iqr=outlier.iqr,
        any_capped=any(r.was_capped for r in outlier.cap_records),
        contributing_legs=contributing_count,
        sector=sector_str,
        # The leg can be "active" in the eyes of the defensibility score
        # only if it survived the sector policy AND contributed math.
        saas_forward_active=saas_forward.available and saas_forward.pre_money > ZERO,
        saas_forward_compatible=is_saas_forward_compatible(sector_str),
        positive_pedigree_claims=pedigree.positive_claims_count,
        evidenced_pedigree_claims=pedigree.evidenced_claims_count,
        vc_contributed=vc.pre_money > ZERO,
        year5_supplied=(
            inputs.year5_revenue_projection is not None and inputs.year5_revenue_projection > ZERO
        ),
        exit_multiple_supplied=(
            inputs.exit_revenue_multiple is not None and inputs.exit_revenue_multiple > ZERO
        ),
        target_roi_supplied=(inputs.target_roi_x is not None and inputs.target_roi_x > ZERO),
        arr=inputs.arr,
        mrr=inputs.mrr,
        active_users=inputs.active_users,
    )

    return StartupBlendOutput(
        equity_mid=equity_mid,
        equity_low=equity_low,
        equity_high=equity_high,
        weights=advisor_weights,
        contributors=advisor_contributors,
        narrative=_augment_narrative_with_lens(
            _narrative(
                inputs.stage,
                advisor_weights,
                advisor_contributors,
                pedigree_multiplier=multiplier,
                canonical_basis=canonical_basis,
            ),
            lens_output,
        ),
        berkus=berkus,
        scorecard=scorecard,
        vc=vc,
        saas_forward=saas_forward,
        founder_weights=founder_weights,
        founder_equity_mid=founder_mid,
        founder_equity_low=founder_low,
        founder_equity_high=founder_high,
        founder_contributors=founder_contributors,
        pedigree=pedigree,
        pre_pedigree_equity_mid=pre_pedigree_equity_mid,
        pre_pedigree_equity_low=pre_pedigree_equity_low,
        pre_pedigree_equity_high=pre_pedigree_equity_high,
        pre_pedigree_founder_equity_mid=pre_pedigree_founder_mid,
        pre_pedigree_founder_equity_low=pre_pedigree_founder_low,
        pre_pedigree_founder_equity_high=pre_pedigree_founder_high,
        inception_lens=lens_output,
        outlier_policy=outlier,
        canonical_pre_money_mid=canonical_mid,
        canonical_pre_money_low=canonical_low,
        canonical_pre_money_high=canonical_high,
        canonical_basis=canonical_basis,
        canonical_basis_key=canonical_basis_key,
        saas_forward_sector_skipped=saas_forward_sector_skipped,
        defensibility=defensibility,
    )


def blend_founder_view(
    inputs: StartupInputs,
    *,
    region_data: RegionalReferenceData,
) -> StartupBlendOutput:
    """Convenience alias used by Mercury / founder-mode Venus.

    Returns the same :class:`StartupBlendOutput` shape as :func:`blend`;
    the founder consumer reads the ``founder_*`` fields for its
    triangulated headline.
    """
    return blend(inputs, region_data=region_data)


# ---------------------------------------------------------------------------
# MethodResult adapter (the canonical engine ↔ rest-of-app contract)
# ---------------------------------------------------------------------------


def blend_to_method_result(
    inputs: StartupInputs,
    *,
    region_data: Optional[RegionalReferenceData] = None,
) -> "MethodResult":
    """Public adapter that returns a stable :class:`MethodResult`.

    Used by ``src.domain.methods.startup`` so the rest of the engine can
    treat startup_valuation like any other Omni-Calc method.

    The ``MethodResult.value`` returned is the **canonical pre-money**
    (April 2026 hardening) — the single number the report renders on
    every page.  The advisor 4-leg blend and the founder 3-leg blend
    are still surfaced in ``details`` so the report can render the
    full triangulation, but no caller should treat either of them as
    *the* headline.
    """
    # Lazy import: ``stateless_api`` itself imports ``StartupInputs`` from
    # this package, so we defer the MethodResult import to call-time to
    # break the circular import.
    from src.api.schemas.stateless_api import MethodResult

    if region_data is None:
        from .regional_data import get_regional_reference_data

        # Pass ``inputs.sector`` so the Q1-2026 8-sector seed in
        # ``startup_valuation_benchmarks`` is actually consulted — without
        # it Athena returned a sector-blind row and the static fallback
        # collapsed every sector to the same anchor.
        region_data = get_regional_reference_data(
            inputs.country_code, inputs.stage, sector=inputs.sector
        )
    region_data = apply_startup_benchmark_inputs(region_data, inputs)

    blend_output = blend(inputs, region_data=region_data)
    methodology_recommendation = build_startup_methodology_recommendation(inputs)
    methodology_recommendation_payload = methodology_recommendation.to_payload()

    # The canonical headline drives MethodResult.value.  When the
    # canonical fell back to zero (no leg produced a number) we mark
    # the method unavailable rather than emit a misleading €0.
    headline = blend_output.canonical_pre_money_mid
    if headline <= ZERO:
        return MethodResult(
            value=None,
            method_key="startup_valuation",
            label="Startup Valuation",
            available=False,
            unavailable_reason=(
                "Insufficient inputs: fill in the qualitative milestones and optionally "
                "MRR/ARR or a five-year revenue projection to produce a valuation range."
            ),
            details={
                "methodology_recommendation": methodology_recommendation_payload,
                "methodology_gate": methodology_recommendation_payload,
            },
        )

    cap_simulation = simulate_round(
        pre_money=headline,
        investment_amount_sought=inputs.investment_amount_sought,
        cap_table=inputs.cap_table,
        round_scenario=inputs.round_scenario,
    )
    round_context = build_round_context_payload(
        objective_pre_money=headline,
        round_scenario=inputs.round_scenario,
        investment_amount_sought=inputs.investment_amount_sought,
        cap_table=inputs.cap_table,
    )

    details: Dict = {
        "stage": inputs.stage,
        "country_code": region_data.region_code,
        "narrative": blend_output.narrative,
        # ---- Advisor 4-leg blend (transparency) -------------------------
        "equity_value_mid": safe_float(blend_output.equity_mid),
        "equity_value_low": safe_float(blend_output.equity_low),
        "equity_value_high": safe_float(blend_output.equity_high),
        "weights": {k: safe_float(v) for k, v in blend_output.weights.items()},
        "contributors": blend_output.contributors,
        # ---- Founder 3-leg blend (transparency) -------------------------
        "founder_view": {
            "equity_value_mid": safe_float(blend_output.founder_equity_mid),
            "equity_value_low": safe_float(blend_output.founder_equity_low),
            "equity_value_high": safe_float(blend_output.founder_equity_high),
            "weights": {k: safe_float(v) for k, v in blend_output.founder_weights.items()},
            "contributors": blend_output.founder_contributors,
        },
        # ---- Canonical headline (single source of truth) ----------------
        "canonical": {
            "pre_money_mid": safe_float(blend_output.canonical_pre_money_mid),
            "pre_money_low": safe_float(blend_output.canonical_pre_money_low),
            "pre_money_high": safe_float(blend_output.canonical_pre_money_high),
            "basis": blend_output.canonical_basis,
            # Stable enum-style key so the report renderer can localise
            # the basis sentence (NL/EN) without parsing the English
            # default string.  See ``_CANONICAL_BASIS_EN`` for the
            # canonical key set.
            "basis_key": blend_output.canonical_basis_key,
        },
        "methodology_recommendation": methodology_recommendation_payload,
        # Backward-compatible alias for consumers that naturally look for
        # a gate object rather than a recommendation object.
        "methodology_gate": methodology_recommendation_payload,
        "pre_pedigree": {
            "equity_value_mid": safe_float(blend_output.pre_pedigree_equity_mid),
            "equity_value_low": safe_float(blend_output.pre_pedigree_equity_low),
            "equity_value_high": safe_float(blend_output.pre_pedigree_equity_high),
            "founder_equity_value_mid": safe_float(blend_output.pre_pedigree_founder_equity_mid),
            "founder_equity_value_low": safe_float(blend_output.pre_pedigree_founder_equity_low),
            "founder_equity_value_high": safe_float(blend_output.pre_pedigree_founder_equity_high),
        },
        "founder_pedigree": pedigree_payload(blend_output.pedigree),
        "inception_lens": lens_payload(blend_output.inception_lens),
        # ---- April 2026 hardening blocks --------------------------------
        "outlier_policy": policy_payload(blend_output.outlier_policy),
        "defensibility": defensibility_payload(blend_output.defensibility),
        "sector_consistency": {
            "sector": inputs.sector,
            "saas_forward_compatible": is_saas_forward_compatible(inputs.sector),
            "saas_forward_sector_skipped": blend_output.saas_forward_sector_skipped,
        },
        # ---- Per-leg payloads -------------------------------------------
        "berkus": berkus_payload(blend_output.berkus),
        "scorecard": scorecard_payload(blend_output.scorecard),
        "vc": vc_payload(blend_output.vc),
        "saas_forward": saas_forward_payload(blend_output.saas_forward),
        # Mirrors Hermes' SME `valuation_method_readiness` contract for the
        # 4 startup-stage legs. Mercury's report renderer + StudioCoPilot
        # consume this to render per-method "ready / blocked" nudges instead
        # of treating the engine as a single black box.
        "startup_method_readiness": {
            "berkus": blend_output.berkus.pre_money > ZERO,
            "scorecard": blend_output.scorecard.pre_money > ZERO,
            "vc": blend_output.vc.pre_money > ZERO,
            "saas_forward": bool(blend_output.saas_forward.available),
        },
        "regional_reference": {
            "average_pre_money": safe_float(region_data.average_pre_money),
            "berkus_max_per_milestone": safe_float(region_data.berkus_max_per_milestone),
            "comparable_exit_revenue_multiple": safe_float(
                region_data.comparable_exit_revenue_multiple
            ),
            "default_target_roi_x": safe_float(region_data.default_target_roi_x),
            "default_dilution_pct": safe_float(region_data.default_dilution_pct),
            "default_yoy_growth_factor": safe_float(region_data.default_yoy_growth_factor),
            "source": region_data.source,
            "methodology_version": region_data.methodology_version,
            "published_at": region_data.published_at,
            "geography_scope": region_data.geography_scope,
            "geography_label": region_data.geography_label,
            "sample_size": region_data.sample_size,
            "evidence_quality": region_data.evidence_quality,
            "benchmark_source_type": region_data.benchmark_source_type,
            "source_url": region_data.source_url,
            "source_observed_at": region_data.source_observed_at,
        },
        "cap_table_simulator": cap_simulation.to_payload() if cap_simulation else None,
        "round_context": round_context,
        "startup_benchmark_context": build_startup_benchmark_context(
            inputs=inputs,
            region_data=region_data,
            round_context=round_context,
        ),
        "startup_value_up_actions": build_startup_value_up_actions(inputs),
    }

    return MethodResult(
        value=headline,
        method_key="startup_valuation",
        label="Startup Valuation",
        available=True,
        confidence=methodology_recommendation.confidence_level,
        value_low=blend_output.canonical_pre_money_low,
        value_high=blend_output.canonical_pre_money_high,
        engine_version="startup_valuation_v1",
        details=details,
    )


__all__ = [
    "LEG_DISPLAY_NAMES",
    "StartupBlendOutput",
    "blend",
    "blend_founder_view",
    "blend_to_method_result",
]


# Keep the q_rate symbol re-exported for any historical caller; remove
# the indirection later once all internal call-sites have migrated.
_ = Q_RATE
