"""Source-backed 2026 reference policies for the additional enabled markets.

These data complete jurisdiction discovery, not calculation certification.
No new method is certified by adding a country or a statutory tax reference.
Rates are decimal fractions. Applicability is part of the policy, not a footnote
that may be discarded when choosing a model tax rate.
"""

# code: currency, rate, tax scope, official source, modelling restriction
EXTENDED_COUNTRY_POLICIES = {
    "AT": (
        "EUR",
        "0.23",
        "standard",
        "https://www.bmf.gv.at/themen/steuern/fuer-unternehmen/einkommensteuer/einkommensbegriff.html",
        "Standard corporation tax; entity status, exemptions and loss utilisation require evidence.",
    ),
    "CH": (
        "CHF",
        "0.085",
        "federal_reference",
        "https://www.estv.admin.ch/en/tax-multipliers-deductions-and-tax-rates",
        "Federal reference on profit after tax, not an all-in EBIT cash-tax rate. Canton, municipality and tax deductibility require an explicit effective-tax model.",
    ),
    "DE": (
        "EUR",
        "0.15825",
        "federal_and_solidarity_reference",
        "https://www.gtai.de/en/invest/investment-guide/corporate-taxation-in-germany",
        "15% corporation tax plus solidarity surcharge on that tax; municipal trade tax is additional. An explicit location-specific combined tax model is required.",
    ),
    "DK": (
        "DKK",
        "0.22",
        "standard",
        "https://skat.dk/erhverv/selskaber-fonde-og-foreninger/selskaber-og-fonde/betal-acontoskat-og-selskabsskat",
        "Standard corporation tax; sector-specific treatment and loss utilisation require evidence.",
    ),
    "ES": (
        "EUR",
        "0.25",
        "standard",
        "https://sede.agenciatributaria.gob.es/Sede/impuesto-sobre-sociedades/que-base-imponible-se-determina-sociedades/tipo-impositivo.html",
        "General rate. 2026 qualifying micro/small-company rates depend on turnover, taxable-profit tranches and eligibility; do not infer from EBITDA.",
    ),
    "FI": (
        "EUR",
        "0.20",
        "standard",
        "https://www.vero.fi/en/businesses-and-corporations/taxes-and-charges/limited-companies-and-cooperatives/income-tax/",
        "2026 corporation tax reference; do not apply prospective reforms before their effective date.",
    ),
    "GB": (
        "GBP",
        "0.25",
        "standard",
        "https://www.gov.uk/corporation-tax-rates/rates",
        "Main rate. 19% small-profits rate and marginal relief require taxable profit, associated-company count and accounting-period length.",
    ),
    "IT": (
        "EUR",
        "0.24",
        "ires_reference",
        "https://www.investinitaly.gov.it/en/doing-business/taxation",
        "IRES only. IRAP is regional and uses a different tax base; adding 3.9 percentage points to every EBIT tax rate is not a general tax calculation.",
    ),
    "LU": (
        "EUR",
        "0.16",
        "national_reference",
        "https://impotsdirects.public.lu/fr/az/t/tarif-applicable-collectivites/tarif-collect.html",
        "National upper-band CIT only. Solidarity surcharge, municipality and small-profit bands require an explicit combined tax model; 23.87% is a Luxembourg-City example, not a national rate.",
    ),
    "NL": (
        "EUR",
        "0.258",
        "standard",
        "https://www.belastingdienst.nl/wps/wcm/connect/bldcontentnl/belastingdienst/zakelijk/winst/vennootschapsbelasting/tarieven_vennootschapsbelasting",
        "Upper marginal rate; 19% on the first EUR 200,000 taxable profit. A flat upper rate is an assumption, not exact SME tax.",
    ),
    "NO": (
        "NOK",
        "0.22",
        "standard",
        "https://www.skatteetaten.no/en/Rates/General-income/",
        "Ordinary corporation tax; financial-sector and resource-sector supplements require separate treatment.",
    ),
    "PL": (
        "PLN",
        "0.19",
        "standard",
        "https://podatki.gov.pl/podatki-firmowe/cit/cit-klasyczny/informacje-podstawowe-cit-klasyczny",
        "Standard CIT; 9% qualifying small/startup rate excludes capital gains and requires eligibility evidence.",
    ),
    "PT": (
        "EUR",
        "0.19",
        "national_reference",
        "https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/codigos_tributarios/CIRC_2R/Pages/irc87.aspx?print=true",
        "Mainland national rate for periods beginning in 2026 under Law 64/2025 transition. 18% in 2027, 17% from 2028; qualifying SMEs 15% on first EUR 50,000. Municipal/state surcharges and island regimes require explicit treatment.",
    ),
    "SE": (
        "SEK",
        "0.206",
        "standard",
        "https://www.skatteverket.se/foretag/drivaforetag/foretagsformer/aktiebolag.4.5c13cb6b1198121ee8580002546.html",
        "Standard corporation tax; loss utilisation and temporary differences require explicit forecast treatment.",
    ),
}
