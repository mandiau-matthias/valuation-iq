"""
Shared market defaults and ERP resolution helpers.

These helpers keep country-level market assumptions consistent across the DCF
runtime, report helpers, and any fallback discount-rate logic.

Includes:
- Equity Risk Premium (ERP) per country (Damodaran 2025)
- Risk-free rate per country (10Y government bond yields, updated monthly)
- Size premium interpolation (Duff & Phelps 2024, 7 revenue tiers)
- NACE-based industry cyclicality risk profiles
- Company-specific risk buildup helpers
"""

import logging
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.utils.decimal_helpers import to_decimal

logger = logging.getLogger(__name__)


DEFAULT_EQUITY_RISK_PREMIUM = Decimal("0.06")

# Seed mature-market defaults first; countries not listed fall back to 6.0%.
# Values sit on the file's own vintage (US 5.0% mature anchor, AAA eurozone core
# DE/NL at 5.2%), with each country's level set by its Damodaran rating tier, not
# by mixing in a different year's mature-premium number.
COUNTRY_EQUITY_RISK_PREMIUMS: Dict[str, Decimal] = {
    "BE": Decimal("0.053"),
    "DE": Decimal("0.052"),
    "FR": Decimal("0.054"),
    "US": Decimal("0.050"),
    "UK": Decimal("0.053"),
    "NL": Decimal("0.052"),
    "IT": Decimal("0.060"),
    "ES": Decimal("0.058"),
    # Nordics (BET-420). DK/SE/NO are Aaa-rated with a 0.00% Damodaran country-risk
    # premium → same as the AAA eurozone core (DE/NL). FI is Aa1 (+0.40% CRP per
    # Damodaran 2025) → one notch above the core. Source: Damodaran "Country Risk
    # 2025" (mature-market premium 4.21%, scaled to this file's vintage).
    "DK": Decimal("0.052"),
    "SE": Decimal("0.052"),
    "NO": Decimal("0.052"),
    "FI": Decimal("0.053"),
    # Slovakia uses the governed EU market-risk snapshot plus its country-risk
    # tier. This is explicit so public Adaptive never consumes the 6% unknown-
    # jurisdiction fallback.
    "SK": Decimal("0.058"),
    # Estonia is A1/AA- — one notch above Slovakia (A2/A+) and one below Finland
    # (Aa1), so it sits between them on the same Damodaran country-risk tiering
    # this map already uses. Explicit for the same reason as SK: never inherit
    # the 6% unknown-jurisdiction fallback.
    "EE": Decimal("0.056"),
    # Lithuania uses the same governed CEE country-risk tier as Slovakia.
    # Keep explicit so it never consumes the 6% unknown-country fallback.
    "LT": Decimal("0.058"),
}

# 10-year government bond yields per country (risk-free rate).
# Source: ECB Statistical Data Warehouse / national treasuries.
# Updated: March 2026.  Refreshed monthly; stale after 60 days.
_RISK_FREE_RATE_LAST_UPDATED = "2026-03-01"

COUNTRY_RISK_FREE_RATES: Dict[str, Decimal] = {
    "BE": Decimal("0.031"),   # 3.1% Belgian OLO 10Y
    "DE": Decimal("0.027"),   # 2.7% German Bund 10Y
    "FR": Decimal("0.032"),   # 3.2% French OAT 10Y
    "NL": Decimal("0.029"),   # 2.9% Netherlands 10Y
    "IT": Decimal("0.038"),   # 3.8% Italian BTP 10Y
    "ES": Decimal("0.034"),   # 3.4% Spanish Bono 10Y
    "UK": Decimal("0.042"),   # 4.2% UK Gilt 10Y
    "US": Decimal("0.043"),   # 4.3% US Treasury 10Y
    # Nordics (BET-420) — Q1 2026 10Y sovereign yields. SE/DK sit by the DE/NL
    # core, FI like ES, NO well above (a 17-year high). Non-EUR (SEK/NOK/DKK) but
    # the engine discounts in EUR; the report layer carries the currency note.
    "SE": Decimal("0.028"),   # 2.8% Sweden 10Y (SEK)
    "DK": Decimal("0.029"),   # 2.9% Denmark 10Y (DKK, EUR-pegged)
    "FI": Decimal("0.034"),   # 3.4% Finland 10Y (EUR)
    "NO": Decimal("0.043"),   # 4.3% Norway 10Y (NOK)
    "SK": Decimal("0.035"),  # 3.5% Slovakia 10Y (EUR), NBS 2026 forecast
    "EE": Decimal("0.036"),  # 3.6% Estonia 10Y (EUR); thinner issuance than FI/SK
    "LT": Decimal("0.0288"),  # 2.88% ECB LT convergence-purpose 10Y, May 2026
}

DEFAULT_RISK_FREE_RATE = Decimal("0.030")
RISK_FREE_RATE_CACHE_TTL = timedelta(hours=24)
_RISK_FREE_RATE_SNAPSHOTS: Dict[str, Dict[str, Any]] = {}
# Process-wide cache may be read/written from concurrent valuation requests (multi-worker
# or overlapping async work). Serialize snapshot access (cheap: uncontended hot path).
_RISK_FREE_SNAPSHOT_LOCK = threading.Lock()

# Size premium tiers (Duff & Phelps / Ibbotson 2024, 7 revenue tiers).
# Higher revenue = lower size premium (less risk).
# Interpolated linearly between breakpoints for smooth transitions.
SIZE_PREMIUM_TIERS: List[Tuple[Decimal, Decimal]] = [
    (Decimal("500000"),    Decimal("0.080")),   # < €500K:  8.0%
    (Decimal("2000000"),   Decimal("0.070")),   # < €2M:    7.0%
    (Decimal("5000000"),   Decimal("0.060")),   # < €5M:    6.0%
    (Decimal("10000000"),  Decimal("0.050")),   # < €10M:   5.0%
    (Decimal("25000000"),  Decimal("0.040")),   # < €25M:   4.0%
    (Decimal("50000000"),  Decimal("0.030")),   # < €50M:   3.0%
]
SIZE_PREMIUM_FLOOR = Decimal("0.020")  # ≥ €50M: 2.0%

# NACE-based industry cyclicality risk premium.
# Cyclical industries carry higher company-specific risk in the WACC buildup.
# Sources: Damodaran (2024) sector betas, Vlerick M&A Monitor sector analysis.
# Values represent the *additional* company-specific risk attributable to
# industry cyclicality (on top of base company-specific risk).
NACE_CYCLICALITY_RISK: Dict[str, Decimal] = {
    # High cyclicality (+2-3% risk)
    "construction":             Decimal("0.025"),
    "home-property":            Decimal("0.025"),
    "hospitality-tourism":      Decimal("0.030"),
    "events-entertainment":     Decimal("0.025"),
    "automotive":               Decimal("0.020"),
    "agriculture":              Decimal("0.020"),
    "arts-crafts":              Decimal("0.020"),
    # Moderate cyclicality (+1-1.5% risk)
    "manufacturing":            Decimal("0.015"),
    "transportation-logistics": Decimal("0.015"),
    "retail":                   Decimal("0.015"),
    "ecommerce-retail":         Decimal("0.015"),
    "creative-media":           Decimal("0.010"),
    "food-beverage":            Decimal("0.010"),
    "beauty-wellness":          Decimal("0.010"),
    "fitness-health":           Decimal("0.010"),
    # Low cyclicality (0-0.5% risk)
    "technology":               Decimal("0.005"),
    "tech-digital":             Decimal("0.005"),
    "services":                 Decimal("0.005"),
    "professional-services":    Decimal("0.000"),
    "consulting":               Decimal("0.000"),
    "healthcare":               Decimal("0.000"),
    "financial-services":       Decimal("0.005"),
    "education-training":       Decimal("0.000"),
    "environmental":            Decimal("0.005"),
    "security-safety":          Decimal("0.005"),
    "pet-services":             Decimal("0.005"),
    "repair-maintenance":       Decimal("0.010"),
}


def get_default_equity_risk_premium(country_code: Optional[str]) -> Decimal:
    """Return the configured ERP default for a country, or the global fallback."""
    normalized = (country_code or "").upper()
    return COUNTRY_EQUITY_RISK_PREMIUMS.get(normalized, DEFAULT_EQUITY_RISK_PREMIUM)


def resolve_equity_risk_premium(
    country_code: Optional[str],
    explicit_override: Any = None,
    economic_context: Optional[Dict[str, Any]] = None,
) -> Tuple[Decimal, str]:
    """
    Resolve ERP with explicit overrides first, then Titan economic context,
    then country defaults, then the global fallback.
    """
    if explicit_override is not None:
        return to_decimal(explicit_override), "request_override"

    if isinstance(economic_context, dict):
        for key in ("equity_risk_premium", "market_risk_premium", "erp"):
            value = economic_context.get(key)
            if value is not None:
                return to_decimal(value), f"economic_context.{key}"

    normalized = (country_code or "").upper()
    if normalized in COUNTRY_EQUITY_RISK_PREMIUMS:
        return COUNTRY_EQUITY_RISK_PREMIUMS[normalized], f"country_default:{normalized}"

    return DEFAULT_EQUITY_RISK_PREMIUM, "global_default"


def get_risk_free_rate(country_code: Optional[str]) -> Tuple[Decimal, str]:
    """
    Return the 10Y government bond yield for a country.

    Returns:
        Tuple of (rate, source_label)
    """
    normalized = (country_code or "").upper()
    with _RISK_FREE_SNAPSHOT_LOCK:
        snapshot = _RISK_FREE_RATE_SNAPSHOTS.get(normalized)
        if snapshot:
            fetched_at = snapshot.get("fetched_at")
            if isinstance(fetched_at, datetime) and datetime.now(timezone.utc) - fetched_at <= RISK_FREE_RATE_CACHE_TTL:
                return snapshot["rate"], snapshot["source"]
    if normalized in COUNTRY_RISK_FREE_RATES:
        return (
            COUNTRY_RISK_FREE_RATES[normalized],
            f"10Y govt bond ({normalized}, {_RISK_FREE_RATE_LAST_UPDATED})",
        )
    return DEFAULT_RISK_FREE_RATE, f"10Y govt bond (global default, {_RISK_FREE_RATE_LAST_UPDATED})"


def cache_risk_free_rate_snapshot(
    country_code: Optional[str],
    rate: Any,
    *,
    source: str,
    fetched_at: Optional[datetime] = None,
) -> None:
    """Store an ECB-backed risk-free-rate snapshot for synchronous valuation reads."""
    normalized = (country_code or "").upper()
    if not normalized:
        return
    with _RISK_FREE_SNAPSHOT_LOCK:
        _RISK_FREE_RATE_SNAPSHOTS[normalized] = {
            "rate": to_decimal(rate),
            "source": source,
            "fetched_at": fetched_at or datetime.now(timezone.utc),
        }


async def refresh_risk_free_rate_snapshot(
    country_code: Optional[str],
    maturity_years: int = 10,
) -> Tuple[Decimal, str]:
    """
    Refresh the in-memory risk-free-rate snapshot from the ECB adapter.

    This is intentionally async and separate from the calculation path so
    synchronous valuation code can read a cached snapshot without awaiting I/O.
    """
    normalized = (country_code or "").upper()
    if not normalized:
        return get_risk_free_rate(country_code)

    try:
        from src.adapters.ecb_adapter import ECBAdapter

        adapter = ECBAdapter()
        try:
            risk_free_data = await adapter.get_risk_free_rate(normalized, maturity_years=maturity_years)
        finally:
            await adapter.close_session()

        rate = to_decimal(risk_free_data.get("yield"))
        source = f"cached ECB snapshot ({risk_free_data.get('source', 'ECB')})"
        fetched_at_raw = risk_free_data.get("retrieved_at")
        fetched_at = None
        if isinstance(fetched_at_raw, str):
            try:
                fetched_at = datetime.fromisoformat(fetched_at_raw.replace("Z", "+00:00"))
            except ValueError:
                fetched_at = None
        cache_risk_free_rate_snapshot(normalized, rate, source=source, fetched_at=fetched_at)
        return get_risk_free_rate(normalized)
    except Exception as exc:
        logger.warning(
            "ECB risk-free rate refresh failed for %s, falling back to cached snapshot",
            normalized,
            exc_info=True,
        )
        return get_risk_free_rate(normalized)


def get_size_premium(revenue: Decimal) -> Tuple[Decimal, str]:
    """
    Interpolate size premium from Duff & Phelps / Ibbotson revenue tiers.

    Uses linear interpolation between breakpoints for smooth transitions
    (no cliff effects at tier boundaries).

    Returns:
        Tuple of (premium_decimal, tier_label)
    """
    revenue = to_decimal(revenue)
    if revenue <= Decimal("0"):
        return SIZE_PREMIUM_TIERS[0][1], "micro (<€500K)"

    prev_rev, prev_prem = Decimal("0"), SIZE_PREMIUM_TIERS[0][1]
    for tier_rev, tier_prem in SIZE_PREMIUM_TIERS:
        if revenue < tier_rev:
            # Linear interpolation within this tier
            span = tier_rev - prev_rev
            progress = (revenue - prev_rev) / span if span > 0 else Decimal("0")
            interpolated = prev_prem - progress * (prev_prem - tier_prem)
            label = f"€{int(prev_rev):,}-€{int(tier_rev):,}"
            return interpolated, label
        prev_rev, prev_prem = tier_rev, tier_prem

    return SIZE_PREMIUM_FLOOR, "large (≥€50M)"


def get_nace_cyclicality_risk(industry: Optional[str]) -> Tuple[Decimal, str]:
    """
    Return the cyclicality risk premium for an industry (NACE category).

    Returns:
        Tuple of (risk_premium, explanation)
    """
    if not industry:
        return Decimal("0.010"), "unknown industry (default moderate risk)"

    key = industry.lower().strip()
    risk = NACE_CYCLICALITY_RISK.get(key)
    if risk is not None:
        if risk >= Decimal("0.020"):
            level = "high cyclicality"
        elif risk >= Decimal("0.010"):
            level = "moderate cyclicality"
        else:
            level = "low cyclicality"
        return risk, f"{key} ({level})"

    return Decimal("0.010"), f"{key} (default moderate risk)"


def calculate_company_specific_risk(
    *,
    is_profitable: bool = True,
    has_audit: Optional[bool] = None,
    customer_concentration_pct: Optional[Decimal] = None,
    industry: Optional[str] = None,
    owner_dependency_score: Optional[Decimal] = None,
) -> Tuple[Decimal, List[Dict[str, Any]]]:
    """
    Build up the company-specific risk component for the WACC discount rate.

    Returns:
        Tuple of (total_company_risk, breakdown_list)
        where breakdown_list contains dicts with 'factor', 'premium', 'explanation'.
    """
    breakdown: List[Dict[str, Any]] = []
    total = Decimal("0")

    # 1. Profitability
    if not is_profitable:
        premium = Decimal("0.020")
        total += premium
        breakdown.append({
            "factor": "Unprofitable company",
            "premium": premium,
            "explanation": "Negative EBITDA adds +2.0% risk (Trugman 2017)",
        })

    # 2. Audit status
    if has_audit is False:
        premium = Decimal("0.015")
        total += premium
        breakdown.append({
            "factor": "No audited financials",
            "premium": premium,
            "explanation": "Unaudited financials add +1.5% risk (Duff & Phelps 2024)",
        })

    # 3. Customer concentration
    if customer_concentration_pct is not None:
        conc = to_decimal(customer_concentration_pct)
        if conc > Decimal("0.50"):
            premium = Decimal("0.040")
            total += premium
            breakdown.append({
                "factor": "High customer concentration",
                "premium": premium,
                "explanation": f"Top customer >{conc * 100:.0f}% of revenue adds +4.0% risk",
            })
        elif conc > Decimal("0.30"):
            premium = Decimal("0.020")
            total += premium
            breakdown.append({
                "factor": "Moderate customer concentration",
                "premium": premium,
                "explanation": f"Top customer >{conc * 100:.0f}% of revenue adds +2.0% risk",
            })

    # 4. Industry cyclicality (NACE)
    nace_risk, nace_label = get_nace_cyclicality_risk(industry)
    if nace_risk > Decimal("0"):
        total += nace_risk
        breakdown.append({
            "factor": "Industry cyclicality",
            "premium": nace_risk,
            "explanation": f"{nace_label}: +{nace_risk * 100:.1f}% risk",
        })

    # 5. Owner dependency
    if owner_dependency_score is not None:
        dep = to_decimal(owner_dependency_score)
        if dep >= Decimal("0.70"):
            premium = Decimal("0.020")
            total += premium
            breakdown.append({
                "factor": "High owner dependency",
                "premium": premium,
                "explanation": f"Owner dependency {dep * 100:.0f}% adds +2.0% key-person risk",
            })
        elif dep >= Decimal("0.40"):
            premium = Decimal("0.010")
            total += premium
            breakdown.append({
                "factor": "Moderate owner dependency",
                "premium": premium,
                "explanation": f"Owner dependency {dep * 100:.0f}% adds +1.0% key-person risk",
            })

    if not breakdown:
        breakdown.append({
            "factor": "Base company risk",
            "premium": Decimal("0"),
            "explanation": "No additional company-specific risk factors identified",
        })

    return total, breakdown
