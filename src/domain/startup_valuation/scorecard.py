"""Bill Payne Scorecard Method (Upswitch 5-factor variant).

Compares the target startup against the average funded startup in the
region using **five** weighted defensibility factors.  The weighted sum
is applied as a multiplier to the regional average pre-money valuation.

Each slider is a 0-100 score where 50 = "average peer", 100 = "150% of
average peer" and 0 = "50% of average peer".  This matches Bill Payne's
1.5x / 0.5x bands.

**Why 5 factors, not 7?** The canonical Bill Payne 7-factor scorecard
includes ``management_strength`` (0.30 weight) and ``product_rollout``
(0.15 weight). In the Upswitch blend we already price both of those
qualifications in the **Berkus** leg (`management_strength` is one of
Berkus's 5 milestones; `product_rollout` is another).  Keeping them in
the Scorecard would double-count those qualifications in the headline:
once via Berkus's evidence-graded contribution and again as a Scorecard
multiplier shift on the regional median.

We therefore drop ``management_strength`` and ``product_rollout`` from
the Scorecard weight matrix and renormalise the remaining 5 factors to
sum to 1.0.  The wizard's ``ScorecardStep`` already exposes only these 5
to the founder, so the surface and the math are now aligned.

The renormalisation preserves the relative ordering Bill Payne assigned
to the 5 surviving factors:

    opportunity_size:                0.25 → 0.45  (largest)
    competitive_environment:         0.10 → 0.20
    sales_marketing_channels:        0.10 → 0.20
    need_for_additional_funding:     0.05 → 0.075
    other_factors:                   0.05 → 0.075

Bottom-line behaviour:
    * All sliders at 50  → blended_multiplier = 1.00× (matches peer median)
    * All sliders at 100 → blended_multiplier = 1.50× (top of band)
    * All sliders at 0   → blended_multiplier = 0.50× (floor of band)
"""

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import List, Mapping

from .money import LegResult, ZERO, q_eur, q_rate, sum_decimals
from .schemas import StartupInputs

#: Frozen weight matrix — Upswitch 5-factor scorecard.  See module
#: docstring for the rationale on dropping ``management_strength`` and
#: ``product_rollout`` (priced by Berkus, not Scorecard).
SCORECARD_WEIGHTS: Mapping[str, Decimal] = MappingProxyType(
    {
        "opportunity_size": Decimal("0.45"),
        "competitive_environment": Decimal("0.20"),
        "sales_marketing_channels": Decimal("0.20"),
        "need_for_additional_funding": Decimal("0.075"),
        "other_factors": Decimal("0.075"),
    }
)

SCORECARD_LABELS: Mapping[str, str] = MappingProxyType(
    {
        "opportunity_size": "Size of the opportunity",
        "competitive_environment": "Competitive environment",
        "sales_marketing_channels": "Sales / marketing channels",
        "need_for_additional_funding": "Need for additional funding",
        "other_factors": "Other factors",
    }
)

SCORECARD_LEG_LABEL: str = "Scorecard (Bill Payne)"

#: Bill Payne's published 0.5x..1.5x band — codified once so the
#: linear interpolation stays grep-able.
_MULTIPLIER_FLOOR: Decimal = Decimal("0.5")
_MULTIPLIER_PER_PCT: Decimal = Decimal("0.01")


@dataclass(frozen=True)
class ScorecardFactor:
    """One row in the scorecard breakdown."""

    key: str
    label: str
    score_pct: int
    weight: Decimal
    multiplier: Decimal
    weighted_multiplier: Decimal


@dataclass(frozen=True)
class ScorecardOutput:
    """Scorecard method output."""

    pre_money: Decimal
    average_pre_money: Decimal
    blended_multiplier: Decimal
    factors: List[ScorecardFactor]

    def to_leg_result(self) -> LegResult:
        """Adapt to the unified :class:`LegResult` consumed by synthesis."""
        return LegResult(
            key="scorecard",
            label=SCORECARD_LEG_LABEL,
            pre_money=self.pre_money,
            available=self.pre_money > ZERO,
            assumptions={
                "average_pre_money": self.average_pre_money,
                "blended_multiplier": self.blended_multiplier,
            },
        )


def _score_to_multiplier(score_pct: int) -> Decimal:
    """Map a 0-100 slider to Bill Payne's 0.5x..1.5x peer-comparison band.

    Score 0   -> 0.50x  (half of average peer)
    Score 50  -> 1.00x  (matches average peer)
    Score 100 -> 1.50x  (150% of average peer)
    """
    return q_rate(_MULTIPLIER_FLOOR + Decimal(score_pct) * _MULTIPLIER_PER_PCT)


def calculate_scorecard(
    inputs: StartupInputs,
    *,
    average_pre_money: Decimal,
) -> ScorecardOutput:
    """Compute the Scorecard pre-money valuation.

    pre_money = average_pre_money * Σ(weight_i * multiplier_i)
    """
    factors: List[ScorecardFactor] = []

    for key, weight in SCORECARD_WEIGHTS.items():
        score = int(getattr(inputs, key))
        multiplier = _score_to_multiplier(score)
        weighted = q_rate(weight * multiplier)
        factors.append(
            ScorecardFactor(
                key=key,
                label=SCORECARD_LABELS[key],
                score_pct=score,
                weight=weight,
                multiplier=multiplier,
                weighted_multiplier=weighted,
            )
        )

    blended_multiplier = q_rate(sum_decimals(f.weighted_multiplier for f in factors))
    pre_money = q_eur(q_eur(average_pre_money) * blended_multiplier)

    return ScorecardOutput(
        pre_money=pre_money,
        average_pre_money=q_eur(average_pre_money),
        blended_multiplier=blended_multiplier,
        factors=factors,
    )
