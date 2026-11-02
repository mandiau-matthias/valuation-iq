from src.utils.exceptions import BusinessTypeError, DataValidationError, MethodologyError, MissingDataError

"""
Insight Generator

This module handles deterministic insight generation and analysis for valuation
reports, including valuation calculations and strategic recommendations.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .report_types import (
    ValuationInsight, InsightCategory, ImpactLevel, ValuationMethodology,
    ValuationCalculationResult, InsightGenerationResult, VALUATION_METHODOLOGIES
)

logger = get_logger(__name__)


class InsightGenerator:
    """
    Deterministic insight generation service for valuation reports

    Handles:
    - Generate valuation insights
    - Calculate valuations using multiple methodologies
    - Generate executive summaries
    - Generate strategic recommendations
    - Assess confidence levels
    """

    def __init__(self, legacy_model_proxy=None, **legacy_kwargs: Any):
        """Initialize the insight generator"""
        self.logger = logger
        if legacy_model_proxy is None:
            legacy_model_proxy = next(
                (
                    value
                    for key, value in legacy_kwargs.items()
                    if key.endswith("_proxy")
                ),
                None,
            )
        if legacy_model_proxy is not None:
            self.logger.warning(
                "Ignoring legacy reporting model proxy; Titan owns external LLM egress"
            )

        self.logger.info("InsightGenerator initialized")

    async def calculate_valuation(
        self,
        revenue: Optional[Decimal],
        ebitda: Optional[Decimal],
        industry: str,
        business_type: str,
        employee_count: str
    ) -> ValuationCalculationResult:
        """
        Calculate valuation using appropriate methodology

        Args:
            revenue: Company revenue
            ebitda: Company EBITDA
            industry: Industry sector
            business_type: Type of business
            employee_count: Number of employees

        Returns:
            ValuationCalculationResult with calculation details
        """
        try:
            self.logger.info("Calculating valuation", revenue=revenue, ebitda=ebitda, industry=industry)

            if not revenue or revenue <= 0:
                return ValuationCalculationResult(
                    estimated_value={"min": 0, "max": 0, "most_likely": 0},
                    methodology=ValuationMethodology.INSUFFICIENT_DATA.value,
                    confidence_score=Decimal('0.0'),
                    assumptions=["Revenue data required for valuation"],
                    limitations=["Cannot calculate valuation without revenue data"]
                )

            # Determine methodology
            if ebitda and ebitda > 0:
                methodology = ValuationMethodology.EBITDA_MULTIPLE
                multipliers = VALUATION_METHODOLOGIES[methodology].multipliers
            else:
                methodology = ValuationMethodology.REVENUE_MULTIPLE
                multipliers = VALUATION_METHODOLOGIES[methodology].multipliers

            # Get industry multipliers
            industry_multipliers = multipliers.get(industry, multipliers.get("services", {"min": Decimal('2.0'), "max": Decimal('3.5'), "typical": 2.7}))

            # Calculate valuation range
            if methodology == ValuationMethodology.EBITDA_MULTIPLE:
                min_value = ebitda * industry_multipliers["min"]
                max_value = ebitda * industry_multipliers["max"]
                most_likely = ebitda * industry_multipliers["typical"]
            else:  # Revenue multiple
                min_value = revenue * industry_multipliers["min"]
                max_value = revenue * industry_multipliers["max"]
                most_likely = revenue * industry_multipliers["typical"]

            # Calculate confidence score
            confidence_score = self._calculate_valuation_confidence(
                revenue, ebitda, industry, business_type, employee_count
            )

            # Generate assumptions and limitations
            assumptions = self._generate_assumptions(methodology, industry, revenue, ebitda)
            limitations = self._generate_limitations(methodology, industry, revenue, ebitda)

            result = ValuationCalculationResult(
                estimated_value={
                    "min": min_value,
                    "max": max_value,
                    "most_likely": most_likely
                },
                methodology=methodology.value,
                confidence_score=confidence_score,
                assumptions=assumptions,
                limitations=limitations,
                calculation_details={
                    "industry_multipliers": industry_multipliers,
                    "base_metric": "ebitda" if methodology == ValuationMethodology.EBITDA_MULTIPLE else "revenue",
                    "base_value": ebitda if methodology == ValuationMethodology.EBITDA_MULTIPLE else revenue
                }
            )

            self.logger.info(
                "Valuation calculated",
                methodology=methodology.value,
                estimated_value=most_likely,
                confidence=f"{confidence_score:.2%}"
            )

            return result

        except MethodologyError as e:
            self.logger.error(f"Valuation calculation failed: {e}")
            raise

    async def generate_insights(
        self,
        collected_data: Dict[str, Any],
        valuation_result: ValuationCalculationResult,
        conversation_data: Dict[str, Any]
    ) -> List[ValuationInsight]:
        """
        Generate deterministic valuation insights

        Args:
            collected_data: Collected data from conversation
            valuation_result: Valuation calculation result
            conversation_data: Raw conversation data

        Returns:
            List of valuation insights
        """
        try:
            self.logger.info("Generating deterministic insights")

            insights = []

            # Generate insights based on data quality
            if valuation_result.confidence_score < 0.5:
                insights.append(ValuationInsight(
                    category=InsightCategory.CONCERN,
                    title="Data Quality Concerns",
                    description="Limited financial data available may affect valuation accuracy",
                    impact=ImpactLevel.HIGH,
                    confidence=Decimal('0.9')
                ))

            # Generate insights based on industry
            industry_insights = self._generate_industry_insights(
                collected_data.get("industry", "unknown"),
                valuation_result
            )
            insights.extend(industry_insights)

            # Generate insights based on business metrics
            metrics_insights = self._generate_metrics_insights(collected_data, valuation_result)
            insights.extend(metrics_insights)

            # Limit number of insights
            insights = insights[:10]  # Max 10 insights

            self.logger.info(f"Generated {len(insights)} insights")
            return insights

        except ValuationEngineError as e:
            self.logger.error(f"Insight generation failed: {e}")
            return []

    async def generate_executive_summary(
        self,
        company_name: str,
        collected_data: Dict[str, Any],
        valuation_result: ValuationCalculationResult,
        insights: List[ValuationInsight]
    ) -> str:
        """
        Generate deterministic executive summary

        Args:
            company_name: Company name
            collected_data: Collected data
            valuation_result: Valuation result
            insights: Generated insights

        Returns:
            Executive summary string
        """
        try:
            self.logger.info("Generating executive summary")

            return self._generate_rule_based_summary(
                company_name, collected_data, valuation_result, insights
            )

        except DataValidationError as e:
            self.logger.error(f"Executive summary generation failed: {e}")
            return f"Executive summary generation failed: {e}"

    async def generate_recommendations(
        self,
        collected_data: Dict[str, Any],
        insights: List[ValuationInsight]
    ) -> List[str]:
        """
        Generate strategic recommendations

        Args:
            collected_data: Collected data
            insights: Generated insights

        Returns:
            List of strategic recommendations
        """
        try:
            self.logger.info("Generating strategic recommendations")

            recommendations = []

            # Generate recommendations based on insights
            for insight in insights:
                if insight.category == InsightCategory.CONCERN:
                    recommendations.append(f"Address {insight.title.lower()}: {insight.description}")
                elif insight.category == InsightCategory.OPPORTUNITY:
                    recommendations.append(f"Leverage {insight.title.lower()}: {insight.description}")

            # Limit number of recommendations
            recommendations = recommendations[:5]  # Max 5 recommendations

            self.logger.info(f"Generated {len(recommendations)} recommendations")
            return recommendations

        except BusinessTypeError as e:
            self.logger.error(f"Recommendation generation failed: {e}")
            return []

    def _calculate_valuation_confidence(
        self,
        revenue: Optional[Decimal],
        ebitda: Optional[Decimal],
        industry: str,
        business_type: str,
        employee_count: str
    ) -> Decimal:
        """Calculate confidence score for valuation"""
        confidence = Decimal('0.0')

        # Revenue confidence
        if revenue and revenue > 0:
            confidence += Decimal('0.3')

        # EBITDA confidence
        if ebitda and ebitda > 0:
            confidence += Decimal('0.3')

        # Industry confidence
        if industry and industry != "unknown":
            confidence += Decimal('0.2')

        # Business type confidence
        if business_type and business_type != "unknown":
            confidence += Decimal('0.1')

        # Employee count confidence
        if employee_count and employee_count != "unknown":
            confidence += Decimal('0.1')

        return min(Decimal('1.0'), confidence)

    def _generate_assumptions(
        self,
        methodology: ValuationMethodology,
        industry: str,
        revenue: Optional[Decimal],
        ebitda: Optional[Decimal]
    ) -> List[str]:
        """Generate valuation assumptions"""
        assumptions = []

        if methodology == ValuationMethodology.EBITDA_MULTIPLE:
            assumptions.append(f"EBITDA multiple based on {industry} industry benchmarks")
            assumptions.append("Current EBITDA represents sustainable profitability")
        else:
            assumptions.append(f"Revenue multiple based on {industry} industry benchmarks")
            assumptions.append("Current revenue represents sustainable business performance")

        assumptions.append("Market conditions remain stable")
        assumptions.append("Industry benchmarks are applicable to this business")

        return assumptions

    def _generate_limitations(
        self,
        methodology: ValuationMethodology,
        industry: str,
        revenue: Optional[Decimal],
        ebitda: Optional[Decimal]
    ) -> List[str]:
        """Generate valuation limitations"""
        limitations = []

        limitations.append("Valuation is based on limited financial data")
        limitations.append("Industry benchmarks may not reflect unique business characteristics")
        limitations.append("Market conditions can change rapidly")

        if not ebitda or ebitda <= 0:
            limitations.append("EBITDA data not available for more accurate valuation")

        return limitations

    def _generate_industry_insights(
        self,
        industry: str,
        valuation_result: ValuationCalculationResult
    ) -> List[ValuationInsight]:
        """Generate industry-specific insights"""
        insights = []

        if industry == "technology":
            insights.append(ValuationInsight(
                category=InsightCategory.STRENGTH,
                title="Technology Sector Growth",
                description="Technology companies typically command higher valuations due to growth potential",
                impact=ImpactLevel.MEDIUM,
                confidence=Decimal('0.8')
            ))
        elif industry == "manufacturing":
            insights.append(ValuationInsight(
                category=InsightCategory.CONCERN,
                title="Manufacturing Volatility",
                description="Manufacturing businesses may face economic cycle sensitivity",
                impact=ImpactLevel.MEDIUM,
                confidence=Decimal('0.7')
            ))

        return insights

    def _generate_metrics_insights(
        self,
        collected_data: Dict[str, Any],
        valuation_result: ValuationCalculationResult
    ) -> List[ValuationInsight]:
        """Generate insights based on business metrics"""
        insights = []

        revenue = collected_data.get("revenue")
        ebitda = collected_data.get("ebitda")

        if revenue and ebitda:
            profit_margin = (ebitda / revenue) * 100
            if profit_margin > 20:
                insights.append(ValuationInsight(
                    category=InsightCategory.STRENGTH,
                    title="High Profitability",
                    description=f"Strong profit margin of {profit_margin:.1f}% indicates efficient operations",
                    impact=ImpactLevel.HIGH,
                    confidence=Decimal('0.9')
                ))
            elif profit_margin < 5:
                insights.append(ValuationInsight(
                    category=InsightCategory.CONCERN,
                    title="Low Profitability",
                    description=f"Low profit margin of {profit_margin:.1f}% may indicate operational challenges",
                    impact=ImpactLevel.HIGH,
                    confidence=Decimal('0.8')
                ))

        return insights

    async def _generate_titan_owned_insights_placeholder(
        self,
        collected_data: Dict[str, Any],
        valuation_result: ValuationCalculationResult,
        conversation_data: Dict[str, Any]
    ) -> List[ValuationInsight]:
        """Placeholder retained for old tests; external narrative belongs in Titan."""
        try:
            return []

        except MissingDataError as e:
            self.logger.error(f"Titan-owned insight placeholder failed: {e}")
            return []

    async def _generate_titan_owned_executive_summary_placeholder(
        self,
        company_name: str,
        collected_data: Dict[str, Any],
        valuation_result: ValuationCalculationResult,
        insights: List[ValuationInsight]
    ) -> str:
        """Placeholder retained for old tests; external narrative belongs in Titan."""
        try:
            return self._generate_rule_based_summary(
                company_name, collected_data, valuation_result, insights
            )

        except DataValidationError as e:
            self.logger.error(f"Titan-owned executive summary placeholder failed: {e}")
            return f"Executive summary generation failed: {e}"

    def _generate_rule_based_summary(
        self,
        company_name: str,
        collected_data: Dict[str, Any],
        valuation_result: ValuationCalculationResult,
        insights: List[ValuationInsight]
    ) -> str:
        """Generate rule-based executive summary"""
        summary_parts = []

        # Company introduction
        summary_parts.append(f"{company_name} has been valued at €{valuation_result.estimated_value['most_likely']:,.0f}")

        # Valuation range
        min_val = valuation_result.estimated_value['min']
        max_val = valuation_result.estimated_value['max']
        summary_parts.append(f"with a valuation range of €{min_val:,.0f} to €{max_val:,.0f}")

        # Methodology
        summary_parts.append(f"using the {valuation_result.methodology.replace('_', ' ').title()} methodology")

        # Confidence
        confidence_pct = valuation_result.confidence_score * 100
        summary_parts.append(f"with a confidence level of {confidence_pct:.0f}%")

        # Key insights
        high_impact_insights = [i for i in insights if i.impact == ImpactLevel.HIGH]
        if high_impact_insights:
            summary_parts.append(f"Key considerations include {high_impact_insights[0].title.lower()}")

        return ". ".join(summary_parts) + "."

    async def _generate_titan_owned_recommendations_placeholder(
        self,
        collected_data: Dict[str, Any],
        insights: List[ValuationInsight]
    ) -> List[str]:
        """Placeholder retained for old tests; external narrative belongs in Titan."""
        try:
            return []

        except MissingDataError as e:
            self.logger.error(f"Titan-owned recommendation placeholder failed: {e}")
            return []
