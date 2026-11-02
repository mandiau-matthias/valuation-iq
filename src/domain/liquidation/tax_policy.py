"""Dated admission and bracket arithmetic for reviewed liquidation tax scenarios."""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

BOX2_SOURCE = "https://www.belastingdienst.nl/wps/wcm/connect/bldcontentnl/belastingdienst/prive/inkomstenbelasting/heffingskortingen_boxen_tarieven/boxen_en_tarieven/box_2/box_2"
BE_INCOME_SOURCE = "https://financien.belgium.be/nl/particulieren/belastingaangifte/tarieven-belastbaar-inkomen/belastbaar-inkomen/roerend-inkomen"
NL_BOX2_BRACKETS = {
    2024: (Decimal("67000"), Decimal("0.245"), Decimal("0.33")),
    2025: (Decimal("67804"), Decimal("0.245"), Decimal("0.31")),
    2026: (Decimal("68843"), Decimal("0.245"), Decimal("0.31")),
}
_DECIMAL = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")


def nonnegative_amount(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (str, Decimal, int, float)):
        return None
    raw = str(value).strip()
    if not _DECIMAL.fullmatch(raw):
        return None
    try:
        result = Decimal(raw)
    except InvalidOperation:
        return None
    # Bound the arithmetic/JSON domain before quantization. Explicit zero is valid.
    if not result.is_finite() or result < 0 or result > Decimal("1e15"):
        return None
    if result != 0 and result < Decimal("1e-12"):
        return None
    return result


@dataclass(frozen=True)
class LiquidationTaxPolicy:
    tax_year: int
    evidence_reference: str
    incremental_corporate_tax: Decimal
    shareholder_basis: Decimal
    exempt_reserve: Decimal
    other_box2_income: Decimal


def read_tax_policy(
    context: Mapping[str, object] | None,
    *,
    country: str,
    paid_up_capital: object,
) -> LiquidationTaxPolicy | None:
    """Only admit a reviewed, single domestic individual with 100% ownership.

    The incremental corporate cash tax must already reconcile gains, deferred
    taxes, losses and amounts paid through the creditor cascade. Accounting DTL
    balances and realised gains alone cannot establish that incremental amount.
    Missing fields are not zero and an ordinary reserve is not an exemption.
    """
    if not isinstance(context, Mapping):
        return None
    year = context.get("tax_year")
    if isinstance(year, bool) or not isinstance(year, int):
        return None
    if year not in ({2025, 2026} if country == "BE" else NL_BOX2_BRACKETS):
        return None
    if context.get("shareholder_scope") != "single_domestic_individual_100pct":
        return None
    reference = context.get("evidence_reference")
    if not isinstance(reference, str) or not reference.strip():
        return None
    corporate = nonnegative_amount(context.get("incremental_corporate_tax"))
    basis = nonnegative_amount(
        paid_up_capital if country == "BE" else context.get("shareholder_tax_basis")
    )
    exempt = (
        nonnegative_amount(context.get("exempt_liquidation_reserve"))
        if country == "BE"
        else Decimal("0")
    )
    other = (
        nonnegative_amount(context.get("other_box2_income")) if country == "NL" else Decimal("0")
    )
    if corporate is None or basis is None or exempt is None or other is None:
        return None
    return LiquidationTaxPolicy(year, reference.strip(), corporate, basis, exempt, other)


def tax_context_for_scenario(
    context: Mapping[str, object] | None,
    scenario: str,
    *,
    ownership_multiplier: Decimal,
    effective_date: str | None,
) -> dict[str, object] | None:
    """Bind reviewed cash tax to its scenario and valuation date, not accounts year."""
    if not isinstance(context, Mapping) or ownership_multiplier != Decimal("1"):
        return None
    if effective_date is not None:
        from datetime import date

        try:
            valuation_year = date.fromisoformat(effective_date).year
        except (TypeError, ValueError):
            return None
        if context.get("tax_year") != valuation_year:
            return None
    amounts = context.get("incremental_corporate_tax")
    if not isinstance(amounts, Mapping) or scenario not in amounts:
        return None
    return {**context, "incremental_corporate_tax": amounts[scenario]}


def box2_liability(income: Decimal, tax_year: int) -> Decimal:
    """Unrounded liability before credits and losses; no blended or reset bracket."""
    threshold, lower, upper = NL_BOX2_BRACKETS[tax_year]
    taxable = max(income, Decimal("0"))
    return min(taxable, threshold) * lower + max(taxable - threshold, Decimal("0")) * upper
