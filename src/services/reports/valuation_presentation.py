"""BET-435 — stage/tier-gated valuation PRESENTATION contract.

Pure derivation of HOW a computed valuation should be presented, keyed off the
``data_tier`` (BET-434). It owns the honest method + confidence labels and the
no-false-precision-headline rule, so a registry-only (``indicative``) valuation is
always a discussion RANGE — never a headline point — while a ``defensible`` one is
grounded in real financials and an ``attested`` one is hash-locked.

This is the ValuationIQ half of the evidence-maturity ladder; the Titan half
(``lifecycle-data-tier.util.ts`` ``valuationTierForStage``) carries the parallel
stage→tier labels for the card surface. They are complementary: titan answers
"what does this STAGE unlock?", this module answers "how do I present THIS
computed number?".

Brand oath ("know your worth", mercury/docs/brand/brand-oath-v1.md, "same grapes,
honest label"): the copy is qualitative and never claims "absolute accuracy" or a
fabricated "+X%". This module NEVER mutates the computed number — it only describes
how to present it. The render-time enforcement (suppressing the point in the PDF /
card) is a downstream, flag-gated consumer decision, not done here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# The shared evidence-maturity ladder. VIQ derives indicative|defensible from input
# provenance; `attested` is owned by the legal/Attest layer (titan ``deal_ready``) and
# is accepted here only so a caller that already knows the stage can ask for its copy.
INDICATIVE = "indicative"
DEFENSIBLE = "defensible"
ATTESTED = "attested"


@dataclass(frozen=True)
class ValuationPresentation:
    """How to honestly present a computed valuation of a given ``data_tier``.

    Stable, immutable contract — surfaces localize off ``data_tier`` +
    ``headline_basis``; the strings here are canonical English defaults.
    """

    data_tier: str
    #: Honest name for the method the number rests on (no false precision).
    method_label: str
    #: Qualitative confidence sentence — brand-oath aligned, never "absolute accuracy".
    confidence_label: str
    #: ``False`` ⇒ headline the low–high RANGE, not a point. The core indicative rule.
    present_point_estimate: bool
    #: ``"range"`` | ``"point"`` — what the headline should lead with.
    headline_basis: str
    #: One-line, brand-oath-aligned presentation disclaimer + advance CTA.
    disclaimer: str


_PRESENTATION: dict[str, ValuationPresentation] = {
    INDICATIVE: ValuationPresentation(
        data_tier=INDICATIVE,
        method_label="Market-multiple on public registry data",
        confidence_label="Indicative range — a starting point, not a binding valuation",
        present_point_estimate=False,
        headline_basis="range",
        disclaimer=(
            "Based on public data only. Connect your financials for a defensible valuation."
        ),
    ),
    DEFENSIBLE: ValuationPresentation(
        data_tier=DEFENSIBLE,
        method_label="Earnings multiple on your connected financials",
        confidence_label="Defensible estimate — grounded in your financials",
        present_point_estimate=True,
        headline_basis="point",
        disclaimer=(
            "Grounded in your real financials; the range tightens as your data quality rises."
        ),
    ),
    ATTESTED: ValuationPresentation(
        data_tier=ATTESTED,
        method_label="Attested, financials-grounded valuation",
        confidence_label="Attested — independently verifiable and hash-locked",
        present_point_estimate=True,
        headline_basis="point",
        disclaimer="Hash-locked and ITAA-bound — defensible to a buyer.",
    ),
}


def derive_valuation_presentation(data_tier: str | None) -> ValuationPresentation:
    """The honest presentation contract for a computed valuation, keyed off its
    ``data_tier``.

    Pure + total: any unknown, empty, or missing tier falls back to the most
    conservative ``indicative`` presentation (a range, no false-precision point),
    so a labeling gap can never *over*-state confidence.
    """
    key = (data_tier or "").strip().lower()
    return _PRESENTATION.get(key, _PRESENTATION[INDICATIVE])


# The contract above is ALWAYS emitted (additive, inert). This flag separately gates
# whether outward-facing RENDER surfaces ENFORCE it — i.e. actually suppress the
# false-precision point for indicative valuations. Default OFF: the outward-facing copy
# change waits for a brand-oath copy review before going live, the same dark-launch
# discipline as the lifecycle stage flags (LIFECYCLE_STAGE_ENABLED). Building the
# enforcement is not the same as turning it on.
_RENDER_FLAG_ENV = "VALUATION_HONEST_PRESENTATION_ENABLED"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def honest_presentation_render_enabled() -> bool:
    """Whether render surfaces should enforce the presentation contract (headline the
    range, not a point, for ``indicative`` valuations). Off unless the env flag is
    explicitly truthy, so report copy never changes until a deliberate promotion."""
    return os.getenv(_RENDER_FLAG_ENV, "").strip().lower() in _TRUTHY
