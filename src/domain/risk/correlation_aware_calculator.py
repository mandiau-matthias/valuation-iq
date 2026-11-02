"""
Correlation-Aware Risk Adjustment Calculator

This module implements correlation-aware calibration for risk adjustments in SME valuations.
It prevents over-conservative valuations when multiple correlated risk factors are present.

Academic Foundation:
- SIZE_RISK_INTEGRATION_FRAMEWORK.md: Correlation methodology for Size × Liquidity
- RISK_FACTOR_CORRELATION_FRAMEWORK.md: New framework for Size × Revenue Trend
- Empirical validation from Belgian/Dutch SME transaction data (2015-2024)

Key Insight:
When size discount (-22.5% for micro-cap) and revenue trend discount (-18% for moderate decline)
are both applied, the combined effect can exceed empirical transaction data (-25% to -35%).
Calibration adjusts revenue trend discount to account for correlation (r ≈ 0.40).

Author: Upswitch Engineering Team
Date: December 20, 2025
"""

from decimal import Decimal
from typing import Dict, Tuple
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CorrelationAwareCalculator:
    """
    Calculates correlation-adjusted risk discounts for SME valuations.
    
    This calculator implements the correlation framework established in:
    - RISK_FACTOR_CORRELATION_FRAMEWORK.md (December 2025)
    - SIZE_RISK_INTEGRATION_FRAMEWORK.md (existing Size × Liquidity treatment)
    
    The calibration prevents over-discounting when multiple correlated risk factors
    are present (e.g., small company with declining revenue).
    """
    
    # Empirically-derived correlation coefficients
    RISK_FACTOR_CORRELATIONS = {
        ("size", "liquidity"): Decimal("0.65"),  # High - already calibrated in system
        ("size", "revenue_trend"): Decimal("0.40"),  # Moderate - NEW
        ("size", "growth"): Decimal("-0.40"),  # Negative - already calibrated
        ("revenue_trend", "owner_concentration"): Decimal("0.25"),  # Low-moderate
        ("liquidity", "country_risk"): Decimal("0.15"),  # Low
    }
    
    # Size tier thresholds (aligned with step_5_discount_calculator.py)
    SIZE_TIERS = {
        "micro_cap": Decimal("250000"),          # < €250K
        "small_micro_cap": Decimal("500000"),    # €250K-€500K
        "small": Decimal("1000000"),             # €500K-€1M
        "small_medium": Decimal("2000000"),      # €1M-€2M
        "medium_small": Decimal("3000000"),      # €2M-€3M
        "lower_mid_market": Decimal("10000000"), # €3M-€10M
        "mid_market": Decimal("25000000"),       # €10M-€25M
        "upper_mid_market": Decimal("50000000"), # €25M-€50M
    }
    
    # Size discounts per tier (aligned with step_5_discount_calculator.py)
    SIZE_DISCOUNTS = {
        "micro_cap": Decimal("-0.225"),           # -22.5%
        "small_micro_cap": Decimal("-0.15"),      # -15.0%
        "small": Decimal("-0.10"),                # -10.0%
        "small_medium": Decimal("-0.05"),         # -5.0%
        "medium_small": Decimal("-0.035"),        # -3.5%
        "lower_mid_market": Decimal("-0.025"),    # -2.5%
        "mid_market": Decimal("-0.015"),          # -1.5%
        "upper_mid_market": Decimal("-0.01"),     # -1.0%
        "large": Decimal("0.00"),                 # 0.0%
    }
    
    def __init__(self):
        """Initialize the correlation-aware calculator."""
        self.logger = logger
    
    def get_size_tier_from_revenue(self, revenue: Decimal) -> str:
        """
        Determine size tier based on revenue, aligned with Step 5 discount tiers.
        
        Args:
            revenue: Company annual revenue
            
        Returns:
            Size tier name (e.g., "micro_cap", "small_micro_cap")
        """
        revenue = to_decimal(revenue)
        
        if revenue < self.SIZE_TIERS["micro_cap"]:
            return "micro_cap"
        elif revenue < self.SIZE_TIERS["small_micro_cap"]:
            return "small_micro_cap"
        elif revenue < self.SIZE_TIERS["small"]:
            return "small"
        elif revenue < self.SIZE_TIERS["small_medium"]:
            return "small_medium"
        elif revenue < self.SIZE_TIERS["medium_small"]:
            return "medium_small"
        elif revenue < self.SIZE_TIERS["lower_mid_market"]:
            return "lower_mid_market"
        elif revenue < self.SIZE_TIERS["mid_market"]:
            return "mid_market"
        elif revenue < self.SIZE_TIERS["upper_mid_market"]:
            return "upper_mid_market"
        else:
            return "large"
    
    def get_size_discount_for_tier(self, size_tier: str) -> Decimal:
        """
        Get the size discount for a given tier.
        
        Args:
            size_tier: Size tier name
            
        Returns:
            Size discount as negative Decimal (e.g., -0.22 for -22%)
        """
        return self.SIZE_DISCOUNTS.get(size_tier, Decimal("0.0"))
    
    def adjust_revenue_trend_discount(
        self,
        base_discount: Decimal,
        size_tier: str,
        revenue: Decimal
    ) -> Tuple[Decimal, Dict[str, any]]:
        """
        Adjust revenue trend discount to account for correlation with size.
        
        Calibration Formula:
        adjusted_discount = base_discount × (1 - correlation × severity_factor)
        
        Where:
        - correlation = 0.40 (size × revenue_trend correlation coefficient)
        - severity_factor = size_discount_magnitude / 0.30 (normalized to max theoretical)
        
        Academic Support:
        - RISK_FACTOR_CORRELATION_FRAMEWORK.md: Empirical validation
        - McKinsey (2015), p. 364: Guidance on correlated risk adjustments
        - Empirical data: Belgian/Dutch SME transactions (2015-2024)
        
        Args:
            base_discount: Base revenue trend discount (e.g., -0.18 for moderate decline)
            size_tier: Company size tier (e.g., "micro_cap")
            revenue: Company revenue (for logging/validation)
            
        Returns:
            Tuple of (adjusted_discount, metadata_dict)
            - adjusted_discount: Calibrated discount as negative Decimal
            - metadata: Dict with calibration details for transparency
        """
        base_discount = to_decimal(base_discount)
        revenue = to_decimal(revenue)
        
        # Get size discount for this tier
        size_discount = self.get_size_discount_for_tier(size_tier)
        
        # If no size discount is applied, no calibration needed
        if size_discount == Decimal("0.0"):
            self.logger.info(
                f"No correlation adjustment needed: no size discount for {size_tier} tier"
            )
            return base_discount, {
                "calibration_applied": False,
                "reason": "No size discount present",
                "base_discount": float(base_discount),
                "adjusted_discount": float(base_discount),
                "size_tier": size_tier,
            }
        
        # Get correlation coefficient
        correlation = self.RISK_FACTOR_CORRELATIONS[("size", "revenue_trend")]
        
        # Calculate severity factor (normalized size discount magnitude)
        # Max theoretical size discount is -30%, so we normalize to that
        max_theoretical_size_discount = Decimal("0.30")
        severity_factor = abs(size_discount) / max_theoretical_size_discount
        
        # Calculate adjustment factor
        # Formula: 1 - (correlation × severity_factor)
        adjustment_factor = Decimal("1.0") - (correlation * severity_factor)
        
        # Apply adjustment to base discount
        adjusted_discount = base_discount * adjustment_factor
        
        # Calculate reduction percentage for transparency
        reduction_pct = (Decimal("1.0") - adjustment_factor) * Decimal("100")
        
        self.logger.info(
            f"Correlation adjustment applied: "
            f"size_tier={size_tier}, "
            f"size_discount={float(size_discount):.1%}, "
            f"base_revenue_discount={float(base_discount):.1%}, "
            f"adjusted_revenue_discount={float(adjusted_discount):.1%}, "
            f"reduction={float(reduction_pct):.1f}%, "
            f"correlation={float(correlation):.2f}"
        )
        
        metadata = {
            "calibration_applied": True,
            "size_tier": size_tier,
            "size_discount": float(size_discount),
            "base_discount": float(base_discount),
            "adjusted_discount": float(adjusted_discount),
            "correlation_coefficient": float(correlation),
            "severity_factor": float(severity_factor),
            "adjustment_factor": float(adjustment_factor),
            "reduction_percentage": float(reduction_pct),
            "academic_source": "McKinsey (2015) Ch. 11, Duff & Phelps (2024)",
            "rationale": (
                f"Revenue trend discount reduced by {float(reduction_pct):.1f}% "
                f"to account for correlation with size discount (r = {float(correlation):.2f}). "
                f"Prevents over-discounting for {size_tier} companies with declining revenue."
            ),
        }
        
        return adjusted_discount, metadata
    
    def validate_combined_discount(
        self,
        size_discount: Decimal,
        revenue_trend_discount: Decimal,
        size_tier: str
    ) -> Dict[str, any]:
        """
        Validate that combined discount falls within empirical ranges.
        
        Empirical Ranges (Belgian/Dutch SME transaction data):
        - Micro-cap: -25% to -35%
        - Very Small: -20% to -30%
        - Small: -18% to -28%
        - Small-Med: -16% to -26%
        - Mid-Market: -15% to -20%
        
        Args:
            size_discount: Size discount applied
            revenue_trend_discount: Revenue trend discount applied (after calibration)
            size_tier: Company size tier
            
        Returns:
            Dict with validation results and empirical comparison
        """
        size_discount = to_decimal(size_discount)
        revenue_trend_discount = to_decimal(revenue_trend_discount)
        
        # Calculate combined discount (multiplicative)
        combined_factor = (Decimal("1.0") + size_discount) * (
            Decimal("1.0") + revenue_trend_discount
        )
        combined_discount_pct = (combined_factor - Decimal("1.0")) * Decimal("100")
        
        # Empirical ranges per tier (aligned with Step 5 tier structure)
        empirical_ranges = {
            "micro_cap": (Decimal("-35"), Decimal("-25")),          # < €250K
            "small_micro_cap": (Decimal("-32"), Decimal("-22")),    # €250K-€500K
            "small": (Decimal("-30"), Decimal("-20")),              # €500K-€1M
            "small_medium": (Decimal("-28"), Decimal("-18")),       # €1M-€2M
            "medium_small": (Decimal("-26"), Decimal("-16")),       # €2M-€3M
            "lower_mid_market": (Decimal("-22"), Decimal("-15")),   # €3M-€10M
            "mid_market": (Decimal("-20"), Decimal("-15")),         # €10M-€25M
            "upper_mid_market": (Decimal("-20"), Decimal("-15")),   # €25M-€50M
            "large": (Decimal("-20"), Decimal("-15")),              # >= €50M
        }
        
        lower_bound, upper_bound = empirical_ranges.get(
            size_tier, (Decimal("-30"), Decimal("-20"))
        )
        
        # Check if within range
        within_range = lower_bound <= combined_discount_pct <= upper_bound
        
        if within_range:
            status = "VALIDATED"
            message = (
                f"Combined discount ({float(combined_discount_pct):.1f}%) falls within "
                f"empirical range for {size_tier} companies ({float(lower_bound):.1f}% to {float(upper_bound):.1f}%)"
            )
        elif combined_discount_pct < lower_bound:
            status = "OVER_CONSERVATIVE"
            message = (
                f"Combined discount ({float(combined_discount_pct):.1f}%) exceeds "
                f"empirical lower bound ({float(lower_bound):.1f}%) for {size_tier}"
            )
        else:
            status = "UNDER_CONSERVATIVE"
            message = (
                f"Combined discount ({float(combined_discount_pct):.1f}%) below "
                f"empirical upper bound ({float(upper_bound):.1f}%) for {size_tier}"
            )
        
        self.logger.info(
            f"Empirical validation: {status} - {message}"
        )
        
        return {
            "status": status,
            "within_empirical_range": within_range,
            "combined_discount_percentage": float(combined_discount_pct),
            "empirical_lower_bound": float(lower_bound),
            "empirical_upper_bound": float(upper_bound),
            "message": message,
            "size_tier": size_tier,
        }
    
    def get_correlation_between(self, factor1: str, factor2: str) -> Decimal:
        """
        Get correlation coefficient between two risk factors.
        
        Args:
            factor1: First risk factor name
            factor2: Second risk factor name
            
        Returns:
            Correlation coefficient (0.0 to 1.0 for positive, -1.0 to 0.0 for negative)
        """
        # Try both orderings
        key1 = (factor1, factor2)
        key2 = (factor2, factor1)
        
        return self.RISK_FACTOR_CORRELATIONS.get(
            key1, self.RISK_FACTOR_CORRELATIONS.get(key2, Decimal("0.0"))
        )

