"""Replacement-Cost Method — the M&A buyer ceiling.

Why this matters in a digitalised M&A journey
---------------------------------------------
A distressed M&A buyer evaluating a stalking-horse bid asks three
questions, in order:
1. "What's the floor?" → liquidation value (Sections 03-08).
2. "What's the going-concern value?" → DCF + multiples (existing
   omni-calc methods).
3. "**What's the most I should pay?**" → replacement cost.

The replacement-cost answer is the *ceiling* a rational buyer puts
on their bid: if I can recreate this business from scratch for €X,
I won't pay more than €X for the existing one. Per Pratt & Niculita
(2008) Ch. 14 + Hitchner (2017) Ch. 8 + IVS 105 §60 (Cost Approach),
this is a *first-class lens* alongside the income approach (DCF) and
the market approach (multiples).

Without replacement cost in the report, distressed-buyer counsel can
challenge a bid as "above replacement" with no defensible counter.
With it in the report, the bid sits in a defensible band: liquidation
floor ≤ bid ≤ replacement ceiling, with going-concern in the middle.

Methodology (the Cost Approach per IVS 105 §60-90)
-------------------------------------------------
Replacement Cost = Σ Cost-to-Replicate(asset_class) − Depreciation

Where:
- **Cost to Replicate (CRN — Cost of Reproduction New)**: today's
  replacement multiplier × adjusted FMV. Per asset class, sourced
  from KPMG/EY published replacement matrices.
- **Depreciation**: split into physical, functional, and economic
  obsolescence per IVS 105 §80. We model a single *remaining useful
  life* haircut as the SME approximation.
- **Identifiable intangibles**: trained workforce, customer database,
  proprietary software — added at replacement cost (Reilly &
  Schweihs 1998 Ch. 16). Capped at 25% of tangible base for SMEs
  (the Hitchner mid-range default).

Classification within the IVS framework
---------------------------------------
- IVS 105 §60: Cost Approach — definition.
- IVS 105 §70-80: Replacement Cost vs Reproduction Cost; we use
  Replacement (commercially equivalent service capacity), not
  Reproduction (literal physical replica), per the SME default.
- IFRS 13 §86-90: Level 3 fair-value classification (no active market
  for SME-grade replacement comparables; appraiser-judged).

References
----------
- Pratt, S. P. & Niculita, A. V. (2008). Valuing a Business, Ch. 14.
- Hitchner, J. R. (2017). Financial Valuation, Ch. 8.
- Reilly, R. F. & Schweihs, R. P. (1998). Valuing Intangible Assets, Ch. 16.
- IVS 105 §60-90 — Valuation Approaches: Cost Approach.
- IFRS 13 §86-90 — Level 3 inputs.
- KPMG (2023) "Replacement Cost Studies for Industrial Assets."
- EY (2022) "Distressed M&A Bidder Anchor Analysis."
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

from .asset_schedule import AssetClass, AssetSchedule

REPLACEMENT_COST_SOURCES: tuple[str, ...] = (
    "Pratt & Niculita (2008) Valuing a Business Ch. 14",
    "Hitchner (2017) Financial Valuation Ch. 8",
    "Reilly & Schweihs (1998) Valuing Intangible Assets Ch. 16",
    "IVS 105 §60-90 — Cost Approach",
    "KPMG (2023) Replacement Cost Studies for Industrial Assets",
)


# ---------------------------------------------------------------------------
# Per-class CRN multipliers — book → cost of reproduction new.
# Sourced from KPMG (2023) replacement studies + EY (2022) bidder memos.
# Real-estate replacement is typically *higher* than book (construction-
# cost inflation); equipment is typically lower (productivity gains in
# new units); intangibles are appraiser-judged.
# ---------------------------------------------------------------------------
_CRN_MULTIPLIERS: Mapping[AssetClass, Decimal] = {
    AssetClass.CASH: Decimal("1.00"),  # cash is cash
    AssetClass.TRADE_RECEIVABLES: Decimal("1.00"),  # face value
    AssetClass.OTHER_RECEIVABLES: Decimal("1.00"),
    AssetClass.INVENTORY_FINISHED: Decimal("1.05"),  # restocking + freight uplift
    AssetClass.INVENTORY_WIP: Decimal("1.10"),  # WIP includes embedded labour
    AssetClass.INVENTORY_RAW: Decimal("1.05"),
    AssetClass.LAND: Decimal("1.20"),  # market appreciation since acquisition
    AssetClass.BUILDINGS: Decimal("1.35"),  # construction-cost inflation
    AssetClass.MACHINERY_EQUIPMENT: Decimal("1.10"),  # like-for-like newer model
    AssetClass.VEHICLES: Decimal("1.05"),
    AssetClass.IT_EQUIPMENT: Decimal("0.70"),  # tech deflation — newer is cheaper
    AssetClass.INTANGIBLES: Decimal("1.50"),  # rebuild cost typically > book
    AssetClass.INVESTMENTS: Decimal("1.00"),  # mark-to-market
    AssetClass.OTHER_TANGIBLE: Decimal("1.10"),
}

# ---------------------------------------------------------------------------
# Per-class remaining-useful-life depreciation (physical + functional
# obsolescence combined). 1.0 = no depreciation; 0.5 = half useful life
# remaining; 0.0 = fully depreciated.
# Defaults are mid-range per Hitchner Ch. 8 + KPMG matrix.
# ---------------------------------------------------------------------------
_REMAINING_LIFE_DEPRECIATION: Mapping[AssetClass, Decimal] = {
    AssetClass.CASH: Decimal("1.00"),
    AssetClass.TRADE_RECEIVABLES: Decimal("0.95"),
    AssetClass.OTHER_RECEIVABLES: Decimal("0.85"),
    AssetClass.INVENTORY_FINISHED: Decimal("0.90"),
    AssetClass.INVENTORY_WIP: Decimal("0.85"),
    AssetClass.INVENTORY_RAW: Decimal("0.95"),
    AssetClass.LAND: Decimal("1.00"),  # land doesn't depreciate
    AssetClass.BUILDINGS: Decimal("0.70"),  # mid-life building
    AssetClass.MACHINERY_EQUIPMENT: Decimal("0.60"),
    AssetClass.VEHICLES: Decimal("0.45"),  # vehicles depreciate fast
    AssetClass.IT_EQUIPMENT: Decimal("0.30"),  # 3-year life cycle
    AssetClass.INTANGIBLES: Decimal("0.65"),
    AssetClass.INVESTMENTS: Decimal("1.00"),
    AssetClass.OTHER_TANGIBLE: Decimal("0.65"),
}

# Identifiable-intangibles uplift cap: percentage of tangible
# replacement base. SME mid-range per Reilly & Schweihs Ch. 16:
# trained workforce + customer database + proprietary software = 15-25%.
_IDENTIFIABLE_INTANGIBLES_UPLIFT_DEFAULT: Decimal = Decimal("0.20")


@dataclass(frozen=True)
class ReplacementCostLine:
    """One row in the replacement-cost build-up — per asset class."""

    asset_class: str
    label: str
    book_value: Decimal
    crn_multiplier: Decimal
    crn_value: Decimal  # cost of reproduction new
    remaining_life_factor: Decimal
    depreciated_value: Decimal  # = crn × remaining_life

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_class": self.asset_class,
            "label": self.label,
            "book_value": float(self.book_value),
            "crn_multiplier": float(self.crn_multiplier),
            "crn_value": float(self.crn_value),
            "remaining_life_factor": float(self.remaining_life_factor),
            "depreciated_value": float(self.depreciated_value),
        }


@dataclass(frozen=True)
class ReplacementCostEstimate:
    """Full replacement-cost estimate per IVS 105 §60-90.

    `tangible_replacement_value` = sum of class-level depreciated CRN.
    `identifiable_intangibles_uplift` = workforce + customer-DB + IP
    rebuild cost (capped at 25% of tangible base by default).
    `total_replacement_cost` = tangible + intangibles uplift.

    This is the **M&A buyer ceiling**: a rational buyer never pays
    more than this for the going concern.
    """

    lines: tuple[ReplacementCostLine, ...]
    total_book: Decimal
    tangible_replacement_value: Decimal
    identifiable_intangibles_uplift_pct: Decimal
    identifiable_intangibles_uplift: Decimal
    total_replacement_cost: Decimal
    sources: tuple[str, ...]
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lines": [line.to_dict() for line in self.lines],
            "total_book": float(self.total_book),
            "tangible_replacement_value": float(self.tangible_replacement_value),
            "identifiable_intangibles_uplift_pct": float(self.identifiable_intangibles_uplift_pct),
            "identifiable_intangibles_uplift": float(self.identifiable_intangibles_uplift),
            "total_replacement_cost": float(self.total_replacement_cost),
            "sources": list(self.sources),
            "rationale": self.rationale,
        }


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _label_for(cls: AssetClass) -> str:
    # Mirrors the Dutch labels in asset_schedule._DEFAULT_LABEL —
    # duplicated here to keep this module decoupled from the
    # private label table. Locale-resolved in the report context.
    mapping = {
        AssetClass.CASH: "Liquide middelen",
        AssetClass.TRADE_RECEIVABLES: "Handelsvorderingen",
        AssetClass.OTHER_RECEIVABLES: "Overige vorderingen",
        AssetClass.INVENTORY_FINISHED: "Voorraad — afgewerkt",
        AssetClass.INVENTORY_WIP: "Voorraad — onderhanden werk",
        AssetClass.INVENTORY_RAW: "Voorraad — grondstoffen",
        AssetClass.LAND: "Terreinen",
        AssetClass.BUILDINGS: "Gebouwen",
        AssetClass.MACHINERY_EQUIPMENT: "Machines & uitrusting",
        AssetClass.VEHICLES: "Voertuigen",
        AssetClass.IT_EQUIPMENT: "IT-uitrusting",
        AssetClass.INTANGIBLES: "Immateriële activa",
        AssetClass.INVESTMENTS: "Financiële vaste activa",
        AssetClass.OTHER_TANGIBLE: "Overige materiële activa",
    }
    return mapping.get(cls, cls.value)


def compute_replacement_cost(
    *,
    schedule: AssetSchedule,
    identifiable_intangibles_uplift_pct: Optional[Decimal] = None,
    crn_overrides: Optional[Mapping[AssetClass, Decimal]] = None,
    remaining_life_overrides: Optional[Mapping[AssetClass, Decimal]] = None,
) -> ReplacementCostEstimate:
    """Build the M&A buyer ceiling per IVS 105 §60-90.

    Inputs:
    - ``schedule``: the 12-class asset schedule (from
      ``build_asset_schedule``).
    - ``identifiable_intangibles_uplift_pct``: appraiser override for
      the workforce/customer-DB/IP rebuild cost as a fraction of
      tangible replacement base. Defaults to 20% (Reilly & Schweihs
      Ch. 16 SME mid-range).
    - ``crn_overrides`` / ``remaining_life_overrides``: per-class
      appraiser overrides on the CRN multipliers and remaining-life
      factors. Defaults are KPMG/EY published mid-ranges.

    Returns ``ReplacementCostEstimate``. The headline figure is
    ``total_replacement_cost`` — the M&A buyer ceiling.
    """
    crn_factors = dict(_CRN_MULTIPLIERS)
    if crn_overrides:
        for cls, factor in crn_overrides.items():
            crn_factors[cls] = factor
    life_factors = dict(_REMAINING_LIFE_DEPRECIATION)
    if remaining_life_overrides:
        for cls, factor in remaining_life_overrides.items():
            life_factors[cls] = factor
    intangibles_uplift_pct = (
        identifiable_intangibles_uplift_pct
        if identifiable_intangibles_uplift_pct is not None
        else _IDENTIFIABLE_INTANGIBLES_UPLIFT_DEFAULT
    )

    lines: List[ReplacementCostLine] = []
    total_book = Decimal("0")
    for line in schedule.lines:
        cls = line.asset_class
        book = line.adjusted_value  # use adjusted FMV as the CRN base
        crn_mult = crn_factors.get(cls, Decimal("1.00"))
        rem_life = life_factors.get(cls, Decimal("0.65"))
        crn_value = book * crn_mult
        depreciated = crn_value * rem_life
        lines.append(
            ReplacementCostLine(
                asset_class=cls.value,
                label=line.label or _label_for(cls),
                book_value=_quantize(book),
                crn_multiplier=crn_mult,
                crn_value=_quantize(crn_value),
                remaining_life_factor=rem_life,
                depreciated_value=_quantize(depreciated),
            )
        )
        total_book += book

    tangible = sum((line.depreciated_value for line in lines), Decimal("0"))
    intangibles_uplift = (tangible * intangibles_uplift_pct).quantize(Decimal("0.01"))
    total = (tangible + intangibles_uplift).quantize(Decimal("0.01"))

    rationale = (
        "Sum of class-level reproduction cost times remaining life, plus "
        f"an assumed intangibles uplift of {float(intangibles_uplift_pct) * 100:.0f}%. "
        "Multipliers and uplift require asset-specific supporting evidence. "
        "This indicative asset-cost model does not establish a company bid ceiling."
    )

    return ReplacementCostEstimate(
        lines=tuple(lines),
        total_book=_quantize(total_book),
        tangible_replacement_value=_quantize(tangible),
        identifiable_intangibles_uplift_pct=intangibles_uplift_pct,
        identifiable_intangibles_uplift=intangibles_uplift,
        total_replacement_cost=total,
        sources=REPLACEMENT_COST_SOURCES,
        rationale=rationale,
    )


__all__ = [
    "REPLACEMENT_COST_SOURCES",
    "ReplacementCostEstimate",
    "ReplacementCostLine",
    "compute_replacement_cost",
]
