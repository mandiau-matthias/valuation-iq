"""Legacy illustrative buyer heuristics, excluded from live valuation reports.

The preset premiums below are not calibrated buyer willingness-to-pay estimates.
They remain available for legacy research callers. The liquidation orchestrator
withholds this pack until assumptions and valuation bases are substantiated.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

STRATEGIC_BUYER_SOURCES: tuple[str, ...] = (
    "Koller/Goedhart/Wessels (McKinsey 2020) Valuation 7th ed. Ch. 18 + 35",
    "Damodaran (2012) Investment Valuation Ch. 24 — synergy + control",
    "Bain & Co (2023) Distressed M&A — Buyer Profiles",
    "KPMG (2022) Stalking-Horse Bid Anchoring Memo",
)


class BuyerProfile(str, Enum):
    """Three canonical distressed-M&A buyer types."""

    FINANCIAL = "financial"  # PE / distressed-debt fund
    STRATEGIC = "strategic"  # industry incumbent
    MBO = "mbo"  # management buyout


@dataclass(frozen=True)
class BuyerScenario:
    """One canonical buyer scenario — bid range + rationale."""

    profile: BuyerProfile
    label_nl: str
    label_en: str
    bid_floor: Decimal
    bid_anchor: Decimal  # mid-point — the negotiation anchor
    bid_ceiling: Decimal
    floor_multiplier_of_lv: Decimal  # × LV-net
    ceiling_multiplier_of_lv: Decimal  # × LV-net
    rationale_nl: str
    rationale_en: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile": self.profile.value,
            "label_nl": self.label_nl,
            "label_en": self.label_en,
            "bid_floor": float(self.bid_floor),
            "bid_anchor": float(self.bid_anchor),
            "bid_ceiling": float(self.bid_ceiling),
            "floor_multiplier_of_lv": float(self.floor_multiplier_of_lv),
            "ceiling_multiplier_of_lv": float(self.ceiling_multiplier_of_lv),
            "rationale_nl": self.rationale_nl,
            "rationale_en": self.rationale_en,
        }


@dataclass(frozen=True)
class StrategicBuyerScenarios:
    """The three-buyer pack — financial / strategic / MBO."""

    scenarios: tuple[BuyerScenario, ...]
    base_lv_net: Decimal  # the liquidation floor anchor
    base_going_concern: Optional[Decimal]
    base_replacement_cost: Optional[Decimal]
    rationale: str
    sources: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment_status": "illustrative_unvalidated",
            "scenarios": [s.to_dict() for s in self.scenarios],
            "base_lv_net": float(self.base_lv_net),
            "base_going_concern": (
                float(self.base_going_concern) if self.base_going_concern is not None else None
            ),
            "base_replacement_cost": (
                float(self.base_replacement_cost)
                if self.base_replacement_cost is not None
                else None
            ),
            "rationale": self.rationale,
            "sources": list(self.sources),
        }


# Empirical multiplier ranges per Bain (2023) public distressed-M&A
# deal data + KPMG stalking-horse memos. Calibrated for SME deals
# €500k-€20M range.
_FINANCIAL_FLOOR_MULT: Decimal = Decimal("1.05")
_FINANCIAL_CEILING_MULT: Decimal = Decimal("1.15")

# Strategic buyer ceiling reaches into replacement-cost territory
# when synergy/goodwill capture justifies it.
_STRATEGIC_PREMIUM_OVER_GC: Decimal = Decimal("0.10")  # 10% above GC mid
_STRATEGIC_CEILING_PREMIUM: Decimal = Decimal("0.25")  # 25% above GC

# MBO sits between floor and going-concern, with a continuity discount.
_MBO_MIDPOINT_DISCOUNT: Decimal = Decimal("0.10")  # 10% off the LV+GC midpoint


def _quantize(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"))


def _financial_buyer(lv_net: Decimal) -> BuyerScenario:
    floor = _quantize(lv_net * _FINANCIAL_FLOOR_MULT)
    ceiling = _quantize(lv_net * _FINANCIAL_CEILING_MULT)
    anchor = _quantize((floor + ceiling) / 2)
    return BuyerScenario(
        profile=BuyerProfile.FINANCIAL,
        label_nl="Financiële koper (PE / distressed-debt fonds)",
        label_en="Financial buyer (PE / distressed-debt fund)",
        bid_floor=floor,
        bid_anchor=anchor,
        bid_ceiling=ceiling,
        floor_multiplier_of_lv=_FINANCIAL_FLOOR_MULT,
        ceiling_multiplier_of_lv=_FINANCIAL_CEILING_MULT,
        rationale_nl=(
            "PE/distressed-debt funds maximaliseren IRR op ingelegd "
            "kapitaal. Bod ligt typisch 5-15% boven de liquidatie-"
            "vloer; goodwill en immateriële activa worden agressief "
            "gestripped. Bain (2023) distressed-M&A dealset midpoint."
        ),
        rationale_en=(
            "PE/distressed-debt funds maximise IRR on deployed capital. "
            "Bid typically 5-15% above the liquidation floor; goodwill "
            "and intangibles are aggressively stripped. Bain (2023) "
            "distressed-M&A dataset midpoint."
        ),
    )


def _strategic_buyer(
    lv_net: Decimal,
    going_concern: Optional[Decimal],
    replacement_cost: Optional[Decimal],
) -> BuyerScenario:
    """Strategic buyer: pays a premium ABOVE going-concern when there's
    synergy. Floor anchored at GC × (1+10%); ceiling at GC × (1+25%) or
    replacement cost, whichever lower (the buyer would never pay above
    replacement)."""
    if going_concern is not None and going_concern > 0:
        floor = _quantize(going_concern * (Decimal("1") + _STRATEGIC_PREMIUM_OVER_GC))
        ceiling_uncapped = _quantize(going_concern * (Decimal("1") + _STRATEGIC_CEILING_PREMIUM))
        # Cap at replacement cost when available — a rational strategic
        # buyer never pays above replacement (they'd build instead).
        if replacement_cost is not None and replacement_cost > 0:
            ceiling = min(ceiling_uncapped, replacement_cost)
        else:
            ceiling = ceiling_uncapped
        floor_mult = (floor / lv_net).quantize(Decimal("0.0001")) if lv_net > 0 else Decimal("0")
        ceiling_mult = (
            (ceiling / lv_net).quantize(Decimal("0.0001")) if lv_net > 0 else Decimal("0")
        )
    else:
        # No going-concern figure — fall back to replacement cost or 2× LV.
        if replacement_cost is not None and replacement_cost > 0:
            ceiling = replacement_cost
        else:
            ceiling = _quantize(lv_net * Decimal("2.0"))
        floor = _quantize(ceiling * Decimal("0.85"))
        floor_mult = (floor / lv_net).quantize(Decimal("0.0001")) if lv_net > 0 else Decimal("0")
        ceiling_mult = (
            (ceiling / lv_net).quantize(Decimal("0.0001")) if lv_net > 0 else Decimal("0")
        )
    anchor = _quantize((floor + ceiling) / 2)
    return BuyerScenario(
        profile=BuyerProfile.STRATEGIC,
        label_nl="Strategische koper (sectorgenoot, verticale integrator)",
        label_en="Strategic buyer (industry incumbent, vertical integrator)",
        bid_floor=floor,
        bid_anchor=anchor,
        bid_ceiling=ceiling,
        floor_multiplier_of_lv=floor_mult,
        ceiling_multiplier_of_lv=ceiling_mult,
        rationale_nl=(
            "Een strategische koper betaalt 10-25% premie boven going-"
            "concern wanneer specifieke synergie (klantenbestand, "
            "productlijn, geografie) dat rechtvaardigt. Plafond gecapd "
            "op replacement cost — een rationele strategische koper "
            "bouwt liever zelf op dan boven replacement te betalen "
            "(McKinsey Ch. 18 + Damodaran Ch. 24)."
        ),
        rationale_en=(
            "A strategic buyer pays a 10-25% premium above going-"
            "concern when specific synergy (customer book, product "
            "line fit, geography) justifies it. Ceiling capped at "
            "replacement cost — a rational strategic never pays above "
            "replacement (McKinsey Ch. 18 + Damodaran Ch. 24)."
        ),
    )


def _mbo_buyer(lv_net: Decimal, going_concern: Optional[Decimal]) -> BuyerScenario:
    """MBO: midpoint of LV-net and going-concern, with 10% continuity
    discount. When no GC is available, fall back to LV × 1.20."""
    if going_concern is not None and going_concern > 0:
        midpoint = _quantize((lv_net + going_concern) / 2)
        anchor = _quantize(midpoint * (Decimal("1") - _MBO_MIDPOINT_DISCOUNT))
        floor = _quantize(anchor * Decimal("0.90"))
        ceiling = _quantize(anchor * Decimal("1.10"))
    else:
        anchor = _quantize(lv_net * Decimal("1.20"))
        floor = _quantize(lv_net * Decimal("1.10"))
        ceiling = _quantize(lv_net * Decimal("1.30"))
    floor_mult = (floor / lv_net).quantize(Decimal("0.0001")) if lv_net > 0 else Decimal("0")
    ceiling_mult = (ceiling / lv_net).quantize(Decimal("0.0001")) if lv_net > 0 else Decimal("0")
    return BuyerScenario(
        profile=BuyerProfile.MBO,
        label_nl="Management Buy-Out (intern team, mezzanine-financiering)",
        label_en="Management Buy-Out (internal team, mezzanine-funded)",
        bid_floor=floor,
        bid_anchor=anchor,
        bid_ceiling=ceiling,
        floor_multiplier_of_lv=floor_mult,
        ceiling_multiplier_of_lv=ceiling_mult,
        rationale_nl=(
            "MBO ligt typisch op het midpoint van liquidatievloer en "
            "going-concern, met 10% continuïteits-discount voor "
            "key-person risico. Financiering meestal mezzanine + "
            "vendor loans — de prijs reflecteert wat het team kan "
            "lenen, niet wat de business waard is voor een derde "
            "(Bain 2023)."
        ),
        rationale_en=(
            "MBO sits at the midpoint of liquidation floor and going-"
            "concern, with a 10% continuity discount for key-person "
            "risk. Financing is typically mezzanine + vendor loans — "
            "the price reflects what the team can borrow, not what "
            "the business is worth to a third party (Bain 2023)."
        ),
    )


def build_strategic_buyer_scenarios(
    *,
    lv_net: Decimal,
    going_concern: Optional[Decimal] = None,
    replacement_cost: Optional[Decimal] = None,
) -> StrategicBuyerScenarios:
    """Build the three-buyer pack from already-computed Phase 1-4 figures.

    `lv_net` is the post-cascade-post-tax-post-wind-down headline —
    the floor a rational owner accepts. `going_concern` is the
    DCF/multiples figure when the orchestrator has it; `replacement_cost`
    is the M&A buyer ceiling.

    Pure-data reduction. No new math, no race conditions.
    """
    if lv_net <= 0:
        # Pathological: no liquidation floor → fall back to 0 anchors.
        # The report flags this as "no defensible bid scenario."
        zero = Decimal("0.00")
        return StrategicBuyerScenarios(
            scenarios=tuple(),
            base_lv_net=zero,
            base_going_concern=going_concern,
            base_replacement_cost=replacement_cost,
            rationale=(
                "Geen verdedigbare bid-scenarios — liquidatievloer is "
                "0 of negatief. De boedel is uitgeput vóór de "
                "aandeelhouder; geen rationele koper betaalt voor een "
                "schuldvrije onderneming aan haar eigenaar."
            ),
            sources=STRATEGIC_BUYER_SOURCES,
        )

    scenarios = (
        _financial_buyer(lv_net),
        _strategic_buyer(lv_net, going_concern, replacement_cost),
        _mbo_buyer(lv_net, going_concern),
    )

    rationale = (
        "Drie canonieke koperprofielen per McKinsey Ch. 18 + "
        "Damodaran Ch. 24. Bid-band van elke koper afgeleid van "
        "(liquidatievloer, going-concern, replacement cost). "
        "M&A-counsel gebruikt dit als anker bij stalking-horse bid "
        "evaluatie + tegenbod onderhandeling."
    )

    return StrategicBuyerScenarios(
        scenarios=scenarios,
        base_lv_net=_quantize(lv_net),
        base_going_concern=(_quantize(going_concern) if going_concern is not None else None),
        base_replacement_cost=(
            _quantize(replacement_cost) if replacement_cost is not None else None
        ),
        rationale=rationale,
        sources=STRATEGIC_BUYER_SOURCES,
    )


__all__ = [
    "STRATEGIC_BUYER_SOURCES",
    "BuyerProfile",
    "BuyerScenario",
    "StrategicBuyerScenarios",
    "build_strategic_buyer_scenarios",
]
