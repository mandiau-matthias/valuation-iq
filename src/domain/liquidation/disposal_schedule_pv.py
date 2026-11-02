"""PV-discounted disposal schedule — Phase 3 Big-4 depth.

Why PV-discount the disposal timeline
-------------------------------------
A McKinsey *Valuation* (Koller/Goedhart/Wessels 7th ed.) and a
Damodaran *Investment Valuation* both frame liquidation as a **cash-
flow stream over time**, not a single point. An asset that liquidates
for €1M in 12 months is worth less *today* than €1M in cash today —
the gap is the time value of money at the appropriate distress
discount rate.

A defensible Big-4 PV bridge:

1. Each asset class has an `orderly_disposal_month` from the schedule
   (Phase 1 module, asset_schedule.py).
2. Each scenario applies a distress-WACC discount (Damodaran 2012 Ch.
   23 puts SME distress WACC at 12-18%; we default to 15%).
3. PV = realisable_value / (1 + r/12)^month.
4. Forced scenarios compress the timeline (≤ 3 months) and apply a
   higher discount rate (auctioneer's holding cost is ~25% on an
   annualised basis per AssetSmart 2022 published auction data).

Output: a `DisposalSchedulePV` with per-class PV + total PV, plus the
implicit "PV haircut" (= nominal − PV) which the report exposes as a
distinct distress-cost line item.

References
----------
- Koller, Goedhart, Wessels (McKinsey 2020). Valuation 7th ed., Ch. 35.
- Damodaran, A. (2012). Investment Valuation, Ch. 23 — distress
  reorganisation expected-value framework.
- AssetSmart (2022). Industrial Auction Recovery — Annual Report.
- Pratt & Niculita (2008) Valuing a Business, Ch. 5 — DLOM and time-
  to-liquidate adjustments.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from .asset_schedule import AssetLine, AssetSchedule


PV_SOURCES: tuple[str, ...] = (
    "Koller/Goedhart/Wessels (McKinsey 2020) Valuation 7th ed. Ch. 35",
    "Damodaran (2012) Investment Valuation Ch. 23 — distress WACC",
    "AssetSmart (2022) Industrial Auction Recovery Annual Report",
)


# Distress WACC defaults (annualised). Damodaran 2012 Ch. 23 puts the
# SME distress range at 12-18%; we default to 15% orderly. Forced
# scenarios pay the auctioneer's effective ~25% annualised holding
# cost.
_DEFAULT_DISTRESS_WACC_ORDERLY: Decimal = Decimal("0.15")
_DEFAULT_DISTRESS_WACC_FORCED: Decimal = Decimal("0.25")


@dataclass(frozen=True)
class DisposalLinePV:
    """One row in the PV bridge — per asset class."""

    asset_class: str
    label: str
    nominal_value: Decimal
    disposal_month: int
    discount_rate_annual: Decimal
    discount_factor: Decimal
    pv_value: Decimal
    pv_haircut: Decimal  # = nominal - pv

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_class": self.asset_class,
            "label": self.label,
            "nominal_value": float(self.nominal_value),
            "disposal_month": self.disposal_month,
            "discount_rate_annual": float(self.discount_rate_annual),
            "discount_factor": float(self.discount_factor),
            "pv_value": float(self.pv_value),
            "pv_haircut": float(self.pv_haircut),
        }


@dataclass(frozen=True)
class DisposalSchedulePV:
    """Full PV bridge for one scenario (orderly OR forced)."""

    scenario: str  # "orderly" | "forced"
    discount_rate_annual: Decimal
    lines: tuple[DisposalLinePV, ...]
    total_nominal: Decimal
    total_pv: Decimal
    total_pv_haircut: Decimal
    sources: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "discount_rate_annual": float(self.discount_rate_annual),
            "lines": [line.to_dict() for line in self.lines],
            "total_nominal": float(self.total_nominal),
            "total_pv": float(self.total_pv),
            "total_pv_haircut": float(self.total_pv_haircut),
            "sources": list(self.sources),
        }


def _discount_factor(rate_annual: Decimal, month: int) -> Decimal:
    """Monthly compounded PV factor: 1 / (1 + r/12)^month.

    Decimal-faithful via float pow at the boundary; the result is
    quantised to 6 decimals — well within report precision and fast.
    """
    if rate_annual <= 0 or month <= 0:
        return Decimal("1.000000")
    monthly = float(rate_annual) / 12.0
    factor = (1.0 + monthly) ** month
    return Decimal(str(1.0 / factor)).quantize(Decimal("0.000001"))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _build_pv_lines(
    *,
    schedule: AssetSchedule,
    scenario: str,
    rate: Decimal,
) -> List[DisposalLinePV]:
    """Project the schedule into PV space for the named scenario."""
    out: List[DisposalLinePV] = []
    for line in schedule.lines:
        if scenario == "orderly":
            nominal = line.orderly_realisable_value
            month = line.orderly_disposal_month
        else:
            nominal = line.forced_realisable_value
            month = line.forced_disposal_month
        factor = _discount_factor(rate, month)
        pv = _quantize(nominal * factor)
        out.append(
            DisposalLinePV(
                asset_class=line.asset_class.value,
                label=line.label or line.asset_class.value,
                nominal_value=_quantize(nominal),
                disposal_month=month,
                discount_rate_annual=rate,
                discount_factor=factor,
                pv_value=pv,
                pv_haircut=_quantize(nominal - pv),
            )
        )
    return out


def compute_disposal_schedule_pv(
    *,
    schedule: AssetSchedule,
    scenario: str,
    distress_wacc_annual: Optional[Any] = None,
) -> DisposalSchedulePV:
    """Build the PV bridge for the named scenario.

    `scenario` is "orderly" or "forced". `distress_wacc_annual` defaults
    to 15% orderly / 25% forced when not supplied (Damodaran SME range +
    auctioneer-published auction data).
    """
    if distress_wacc_annual is not None:
        rate: Decimal
        try:
            rate = Decimal(str(distress_wacc_annual))
        except Exception:
            rate = (
                _DEFAULT_DISTRESS_WACC_ORDERLY
                if scenario == "orderly"
                else _DEFAULT_DISTRESS_WACC_FORCED
            )
    else:
        rate = (
            _DEFAULT_DISTRESS_WACC_ORDERLY
            if scenario == "orderly"
            else _DEFAULT_DISTRESS_WACC_FORCED
        )

    lines = _build_pv_lines(schedule=schedule, scenario=scenario, rate=rate)
    nominal = sum((line.nominal_value for line in lines), Decimal("0"))
    pv = sum((line.pv_value for line in lines), Decimal("0"))
    haircut = nominal - pv

    return DisposalSchedulePV(
        scenario=scenario,
        discount_rate_annual=rate,
        lines=tuple(lines),
        total_nominal=_quantize(nominal),
        total_pv=_quantize(pv),
        total_pv_haircut=_quantize(haircut),
        sources=PV_SOURCES,
    )


__all__ = [
    "PV_SOURCES",
    "DisposalLinePV",
    "DisposalSchedulePV",
    "compute_disposal_schedule_pv",
]
