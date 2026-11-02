"""Asset schedule — 12-class realisation table per IVS 230 / IFRS 13.

Why 12 classes (and not the 4 the engine uses today)
----------------------------------------------------
Today ``AssetBasedEngine.calculate_liquidation_value`` recovers
``cash``, ``accounts_receivable``, ``inventory`` and lumps everything
else into ``equipment``. That's a credible Pratt-defaults pass; it is
*not* what a Big-4 restructuring practice would put in front of an
auditor. EY's "Statement of Affairs" template, KPMG's "Realisable Value
Analysis" and Deloitte's "Wind-Down Cost Estimate" all decompose to ~12
asset classes, mapped to the line-item granularity that the chart of
accounts (BE MAR class 2 / NL RGS 0.x) actually exposes.

The 12 classes here are the union of those Big-4 templates with the
academic factor tables in Pratt & Niculita (2008), Hitchner (2017), and
Damodaran (2012):

| Class                | BE MAR    | NL RGS    | Recovery sensitivity |
|----------------------|-----------|-----------|----------------------|
| cash                 | 50–58     | 1.1.1     | flat (1.00)          |
| trade_receivables    | 40        | 1.2.1.1   | aging-driven         |
| other_receivables    | 41        | 1.2.1.x   | flat                 |
| inventory_finished   | 33–35     | 1.3.4     | sector-driven        |
| inventory_wip        | 32        | 1.3.3     | sector-driven        |
| inventory_raw        | 30–31     | 1.3.1     | sector-driven        |
| land                 | 22        | 0.2.1.1   | high (real estate)   |
| buildings            | 22        | 0.2.1.2   | high (real estate)   |
| machinery_equipment  | 23        | 0.2.2     | sector-driven        |
| vehicles             | 24        | 0.2.3     | flat                 |
| it_equipment         | 24/25     | 0.2.4     | depreciates fast     |
| intangibles          | 21        | 0.1       | low (rarely sells)   |
| investments          | 28        | 0.3       | mark-to-market       |
| other_tangible       | 26/27     | 0.2.9     | conservative         |

Why this is a separate module from ``factors.py``
-------------------------------------------------
``factors.py`` owns the *recovery rate per class*. This module owns the
*schedule* — how a balance sheet is decomposed into those classes, with
optional override per line, optional aging, and optional disposal-month
hint that Phase 3 will use to PV-discount. Keeping them separate means
sector calibration (Phase 4 / Delphi) plugs in cleanly.

References
----------
- IVS 230 (International Valuation Standards) — Inventory.
- IFRS 13 §82 — Fair Value Measurement: highest and best use.
- IAS 36 §6 — Recoverable amount = max(FVLCD, value in use).
- EY (2022) "Restructuring & Insolvency: Statement of Affairs Template."
- KPMG (2021) "Realisable Value Analysis — Methodology Note."
- Pratt & Niculita (2008) Valuing a Business, Ch. 14 — Asset Methods.
- Hitchner (2017) Financial Valuation, Ch. 8.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

from src.domain.liquidation.decimal_coercion import to_decimal_or_none


class AssetClass(str, Enum):
    """The 12-class taxonomy. Stable codes — surfaced in the report."""

    CASH = "cash"
    TRADE_RECEIVABLES = "trade_receivables"
    OTHER_RECEIVABLES = "other_receivables"
    INVENTORY_FINISHED = "inventory_finished"
    INVENTORY_WIP = "inventory_wip"
    INVENTORY_RAW = "inventory_raw"
    LAND = "land"
    BUILDINGS = "buildings"
    MACHINERY_EQUIPMENT = "machinery_equipment"
    VEHICLES = "vehicles"
    IT_EQUIPMENT = "it_equipment"
    INTANGIBLES = "intangibles"
    INVESTMENTS = "investments"
    OTHER_TANGIBLE = "other_tangible"


# Default recovery factors per (class × scenario). These extend the
# 8-class table in factors.py to the full 12-class schedule. Numbers
# anchored in Pratt&Niculita (2008) Ch. 14 + Hitchner (2017) Ch. 8 +
# EY/KPMG public restructuring reports.
ORDERLY_CLASS_FACTORS: Mapping[AssetClass, Decimal] = {
    AssetClass.CASH: Decimal("1.00"),
    AssetClass.TRADE_RECEIVABLES: Decimal("0.85"),
    AssetClass.OTHER_RECEIVABLES: Decimal("0.70"),
    AssetClass.INVENTORY_FINISHED: Decimal("0.65"),
    AssetClass.INVENTORY_WIP: Decimal("0.40"),  # WIP rarely fetches FG price
    AssetClass.INVENTORY_RAW: Decimal("0.55"),  # raw materials hold value better than WIP
    AssetClass.LAND: Decimal("0.95"),  # land barely discounts in orderly
    AssetClass.BUILDINGS: Decimal("0.85"),
    AssetClass.MACHINERY_EQUIPMENT: Decimal("0.50"),
    AssetClass.VEHICLES: Decimal("0.60"),
    AssetClass.IT_EQUIPMENT: Decimal("0.20"),  # depreciates fast even orderly
    AssetClass.INTANGIBLES: Decimal("0.20"),
    AssetClass.INVESTMENTS: Decimal("0.90"),  # marketable securities
    AssetClass.OTHER_TANGIBLE: Decimal("0.50"),
}

FORCED_CLASS_FACTORS: Mapping[AssetClass, Decimal] = {
    AssetClass.CASH: Decimal("1.00"),
    AssetClass.TRADE_RECEIVABLES: Decimal("0.60"),
    AssetClass.OTHER_RECEIVABLES: Decimal("0.40"),
    AssetClass.INVENTORY_FINISHED: Decimal("0.35"),
    AssetClass.INVENTORY_WIP: Decimal("0.15"),
    AssetClass.INVENTORY_RAW: Decimal("0.30"),
    AssetClass.LAND: Decimal("0.75"),
    AssetClass.BUILDINGS: Decimal("0.65"),
    AssetClass.MACHINERY_EQUIPMENT: Decimal("0.25"),
    AssetClass.VEHICLES: Decimal("0.40"),
    AssetClass.IT_EQUIPMENT: Decimal("0.05"),
    AssetClass.INTANGIBLES: Decimal("0.05"),
    AssetClass.INVESTMENTS: Decimal("0.75"),  # forced sale of securities
    AssetClass.OTHER_TANGIBLE: Decimal("0.25"),
}

# Default disposal-month hint (orderly scenario). Phase 3 PV-discounts
# at the distress WACC over this schedule. Cash is month 0; intangibles
# (if they sell at all) sell last.
ORDERLY_DISPOSAL_MONTH: Mapping[AssetClass, int] = {
    AssetClass.CASH: 0,
    AssetClass.TRADE_RECEIVABLES: 3,
    AssetClass.OTHER_RECEIVABLES: 4,
    AssetClass.INVENTORY_FINISHED: 4,
    AssetClass.INVENTORY_WIP: 6,
    AssetClass.INVENTORY_RAW: 5,
    AssetClass.INVESTMENTS: 1,
    AssetClass.IT_EQUIPMENT: 6,
    AssetClass.VEHICLES: 5,
    AssetClass.MACHINERY_EQUIPMENT: 8,
    AssetClass.BUILDINGS: 10,
    AssetClass.LAND: 10,
    AssetClass.INTANGIBLES: 11,
    AssetClass.OTHER_TANGIBLE: 8,
}

# Forced scenarios compress the timeline — auctioneer typically clears
# everything within 90 days regardless of asset class. Capped at 3.
FORCED_DISPOSAL_MONTH: Mapping[AssetClass, int] = {
    cls: min(month, 3) for cls, month in ORDERLY_DISPOSAL_MONTH.items()
}


@dataclass(frozen=True)
class AssetLine:
    """One row in the 12-class realisation schedule.

    ``book_value`` — what the GL says.
    ``adjusted_value`` — the FMV the appraiser landed on (defaults to
    book if no adjustment supplied; an EY working paper would have a
    column for "book → FMV" with the appraiser's source).
    ``orderly_recovery_factor`` / ``forced_recovery_factor`` — the
    decimal factor applied to ``adjusted_value`` to land on realisable
    value in each scenario.
    """

    asset_class: AssetClass
    book_value: Decimal
    adjusted_value: Decimal
    orderly_recovery_factor: Decimal
    forced_recovery_factor: Decimal
    orderly_disposal_month: int
    forced_disposal_month: int
    label: str = ""  # human-readable, e.g. "Trade receivables (gross)"
    source_account_code: Optional[str] = None  # MAR / RGS code, when known
    rationale: str = ""  # appraiser note (defaults to factor source)

    @property
    def orderly_realisable_value(self) -> Decimal:
        return (self.adjusted_value * self.orderly_recovery_factor).quantize(Decimal("0.01"))

    @property
    def forced_realisable_value(self) -> Decimal:
        return (self.adjusted_value * self.forced_recovery_factor).quantize(Decimal("0.01"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_class": self.asset_class.value,
            "label": self.label,
            "source_account_code": self.source_account_code,
            "book_value": float(self.book_value),
            "adjusted_value": float(self.adjusted_value),
            "orderly_recovery_factor": float(self.orderly_recovery_factor),
            "forced_recovery_factor": float(self.forced_recovery_factor),
            "orderly_realisable_value": float(self.orderly_realisable_value),
            "forced_realisable_value": float(self.forced_realisable_value),
            "orderly_disposal_month": self.orderly_disposal_month,
            "forced_disposal_month": self.forced_disposal_month,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class AssetSchedule:
    """The full 12-class realisation schedule.

    ``unallocated`` is non-zero whenever total_assets reported on the
    balance sheet exceeds the sum of decomposed lines. We treat the
    residual as ``OTHER_TANGIBLE`` with a warning rather than silently
    inflating one of the named classes — silent inflation is the bug
    Big-4 reviewers flag first.
    """

    lines: tuple[AssetLine, ...]
    total_book: Decimal
    total_adjusted: Decimal
    total_orderly_realisable: Decimal
    total_forced_realisable: Decimal
    unallocated_book: Decimal  # diff between balance-sheet total and sum(lines)
    warnings: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lines": [line.to_dict() for line in self.lines],
            "total_book": float(self.total_book),
            "total_adjusted": float(self.total_adjusted),
            "total_orderly_realisable": float(self.total_orderly_realisable),
            "total_forced_realisable": float(self.total_forced_realisable),
            "unallocated_book": float(self.unallocated_book),
            "warnings": list(self.warnings),
            "sources": list(self.sources),
        }


# Map from balance_sheet payload keys → AssetClass. The keys here
# match what hermes/payload_assembly emits as TitanYearData and what
# Venus's manual form puts in `balance_sheet`. Anything not listed
# falls into the unallocated residual.
_BALANCE_SHEET_KEY_TO_CLASS: Mapping[str, AssetClass] = {
    "cash": AssetClass.CASH,
    "accounts_receivable": AssetClass.TRADE_RECEIVABLES,
    "other_receivables": AssetClass.OTHER_RECEIVABLES,
    "inventory": AssetClass.INVENTORY_FINISHED,
    "inventory_finished": AssetClass.INVENTORY_FINISHED,
    "inventory_wip": AssetClass.INVENTORY_WIP,
    "inventory_raw": AssetClass.INVENTORY_RAW,
    "land": AssetClass.LAND,
    "buildings": AssetClass.BUILDINGS,
    "real_estate": AssetClass.BUILDINGS,  # legacy alias
    "machinery_equipment": AssetClass.MACHINERY_EQUIPMENT,
    "equipment": AssetClass.MACHINERY_EQUIPMENT,  # legacy alias
    "vehicles": AssetClass.VEHICLES,
    "it_equipment": AssetClass.IT_EQUIPMENT,
    "intangibles": AssetClass.INTANGIBLES,
    "intangible_assets": AssetClass.INTANGIBLES,
    "investments": AssetClass.INVESTMENTS,
    "financial_assets": AssetClass.INVESTMENTS,
    "other_tangible": AssetClass.OTHER_TANGIBLE,
}


_DEFAULT_LABEL: Mapping[AssetClass, str] = {
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


_FACTOR_SOURCES: tuple[str, ...] = (
    "Pratt & Niculita (2008) Valuing a Business Ch. 14",
    "Hitchner (2017) Financial Valuation Ch. 8",
    "EY (2022) Restructuring & Insolvency: Statement of Affairs",
    "KPMG (2021) Realisable Value Analysis — Methodology Note",
)


def _aggregate_balance_sheet_classes(
    balance_sheet: Mapping[str, object],
) -> Dict[AssetClass, Decimal]:
    seen_classes: Dict[AssetClass, Decimal] = {}
    for bs_key, asset_class in _BALANCE_SHEET_KEY_TO_CLASS.items():
        raw = balance_sheet.get(bs_key)
        amount = to_decimal_or_none(raw)
        if amount is None or amount <= 0:
            continue
        # If two balance-sheet keys map to the same class (e.g. both
        # `inventory` and `inventory_finished`), aggregate.
        seen_classes[asset_class] = seen_classes.get(asset_class, Decimal("0")) + amount
    return seen_classes


def _recovery_factors(
    asset_class: AssetClass,
    override: Mapping[str, object],
) -> tuple[Decimal, Decimal]:
    return (
        to_decimal_or_none(override.get("orderly_recovery_factor"))
        or ORDERLY_CLASS_FACTORS[asset_class],
        to_decimal_or_none(override.get("forced_recovery_factor"))
        or FORCED_CLASS_FACTORS[asset_class],
    )


def _existing_line_disposal_month(
    override: Mapping[str, object],
    key: str,
    default: int,
) -> int:
    raw_month = override.get(key)
    return int(raw_month) if isinstance(raw_month, (int, float)) else default


def _override_line_disposal_month(
    override: Mapping[str, object],
    key: str,
    default: int,
) -> int:
    return int(override.get(key) or default)


def _source_account_code(override: Mapping[str, object]) -> Optional[str]:
    raw_source = override.get("source_account_code")
    return str(raw_source) if raw_source else None


def _asset_line(
    *,
    asset_class: AssetClass,
    book: Decimal,
    adjusted: Decimal,
    override: Mapping[str, object],
    orderly_disposal_month: int,
    forced_disposal_month: int,
    default_rationale: str,
) -> AssetLine:
    orderly_factor, forced_factor = _recovery_factors(asset_class, override)
    return AssetLine(
        asset_class=asset_class,
        book_value=book,
        adjusted_value=adjusted,
        orderly_recovery_factor=orderly_factor,
        forced_recovery_factor=forced_factor,
        orderly_disposal_month=orderly_disposal_month,
        forced_disposal_month=forced_disposal_month,
        label=str(override.get("label") or _DEFAULT_LABEL[asset_class]),
        source_account_code=_source_account_code(override),
        rationale=str(override.get("rationale") or default_rationale),
    )


def _asset_line_from_balance_sheet(
    asset_class: AssetClass,
    book: Decimal,
    override: Mapping[str, object],
) -> AssetLine:
    adjusted = to_decimal_or_none(override.get("adjusted_value")) or book
    return _asset_line(
        asset_class=asset_class,
        book=book,
        adjusted=adjusted,
        override=override,
        orderly_disposal_month=_existing_line_disposal_month(
            override,
            "orderly_disposal_month",
            ORDERLY_DISPOSAL_MONTH[asset_class],
        ),
        forced_disposal_month=_existing_line_disposal_month(
            override,
            "forced_disposal_month",
            FORCED_DISPOSAL_MONTH[asset_class],
        ),
        default_rationale="Default factor table — Pratt&Niculita (2008) / Hitchner (2017)",
    )


def _asset_line_from_extra_override(
    asset_class: AssetClass,
    override: Mapping[str, object],
) -> AssetLine | None:
    book = to_decimal_or_none(override.get("book_value")) or Decimal("0")
    adjusted = to_decimal_or_none(override.get("adjusted_value")) or book
    if adjusted <= 0:
        return None
    return _asset_line(
        asset_class=asset_class,
        book=book,
        adjusted=adjusted,
        override=override,
        orderly_disposal_month=_override_line_disposal_month(
            override,
            "orderly_disposal_month",
            ORDERLY_DISPOSAL_MONTH[asset_class],
        ),
        forced_disposal_month=_override_line_disposal_month(
            override,
            "forced_disposal_month",
            FORCED_DISPOSAL_MONTH[asset_class],
        ),
        default_rationale="Appraiser-supplied line",
    )


def _build_balance_sheet_asset_lines(
    *,
    seen_classes: Mapping[AssetClass, Decimal],
    overrides: Dict[str, Mapping[str, object]],
) -> list[AssetLine]:
    return [
        _asset_line_from_balance_sheet(
            asset_class,
            book,
            overrides.pop(asset_class.value, {}) or {},
        )
        for asset_class, book in seen_classes.items()
    ]


def _build_extra_override_lines(
    *,
    overrides: Mapping[str, Mapping[str, object]],
    warnings: list[str],
) -> list[AssetLine]:
    lines: list[AssetLine] = []
    for class_value, override in overrides.items():
        try:
            asset_class = AssetClass(class_value)
        except ValueError:
            warnings.append(f"Override for unknown asset class skipped: {class_value!r}")
            continue
        line = _asset_line_from_extra_override(asset_class, override)
        if line is not None:
            lines.append(line)
    return lines


def _unallocated_book_value(
    *,
    balance_sheet: Mapping[str, object],
    total_book: Decimal,
    warnings: list[str],
) -> Decimal:
    bs_total = to_decimal_or_none(balance_sheet.get("total_assets"))
    if bs_total is None or bs_total <= 0:
        return Decimal("0")

    unallocated = (bs_total - total_book).quantize(Decimal("0.01"))
    if unallocated > 0 and (unallocated / bs_total) > Decimal("0.05"):
        warnings.append(
            f"Unallocated residual on the balance sheet "
            f"= {float(unallocated):,.2f} ({float(unallocated / bs_total) * 100:.1f}% "
            "of total assets). The realisation schedule covers only "
            "the named line items; consider a manual override for "
            "the residual."
        )
    elif unallocated < 0:
        warnings.append(
            f"Sum of decomposed asset lines exceeds reported total assets "
            f"by {float(-unallocated):,.2f}. Check for double-counting."
        )
    return unallocated


def build_asset_schedule(
    *,
    balance_sheet: Mapping[str, Any],
    asset_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> AssetSchedule:
    """Decompose a balance sheet into the 12-class realisation schedule.

    ``balance_sheet`` — the same dict shape ``compute_liquidation_scenarios``
    accepts. Keys map to asset classes via ``_BALANCE_SHEET_KEY_TO_CLASS``.

    ``asset_overrides`` — optional per-class override map keyed by
    ``AssetClass.value``. Each entry may set:
      - ``adjusted_value``  : Decimal | float — appraiser FMV
      - ``orderly_recovery_factor`` / ``forced_recovery_factor`` : Decimal
      - ``orderly_disposal_month`` / ``forced_disposal_month`` : int
      - ``label`` : str
      - ``rationale`` : str
    Overrides are how Venus's manual form contributes asset-by-asset
    appraiser knowledge without forking this module.

    The total_assets entry on balance_sheet is used only to compute the
    *unallocated* residual; lines are built strictly from the named keys
    so the schedule never silently invents a value.
    """
    overrides = dict(asset_overrides or {})
    warnings: List[str] = []
    seen_classes = _aggregate_balance_sheet_classes(balance_sheet)

    lines = _build_balance_sheet_asset_lines(
        seen_classes=seen_classes,
        overrides=overrides,
    )
    # Override entries that didn't match an existing line — they're
    # additional appraiser-supplied lines (e.g. land/buildings the GL
    # didn't decompose).
    lines.extend(_build_extra_override_lines(overrides=overrides, warnings=warnings))

    total_book = sum((line.book_value for line in lines), Decimal("0"))
    total_adjusted = sum((line.adjusted_value for line in lines), Decimal("0"))
    total_orderly = sum((line.orderly_realisable_value for line in lines), Decimal("0"))
    total_forced = sum((line.forced_realisable_value for line in lines), Decimal("0"))

    # Reconcile against balance-sheet headline total_assets if present.
    # The residual is reported as "unallocated_book" and a warning is
    # raised when it's non-trivial — it tells the appraiser there are
    # GL classes the schedule didn't cover.
    unallocated = _unallocated_book_value(
        balance_sheet=balance_sheet,
        total_book=total_book,
        warnings=warnings,
    )

    # Sort lines by orderly disposal month so the report renders in
    # temporal order — cash first, intangibles last.
    lines.sort(key=lambda l: (l.orderly_disposal_month, l.asset_class.value))

    return AssetSchedule(
        lines=tuple(lines),
        total_book=total_book.quantize(Decimal("0.01")),
        total_adjusted=total_adjusted.quantize(Decimal("0.01")),
        total_orderly_realisable=total_orderly.quantize(Decimal("0.01")),
        total_forced_realisable=total_forced.quantize(Decimal("0.01")),
        unallocated_book=unallocated,
        warnings=tuple(warnings),
        sources=_FACTOR_SOURCES,
    )


__all__ = [
    "AssetClass",
    "AssetLine",
    "AssetSchedule",
    "FORCED_CLASS_FACTORS",
    "FORCED_DISPOSAL_MONTH",
    "ORDERLY_CLASS_FACTORS",
    "ORDERLY_DISPOSAL_MONTH",
    "build_asset_schedule",
]
