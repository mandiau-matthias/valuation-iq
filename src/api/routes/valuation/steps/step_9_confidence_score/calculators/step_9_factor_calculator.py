"""
Step 9 Factor Calculator

Calculates all 8 confidence factors for Step 9.
"""

import math
from decimal import Decimal
from typing import Any, Dict, Optional

from src.api.routes.valuation.shared.historical_years import oldest_historical_year
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class Step9FactorCalculator:
    """Calculates all 8 confidence factors."""

    def calculate_all_factors(
        self,
        request: any,
        step0: Dict[str, Any],
        step1: Dict[str, Any],
        step2: Dict[str, Any],
        equity_result: Dict[str, Any],
    ) -> Dict[str, int]:
        """
        Calculate all 8 confidence factors using real data from previous steps.

        Args:
            request: Valuation request
            step0: Step 0 result dictionary
            step1: Step 1 result dictionary
            step2: Step 2 result dictionary
            equity_result: Equity result dictionary (from Step 7 or 8)

        Returns:
            Dictionary with all 8 factor scores
        """
        # Factor 1: Data Quality (from Step 0) - Enhanced with dimension scores
        data_quality = step0.get("quality_score", 50)

        # Adjust data quality based on dimension scores and warnings
        dimension_scores = step0.get("dimension_scores", {})
        warnings = step0.get("warnings", [])

        # Apply penalty for critical/high severity warnings
        critical_warnings = [w for w in warnings if w.get("severity") == "critical"]
        high_warnings = [w for w in warnings if w.get("severity") == "high"]

        # Reduce data quality factor if there are critical issues
        if critical_warnings:
            data_quality = max(0, data_quality - len(critical_warnings) * 10)
        if high_warnings:
            data_quality = max(0, data_quality - len(high_warnings) * 5)

        # Factor 2: Historical Data
        historical_data = self._calculate_historical_data(request)

        # Factor 3: Methodology Agreement
        methodology_agreement = self._calculate_methodology_agreement(step2, equity_result)

        # Factor 4: Industry Benchmarks
        industry_benchmarks = self._calculate_industry_benchmarks(step2)

        # Factor 5: Company Profile
        ebitda_margin = step1.get("ebitda_margin", 0) or 0
        revenue = step1.get("revenue", 0) or 0
        growth_rate = self._calculate_growth_rate(request, revenue)
        company_profile = self._calculate_company_profile(ebitda_margin, revenue, growth_rate)

        # Factor 6: Market Conditions
        market_conditions = self._calculate_market_conditions(step2, request)

        # Factor 7: Geographic Data
        geographic_data = self._calculate_geographic_data(request)

        # Factor 8: Business Model Clarity
        business_model_clarity = self._calculate_business_model_clarity(request, step2)

        return {
            "data_quality": data_quality,
            "historical_data": historical_data,
            "methodology_agreement": methodology_agreement,
            "industry_benchmarks": industry_benchmarks,
            "company_profile": company_profile,
            "market_conditions": market_conditions,
            "geographic_data": geographic_data,
            "business_model_clarity": business_model_clarity,
        }

    def _calculate_historical_data(self, request: any) -> int:
        """
        Calculate historical data factor based on years of historical data available.

        Args:
            request: Valuation request

        Returns:
            Historical data score (0-100)
        """
        historical_years = getattr(request, "historical_years_data", None) or getattr(
            request, "historical_years", []
        )
        if historical_years is None:
            historical_years = []
        historical_count = len(historical_years) if isinstance(historical_years, list) else 0

        if historical_count >= 5:
            return 100
        elif historical_count >= 3:
            return 80
        elif historical_count >= 2:
            return 60
        elif historical_count >= 1:
            return 50
        else:
            return 20

    def _calculate_methodology_agreement(
        self, step2: Dict[str, Any], equity_result: Dict[str, Any]
    ) -> int:
        """
        Calculate methodology agreement score based on DCF vs Multiples alignment.

        Args:
            step2: Step 2 result dictionary
            equity_result: Equity result dictionary

        Returns:
            Methodology agreement score (0-100)
        """
        if not step2:
            return 70  # Default moderate agreement

        recommended_methodology = step2.get("recommended_methodology", "multiples_only")
        dcf_suitability_score = step2.get("dcf_suitability_score", 0)

        # If only one methodology used, agreement is based on methodology decision confidence
        if recommended_methodology == "multiples_only":
            # Multiples only - high confidence if data quality is good
            if dcf_suitability_score < 40:
                return 85  # High confidence in multiples-only decision
            else:
                return 70  # Moderate confidence
        elif recommended_methodology in ["hybrid_multiples_primary", "hybrid_dcf_primary"]:
            # Hybrid approach - check if both methodologies agree
            if dcf_suitability_score >= 70:
                return 80  # High confidence in hybrid decision
            elif dcf_suitability_score >= 40:
                return 70  # Moderate confidence
            else:
                return 60  # Lower confidence
        else:
            return 70  # Default moderate agreement

    def _calculate_industry_benchmarks(self, step2: Dict[str, Any]) -> int:
        """
        Calculate industry benchmarks score based on comparables availability.

        Args:
            step2: Step 2 result dictionary

        Returns:
            Industry benchmarks score (0-100)
        """
        if not step2:
            return 75  # Default moderate benchmark availability

        comparables_found_raw = step2.get("comparables_found", 0)
        # Ensure comparables_found is an integer (handle string conversion if needed)
        try:
            comparables_found = (
                int(comparables_found_raw) if comparables_found_raw is not None else 0
            )
        except (ValueError, TypeError):
            comparables_found = 0

        sufficient_comparables = step2.get("sufficient_comparables", False)
        data_source = step2.get("data_source", "default")

        # Check for placeholder comparables
        comparables_list = step2.get("comparables", [])
        has_placeholders = False
        if comparables_list:
            placeholder_patterns = [
                "placeholder",
                "sample",
                "demo",
                "test",
                "example",
                "n/a",
                "unknown",
                "xxx",
            ]

            for comp in comparables_list:
                comp_name = (
                    comp.get("name", "").lower() if isinstance(comp, dict) else str(comp).lower()
                )
                comp_ticker = comp.get("ticker", "").lower() if isinstance(comp, dict) else ""

                if any(
                    pattern in comp_name or pattern in comp_ticker
                    for pattern in placeholder_patterns
                ):
                    has_placeholders = True
                    logger.debug(
                        "Placeholder comparable detected",
                        extra={
                            "step_number": 9,
                            "comp_name": comp_name,
                            "comp_ticker": comp_ticker,
                        },
                    )
                    break

        # Score based on comparables count
        if sufficient_comparables and comparables_found >= 10:
            base_score = 95  # Excellent: 10+ comparables
        elif sufficient_comparables and comparables_found >= 5:
            base_score = 85  # Good: 5-9 comparables
        elif comparables_found >= 3:
            base_score = 60  # 3-4 comparables (insufficient)
        elif comparables_found >= 1:
            base_score = 40  # 1-2 comparables (very limited)
        else:
            # No comparables, but check data source quality
            if data_source in ["fmp_api", "cache"]:
                base_score = 50  # Market data available but no comparables found
            elif data_source == "db":
                base_score = 45  # Database multiples available but no comparables
            else:
                base_score = 30  # Default/fallback multiples, no comparables

        # Additional penalty for placeholder comparables
        if has_placeholders:
            base_score = max(20, base_score - 20)  # Penalize by 20 points, minimum 20
            logger.warning(
                "⚠️ Step 9: Placeholder comparables detected - reducing industry benchmarks score",
                extra={
                    "step_number": 9,
                    "comparables_found": comparables_found,
                    "has_placeholders": True,
                    "adjusted_score": base_score,
                },
            )

        return base_score

    def _calculate_company_profile(
        self, ebitda_margin: Decimal, revenue: Decimal, growth_rate: Optional[Decimal]
    ) -> int:
        """
        Calculate company profile score based on profitability, size, and growth.

        Args:
            ebitda_margin: EBITDA margin percentage
            revenue: Revenue value
            growth_rate: Growth rate (optional)

        Returns:
            Company profile score (0-100)
        """
        score = 50  # Base score

        # Profitability component (0-40 points)
        if ebitda_margin > 20:
            score += 40
        elif ebitda_margin > 15:
            score += 30
        elif ebitda_margin > 10:
            score += 20
        elif ebitda_margin > 5:
            score += 10
        elif ebitda_margin > 0:
            score += 5
        else:
            score += 0  # Negative EBITDA reduces confidence

        # Size component (0-30 points)
        if revenue >= 10_000_000:
            score += 30
        elif revenue >= 5_000_000:
            score += 20
        elif revenue >= 1_000_000:
            score += 10
        else:
            score += 0

        # Growth component (0-20 points)
        if growth_rate is not None:
            if growth_rate > Decimal("0.25"):
                score += 20  # High growth
            elif growth_rate > Decimal("0.15"):
                score += 15  # Moderate-high growth
            elif growth_rate > Decimal("0.05"):
                score += 10  # Moderate growth
            elif growth_rate > 0:
                score += 5  # Low growth
            else:
                score += 0  # Declining

        return min(100, max(0, score))

    def _calculate_growth_rate(self, request: any, revenue: Decimal) -> Optional[Decimal]:
        """
        Calculate growth rate from historical data.

        Args:
            request: Valuation request
            revenue: Current revenue

        Returns:
            Growth rate or None if not calculable
        """
        historical_years = getattr(request, "historical_years_data", None) or getattr(
            request, "historical_years", []
        )
        if historical_years is None:
            historical_years = []
        historical_count = len(historical_years) if isinstance(historical_years, list) else 0

        if historical_count < 2:
            return None

        try:
            oldest_year = oldest_historical_year(historical_years)
            if oldest_year is None:
                return None
            first_revenue = (
                oldest_year.revenue
                if hasattr(oldest_year, "revenue")
                else oldest_year.get("revenue", 0)
            )
            if first_revenue > 0 and revenue > 0 and historical_count > 0:
                first_year = (
                    getattr(oldest_year, "year", None)
                    if hasattr(oldest_year, "year")
                    else oldest_year.get("year") if isinstance(oldest_year, dict) else None
                )
                current_year_data = getattr(request, "current_year_data", None)
                current_year = (
                    getattr(current_year_data, "year", None) if current_year_data else None
                )
                periods = (
                    (current_year - first_year)
                    if (first_year and current_year and current_year > first_year)
                    else historical_count
                )
                growth_rate = ((revenue / first_revenue) ** (Decimal("1.0") / periods)) - 1
                growth_rate_f = float(growth_rate)
                if not math.isfinite(growth_rate_f):
                    logger.warning(
                        "⚠️ Growth rate calculation produced invalid result (NaN/Infinity), setting to None",
                        extra={
                            "step_number": 9,
                            "first_revenue": first_revenue,
                            "revenue": revenue,
                            "historical_count": historical_count,
                        },
                    )
                    return None
                return growth_rate
        except (AttributeError, KeyError, ZeroDivisionError, OverflowError) as e:
            logger.warning(
                "⚠️ Growth rate calculation failed",
                extra={"step_number": 9, "error": str(e), "historical_count": historical_count},
            )
            return None

        return None

    def _calculate_market_conditions(self, step2: Dict[str, Any], request: any) -> int:
        """
        Calculate market conditions score.

        Args:
            step2: Step 2 result dictionary
            request: Valuation request

        Returns:
            Market conditions score (0-100)
        """
        if step2:
            data_source = step2.get("data_source", "default")
            if data_source in ["fmp_api", "cache"]:
                return 80  # Market data available - assume stable conditions
            elif data_source == "db":
                return 75  # Database data - assume normal conditions
            else:
                return 70  # Default/fallback - assume moderate uncertainty
        else:
            return 70  # No market data - assume moderate uncertainty

    def _calculate_geographic_data(self, request: any) -> int:
        """
        Calculate geographic data score based on country-specific data availability.

        Args:
            request: Valuation request

        Returns:
            Geographic data score (0-100)
        """
        country = getattr(request, "country", None) or getattr(request, "country_code", None)

        # Countries with excellent data availability
        excellent_data_countries = ["US", "GB", "DE", "FR", "NL", "BE", "CH", "AT"]
        # Countries with good data availability
        good_data_countries = ["IT", "ES", "SE", "DK", "NO", "FI", "IE", "PL"]

        if country:
            country_upper = str(country).upper()
            if country_upper in excellent_data_countries:
                return 95
            elif country_upper in good_data_countries:
                return 85
            else:
                return 75  # Other countries - moderate data availability
        else:
            return 70  # Unknown country - default moderate score

    def _calculate_business_model_clarity(self, request: any, step2: Dict[str, Any]) -> int:
        """
        Calculate business model clarity score.

        Args:
            request: Valuation request
            step2: Step 2 result dictionary

        Returns:
            Business model clarity score (0-100)
        """
        score = 70  # Base score

        # Check business type category from Step 2
        if step2:
            business_type_category = step2.get("business_type_category")
            if business_type_category in [
                "saas_software",
                "professional_services",
                "manufacturing",
                "retail",
            ]:
                score += 15  # Well-standardized categories
            elif business_type_category:
                score += 10  # Standard category
            else:
                score += 5  # Unknown category

        # Check business model
        business_model = getattr(request, "business_model", None)
        if business_model:
            standard_models = [
                "saas",
                "software",
                "subscription",
                "ecommerce",
                "manufacturing",
                "retail",
                "services",
            ]
            if any(model in str(business_model).lower() for model in standard_models):
                score += 10
            else:
                score += 5

        # Check industry
        industry = getattr(request, "industry", None)
        if industry:
            standard_industries = [
                "technology",
                "professional-services",
                "manufacturing",
                "retail",
                "healthcare",
            ]
            if any(ind in str(industry).lower() for ind in standard_industries):
                score += 5

        return min(100, max(0, score))
