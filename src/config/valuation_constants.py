"""
Valuation Constants and Configuration

This module contains all configurable constants used in valuation calculations.
All values are based on academic research, industry standards, and regulatory guidelines.

Author: Senior CTO
Version: 2.1.0
Last Updated: October 23, 2025
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ValuationConstants:
    """
    Centralized configuration for all valuation constants.

    All values are based on:
    - Academic research (Damodaran, McKinsey, Koller et al.)
    - Industry standards (Big 4 methodology)
    - Regulatory guidelines (IFRS 13, ASC 820)
    """

    # Range Calculation Constants
    CONFIDENCE_SPREADS = {
        "high": 0.12,    # ±12% for high confidence (>80%)
        "medium": 0.18,  # ±18% for medium confidence (60-80%)
        "low": 0.22      # ±22% for low confidence (<60%)
    }

    # Asymmetric Range Constants (SME Risk Modeling)
    ASYMMETRIC_RANGES = {
        "sme": {
            "downside_factor": 0.20,  # -20% downside risk
            "upside_factor": 0.15     # +15% upside potential
        },
        "large_company": {
            "downside_factor": 0.15,  # -15% downside risk
            "upside_factor": 0.15     # +15% upside potential
        }
    }

    # Recommended Asking Price Markup (applied to Enterprise Value)
    # Academic basis:
    #   - Pratt & Niculita (2008): seller negotiation premium 5–15% above fair value
    #   - IBBA Market Pulse (2024): median listing-to-close discount ~8–12%
    #   - Pepperdine PCM Report (2024): deal-close discount averages 7–10%
    # Higher-confidence valuations warrant a larger negotiation buffer because
    # the fair-value estimate is tighter, giving sellers more room to anchor high.
    ASKING_PRICE_MARKUP = {
        "high_confidence": 1.10,   # 10% — strong data, tight range
        "medium_confidence": 1.08, # 8%  — adequate data
        "low_confidence": 1.05     # 5%  — limited data, conservative buffer
    }

    # Net Income Estimation (when missing)
    NET_INCOME_ESTIMATION = {
        "default_ratio": 0.70,  # Net income = 70% of EBITDA (industry average)
        "saas_ratio": 0.60,     # SaaS companies typically have lower margins
        "manufacturing_ratio": 0.80  # Manufacturing has higher margins
    }

    # Discount Rate Components (Build-up Method)
    # NOTE: For live values use market_defaults.get_risk_free_rate() and
    #       market_defaults.get_size_premium(). These constants are kept as
    #       documentation of the methodology and ultimate fallbacks.
    DISCOUNT_RATE_COMPONENTS = {
        "risk_free_rate": 0.031,       # Belgium 10Y OLO (updated 2026-03)
        "equity_risk_premium": 0.053,  # Belgium ERP (Damodaran 2025)
        "size_premium_tiers": {
            "tier_1_under_500k":   0.080,   # 8.0%
            "tier_2_500k_2m":      0.070,   # 7.0%
            "tier_3_2m_5m":        0.060,   # 6.0%
            "tier_4_5m_10m":       0.050,   # 5.0%
            "tier_5_10m_25m":      0.040,   # 4.0%
            "tier_6_25m_50m":      0.030,   # 3.0%
            "tier_7_over_50m":     0.020,   # 2.0%
        },
        "company_specific_risk": {
            "base": 0.00,
            "unprofitable": 0.02,
            "no_audit": 0.015,
            "high_customer_concentration": 0.04,
            "moderate_customer_concentration": 0.02,
            "high_owner_dependency": 0.02,
            "moderate_owner_dependency": 0.01,
        }
    }

    # Growth Rate Assumptions
    GROWTH_RATE_ASSUMPTIONS = {
        "terminal_growth_rate": 0.025,  # 2.5% terminal growth (inflation + real growth)
        "high_growth_threshold": 0.15,  # 15% considered high growth
        "mature_growth_rate": 0.03,     # 3% for mature companies
        "startup_growth_rate": 0.20     # 20% for early-stage companies
    }

    # Industry-Specific Multiples (Revenue)
    INDUSTRY_REVENUE_MULTIPLES = {
        "technology": {
            "b2b_saas": 12.0,
            "b2c": 4.0,
            "marketplace": 6.0,
            "ecommerce": 3.0
        },
        "hospitality": {
            "services": 2.0,
            "manufacturing": 1.5
        },
        "manufacturing": {
            "manufacturing": 1.2,
            "services": 1.8
        },
        "retail": {
            "ecommerce": 2.5,
            "services": 1.5
        }
    }

    # Industry-Specific Multiples (EBITDA)
    INDUSTRY_EBITDA_MULTIPLES = {
        "technology": {
            "b2b_saas": 22.0,
            "b2c": 12.0,
            "marketplace": 16.0,
            "ecommerce": 8.0
        },
        "hospitality": {
            "services": 6.0,
            "manufacturing": 4.0
        },
        "manufacturing": {
            "manufacturing": 5.0,
            "services": 7.0
        },
        "retail": {
            "ecommerce": 10.0,
            "services": 6.0
        }
    }

    # Multi-Year EBITDA Weighting (McKinsey Valuation 2015, Ch. 7; Damodaran 2012, pp. 234-237)
    # Recent performance weighted heavier as a better predictor of future cash flows.
    # Ordered oldest-first: [Year1_oldest, Year2_middle, Year3_recent]
    EBITDA_WEIGHTS_3Y = (
        Decimal("1") / Decimal("6"),  # Oldest:      1/6 ≈ 16.67%
        Decimal("2") / Decimal("6"),  # Middle:       2/6 ≈ 33.33%
        Decimal("3") / Decimal("6"),  # Most recent:  3/6 = 50.00%
    )
    EBITDA_WEIGHTS_2Y = (
        Decimal("1") / Decimal("3"),  # Older:  1/3 ≈ 33.33%
        Decimal("2") / Decimal("3"),  # Recent: 2/3 ≈ 66.67%
    )
    EBITDA_WEIGHTS_1Y = (Decimal("1"),)

    # Same weights but descending (most-recent-first) for report display
    EBITDA_WEIGHTS_3Y_DESC = (
        Decimal("3") / Decimal("6"),  # Most recent:  3/6 = 50.00%
        Decimal("2") / Decimal("6"),  # Middle:       2/6 ≈ 33.33%
        Decimal("1") / Decimal("6"),  # Oldest:       1/6 ≈ 16.67%
    )
    EBITDA_WEIGHTS_2Y_DESC = (
        Decimal("2") / Decimal("3"),  # Recent: 2/3 ≈ 66.67%
        Decimal("1") / Decimal("3"),  # Older:  1/3 ≈ 33.33%
    )

    # Data Quality Thresholds
    DATA_QUALITY_THRESHOLDS = {
        "high_quality": 0.8,      # 80%+ completeness
        "medium_quality": 0.6,    # 60-80% completeness
        "low_quality": 0.4        # <60% completeness
    }

    # Confidence Score Thresholds
    CONFIDENCE_THRESHOLDS = {
        "high": 0.8,      # 80%+ confidence
        "medium": 0.6,    # 60-80% confidence
        "low": 0.4        # <60% confidence
    }

    # Monte Carlo Simulation Parameters
    MONTE_CARLO_PARAMETERS = {
        "n_simulations": 10000,           # Number of simulations
        "revenue_volatility": 0.15,       # 15% revenue volatility
        "multiple_volatility": 0.20,       # 20% multiple volatility
        "confidence_intervals": [0.10, 0.50, 0.90]  # P10, P50, P90
    }

    # Sensitivity Analysis Parameters
    SENSITIVITY_ANALYSIS = {
        "revenue_shock": 0.10,      # ±10% revenue change
        "multiple_shock": 0.20,     # ±20% multiple change
        "discount_rate_shock": 0.02, # ±2% discount rate change
        "growth_rate_shock": 0.01   # ±1% growth rate change
    }

    # Valuation Quality Metrics
    QUALITY_METRICS = {
        "minimum_historical_years": 2,    # Minimum years for trend analysis
        "maximum_projection_years": 10,   # Maximum DCF projection period
        "minimum_data_completeness": 0.3,  # Minimum 30% data completeness
        "maximum_valuation_range": 0.5    # Maximum 50% range spread
    }


# Global instance
VALUATION_CONSTANTS = ValuationConstants()


def get_confidence_spread(confidence_level: str) -> Decimal:
    """
    Get the spread factor for a given confidence level.

    Args:
        confidence_level: "high", "medium", or "low"

    Returns:
        Spread factor (e.g., 0.18 for medium confidence)

    Source: PwC Valuation Handbook 2024, Section 4.2
    """
    return VALUATION_CONSTANTS.CONFIDENCE_SPREADS.get(confidence_level, 0.18)


def get_asymmetric_factors(company_size: str) -> Dict[str, Decimal]:
    """
    Get asymmetric range factors for company size.

    Args:
        company_size: "sme" or "large_company"

    Returns:
        Dictionary with downside_factor and upside_factor

    Source: Damodaran (2018), The Dark Side of Valuation, p. 142
    """
    return VALUATION_CONSTANTS.ASYMMETRIC_RANGES.get(company_size, {
        "downside_factor": 0.15,
        "upside_factor": 0.15
    })


def get_asking_price_markup(
    confidence_level: str,
    advisor_override_pct: Optional[Any] = None,
) -> Decimal:
    """
    Get the asking-price markup factor.

    By default the markup is confidence-aware (5–10%). Advisors can override
    this per-firm via Mercury's branding settings; the override flows in as
    `advisor_override_pct` (a fraction in [0, 0.25] — e.g. 0.12 for 12%) and
    completely replaces the confidence-aware default when present.

    Args:
        confidence_level: "high", "medium", or "low"
        advisor_override_pct: Optional firm-level override as a fraction
            (0.10 → 10% markup). Clamped to [0, 0.25] for safety; values
            outside that band fall back to the confidence default.

    Returns:
        Markup factor (e.g. Decimal("1.10") for 10%)

    Source: Pratt & Niculita (2008), IBBA Market Pulse (2024), Pepperdine PCM (2024)
    """
    from decimal import Decimal, InvalidOperation

    if advisor_override_pct is not None:
        try:
            override_dec = Decimal(str(advisor_override_pct))
        except (InvalidOperation, ValueError, TypeError):
            override_dec = None
        if override_dec is not None:
            # Defensive bounds: [0, 0.25] = [0%, 25%] — same band as the
            # Mercury UI validator. Outside band → fall through to default.
            if Decimal("0") <= override_dec <= Decimal("0.25"):
                return Decimal("1") + override_dec

    # Map confidence level to dictionary key (handle both "HIGH"/"high" and "MEDIUM"/"medium")
    level_lower = str(confidence_level).lower() if confidence_level else "medium"
    key_mapping = {
        "high": "high_confidence",
        "medium": "medium_confidence",
        "low": "low_confidence"
    }
    mapped_key = key_mapping.get(level_lower, "medium_confidence")

    markup_value = VALUATION_CONSTANTS.ASKING_PRICE_MARKUP.get(mapped_key, 1.08)
    return Decimal(str(markup_value))


def get_net_income_ratio(industry: str, business_model: str) -> Decimal:
    """
    Get the net income to EBITDA ratio for estimation.

    Args:
        industry: Industry classification
        business_model: Business model

    Returns:
        Ratio for net income estimation

    Source: Industry-specific financial ratios
    """
    if industry == "technology" and business_model == "b2b_saas":
        return VALUATION_CONSTANTS.NET_INCOME_ESTIMATION["saas_ratio"]
    elif industry == "manufacturing":
        return VALUATION_CONSTANTS.NET_INCOME_ESTIMATION["manufacturing_ratio"]
    else:
        return VALUATION_CONSTANTS.NET_INCOME_ESTIMATION["default_ratio"]


def get_industry_multiples(industry: str, business_model: str) -> Dict[str, Decimal]:
    """
    Get industry-specific multiples.

    Args:
        industry: Industry classification
        business_model: Business model

    Returns:
        Dictionary with revenue and ebitda multiples

    Source: KPMG (2023), Technology Sector Valuation Report
    """
    revenue_multiples = VALUATION_CONSTANTS.INDUSTRY_REVENUE_MULTIPLES.get(industry, {})
    ebitda_multiples = VALUATION_CONSTANTS.INDUSTRY_EBITDA_MULTIPLES.get(industry, {})

    return {
        "revenue": revenue_multiples.get(business_model, 3.0),
        "ebitda": ebitda_multiples.get(business_model, 8.0)
    }


def get_discount_rate_components() -> Dict[str, Decimal]:
    """
    Get discount rate components for build-up method.

    Returns:
        Dictionary with discount rate components

    Source: Pratt & Grabowski (2014), Cost of Capital, p. 156
    """
    return VALUATION_CONSTANTS.DISCOUNT_RATE_COMPONENTS


def get_monte_carlo_parameters() -> Dict[str, Any]:
    """
    Get Monte Carlo simulation parameters.

    Returns:
        Dictionary with simulation parameters

    Source: Glasserman (2003), Monte Carlo Methods in Financial Engineering, p. 23
    """
    return VALUATION_CONSTANTS.MONTE_CARLO_PARAMETERS


def get_sensitivity_parameters() -> Dict[str, Decimal]:
    """
    Get sensitivity analysis parameters.

    Returns:
        Dictionary with sensitivity parameters

    Source: McKinsey (2020), Valuation, Chapter 8
    """
    return VALUATION_CONSTANTS.SENSITIVITY_ANALYSIS


def get_quality_thresholds() -> Dict[str, Decimal]:
    """
    Get data quality thresholds.

    Returns:
        Dictionary with quality thresholds

    Source: Internal data quality standards
    """
    return VALUATION_CONSTANTS.DATA_QUALITY_THRESHOLDS


def get_confidence_thresholds() -> Dict[str, Decimal]:
    """
    Get confidence score thresholds.

    Returns:
        Dictionary with confidence thresholds

    Source: Statistical confidence interval standards
    """
    return VALUATION_CONSTANTS.CONFIDENCE_THRESHOLDS


def get_quality_metrics() -> Dict[str, int]:
    """
    Get valuation quality metrics.

    Returns:
        Dictionary with quality metrics

    Source: Valuation quality standards
    """
    return VALUATION_CONSTANTS.QUALITY_METRICS


# Validation functions
def validate_confidence_level(confidence_level: str) -> bool:
    """Validate confidence level is supported."""
    return confidence_level in VALUATION_CONSTANTS.CONFIDENCE_SPREADS


def validate_company_size(company_size: str) -> bool:
    """Validate company size is supported."""
    return company_size in VALUATION_CONSTANTS.ASYMMETRIC_RANGES


def validate_industry(industry: str) -> bool:
    """Validate industry is supported."""
    return industry in VALUATION_CONSTANTS.INDUSTRY_REVENUE_MULTIPLES


def validate_business_model(business_model: str, industry: str) -> bool:
    """Validate business model is supported for industry."""
    industry_models = VALUATION_CONSTANTS.INDUSTRY_REVENUE_MULTIPLES.get(industry, {})
    return business_model in industry_models


# Export all constants for easy access
__all__ = [
    'VALUATION_CONSTANTS',
    'get_confidence_spread',
    'get_asymmetric_factors', 
    'get_asking_price_markup',
    'get_net_income_ratio',
    'get_industry_multiples',
    'get_discount_rate_components',
    'get_monte_carlo_parameters',
    'get_sensitivity_parameters',
    'get_quality_thresholds',
    'get_confidence_thresholds',
    'get_quality_metrics',
    'validate_confidence_level',
    'validate_company_size',
    'validate_industry',
    'validate_business_model',
    'get_ebitda_weights',
    'get_ebitda_weights_desc',
    'recency_weights',
    'recency_weights_desc',
]


def recency_weights(num_years: int) -> tuple:
    """
    Linear recency-ramp weights ordered oldest-first, summing to 1.0.

    Each year is weighted by its recency rank (oldest=1 … most_recent=n) and
    normalized, so the most recent year always carries the most weight and no
    visible year is dropped:

        n=1 -> (1.0,)
        n=2 -> (1/3, 2/3)                 ≈ 33% / 67%
        n=3 -> (1/6, 2/6, 3/6)            ≈ 17% / 33% / 50%   (the canonical 50/33/17)
        n=4 -> (1/10, 2/10, 3/10, 4/10)   = 10% / 20% / 30% / 40%
        n=5 -> (1/15, 2/15, 3/15, 4/15, 5/15)

    The n≤3 cases reproduce the McKinsey/Damodaran weights exactly; n=4..5 extend
    the same recency principle smoothly across the visible window.

    Source: McKinsey Valuation (2015), Ch. 7; Damodaran (2012), pp. 234-237.
    """
    n = max(int(num_years), 1)
    denominator = Decimal(n * (n + 1) // 2)  # 1+2+…+n
    return tuple(Decimal(rank) / denominator for rank in range(1, n + 1))


def recency_weights_desc(num_years: int) -> tuple:
    """Linear recency-ramp weights ordered most-recent-first (for report display)."""
    return tuple(reversed(recency_weights(num_years)))


def get_ebitda_weights(num_years: int) -> tuple:
    """
    Get EBITDA weights ordered oldest-first for calculation.

    Returns:
        Tuple of Decimal weights summing to 1.0 (linear recency ramp).

    Source: McKinsey Valuation (2015), Ch. 7; Damodaran (2012), pp. 234-237.
    """
    return recency_weights(num_years)


def get_ebitda_weights_desc(num_years: int) -> tuple:
    """
    Get EBITDA weights ordered most-recent-first for report display.

    Returns:
        Tuple of Decimal weights summing to 1.0 (linear recency ramp).

    Source: McKinsey Valuation (2015), Ch. 7; Damodaran (2012), pp. 234-237.
    """
    return recency_weights_desc(num_years)
