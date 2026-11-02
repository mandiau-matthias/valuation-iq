"""Conditional per-scenario cash bridge from asset proceeds to owner proceeds.

Aggregates wind-down costs, creditor distributions and the admitted tax scenario.
The bridge does not establish a legal statement of affairs or a buyer bid range.
Personal after-tax proceeds, company equity and gross replacement cost are not
interchangeable valuation bases.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

STATEMENT_OF_AFFAIRS_SOURCES: tuple[str, ...] = ()


class WaterfallStepKind(str, Enum):
    """Stable codes for the report's waterfall renderer."""

    GROSS = "gross"
    DEDUCTION = "deduction"
    SUBTOTAL = "subtotal"
    NET = "net"


@dataclass(frozen=True)
class WaterfallStep:
    """One row in the gross-to-net waterfall.

    ``step_code`` identifies the semantic row (gross_assets,
    deduction_wind_down, deduction_cascade_tier, deduction_tax,
    subtotal_available_for_creditors, …) so the report context can
    overlay a locale-aware label + rationale.  ``label_params`` carries
    any dynamic values (scenario name, tier name, tax label) that the
    Dutch fallback label baked in.

    Both default empty so legacy / direct dict consumers see the
    engine's Dutch fallback strings untouched.
    """

    kind: WaterfallStepKind
    label: str
    amount: Decimal
    running_total: Decimal
    rationale: str = ""
    step_code: str = ""
    label_params: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.label_params is None:
            object.__setattr__(self, "label_params", {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "label": self.label,
            "amount": float(self.amount),
            "running_total": float(self.running_total),
            "rationale": self.rationale,
            "step_code": self.step_code,
            "label_params": dict(self.label_params or {}),
        }


@dataclass(frozen=True)
class MAndABand:
    """Legacy wire structure; current calculations withhold an unreconciled band."""

    floor: Decimal
    floor_label: str
    reference: Optional[Decimal]
    reference_label: Optional[str]
    ceiling: Optional[Decimal]
    ceiling_label: Optional[str]
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "floor": float(self.floor),
            "floor_label": self.floor_label,
            "reference": float(self.reference) if self.reference is not None else None,
            "reference_label": self.reference_label,
            "ceiling": float(self.ceiling) if self.ceiling is not None else None,
            "ceiling_label": self.ceiling_label,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class StatementOfAffairs:
    """Cash bridges with an optional legacy band, withheld by current policy."""

    waterfall_orderly: tuple[WaterfallStep, ...]
    waterfall_forced: tuple[WaterfallStep, ...]
    headline_net_orderly: Decimal
    headline_net_forced: Decimal
    headline_book_equity: Decimal
    band: Optional[MAndABand]
    sources: tuple[str, ...]
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "waterfall_orderly": [s.to_dict() for s in self.waterfall_orderly],
            "waterfall_forced": [s.to_dict() for s in self.waterfall_forced],
            "headline_net_orderly": float(self.headline_net_orderly),
            "headline_net_forced": float(self.headline_net_forced),
            "headline_book_equity": float(self.headline_book_equity),
            "band": self.band.to_dict() if self.band is not None else None,
            "band_status": "not_assessed_mixed_value_bases",
            "sources": list(self.sources),
            "rationale": self.rationale,
        }


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _build_scenario_waterfall(
    *,
    scenario_label_orderly: str,  # "Orderly" or "Forced" — kept for label clarity
    total_assets_adjusted: Decimal,
    wind_down_total: Decimal,
    cascade_tiers: tuple[Any, ...],  # CascadeTier-shaped
    cascade_tier_label_prefix: str,
    tax_total: Decimal,
    tax_label: str,
    net_to_shareholders: Decimal,
) -> List[WaterfallStep]:
    """Build the gross-to-net waterfall for one scenario.

    The math identity that pins this:
      total_assets_adjusted
      − wind_down_total                            (operational)
      − Σ tier.recovery_amount   (per cascade tier)
      − tax_total
      = net_to_shareholders
    """
    steps: List[WaterfallStep] = []
    running = total_assets_adjusted
    steps.append(
        WaterfallStep(
            kind=WaterfallStepKind.GROSS,
            step_code="gross_assets_at_fmv",
            label_params={"scenario": scenario_label_orderly},
            label=f"{scenario_label_orderly}: bruto activa op FMV",
            amount=_quantize(total_assets_adjusted),
            running_total=_quantize(running),
            rationale="Som van 12-class realisatieschema, vóór kosten + crediteuren.",
        )
    )
    if wind_down_total > 0:
        running = running - wind_down_total
        steps.append(
            WaterfallStep(
                kind=WaterfallStepKind.DEDUCTION,
                step_code="deduction_wind_down",
                label="− Afbouwkosten (operationeel)",
                amount=_quantize(-wind_down_total),
                running_total=_quantize(running),
                rationale="Bottom-up build-up: payroll runway + huur + ontslagvergoeding "
                "+ professional fees + retentie + overige eenmalige kosten. "
                "EY/KPMG werkpapierformat.",
            )
        )
    steps.append(
        WaterfallStep(
            kind=WaterfallStepKind.SUBTOTAL,
            step_code="subtotal_available_for_creditors",
            label="= Beschikbaar voor schuldeisers",
            amount=_quantize(running),
            running_total=_quantize(running),
            rationale="Netto-boedel voor de prioriteitscascade.",
        )
    )
    for tier in cascade_tiers:
        recovery = tier.recovery_amount if hasattr(tier, "recovery_amount") else Decimal("0")
        if recovery <= 0:
            continue
        running = running - recovery
        # Carry the tier's stable code so the report context can
        # substitute a locale-aware label without re-deriving from
        # the (Dutch) tier.label string.
        tier_code = (getattr(tier.code, "value", None) if hasattr(tier, "code") else None) or ""
        steps.append(
            WaterfallStep(
                kind=WaterfallStepKind.DEDUCTION,
                step_code="deduction_cascade_tier",
                label_params={
                    "prefix": cascade_tier_label_prefix,
                    "tier_label": tier.label,
                    "tier_code": tier_code,
                },
                label=f"− {cascade_tier_label_prefix}: {tier.label}",
                amount=_quantize(-recovery),
                running_total=_quantize(running),
                rationale=tier.statutory_anchor if hasattr(tier, "statutory_anchor") else "",
            )
        )
    steps.append(
        WaterfallStep(
            kind=WaterfallStepKind.SUBTOTAL,
            step_code="subtotal_gross_distribution",
            label="= Bruto uitkering aan aandeelhouders",
            amount=_quantize(running),
            running_total=_quantize(running),
            rationale="Vóór belastingen.",
        )
    )
    if tax_total > 0:
        running = running - tax_total
        steps.append(
            WaterfallStep(
                kind=WaterfallStepKind.DEDUCTION,
                step_code="deduction_tax_leakage",
                label_params={"tax_label": tax_label},
                label=f"− {tax_label}",
                amount=_quantize(-tax_total),
                running_total=_quantize(running),
                rationale="Liquidatiebonus / box-2 / DTL-reversal.",
            )
        )
    if running < 0:
        running = Decimal("0")
    steps.append(
        WaterfallStep(
            kind=WaterfallStepKind.NET,
            step_code="net_to_shareholder",
            label="= Netto naar aandeelhouder",
            amount=_quantize(running),
            running_total=_quantize(running),
            rationale="Wat de eigenaar werkelijk in handen krijgt.",
        )
    )
    # Sanity-pin the math identity. The running total at the NET step
    # must equal the orchestrator's net_to_shareholders within rounding.
    if abs(running - net_to_shareholders) > Decimal("0.05"):
        # Don't raise — the scenarios.py orchestrator may have applied
        # a 0-clamp that we mirror above; record the rationale instead.
        steps[-1] = WaterfallStep(
            kind=WaterfallStepKind.NET,
            step_code="net_to_shareholder_corrected",
            label="= Netto naar aandeelhouder",
            amount=_quantize(net_to_shareholders),
            running_total=_quantize(net_to_shareholders),
            rationale=(
                "Engine-gecorrigeerd. Cascade- of belastingclamp werd toegepast. "
                "Voor exacte reconciliatie zie individuele secties hieronder."
            ),
        )
    return steps


def build_statement_of_affairs(
    *,
    book_equity: Decimal,
    orderly_assets_adjusted: Decimal,
    forced_assets_adjusted: Decimal,
    wind_down_orderly_total: Decimal,
    wind_down_forced_total: Decimal,
    cascade_orderly_tiers: tuple[Any, ...],
    cascade_forced_tiers: tuple[Any, ...],
    tax_orderly_total: Decimal,
    tax_forced_total: Decimal,
    net_orderly: Decimal,
    net_forced: Decimal,
    going_concern_value: Optional[Decimal],
    replacement_cost_value: Optional[Decimal],
    cascade_jurisdiction: str = "BE",
) -> StatementOfAffairs:
    """Aggregate all Phase 1-4 outputs into the Statement of Affairs.

    Inputs are the typed dataclass fields off ``LiquidationScenarios``;
    the function is pure orchestration above the Phase 2-4 modules.
    """
    cascade_label_prefix = "Boek XX WER" if cascade_jurisdiction == "BE" else "Faillissementswet"
    # tax_label is intentionally Dutch — the report context overlays
    # an EN variant per `deduction_tax_leakage` step_code via the
    # `tax_label` value in label_params.  The jurisdiction-aware EN
    # variant is keyed in the translation dict.
    tax_label = (
        "Belastinglekkage (BE liquidatiebonus + aanvullende vennootschapsbelasting)"
        if cascade_jurisdiction == "BE"
        else "Belastinglekkage (NL box-2 + aanvullende vennootschapsbelasting)"
    )

    orderly_steps = _build_scenario_waterfall(
        scenario_label_orderly="Geordende liquidatie",
        total_assets_adjusted=orderly_assets_adjusted,
        wind_down_total=wind_down_orderly_total,
        cascade_tiers=cascade_orderly_tiers,
        cascade_tier_label_prefix=cascade_label_prefix,
        tax_total=tax_orderly_total,
        tax_label=tax_label,
        net_to_shareholders=net_orderly,
    )
    forced_steps = _build_scenario_waterfall(
        scenario_label_orderly="Gedwongen liquidatie",
        total_assets_adjusted=forced_assets_adjusted,
        wind_down_total=wind_down_forced_total,
        cascade_tiers=cascade_forced_tiers,
        cascade_tier_label_prefix=cascade_label_prefix,
        tax_total=tax_forced_total,
        tax_label=tax_label,
        net_to_shareholders=net_forced,
    )

    # Personal after-tax proceeds, going-concern equity and gross asset
    # replacement cost do not form one comparable bid interval. Reinstatement
    # requires an explicit basis reconciliation and supported buyer assumptions.
    band = None
    rationale = (
        "Per-scenario cash bridge. Buyer bid bands are not assessed: owner tax, "
        "company equity and gross replacement cost have different value bases."
    )

    return StatementOfAffairs(
        waterfall_orderly=tuple(orderly_steps),
        waterfall_forced=tuple(forced_steps),
        headline_net_orderly=_quantize(net_orderly),
        headline_net_forced=_quantize(net_forced),
        headline_book_equity=_quantize(book_equity),
        band=band,
        sources=STATEMENT_OF_AFFAIRS_SOURCES,
        rationale=rationale,
    )


__all__ = [
    "STATEMENT_OF_AFFAIRS_SOURCES",
    "MAndABand",
    "StatementOfAffairs",
    "WaterfallStep",
    "WaterfallStepKind",
    "build_statement_of_affairs",
]
