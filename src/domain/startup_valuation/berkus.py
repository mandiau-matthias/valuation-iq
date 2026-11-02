"""Berkus Method — Dave Berkus' qualitative pre-revenue valuation.

Five risk-reduction milestones, each scored 0-100 by the founder, scale a
per-milestone cap (default €500k = €2.5M total).  The output is the sum
of contributions plus a per-milestone breakdown for the report.

All arithmetic flows through :mod:`.money` so EUR amounts share the same
quantization across every leg.  Pure function, no shared state — safe to
call concurrently.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import List

from .money import LegResult, ONE_HUNDRED, q_eur, sum_decimals
from .schemas import StartupInputs

BERKUS_MILESTONES: List[str] = [
    "sound_idea",
    "prototype_status",
    "management_strength",
    "strategic_relationships",
    "product_rollout",
]

BERKUS_LABELS = {
    "sound_idea": "Sound idea (basic value)",
    "prototype_status": "Prototype (technology risk)",
    "management_strength": "Quality management team (execution risk)",
    "strategic_relationships": "Strategic relationships (market risk)",
    "product_rollout": "Product rollout / first sales (production risk)",
}

BERKUS_LEG_LABEL: str = "Berkus Method"


@dataclass(frozen=True)
class BerkusContribution:
    """Per-milestone Berkus contribution."""

    key: str
    label: str
    score_pct: int
    max_value: Decimal
    value: Decimal


@dataclass(frozen=True)
class BerkusOutput:
    """Berkus method total + breakdown."""

    pre_money: Decimal
    contributions: List[BerkusContribution]
    max_per_milestone: Decimal
    max_total: Decimal

    def to_leg_result(self) -> LegResult:
        """Adapt to the unified :class:`LegResult` consumed by synthesis."""
        return LegResult(
            key="berkus",
            label=BERKUS_LEG_LABEL,
            pre_money=self.pre_money,
            available=self.pre_money > 0,
            assumptions={
                "max_per_milestone": self.max_per_milestone,
                "active_milestones": [
                    c.key for c in self.contributions if c.score_pct >= 60
                ],
            },
        )


def calculate_berkus(
    inputs: StartupInputs,
    *,
    max_per_milestone: Decimal,
) -> BerkusOutput:
    """Compute the Berkus pre-money valuation.

    Each milestone contribution is ``(score / 100) * max_per_milestone``
    so the worst case is €0 and the best case is the full per-milestone cap.
    """
    contributions: List[BerkusContribution] = []
    cap = q_eur(max_per_milestone)

    for key in BERKUS_MILESTONES:
        score = int(getattr(inputs, key))
        weight = Decimal(score) / ONE_HUNDRED
        value = q_eur(cap * weight)
        contributions.append(
            BerkusContribution(
                key=key,
                label=BERKUS_LABELS[key],
                score_pct=score,
                max_value=cap,
                value=value,
            )
        )

    total = q_eur(sum_decimals(c.value for c in contributions))

    return BerkusOutput(
        pre_money=total,
        contributions=contributions,
        max_per_milestone=cap,
        max_total=q_eur(cap * Decimal(len(BERKUS_MILESTONES))),
    )
