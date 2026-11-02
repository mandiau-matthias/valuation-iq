"""Versioned jurisdiction packs used by the canonical valuation kernel.

Country packs are policy inputs, not narrative defaults.  Their dates and
official sources are carried into the calculation lineage; an unknown pack or
an unresolved conditional tax regime must never inherit Belgian economics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Mapping

from src.domain.method_certification_profiles import supported_certification_methods
from src.config.country_pack_extensions import EXTENDED_COUNTRY_POLICIES

COUNTRY_PACK_SCHEMA_VERSION = "country_pack.v1"
CountryPackCertificationState = Literal["draft", "certified", "expired", "revoked"]


@dataclass(frozen=True)
class EconomicSnapshotBlocker:
    issue: str
    field: str
    reason: str
    value: object = None


@dataclass(frozen=True)
class TaxRegime:
    key: str
    rate: Decimal
    applicability: str
    source_url: str


@dataclass(frozen=True)
class CountryPack:
    schema_version: str
    country_code: str
    pack_version: str
    effective_from: date
    effective_to: date | None
    currency: str
    risk_free_rate_source: str
    equity_risk_premium_source: str
    long_term_growth_source: str
    tax_regimes: Mapping[str, TaxRegime]
    supported_methods: tuple[str, ...]
    statutory_methods: tuple[str, ...]
    benchmark_freshness_days: int
    macro_freshness_days: int
    official_sources: tuple[str, ...]
    official_sources_retrieved_at: date
    fx_policy: str
    required_economic_observation_fields: tuple[str, ...]
    jurisdiction_restrictions: tuple[str, ...]
    liquidation_policy: str
    legal_disclosures: tuple[str, ...]
    certification_state: CountryPackCertificationState = "draft"
    certification_manifest_hash: str | None = None
    certification_reviewer_receipt_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.certification_state == "certified":
            digest = self.certification_manifest_hash or ""
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("certified CountryPack requires a lowercase SHA-256 manifest")
            if len(set(self.certification_reviewer_receipt_ids)) < 3:
                raise ValueError("certified CountryPack requires three distinct reviewer receipts")


COUNTRY_PACKS: Mapping[str, CountryPack] = {
    "BE": CountryPack(
        schema_version=COUNTRY_PACK_SCHEMA_VERSION,
        country_code="BE",
        pack_version="BE.2026.1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        currency="EUR",
        risk_free_rate_source="National Bank of Belgium / ECB, source-dated 10Y sovereign series",
        equity_risk_premium_source="governed EU market-risk snapshot",
        long_term_growth_source="IMF WEO / ECB governed macro snapshot",
        tax_regimes={
            "standard": TaxRegime(
                key="standard",
                rate=Decimal("0.25"),
                applicability="Belgian standard corporate income tax",
                source_url="https://finance.belgium.be/en/enterprises/corporation-tax",
            ),
            "sme_reduced": TaxRegime(
                key="sme_reduced",
                rate=Decimal("0.20"),
                applicability="First qualifying profit tranche when all statutory SME conditions pass",
                source_url="https://finance.belgium.be/en/enterprises/corporation-tax",
            ),
        },
        supported_methods=supported_certification_methods("BE"),
        statutory_methods=("fiscal_4x",),
        benchmark_freshness_days=365,
        macro_freshness_days=120,
        official_sources=("https://finance.belgium.be/", "https://www.nbb.be/"),
        official_sources_retrieved_at=date(2026, 8, 13),
        fx_policy="EUR native; non-EUR inputs require an explicit source-dated FX snapshot",
        required_economic_observation_fields=(
            "risk_free_rate_observed_at",
            "equity_risk_premium_observed_at",
            "growth_rates_observed_at",
        ),
        jurisdiction_restrictions=(
            "fiscal_4x is a Belgian statutory/reference lens and never a market-value substitute",
            "SME reduced tax rate applies only after all statutory conditions are evidenced",
        ),
        liquidation_policy="Apply instrument priority, realizable asset values, wind-down costs and tax leakage at the measurement date",
        legal_disclosures=(
            "Calculation certification does not constitute a legal, tax or fairness opinion",
        ),
    ),
    "FR": CountryPack(
        schema_version=COUNTRY_PACK_SCHEMA_VERSION,
        country_code="FR",
        pack_version="FR.2026.1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        currency="EUR",
        risk_free_rate_source="Banque de France / ECB, source-dated 10Y sovereign series",
        equity_risk_premium_source="governed EU market-risk snapshot",
        long_term_growth_source="IMF WEO / Banque de France governed macro snapshot",
        tax_regimes={
            "standard": TaxRegime(
                key="standard",
                rate=Decimal("0.25"),
                applicability="French standard corporate income tax",
                source_url="https://www.impots.gouv.fr/international-professionnel/corporate-tax",
            )
        },
        supported_methods=supported_certification_methods("FR"),
        statutory_methods=(),
        benchmark_freshness_days=365,
        macro_freshness_days=120,
        official_sources=("https://www.impots.gouv.fr/", "https://www.banque-france.fr/"),
        official_sources_retrieved_at=date(2026, 8, 13),
        fx_policy="EUR native; non-EUR inputs require an explicit source-dated FX snapshot",
        required_economic_observation_fields=(
            "risk_free_rate_observed_at",
            "equity_risk_premium_observed_at",
            "growth_rates_observed_at",
        ),
        jurisdiction_restrictions=(
            "Belgian fiscal_4x is not applicable",
            "Reduced or exceptional tax treatment requires jurisdiction-specific evidence",
        ),
        liquidation_policy=(
            "Unsupported: French liquidation priority, tax leakage and legal disclosure "
            "are not implemented in the canonical kernel"
        ),
        legal_disclosures=(
            "Calculation certification does not constitute a legal, tax or fairness opinion",
        ),
    ),
    "IE": CountryPack(
        schema_version=COUNTRY_PACK_SCHEMA_VERSION,
        country_code="IE",
        pack_version="IE.2026.1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        currency="EUR",
        risk_free_rate_source="Central Bank of Ireland / ECB, source-dated 10Y sovereign series",
        equity_risk_premium_source="governed EU market-risk snapshot",
        long_term_growth_source="IMF WEO / Central Bank of Ireland governed macro snapshot",
        tax_regimes={
            "trading": TaxRegime(
                key="trading",
                rate=Decimal("0.125"),
                applicability="Irish trading income outside a higher applicable minimum-tax outcome",
                source_url="https://www.revenue.ie/en/companies-and-charities/corporation-tax-for-companies/corporation-tax/basis-of-charge.aspx",
            ),
            "non_trading": TaxRegime(
                key="non_trading",
                rate=Decimal("0.25"),
                applicability="Irish non-trading or investment income",
                source_url="https://www.revenue.ie/en/companies-and-charities/corporation-tax-for-companies/corporation-tax/basis-of-charge.aspx",
            ),
            "pillar_two": TaxRegime(
                key="pillar_two",
                rate=Decimal("0.15"),
                applicability="In-scope Pillar Two group minimum effective tax assumption",
                source_url="https://www.revenue.ie/en/companies-and-charities/pillar-two/index.aspx",
            ),
        },
        supported_methods=supported_certification_methods("IE"),
        statutory_methods=(),
        benchmark_freshness_days=365,
        macro_freshness_days=120,
        official_sources=("https://www.revenue.ie/", "https://www.centralbank.ie/"),
        official_sources_retrieved_at=date(2026, 8, 13),
        fx_policy="EUR native; non-EUR inputs require an explicit source-dated FX snapshot",
        required_economic_observation_fields=(
            "risk_free_rate_observed_at",
            "equity_risk_premium_observed_at",
            "growth_rates_observed_at",
        ),
        jurisdiction_restrictions=(
            "Belgian fiscal_4x is not applicable",
            "DCF is excluded or scenario-only until trading, non-trading or Pillar Two treatment is evidenced",
        ),
        liquidation_policy=(
            "Unsupported: Irish liquidation priority, tax leakage and legal disclosure "
            "are not implemented in the canonical kernel"
        ),
        legal_disclosures=(
            "Calculation certification does not constitute a legal, tax or fairness opinion",
        ),
    ),
    "LT": CountryPack(
        schema_version=COUNTRY_PACK_SCHEMA_VERSION,
        country_code="LT",
        pack_version="LT.2026.1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        currency="EUR",
        risk_free_rate_source=(
            "ECB long-term interest rate for convergence purposes, Lithuania, "
            "source-dated 10Y EUR series IRS.M.LT.L.L40.CI.0000.EUR.N.Z"
        ),
        equity_risk_premium_source="governed EU market-risk snapshot",
        long_term_growth_source="Bank of Lithuania governed macroeconomic projections",
        tax_regimes={
            "standard": TaxRegime(
                key="standard",
                rate=Decimal("0.17"),
                applicability=(
                    "Lithuanian standard corporate income tax for tax periods beginning "
                    "on or after 1 January 2026"
                ),
                source_url=(
                    "https://finmin.lrv.lt/en/competence-areas/taxation/main-taxes/"
                    "corporate-income-tax/"
                ),
            ),
            "small": TaxRegime(
                key="small",
                rate=Decimal("0.07"),
                applicability=(
                    "Qualifying small entity with tax-period income not exceeding EUR "
                    "300,000 and every statutory related-entity condition evidenced"
                ),
                source_url="https://www.vmi.lt/evmi/5724?lang=en",
            ),
            "new_entity": TaxRegime(
                key="new_entity",
                rate=Decimal("0.00"),
                applicability=(
                    "First and second qualifying tax periods only when every statutory "
                    "new-entity, ownership, income and continuity condition is evidenced"
                ),
                source_url="https://www.vmi.lt/evmi/5724?lang=en",
            ),
        },
        supported_methods=supported_certification_methods("LT"),
        statutory_methods=(),
        benchmark_freshness_days=365,
        macro_freshness_days=120,
        official_sources=(
            "https://finmin.lrv.lt/en/competence-areas/taxation/main-taxes/corporate-income-tax/",
            "https://www.vmi.lt/evmi/5724?lang=en",
            "https://data.ecb.europa.eu/data/datasets/IRS/IRS.M.LT.L.L40.CI.0000.EUR.N.Z",
            "https://www.lb.lt/en/latest-economic-projections",
        ),
        official_sources_retrieved_at=date(2026, 9, 1),
        fx_policy="EUR native; non-EUR inputs require an explicit source-dated FX snapshot",
        required_economic_observation_fields=(
            "risk_free_rate_observed_at",
            "equity_risk_premium_observed_at",
            "growth_rates_observed_at",
        ),
        jurisdiction_restrictions=(
            "Belgian fiscal_4x is not applicable",
            "The 7% small-entity and 0% new-entity rates require complete statutory "
            "eligibility evidence; missing evidence defaults to the conservative 17% rate",
            "Reduced, exceptional, bank, cooperative, project, or sector-specific tax "
            "treatment requires explicit evidence",
        ),
        liquidation_policy=(
            "Unsupported: Lithuanian liquidation priority, tax leakage and legal disclosure "
            "are not implemented in the canonical kernel"
        ),
        legal_disclosures=(
            "Calculation certification does not constitute a legal, tax or fairness opinion",
        ),
    ),
    "SK": CountryPack(
        schema_version=COUNTRY_PACK_SCHEMA_VERSION,
        country_code="SK",
        pack_version="SK.2026.1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        currency="EUR",
        risk_free_rate_source=(
            "National Bank of Slovakia, source-dated 10Y Slovak government bond series"
        ),
        equity_risk_premium_source="governed EU market-risk snapshot",
        long_term_growth_source="National Bank of Slovakia governed macro forecast",
        tax_regimes={
            "small": TaxRegime(
                key="small",
                rate=Decimal("0.10"),
                applicability=(
                    "Taxable revenue not exceeding EUR 100,000 for tax periods beginning "
                    "on or after 1 January 2025"
                ),
                source_url=(
                    "https://www.financnasprava.sk/sk/podnikatelia/dane/"
                    "dan-z-prijmov/pravnicke-osoby/informovanie-dan-prijem-po"
                ),
            ),
            "standard": TaxRegime(
                key="standard",
                rate=Decimal("0.21"),
                applicability=("Taxable revenue above EUR 100,000 and not exceeding EUR 5,000,000"),
                source_url=(
                    "https://www.financnasprava.sk/sk/podnikatelia/dane/"
                    "dan-z-prijmov/pravnicke-osoby/informovanie-dan-prijem-po"
                ),
            ),
            "large": TaxRegime(
                key="large",
                rate=Decimal("0.24"),
                applicability=(
                    "Taxable revenue exceeding EUR 5,000,000 for tax periods beginning "
                    "on or after 1 January 2025"
                ),
                source_url=(
                    "https://www.financnasprava.sk/sk/podnikatelia/dane/"
                    "dan-z-prijmov/pravnicke-osoby/informovanie-dan-prijem-po"
                ),
            ),
        },
        supported_methods=supported_certification_methods("SK"),
        statutory_methods=(),
        benchmark_freshness_days=365,
        macro_freshness_days=120,
        official_sources=(
            "https://www.financnasprava.sk/",
            "https://nbs.sk/en/",
        ),
        official_sources_retrieved_at=date(2026, 8, 31),
        fx_policy="EUR native; non-EUR inputs require an explicit source-dated FX snapshot",
        required_economic_observation_fields=(
            "risk_free_rate_observed_at",
            "equity_risk_premium_observed_at",
            "growth_rates_observed_at",
        ),
        jurisdiction_restrictions=(
            "Belgian fiscal_4x is not applicable",
            "The 10%, 21%, and 24% corporate tax bands require source-period taxable-revenue evidence",
            "Reduced, exceptional, or sector-specific tax treatment requires explicit evidence",
        ),
        liquidation_policy=(
            "Unsupported: Slovak liquidation priority, tax leakage and legal disclosure "
            "are not implemented in the canonical kernel"
        ),
        legal_disclosures=(
            "Calculation certification does not constitute a legal, tax or fairness opinion",
        ),
    ),
    "EE": CountryPack(
        schema_version=COUNTRY_PACK_SCHEMA_VERSION,
        country_code="EE",
        pack_version="EE.2026.2",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        currency="EUR",
        risk_free_rate_source=(
            "Eesti Pank / ECB Statistical Data Warehouse, source-dated 10Y Estonian "
            "government bond series"
        ),
        equity_risk_premium_source="governed EU market-risk snapshot",
        long_term_growth_source="Eesti Pank governed macro forecast",
        tax_regimes={
            # Reference only: tax arises on distributions, not accrued EBIT.
            "distribution_reference": TaxRegime(
                key="distribution_reference",
                rate=Decimal("0.22"),
                applicability=(
                    "Distributed profit only, for tax periods beginning on or after "
                    "1 January 2025 (22/78 of the net distribution). Undistributed and "
                    "reinvested profit is taxed at 0%. The reduced 14/86 rate on regular "
                    "distributions was repealed with effect from 1 January 2025"
                ),
                source_url="https://www.emta.ee/en/business-client/taxes-and-payment/income-tax",
            ),
        },
        supported_methods=supported_certification_methods("EE"),
        statutory_methods=(),
        benchmark_freshness_days=365,
        macro_freshness_days=120,
        official_sources=(
            "https://www.emta.ee/en",
            "https://www.eestipank.ee/en",
            "https://ariregister.rik.ee/eng",
        ),
        official_sources_retrieved_at=date(2026, 9, 1),
        fx_policy="EUR native; non-EUR inputs require an explicit source-dated FX snapshot",
        required_economic_observation_fields=(
            "risk_free_rate_observed_at",
            "equity_risk_premium_observed_at",
            "growth_rates_observed_at",
        ),
        jurisdiction_restrictions=(
            "Belgian fiscal_4x is not applicable",
            "Estonia taxes distributed profit. Distribution timing and other taxable "
            "payments require an explicit cash-tax model; neither a flat 22% EBIT "
            "charge nor a permanent 0% assumption follows from a sale valuation",
            "Reduced, exceptional, or sector-specific tax treatment requires explicit evidence",
        ),
        liquidation_policy=(
            "Unsupported: Estonian liquidation priority, tax leakage and legal disclosure "
            "are not implemented in the canonical kernel"
        ),
        legal_disclosures=(
            "Calculation certification does not constitute a legal, tax or fairness opinion",
            "Estonian corporate income tax is levied on distribution, not on accrual; any "
            "tax figure shown is a modelled distribution charge, not an assessed liability",
        ),
    ),
}


# New reference packs deliberately retain the existing method-certification
# scope. Completing tax/currency discovery cannot manufacture benchmarks,
# accounting mappings or calculation-review receipts.
COUNTRY_PACKS = {
    **COUNTRY_PACKS,
    **{
        code: CountryPack(
            schema_version=COUNTRY_PACK_SCHEMA_VERSION,
            country_code=code,
            pack_version=f"{code}.2026.1",
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            currency=currency,
            risk_free_rate_source="Source-dated sovereign curve in the cash-flow currency",
            equity_risk_premium_source="Governed market-risk snapshot in consistent units",
            long_term_growth_source="Source-dated nominal growth consistent with cash-flow currency",
            tax_regimes={scope: TaxRegime(scope, Decimal(rate), restriction, source)},
            supported_methods=supported_certification_methods(code),
            statutory_methods=(),
            benchmark_freshness_days=365,
            macro_freshness_days=120,
            official_sources=(source,),
            official_sources_retrieved_at=date(2026, 10, 1),
            fx_policy=f"{currency} native; cross-currency inputs require an explicit source-dated FX snapshot",
            required_economic_observation_fields=(
                "risk_free_rate_observed_at",
                "equity_risk_premium_observed_at",
                "growth_rates_observed_at",
            ),
            jurisdiction_restrictions=(
                restriction,
                "Reference pack only: local accounting mappings and method certification remain unverified",
                "Belgian fiscal_4x is not applicable",
            ),
            liquidation_policy="Unsupported: jurisdiction-specific liquidation priority and tax leakage have not been reviewed",
            legal_disclosures=(
                "Tax references do not establish an entity-specific effective tax rate",
                "Calculation certification does not constitute a legal, tax or fairness opinion",
            ),
        )
        for code, (
            currency,
            rate,
            scope,
            source,
            restriction,
        ) in EXTENDED_COUNTRY_POLICIES.items()
    },
}


def country_pack(country_code: str) -> CountryPack | None:
    return COUNTRY_PACKS.get(str(country_code or "").strip().upper())


def dcf_country_configuration_blocker(
    country_code: str,
    business_context: Mapping[str, object] | None,
) -> str | None:
    code = str(country_code or "").strip().upper()
    pack = country_pack(code)
    if (
        code in EXTENDED_COUNTRY_POLICIES
        and pack is not None
        and "standard" not in pack.tax_regimes
    ):
        return (
            f"{code} DCF requires an explicit governed effective-tax model; "
            "the country pack contains a component reference, not an all-in tax rate"
        )
    if code == "EE":
        return "Estonia DCF requires an explicit governed effective-tax model; distribution taxation is not an earnings tax"
    if code != "IE":
        return None
    regime = str((business_context or {}).get("irish_tax_regime") or "").strip().lower()
    if regime not in COUNTRY_PACKS["IE"].tax_regimes:
        return (
            "Ireland DCF requires governed irish_tax_regime evidence: "
            "trading, non_trading, or pillar_two"
        )
    return None


def dcf_economic_snapshot_blocker(
    country_code: str,
    economic_context: object,
    *,
    valuation_date: date | None = None,
) -> EconomicSnapshotBlocker | None:
    """Fail DCF closed when macro inputs are ungoverned, future-dated or stale."""
    pack = country_pack(country_code)
    if pack is None:
        return EconomicSnapshotBlocker(
            issue="country_pack_missing",
            field="country_code",
            reason=f"No CountryPack is configured for {country_code!r}",
            value=country_code,
        )

    required_identity = ("schema_version", "snapshot_id", "snapshot_hash", "snapshot_issuer")
    missing_identity = [
        field for field in required_identity if not getattr(economic_context, field, None)
    ]
    missing_dates = [
        field
        for field in pack.required_economic_observation_fields
        if getattr(economic_context, field, None) is None
    ]
    source_references = getattr(economic_context, "source_references", None) or []
    source = str(getattr(economic_context, "source", "") or "").strip().lower()
    if missing_identity or missing_dates or not source_references or source == "static_defaults":
        missing = [*missing_identity, *missing_dates]
        if not source_references:
            missing.append("source_references")
        if source == "static_defaults":
            missing.append("governed_source")
        return EconomicSnapshotBlocker(
            issue="economic_snapshot_missing_or_ungoverned",
            field="economic_context",
            reason=(
                "DCF requires a sealed, source-dated economic_snapshot.v1; "
                f"missing or ungoverned: {', '.join(missing)}"
            ),
            value={"missing_or_ungoverned": missing},
        )

    as_of = valuation_date or date.today()
    observed_dates = {
        field: getattr(economic_context, field)
        for field in pack.required_economic_observation_fields
    }
    future = {
        field: observed.isoformat()
        for field, observed in observed_dates.items()
        if observed > as_of
    }
    if future:
        return EconomicSnapshotBlocker(
            issue="economic_snapshot_future_dated",
            field="economic_context",
            reason="DCF economic evidence cannot be observed after the valuation lens date",
            value=future,
        )

    stale = {
        field: {"observed_at": observed.isoformat(), "age_days": (as_of - observed).days}
        for field, observed in observed_dates.items()
        if (as_of - observed).days > pack.macro_freshness_days
    }
    if stale:
        return EconomicSnapshotBlocker(
            issue="economic_snapshot_stale",
            field="economic_context",
            reason=(
                f"DCF economic evidence exceeds the {pack.macro_freshness_days}-day "
                f"freshness limit in CountryPack {pack.pack_version}"
            ),
            value=stale,
        )
    return None


def resolve_country_pack_tax_rate(
    country_code: str,
    business_context: Mapping[str, object] | None,
) -> Decimal:
    code = str(country_code or "").strip().upper()
    pack = country_pack(code)
    if pack is None:
        raise ValueError(f"no certified CountryPack configured for {code!r}")
    blocker = dcf_country_configuration_blocker(code, business_context)
    if blocker:
        raise ValueError(blocker)
    if code == "IE":
        regime = str((business_context or {}).get("irish_tax_regime")).strip().lower()
        return pack.tax_regimes[regime].rate
    return pack.tax_regimes["standard"].rate
