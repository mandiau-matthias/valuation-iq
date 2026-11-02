"""Indicative comparison of caller-supplied equity values on a common basis.

The caller must align valuation date, currency and ownership interest.
The ranking buffer is a model assumption, not a standard-mandated test
of viability or legal insolvency. Zero is an observed value.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

from src.domain.asset_nav_core import to_decimal_or_none

RECONCILIATION_SOURCES: tuple[str, ...] = ("IVSC Standards Glossary — premise of value",)


class PremiseRecommendation(str, Enum):
    """Stable codes for the engine's premise recommendation."""

    GOING_CONCERN_DCF = "going_concern_dcf"
    GOING_CONCERN_NAV = "going_concern_nav"
    LIQUIDATION = "liquidation"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class PremiseReconciliation:
    """The four-corner premise reconciliation."""

    liquidation_value: Decimal
    adjusted_nav: Optional[Decimal]
    dcf_value: Optional[Decimal]
    multiples_value: Optional[Decimal]
    going_concern_defensible: None
    recommendation: PremiseRecommendation
    rationale: str
    sources: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "assessment_status": "indicative_equity_comparison",
            "value_basis": "equity_same_interest",
            "liquidation_value": float(self.liquidation_value),
            "adjusted_nav": float(self.adjusted_nav) if self.adjusted_nav is not None else None,
            "dcf_value": float(self.dcf_value) if self.dcf_value is not None else None,
            "multiples_value": (
                float(self.multiples_value) if self.multiples_value is not None else None
            ),
            "going_concern_defensible": self.going_concern_defensible,
            "recommendation": self.recommendation.value,
            "rationale": self.rationale,
            "sources": list(self.sources),
        }


def reconcile_premises(
    *,
    liquidation_value: object,
    adjusted_nav: object = None,
    dcf_value: object = None,
    multiples_value: object = None,
    margin_of_safety: Decimal = Decimal("0.10"),
) -> PremiseReconciliation:
    """Rank supplied equity scenarios; no conclusion on going-concern viability."""
    lv = _equity_amount(liquidation_value)
    if lv is None:
        raise ValueError("A finite nonnegative liquidation equity value is required.")
    if (
        not isinstance(margin_of_safety, Decimal)
        or not margin_of_safety.is_finite()
        or not 0 <= margin_of_safety <= 1
    ):
        raise ValueError("Comparison margin must be between zero and one.")
    nav = _equity_amount(adjusted_nav)
    dcf = _equity_amount(dcf_value)
    mult = _equity_amount(multiples_value)
    comparisons = [v for v in (dcf, mult, nav) if v is not None]
    earnings = [v for v in (dcf, mult) if v is not None]
    highest = max(comparisons, default=None)
    earnings_max = max(earnings, default=None)
    recommendation = PremiseRecommendation.INDETERMINATE
    rationale = "Insufficient or similar comparison values; the premise requires review."
    if highest is not None and lv > highest and lv >= highest * (1 + margin_of_safety):
        recommendation = PremiseRecommendation.LIQUIDATION
        rationale = "Liquidation equity exceeds the supplied comparison values by the model's comparison margin."
    elif (
        nav is not None and earnings_max is not None and nav > earnings_max * (1 + margin_of_safety)
    ):
        recommendation = PremiseRecommendation.GOING_CONCERN_NAV
        rationale = "Adjusted NAV exceeds the supplied earnings-based equity comparisons by the model's comparison margin."
    elif earnings_max is not None and earnings_max > lv:
        recommendation = PremiseRecommendation.GOING_CONCERN_DCF
        rationale = "A supplied earnings-based equity comparison exceeds liquidation equity."
    return PremiseReconciliation(
        liquidation_value=lv,
        adjusted_nav=nav,
        dcf_value=dcf,
        multiples_value=mult,
        going_concern_defensible=None,
        recommendation=recommendation,
        rationale=rationale
        + " This ranking does not establish viability, sale conditions or a transaction price.",
        sources=RECONCILIATION_SOURCES,
    )


def _equity_amount(value: object) -> Decimal | None:
    amount = to_decimal_or_none(value)
    if not isinstance(amount, Decimal) or amount < 0 or amount > Decimal("1e15"):
        return None
    return amount
