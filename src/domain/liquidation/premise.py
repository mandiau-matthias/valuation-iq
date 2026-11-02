"""Scenario references requiring review; financial screens cannot elect a premise."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .distress_probability import DistressAssessment, DistressZone

PREMISE_SOURCES = ("IVSC Standards Glossary — premise of value and forced sale",)


class PremiseOfValue(str, Enum):
    GOING_CONCERN = "going_concern"
    ORDERLY_LIQUIDATION = "orderly_liquidation"
    FORCED_LIQUIDATION = "forced_liquidation"


class PremiseSelectionTrigger(str, Enum):
    DISTRESS_SCORE = "distress_score"
    BALANCE_SHEET_INSOLVENT = "balance_sheet_insolvent"
    OWNER_OVERRIDE = "owner_override"
    DEFAULT_GOING_CONCERN = "default_going_concern"


@dataclass(frozen=True)
class PremiseDecision:
    primary: PremiseOfValue
    secondary: PremiseOfValue
    probability_of_distress: None
    going_concern_weight: None
    liquidation_weight: None
    trigger: PremiseSelectionTrigger
    rationale: str
    sources: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "assessment_status": "scenario_reference_requires_review",
            "primary": self.primary.value,
            "secondary": self.secondary.value,
            "probability_of_distress": None,
            "going_concern_weight": None,
            "liquidation_weight": None,
            "trigger": self.trigger.value,
            "rationale": self.rationale,
            "sources": list(self.sources),
        }


def select_premise(
    *,
    distress: DistressAssessment | None,
    is_insolvent: bool,
    owner_override: PremiseOfValue | None = None,
) -> PremiseDecision:
    """Suggest a comparison lens, never a court/liquidity determination.

    A shortfall against haircut asset values does not prove a forced sale.
    An explicit override is disclosed as a scenario assumption. No score
    or absent data creates probability weights or an expected value.
    """
    primary = PremiseOfValue.GOING_CONCERN
    trigger = PremiseSelectionTrigger.DEFAULT_GOING_CONCERN
    rationale = "Going-concern comparison pending review; financial screen unavailable."
    if owner_override is not None:
        primary = owner_override
        trigger = PremiseSelectionTrigger.OWNER_OVERRIDE
        rationale = "Explicit owner/advisor override is a scenario assumption requiring review."
    elif is_insolvent:
        primary = PremiseOfValue.ORDERLY_LIQUIDATION
        trigger = PremiseSelectionTrigger.BALANCE_SHEET_INSOLVENT
        rationale = (
            "Liquidation asset shortfall requires review of funding, obligations and sale conditions; "
            "it does not establish legal insolvency or a forced sale."
        )
    elif distress is not None and distress.available:
        trigger = PremiseSelectionTrigger.DISTRESS_SCORE
        if distress.zone is DistressZone.DISTRESS:
            primary = PremiseOfValue.ORDERLY_LIQUIDATION
        rationale = "Financial screen suggests a comparison lens only; the valuation premise requires advisor review."
    secondary = (
        PremiseOfValue.ORDERLY_LIQUIDATION
        if primary is PremiseOfValue.GOING_CONCERN
        else PremiseOfValue.GOING_CONCERN
    )
    return PremiseDecision(
        primary=primary,
        secondary=secondary,
        probability_of_distress=None,
        going_concern_weight=None,
        liquidation_weight=None,
        trigger=trigger,
        rationale=rationale,
        sources=PREMISE_SOURCES,
    )


def expected_value(
    *,
    going_concern_value: Decimal,
    liquidation_value: Decimal,
    decision: PremiseDecision,
) -> None:
    """Legacy callable retained fail-closed until a calibrated, basis-aligned contract exists."""
    return None
