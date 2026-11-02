"""Advisor-input liquidation cash-tax scenarios, separate from company equity value.

Corporate cash taxes are supplied AFTER reconciliation with creditor liabilities.
The shareholder tax is charged on the remaining distribution. Ordinary taxed
reserves are not automatically exempt; Dutch shareholder basis is not paid-up
company capital. Missing evidence returns no after-tax estimate.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Mapping, Optional

from .tax_policy import (
    BE_INCOME_SOURCE,
    BOX2_SOURCE,
    box2_liability,
    nonnegative_amount,
    read_tax_policy,
)

BE_LIQUIDATION_BONUS_RATE = Decimal("0.30")
TAX_LEAKAGE_SOURCES_BE = (
    BE_INCOME_SOURCE,
    "WIB 92 Art. 209; specific reserve relief requires evidence",
)
TAX_LEAKAGE_SOURCES_NL = (
    BOX2_SOURCE,
    "Wet IB 2001: shareholder acquisition basis and annual box-2 income",
)


class TaxLeakageJurisdiction(str, Enum):
    BE = "BE"
    NL = "NL"


@dataclass(frozen=True)
class TaxLeakageLine:
    """One tax line in the leakage bridge.

    `gross` is the tax base, or the supplied cash-tax amount for an
    amount-only corporate line (rate=None). The anchor identifies the
    policy source or advisor schedule; it does not certify legal eligibility.

    ``code`` is a stable engine-agnostic key (e.g. ``be_liquidation_bonus``)
    that the report context uses to look up the localised label. The
    engine still emits a fallback ``label`` (Dutch on BE bridges, mixed
    on NL — see ``compute_*_tax_leakage`` for the source) so direct
    dict consumers and unit tests get a non-empty label without needing
    the locale-resolution step.
    """

    label: str
    gross: Decimal
    rate: Optional[Decimal]
    tax_amount: Decimal
    statutory_anchor: str
    rationale: str = ""
    code: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "gross": float(self.gross),
            "rate": float(self.rate) if self.rate is not None else None,
            "tax_amount": float(self.tax_amount),
            "statutory_anchor": self.statutory_anchor,
            "rationale": self.rationale,
            "code": self.code,
        }


@dataclass(frozen=True)
class TaxLeakageBridge:
    """Gross → net bridge for the shareholder distribution.

    Total tax leakage = sum of `tax_amount` across all lines.
    `net_to_shareholders` = max(gross_distribution − total_tax_leakage, 0).
    Corporate tax above available funds is separately disclosed as unfunded.
    """

    jurisdiction: TaxLeakageJurisdiction
    gross_distribution: Decimal
    paid_up_capital: Decimal | None
    taxable_base: Decimal
    lines: tuple[TaxLeakageLine, ...]
    total_tax_leakage: Decimal
    net_to_shareholders: Decimal
    sources: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    shareholder_tax_basis: Decimal = Decimal("0")
    tax_year: int | None = None
    evidence_reference: str | None = None
    unfunded_corporate_tax: Decimal = Decimal("0")
    exempt_liquidation_reserve: Decimal = Decimal("0")
    other_box2_income: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, object]:
        return {
            "jurisdiction": self.jurisdiction.value,
            "gross_distribution": float(self.gross_distribution),
            "paid_up_capital": (
                float(self.paid_up_capital) if self.paid_up_capital is not None else None
            ),
            "shareholder_tax_basis": float(self.shareholder_tax_basis),
            "taxable_base": float(self.taxable_base),
            "lines": [line.to_dict() for line in self.lines],
            "total_tax_leakage": float(self.total_tax_leakage),
            "net_to_shareholders": float(self.net_to_shareholders),
            "sources": list(self.sources),
            "warnings": list(self.warnings),
            "tax_year": self.tax_year,
            "evidence_reference": self.evidence_reference,
            "assessment_status": "advisor_input_scenario",
            "policy_version": "liquidation-tax.v2",
            "unfunded_corporate_tax": float(self.unfunded_corporate_tax),
            "exempt_liquidation_reserve": float(self.exempt_liquidation_reserve),
            "other_box2_income": float(self.other_box2_income),
        }


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_tax_leakage(
    *,
    country_code: str,
    gross_distribution: object,
    paid_up_capital: object,
    taxable_reserves: object = None,
    realised_capital_gains: object = None,
    deferred_tax_liabilities: object = None,
    tax_context: Mapping[str, object] | None = None,
) -> TaxLeakageBridge | None:
    """Price only a complete advisor-input scenario; legacy balances do not imply tax.

    ``incremental_corporate_tax`` is additional cash tax after amounts already
    included in the creditor cascade. It must reconcile gains and DTL overlap in
    the referenced tax schedule. Legacy gain/DTL/reserve fields remain accepted
    for wire compatibility, but are never independently charged or exempted.
    """
    country = (country_code or "").strip().upper()
    if country not in {"BE", "NL"}:
        return None
    gross = nonnegative_amount(gross_distribution)
    policy = read_tax_policy(tax_context, country=country, paid_up_capital=paid_up_capital)
    if gross is None or policy is None:
        return None
    gross = _quantize(gross)
    corporate = _quantize(policy.incremental_corporate_tax)
    distributable = max(gross - corporate, Decimal("0"))
    base = max(distributable - policy.shareholder_basis - policy.exempt_reserve, Decimal("0"))
    warnings = [
        "Scenario for one domestic individual owning 100%; subject to the referenced tax evidence.",
        "Corporate cash tax is incremental to the creditor cascade; gains and DTL balances are not charged again.",
    ]
    if country == "BE":
        shareholder_tax = _quantize(base * BE_LIQUIDATION_BONUS_RATE)
        rate = BE_LIQUIDATION_BONUS_RATE
        code, label = "be_liquidation_bonus", "Liquidatiebonus — standaardsituatie"
        anchor = "WIB 92 Art. 209; standard investment-income rate"
        rationale = "After corporate cash tax, fiscal paid-up capital and explicitly evidenced qualifying reserve distribution."
        if nonnegative_amount(taxable_reserves):
            warnings.append(
                "Ordinary taxed reserves have not been treated as an exempt liquidation reserve."
            )
    else:
        shareholder_tax = _quantize(
            box2_liability(policy.other_box2_income + base, policy.tax_year)
            - box2_liability(policy.other_box2_income, policy.tax_year)
        )
        rate = shareholder_tax / base if base > 0 else Decimal("0")
        code, label = "nl_box2", "Box 2 — progressief"
        anchor = f"Belastingdienst box 2, {policy.tax_year}"
        rationale = "Incremental annual box-2 liability using shareholder acquisition basis and other box-2 income; credits and loss offsets excluded."
    lines = (
        TaxLeakageLine(
            label="Aanvullende vennootschapsbelasting",
            gross=corporate,
            rate=None,
            tax_amount=corporate,
            statutory_anchor="Reviewed incremental cash-tax schedule",
            rationale="Net of tax amounts already included in creditor liabilities; no separate DTL addition.",
            code="corporate_cash_tax",
        ),
        TaxLeakageLine(
            label=label,
            gross=_quantize(base),
            rate=rate,
            tax_amount=shareholder_tax,
            statutory_anchor=anchor,
            rationale=rationale,
            code=code,
        ),
    )
    total = corporate + shareholder_tax
    shortfall = max(corporate - gross, Decimal("0"))
    if shortfall > 0:
        warnings.append(
            "Corporate tax exceeds available funds; unfunded tax liability is disclosed and shareholder proceeds are zero."
        )
    return TaxLeakageBridge(
        jurisdiction=TaxLeakageJurisdiction(country),
        gross_distribution=gross,
        paid_up_capital=nonnegative_amount(paid_up_capital),
        shareholder_tax_basis=policy.shareholder_basis,
        taxable_base=_quantize(base),
        lines=lines,
        total_tax_leakage=total,
        net_to_shareholders=max(gross - total, Decimal("0")),
        sources=TAX_LEAKAGE_SOURCES_BE if country == "BE" else TAX_LEAKAGE_SOURCES_NL,
        warnings=tuple(warnings),
        tax_year=policy.tax_year,
        evidence_reference=policy.evidence_reference,
        unfunded_corporate_tax=shortfall,
        exempt_liquidation_reserve=policy.exempt_reserve,
        other_box2_income=policy.other_box2_income,
    )


def compute_be_tax_leakage(
    *,
    gross_distribution: Decimal,
    paid_up_capital: Decimal,
    taxable_reserves: Decimal,
    realised_capital_gains: Decimal,
    deferred_tax_liabilities: Decimal,
    tax_context: Mapping[str, object] | None = None,
) -> TaxLeakageBridge | None:
    return compute_tax_leakage(
        country_code="BE",
        gross_distribution=gross_distribution,
        paid_up_capital=paid_up_capital,
        taxable_reserves=taxable_reserves,
        realised_capital_gains=realised_capital_gains,
        deferred_tax_liabilities=deferred_tax_liabilities,
        tax_context=tax_context,
    )


def compute_nl_tax_leakage(
    *,
    gross_distribution: Decimal,
    paid_up_capital: Decimal,
    realised_capital_gains: Decimal,
    deferred_tax_liabilities: Decimal,
    tax_context: Mapping[str, object] | None = None,
) -> TaxLeakageBridge | None:
    return compute_tax_leakage(
        country_code="NL",
        gross_distribution=gross_distribution,
        paid_up_capital=paid_up_capital,
        realised_capital_gains=realised_capital_gains,
        deferred_tax_liabilities=deferred_tax_liabilities,
        tax_context=tax_context,
    )
