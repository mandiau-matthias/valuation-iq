"""
Decimal Constants for Valuation Engine

This module centralizes all numeric constants used throughout the valuation
calculation pipeline to ensure type safety and consistency.

All constants are defined as Decimal types to avoid floating-point precision
issues in financial calculations.

Author: Upswitch Engineering Team
Date: November 2025
Status: Production Ready
"""

from decimal import Decimal
from typing import Dict


class DecimalConstants:
    """
    Centralized numeric constants for valuation calculations.

    All values are Decimal types to ensure precise financial calculations
    without floating-point rounding errors.

    Academic Sources:
    - McKinsey Valuation (2015)
    - Damodaran (2012)
    - Duff & Phelps Size Premium Study (2024)
    - PwC Valuation Guidelines
    - Big 4 Accounting Firm Standards
    """

    # ==================== SIZE DISCOUNT TIERS ====================
    # Based on McKinsey Size Premium Study and Duff & Phelps research

    # Revenue thresholds for size categorization (in EUR)
    MICRO_CAP_THRESHOLD = Decimal('1000000')       # €1M
    SMALL_CAP_THRESHOLD = Decimal('5000000')       # €5M
    MID_CAP_THRESHOLD = Decimal('50000000')        # €50M
    LARGE_CAP_THRESHOLD = Decimal('500000000')     # €500M

    # 9-tier size discount percentages aligned with Step 5 calculator
    # Based on Banz (1981), Fama-French (1993), Duff & Phelps Size Study
    SIZE_DISCOUNT_MICRO_CAP = Decimal('-0.225')        # -22.5% for <€250K
    SIZE_DISCOUNT_SMALL_MICRO_CAP = Decimal('-0.15')   # -15.0% for €250K-€500K
    SIZE_DISCOUNT_SMALL = Decimal('-0.10')             # -10.0% for €500K-€1M
    SIZE_DISCOUNT_SMALL_MEDIUM = Decimal('-0.05')      # -5.0% for €1M-€2M
    SIZE_DISCOUNT_MEDIUM_SMALL = Decimal('-0.035')     # -3.5% for €2M-€3M
    SIZE_DISCOUNT_LOWER_MID = Decimal('-0.025')        # -2.5% for €3M-€10M
    SIZE_DISCOUNT_MID = Decimal('-0.015')              # -1.5% for €10M-€25M
    SIZE_DISCOUNT_UPPER_MID = Decimal('-0.01')         # -1.0% for €25M-€50M
    SIZE_DISCOUNT_LARGE = Decimal('0.00')              # 0.0% for ≥€50M

    # Minimum size discount for small companies
    SIZE_DISCOUNT_MINIMUM = Decimal('-0.02')       # -2% minimum

    # ==================== LIQUIDITY DISCOUNT BOUNDS ====================
    # Based on Damodaran (2012), PwC/Deloitte Restricted Stock Studies

    LIQUIDITY_DISCOUNT_FLOOR = Decimal('-0.30')    # -30% (maximum discount, most negative)
    LIQUIDITY_DISCOUNT_CEILING = Decimal('-0.10')  # -10% (minimum discount, least negative)

    # Base liquidity discount for private companies
    LIQUIDITY_BASE_DISCOUNT = Decimal('-0.20')     # -20% baseline

    # ==================== OWNER CONCENTRATION RISK ====================
    # Based on McKinsey Valuation (2015), Big 4 Key Person Risk Standards

    # Owner/Employee ratio thresholds
    OWNER_RATIO_LOW_THRESHOLD = Decimal('0.10')    # 10% - Low risk
    OWNER_RATIO_MEDIUM_THRESHOLD = Decimal('0.25') # 25% - Medium risk
    OWNER_RATIO_HIGH_THRESHOLD = Decimal('0.50')   # 50% - High risk
    OWNER_RATIO_CRITICAL_THRESHOLD = Decimal('1.00') # 100% - Critical risk

    # Owner concentration adjustment percentages
    OWNER_CONCENTRATION_LOW = Decimal('-0.03')      # -3%
    OWNER_CONCENTRATION_MEDIUM = Decimal('-0.08')   # -8%
    OWNER_CONCENTRATION_HIGH = Decimal('-0.15')     # -15%
    OWNER_CONCENTRATION_CRITICAL = Decimal('-0.20') # -20%

    # Minimum owner concentration discount
    OWNER_CONCENTRATION_MINIMUM = Decimal('-0.03')  # -3% minimum

    # ==================== EBITDA MARGIN BOUNDS ====================

    EBITDA_MARGIN_MIN = Decimal('-1.00')           # -100%
    EBITDA_MARGIN_MAX = Decimal('1.00')            # +100%

    # ==================== GROWTH RATE BOUNDS ====================

    GROWTH_RATE_MIN = Decimal('-0.50')             # -50%
    GROWTH_RATE_MAX = Decimal('5.00')              # +500%

    # ==================== DEFAULT MULTIPLES ====================
    # Fallback multiples when no data source is available

    DEFAULT_EV_REVENUE_MULTIPLE = Decimal('1.0')
    DEFAULT_EV_EBITDA_MULTIPLE = Decimal('5.0')
    DEFAULT_PE_RATIO = Decimal('16.0')

    # ==================== MULTIPLE BOUNDS ====================

    EV_REVENUE_MIN = Decimal('0.1')
    EV_REVENUE_MAX = Decimal('20.0')
    EV_EBITDA_MIN = Decimal('1.0')
    EV_EBITDA_MAX = Decimal('50.0')
    PE_RATIO_MIN = Decimal('3.0')
    PE_RATIO_MAX = Decimal('100.0')

    # ==================== SME CALIBRATION FACTORS ====================
    # Based on McKinsey Valuation Standards and Duff & Phelps Studies
    # Database multiples (Capital IQ, Bloomberg, PitchBook) are biased toward
    # larger companies (€50M+ revenue). For SMEs, systematic calibration required.
    #
    # SCOPE (Feb 2025 - Academic Recalibration):
    # - Size premium removal: 10-12% (Damodaran 2024 data)
    # - Baseline market liquidity: 18-20% (McKinsey/Duff & Phelps)
    # - Database quality/coverage: 2-3%
    # - Does NOT include: Management depth (Step 4), Company-specific illiquidity (Step 4)
    #
    # Target: 30-35% for micro, 22-28% for small (vs. old 42-35%)

    # Revenue thresholds for calibration tiers
    SME_CALIBRATION_THRESHOLD = Decimal('5000000')  # €5M - no calibration above this
    MICRO_CAP_REVENUE_THRESHOLD = Decimal('250000')  # €250K - micro-cap threshold
    MICRO_REVENUE_THRESHOLD = Decimal('500000')     # €500K
    SMALL_REVENUE_THRESHOLD = Decimal('1000000')    # €1M (same as MICRO_CAP_THRESHOLD)
    MEDIUM_REVENUE_THRESHOLD = Decimal('3000000')   # €3M

    # Base calibration factors by tier (multiply database multiple by this factor)
    # UPDATED Feb 2025 Phase 2: Reduced to academic levels based on Damodaran 2024 + McKinsey 2015
    CALIBRATION_MICRO_CAP = Decimal('0.40')  # 60% reduction for <€250K (micro-cap - adjusted from 0.35)
    CALIBRATION_MICRO = Decimal('0.50')      # 50% reduction for €250K-€500K (adjusted from 0.40)
    CALIBRATION_VERY_SMALL = Decimal('0.72') # 28% reduction for €500K-€1M (was 35%)
    CALIBRATION_SMALL = Decimal('0.78')      # 22% reduction for €1M-€3M (was 30%)
    CALIBRATION_MEDIUM = Decimal('0.88')     # 12% reduction for €3M-€5M (was 15%)

    # Industry adjustments to calibration factor (added to base factor)
    CALIBRATION_TECH_PREMIUM = Decimal('0.10')           # +10% for tech/SaaS (asset-light, scalable)
    CALIBRATION_ASSET_HEAVY_DISCOUNT = Decimal('-0.05')  # -5% for manufacturing/retail

    # Calibration bounds
    CALIBRATION_FACTOR_MIN = Decimal('0.30')  # Minimum 30% of database multiple
    CALIBRATION_FACTOR_MAX = Decimal('1.00')  # Maximum 100% (no reduction)

    # Target multiple ranges (EBITDA multiples, post-calibration)
    # Used for validation in Step 11 to ensure final multiples are reasonable

    # Asset-light services (SaaS, Consulting)
    TARGET_MULTIPLE_TECH_MIN = Decimal('2.0')
    TARGET_MULTIPLE_TECH_MAX = Decimal('10.0')

    # Manufacturing/Industrial
    TARGET_MULTIPLE_MANUFACTURING_MIN = Decimal('2.0')
    TARGET_MULTIPLE_MANUFACTURING_MAX = Decimal('7.0')

    # Retail/Hospitality
    TARGET_MULTIPLE_RETAIL_MIN = Decimal('1.5')
    TARGET_MULTIPLE_RETAIL_MAX = Decimal('6.0')

    # General SME (default)
    TARGET_MULTIPLE_SME_MIN = Decimal('2.0')
    TARGET_MULTIPLE_SME_MAX = Decimal('6.0')

    # ==================== CONFIDENCE SCORE THRESHOLDS ====================

    CONFIDENCE_HIGH_THRESHOLD = Decimal('0.80')    # 80%
    CONFIDENCE_MEDIUM_THRESHOLD = Decimal('0.60')  # 60%
    CONFIDENCE_LOW_THRESHOLD = Decimal('0.40')     # 40%

    # ==================== SOLE TRADER ADJUSTMENTS ====================

    SOLE_TRADER_SIZE_ADJUSTMENT = Decimal('-0.05')      # Additional -5% size discount
    SOLE_TRADER_LIQUIDITY_ADJUSTMENT = Decimal('-0.05') # Additional -5% liquidity discount

    # ==================== CONTROL PREMIUM / MINORITY DISCOUNT ====================
    # Based on Mergerstat and Control Premium Studies

    CONTROL_PREMIUM_LOW = Decimal('0.10')          # 10%
    CONTROL_PREMIUM_MEDIUM = Decimal('0.20')       # 20%
    CONTROL_PREMIUM_HIGH = Decimal('0.30')         # 30%

    MINORITY_DISCOUNT_LOW = Decimal('-0.10')       # -10%
    MINORITY_DISCOUNT_MEDIUM = Decimal('-0.20')    # -20%
    MINORITY_DISCOUNT_HIGH = Decimal('-0.30')      # -30%

    # ==================== ASKING PRICE MARKUP ====================

    ASKING_PRICE_MARKUP_DEFAULT = Decimal('0.15')  # 15% above mid-point
    ASKING_PRICE_MARKUP_MIN = Decimal('0.10')      # 10%
    ASKING_PRICE_MARKUP_MAX = Decimal('0.25')      # 25%

    # ==================== VALUATION RANGE SPREAD ====================

    RANGE_SPREAD_NARROW = Decimal('0.15')          # ±15% (high confidence)
    RANGE_SPREAD_MEDIUM = Decimal('0.25')          # ±25% (medium confidence)
    RANGE_SPREAD_WIDE = Decimal('0.35')            # ±35% (low confidence)

    # ==================== ZERO AND ONE ====================

    ZERO = Decimal('0')
    ONE = Decimal('1')

    # ==================== ROUNDING PRECISION ====================

    DECIMAL_PLACES_CURRENCY = 2                    # 2 decimal places for currency
    DECIMAL_PLACES_PERCENTAGE = 4                  # 4 decimal places for percentages
    DECIMAL_PLACES_RATIO = 6                       # 6 decimal places for ratios

    # ==================== VALIDATION THRESHOLDS ====================

    EPSILON = Decimal('0.0001')                    # Threshold for "effectively zero"

    # Minimum values for calculations
    MIN_REVENUE = Decimal('1000')                  # €1,000 minimum revenue
    MIN_EBITDA = Decimal('-1000000000')            # Allow negative EBITDA (losses)
    MIN_EMPLOYEES = 0                              # Integer count
    MIN_OWNERS = 1                                 # At least 1 owner

    # ==================== BUSINESS TYPE ADJUSTMENTS ====================

    # Multipliers for business-type-specific calibrations
    SAAS_SIZE_MULTIPLIER = Decimal('0.8')          # SaaS gets 20% less size discount
    ECOMMERCE_LIQUIDITY_MULTIPLIER = Decimal('0.9') # E-commerce gets 10% less liquidity discount
    SERVICES_OWNER_MULTIPLIER = Decimal('1.2')     # Services gets 20% more owner concentration risk

    # ==================== DCF PARAMETERS ====================

    # Discount rates
    WACC_MIN = Decimal('0.05')                     # 5%
    WACC_MAX = Decimal('0.30')                     # 30%
    WACC_DEFAULT = Decimal('0.12')                 # 12% (typical for SMEs)

    # Terminal growth rates
    TERMINAL_GROWTH_MIN = Decimal('0.01')          # 1%
    TERMINAL_GROWTH_MAX = Decimal('0.05')          # 5%
    TERMINAL_GROWTH_DEFAULT = Decimal('0.025')     # 2.5%

    # DCF projection years
    DCF_PROJECTION_YEARS = 10                      # Standard 10-year projection

    # ==================== HELPER METHODS ====================

    @classmethod
    def get_size_discount(cls, revenue: Decimal) -> Decimal:
        """
        Get size discount based on revenue tier (9-tier system).

        Aligned with Step 5 size discount calculator and CorrelationAwareCalculator.

        Args:
            revenue: Annual revenue in EUR

        Returns:
            Size discount as Decimal (negative value)
        """
        if revenue < Decimal('250000'):
            return cls.SIZE_DISCOUNT_MICRO_CAP
        elif revenue < Decimal('500000'):
            return cls.SIZE_DISCOUNT_SMALL_MICRO_CAP
        elif revenue < cls.MICRO_CAP_THRESHOLD:
            return cls.SIZE_DISCOUNT_SMALL
        elif revenue < Decimal('2000000'):
            return cls.SIZE_DISCOUNT_SMALL_MEDIUM
        elif revenue < Decimal('3000000'):
            return cls.SIZE_DISCOUNT_MEDIUM_SMALL
        elif revenue < Decimal('10000000'):
            return cls.SIZE_DISCOUNT_LOWER_MID
        elif revenue < Decimal('25000000'):
            return cls.SIZE_DISCOUNT_MID
        elif revenue < cls.MID_CAP_THRESHOLD:
            return cls.SIZE_DISCOUNT_UPPER_MID
        else:
            return cls.SIZE_DISCOUNT_LARGE

    @classmethod
    def get_owner_concentration_adjustment(cls, ratio: Decimal) -> Decimal:
        """
        Get owner concentration adjustment based on owner/employee ratio.

        Args:
            ratio: Owner to employee ratio (normalized)

        Returns:
            Adjustment as Decimal (negative value = discount)
        """
        if ratio >= cls.OWNER_RATIO_CRITICAL_THRESHOLD:
            return cls.OWNER_CONCENTRATION_CRITICAL
        elif ratio >= cls.OWNER_RATIO_HIGH_THRESHOLD:
            return cls.OWNER_CONCENTRATION_HIGH
        elif ratio >= cls.OWNER_RATIO_MEDIUM_THRESHOLD:
            return cls.OWNER_CONCENTRATION_MEDIUM
        else:
            return cls.OWNER_CONCENTRATION_LOW

    @classmethod
    def clamp_value(cls, value: Decimal, min_val: Decimal, max_val: Decimal) -> Decimal:
        """
        Clamp a value between min and max bounds.

        Args:
            value: Value to clamp
            min_val: Minimum bound
            max_val: Maximum bound

        Returns:
            Clamped value
        """
        return max(min_val, min(max_val, value))

    @classmethod
    def is_effectively_zero(cls, value: Decimal) -> bool:
        """
        Check if a value is effectively zero (within epsilon threshold).

        Args:
            value: Value to check

        Returns:
            True if value is within epsilon of zero
        """
        return abs(value) < cls.EPSILON

    @classmethod
    def to_percentage(cls, decimal_value: Decimal, places: int = 2) -> str:
        """
        Convert decimal to percentage string.

        Args:
            decimal_value: Decimal value (e.g., 0.15 for 15%)
            places: Decimal places for rounding

        Returns:
            Formatted percentage string (e.g., "15.00%")
        """
        percentage = decimal_value * Decimal('100')
        return f"{percentage:.{places}f}%"

    @classmethod
    def get_all_constants(cls) -> Dict[str, Decimal]:
        """
        Get all numeric constants as a dictionary.

        Returns:
            Dictionary of constant names to values
        """
        return {
            name: value
            for name, value in vars(cls).items()
            if not name.startswith('_') and isinstance(value, Decimal)
        }


# ==================== CONVENIENCE FUNCTIONS ====================

def get_size_tier(revenue: Decimal) -> str:
    """
    Get human-readable size tier description.

    Args:
        revenue: Annual revenue in EUR

    Returns:
        Size tier description
    """
    if revenue < DecimalConstants.MICRO_CAP_THRESHOLD:
        return "Micro (<€1M)"
    elif revenue < DecimalConstants.SMALL_CAP_THRESHOLD:
        return "Small (€1M-€5M)"
    elif revenue < DecimalConstants.MID_CAP_THRESHOLD:
        return "Mid (€5M-€50M)"
    elif revenue < DecimalConstants.LARGE_CAP_THRESHOLD:
        return "Large (€50M-€500M)"
    else:
        return "Mega (>€500M)"


def get_risk_level(ratio: Decimal) -> str:
    """
    Get risk level description based on owner concentration ratio.

    Args:
        ratio: Owner to employee ratio (normalized)

    Returns:
        Risk level description
    """
    if ratio >= DecimalConstants.OWNER_RATIO_CRITICAL_THRESHOLD:
        return "CRITICAL"
    elif ratio >= DecimalConstants.OWNER_RATIO_HIGH_THRESHOLD:
        return "HIGH"
    elif ratio >= DecimalConstants.OWNER_RATIO_MEDIUM_THRESHOLD:
        return "MEDIUM"
    else:
        return "LOW"


# ==================== EXPORT ====================

__all__ = [
    'DecimalConstants',
    'get_size_tier',
    'get_risk_level'
]

