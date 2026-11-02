"""
Step 9 Score Calculator

Calculates overall confidence score with weights and adjustments.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from src.utils.decimal_helpers import from_decimal
from src.utils.logging import get_logger

from .step_9_confidence_adjustments import (
    adjustment_total,
    data_quality_warning_adjustments,
    quality_of_earnings_adjustments,
)

logger = get_logger(__name__)


class Step9ScoreCalculator:
    """Calculates overall confidence score."""

    # Factor weights for weighted average
    WEIGHTS = {
        "data_quality": Decimal("0.20"),
        "historical_data": Decimal("0.15"),
        "methodology_agreement": Decimal("0.10"),
        "industry_benchmarks": Decimal("0.15"),
        "company_profile": Decimal("0.15"),
        "market_conditions": Decimal("0.10"),
        "geographic_data": Decimal("0.075"),
        "business_model_clarity": Decimal("0.075"),
    }

    def calculate_overall_score(
        self,
        scores: Dict[str, int],
        step2: Optional[Dict[str, Any]] = None,
        step2_5: Optional[Dict[str, Any]] = None,
    ) -> tuple[int, list]:
        """
        Calculate overall confidence score with size-based adjustments and QoE penalties.

        Args:
            scores: Dictionary of factor scores
            step2: Step 2 result dictionary (for size adjustments)
            step2_5: Step 2.5 result dictionary (for Quality of Earnings penalties)

        Returns:
            Tuple of (overall_score, size_adjustments)
        """
        # Calculate weighted average
        total_score = sum(scores[key] * self.WEIGHTS[key] for key in self.WEIGHTS.keys())
        overall_score = round(total_score)

        # Apply size-based confidence adjustments (McKinsey/Bain 2025)
        qoe_adjustments = quality_of_earnings_adjustments(step2_5)
        self._log_quality_of_earnings_adjustments(qoe_adjustments)
        size_adjustments = [
            self._public_adjustment_payload(adjustment) for adjustment in qoe_adjustments
        ]
        size_adjustments.extend(data_quality_warning_adjustments(step2))
        overall_score += adjustment_total(size_adjustments)

        # Ensure score stays within 0-100 range
        overall_score = max(0, min(100, overall_score))

        # Log size adjustments if any were applied
        if size_adjustments:
            total_adjustment = sum(adj["adjustment"] for adj in size_adjustments)
            # DEBUG: per-adjustment detail; "Step 9: Confidence Score Analysis
            # Complete - X% (LEVEL)" carries the final score.
            logger.debug(
                f"📉 Applied {len(size_adjustments)} size-based confidence adjustment(s): {total_adjustment} points",
                extra={
                    "step_number": 9,
                    "size_adjustments": size_adjustments,
                    "total_adjustment": total_adjustment,
                    "score_before_adjustments": overall_score - total_adjustment,
                    "score_after_adjustments": overall_score,
                    "note": "Size concerns addressed via confidence scoring, not methodology restrictions",
                },
            )

        return overall_score, size_adjustments

    def _log_quality_of_earnings_adjustments(self, adjustments: list[dict[str, object]]) -> None:
        for adjustment in adjustments:
            margin_stdev = adjustment.get("margin_stdev", Decimal("0"))
            if not isinstance(margin_stdev, Decimal):
                margin_stdev = Decimal("0")

            if adjustment.get("log_level") == "warning":
                logger.warning(
                    "⚠️ Quality of Earnings penalty applied for high margin volatility",
                    extra={
                        "step_number": 9,
                        "margin_stdev_pp": from_decimal(margin_stdev),
                        "qoe_penalty": adjustment["adjustment"],
                        "volatility_level": adjustment.get("volatility_level", "LOW"),
                        "academic_source": "Hitchner (2017) - Quality of Earnings Analysis",
                    },
                )
            elif adjustment.get("log_level") == "info":
                logger.info(
                    "ℹ️ Moderate QoE penalty for medium margin volatility",
                    extra={
                        "step_number": 9,
                        "margin_stdev_pp": from_decimal(margin_stdev),
                        "qoe_penalty": adjustment["adjustment"],
                    },
                )

    def _public_adjustment_payload(self, adjustment: dict[str, object]) -> dict[str, object]:
        return {
            "type": adjustment["type"],
            "adjustment": adjustment["adjustment"],
            "reason": adjustment["reason"],
        }

    def determine_confidence_level(self, overall_score: int) -> str:
        """
        Determine confidence level from overall score.

        Args:
            overall_score: Overall confidence score

        Returns:
            Confidence level ('HIGH', 'MEDIUM', or 'LOW')
        """
        if overall_score >= 80:
            return "HIGH"
        elif overall_score >= 60:
            return "MEDIUM"
        else:
            return "LOW"

    def calculate_weighted_contributions(
        self, scores: Dict[str, int]
    ) -> Dict[str, Dict[str, Decimal]]:
        """
        Calculate weighted contributions for each factor.

        Args:
            scores: Dictionary of factor scores

        Returns:
            Dictionary of weighted contributions
        """
        weighted_contributions = {}
        for factor, score in scores.items():
            weight = self.WEIGHTS.get(factor, Decimal("0.0"))
            weighted_contributions[factor] = {
                "factor_score": score,
                "weight": weight,
                "weighted_contribution": score * weight,
            }
        return weighted_contributions
