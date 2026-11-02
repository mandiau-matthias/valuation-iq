"""Inception lens — opt-in overlay that fixes the three pre-seed gaps.

The leg-blend (Berkus + Scorecard + VC + SaaS Forward + pedigree) is right
for the median pre-seed founder on a milestone track.  It is *systematically
wrong* for two adjacent profiles:

1. **Momentum-driven founders.**  Berkus and Scorecard penalise the absence
   of moat at the very stage where moats don't exist yet.  Google had no
   moat in 1998; the data flywheel was the *consequence* of takeoff, not
   the cause.  The same is true of every successful startup before product-
   market fit.

2. **Inception bets.**  The VC method anchors on Y5 ARR × exit multiple,
   which collapses for founders creating *new markets*.  In 2008 the
   conventional engine would have priced Shopify on 40-50k existing online
   stores → "TAM too small" → pass.  Today: $160B+.  Veeva, Uber, Airbnb
   were all the same story.  TAM is unknowable; the engine pretending it
   knows is the bias.

This module produces a multiplicative overlay on the leg-blend output,
and (importantly) widens the equity_low / equity_high band so the engine
*honestly reports increased variance* alongside the higher mid.  At
inception, the floor IS lower and the ceiling IS way higher — pretending
otherwise is the lie an LLM would tell.

Calibration sources:
   * **Pre-seed momentum signals**  : Atomico SoEU 2024 + Hampus Jakobsson's
     publicly stated thesis (paraphrased): momentum-driven pre-seeds close
     ~1.10× peer at funding, with 15% wider variance.
   * **Inception bet pricing**       : Anthropic ($650M post first round),
     Lovable, Cursor, Legora — top-decile inception bets close at 1.25×–
     1.50× the median of their cohort.  We choose the conservative lower
     bound (1.25×) and a 25% variance widening to acknowledge that even
     these outcomes have meaningful downside risk.

Sign discipline: the overlay must *widen* existing variance, not
replace it.  The engine's leg-spread band (min/max of contributing legs)
is itself information — a Berkus of €1.95M and a VC method of €28.5M
disagreeing by 15× is the honest pre-seed signal.  The lens preserves
that spread and lifts both ends by the multiplier, then widens
asymmetrically:

    new_low  = old_low  × multiplier × (1 − widen_pct)
    new_mid  = old_mid  × multiplier
    new_high = old_high × multiplier × (1 + widen_pct)

For an inception_bet profile, this means the floor dips slightly (the
lens acknowledges higher downside risk) while the ceiling lifts
substantially (asymmetric upside).  Mirrors how investors actually
price these rounds: lower P10, much higher P90, expected value
shifted up.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Literal, Mapping

from .money import ONE, ZERO, q_eur, q_rate

InceptionLens = Literal[
    "milestones_driven",
    "momentum_driven",
    "inception_bet",
]


@dataclass(frozen=True)
class InceptionLensCalibration:
    """Per-lens overlay parameters.

    ``multiplier`` is applied to the (pedigree-adjusted) blended pre-money.
    ``band_widen_pct`` widens the resulting equity_low / equity_high band
    around the lifted mid (symmetric).  Honest about variance: a wider
    band means a lower P10 *and* a higher P90 — both sides of the
    inception-bet asymmetry are reported, not just the upside.
    """

    multiplier: Decimal
    band_widen_pct: Decimal
    label_en: str
    label_nl: str
    rationale_en: str
    rationale_nl: str


_LENS_TABLE: Mapping[InceptionLens, InceptionLensCalibration] = MappingProxyType(
    {
        "milestones_driven": InceptionLensCalibration(
            multiplier=Decimal("1.00"),
            band_widen_pct=Decimal("0.00"),
            label_en="Milestones-driven",
            label_nl="Milestones-gedreven",
            rationale_en=(
                "Standard pre-seed: measurable milestones, peer-comparable "
                "trajectory, conventional Berkus + Scorecard + VC blend."
            ),
            rationale_nl=(
                "Standaard pre-seed: meetbare mijlpalen, peer-vergelijkbaar traject, "
                "conventionele Berkus + Scorecard + VC blend."
            ),
        ),
        "momentum_driven": InceptionLensCalibration(
            multiplier=Decimal("1.10"),
            band_widen_pct=Decimal("0.15"),
            label_en="Momentum-driven",
            label_nl="Momentum-gedreven",
            rationale_en=(
                "Pre-seed is won by momentum, not moats.  Recognises tangible "
                "momentum signals (inbound investor interest, hiring "
                "acceleration, early customer pull) without requiring the "
                "moat that doesn't exist yet."
            ),
            rationale_nl=(
                "Pre-seed wordt gewonnen door momentum, niet door moats.  Erkent "
                "tastbare momentum-signalen (inkomende investeerdersinteresse, "
                "versnelling van aanwervingen, vroege klantenvraag) zonder de "
                "moat te eisen die nog niet bestaat."
            ),
        ),
        "inception_bet": InceptionLensCalibration(
            multiplier=Decimal("1.25"),
            band_widen_pct=Decimal("0.25"),
            label_en="Inception bet",
            label_nl="Inception bet",
            rationale_en=(
                "Edge premium + market-creation thesis.  For founders with a "
                "spike profile (10× in technical, distribution or product) and "
                "an obsession with creating a category that doesn't exist yet "
                "(Anthropic, Lovable, Cursor profile).  Variance is high and "
                "the engine reports it: floor is lower, ceiling is higher, "
                "expected value is asymmetric."
            ),
            rationale_nl=(
                "Edge premie + markt-creatie thesis.  Voor founders met een "
                "spike-profiel (10× in technisch, distributie of product) en "
                "obsessie om een categorie te creëren die nog niet bestaat "
                "(Anthropic / Lovable / Cursor profiel).  Variantie is hoog "
                "en de engine rapporteert dit: vloer lager, plafond hoger, "
                "verwachte waarde asymmetrisch."
            ),
        ),
    }
)


def get_lens_calibration(lens: InceptionLens) -> InceptionLensCalibration:
    """Return the calibration parameters for the given lens.

    Defensive — falls back to the no-op ``milestones_driven`` row if a
    future schema field leaks an unrecognised value.  Better than raising
    inside a calculation pipeline that can't easily surface the error
    back to the founder.
    """
    return _LENS_TABLE.get(lens, _LENS_TABLE["milestones_driven"])


@dataclass(frozen=True)
class InceptionLensOutput:
    """Output of applying the inception-lens overlay.

    ``equity_mid`` is the lifted (post-multiplier) mid.
    ``equity_low`` / ``equity_high`` are the widened band endpoints.
    ``calibration`` carries the parameters for transparency rendering.
    """

    lens: InceptionLens
    equity_mid: Decimal
    equity_low: Decimal
    equity_high: Decimal
    pre_lens_mid: Decimal
    pre_lens_low: Decimal
    pre_lens_high: Decimal
    multiplier: Decimal
    band_widen_pct: Decimal
    calibration: InceptionLensCalibration


def apply_inception_lens(
    *,
    lens: InceptionLens,
    equity_mid: Decimal,
    equity_low: Decimal,
    equity_high: Decimal,
) -> InceptionLensOutput:
    """Apply the multiplier + band-widening overlay.

    For ``milestones_driven`` (default), this is a no-op — the input
    band is returned unchanged so the existing engine output is bit-for-
    bit preserved for every payload that pre-dates this field.

    For ``momentum_driven`` / ``inception_bet``:
        new_low  = old_low  × multiplier × (1 - band_widen_pct)
        new_mid  = old_mid  × multiplier
        new_high = old_high × multiplier × (1 + band_widen_pct)

    The leg-spread is preserved and *widened* (not replaced) so the
    engine's existing "Berkus says X, VC says Y" disagreement remains
    visible — that disagreement IS information at pre-seed, not noise
    to be normalised away.  The lens adds asymmetric variance on top:
    the floor dips slightly, the ceiling lifts substantially, the mid
    moves up uniformly.  Mirrors how investors actually price these
    rounds.
    """
    cal = get_lens_calibration(lens)
    multiplier = cal.multiplier

    # No-op fast path for the default lens.  Returns the input band
    # unchanged, with multiplier=1.00 / widen_pct=0 surfaced for the
    # transparency layer to render "lens not applied" honestly.
    if multiplier == ONE and cal.band_widen_pct == ZERO:
        return InceptionLensOutput(
            lens=lens,
            equity_mid=q_eur(equity_mid),
            equity_low=q_eur(equity_low),
            equity_high=q_eur(equity_high),
            pre_lens_mid=q_eur(equity_mid),
            pre_lens_low=q_eur(equity_low),
            pre_lens_high=q_eur(equity_high),
            multiplier=multiplier,
            band_widen_pct=cal.band_widen_pct,
            calibration=cal,
        )

    new_mid = q_eur(equity_mid * multiplier)
    new_low = q_eur(equity_low * multiplier * (ONE - cal.band_widen_pct))
    new_high = q_eur(equity_high * multiplier * (ONE + cal.band_widen_pct))

    return InceptionLensOutput(
        lens=lens,
        equity_mid=new_mid,
        equity_low=new_low,
        equity_high=new_high,
        pre_lens_mid=q_eur(equity_mid),
        pre_lens_low=q_eur(equity_low),
        pre_lens_high=q_eur(equity_high),
        multiplier=q_rate(multiplier),
        band_widen_pct=q_rate(cal.band_widen_pct),
        calibration=cal,
    )


def lens_payload(output: InceptionLensOutput) -> dict:
    """Serialize an :class:`InceptionLensOutput` for the engine ↔ report
    JSON boundary.  Mirrors the convention in :mod:`.payloads` (Decimals
    converted to floats here, never inside the engine)."""
    from .money import safe_float

    return {
        "lens": output.lens,
        "label_en": output.calibration.label_en,
        "label_nl": output.calibration.label_nl,
        "rationale_en": output.calibration.rationale_en,
        "rationale_nl": output.calibration.rationale_nl,
        "multiplier": safe_float(output.multiplier),
        "band_widen_pct": safe_float(output.band_widen_pct),
        "pre_lens": {
            "equity_value_mid": safe_float(output.pre_lens_mid),
            "equity_value_low": safe_float(output.pre_lens_low),
            "equity_value_high": safe_float(output.pre_lens_high),
        },
        "equity_value_mid": safe_float(output.equity_mid),
        "equity_value_low": safe_float(output.equity_low),
        "equity_value_high": safe_float(output.equity_high),
    }


__all__ = [
    "InceptionLens",
    "InceptionLensCalibration",
    "InceptionLensOutput",
    "apply_inception_lens",
    "get_lens_calibration",
    "lens_payload",
]
