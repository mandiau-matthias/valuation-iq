"""
Score Breakdown Generator for Step 0 Data Quality

Generates detailed breakdown of quality score components.
"""

from typing import Any, Dict


class ScoreBreakdownGenerator:
    """Generates detailed breakdown of quality score components."""

    @staticmethod
    def generate_breakdown(dimension_scores: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a detailed breakdown from dimension scores.

        Args:
            dimension_scores: Dictionary of dimension name to score

        Returns:
            Dictionary with breakdown details per dimension
        """
        breakdown = {}
        for dimension, score in dimension_scores.items():
            breakdown[dimension] = {
                "score": score,
                "weight": 1.0 / len(dimension_scores) if dimension_scores else 0,
            }
        return breakdown

    @staticmethod
    def get_score_breakdown(request) -> Dict[str, Any]:
        """
        Get detailed breakdown of quality score components.

        Args:
            request: The valuation request object

        Returns:
            Dictionary with breakdown of available data components
        """
        breakdown = {
            "revenue_available": False,
            "ebitda_available": False,
            "historical_years_count": 0,
            "balance_sheet_complete": False,
            "growth_metrics_available": False,
        }

        if hasattr(request, "current_year_data") and request.current_year_data:
            breakdown["revenue_available"] = bool(
                request.current_year_data.revenue and request.current_year_data.revenue > 0
            )
            breakdown["ebitda_available"] = bool(
                hasattr(request.current_year_data, "ebitda")
                and request.current_year_data.ebitda is not None
            )

            has_debt = (
                hasattr(request.current_year_data, "total_debt")
                and request.current_year_data.total_debt is not None
            )
            has_cash = (
                hasattr(request.current_year_data, "cash")
                and request.current_year_data.cash is not None
            )
            breakdown["balance_sheet_complete"] = has_debt and has_cash

        # Try both attribute names for backward compatibility
        historical_years = getattr(request, "historical_years_data", None) or getattr(
            request, "historical_years", []
        )
        if historical_years is None:
            historical_years = []
        breakdown["historical_years_count"] = (
            len(historical_years) if isinstance(historical_years, list) else 0
        )

        if hasattr(request, "projections") and request.projections:
            breakdown["growth_metrics_available"] = bool(
                hasattr(request.projections, "revenue_growth_rate")
                and request.projections.revenue_growth_rate is not None
            )

        return breakdown
