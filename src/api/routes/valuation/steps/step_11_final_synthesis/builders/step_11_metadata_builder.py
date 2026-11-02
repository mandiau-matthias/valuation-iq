"""
Step 11 Metadata Builder

Builds metadata dictionary for Step 11.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import from_decimal, to_decimal


class Step11MetadataBuilder:
    """Builds metadata dictionary for Step 11."""

    def __init__(self):
        """Initialize the metadata builder."""
        pass

    def build_metadata_dict(
        self,
        valuation_low: Decimal,
        valuation_mid: Decimal,
        valuation_high: Decimal,
        original_low: Decimal,
        original_mid: Decimal,
        original_high: Decimal,
        rounding_details: Dict[str, Any],
        value_chain_validated: bool,
        equity_value_mid: Optional[Decimal],
        use_fallback: bool,
        quality_checkpoint: Optional[Dict[str, Any]],
        methodologies: Dict[str, Any],
        academic_sources: list,
        professional_review_ready: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build comprehensive metadata dictionary.

        Args:
            valuation_low: Final valuation low value
            valuation_mid: Final valuation mid value
            valuation_high: Final valuation high value
            original_low: Original valuation low (before rounding)
            original_mid: Original valuation mid (before rounding)
            original_high: Original valuation high (before rounding)
            rounding_details: Rounding details dictionary
            value_chain_validated: Whether value chain was validated
            equity_value_mid: Equity value mid from Step 7/8
            use_fallback: Whether fallback logic was used
            quality_checkpoint: Quality checkpoint dict
            methodologies: Methodologies dict
            academic_sources: List of academic sources
            professional_review_ready: Professional review readiness dict

        Returns:
            Metadata dictionary
        """
        metadata = {
            "methodology": "McKinsey modular step pipeline",
            "standards": "IFRS 13, IVS 2017, Big 4 methodologies",
            "precision": "Rounded to meaningful values",
            "rounding_details": rounding_details,
            "value_chain_validated": value_chain_validated,
            "step8_7_equity_value_mid": equity_value_mid,
            "fallback_mode": use_fallback,  # Indicate if fallback logic was used
        }

        if use_fallback:
            metadata["fallback_reason"] = "Step 10 results unavailable or Step 10 failed"
            metadata["fallback_methodology"] = "Confidence-based spread from Step 7/8 equity values"

        if quality_checkpoint:
            metadata["final_quality_checkpoint"] = quality_checkpoint

        # Add methodology information
        metadata.update(
            {
                "methodologies_used": list(set(methodologies.get("used_methodologies", []))),
                "primary_method": methodologies.get("primary_method"),
                "range_methodology": methodologies.get("range_methodology"),
                "academic_sources_count": len(academic_sources),
                "professional_review_ready": professional_review_ready.get("ready", False),
                "professional_review_status": professional_review_ready.get("status", "UNKNOWN"),
            }
        )

        return metadata

    def add_rounding_details(
        self,
        original_low: Decimal,
        original_mid: Decimal,
        original_high: Decimal,
        rounded_low: Decimal,
        rounded_mid: Decimal,
        rounded_high: Decimal,
    ) -> Dict[str, Any]:
        """
        Calculate and add rounding impact details.

        Args:
            original_low: Original valuation low (before rounding)
            original_mid: Original valuation mid (before rounding)
            original_high: Original valuation high (before rounding)
            rounded_low: Rounded valuation low
            rounded_mid: Rounded valuation mid
            rounded_high: Rounded valuation high

        Returns:
            Rounding details dictionary
        """
        rounding_impact_mid = (
            ((rounded_mid - original_mid) / original_mid * 100) if original_mid > 0 else 0
        )
        rounding_impact_low = (
            ((rounded_low - original_low) / original_low * 100) if original_low > 0 else 0
        )
        rounding_impact_high = (
            ((rounded_high - original_high) / original_high * 100) if original_high > 0 else 0
        )

        return {
            "original_low": original_low,
            "original_mid": original_mid,
            "original_high": original_high,
            "rounded_low": rounded_low,
            "rounded_mid": rounded_mid,
            "rounded_high": rounded_high,
            "rounding_impact_mid_pct": rounding_impact_mid,
            "rounding_impact_low_pct": rounding_impact_low,
            "rounding_impact_high_pct": rounding_impact_high,
        }
