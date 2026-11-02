"""
Belgian Owner Compensation & Salary Benchmarks

Single source of truth for all Belgian salary/compensation data used in:
- SDE calculation (Step 2.7)
- Owner compensation normalization (Step 2.5)
- SDE domain engine

All values are indexed to 2026 using Belgian automatic indexation (+4.5% from 2024 base).

Sources:
- VFB Belgium (2024): "Vlaamse Federatie van Beleggingsclubs en Beleggers" survey data
- SD Worx Salary Survey (2024): Belgian salary benchmarks by sector
- Trugman, G.R. (2017): "Understanding Business Valuation" (AICPA), p. 287
- Pratt, S.P. & Niculita, A.V. (2008): "Valuing a Business", 5th ed.
- Brussels Times (2025): Belgian automatic indexation forecast (~2.21%/yr)
"""

from decimal import Decimal


# ============================================================================
# OWNER COMPENSATION BY BUSINESS SIZE
# Used by: SDE Engine, Step 2.7 SDE Calculator
# Basis: VFB Belgium 2024, indexed to 2026 (+4.5%)
# ============================================================================

OWNER_COMPENSATION_BY_SIZE = {
    "micro": {
        "salary": Decimal("47000"),
        "benefits": Decimal("8400"),
        "perks": Decimal("5200"),
    },
    "small": {
        "salary": Decimal("68000"),
        "benefits": Decimal("12500"),
        "perks": Decimal("8400"),
    },
    "lower_middle": {
        "salary": Decimal("89000"),
        "benefits": Decimal("15700"),
        "perks": Decimal("12500"),
    },
}


# ============================================================================
# MARKET RATES BY REVENUE TIER
# Used by: Owner Compensation Adjuster (Step 2.5)
# Basis: VFB Belgium 2024, indexed to 2026 (+4.5%), Trugman (2017)
# ============================================================================

MARKET_RATES_BY_REVENUE = {
    "under_500k": Decimal("52000"),
    "500k_to_1m": Decimal("73000"),
    "1m_to_2m": Decimal("94000"),
    "2m_to_5m": Decimal("125000"),
    "over_5m": Decimal("157000"),
}


# ============================================================================
# INDUSTRY MULTIPLIERS
# Applied to base market rate to reflect sector-specific compensation
# Used by: Owner Compensation Adjuster (Step 2.5)
# Source: SD Worx 2024 Belgian sector data, VFB Belgium 2024
# ============================================================================

INDUSTRY_MULTIPLIERS = {
    "professional_services": Decimal("1.15"),
    "construction": Decimal("1.0"),
    "retail": Decimal("0.90"),
    "manufacturing": Decimal("1.05"),
    "technology": Decimal("1.30"),
}


# ============================================================================
# BELGIAN LOCATION MULTIPLIERS
# Regional cost-of-living adjustments for Belgium
# Used by: Owner Compensation Adjuster (Step 2.5)
# Source: Statbel regional wage statistics 2024
# ============================================================================

LOCATION_MULTIPLIERS = {
    "Brussels": Decimal("1.15"),
    "Flanders": Decimal("1.0"),
    "Wallonia": Decimal("0.95"),
    "Belgium": Decimal("1.0"),
}
