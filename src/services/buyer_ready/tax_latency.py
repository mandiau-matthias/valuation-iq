"""Tax-Latency Flagger — F5 Part B (BET-245).

Pure deterministic rules engine that surfaces latent tax exposures
likely to destroy 1-3% of EV if not addressed before legal handoff. 10 rules
(7 BE + 3 NL) — every rule fires on documented signals from the
balance sheet or Owner Profile, never invents an exposure.

Each rule:
    - Has a unique `rule_id` (matches the F1 Pydantic enum
      `TaxLatencyRuleID` for wire-compatibility).
    - Fires on deterministic trigger criteria.
    - Returns a structured `TaxLatencyFlag` with severity + estimated
      impact when computable.
    - Is unit-tested for both trigger + no-trigger cases.

Country routing: rules dispatch by `signals.country_code`. BE rules
don't fire for NL entities and vice versa. EU expansion = new rule
sets behind a country branch — no existing rule changes.

Pure: same inputs → same outputs. No I/O, no DB, no service calls.

Anti-scope (per BET-247):
    - Generic "tax optimisation" advice → Legora / tax-adviser territory
    - Cross-border deal structures
    - EU jurisdictions beyond BE + NL (fast-follow when GTM expands)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Literal, Optional

# ---------------------------------------------------------------------
# Configuration constants — locked for v1
# ---------------------------------------------------------------------

# Belgium thresholds
BE_LIQUIDATIEBONUS_RESERVE_THRESHOLD_EUR: float = 500_000.0
BE_LIQUIDATIEBONUS_OWNER_AGE_THRESHOLD: int = 55
BE_LIQUIDATIEBONUS_TAX_RATE: float = 0.30  # 30% statutory rate

BE_DTL_REVALUATION_THRESHOLD_PCT: float = 0.20  # 20% book/historical-cost divergence
BE_VENDOR_LOAN_THRESHOLD_EUR: float = 100_000.0

# Netherlands thresholds
NL_DGA_MINIMUM_SALARY_EUR: float = 56_000.0  # Wettelijk minimum DGA salary 2026
NL_30PCT_RULING_EXPIRY_MONTHS: int = 24  # Months threshold for flagging

# ---------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------


TaxLatencyJurisdiction = Literal["BE", "NL"]
TaxLatencySeverity = Literal["info", "warning", "critical"]
TaxLatencyRuleID = Literal[
    # Belgium (7)
    "be_liquidatiebonus_optimisation",
    "be_dtl_revalued_assets",
    "be_vendor_loans",
    "be_vat_share_vs_asset",
    "be_management_fee_circularity",
    "be_consolidated_goodwill_amortisation",
    "be_carry_forward_losses",
    # Netherlands (3)
    "nl_box2_dga_salary",
    "nl_latent_dtl_goodwill",
    "nl_thirty_percent_ruling_expiry",
]


@dataclass(frozen=True)
class TaxLatencyFlag:
    """One triggered rule. Mirrors F1 `TaxLatencyFlagRender` shape."""

    rule_id: TaxLatencyRuleID
    jurisdiction: TaxLatencyJurisdiction
    label: str
    rationale: str
    severity: TaxLatencySeverity
    estimated_impact_eur: Optional[int] = None


@dataclass(frozen=True)
class TaxLatencyResult:
    """Full flag set for one entity. Drives F1 `TaxLatencyRender`."""

    jurisdiction: TaxLatencyJurisdiction
    flags: List[TaxLatencyFlag] = field(default_factory=list)

    @property
    def flag_count(self) -> int:
        return len(self.flags)


@dataclass(frozen=True)
class TaxLatencySignals:
    """All signals any rule might consult. Caller assembles from Titan."""

    country_code: TaxLatencyJurisdiction
    # Balance sheet (EUR)
    accumulated_reserves: Optional[float] = None
    revalued_asset_book_value: Optional[float] = None
    revalued_asset_historical_cost: Optional[float] = None
    vendor_loan_balance: Optional[float] = None  # Sum of 17x + 174x BE accounts
    consolidated_goodwill: Optional[float] = None
    carry_forward_losses: Optional[float] = None
    # Owner / entity
    owner_age: Optional[int] = None
    owner_compensation_annual: Optional[float] = None  # NL DGA salary signal
    # Related-party
    intercompany_management_fees: Optional[float] = None
    # Deal context
    deal_type: Optional[Literal["share", "asset", "unknown"]] = "unknown"
    # NL 30%-ruling employee count
    employees_with_30pct_ruling_expiring_24m: Optional[int] = None


# ---------------------------------------------------------------------
# Belgium rules
# ---------------------------------------------------------------------


def _rule_be_liquidatiebonus(s: TaxLatencySignals) -> Optional[TaxLatencyFlag]:
    """Trigger: reserves > €500k AND owner_age > 55.

    Impact: 30% liquidatiebonus tax on reserves above threshold.
    """
    if s.accumulated_reserves is None or s.owner_age is None:
        return None
    if (
        s.accumulated_reserves > BE_LIQUIDATIEBONUS_RESERVE_THRESHOLD_EUR
        and s.owner_age > BE_LIQUIDATIEBONUS_OWNER_AGE_THRESHOLD
    ):
        estimated_impact = int(round(s.accumulated_reserves * BE_LIQUIDATIEBONUS_TAX_RATE))
        return TaxLatencyFlag(
            rule_id="be_liquidatiebonus_optimisation",
            jurisdiction="BE",
            label="Liquidatiebonus exposure",
            rationale=(
                f"Owner age {s.owner_age} (>{BE_LIQUIDATIEBONUS_OWNER_AGE_THRESHOLD}) and "
                f"accumulated reserves €{s.accumulated_reserves:,.0f} "
                f"(>€{BE_LIQUIDATIEBONUS_RESERVE_THRESHOLD_EUR:,.0f}) — "
                "liquidation route triggers 30% bonus tax. "
                "Compare share-deal vs liquidation distribution paths before legal handoff."
            ),
            severity="warning",
            estimated_impact_eur=estimated_impact,
        )
    return None


def _rule_be_dtl_revalued_assets(s: TaxLatencySignals) -> Optional[TaxLatencyFlag]:
    """Trigger: book value diverges from historical cost by >20%.

    Impact: latent deferred tax liability surfaces at share-deal exit.
    """
    if s.revalued_asset_book_value is None or s.revalued_asset_historical_cost is None:
        return None
    if s.revalued_asset_historical_cost <= 0:
        return None
    divergence = (
        s.revalued_asset_book_value - s.revalued_asset_historical_cost
    ) / s.revalued_asset_historical_cost
    if abs(divergence) > BE_DTL_REVALUATION_THRESHOLD_PCT:
        return TaxLatencyFlag(
            rule_id="be_dtl_revalued_assets",
            jurisdiction="BE",
            label="Latent DTL on revalued assets",
            rationale=(
                f"Asset book value €{s.revalued_asset_book_value:,.0f} diverges "
                f"{divergence * 100:+.1f}% from historical cost "
                f"€{s.revalued_asset_historical_cost:,.0f}. "
                "Buyer will price a deferred tax liability — quantify before legal handoff."
            ),
            severity="warning",
        )
    return None


def _rule_be_vendor_loans(s: TaxLatencySignals) -> Optional[TaxLatencyFlag]:
    """Trigger: any 17x or 174x vendor-loan account > €100k.

    Common in family-owned BE SMEs; buyer typically requires repayment
    at closing or treatment in net-debt definition.
    """
    if s.vendor_loan_balance is None:
        return None
    if s.vendor_loan_balance > BE_VENDOR_LOAN_THRESHOLD_EUR:
        return TaxLatencyFlag(
            rule_id="be_vendor_loans",
            jurisdiction="BE",
            label="Vendor loans on balance sheet",
            rationale=(
                f"Vendor-loan balance €{s.vendor_loan_balance:,.0f} "
                f"(>€{BE_VENDOR_LOAN_THRESHOLD_EUR:,.0f}) on 17x/174x accounts. "
                "Buyer will require closing repayment or net-debt treatment. "
                "Confirm structure with owner before legal handoff."
            ),
            severity="info",
            estimated_impact_eur=int(round(s.vendor_loan_balance)),
        )
    return None


def _rule_be_vat_share_vs_asset(s: TaxLatencySignals) -> Optional[TaxLatencyFlag]:
    """Trigger: deal_type == 'asset' (regardless of value).

    Asset deals attract VAT (21% / 12% / 6%); share deals exempt.
    Flag the math at the deal-type fork so the advisor can quantify.
    """
    if s.deal_type != "asset":
        return None
    return TaxLatencyFlag(
        rule_id="be_vat_share_vs_asset",
        jurisdiction="BE",
        label="Asset-deal VAT exposure",
        rationale=(
            "Asset deal triggers 21% VAT on transferred assets "
            "(12% / 6% reduced rates for specific categories). "
            "Share deal is VAT-exempt. Compare net proceeds before locking deal form."
        ),
        severity="info",
    )


def _rule_be_management_fee_circularity(s: TaxLatencySignals) -> Optional[TaxLatencyFlag]:
    """Trigger: intercompany management fees present (any amount > 0).

    Buyer will challenge whether the management fee inflates EBITDA at
    OpCo. Standard normalisation issue in BE holding structures.
    """
    if s.intercompany_management_fees is None:
        return None
    if s.intercompany_management_fees > 0:
        return TaxLatencyFlag(
            rule_id="be_management_fee_circularity",
            jurisdiction="BE",
            label="Intercompany management fee — normalisation review",
            rationale=(
                f"Intercompany management fees €{s.intercompany_management_fees:,.0f} "
                "paid OpCo → HoldCo. Buyer will challenge EBITDA inflation; "
                "ensure normalisation bridge shows the elimination."
            ),
            severity="info",
            estimated_impact_eur=int(round(s.intercompany_management_fees)),
        )
    return None


def _rule_be_consolidated_goodwill(s: TaxLatencySignals) -> Optional[TaxLatencyFlag]:
    """Trigger: consolidated goodwill > €0 on balance sheet.

    BE goodwill amortisation tax treatment differs from IFRS — confirm
    base for any new acquisition that emerges from the buyer.
    """
    if s.consolidated_goodwill is None:
        return None
    if s.consolidated_goodwill > 0:
        return TaxLatencyFlag(
            rule_id="be_consolidated_goodwill_amortisation",
            jurisdiction="BE",
            label="Consolidated goodwill — amortisation treatment",
            rationale=(
                f"Consolidated goodwill €{s.consolidated_goodwill:,.0f} on balance sheet. "
                "BE amortisation rules differ from IFRS — confirm tax base before legal handoff."
            ),
            severity="info",
        )
    return None


def _rule_be_carry_forward_losses(s: TaxLatencySignals) -> Optional[TaxLatencyFlag]:
    """Trigger: carry-forward losses present.

    Carry-forward losses can be a deal asset (reduces buyer's tax bill)
    or a liability (restrictions apply on change-of-control). Always
    flag for advisor review.
    """
    if s.carry_forward_losses is None:
        return None
    if s.carry_forward_losses > 0:
        return TaxLatencyFlag(
            rule_id="be_carry_forward_losses",
            jurisdiction="BE",
            label="Carry-forward losses — change-of-control review",
            rationale=(
                f"Carry-forward losses €{s.carry_forward_losses:,.0f} on the books. "
                "BE change-of-control rules may limit utilisation post-acquisition. "
                "Confirm restrictions before legal handoff — can be a value driver or limiter."
            ),
            severity="info",
        )
    return None


BE_RULES: tuple[Callable[[TaxLatencySignals], Optional[TaxLatencyFlag]], ...] = (
    _rule_be_liquidatiebonus,
    _rule_be_dtl_revalued_assets,
    _rule_be_vendor_loans,
    _rule_be_vat_share_vs_asset,
    _rule_be_management_fee_circularity,
    _rule_be_consolidated_goodwill,
    _rule_be_carry_forward_losses,
)


# ---------------------------------------------------------------------
# Netherlands rules
# ---------------------------------------------------------------------


def _rule_nl_box2_dga_salary(s: TaxLatencySignals) -> Optional[TaxLatencyFlag]:
    """Trigger: owner_compensation < DGA minimum wage (€56k for 2026).

    Under-paying owner = upward EBITDA normalisation needed = larger
    tax liability for the buyer. The Dutch revenue service can assess
    additional wage tax retroactively.
    """
    if s.owner_compensation_annual is None:
        return None
    if s.owner_compensation_annual < NL_DGA_MINIMUM_SALARY_EUR:
        gap = NL_DGA_MINIMUM_SALARY_EUR - s.owner_compensation_annual
        return TaxLatencyFlag(
            rule_id="nl_box2_dga_salary",
            jurisdiction="NL",
            label="DGA-salary normalisation (box 2)",
            rationale=(
                f"Owner compensation €{s.owner_compensation_annual:,.0f} below "
                f"the wettelijk DGA minimum €{NL_DGA_MINIMUM_SALARY_EUR:,.0f}. "
                f"Gap €{gap:,.0f}. Buyer will require upward EBITDA normalisation "
                "and may discount for retroactive wage-tax exposure."
            ),
            severity="warning",
            estimated_impact_eur=int(round(gap)),
        )
    return None


def _rule_nl_latent_dtl_goodwill(s: TaxLatencySignals) -> Optional[TaxLatencyFlag]:
    """Trigger: consolidated goodwill > 0.

    Dutch goodwill amortisation rules differ from IFRS; latent DTL
    exposure where book amortisation diverges from fiscal amortisation.
    """
    if s.consolidated_goodwill is None:
        return None
    if s.consolidated_goodwill > 0:
        return TaxLatencyFlag(
            rule_id="nl_latent_dtl_goodwill",
            jurisdiction="NL",
            label="Latent DTL on goodwill",
            rationale=(
                f"Consolidated goodwill €{s.consolidated_goodwill:,.0f}. "
                "Dutch fiscal amortisation (min 10 yrs) typically slower than "
                "book amortisation — latent DTL likely on the balance sheet. "
                "Confirm with tax adviser before legal handoff."
            ),
            severity="info",
        )
    return None


def _rule_nl_30pct_ruling_expiry(s: TaxLatencySignals) -> Optional[TaxLatencyFlag]:
    """Trigger: ≥1 employee on 30%-ruling expiring within 24 months.

    If a key employee's net pay drops sharply after their 30%-ruling
    expires, retention risk surfaces post-deal.
    """
    if s.employees_with_30pct_ruling_expiring_24m is None:
        return None
    if s.employees_with_30pct_ruling_expiring_24m > 0:
        return TaxLatencyFlag(
            rule_id="nl_thirty_percent_ruling_expiry",
            jurisdiction="NL",
            label="30%-ruling expiry within 24 months",
            rationale=(
                f"{s.employees_with_30pct_ruling_expiring_24m} employee(s) "
                f"on the 30%-ruling expiring within {NL_30PCT_RULING_EXPIRY_MONTHS} months. "
                "Net-pay cliff = retention risk post-deal. "
                "Disclose to buyer and price into the team transition plan."
            ),
            severity="info",
        )
    return None


NL_RULES: tuple[Callable[[TaxLatencySignals], Optional[TaxLatencyFlag]], ...] = (
    _rule_nl_box2_dga_salary,
    _rule_nl_latent_dtl_goodwill,
    _rule_nl_30pct_ruling_expiry,
)


# ---------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------


def compute_tax_latency(signals: TaxLatencySignals) -> TaxLatencyResult:
    """Run the appropriate jurisdiction rule set.

    BE entity → BE_RULES dispatch (NL rules silent).
    NL entity → NL_RULES dispatch (BE rules silent).
    Output is deterministic: same signals → same flag list, same order.

    Args:
        signals: assembled by Titan from TitanYearData + Owner Profile
            + balance-sheet signals.

    Returns:
        `TaxLatencyResult` with `flags` in fixed rule order. Empty
        `flags` is a valid result (no latent exposures detected).
    """
    if signals.country_code == "BE":
        rule_set = BE_RULES
    elif signals.country_code == "NL":
        rule_set = NL_RULES
    else:
        # Defensive — Literal type should prevent this; keeps mypy
        # exhaustive-check happy.
        return TaxLatencyResult(jurisdiction=signals.country_code, flags=[])

    flags: List[TaxLatencyFlag] = []
    for rule in rule_set:
        flag = rule(signals)
        if flag is not None:
            flags.append(flag)
    return TaxLatencyResult(jurisdiction=signals.country_code, flags=flags)


__all__ = [
    "BE_DTL_REVALUATION_THRESHOLD_PCT",
    "BE_LIQUIDATIEBONUS_OWNER_AGE_THRESHOLD",
    "BE_LIQUIDATIEBONUS_RESERVE_THRESHOLD_EUR",
    "BE_LIQUIDATIEBONUS_TAX_RATE",
    "BE_RULES",
    "BE_VENDOR_LOAN_THRESHOLD_EUR",
    "NL_30PCT_RULING_EXPIRY_MONTHS",
    "NL_DGA_MINIMUM_SALARY_EUR",
    "NL_RULES",
    "TaxLatencyFlag",
    "TaxLatencyJurisdiction",
    "TaxLatencyResult",
    "TaxLatencyRuleID",
    "TaxLatencySeverity",
    "TaxLatencySignals",
    "compute_tax_latency",
]
