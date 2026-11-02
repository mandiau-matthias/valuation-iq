"""
Valuation Quality Scoring Service

Implements ML-powered quality scoring for valuations based on:
- Data completeness
- Financial health indicators
- Market context relevance
- Historical pattern matching confidence

Author: Upswitch Engineering Team
Date: October 2025
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal
import structlog

from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal, from_decimal, bank_round

from src.utils.exceptions import (
    CalculationError,
    ValidationError,
    DataQualityError
)
# Built-in exceptions don't need to be imported from src.errors

logger = get_logger(__name__)


class ValuationQualityScorer:
    """
    Quality scoring system for valuation assessments

    Provides confidence scoring based on multiple quality dimensions.
    """

    # Scoring weights
    WEIGHT_DATA_COMPLETENESS = Decimal('0.30')
    WEIGHT_FINANCIAL_HEALTH = Decimal('0.25')
    WEIGHT_MARKET_CONTEXT = Decimal('0.20')
    WEIGHT_HISTORICAL_MATCH = Decimal('0.15')
    WEIGHT_METHODOLOGY_FIT = Decimal('0.10')

    def __init__(self):
        """Initialize quality scorer"""
        logger.info("✅ ValuationQualityScorer initialized")

    @staticmethod
    def _chronological_historical_years(historical_years: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return historical-year dictionaries sorted oldest to newest when year is available."""
        return sorted(historical_years or [], key=lambda year: year.get("year") or 0)

    def calculate_quality_score(
        self,
        valuation_data: Dict[str, Any],
        mcp_patterns: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive quality score for valuation

        Args:
            valuation_data: Valuation request and result data
            mcp_patterns: Optional MCP pattern analysis results

        Returns:
            Quality score breakdown
        """
        try:
            # 1. Data Completeness Score (0-100)
            data_score = self._score_data_completeness(valuation_data)

            # 2. Financial Health Score (0-100)
            financial_score = self._score_financial_health(valuation_data)

            # 3. Market Context Score (0-100)
            market_score = self._score_market_context(valuation_data)

            # 4. Historical Pattern Match Score (0-100)
            pattern_score = self._score_pattern_match(valuation_data, mcp_patterns)

            # 5. Methodology Fit Score (0-100)
            methodology_score = self._score_methodology_fit(valuation_data)

            # Convert scores to Decimal for calculations
            data_score_decimal = to_decimal(data_score)
            financial_score_decimal = to_decimal(financial_score)
            market_score_decimal = to_decimal(market_score)
            pattern_score_decimal = to_decimal(pattern_score)
            methodology_score_decimal = to_decimal(methodology_score)
            
            # Calculate weighted overall score
            overall_score_decimal = (
                data_score_decimal * self.WEIGHT_DATA_COMPLETENESS +
                financial_score_decimal * self.WEIGHT_FINANCIAL_HEALTH +
                market_score_decimal * self.WEIGHT_MARKET_CONTEXT +
                pattern_score_decimal * self.WEIGHT_HISTORICAL_MATCH +
                methodology_score_decimal * self.WEIGHT_METHODOLOGY_FIT
            )
            overall_score = from_decimal(bank_round(overall_score_decimal, 1))

            # Categorize quality level
            quality_level = self._categorize_quality(overall_score)

            result = {
                "overall_score": from_decimal(bank_round(overall_score_decimal, 1)),
                "quality_level": quality_level,
                "dimension_scores": {
                    "data_completeness": from_decimal(bank_round(data_score_decimal, 1)),
                    "financial_health": from_decimal(bank_round(financial_score_decimal, 1)),
                    "market_context": from_decimal(bank_round(market_score_decimal, 1)),
                    "historical_match": from_decimal(bank_round(pattern_score_decimal, 1)),
                    "methodology_fit": from_decimal(bank_round(methodology_score_decimal, 1))
                },
                "strengths": self._identify_strengths(
                    from_decimal(data_score_decimal), from_decimal(financial_score_decimal), 
                    from_decimal(market_score_decimal), from_decimal(pattern_score_decimal), 
                    from_decimal(methodology_score_decimal)
                ),
                "improvement_areas": self._identify_improvements(
                    from_decimal(data_score_decimal), from_decimal(financial_score_decimal), 
                    from_decimal(market_score_decimal), from_decimal(pattern_score_decimal), 
                    from_decimal(methodology_score_decimal)
                ),
                "confidence_impact": self._calculate_confidence_impact(overall_score)
            }

            logger.info(f"✅ Quality score calculated: {from_decimal(overall_score_decimal):.1f} ({quality_level})")
            return result

        except (CalculationError, ValidationError, DataQualityError, ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(f"❌ Quality scoring failed: {e}", extra={'error_type': type(e).__name__}, exc_info=True)
            return {
                "overall_score": Decimal('50.0'),
                "quality_level": "medium",
                "error": str(e),
                "error_type": type(e).__name__
            }

    def _score_data_completeness(self, data: Dict[str, Any]) -> Decimal:
        """Score data completeness (0-100)"""
        score = Decimal('0.0')
        max_score = Decimal('100.0')

        # Required fields (50 points)
        required_fields = ['revenue', 'ebitda', 'industry', 'country_code']
        for field in required_fields:
            if data.get(field):
                score += Decimal('12.5')

        # Historical data (20 points)
        historical_years = data.get('historical_years_data', [])
        if len(historical_years) >= 3:
            score += Decimal('20')
        elif len(historical_years) >= 1:
            score += Decimal('10')

        # Balance sheet data (15 points)
        balance_fields = ['total_assets', 'total_debt', 'cash']
        balance_count = sum(1 for field in balance_fields if data.get('current_year_data', {}).get(field))
        if len(balance_fields) > 0:
            balance_ratio = Decimal(str(balance_count)) / Decimal(str(len(balance_fields)))
            score += balance_ratio * Decimal('15')

        # Optional enrichments (15 points)
        if data.get('number_of_employees'):
            score += Decimal('5')
        recurring_revenue_pct = to_decimal(data.get('recurring_revenue_percentage', 0))
        if recurring_revenue_pct > Decimal('0'):
            score += Decimal('5')
        if data.get('comparables', []):
            score += Decimal('5')

        return min(score, max_score)

    def _score_financial_health(self, data: Dict[str, Any]) -> Decimal:
        """Score financial health indicators (0-100)"""
        score = Decimal('50.0')  # Baseline

        current_data = data.get('current_year_data', {})
        revenue_decimal = to_decimal(current_data.get('revenue', 0))
        ebitda_decimal = to_decimal(current_data.get('ebitda', 0))

        # EBITDA margin assessment (±25 points)
        if revenue_decimal > Decimal('0'):
            ebitda_margin = ebitda_decimal / revenue_decimal
            if ebitda_margin > Decimal('0.25'):
                score += Decimal('25')  # Excellent margin
            elif ebitda_margin > Decimal('0.15'):
                score += Decimal('15')  # Good margin
            elif ebitda_margin > Decimal('0.05'):
                score += Decimal('5')  # Acceptable margin
            elif ebitda_margin < Decimal('0'):
                score -= Decimal('25')  # Negative EBITDA

        # Growth trajectory (±25 points)
        historical_years = self._chronological_historical_years(data.get('historical_years_data', []))
        if len(historical_years) >= 2:
            older_revenue_decimal = to_decimal(historical_years[0].get('revenue', 1))
            if older_revenue_decimal > Decimal('0'):
                growth_rate = (revenue_decimal - older_revenue_decimal) / older_revenue_decimal
            else:
                growth_rate = Decimal('0')

            if growth_rate > Decimal('0.30'):
                score += Decimal('25')  # High growth
            elif growth_rate > Decimal('0.10'):
                score += Decimal('15')  # Good growth
            elif growth_rate > Decimal('0'):
                score += Decimal('5')  # Stable growth
            elif growth_rate < Decimal('-0.20'):
                score -= Decimal('25')  # Declining

        return max(min(score, Decimal('100')), Decimal('0'))

    def _score_market_context(self, data: Dict[str, Any]) -> Decimal:
        """Score market context relevance (0-100)"""
        score = Decimal('60.0')  # Baseline

        # Industry recognition (20 points)
        known_industries = [
            'technology', 'saas', 'ecommerce', 'manufacturing',
            'retail', 'healthcare', 'consulting', 'services'
        ]
        if data.get('industry', '').lower() in known_industries:
            score += Decimal('20')

        # Country market data availability (20 points)
        major_markets = ['BE', 'NL', 'DE', 'FR', 'LU', 'US', 'GB']
        if data.get('country_code') in major_markets:
            score += Decimal('20')

        return min(score, Decimal('100'))

    def _score_pattern_match(
        self,
        data: Dict[str, Any],
        mcp_patterns: Optional[Dict[str, Any]]
    ) -> Decimal:
        """Score historical pattern matching confidence (0-100)"""
        if not mcp_patterns:
            return Decimal('50.0')  # No patterns available

        score = Decimal('50.0')  # Baseline

        # Sample size quality (30 points)
        sample_size = mcp_patterns.get('data_summary', {}).get('total_valuations', 0)
        if sample_size >= 100:
            score += Decimal('30')
        elif sample_size >= 50:
            score += Decimal('20')
        elif sample_size >= 20:
            score += Decimal('10')

        # Industry match (20 points)
        industry = data.get('industry')
        if industry in mcp_patterns.get('industry_patterns', {}):
            score += Decimal('20')

        return min(score, Decimal('100'))

    def _score_methodology_fit(self, data: Dict[str, Any]) -> Decimal:
        """Score methodology appropriateness (0-100)"""
        score = Decimal('70.0')  # Baseline

        # DCF suitability (15 points)
        historical_years = data.get('historical_years_data', [])
        current_data = data.get('current_year_data', {})
        ebitda_decimal = to_decimal(current_data.get('ebitda', 0))

        if len(historical_years) >= 3 and ebitda_decimal > Decimal('0'):
            score += Decimal('15')  # Good for DCF

        # Multiples suitability (15 points)
        revenue_decimal = to_decimal(current_data.get('revenue', 0))
        if data.get('industry') and revenue_decimal > Decimal('0'):
            score += Decimal('15')  # Good for multiples

        return min(score, Decimal('100'))

    def _categorize_quality(self, score: Decimal) -> str:
        """Categorize quality level from score"""
        score_decimal = to_decimal(score)
        if score_decimal >= Decimal('85'):
            return "excellent"
        elif score_decimal >= Decimal('70'):
            return "high"
        elif score_decimal >= Decimal('55'):
            return "medium"
        elif score_decimal >= Decimal('40'):
            return "acceptable"
        else:
            return "low"

    def _identify_strengths(
        self,
        data_score: Decimal,
        financial_score: Decimal,
        market_score: Decimal,
        pattern_score: Decimal,
        methodology_score: Decimal
    ) -> List[str]:
        """Identify valuation strengths"""
        strengths = []
        data_score_decimal = to_decimal(data_score)
        financial_score_decimal = to_decimal(financial_score)
        market_score_decimal = to_decimal(market_score)
        pattern_score_decimal = to_decimal(pattern_score)
        methodology_score_decimal = to_decimal(methodology_score)

        if data_score_decimal >= Decimal('80'):
            strengths.append("Comprehensive financial data provided")
        if financial_score_decimal >= Decimal('75'):
            strengths.append("Strong financial health indicators")
        if market_score_decimal >= Decimal('75'):
            strengths.append("Excellent market context coverage")
        if pattern_score_decimal >= Decimal('75'):
            strengths.append("Strong historical pattern matching")
        if methodology_score_decimal >= Decimal('80'):
            strengths.append("Ideal fit for valuation methodologies")

        return strengths if strengths else ["Standard valuation quality"]

    def _identify_improvements(
        self,
        data_score: Decimal,
        financial_score: Decimal,
        market_score: Decimal,
        pattern_score: Decimal,
        methodology_score: Decimal
    ) -> List[str]:
        """Identify areas for improvement"""
        improvements = []
        data_score_decimal = to_decimal(data_score)
        financial_score_decimal = to_decimal(financial_score)
        market_score_decimal = to_decimal(market_score)
        pattern_score_decimal = to_decimal(pattern_score)
        methodology_score_decimal = to_decimal(methodology_score)

        if data_score_decimal < Decimal('60'):
            improvements.append("Provide more complete financial data (balance sheet, historical years)")
        if financial_score_decimal < Decimal('50'):
            improvements.append("Financial health indicators show concerns (margins, growth)")
        if market_score_decimal < Decimal('60'):
            improvements.append("Limited market context data for this industry/region")
        if pattern_score_decimal < Decimal('50'):
            improvements.append("Limited historical comparables for pattern matching")
        if methodology_score_decimal < Decimal('60'):
            improvements.append("Consider additional valuation methodologies")

        return improvements if improvements else ["No significant improvement areas identified"]

    def _calculate_confidence_impact(self, quality_score: Decimal) -> str:
        """Calculate impact on valuation confidence"""
        quality_score_decimal = to_decimal(quality_score)
        if quality_score_decimal >= Decimal('85'):
            return "+10-15% confidence boost due to excellent data quality"
        elif quality_score_decimal >= Decimal('70'):
            return "+5-10% confidence boost due to high data quality"
        elif quality_score_decimal >= Decimal('55'):
            return "Neutral impact on confidence"
        elif quality_score_decimal >= Decimal('40'):
            return "-5-10% confidence adjustment due to data limitations"
        else:
            return "-10-20% confidence adjustment due to significant data gaps"


# Global service instance
_quality_scorer_instance = None

def get_quality_scorer() -> ValuationQualityScorer:
    """Get or create global quality scorer instance"""
    global _quality_scorer_instance
    if _quality_scorer_instance is None:
        _quality_scorer_instance = ValuationQualityScorer()
    return _quality_scorer_instance
