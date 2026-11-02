from src.utils.exceptions import MethodologyError, ValuationEngineError

"""
Insights Generator for Conversation Report Generator

This module handles insight generation from data, recommendation generation,
confidence score calculation, and adjustment calculations.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from typing import Dict, Any, List, Optional
from src.utils.logging import get_logger
from src.services.reporting.report_types import ValuationInsight, VALUATION_METHODOLOGIES
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


class InsightsGenerator:
    """
    Handles insight generation and business logic for report generation
    """

    def __init__(self):
        """Initialize the insights generator"""
        self.valuation_methodologies = VALUATION_METHODOLOGIES
        logger.info("✅ InsightsGenerator initialized")

    async def calculate_valuation(
        self,
        revenue: Optional[Decimal],
        ebitda: Optional[Decimal],
        industry: str,
        business_type: str,
        employee_count: str
    ) -> Dict[str, Any]:
        """Calculate valuation using appropriate methodology"""

        if revenue is None:
            return {
                "estimated_value": {"min": 0, "max": 0, "most_likely": 0},
                "methodology": "Insufficient data",
                "confidence_score": Decimal('0.0'),
                "assumptions": ["Revenue data required for valuation"],
                "limitations": ["Cannot calculate valuation without revenue data"]
            }

        # Determine methodology
        if ebitda is not None and ebitda > 0:
            methodology = "ebitda_multiple"
            multipliers = self.valuation_methodologies["ebitda_multiple"]["multipliers"]
        else:
            methodology = "revenue_multiple"
            multipliers = self.valuation_methodologies["revenue_multiple"]["multipliers"]

        # Get industry multipliers
        industry_key = industry.lower() if industry else "services"
        industry_multipliers = multipliers.get(industry_key, multipliers["services"])

        # Calculate base valuation
        if methodology == "ebitda_multiple":
            base_value = ebitda * industry_multipliers["typical"]
            min_value = ebitda * industry_multipliers["min"]
            max_value = ebitda * industry_multipliers["max"]
        else:
            base_value = revenue * industry_multipliers["typical"]
            min_value = revenue * industry_multipliers["min"]
            max_value = revenue * industry_multipliers["max"]

        # Adjust for business type and size
        adjustments = self._calculate_adjustments(business_type, employee_count)
        adjusted_value = base_value * adjustments["multiplier"]
        adjusted_min = min_value * adjustments["multiplier"]
        adjusted_max = max_value * adjustments["multiplier"]

        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(
            revenue=revenue,
            ebitda=ebitda,
            industry=industry,
            business_type=business_type
        )

        return {
            "estimated_value": {
                "min": adjusted_min,
                "max": adjusted_max,
                "most_likely": adjusted_value
            },
            "methodology": self.valuation_methodologies[methodology]["description"],
            "confidence_score": confidence_score,
            "assumptions": [
                f"Industry: {industry}",
                f"Business type: {business_type}",
                f"Employee count: {employee_count}",
                f"Using {methodology} methodology"
            ],
            "limitations": [
                "Based on limited financial data",
                "Industry averages may not reflect specific company circumstances",
                "Market conditions not considered",
                "Professional appraisal recommended for accuracy"
            ]
        }

    def _calculate_adjustments(self, business_type: str, employee_count: str) -> Dict[str, Decimal]:
        """Calculate adjustments based on business characteristics"""
        multiplier = Decimal('1.0')

        # Business type adjustments
        if business_type.lower() in ["sole proprietorship", "sole proprietor"]:
            multiplier *= Decimal('0.8')  # Discount for sole proprietor
        elif business_type.lower() in ["corporation", "llc"]:
            multiplier *= Decimal('1.1')  # Premium for formal structure

        # Employee count adjustments
        if employee_count == "1":
            multiplier *= Decimal('0.9')  # Small discount for single employee
        elif employee_count == "100+":
            multiplier *= Decimal('1.2')  # Premium for large company

        return {"multiplier": multiplier}

    def _calculate_confidence_score(
        self,
        revenue: Optional[Decimal],
        ebitda: Optional[Decimal],
        industry: str,
        business_type: str
    ) -> Decimal:
        """Calculate confidence score for the valuation"""
        score = Decimal('0.5')  # Base score

        # Revenue data available
        if revenue:
            score += Decimal('0.3')

        # EBITDA data available
        if ebitda:
            score += Decimal('0.2')

        # Industry specified
        if industry and industry != "unknown":
            score += Decimal('0.1')

        # Business type specified
        if business_type and business_type != "unknown":
            score += Decimal('0.1')

        return min(Decimal('1.0'), score)

    async def generate_insights(
        self,
        collected_data: Dict[str, Any],
        valuation_result: Dict[str, Any],
        conversation_data: Dict[str, Any],
        legacy_model_proxy: Any = None,
        **legacy_kwargs: Any,
    ) -> List[ValuationInsight]:
        """Generate deterministic report insights.

        Legacy model proxy parameters are accepted for old call sites but
        intentionally ignored. Titan owns generated narrative and external
        model egress.
        """
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
            logger.warning("Ignoring legacy reporting model proxy; generated work belongs to Titan")

        try:
            logger.info("Generating deterministic report insights")

            insights = [
                ValuationInsight(
                    category="recommendation",
                    title="Advisor Review Recommended",
                    description=(
                        "Review the deterministic valuation output, benchmark context, "
                        "and any company-specific adjustments before sharing externally."
                    ),
                    impact="medium",
                    confidence=Decimal("0.8"),
                )
            ]

            try:
                confidence_score = to_decimal(
                    valuation_result.get("confidence_score") or Decimal("0.0")
                )
            except ValueError:
                confidence_score = Decimal("0.0")
            if confidence_score < Decimal("0.6"):
                insights.append(
                    ValuationInsight(
                        category="concern",
                        title="Confidence Review Needed",
                        description=(
                            "The valuation confidence score is below the preferred "
                            "review threshold; validate inputs and assumptions."
                        ),
                        impact="high",
                        confidence=Decimal("0.85"),
                    )
                )

            logger.info(f"Generated {len(insights)} deterministic insights")
            return insights

        except ValuationEngineError as e:
            logger.error(f"Failed to generate insights: {str(e)}")
            return [
                ValuationInsight(
                    category="recommendation",
                    title="Professional Appraisal Recommended",
                    description="For accurate valuation, consider a professional business appraisal.",
                    impact="high",
                    confidence=Decimal('0.9')
                )
            ]

    async def generate_executive_summary(
        self,
        company_name: str,
        collected_data: Dict[str, Any],
        valuation_result: Dict[str, Any],
        insights: List[ValuationInsight],
        legacy_model_proxy: Any = None,
        **legacy_kwargs: Any,
    ) -> str:
        """Generate deterministic executive summary.

        Legacy model proxy parameters are accepted for old call sites but
        intentionally ignored. Titan owns generated narrative and external
        model egress.
        """
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
            logger.warning("Ignoring legacy reporting model proxy; generated work belongs to Titan")

        try:
            logger.info(f"Generating deterministic executive summary for {company_name}")
            estimated_value = valuation_result.get("estimated_value", {})
            if not isinstance(estimated_value, dict):
                estimated_value = {}
            most_likely = estimated_value.get("most_likely", "not available")
            methodology = valuation_result.get("methodology", "the selected")
            confidence = valuation_result.get("confidence_score", "not available")
            return (
                f"{company_name} has been valued using {methodology} methodology. "
                f"The indicative value is {most_likely}, with confidence {confidence}. "
                "Review the benchmark inputs, assumptions, and advisor adjustments "
                "before relying on the report externally."
            )

        except MethodologyError as e:
            logger.error(f"Failed to generate executive summary: {str(e)}")
            return f"Based on the available data, {company_name} has an estimated value of €{valuation_result['estimated_value']['most_likely']:,.0f} using the {valuation_result['methodology']} methodology."

    async def generate_recommendations(
        self,
        collected_data: Dict[str, Any],
        insights: List[ValuationInsight]
    ) -> List[str]:
        """Generate strategic recommendations"""
        logger.info("💡 Generating strategic recommendations")

        recommendations = [
            "Consider obtaining a professional business appraisal for accuracy",
            "Review and optimize key financial metrics to improve valuation",
            "Document all business processes and intellectual property"
        ]

        # Add industry-specific recommendations
        industry = collected_data.get("industry", "").lower()
        if industry == "technology":
            recommendations.append("Focus on recurring revenue and customer retention")
        elif industry == "manufacturing":
            recommendations.append("Optimize inventory management and production efficiency")
        elif industry == "retail":
            recommendations.append("Improve inventory turnover and customer experience")

        logger.info(f"✅ Generated {len(recommendations)} recommendations")
        return recommendations

    def _summarize_conversation(self, conversation_data: Dict[str, Any]) -> str:
        """Summarize conversation for context"""
        messages = conversation_data.get("conversation_history", [])
        if not messages:
            return "No conversation history available"

        # Simple summary of conversation length and topics
        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        return f"Conversation with {len(user_messages)} user inputs covering business valuation topics."
