"""
Step 2 Constants

Centralized constants for Step 2 multiples calculation.
All default values and thresholds are defined here.

Based on:
- McKinsey SME Valuation Standards (7th Edition)
- Industry averages for professional services
- Conservative estimates for risk mitigation
"""

from decimal import Decimal


class Step2MultiplesDefaults:
    """
    Default multiples when no data source available.
    
    References:
    - McKinsey Valuation, Chapter 12: Valuing Small Companies
    - Industry benchmarks from FMP API historical data
    """
    
    # EV/EBITDA Multiple
    DEFAULT_EV_EBITDA = Decimal("7.0")  # Professional services average
    
    # EV/Revenue Multiple  
    DEFAULT_EV_REVENUE = Decimal("1.0")  # Conservative revenue multiple
    
    # PE Ratio
    DEFAULT_PE_RATIO = Decimal("15.0")   # Market average
    
    # Percentile defaults (as multipliers of median)
    PERCENTILE_P25_MULTIPLIER = Decimal("0.8")
    PERCENTILE_P75_MULTIPLIER = Decimal("1.2")


class Step2ValidationThresholds:
    """Validation thresholds for Step 2 calculations."""
    
    # Multiple ranges (realistic bounds)
    MIN_EV_EBITDA = Decimal("0.1")
    MAX_EV_EBITDA = Decimal("50.0")
    
    MIN_EV_REVENUE = Decimal("0.01")
    MAX_EV_REVENUE = Decimal("10.0")
    
    MIN_PE_RATIO = Decimal("1.0")
    MAX_PE_RATIO = Decimal("100.0")
    
    # Revenue thresholds
    MIN_REVENUE = Decimal("1000")  # €1K minimum
    MAX_REVENUE = Decimal("1000000000")  # €1B maximum
    
    # EBITDA thresholds
    MIN_EBITDA = Decimal("-1000000")  # Allow negative EBITDA
    MAX_EBITDA = Decimal("100000000")  # €100M maximum


class Step2DataQualityThresholds:
    """Data quality thresholds for Step 2."""
    
    # Minimum comparables required
    MIN_COMPARABLES_COUNT = 3
    
    # Confidence levels
    HIGH_CONFIDENCE_THRESHOLD = Decimal("0.8")
    MEDIUM_CONFIDENCE_THRESHOLD = Decimal("0.5")
    LOW_CONFIDENCE_THRESHOLD = Decimal("0.3")

