"""
Actionable data quality recommendations.

Recommendations are derived from request completeness and the final quality
score. Keeping them outside DataQualityAssessor keeps the assessor's public
surface focused on orchestration and scoring state.
"""

from decimal import Decimal

from src.utils.decimal_helpers import to_decimal


def generate_quality_recommendations(
    request: object, quality_score: int
) -> list[dict[str, object]]:
    """Generate actionable recommendations to improve quality score."""
    recommendations: list[dict[str, object]] = []

    if _revenue_needs_recommendation(request):
        recommendations.append(
            {
                "priority": "critical",
                "action": "Provide current year revenue data",
                "impact": "Improve quality score by 8+ points",
                "reason": "Revenue is required for all valuation methodologies",
            }
        )

    historical_count = _historical_year_count(request)
    if historical_count < 3:
        points_needed = 3 - historical_count
        recommendations.append(
            {
                "priority": "high",
                "action": f"Add {points_needed} more year(s) of historical data",
                "impact": f"Improve quality score by {min(10, points_needed * 3)} points",
                "reason": "DCF methodology requires 3+ years of historical data",
            }
        )

    if _balance_sheet_needs_recommendation(request):
        recommendations.append(
            {
                "priority": "medium",
                "action": "Provide complete balance sheet data (total debt and cash)",
                "impact": "Improve quality score by 2-4 points",
                "reason": "Complete balance sheet enables accurate EV to Equity conversion",
            }
        )

    if quality_score < 60:
        recommendations.append(
            {
                "priority": "high",
                "action": "Review and improve data completeness and accuracy",
                "impact": f"Current score {quality_score}% limits DCF eligibility (requires 60%+)",
                "reason": "Low data quality score prevents DCF methodology",
            }
        )

    return recommendations


def _current_year_data(request: object) -> object | None:
    current_year_data = getattr(request, "current_year_data", None)
    return current_year_data if current_year_data else None


def _revenue_needs_recommendation(request: object) -> bool:
    current_year_data = _current_year_data(request)
    if current_year_data is None:
        return False

    revenue = getattr(current_year_data, "revenue", None)
    if revenue is None:
        return True
    if isinstance(revenue, (int, float, Decimal)):
        return revenue <= 0

    try:
        return to_decimal(str(revenue)) <= 0
    except (ValueError, TypeError):
        return True


def _historical_year_count(request: object) -> int:
    historical_years = getattr(request, "historical_years_data", None) or getattr(
        request, "historical_years", []
    )
    return len(historical_years) if isinstance(historical_years, list) else 0


def _balance_sheet_needs_recommendation(request: object) -> bool:
    current_year_data = _current_year_data(request)
    if current_year_data is None:
        return False

    has_debt = (
        hasattr(current_year_data, "total_debt")
        and getattr(current_year_data, "total_debt") is not None
    )
    has_cash = hasattr(current_year_data, "cash") and getattr(current_year_data, "cash") is not None
    return not (has_debt and has_cash)
