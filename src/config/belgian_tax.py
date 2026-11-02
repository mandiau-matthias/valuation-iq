"""Belgian corporate income tax (CIT) rate logic.

Centralises the resolution between the standard 25% rate and the reduced
20% SME rate (Art. 215 WIB 92) so the engine has a single source of truth
for fiscal calculations involving:
  - Adjusted NAV deferred-tax (latente belastingen) on revaluation surplus
  - DCF tax-rate defaults
  - Goodwill amortisation tax-shield NPV (Art. 61 WIB 92)
  - Asset-vs-share deal seller / buyer tax comparisons
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Literal, Optional

# ---------------------------------------------------------------------------
# Statutory constants
# ---------------------------------------------------------------------------

# Belgian standard corporate income tax rate (since 2020).
STANDARD_CIT_RATE: Decimal = Decimal("25")

# Reduced rate for qualifying SMEs on the first EUR 100,000 of taxable
# profit (Art. 215 WIB 92).
REDUCED_SME_CIT_RATE: Decimal = Decimal("20")

# Upper limit of the reduced-rate bracket, NOT an eligibility ceiling.
SME_PROFIT_THRESHOLD: Decimal = Decimal("100000")

# Legacy compatibility constant only. It is not used to determine eligibility:
# the applicable tax period and all legal conditions require dated evidence.
SME_MINIMUM_DIRECTOR_REMUNERATION: Decimal = Decimal("45000")

# Goodwill amortisation: Belgian fiscal practice accepts a 5-year linear
# amortisation of acquired goodwill in an asset deal (handelsfonds).
# Some files apply a longer life if economically justified; 5y is the
# defensible default.
GOODWILL_AMORTISATION_YEARS: int = 5

# Movables registration duty estimate for asset deals — assumed average,
# left as a constant so it can be overridden by region.
MOVABLES_REGISTRATION_DUTY_PCT: Decimal = Decimal("0")  # 0% on most movables

# Capital-gains tax rate that applies to private shareholders selling
# shares as of 01/01/2026 (Art. 90 / 95 WIB 92, "meerwaardebelasting").
PRIVATE_SHARE_CAPITAL_GAINS_RATE: Decimal = Decimal("10")

# Default rate applied to a corporate seller's capital gain on the sale
# of a goodwill (handelsfonds). Falls back to the standard CIT rate.
ASSET_DEAL_GOODWILL_GAIN_RATE: Decimal = STANDARD_CIT_RATE


# ---------------------------------------------------------------------------
# SME eligibility & rate resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SmeEligibility:
    """Eligibility scenario and the separately identified modelling rate.

    ``is_eligible`` never implies that ``rate`` is a flat 20%: a qualifying
    company's profits above the first bracket remain subject to 25%.
    """

    is_eligible: bool
    rate: Decimal
    reasons: tuple[str, ...]
    rate_basis: str = "statutory_flat_assumption"

    def to_dict(self) -> dict[str, object]:
        return {
            "is_eligible": self.is_eligible,
            "rate_pct": float(self.rate),
            "reasons": list(self.reasons),
            "rate_basis": self.rate_basis,
        }


def is_sme_eligible(
    *,
    taxable_profit: Optional[Decimal] = None,
    director_remuneration: Optional[Decimal] = None,
    is_financial_company: Optional[bool] = None,
    is_holding_more_than_50pct_shares: Optional[bool] = None,
    explicit_override: Optional[bool] = None,
) -> SmeEligibility:
    """Resolve an SME eligibility scenario without inferring legal relief.

    Profit and director pay alone cannot establish all Art. 215 conditions
    (including company size, exclusions and the applicable tax period).
    Until that dated evidence is modelled, only an explicit boolean advisor
    assertion may select the reduced bracket. It is disclosed as a scenario.
    Known exclusions still take precedence over that assertion.
    """
    if explicit_override is not None and not isinstance(explicit_override, bool):
        raise ValueError("SME eligibility override must be a boolean")

    # Hard disqualifiers
    if is_financial_company is True:
        return SmeEligibility(
            False,
            STANDARD_CIT_RATE,
            ("Financial / investment company — excluded from Art. 215.",),
        )
    if is_holding_more_than_50pct_shares is True:
        return SmeEligibility(
            False,
            STANDARD_CIT_RATE,
            ("Shares held >50% by another company — excluded from Art. 215.",),
        )
    if explicit_override is True:
        return SmeEligibility(
            True,
            REDUCED_SME_CIT_RATE,
            (
                "Advisor-supplied SME eligibility scenario; confirm all conditions for the tax period.",
                "Reduced 20% applies only to the first EUR 100,000 of taxable profit; 25% above it.",
            ),
            "reduced_first_bracket",
        )
    reason = (
        "Advisor excluded reduced-rate eligibility."
        if explicit_override is False
        else "SME eligibility unknown: profit and director remuneration do not establish all dated legal conditions."
    )
    return SmeEligibility(
        False, STANDARD_CIT_RATE, (reason, "Standard 25% modelling assumption applied.")
    )


def belgian_corporate_tax_amount(
    taxable_profit: Decimal, *, reduced_rate_eligible: bool
) -> Decimal:
    """Unrounded period-tax scenario, before credits, losses and other relief.

    Tax(P) = .20 min(max(P, 0), 100000) + .25 max(P - 100000, 0)
    for the eligible scenario, otherwise .25 max(P, 0). Negative profits do
    not create an immediate refund. Round monetary outputs at the boundary.
    """
    if not isinstance(taxable_profit, Decimal) or not taxable_profit.is_finite():
        raise ValueError("Taxable profit must be a finite Decimal")
    if not isinstance(reduced_rate_eligible, bool):
        raise ValueError("Reduced-rate eligibility must be a boolean")
    profit = max(taxable_profit, Decimal("0"))
    standard_tax = profit * STANDARD_CIT_RATE / Decimal("100")
    if not reduced_rate_eligible:
        return standard_tax
    relief = (
        min(profit, SME_PROFIT_THRESHOLD)
        * (STANDARD_CIT_RATE - REDUCED_SME_CIT_RATE)
        / Decimal("100")
    )
    return standard_tax - relief


def resolve_corporate_tax_rate(
    *,
    country_code: str = "BE",
    taxable_profit: Optional[Decimal] = None,
    director_remuneration: Optional[Decimal] = None,
    is_financial_company: Optional[bool] = None,
    is_holding_more_than_50pct_shares: Optional[bool] = None,
    explicit_override: Optional[bool] = None,
    explicit_rate_pct: Optional[Decimal] = None,
    rate_basis: Literal["flat_projection", "taxable_period"] = "flat_projection",
) -> SmeEligibility:
    """Public entry point. Returns the rate and the reasoning trail.

    A projection has no evidenced annual taxable-profit schedule. Its default
    is therefore the standard flat rate, even for an SME eligibility scenario.
    ``taxable_period`` explicitly requests a bracket-weighted average for one
    supplied profit only; it must not be reused for incremental gains or
    future cash flows. An explicit advisor rate is a separate flat assumption.

    For the other 15 product-exposed countries (Phase 4): pulls the top-bracket
    statutory CIT from Delphi via :mod:`src.services.country_data_service`. SME
    refinements specific to BE (Art. 215 20% on first €100k) are *not* applied
    cross-jurisdiction; the defensibility banner already calls out the
    "SME-rate refinements specific to Belgium are not modelled" caveat for
    non-BE reports. The only nuance the dispatcher *does* honour is that the
    returned ``rate`` matches the country's actual statutory CIT rather than
    silently defaulting to Belgium's 25% — that was the bug Phase 4 closes.

    Country code is normalised through the SoT alias map (UK → GB).
    """
    if explicit_rate_pct is not None:
        if (
            not isinstance(explicit_rate_pct, Decimal)
            or not explicit_rate_pct.is_finite()
            or not Decimal("0") <= explicit_rate_pct <= Decimal("100")
        ):
            raise ValueError("Explicit tax rate must be a finite Decimal percentage from 0 to 100")
        return SmeEligibility(
            False,
            Decimal(str(explicit_rate_pct)),
            (f"Explicit user-supplied rate: {explicit_rate_pct}%.",),
            "advisor_flat_rate",
        )
    if rate_basis not in ("flat_projection", "taxable_period"):
        raise ValueError("Unsupported corporate tax rate basis")

    normalised = (country_code or "BE").strip().upper()
    if normalised == "UK":
        normalised = "GB"

    if normalised == "BE":
        eligibility = is_sme_eligible(
            taxable_profit=taxable_profit,
            director_remuneration=director_remuneration,
            is_financial_company=is_financial_company,
            is_holding_more_than_50pct_shares=is_holding_more_than_50pct_shares,
            explicit_override=explicit_override,
        )
        if rate_basis == "taxable_period":
            if taxable_profit is None:
                raise ValueError("A taxable-period rate requires taxable profit")
            tax = belgian_corporate_tax_amount(
                taxable_profit, reduced_rate_eligible=eligibility.is_eligible
            )
            average = tax * Decimal("100") / taxable_profit if taxable_profit > 0 else Decimal("0")
            return replace(
                eligibility,
                rate=average,
                rate_basis="taxable_period_average",
                reasons=eligibility.reasons
                + (
                    "Average rate for the supplied taxable profit only; not a forecast or marginal rate.",
                ),
            )
        return replace(
            eligibility,
            rate=STANDARD_CIT_RATE,
            rate_basis="statutory_flat_assumption",
            reasons=eligibility.reasons
            + (
                "Flat 25% valuation assumption: future taxable profits and reduced-bracket utilisation are not evidenced.",
            ),
        )

    return _resolve_non_be_statutory_rate(normalised)


def _resolve_non_be_statutory_rate(country_code: str) -> SmeEligibility:
    """Look up the top-bracket statutory CIT for a non-BE country.

    Order of precedence:
      1. Delphi-backed runtime cache
         (``src.services.country_data_service.CountryDataService``).
      2. Static bootstrap dict (mirrors migration 071 seed) so the engine
         keeps producing defensible numbers when Delphi is unreachable at
         boot.
      3. ``STANDARD_CIT_RATE`` (25%) as the last-resort default — only hit
         when the country isn't in the supported set at all.

    Always returns ``is_eligible=False`` because the BE-specific Art. 215
    SME path doesn't apply outside Belgium (a separate per-country
    dispatcher would be needed to model NL 19% first-bracket, GB small
    profits 19%, PL 9% small taxpayer, etc. — flagged in Phase 4 follow-ups
    as the right next step). The reason string discloses the source so the
    audit trail is honest about which rate was used.
    """
    rate_pct: Optional[Decimal] = None
    source_label: str = "static_bootstrap"

    # 1. Try Delphi cache.
    try:
        from src.services.country_data_service import get_country_data_service

        cit_pct = get_country_data_service().get_corporate_tax_statutory(country_code)
        if cit_pct is not None and cit_pct > 0:
            rate_pct = Decimal(str(cit_pct))
            source_label = "delphi_runtime_cache"
    except Exception:  # pragma: no cover — defensive: never let a cache failure break tax math
        rate_pct = None

    # 2. Fall back to static bootstrap mirror of migration 071 seed.
    if rate_pct is None:
        bootstrap = _STATUTORY_CIT_BOOTSTRAP.get(country_code)
        if bootstrap is not None:
            rate_pct = bootstrap

    # 3. Last-resort: standard 25%.
    if rate_pct is None:
        return SmeEligibility(
            False,
            STANDARD_CIT_RATE,
            (
                f"Country {country_code} not in supported set — "
                f"defaulted to {STANDARD_CIT_RATE}% standard CIT.",
            ),
        )

    return SmeEligibility(
        False,
        rate_pct,
        (
            f"Country {country_code} statutory CIT {rate_pct}% "
            f"(source: {source_label}); SME-rate refinements "
            "specific to Belgium not applied.",
        ),
    )


# Phase 4 bootstrap mirror of migration 071 seed
# (apps/delphi/database/migrations/071_country_contextual_factors_currency_and_seed.sql).
# Used only when the Delphi cache is cold or Delphi is unreachable. Keep in
# lockstep with the migration seed and with the bootstrap maps in
# `tax-rate-by-country.util.ts` and `dcf_data_adapter.COUNTRY_DEFAULTS`.
_STATUTORY_CIT_BOOTSTRAP: dict[str, Decimal] = {
    "AT": Decimal("23"),
    # BE handled separately via Art. 215 dispatch above.
    "CH": Decimal("14.9"),
    "DE": Decimal("30"),
    "DK": Decimal("22"),
    "ES": Decimal("25"),
    "FI": Decimal("20"),
    "FR": Decimal("25"),
    "GB": Decimal("25"),
    "IT": Decimal("27.9"),
    "LU": Decimal("24.94"),
    "NL": Decimal("25.8"),
    "NO": Decimal("22"),
    "PL": Decimal("19"),
    "PT": Decimal("22.5"),
    "SE": Decimal("20.6"),
}


def effective_tax_rate_decimal(
    eligibility: SmeEligibility,
) -> Decimal:
    """Convert the selected rate to a fraction without rounding intermediate math."""
    return eligibility.rate / Decimal("100")


__all__ = [
    "STANDARD_CIT_RATE",
    "REDUCED_SME_CIT_RATE",
    "SME_PROFIT_THRESHOLD",
    "SME_MINIMUM_DIRECTOR_REMUNERATION",
    "GOODWILL_AMORTISATION_YEARS",
    "MOVABLES_REGISTRATION_DUTY_PCT",
    "PRIVATE_SHARE_CAPITAL_GAINS_RATE",
    "ASSET_DEAL_GOODWILL_GAIN_RATE",
    "SmeEligibility",
    "is_sme_eligible",
    "belgian_corporate_tax_amount",
    "resolve_corporate_tax_rate",
    "effective_tax_rate_decimal",
]
