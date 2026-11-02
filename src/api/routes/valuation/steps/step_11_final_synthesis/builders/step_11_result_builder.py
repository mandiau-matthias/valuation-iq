"""
Step 11 Result Builder

Builds final result dictionary for Step 11.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from src.domain.multiples.advisor_controls import (
    build_pipeline_multiple_build_up,
    normalize_earnings_basis,
)
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.equity_range_normalization import coerce_equity_range_triple

logger = logging.getLogger(__name__)


class Step11ResultBuilder:
    """Builds final result dictionary for Step 11."""

    def __init__(self):
        """Initialize the result builder."""
        pass

    def build_result_dict(
        self,
        valuation_low: Decimal,
        valuation_mid: Decimal,
        valuation_high: Decimal,
        asking_price: Decimal,
        confidence_score: int,
        confidence_level: str,
        methodology_statement: str,
        academic_sources: list,
        professional_review_ready: Dict[str, Any],
        transparency: Optional[Dict[str, Any]],
        multiple_pipeline: Optional[Dict[str, Any]],
        multiple_range_validation: Optional[Dict[str, Any]],
        total_discount_validation: Optional[Dict[str, Any]],
        recommended_asking_multiple: Optional[Decimal] = None,
        sde_cross_check: Optional[Dict[str, Any]] = None,
        value_chain_validated: bool = False,
    ) -> Dict[str, Any]:
        """
        Build comprehensive result dictionary.

        Args:
            valuation_low: Valuation low value
            valuation_mid: Valuation mid value
            valuation_high: Valuation high value
            asking_price: Asking price
            confidence_score: Confidence score (0-100)
            confidence_level: Confidence level (LOW/MEDIUM/HIGH)
            methodology_statement: Methodology statement
            academic_sources: List of academic sources
            professional_review_ready: Professional review readiness dict
            transparency: Transparency report dict
            multiple_pipeline: Multiple pipeline dict
            multiple_range_validation: Multiple range validation dict
            total_discount_validation: Total discount validation dict
            recommended_asking_multiple: Strategic asking multiple (optional)
            sde_cross_check: SDE cross-check data (optional)
            value_chain_validated: Whether value chain was validated

        Returns:
            Result dictionary
        """
        # Final invariant gate at the SOURCE: Step 11 must never emit a
        # triple where mid is outside [low, high]. apply_rounding has its own
        # ordering clamps, but mutations downstream of it (e.g. SDE blend
        # re-runs, post-deal swap) can still rewrite the band. This gate
        # makes Step 11's output contract self-enforcing — the band leaving
        # this builder is always coherent.
        #
        # We bound-widen rather than median-sort because the mid is the
        # canonical economic answer; the band describes uncertainty around
        # it. Moving the mid silently changes the user's valuation.
        valuation_low, valuation_mid, valuation_high, _band_widened = (
            coerce_equity_range_triple(valuation_low, valuation_mid, valuation_high)
        )
        if _band_widened:
            logger.warning(
                "Step 11 result builder widened band so mid lies within [low, high]",
                extra={
                    "step_number": 11,
                    "valuation_low": str(valuation_low),
                    "valuation_mid": str(valuation_mid),
                    "valuation_high": str(valuation_high),
                    "note": (
                        "An upstream synthesis stage (SDE blend, post-deal swap, "
                        "or rounding clamp) produced an unordered band. Mid was "
                        "preserved bit-for-bit; investigate which stage drifted."
                    ),
                },
            )

        result = {
            "valuation_low": valuation_low,
            "valuation_mid": valuation_mid,
            "valuation_high": valuation_high,
            # Downstream invariants consume the final Step 11 answer via
            # equity_* names. Keep these aliases synchronized with valuation_*
            # so SDE-blended final ranges do not get compared against the old
            # Step 7 equity anchor.
            "equity_value_low": valuation_low,
            "equity_value_mid": valuation_mid,
            "equity_value_high": valuation_high,
            "equity_value": valuation_mid,
            "asking_price": asking_price,
            "recommended_asking_multiple": recommended_asking_multiple,
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
            "methodology_statement": methodology_statement,
            "academic_sources": academic_sources,
            "professional_review_ready": professional_review_ready,
            "transparency_report": transparency,
            "multiple_pipeline": multiple_pipeline,
            "multiple_range_validation": multiple_range_validation,
            "total_discount_validation": total_discount_validation,
            "value_chain_validated": value_chain_validated,
        }
        if multiple_pipeline:
            result["earnings_basis"] = normalize_earnings_basis(
                multiple_pipeline.get("metric_type")
            )
            result["multiple_build_up"] = build_pipeline_multiple_build_up(multiple_pipeline)
        if sde_cross_check:
            result["sde_cross_check"] = sde_cross_check
        return result
