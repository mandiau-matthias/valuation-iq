"""Cash-free/debt-free acquisition scenarios. All outputs are modeled, never appraisals.

One financial authority (ValuationIQ); no database, external calls or seller prediction.
Cash after mandatory outflows is distributed; deficits are additional equity funding.
This explicit convention prevents counting retained cash twice at exit.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, le=1_000_000_000, max_digits=15, decimal_places=2)]
SignedMoney = Annotated[
    Decimal, Field(ge=-1_000_000_000, le=1_000_000_000, max_digits=15, decimal_places=2)
]
Text = Annotated[str, Field(min_length=1, max_length=1000)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class Adjustment(Input):
    id: Text
    amount: SignedMoney
    evidence: Text
    rationale: Text
    adviserApproved: Literal[True]


class Improvement(Input):
    id: Text
    # One economic driver per action: two actions cannot both count the same saving.
    driver: Text
    evidence: Text
    annualEbitdaBenefit: Money
    implementationCost: Money
    startYear: int = Field(ge=1, le=10)
    costYear: int = Field(ge=0, le=10)
    status: Literal["assumed", "measured"] = "assumed"


class Year(Input):
    year: int = Field(ge=1, le=10)
    # Earnings before improvement benefits; owner replacement already included.
    ebitdaBeforeImprovements: SignedMoney
    maintenanceCapex: Money
    workingCapitalIncrease: SignedMoney
    cashTaxes: Money
    debtRepayment: Money


class Scenario(Input):
    key: Literal["downside", "base", "upside"]
    assumptions: Text
    improvementIds: list[str] = Field(max_length=30)
    years: list[Year] = Field(min_length=1, max_length=10)
    exitMultiple: Decimal = Field(gt=0, le=30)
    exitCostFixed: Money
    exitCostRate: Decimal = Field(ge=0, le=1)


class AcquisitionScenarioInput(Input):
    version: Literal["acquisition-scenario/1"] = "acquisition-scenario/1"
    currency: Literal["EUR"]
    dealStructure: Literal["asset_purchase", "share_purchase"]
    cashFreeDebtFree: Literal[True]
    transactionBoundary: Text
    boundaryReviewed: Literal[True]
    earningsScope: Literal["standalone", "consolidated", "reviewed_transaction_scope"]
    earningsEvidence: Text
    purchaseEnterpriseValue: Money
    purchaseCosts: Money
    initialWorkingCapitalTopUp: Money
    acquisitionDebt: Money
    annualInterestRate: Decimal = Field(ge=0, le=1)
    reportedEbitda: SignedMoney
    ownerPayAlreadyExpensed: Money
    ownerReplacementCost: Money
    adjustments: list[Adjustment] = Field(max_length=30)
    improvements: list[Improvement] = Field(max_length=30)
    scenarios: list[Scenario] = Field(min_length=3, max_length=3)

    @property
    def sustainable_earnings(self) -> Decimal:
        return (
            self.reportedEbitda
            + self.ownerPayAlreadyExpensed
            - self.ownerReplacementCost
            + sum((a.amount for a in self.adjustments), Decimal(0))
        )

    @model_validator(mode="after")
    def coherent(self):
        if self.purchaseEnterpriseValue <= 0 or self.sustainable_earnings <= 0:
            raise ValueError(
                "This EV/EBITDA scenario requires positive purchase EV and sustainable earnings"
            )
        if {s.key for s in self.scenarios} != {"downside", "base", "upside"}:
            raise ValueError("Exactly one downside, base and upside scenario is required")
        ids = [a.id for a in self.improvements]
        drivers = [a.driver.strip().casefold() for a in self.improvements]
        adjustment_ids = [a.id for a in self.adjustments]
        if len(set(ids + adjustment_ids)) != len(ids + adjustment_ids) or len(set(drivers)) != len(
            drivers
        ):
            raise ValueError(
                "Duplicate improvement, adjustment or economic driver would double-count value"
            )
        horizons = {len(s.years) for s in self.scenarios}
        if len(horizons) != 1:
            raise ValueError("All scenarios must use the same holding period")
        for s in self.scenarios:
            if [y.year for y in s.years] != list(range(1, len(s.years) + 1)):
                raise ValueError("Forecast years must be consecutive from year 1")
            if len(set(s.improvementIds)) != len(s.improvementIds) or not set(
                s.improvementIds
            ) <= set(ids):
                raise ValueError("An improvement can be included only once and must exist")
            if (
                s.key == "base"
                and s.exitMultiple > self.purchaseEnterpriseValue / self.sustainable_earnings
            ):
                raise ValueError("The base case cannot require multiple expansion")
            for a in self.improvements:
                if a.id in s.improvementIds and (
                    a.startYear > len(s.years) or a.costYear > a.startYear
                ):
                    raise ValueError(
                        "Improvement timing must fall within the hold and costs cannot follow its start"
                    )
            debt = self.acquisitionDebt
            for y in s.years:
                if y.debtRepayment > debt:
                    raise ValueError("Debt repayment exceeds outstanding debt")
                debt -= y.debtRepayment
            upfront = sum(
                (
                    a.implementationCost
                    for a in self.improvements
                    if a.id in s.improvementIds and a.costYear == 0
                ),
                Decimal(0),
            )
            if (
                self.acquisitionDebt
                >= self.purchaseEnterpriseValue
                + self.purchaseCosts
                + self.initialWorkingCapitalTopUp
                + upfront
            ):
                raise ValueError(
                    "Positive initial equity is required; overfunded acquisitions are unsupported"
                )
        return self


def amount(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def calculate(request: AcquisitionScenarioInput) -> dict:
    data = request.model_dump(mode="json")
    calculation_id = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    entry_multiple = request.purchaseEnterpriseValue / request.sustainable_earnings
    outputs = []
    for scenario in request.scenarios:
        actions = [a for a in request.improvements if a.id in scenario.improvementIds]
        initial = (
            request.purchaseEnterpriseValue
            + request.purchaseCosts
            + request.initialWorkingCapitalTopUp
            + sum((a.implementationCost for a in actions if a.costYear == 0), Decimal(0))
            - request.acquisitionDebt
        )
        debt, funding, distributions = request.acquisitionDebt, Decimal(0), Decimal(0)
        years = []
        earnings = request.sustainable_earnings
        for year in scenario.years:
            benefit = sum(
                (a.annualEbitdaBenefit for a in actions if a.startYear <= year.year), Decimal(0)
            )
            costs = sum(
                (a.implementationCost for a in actions if a.costYear == year.year), Decimal(0)
            )
            earnings = year.ebitdaBeforeImprovements + benefit
            interest = debt * request.annualInterestRate
            cash = (
                earnings
                - interest
                - year.maintenanceCapex
                - year.workingCapitalIncrease
                - year.cashTaxes
                - year.debtRepayment
                - costs
            )
            additional = max(-cash, Decimal(0))
            distributed = max(cash, Decimal(0))
            debt -= year.debtRepayment
            funding += additional
            distributions += distributed
            years.append(
                {
                    "year": year.year,
                    "ebitda": amount(earnings),
                    "improvementBenefit": amount(benefit),
                    "implementationCost": amount(costs),
                    "interest": amount(interest),
                    "closingDebt": amount(debt),
                    "additionalEquityRequired": amount(additional),
                    "equityDistribution": amount(distributed),
                }
            )
        # Negative earnings require another valuation method, never a negative EV or a fake zero.
        exit_ev = earnings * scenario.exitMultiple if earnings > 0 else None
        exit_costs = (
            exit_ev * scenario.exitCostRate + scenario.exitCostFixed
            if exit_ev is not None
            else None
        )
        proceeds = exit_ev - debt - exit_costs if exit_ev is not None else None
        outputs.append(
            {
                "key": scenario.key,
                "initialEquity": amount(initial),
                "additionalEquityRequired": amount(funding),
                "distributionsDuringHold": amount(distributions),
                "years": years,
                "exitEnterpriseValue": amount(exit_ev) if exit_ev is not None else None,
                "exitCosts": amount(exit_costs) if exit_costs is not None else None,
                "exitDebt": amount(debt),
                "exitEquityProceeds": amount(proceeds) if proceeds is not None else None,
                "equityProfitBeforeInvestorTax": (
                    amount(proceeds + distributions - initial - funding)
                    if proceeds is not None
                    else None
                ),
                "exitUnavailableReason": "non_positive_exit_earnings" if exit_ev is None else None,
                "valueBridge": {
                    "earningsChangeAtEntryMultiple": amount(
                        (earnings - request.sustainable_earnings) * entry_multiple
                    ),
                    "multipleChange": (
                        amount(earnings * (scenario.exitMultiple - entry_multiple))
                        if exit_ev is not None
                        else None
                    ),
                    "debtRepaid": amount(request.acquisitionDebt - debt),
                },
            }
        )
    return {
        "methodologyVersion": "acquisition-scenario/1",
        "calculationId": calculation_id,
        "valueKind": "modeled",
        "currency": request.currency,
        "sustainableEbitda": amount(request.sustainable_earnings),
        "entryMultiple": float(entry_multiple),
        "scenarios": outputs,
        "limitations": [
            "Scenario assumptions are supplied by the case author; references are not independently verified.",
            "Cash-free/debt-free price with normal working capital; excludes investor capital-gains tax.",
            "Annual opening-debt interest; cash surplus distributed and cash deficits funded by extra equity.",
            "No seller willingness, market transaction price or recommendation is inferred.",
        ],
    }
