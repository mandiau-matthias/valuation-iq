"""Defensibility score for the startup valuation report.

Produces a single 0–10 score the report can render on the cover so a
founder (and any reader) immediately knows how *defensible* the headline
pre-money is in front of a sceptical investor — before they read the
methodology breakdown.

The score is the equally-weighted average of five binary / graded
signals chosen to map directly onto the failure modes the consortium
review identified in April 2026:

1. **Headline coherence** — do the contributing legs converge?  Score
   ``1.0`` when the IQR is < 50% of the median; ``0.5`` when the
   outlier policy had to cap one leg; ``0.0`` when the spread is
   wider than 5× even after capping.

2. **Sector consistency** — is the active SaaS Forward leg compatible
   with the founder-picked sector?  ``1.0`` when there is no conflict;
   ``0.0`` when SaaS Forward contributed a non-zero pre-money for a
   non-SaaS-family sector (consumer, hardware, marketplace, etc.).

3. **Pedigree evidence** — for every positive pedigree delta the founder
   claimed, is the corresponding evidence note non-empty?  ``1.0`` when
   all positive claims are evidenced; partial credit proportional to the
   evidenced fraction; ``1.0`` when no positive deltas claimed (no
   penalty for an honest founder).

4. **Forward-looking inputs** — when the VC method contributed, did the
   founder supply the explicit Y5 projection / target ROI / exit
   multiple instead of relying on regional defaults?  ``1.0`` for fully
   founder-supplied; ``0.5`` when one or two were defaulted; ``0.0``
   when the VC method ran entirely on extrapolated regional defaults.
   Returns ``1.0`` (no penalty) when VC didn't contribute at all.

5. **Traction signal** — any of MRR / ARR / signed pilots evidence?
   ``1.0`` when ARR ≥ :data:`STRONG_TRACTION_ARR_THRESHOLD`; ``0.5``
   when ARR is positive but below the pilot-scale threshold *or* when
   MRR > 0 but ARR is missing (younger pre-revenue); ``0.0`` when
   there is no recurring revenue signal at all.  The two-band split
   on ARR exists so a €1k "friends-and-family" trickle doesn't get
   the same "sterke pre-seed tractie" stamp as a real paid-pilot
   cohort — an angel reader will spot the overclaim instantly.

The five sub-scores are surfaced individually so the report can render
a "what would lift this score" widget — the goal is to push the founder
toward a more defensible deck, not to grade them once and forget.

Two grades are also exposed:

* ``letter_grade`` — A / B / C / D, mapped from the 0–10 score.
* ``traffic_light`` — green / yellow / red for the cover badge.

The module is pure-Python and side-effect-free; safe to call from any
worker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, List, Optional, Sequence

from .money import ZERO, q_eur, q_rate, safe_float


# ---------------------------------------------------------------------------
# Score thresholds
# ---------------------------------------------------------------------------

#: Score → letter grade mapping.  Tuned so the median Benelux pre-seed
#: deck (with sound idea, basic prototype, no signed contracts) lands
#: at C/B− and the rare exceptional pre-seed deck (named pilots, signed
#: LOIs, evidenced pedigree) reaches A−/A.
_GRADE_BANDS: Sequence[tuple[Decimal, str]] = (
    (Decimal("8.5"), "A"),
    (Decimal("7.0"), "B"),
    (Decimal("5.0"), "C"),
    (Decimal("0.0"), "D"),
)

#: Traffic-light bands for the cover badge.  Conservative — yellow when
#: any of the five sub-scores is below 0.5 (i.e. a known weakness is
#: present), red only when the composite is below 4 (i.e. multiple
#: weaknesses).  Founders should *never* see green without evidence; the
#: thresholds make that the empirical default rather than the exception.
_TRAFFIC_RED_THRESHOLD: Decimal = Decimal("4.0")
_TRAFFIC_GREEN_THRESHOLD: Decimal = Decimal("7.5")

#: ARR floor above which the traction signal earns full credit + the
#: "sterke pre-seed tractie" stamp.  Below this the leg drops to 0.5
#: with a softened rationale.  €25k anchors to the empirical Benelux
#: pre-seed "first paid pilots" line — under that, an angel reader
#: will (correctly) read a €1k figure as friends-and-family / token
#: revenue rather than commercial validation.
STRONG_TRACTION_ARR_THRESHOLD: Decimal = Decimal("25000")


@dataclass(frozen=True)
class DefensibilityFactor:
    """One component of the composite score, surfaced in the report."""

    key: str
    """Stable machine name for the factor."""

    label: str
    """Human-readable label rendered in the report widget. NL (the
    historical default that downstream callers consume verbatim)."""

    score: Decimal
    """The factor's contribution in ``[0, 1]`` (Decimal-precise)."""

    rationale: str
    """One-line localized explanation rendered next to the factor row.
    NL (historical default)."""

    label_en: str = ""
    """EN twin of :attr:`label`. The report context substitutes this on
    EN renders so an English investor PDF doesn't surface Dutch labels.
    Defaults to empty string for backward compat — callers that pre-date
    the i18n bump still produce a NL-only factor without crashing."""

    rationale_en: str = ""
    """EN twin of :attr:`rationale`. Same substitution + back-compat
    rules as :attr:`label_en`."""


@dataclass(frozen=True)
class DefensibilityScore:
    """Composite defensibility output for a single startup valuation."""

    score_0_10: Decimal
    """Composite score in ``[0, 10]``, banker's-rounded to one decimal."""

    letter_grade: str
    """A / B / C / D — derived from :attr:`score_0_10` via :data:`_GRADE_BANDS`."""

    traffic_light: str
    """One of ``green`` / ``yellow`` / ``red`` for the cover badge."""

    factors: List[DefensibilityFactor] = field(default_factory=list)
    """Per-factor breakdown.  Always five entries in the canonical order
    (headline_coherence, sector_consistency, pedigree_evidence,
    forward_inputs, traction_signal) so the template can render a
    stable table without conditionals."""


# ---------------------------------------------------------------------------
# Per-factor calculators
# ---------------------------------------------------------------------------


def _headline_coherence(
    *,
    median: Decimal,
    iqr: Decimal,
    any_capped: bool,
    contributing_legs: int,
) -> DefensibilityFactor:
    """Score the convergence of the contributing legs.

    Mirrors the consortium review's "Football field is not a range, it's
    a confession" finding: we want IQR < median * 0.5 ⇒ tight, IQR <
    median * 1.5 ⇒ acceptable, anything wider than that ⇒ the legs
    disagree and the headline is fragile.
    """
    if contributing_legs == 0 or median <= ZERO:
        return DefensibilityFactor(
            key="headline_coherence",
            label="Coherentie van de methoden",
            label_en="Method coherence",
            score=Decimal("0"),
            rationale="Geen actieve methodes — geen coherentie meetbaar.",
            rationale_en="No methods active — coherence not measurable.",
        )

    ratio = iqr / median if median > ZERO else Decimal("999")
    if ratio <= Decimal("0.5") and not any_capped:
        score = Decimal("1.0")
        rationale = (
            f"Methoden convergeren strak (IQR {iqr:,.0f} ≤ {ratio * 100:.0f}% van mediaan)."
        )
        rationale_en = (
            f"Methods converge tightly (IQR {iqr:,.0f} ≤ {ratio * 100:.0f}% of median)."
        )
    elif ratio <= Decimal("1.5") or any_capped:
        score = Decimal("0.5")
        if any_capped:
            rationale = (
                "Eén of meer methoden zijn buiten de Tukey-fence afgevlakt; "
                "headline blijft verdedigbaar, maar de spread is breed."
            )
            rationale_en = (
                "One or more methods were flattened beyond the Tukey fence; "
                "the headline stays defensible but the spread is wide."
            )
        else:
            rationale = (
                f"Methoden divergeren matig (IQR {iqr:,.0f} ≈ {ratio * 100:.0f}% van mediaan)."
            )
            rationale_en = (
                f"Methods diverge moderately (IQR {iqr:,.0f} ≈ {ratio * 100:.0f}% of median)."
            )
    else:
        score = Decimal("0.0")
        rationale = (
            f"Methoden divergeren te ver uit elkaar (IQR {iqr:,.0f} ≈ "
            f"{ratio * 100:.0f}% van mediaan); headline is fragiel."
        )
        rationale_en = (
            f"Methods diverge too widely (IQR {iqr:,.0f} ≈ {ratio * 100:.0f}% of "
            "median); the headline is fragile."
        )
    return DefensibilityFactor(
        key="headline_coherence",
        label="Coherentie van de methoden",
        label_en="Method coherence",
        score=score,
        rationale=rationale,
        rationale_en=rationale_en,
    )


def _sector_consistency(
    *,
    sector: str,
    saas_forward_active: bool,
    saas_forward_compatible: bool,
) -> DefensibilityFactor:
    """Score whether the active legs match the founder-picked sector."""
    if not saas_forward_active:
        return DefensibilityFactor(
            key="sector_consistency",
            label="Sector ↔ methode-consistentie",
            label_en="Sector ↔ method consistency",
            score=Decimal("1.0"),
            rationale="Geen sector-gevoelige methoden actief.",
            rationale_en="No sector-sensitive methods active.",
        )
    if saas_forward_compatible:
        return DefensibilityFactor(
            key="sector_consistency",
            label="Sector ↔ methode-consistentie",
            label_en="Sector ↔ method consistency",
            score=Decimal("1.0"),
            rationale=f"SaaS Forward methode is consistent met sector '{sector}'.",
            rationale_en=f"SaaS Forward method is consistent with sector '{sector}'.",
        )
    return DefensibilityFactor(
        key="sector_consistency",
        label="Sector ↔ methode-consistentie",
        label_en="Sector ↔ method consistency",
        score=Decimal("0.0"),
        rationale=(
            f"SaaS Forward methode draagt bij maar sector '{sector}' is "
            "geen recurring-revenue SaaS — methode hoort uitgeschakeld te zijn."
        ),
        rationale_en=(
            f"SaaS Forward method contributes but sector '{sector}' is not "
            "recurring-revenue SaaS — the method should be disabled."
        ),
    )


def _pedigree_evidence(
    *,
    positive_claims: int,
    evidenced_claims: int,
) -> DefensibilityFactor:
    """Score the fraction of positive pedigree claims backed by evidence."""
    if positive_claims == 0:
        return DefensibilityFactor(
            key="pedigree_evidence",
            label="Founder-pedigree onderbouwing",
            label_en="Founder pedigree evidence",
            score=Decimal("1.0"),
            rationale="Geen pedigree-claims — geen onderbouwing nodig.",
            rationale_en="No pedigree claims — no evidence required.",
        )
    fraction = Decimal(evidenced_claims) / Decimal(positive_claims)
    if fraction >= Decimal("1.0"):
        rationale = (
            f"Alle {positive_claims} pedigree-claims zijn met evidence onderbouwd."
        )
        rationale_en = (
            f"All {positive_claims} pedigree claims are backed with evidence."
        )
    elif fraction >= Decimal("0.5"):
        rationale = (
            f"{evidenced_claims}/{positive_claims} pedigree-claims onderbouwd; "
            "voeg LinkedIn / KBO-referenties toe voor de overige."
        )
        rationale_en = (
            f"{evidenced_claims}/{positive_claims} pedigree claims evidenced; "
            "add LinkedIn / KBO references for the remainder."
        )
    else:
        rationale = (
            f"Slechts {evidenced_claims}/{positive_claims} pedigree-claims onderbouwd; "
            "een investeerder zal de pedigree-multiplier aanvechten."
        )
        rationale_en = (
            f"Only {evidenced_claims}/{positive_claims} pedigree claims evidenced; "
            "an investor will challenge the pedigree multiplier."
        )
    return DefensibilityFactor(
        key="pedigree_evidence",
        label="Founder-pedigree onderbouwing",
        label_en="Founder pedigree evidence",
        score=q_rate(fraction),
        rationale=rationale,
        rationale_en=rationale_en,
    )


def _forward_inputs(
    *,
    vc_contributed: bool,
    year5_supplied: bool,
    exit_multiple_supplied: bool,
    target_roi_supplied: bool,
) -> DefensibilityFactor:
    """Score whether the VC method ran on founder-supplied inputs."""
    if not vc_contributed:
        return DefensibilityFactor(
            key="forward_inputs",
            label="VC-methode inputs",
            label_en="VC method inputs",
            score=Decimal("1.0"),
            rationale="VC-methode niet actief — geen forward-looking inputs vereist.",
            rationale_en="VC method not active — no forward-looking inputs required.",
        )
    supplied = sum(
        1
        for flag in (year5_supplied, exit_multiple_supplied, target_roi_supplied)
        if flag
    )
    if supplied == 3:
        return DefensibilityFactor(
            key="forward_inputs",
            label="VC-methode inputs",
            label_en="VC method inputs",
            score=Decimal("1.0"),
            rationale="Y5-projectie, exit-multiple en target-ROI zijn alle drie expliciet opgegeven.",
            rationale_en="Y5 projection, exit multiple and target ROI are all explicitly supplied.",
        )
    if supplied >= 2:
        return DefensibilityFactor(
            key="forward_inputs",
            label="VC-methode inputs",
            label_en="VC method inputs",
            score=Decimal("0.5"),
            rationale=(
                f"{supplied}/3 forward-inputs door oprichter opgegeven; "
                "regionale fallback gebruikt voor de rest."
            ),
            rationale_en=(
                f"{supplied}/3 forward inputs supplied by the founder; "
                "regional fallback used for the remainder."
            ),
        )
    return DefensibilityFactor(
        key="forward_inputs",
        label="VC-methode inputs",
        label_en="VC method inputs",
        score=Decimal("0.0"),
        rationale=(
            "VC-methode draait grotendeels op regionale defaults — "
            "investeerder zal vragen om je eigen Y5-model."
        ),
        rationale_en=(
            "VC method runs largely on regional defaults — "
            "an investor will ask for your own Y5 model."
        ),
    )


#: Engagement-signal thresholds for the active-users bump that layers
#: onto the revenue-based traction score.  Tuned conservatively against
#: Benelux pre-seed cohorts: 100 active accounts is the empirical "more
#: than friends-and-family" line, 1 000 is the "real engagement" line.
#: Below the lower band, active-users adds no credit (we don't reward
#: vanity counts).
ENGAGEMENT_USERS_REAL_THRESHOLD: int = 1_000
ENGAGEMENT_USERS_TOKEN_THRESHOLD: int = 100


def _engagement_bump(active_users: Optional[int]) -> Decimal:
    """Return the additive bump for the active-user signal.

    The bump layers onto the revenue baseline — capped so the composite
    can never exceed 1.0 — and exists so a marketplace / consumer
    founder with real engagement isn't penalised for charging late.
    """
    if active_users is None or active_users <= 0:
        return ZERO
    if active_users >= ENGAGEMENT_USERS_REAL_THRESHOLD:
        return Decimal("0.25")
    if active_users >= ENGAGEMENT_USERS_TOKEN_THRESHOLD:
        return Decimal("0.10")
    return ZERO


def _traction_signal(
    *,
    arr: Optional[Decimal],
    mrr: Optional[Decimal],
    active_users: Optional[int] = None,
) -> DefensibilityFactor:
    """Score the recurring-revenue signal, with an engagement-bump.

    ``active_users`` layers on top of the revenue baseline (it doesn't
    replace it) so a founder with €1k ARR and 500 active users earns
    more credit than a founder with €1k ARR and 5 users — same
    revenue, very different real signal.
    """
    bump = _engagement_bump(active_users)
    users_clause = ""
    users_clause_en = ""
    if bump > ZERO and active_users is not None and active_users > 0:
        users_clause = (
            f" {active_users:,} actieve gebruikers tilt deze score "
            f"met +{(bump * 100):.0f}%."
        )
        users_clause_en = (
            f" {active_users:,} active users lift this score "
            f"by +{(bump * 100):.0f}%."
        )

    if arr is not None and arr > ZERO:
        if arr >= STRONG_TRACTION_ARR_THRESHOLD:
            return DefensibilityFactor(
                key="traction_signal",
                label="Tractie / recurring revenue",
                label_en="Traction / recurring revenue",
                score=Decimal("1.0"),
                rationale=f"ARR €{arr:,.0f} bevestigd — sterke pre-seed tractie.",
                rationale_en=f"ARR €{arr:,.0f} confirmed — strong pre-seed traction.",
            )
        score = min(Decimal("0.5") + bump, Decimal("1.0"))
        return DefensibilityFactor(
            key="traction_signal",
            label="Tractie / recurring revenue",
            label_en="Traction / recurring revenue",
            score=score,
            rationale=(
                f"ARR €{arr:,.0f} — tractie aanwezig, maar onder de pilot-schaal "
                f"(€{STRONG_TRACTION_ARR_THRESHOLD:,.0f}). Een betaalde pilot of "
                "LOI tilt deze score naar volledig." + users_clause
            ),
            rationale_en=(
                f"ARR €{arr:,.0f} — traction present, but below the pilot-scale "
                f"floor (€{STRONG_TRACTION_ARR_THRESHOLD:,.0f}). A paid pilot or "
                "LOI lifts this score to full." + users_clause_en
            ),
        )
    if mrr is not None and mrr > ZERO:
        score = min(Decimal("0.5") + bump, Decimal("1.0"))
        return DefensibilityFactor(
            key="traction_signal",
            label="Tractie / recurring revenue",
            label_en="Traction / recurring revenue",
            score=score,
            rationale=f"MRR €{mrr:,.0f} bevestigd — eerste betalende klanten.{users_clause}",
            rationale_en=f"MRR €{mrr:,.0f} confirmed — first paying customers.{users_clause_en}",
        )
    if active_users is not None and active_users >= ENGAGEMENT_USERS_TOKEN_THRESHOLD:
        # No revenue, but a real engagement signal — give partial credit
        # so a marketplace founder doesn't read 0.0 when the product has
        # genuine usage.
        return DefensibilityFactor(
            key="traction_signal",
            label="Tractie / recurring revenue",
            label_en="Traction / recurring revenue",
            score=bump * Decimal("2"),  # 0.20 at 100+, 0.50 at 1 000+
            rationale=(
                f"{active_users:,} actieve gebruikers — engagement bevestigd "
                "zonder recurring revenue. Een eerste betaalde pilot maakt dit volledig."
            ),
            rationale_en=(
                f"{active_users:,} active users — engagement confirmed "
                "without recurring revenue. A first paid pilot makes this full."
            ),
        )
    return DefensibilityFactor(
        key="traction_signal",
        label="Tractie / recurring revenue",
        label_en="Traction / recurring revenue",
        score=Decimal("0.0"),
        rationale=(
            "Geen MRR/ARR — een ondertekende pilot of LOI verhoogt deze score significant."
        ),
        rationale_en=(
            "No MRR/ARR — a signed pilot or LOI lifts this score significantly."
        ),
    )


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


def _grade(score: Decimal) -> str:
    for threshold, letter in _GRADE_BANDS:
        if score >= threshold:
            return letter
    return "D"


def _traffic_light(score: Decimal, factors: Iterable[DefensibilityFactor]) -> str:
    """Conservative traffic-light: green requires both a high composite
    AND no individual sub-score below 0.5. A single weakness degrades to
    yellow regardless of average."""
    if score < _TRAFFIC_RED_THRESHOLD:
        return "red"
    if score < _TRAFFIC_GREEN_THRESHOLD:
        return "yellow"
    if any(f.score < Decimal("0.5") for f in factors):
        return "yellow"
    return "green"


def calculate_defensibility(
    *,
    median: Decimal,
    iqr: Decimal,
    any_capped: bool,
    contributing_legs: int,
    sector: str,
    saas_forward_active: bool,
    saas_forward_compatible: bool,
    positive_pedigree_claims: int,
    evidenced_pedigree_claims: int,
    vc_contributed: bool,
    year5_supplied: bool,
    exit_multiple_supplied: bool,
    target_roi_supplied: bool,
    arr: Optional[Decimal],
    mrr: Optional[Decimal],
    active_users: Optional[int] = None,
) -> DefensibilityScore:
    """Compute the composite defensibility score for a startup valuation.

    All keyword arguments — no positional — so call-sites read as
    self-documenting evidence.  Returns a frozen :class:`DefensibilityScore`
    safe to drop directly into the report context.
    """
    factors: List[DefensibilityFactor] = [
        _headline_coherence(
            median=median,
            iqr=iqr,
            any_capped=any_capped,
            contributing_legs=contributing_legs,
        ),
        _sector_consistency(
            sector=sector,
            saas_forward_active=saas_forward_active,
            saas_forward_compatible=saas_forward_compatible,
        ),
        _pedigree_evidence(
            positive_claims=positive_pedigree_claims,
            evidenced_claims=evidenced_pedigree_claims,
        ),
        _forward_inputs(
            vc_contributed=vc_contributed,
            year5_supplied=year5_supplied,
            exit_multiple_supplied=exit_multiple_supplied,
            target_roi_supplied=target_roi_supplied,
        ),
        _traction_signal(arr=arr, mrr=mrr, active_users=active_users),
    ]

    raw = sum((f.score for f in factors), start=ZERO)
    composite = (raw / Decimal(len(factors))) * Decimal(10)
    composite = composite.quantize(Decimal("0.1"))
    return DefensibilityScore(
        score_0_10=composite,
        letter_grade=_grade(composite),
        traffic_light=_traffic_light(composite, factors),
        factors=factors,
    )


def defensibility_payload(score: DefensibilityScore) -> dict:
    """Serialize a :class:`DefensibilityScore` for the engine ↔ report boundary.

    Emits both NL (`label` / `rationale`) and EN (`label_en` /
    `rationale_en`) variants per factor.  The report context picks based
    on the founder's locale so an EN investor PDF never surfaces Dutch
    sentences in the defensibility breakdown.
    """
    return {
        "score_0_10": safe_float(score.score_0_10),
        "letter_grade": score.letter_grade,
        "traffic_light": score.traffic_light,
        "factors": [
            {
                "key": f.key,
                "label": f.label,
                "label_en": f.label_en,
                "score": safe_float(f.score),
                "rationale": f.rationale,
                "rationale_en": f.rationale_en,
            }
            for f in score.factors
        ],
    }


__all__ = [
    "DefensibilityFactor",
    "DefensibilityScore",
    "calculate_defensibility",
    "defensibility_payload",
]


# Keep the q_eur symbol re-exported for any downstream caller that
# wants to format a derived euro amount the same way the score does.
_ = q_eur
