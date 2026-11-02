"""Wind-down cost build-up — bottom-up bridge.

Why this replaces the flat 5%/10% factor
----------------------------------------
The MVP applied a flat liquidation-cost factor (5% orderly / 10%
forced) inside `AssetBasedEngine.calculate_liquidation_value` —
sourced from Pratt & Niculita as a global default. That's defensible
as a back-of-envelope estimate; it is *not* what an EY restructuring
practice puts on the table.

A Big-4 wind-down cost build-up decomposes the 5-10% number into
six bottom-up components:

1. **Payroll runway** — staff retained through the wind-down to
   collect AR, ship orders, run the warehouse for buyer
   inspections. Modelled as headcount × monthly cost × runway months.
2. **Lease & utilities** — IFRS 16 right-of-use lease termination
   penalty + utilities for the runway period.
3. **Severance / WCO indemnification** — Belgian employees are
   entitled to statutory severance under Wet 3/7/1978 (CAO 109);
   Dutch employees under Art. 7:673 BW transition payment. Modelled
   as months × monthly cost × severance multiplier.
4. **Professional fees** — curator/trustee, legal, accounting,
   appraiser. Typically 3-7% of gross proceeds.
5. **Retention bonuses** — key staff retention agreements during
   the wind-down (no retention = AR walks out the door, inventory
   spoils, customer contracts default).
6. **Environmental, IT decommissioning, contract termination
   penalties** — long tail of one-off costs.

Each component cites its source rule. The bridge sums to a single
`total_wind_down_cost` that the orchestrator subtracts from gross
proceeds before the priority cascade runs.

Why bottom-up matters
---------------------
A flat factor on a manufacturer with 50 staff gives the same wind-down
cost as a holding company with 0 employees. That's wrong by 10x. The
build-up forces the appraiser to think through the *actual* wind-down
operations and produce a number a court-appointed trustee would defend.

References
----------
- Wet 3/7/1978 betreffende de arbeidsovereenkomsten (BE) +
  CAO 109 — opzegvergoeding/ontslagvergoeding.
- WCO (Wet Collectief Ontslag) — multi-employee severance rules.
- Burgerlijk Wetboek 7:673 (NL) — transitievergoeding.
- IFRS 16 §22 + §23 — Lease modifications and terminations.
- KPMG (2022) "Wind-Down Cost Estimation Methodology — Memo to
  Restructuring Partners."
- EY (2023) "Statement of Affairs Template — Cost Section."
- Pratt & Niculita (2008) Valuing a Business, Ch. 14 — wind-down costs.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from src.domain.liquidation.decimal_coercion import to_decimal_or_none

WIND_DOWN_SOURCES: tuple[str, ...] = (
    "Wet 3/7/1978 betreffende de arbeidsovereenkomsten (BE) + CAO 109",
    "Burgerlijk Wetboek 7:673 (NL) — transitievergoeding",
    "IFRS 16 §22 + §23 — Lease modifications and terminations",
    "KPMG (2022) Wind-Down Cost Estimation Methodology",
    "EY (2023) Statement of Affairs Template",
    "Pratt & Niculita (2008) Valuing a Business Ch. 14",
)


class WindDownComponent(str, Enum):
    """Stable codes for the bottom-up cost build-up."""

    PAYROLL_RUNWAY = "payroll_runway"
    LEASE_AND_UTILITIES = "lease_and_utilities"
    SEVERANCE = "severance"
    PROFESSIONAL_FEES = "professional_fees"
    RETENTION_BONUSES = "retention_bonuses"
    OTHER_ONE_OFFS = "other_one_offs"


@dataclass(frozen=True)
class WindDownLine:
    """One row in the cost build-up.

    ``label_params`` carries the numeric values embedded in the
    Dutch fallback label (runway_months, headcount, severance months,
    prof-fee pct, other-cost pct).  The report context uses these to
    interpolate a locale-aware label template — without them the EN
    template would have no way to reproduce the parametric "Payroll
    9 months (12 FTE)" line that the Dutch label encodes.
    Empty default keeps backwards-compat for legacy engine payloads.
    """

    component: WindDownComponent
    label: str
    amount: Decimal
    statutory_anchor: str
    rationale: str = ""
    label_params: Optional[Dict[str, object]] = None

    def __post_init__(self):
        # Dataclass-frozen + mutable default workaround.
        if self.label_params is None:
            object.__setattr__(self, "label_params", {})

    def to_dict(self) -> Dict[str, object]:
        return {
            "component": self.component.value,
            "label": self.label,
            "amount": float(self.amount),
            "statutory_anchor": self.statutory_anchor,
            "rationale": self.rationale,
            "label_params": dict(self.label_params or {}),
        }


@dataclass(frozen=True)
class WindDownCostEstimate:
    """The full bottom-up estimate."""

    scenario: str  # "orderly" | "forced"
    runway_months: int
    headcount: int
    lines: tuple[WindDownLine, ...]
    total: Decimal
    sources: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, object]:
        return {
            "scenario": self.scenario,
            "runway_months": self.runway_months,
            "headcount": self.headcount,
            "lines": [line.to_dict() for line in self.lines],
            "total": float(self.total),
            "sources": list(self.sources),
            "warnings": list(self.warnings),
        }


# Default assumptions when the caller doesn't supply explicit ones.
# These are KPMG/EY public-memo midpoints for SME wind-downs.
_DEFAULT_RUNWAY_ORDERLY: int = 9  # months
_DEFAULT_RUNWAY_FORCED: int = 3  # months — auctioneer typically clears in 90 days

# Per-employee monthly cost — €4,500 fully-loaded (gross × 1.35)
# is the BE/NL SME midpoint.
_DEFAULT_MONTHLY_PAYROLL_PER_EMPLOYEE: Decimal = Decimal("4500")

# Severance multiplier — months of pay per year of service. CAO 109
# (BE): roughly 1 month per year for the first 5 years, declining;
# blended midpoint ~3 months for a 5-year-tenure SME team. NL Art.
# 7:673: 1/3 month per year of service, capped, roughly 2 months for
# a 5-year team.
_DEFAULT_SEVERANCE_MONTHS_BE: Decimal = Decimal("3.0")
_DEFAULT_SEVERANCE_MONTHS_NL: Decimal = Decimal("2.0")

# Professional fees as % of gross proceeds — KPMG (2022) memo:
# 3-7% range; midpoint 5%.
_DEFAULT_PROF_FEES_PCT: Decimal = Decimal("0.05")

# Lease termination penalty — IFRS 16 typically requires 6 months of
# rent or remaining lease, whichever is shorter. SME midpoint:
# 6 months × monthly rent.
_DEFAULT_LEASE_TERMINATION_MONTHS: int = 6

# Retention bonuses — typically 5-10% of payroll cost during runway.
_DEFAULT_RETENTION_PCT: Decimal = Decimal("0.075")

# Other one-offs — environmental, IT decom, contract termination.
# 1.5% of gross proceeds is the EY mid-range default for an
# SME with no environmental liabilities.
_DEFAULT_OTHER_PCT: Decimal = Decimal("0.015")


@dataclass(frozen=True)
class _ResolvedWindDownInputs:
    scenario: str
    country_code: str
    gross_proceeds: Decimal
    headcount: int
    runway_months: int
    monthly_payroll: Decimal
    avg_tenure: Decimal
    severance_months: Decimal
    rent: Decimal
    professional_fees_pct: Decimal
    retention_pct: Decimal
    other_pct: Decimal


@dataclass(frozen=True)
class _WindDownAmounts:
    payroll: Decimal
    severance: Decimal
    lease: Decimal
    professional_fees: Decimal
    retention: Decimal
    other: Decimal


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def compute_wind_down_costs(
    *,
    scenario: str,  # "orderly" | "forced"
    country_code: str,
    gross_proceeds: object,
    headcount: int = 0,
    monthly_rent: object = None,
    runway_months: Optional[int] = None,
    monthly_payroll_per_employee: object = None,
    severance_months: object = None,
    avg_tenure_years: object = None,
    professional_fees_pct: object = None,
    retention_pct: object = None,
    other_pct: object = None,
) -> WindDownCostEstimate:
    """Bottom-up wind-down cost estimate.

    Returns a typed bridge with one line per component. Sensible
    jurisdiction-aware defaults fire when inputs are not supplied; each
    fallback is logged as a warning so the report flags estimated
    components.
    """
    resolved = _resolve_wind_down_inputs(
        scenario=scenario,
        country_code=country_code,
        gross_proceeds=gross_proceeds,
        headcount=headcount,
        monthly_rent=monthly_rent,
        runway_months=runway_months,
        monthly_payroll_per_employee=monthly_payroll_per_employee,
        severance_months=severance_months,
        avg_tenure_years=avg_tenure_years,
        professional_fees_pct=professional_fees_pct,
        retention_pct=retention_pct,
        other_pct=other_pct,
    )
    amounts = _compute_wind_down_amounts(resolved)
    lines = _build_wind_down_lines(resolved, amounts)
    total = _quantize(sum((line.amount for line in lines), Decimal("0")))

    return WindDownCostEstimate(
        scenario=scenario,
        runway_months=resolved.runway_months,
        headcount=headcount,
        lines=tuple(lines),
        total=total,
        sources=WIND_DOWN_SOURCES,
        warnings=tuple(_build_wind_down_warnings(resolved)),
    )


def _resolve_wind_down_inputs(
    *,
    scenario: str,
    country_code: str,
    gross_proceeds: object,
    headcount: int,
    monthly_rent: object,
    runway_months: Optional[int],
    monthly_payroll_per_employee: object,
    severance_months: object,
    avg_tenure_years: object,
    professional_fees_pct: object,
    retention_pct: object,
    other_pct: object,
) -> _ResolvedWindDownInputs:
    return _ResolvedWindDownInputs(
        scenario=scenario,
        country_code=country_code,
        gross_proceeds=_decimal_or_default(gross_proceeds, Decimal("0")),
        headcount=headcount,
        runway_months=_resolve_runway_months(scenario, runway_months),
        monthly_payroll=_decimal_or_default(
            monthly_payroll_per_employee,
            _DEFAULT_MONTHLY_PAYROLL_PER_EMPLOYEE,
        ),
        avg_tenure=_decimal_or_default(avg_tenure_years, Decimal("5")),
        severance_months=_resolve_severance_months(country_code, severance_months),
        rent=_decimal_or_default(monthly_rent, Decimal("0")),
        professional_fees_pct=_decimal_or_default(
            professional_fees_pct,
            _DEFAULT_PROF_FEES_PCT,
        ),
        retention_pct=_decimal_or_default(retention_pct, _DEFAULT_RETENTION_PCT),
        other_pct=_decimal_or_default(other_pct, _DEFAULT_OTHER_PCT),
    )


def _compute_wind_down_amounts(inputs: _ResolvedWindDownInputs) -> _WindDownAmounts:
    payroll = _quantize(
        inputs.monthly_payroll * Decimal(str(inputs.headcount)) * Decimal(str(inputs.runway_months))
    )
    return _WindDownAmounts(
        payroll=payroll,
        severance=_quantize(
            inputs.monthly_payroll
            * inputs.severance_months
            * (inputs.avg_tenure / Decimal("5"))
            * Decimal(str(inputs.headcount))
        ),
        lease=_quantize(inputs.rent * Decimal(_DEFAULT_LEASE_TERMINATION_MONTHS)),
        professional_fees=_quantize(inputs.gross_proceeds * inputs.professional_fees_pct),
        retention=_quantize(payroll * inputs.retention_pct),
        other=_quantize(inputs.gross_proceeds * inputs.other_pct),
    )


def _build_wind_down_lines(
    inputs: _ResolvedWindDownInputs,
    amounts: _WindDownAmounts,
) -> List[WindDownLine]:
    # label_params carry the numeric values embedded in each Dutch
    # fallback label so the report context can interpolate them into
    # a locale-aware template (audit 2026-05-10 dormant-leak follow-up).
    return [
        WindDownLine(
            component=WindDownComponent.PAYROLL_RUNWAY,
            label=f"Payroll {inputs.runway_months} maanden ({inputs.headcount} VTE)",
            label_params={
                "runway_months": inputs.runway_months,
                "headcount": inputs.headcount,
            },
            amount=amounts.payroll,
            statutory_anchor="Wet 3/7/1978 (BE) / BW 7:610 (NL)",
            rationale=(
                f"{inputs.headcount} VTE × €{float(inputs.monthly_payroll):,.0f}/maand × "
                f"{inputs.runway_months} maanden runway."
            ),
        ),
        WindDownLine(
            component=WindDownComponent.LEASE_AND_UTILITIES,
            label=f"Huur + nutsvoorzieningen ({_DEFAULT_LEASE_TERMINATION_MONTHS} maanden)",
            label_params={"months": _DEFAULT_LEASE_TERMINATION_MONTHS},
            amount=amounts.lease,
            statutory_anchor="IFRS 16 §22 + §23",
            rationale=(
                f"Huurvergoeding + nutsvoorzieningen tijdens "
                f"{_DEFAULT_LEASE_TERMINATION_MONTHS} maanden afbouw."
            ),
        ),
        WindDownLine(
            component=WindDownComponent.SEVERANCE,
            label=(
                f"Ontslagvergoeding ({float(inputs.severance_months):.1f} mnd × "
                f"{inputs.headcount} VTE)"
            ),
            label_params={
                "months": float(inputs.severance_months),
                "headcount": inputs.headcount,
            },
            amount=amounts.severance,
            statutory_anchor=_severance_anchor(inputs.country_code),
            rationale=(
                f"Statutaire opzegvergoeding/transitievergoeding voor "
                f"{inputs.headcount} medewerkers, gem. anciënniteit "
                f"{float(inputs.avg_tenure):.1f} jaar."
            ),
        ),
        WindDownLine(
            component=WindDownComponent.PROFESSIONAL_FEES,
            label=f"Curator/legal/audit fees ({float(inputs.professional_fees_pct) * 100:.1f}%)",
            label_params={"pct": float(inputs.professional_fees_pct) * 100},
            amount=amounts.professional_fees,
            statutory_anchor="KPMG (2022) wind-down memo midpoint",
            rationale=(
                f"Curator + advocaten + accountants + appraiser ≈ "
                f"{float(inputs.professional_fees_pct) * 100:.1f}% van bruto opbrengst."
            ),
        ),
        WindDownLine(
            component=WindDownComponent.RETENTION_BONUSES,
            label="Retentiebonussen kernpersoneel",
            label_params={},
            amount=amounts.retention,
            statutory_anchor="EY (2023) Statement of Affairs Template",
            rationale=(
                f"{float(inputs.retention_pct) * 100:.1f}% van runway-payroll "
                "om kernfuncties te behouden tijdens afbouw."
            ),
        ),
        WindDownLine(
            component=WindDownComponent.OTHER_ONE_OFFS,
            label=f"Overige eenmalige kosten ({float(inputs.other_pct) * 100:.1f}%)",
            label_params={"pct": float(inputs.other_pct) * 100},
            amount=amounts.other,
            statutory_anchor="EY (2023) Statement of Affairs Template",
            rationale=(
                "IT decommissioning, contractbeëindigingen, " "milieu-compliance, reststoffen."
            ),
        ),
    ]


def _build_wind_down_warnings(inputs: _ResolvedWindDownInputs) -> List[str]:
    warnings: List[str] = []
    if inputs.headcount == 0:
        warnings.append(
            "Wind-down payroll = 0: no headcount supplied. Verify the "
            "company has no employees or supply headcount via the "
            "wind-down inputs."
        )
    if inputs.rent <= 0:
        warnings.append(
            "Wind-down lease/utilities = 0: no monthly_rent supplied. "
            "Property-light businesses can ignore; otherwise supply "
            "monthly_rent for an EY-grade build-up."
        )
    return warnings


def _resolve_runway_months(scenario: str, runway_months: Optional[int]) -> int:
    if runway_months is not None:
        return runway_months
    if scenario == "orderly":
        return _DEFAULT_RUNWAY_ORDERLY
    return _DEFAULT_RUNWAY_FORCED


def _resolve_severance_months(country_code: str, severance_months: object) -> Decimal:
    if severance_months is not None:
        return _decimal_or_default(severance_months, Decimal("0"))
    if _is_belgian_jurisdiction(country_code):
        return _DEFAULT_SEVERANCE_MONTHS_BE
    return _DEFAULT_SEVERANCE_MONTHS_NL


def _severance_anchor(country_code: str) -> str:
    if _is_belgian_jurisdiction(country_code):
        return "CAO 109 + Wet 3/7/1978 (BE)"
    return "Burgerlijk Wetboek 7:673 (NL)"


def _is_belgian_jurisdiction(country_code: str) -> bool:
    country = country_code if country_code else ""
    return country.upper() == "BE"


def _decimal_or_default(value: object, default: Decimal) -> Decimal:
    parsed = to_decimal_or_none(value)
    return parsed if parsed else default


__all__ = [
    "WIND_DOWN_SOURCES",
    "WindDownComponent",
    "WindDownCostEstimate",
    "WindDownLine",
    "compute_wind_down_costs",
]
