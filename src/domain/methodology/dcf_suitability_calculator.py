"""
DCF Suitability Score Calculator

Responsibility: Calculate DCF suitability score (0-100) across 6 dimensions.

Single Responsibility: DCF suitability scoring only.
"""

from decimal import Decimal
from typing import List, Optional

from src.domain.historical_years import newest_historical_year, oldest_historical_year
from src.domain.hybrid_types import (
    BUSINESS_MODELS_DCF_FRIENDLY,
    DATA_QUALITY_EXCELLENT,
    DATA_QUALITY_FAIR,
    DATA_QUALITY_GOOD,
    GROWTH_HIGH,
    GROWTH_LOW,
    GROWTH_MODERATE,
    HISTORICAL_DATA_MINIMUM,
    HISTORICAL_DATA_PREFERRED,
    REVENUE_MEDIUM,
    REVENUE_MICRO,
    REVENUE_SMALL,
    REVENUE_VERY_SMALL,
    DCFSuitabilityScore,
)
from src.domain.interfaces.request_protocol import ValuationRequestProtocol
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _positive_decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        decimal_value = to_decimal(value)
    except (TypeError, ValueError):
        return None
    if decimal_value <= 0:
        return None
    return decimal_value


def _year_as_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _revenue_and_year(data_point: object) -> tuple[Optional[Decimal], Optional[int]]:
    return (
        _positive_decimal(getattr(data_point, "revenue", None)),
        _year_as_int(getattr(data_point, "year", None)),
    )


def _current_revenue_and_year(
    request: ValuationRequestProtocol,
) -> tuple[Optional[Decimal], Optional[int]]:
    current_year_data = getattr(request, "current_year_data", None)
    if not current_year_data:
        return None, None
    return _revenue_and_year(current_year_data)


def _growth_period_years(
    *,
    oldest_year: Optional[int],
    newest_year: Optional[int],
    historical_count: int,
    uses_current_year: bool,
) -> int:
    if oldest_year is not None and newest_year is not None and newest_year > oldest_year:
        return newest_year - oldest_year
    return max(1, historical_count - (0 if uses_current_year else 1))


def _compound_annual_growth_rate(
    *,
    oldest_revenue: Decimal,
    newest_revenue: Decimal,
    years: int,
) -> Optional[Decimal]:
    if years < 1:
        return None

    ratio = float(newest_revenue / oldest_revenue)
    cagr_float = ratio ** (1.0 / years) - 1.0
    return Decimal(str(round(cagr_float, 6)))


class DCFSuitabilityCalculator:
    """
    Calculates DCF suitability score across 6 dimensions.

    Single Responsibility: DCF suitability scoring only.
    """

    def __init__(self):
        """Initialize calculator"""
        self.logger = logger

    def calculate_score(
        self, request: ValuationRequestProtocol, quality_score_from_step0: Optional[int] = None
    ) -> DCFSuitabilityScore:
        """
        Calculate DCF suitability score (0-100) across 6 dimensions.

        Scoring:
        - Revenue size: 0-25 points (with growth context)
        - Data quality: 0-25 points (uses Step 0 quality_score if provided)
        - Growth rate: 0-20 points
        - Business model: 0-15 points
        - Recurring revenue: 0-10 points
        - Historical data: 0-5 points

        Total: 100 points maximum

        Args:
            request: Valuation request
            quality_score_from_step0: Optional quality score (0-100) from Step 0.
                                     If provided, maps to 0-25 points for data quality.

        Returns:
            DCFSuitabilityScore with all dimension scores and breakdown
        """
        revenue = request.current_year_data.revenue or Decimal("0")
        business_model = request.business_model.lower() if request.business_model else ""

        # Calculate each dimension score
        revenue_score = self._score_revenue_size(to_decimal(revenue))
        data_quality_score = self._score_data_quality(request, quality_score_from_step0)
        growth_score = self._score_growth_rate(request)
        business_model_score = self._score_business_model(business_model, request)
        raw_recurring = getattr(request, "recurring_revenue_percentage", None)
        recurring_score = self._score_recurring_revenue(
            to_decimal(raw_recurring) if raw_recurring is not None else Decimal("0")
        )
        historical_actuals = [
            year
            for year in (request.historical_years_data or [])
            if not getattr(year, "is_forecast", False)
        ]
        historical_score = self._score_historical_data(historical_actuals)

        # Calculate total
        total_score = (
            revenue_score
            + data_quality_score
            + growth_score
            + business_model_score
            + recurring_score
            + historical_score
        )

        # Build breakdown with explanations
        breakdown = self._build_breakdown(
            request,
            revenue,
            revenue_score,
            data_quality_score,
            growth_score,
            business_model_score,
            business_model,
            recurring_score,
            historical_score,
        )

        # Add explanations to breakdown
        breakdown["revenue_size"]["explanation"] = self._explain_revenue_score(
            to_decimal(revenue), revenue_score
        )
        breakdown["data_quality"]["explanation"] = self._explain_data_quality_score(
            request, data_quality_score
        )
        breakdown["growth_rate"]["explanation"] = self._explain_growth_score(request, growth_score)
        breakdown["business_model"]["explanation"] = self._explain_business_model_score(
            business_model, business_model_score
        )
        breakdown["recurring_revenue"]["explanation"] = self._explain_recurring_score(
            (
                to_decimal(request.recurring_revenue_percentage)
                if request.recurring_revenue_percentage
                else Decimal("0")
            ),
            recurring_score,
        )
        breakdown["historical_data"]["explanation"] = self._explain_historical_score(
            len(historical_actuals), historical_score
        )

        # Check for exclusion reasons
        exclusion_reason = self._check_exclusion_criteria(request)

        return DCFSuitabilityScore(
            total_score=total_score if not exclusion_reason else 0,
            revenue_size_score=revenue_score,
            data_quality_score=data_quality_score,
            growth_score=growth_score,
            business_model_score=business_model_score,
            recurring_revenue_score=recurring_score,
            historical_data_score=historical_score,
            breakdown=breakdown,
            exclusion_reason=exclusion_reason,
        )

    def _score_revenue_size(self, revenue: Decimal) -> int:
        """Score revenue size dimension (0-25 points)"""
        if revenue < REVENUE_MICRO:
            return 0
        elif revenue < REVENUE_VERY_SMALL:
            return 5
        elif revenue < REVENUE_SMALL:
            return 12
        elif revenue < REVENUE_MEDIUM:
            return 18
        else:
            return 25

    def _score_data_quality(
        self, request: ValuationRequestProtocol, quality_score_from_step0: Optional[int]
    ) -> int:
        """
        Score data quality dimension (0-25 points).

        Uses Step 0 quality_score if provided, otherwise calculates from data completeness.
        """
        if quality_score_from_step0 is not None:
            # Map Step 0 quality_score (0-100) to Step 2 data quality score (0-25)
            return int((quality_score_from_step0 / Decimal("100.0")) * 25)

        # Calculate data quality score from data completeness
        score = 0
        current = request.current_year_data
        historical = [
            year
            for year in (request.historical_years_data or [])
            if not getattr(year, "is_forecast", False)
        ]

        # Base score for having current year data (5 points)
        score += 5

        # Balance sheet data (5 points)
        if current.total_assets is not None and current.total_debt is not None:
            score += 5

        # Cash flow data (5 points)
        if current.cash is not None and current.capex is not None:
            score += 5

        # Historical data quality (5 points)
        if len(historical) >= HISTORICAL_DATA_MINIMUM:
            score += 5

        # Profitability and stability (5 points)
        if current.ebitda and current.ebitda > 0:
            score += 3
            # Additional points for consistent profitability
            if len(historical) > 0 and all(h.ebitda and h.ebitda > 0 for h in historical):
                score += 2

        return min(score, 25)  # Cap at 25

    def _score_growth_rate(self, request: ValuationRequestProtocol) -> int:
        """
        Score growth rate dimension (0-20 points).

        Calculates CAGR from historical data and scores based on growth rate.
        """
        growth_rate = self._calculate_growth_rate(request)

        if growth_rate is None:
            # No historical data, assume moderate growth
            return 8

        growth_rate_decimal = to_decimal(growth_rate)
        growth_high_decimal = to_decimal(GROWTH_HIGH)
        growth_moderate_decimal = to_decimal(GROWTH_MODERATE)
        growth_low_decimal = to_decimal(GROWTH_LOW)

        if growth_rate_decimal >= growth_high_decimal:
            return 20  # ≥ 25% CAGR
        elif growth_rate_decimal >= growth_moderate_decimal:
            return 15  # 15-25% CAGR
        elif growth_rate_decimal >= growth_low_decimal:
            return 8  # 5-15% CAGR
        elif growth_rate_decimal >= Decimal("0"):
            return 2  # 0-5% CAGR
        else:
            return 0  # Negative growth

    def _calculate_growth_rate(self, request: ValuationRequestProtocol) -> Optional[Decimal]:
        """Calculate CAGR from historical + current year data."""
        historical = request.historical_years_data

        if not historical or len(historical) < 1:
            return None

        oldest = oldest_historical_year(historical)
        if oldest is None:
            return None
        oldest_revenue, oldest_year = _revenue_and_year(oldest)
        if oldest_revenue is None:
            return None

        newest_revenue, newest_year = _current_revenue_and_year(request)
        uses_current_year = newest_revenue is not None
        if newest_revenue is None:
            newest = newest_historical_year(historical)
            if newest is None:
                return None
            newest_revenue, newest_year = _revenue_and_year(newest)
        if newest_revenue is None:
            return None

        years = _growth_period_years(
            oldest_year=oldest_year,
            newest_year=newest_year,
            historical_count=len(historical),
            uses_current_year=uses_current_year,
        )
        return _compound_annual_growth_rate(
            oldest_revenue=oldest_revenue,
            newest_revenue=newest_revenue,
            years=years,
        )

    def _score_business_model(self, business_model: str, request: ValuationRequestProtocol) -> int:
        """
        Score business model dimension (0-15 points).

        Some business models are inherently more suitable for DCF.
        """
        score = 0
        valuation_preferences = getattr(request, "valuation_preferences", None) or {}
        primary_model = str(valuation_preferences.get("primary_model") or "").lower()
        preferred_multiples = [
            str(item).upper() for item in (valuation_preferences.get("preferred_multiples") or [])
        ]

        # Check if business model is DCF-friendly (10 points)
        model_hints = " ".join(part for part in [business_model, primary_model] if part)
        if any(model in model_hints for model in BUSINESS_MODELS_DCF_FRIENDLY):
            score += 10

        # If authoritative business-type metadata explicitly prefers DCF-friendly
        # models and does not strongly bias toward revenue multiples, reward it.
        if primary_model in {"subscription", "recurring", "contracted", "license"}:
            score += 3
        if preferred_multiples and preferred_multiples[0] == "EV/REVENUE":
            score = max(score - 2, 0)

        # Additional points for specific characteristics
        # High recurring revenue bonus (5 points)
        if (
            request.recurring_revenue_percentage
            and request.recurring_revenue_percentage >= Decimal("0.7")
        ):
            score += 5
        elif (
            request.recurring_revenue_percentage
            and request.recurring_revenue_percentage >= Decimal("0.5")
        ):
            score += 3

        return min(score, 15)  # Cap at 15

    def _score_recurring_revenue(self, recurring_percentage: Decimal) -> int:
        """
        Score recurring revenue dimension (0-10 points).

        Recurring revenue improves cash flow predictability for DCF.
        """
        recurring_percentage_decimal = to_decimal(recurring_percentage)
        if recurring_percentage_decimal >= Decimal("0.7"):
            return 10
        elif recurring_percentage_decimal >= Decimal("0.5"):
            return 7
        elif recurring_percentage_decimal >= Decimal("0.3"):
            return 5
        else:
            return 2

    def _score_historical_data(self, historical_years: List) -> int:
        """Score historical data dimension (0-5 points)"""
        if not historical_years:
            return 0

        years_count = len(historical_years)

        if years_count >= HISTORICAL_DATA_PREFERRED:
            return 5
        elif years_count >= HISTORICAL_DATA_MINIMUM:
            return 3
        else:
            return 1

    def _build_breakdown(
        self,
        request: ValuationRequestProtocol,
        revenue: Decimal,
        revenue_score: int,
        data_quality_score: int,
        growth_score: int,
        business_model_score: int,
        business_model: str,
        recurring_score: int,
        historical_score: int,
    ) -> dict:
        """Build breakdown dictionary"""
        return {
            "revenue_size": {
                "score": revenue_score,
                "max": 25,
                "revenue": revenue,
            },
            "data_quality": {
                "score": data_quality_score,
                "max": 25,
            },
            "growth_rate": {
                "score": growth_score,
                "max": 20,
            },
            "business_model": {
                "score": business_model_score,
                "max": 15,
                "model": business_model,
            },
            "recurring_revenue": {
                "score": recurring_score,
                "max": 10,
                "percentage": request.recurring_revenue_percentage,
            },
            "historical_data": {
                "score": historical_score,
                "max": 5,
                "years": len(
                    [
                        year
                        for year in (request.historical_years_data or [])
                        if not getattr(year, "is_forecast", False)
                    ]
                ),
            },
        }

    def _check_exclusion_criteria(self, request: ValuationRequestProtocol) -> Optional[str]:
        """
        Check if DCF should be excluded entirely.

        Exclusion criteria:
        - Revenue < €100K (micro-businesses)
        - Sole trader (owner-dependent)
        """
        revenue = request.current_year_data.revenue or Decimal("0")

        revenue_decimal = to_decimal(revenue)
        revenue_micro_decimal = to_decimal(REVENUE_MICRO)
        if revenue_decimal < revenue_micro_decimal:
            return f"Revenue €{revenue_decimal:,.0f} below €100K threshold (DCF not reliable for micro-businesses)"

        # Check sole trader
        if request.is_sole_trader:
            return "Sole trader (owner-dependent)"

        # No other hard exclusions - let scoring determine suitability
        return None

    def _explain_revenue_score(self, revenue: Decimal, score: int) -> str:
        """Generate explanation for revenue size score."""
        if score == 0:
            return f"Revenue €{revenue:,.0f} below €100K threshold (DCF not suitable)"
        elif score <= 5:
            return f"Revenue €{revenue:,.0f} is very small (€100K-€500K), limited DCF suitability"
        elif score <= 12:
            return f"Revenue €{revenue:,.0f} is small (€500K-€2M), moderate DCF suitability"
        elif score <= 18:
            return f"Revenue €{revenue:,.0f} is medium (€2M-€10M), good DCF suitability"
        else:
            return f"Revenue €{revenue:,.0f} is large (≥€10M), excellent DCF suitability"

    def _explain_data_quality_score(self, request: ValuationRequestProtocol, score: int) -> str:
        """Generate explanation for data quality score."""
        if score <= 5:
            return "Limited data quality - only current year data available"
        elif score <= 10:
            return "Fair data quality - basic financial data available"
        elif score <= 20:
            return "Good data quality - comprehensive financial data with some historical data"
        else:
            return "Excellent data quality - comprehensive financial data with consistent historical profitability"

    def _explain_growth_score(self, request: ValuationRequestProtocol, score: int) -> str:
        """Generate explanation for growth rate score."""
        growth_rate = self._calculate_growth_rate(request)
        if growth_rate is None:
            return "No historical data available - assuming moderate growth"
        elif score >= 20:
            return f"High growth rate ({growth_rate*100:.1f}% CAGR) - excellent for DCF"
        elif score >= 15:
            return f"Moderate-high growth rate ({growth_rate*100:.1f}% CAGR) - good for DCF"
        elif score >= 8:
            return f"Moderate growth rate ({growth_rate*100:.1f}% CAGR) - fair for DCF"
        elif score >= 2:
            return f"Low growth rate ({growth_rate*100:.1f}% CAGR) - limited DCF suitability"
        else:
            return f"Negative growth rate ({growth_rate*100:.1f}% CAGR) - poor DCF suitability"

    def _explain_business_model_score(self, business_model: str, score: int) -> str:
        """Generate explanation for business model score."""
        if score >= 15:
            return (
                f"Highly DCF-friendly business model ({business_model}) with high recurring revenue"
            )
        elif score >= 10:
            return f"DCF-friendly business model ({business_model})"
        elif score >= 3:
            return f"Somewhat DCF-friendly business model ({business_model}) with moderate recurring revenue"
        else:
            return f"Traditional business model ({business_model}) - less suitable for DCF"

    def _explain_recurring_score(self, recurring_percentage: Decimal, score: int) -> str:
        """Generate explanation for recurring revenue score."""
        pct = recurring_percentage * Decimal("100")
        if score >= 10:
            return f"High recurring revenue ({pct:.0f}%) - excellent cash flow predictability"
        elif score >= 7:
            return f"Good recurring revenue ({pct:.0f}%) - good cash flow predictability"
        elif score >= 5:
            return f"Moderate recurring revenue ({pct:.0f}%) - fair cash flow predictability"
        else:
            return f"Low recurring revenue ({pct:.0f}%) - limited cash flow predictability"

    def _explain_historical_score(self, years_count: int, score: int) -> str:
        """Generate explanation for historical data score."""
        if score >= 5:
            return f"Excellent historical data ({years_count} years) - strong foundation for DCF"
        elif score >= 3:
            return f"Good historical data ({years_count} years) - adequate for DCF"
        elif score >= 1:
            return f"Limited historical data ({years_count} years) - less reliable for DCF"
        else:
            return "No historical data - reduces DCF reliability"
