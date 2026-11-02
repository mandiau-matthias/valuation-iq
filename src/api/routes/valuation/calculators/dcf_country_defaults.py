"""Country and industry defaults used by the DCF data adapter."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from src.services.country_data_service import get_country_data_service
from src.utils.percent_to_decimal import percentage_points_to_decimal_decimal

# Country-specific market defaults for the valuation-enabled countries.
# Sources:
#   - bond_yield: 10-year sovereign yield, Q1 2026 (Bloomberg / national CB).
#   - gdp_growth: IMF WEO long-term real GDP growth forecast.
#   - inflation: ECB / national CB inflation target (typically 2%).
#   - tax_rate: Top-bracket statutory CIT, mirrors
#     reference values only. DCF cash-tax resolution uses dcf_tax_policy.v2;
#     conditional/component/distribution references use a null sentinel.
#
# The DEFAULT row is reserved for unsupported countries; the engine should
# never reach it for a country in `SUPPORTED_COUNTRY_CODES`. The contract
# test in `test_dcf_country_defaults_parity` enforces 20-country coverage.
COUNTRY_DEFAULTS = {
    # Austria - flat CIT 23% from 2025, AAA sovereign.
    "AT": {
        "bond_yield": Decimal("0.029"),
        "gdp_growth": Decimal("0.014"),
        "inflation": Decimal("0.02"),
        "tax_rate": 0.23,
    },
    "BE": {
        "bond_yield": Decimal("0.025"),
        "gdp_growth": Decimal("0.015"),
        "inflation": Decimal("0.02"),
        "tax_rate": 0.25,
    },
    # Switzerland requires a canton/municipality-specific effective tax model.
    "CH": {
        "bond_yield": Decimal("0.008"),
        "gdp_growth": Decimal("0.014"),
        "inflation": Decimal("0.011"),
        "tax_rate": None,
    },
    "DE": {
        "bond_yield": Decimal("0.023"),
        "gdp_growth": Decimal("0.013"),
        "inflation": Decimal("0.02"),
        "tax_rate": None,
    },
    # Denmark - flat CIT 22%, DKK pegged to EUR.
    "DK": {
        "bond_yield": Decimal("0.024"),
        "gdp_growth": Decimal("0.018"),
        "inflation": Decimal("0.02"),
        "tax_rate": 0.22,
    },
    # Distribution tax requires an explicit timing/cash-tax model. It is not
    # a default 22% annual EBIT charge.
    "EE": {
        "bond_yield": Decimal("0.034"),
        "gdp_growth": Decimal("0.020"),
        "inflation": Decimal("0.02"),
        "tax_rate": None,
    },
    "ES": {
        "bond_yield": Decimal("0.032"),
        "gdp_growth": Decimal("0.012"),
        "inflation": Decimal("0.02"),
        "tax_rate": 0.25,
    },
    # Finland - flat CIT 20%.
    "FI": {
        "bond_yield": Decimal("0.027"),
        "gdp_growth": Decimal("0.014"),
        "inflation": Decimal("0.02"),
        "tax_rate": 0.20,
    },
    "FR": {
        "bond_yield": Decimal("0.028"),
        "gdp_growth": Decimal("0.014"),
        "inflation": Decimal("0.02"),
        "tax_rate": 0.25,
    },
    # United Kingdom - main CIT 25% post-2023 hike.
    "GB": {
        "bond_yield": Decimal("0.038"),
        "gdp_growth": Decimal("0.018"),
        "inflation": Decimal("0.02"),
        "tax_rate": 0.25,
    },
    # Ireland's rate is conditional: 12.5% trading, 25% non-trading and a
    # 15% Pillar Two floor for in-scope groups. The DCF adapter resolves this
    # from CountryPack evidence and must never consume this null sentinel.
    "IE": {
        "bond_yield": Decimal("0.028"),
        "gdp_growth": Decimal("0.025"),
        "inflation": Decimal("0.02"),
        "tax_rate": None,
    },
    # Italy requires separate IRES/IRAP bases; no universal combined rate.
    "IT": {
        "bond_yield": Decimal("0.035"),
        "gdp_growth": Decimal("0.010"),
        "inflation": Decimal("0.02"),
        "tax_rate": None,
    },
    # Lithuania — ECB May 2026 convergence-purpose 10Y EUR series; Bank of
    # Lithuania June 2026 baseline real-GDP projection; standard CIT is 17%
    # for tax periods beginning on or after 1 January 2026. Conditional 7%
    # and 0% regimes require evidence and are not bootstrap defaults.
    "LT": {
        "bond_yield": Decimal("0.0288"),
        "gdp_growth": Decimal("0.027"),
        "inflation": Decimal("0.02"),
        "tax_rate": 0.17,
    },
    # Luxembourg requires a location-specific combined tax model.
    "LU": {
        "bond_yield": Decimal("0.026"),
        "gdp_growth": Decimal("0.022"),
        "inflation": Decimal("0.02"),
        "tax_rate": None,
    },
    "NL": {
        "bond_yield": Decimal("0.024"),
        "gdp_growth": Decimal("0.016"),
        "inflation": Decimal("0.02"),
        # VPB (Vennootschapsbelasting) top bracket: 25.8% on profit > EUR 200k.
        # Low bracket (19% on first EUR 200k) is ignored here consistent with
        # how BE uses the 25% standard rate rather than the 20% SME rate.
        "tax_rate": 0.258,
    },
    # Norway - flat CIT 22%, NOK.
    "NO": {
        "bond_yield": Decimal("0.034"),
        "gdp_growth": Decimal("0.018"),
        "inflation": Decimal("0.025"),
        "tax_rate": 0.22,
    },
    # Poland - standard CIT 19%, PLN.
    "PL": {
        "bond_yield": Decimal("0.052"),
        "gdp_growth": Decimal("0.030"),
        "inflation": Decimal("0.025"),
        "tax_rate": 0.19,
    },
    # Portugal requires dated national, municipal and state tax treatment.
    "PT": {
        "bond_yield": Decimal("0.030"),
        "gdp_growth": Decimal("0.015"),
        "inflation": Decimal("0.02"),
        "tax_rate": None,
    },
    # Sweden - flat CIT 20.6%, SEK.
    "SE": {
        "bond_yield": Decimal("0.024"),
        "gdp_growth": Decimal("0.020"),
        "inflation": Decimal("0.02"),
        "tax_rate": 0.206,
    },
    # Slovakia - NBS 2026 10Y sovereign series / medium-term forecast. The
    # middle 21% corporate-tax band is the neutral bootstrap; the CountryPack
    # records the evidence requirements for the conditional 10% and 24% bands.
    "SK": {
        "bond_yield": Decimal("0.035"),
        "gdp_growth": Decimal("0.020"),
        "inflation": Decimal("0.02"),
        "tax_rate": 0.21,
    },
    # Legacy UK alias retained for old callers. US is a canonical ISO-2 public
    # Adaptive jurisdiction even though it is not yet product-exposed in Venus.
    "UK": {
        "bond_yield": Decimal("0.038"),
        "gdp_growth": Decimal("0.018"),
        "inflation": Decimal("0.02"),
        "tax_rate": 0.25,
    },
    "US": {
        "bond_yield": Decimal("0.042"),
        "gdp_growth": Decimal("0.025"),
        "inflation": Decimal("0.02"),
        "tax_rate": 0.21,
    },
    "DEFAULT": {
        "bond_yield": Decimal("0.03"),
        "gdp_growth": Decimal("0.02"),
        "inflation": Decimal("0.02"),
        "tax_rate": 0.25,
    },
}


def resolve_country_defaults(
    country_code: Optional[str],
    *,
    country_defaults: Optional[dict] = None,
) -> dict:
    """Return effective country defaults: Delphi overlay over the static map."""
    merged = _bootstrap_country_defaults(country_code, country_defaults or COUNTRY_DEFAULTS)
    snap = _country_context_snapshot(country_code)
    if snap is None:
        return merged

    _apply_country_context_overlay(merged, snap)
    return merged


def _bootstrap_country_defaults(country_code: Optional[str], defaults: dict) -> dict:
    code = str(country_code or "").strip().upper()
    if code == "UK":
        code = "GB"
    if not code or code not in defaults or code in {"DEFAULT", "UK"}:
        raise ValueError(f"unsupported or unconfigured DCF country_code: {country_code!r}")
    bootstrap = defaults[code]
    # Copy so callers can't mutate module-level bootstrap values via the returned dict.
    return dict(bootstrap)


def _country_context_snapshot(country_code: Optional[str]) -> object | None:
    if not country_code:
        return None
    try:
        service = get_country_data_service()
    except Exception:  # pragma: no cover - defensive
        return None
    return service.get(country_code)


def _apply_country_context_overlay(merged: dict, snap: object) -> None:
    # Delphi stores percents as DECIMAL(5,2). The engine wants decimals
    # (0.025 for 2.5%). Doing the divide in `Decimal` avoids floating-point
    # artefacts that would otherwise show up downstream in DCF assertions.
    if snap.risk_free_rate_10y is not None:
        merged["bond_yield"] = percentage_points_to_decimal_decimal(snap.risk_free_rate_10y)

    # DCF terminal growth is a forward-looking assumption.  A missing forward
    # observation must therefore fall back to the governed long-term bootstrap,
    # never to the latest backward-looking print.  The latter can legitimately
    # be zero during a stagnant period and was previously overriding Belgium's
    # 1.5% long-term default in public Adaptive runs.
    chosen_gdp = snap.gdp_growth_forecast_2y
    if chosen_gdp is not None:
        gdp_decimal = percentage_points_to_decimal_decimal(chosen_gdp)
        if gdp_decimal is not None:
            merged["gdp_growth"] = gdp_decimal

    if snap.inflation_hicp is not None:
        inflation_decimal = percentage_points_to_decimal_decimal(snap.inflation_hicp)
        if inflation_decimal is not None:
            merged["inflation"] = inflation_decimal

    # A national statutory observation is not an entity cash-tax model. Keep
    # it in the source snapshot; only the versioned DCF tax policy may resolve
    # the calculation rate. In particular, never overwrite a null sentinel.


INDUSTRY_DEFAULTS = {
    "technology": {
        "beta": Decimal("1.2"),
        "growth": Decimal("0.15"),
        "ebitda_margin": Decimal("0.25"),
        "capex_to_revenue": Decimal("0.05"),
        "ev_ebitda": Decimal("12.0"),
        "ev_revenue": Decimal("3.0"),
    },
    "manufacturing": {
        "beta": Decimal("1.0"),
        "growth": Decimal("0.05"),
        "ebitda_margin": Decimal("0.15"),
        "capex_to_revenue": Decimal("0.08"),
        "ev_ebitda": Decimal("8.0"),
        "ev_revenue": Decimal("1.2"),
    },
    "retail": {
        "beta": Decimal("0.9"),
        "growth": Decimal("0.03"),
        "ebitda_margin": Decimal("0.08"),
        "capex_to_revenue": Decimal("0.04"),
        "ev_ebitda": Decimal("6.0"),
        "ev_revenue": Decimal("0.5"),
    },
    "services": {
        "beta": Decimal("0.9"),
        "growth": Decimal("0.06"),
        "ebitda_margin": Decimal("0.20"),
        "capex_to_revenue": Decimal("0.03"),
        "ev_ebitda": Decimal("9.0"),
        "ev_revenue": Decimal("1.8"),
    },
    "healthcare": {
        "beta": Decimal("0.8"),
        "growth": Decimal("0.08"),
        "ebitda_margin": Decimal("0.18"),
        "capex_to_revenue": Decimal("0.06"),
        "ev_ebitda": Decimal("10.0"),
        "ev_revenue": Decimal("2.0"),
    },
    "finance": {
        "beta": Decimal("1.1"),
        "growth": Decimal("0.04"),
        "ebitda_margin": Decimal("0.35"),
        "capex_to_revenue": Decimal("0.02"),
        "ev_ebitda": Decimal("11.0"),
        "ev_revenue": Decimal("3.5"),
    },
    "real_estate": {
        "beta": Decimal("0.7"),
        "growth": Decimal("0.04"),
        "ebitda_margin": Decimal("0.40"),
        "capex_to_revenue": Decimal("0.10"),
        "ev_ebitda": Decimal("13.0"),
        "ev_revenue": Decimal("5.0"),
    },
    "hospitality": {
        "beta": Decimal("1.3"),
        "growth": Decimal("0.06"),
        "ebitda_margin": Decimal("0.12"),
        "capex_to_revenue": Decimal("0.07"),
        "ev_ebitda": Decimal("7.0"),
        "ev_revenue": Decimal("0.8"),
    },
    "construction": {
        "beta": Decimal("1.2"),
        "growth": Decimal("0.05"),
        "ebitda_margin": Decimal("0.10"),
        "capex_to_revenue": Decimal("0.06"),
        "ev_ebitda": Decimal("6.5"),
        "ev_revenue": Decimal("0.6"),
    },
    "other": {
        "beta": Decimal("1.0"),
        "growth": Decimal("0.05"),
        "ebitda_margin": Decimal("0.15"),
        "capex_to_revenue": Decimal("0.05"),
        "ev_ebitda": Decimal("8.0"),
        "ev_revenue": Decimal("1.5"),
    },
}


EU_COUNTRIES = {
    "BE",
    "DE",
    "FR",
    "NL",
    "IT",
    "ES",
    "AT",
    "PT",
    "IE",
    "FI",
    "GR",
    "LU",
    "CY",
    "MT",
    "SK",
    "SI",
    "EE",
    "LV",
    "LT",
}
