"""Single source of truth for the 20 valuation-enabled countries.

Mirrors:
  - `apps/mercury/shared/lib/countries.ts`
  - `apps/titan-api/src/common/constants/countries.ts`
  - `apps/hermes/src/core/countries.py`

Delphi benchmark publication coverage is a separate, narrower contract.
Configured CountryPacks do not imply certified benchmark evidence.

Drift between mirrors triggers contract test failures. If the runtime country contract
ever changes, update all four files in lockstep.
"""

from __future__ import annotations

from typing import Final, FrozenSet, Tuple

# 20 valuation-enabled countries, alphabetical to match the TS/Python mirrors.
SUPPORTED_COUNTRY_CODES: Final[Tuple[str, ...]] = (
    "AT",
    "BE",
    "CH",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GB",
    "IE",
    "IT",
    "LT",
    "LU",
    "NL",
    "NO",
    "PL",
    "PT",
    "SE",
    "SK",
)

SUPPORTED_COUNTRIES: Final[FrozenSet[str]] = frozenset(SUPPORTED_COUNTRY_CODES)

# Subset with wired registry search support in the product surface:
# KBO (BE), Companies House (GB), and KVK (NL). Runtime registry search is
# Titan-owned for stateless flows; keep this mirror aligned with Mercury/Titan.
REGISTRY_COUNTRY_CODES: Final[Tuple[str, ...]] = ("BE", "GB", "NL")
REGISTRY_COUNTRIES: Final[FrozenSet[str]] = frozenset(REGISTRY_COUNTRY_CODES)

# Statutory currency != EUR. Used by the report disclosure layer to inform
# the reader that valuation math runs in EUR even though their statutory
# accounts are in another currency.
NON_EUR_COUNTRY_CODES: Final[Tuple[str, ...]] = (
    "CH",
    "DK",
    "GB",
    "NO",
    "PL",
    "SE",
)
NON_EUR_COUNTRIES: Final[FrozenSet[str]] = frozenset(NON_EUR_COUNTRY_CODES)


def is_supported_country(value: object) -> bool:
    """True when `value` is a string ISO-2 code in the supported set."""
    return isinstance(value, str) and value.upper() in SUPPORTED_COUNTRIES


def is_registry_country(value: object) -> bool:
    """True when `value` has wired registry search support."""
    return isinstance(value, str) and value.upper() in REGISTRY_COUNTRIES


def is_non_eur_country(value: object) -> bool:
    """True when `value` is one of the 6 supported countries that don't use EUR."""
    return isinstance(value, str) and value.upper() in NON_EUR_COUNTRIES


def normalize_country_code(raw: object, fallback: str | None = None) -> str:
    """Normalize an arbitrary input to a supported ISO-2 country code.

    Accepts ``UK`` as an alias for ``GB``. Unsupported or missing countries
    fail closed unless a caller explicitly supplies a non-pricing fallback
    such as ``DEFAULT`` for a confidence label.
    """
    if not isinstance(raw, str):
        if fallback is not None:
            return fallback
        raise ValueError("country_code is required and must be explicitly supported")
    code = raw.strip().upper()
    if len(code) < 2:
        if fallback is not None:
            return fallback
        raise ValueError(f"unsupported country_code: {raw!r}")
    code = code[:2]
    if code == "UK":
        code = "GB"
    if code in SUPPORTED_COUNTRIES:
        return code
    if fallback is not None:
        return fallback
    raise ValueError(f"unsupported country_code: {raw!r}")


# ---------------------------------------------------------------------------
# Currency + confidence tier
# ---------------------------------------------------------------------------

# Statutory reporting currency for each valuation-enabled country.
# in EUR throughout — this mapping is for the report disclosure layer.
COUNTRY_CURRENCY: Final[dict[str, str]] = {
    "AT": "EUR",
    "BE": "EUR",
    "CH": "CHF",
    "DE": "EUR",
    "DK": "DKK",
    "EE": "EUR",
    "ES": "EUR",
    "FI": "EUR",
    "FR": "EUR",
    "GB": "GBP",
    "IE": "EUR",
    "IT": "EUR",
    "LT": "EUR",
    "LU": "EUR",
    "NL": "EUR",
    "NO": "NOK",
    "PL": "PLN",
    "PT": "EUR",
    "SE": "SEK",
    "SK": "EUR",
}


def currency_for_country(code: str) -> str:
    """Return statutory currency; unsupported countries never inherit EUR."""
    return COUNTRY_CURRENCY[normalize_country_code(code)]


# 3-tier confidence classification.
#   high   : BE / NL — registry + SME-rate Belgian tax module + EUR
#   medium : DE / FR / GB / IT / ES / LU — explicit per-country defaults
#   default: AT / CH / DK / EE / FI / LT / NO / PL / PT / SE / SK — statutory rate fallback,
#            non-EUR for some, BENELUX-shaped peer benchmarks today
HIGH_CONFIDENCE_COUNTRIES: Final[FrozenSet[str]] = frozenset({"BE", "NL"})
MEDIUM_CONFIDENCE_COUNTRIES: Final[FrozenSet[str]] = frozenset(
    {"DE", "FR", "GB", "IE", "IT", "ES", "LU"}
)


def country_confidence_tier(code: str) -> str:
    """Return ``"high"`` / ``"medium"`` / ``"default"`` for a country code.

    Surfaced on the report cover so readers know how much engine fidelity
    the country received. ``"default"`` reports should be reviewed by an
    accountant before stakeholder distribution.
    """
    normalized = normalize_country_code(code, fallback="DEFAULT")
    if normalized in HIGH_CONFIDENCE_COUNTRIES:
        return "high"
    if normalized in MEDIUM_CONFIDENCE_COUNTRIES:
        return "medium"
    return "default"


# ---------------------------------------------------------------------------
# Peer-region classification (used by FMP / market-data collectors)
# ---------------------------------------------------------------------------


def peer_region_for_country(code: object) -> str:
    """Return the peer-comparison region for a country code.

    Used by ``step_2_benchmarking`` collectors when querying FMP for
    comparable companies. Before Phase 2 the rule was
    ``"EU" if country in ["BE","NL","DE","FR"] else "US"`` — which silently
    pulled US peers for ES / IT / PL / etc. and produced misleading
    benchmarks. This helper widens "EU" to the full valuation-enabled
    set (UK retained as part of the European peer pool even though it left
    the EU — its SME ecosystem still benchmarks against EU peers more
    naturally than the US).
    """
    if isinstance(code, str) and code.upper() in SUPPORTED_COUNTRIES:
        return "EU"
    return "US"
