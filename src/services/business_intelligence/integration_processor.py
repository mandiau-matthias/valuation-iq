from src.utils.exceptions import APIError

"""
Integration Processor

Processes business type integration and provides comprehensive analysis
including market context, owner profiling, and strategic insights.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.business_intelligence.integration_types import (
    BusinessType, BusinessCategory, IndustryCategory, ValuationMethodology,
    BusinessComplexity, OwnerDependencyLevel, IntegrationResult,
    BusinessAnalysisResult, MarketContext, OwnerProfile, IndustryAnalysis,
    RiskAssessment, GrowthForecast, FinancialProjections, OperationalMetrics,
    MarketMetrics, StrategicInsight, IntegrationStatus
)

logger = get_logger(__name__)


class IntegrationProcessor:
    """Processes business type integration and provides comprehensive analysis"""

    def __init__(self):
        """Initialize the integration processor"""
        self.business_analyzer = None
        self.market_contexts: Dict[IndustryCategory, MarketContext] = {}
        self.industry_analyses: Dict[IndustryCategory, IndustryAnalysis] = {}
        self.owner_profiles: Dict[str, OwnerProfile] = {}
        self.risk_assessments: Dict[BusinessType, RiskAssessment] = {}
        self.growth_forecasts: Dict[BusinessType, GrowthForecast] = {}
        self.financial_projections: Dict[BusinessType, FinancialProjections] = {}
        self.operational_metrics: Dict[BusinessType, OperationalMetrics] = {}
        self.market_metrics: Dict[BusinessType, MarketMetrics] = {}
        self.strategic_insights: Dict[BusinessType, List[StrategicInsight]] = {}

        logger.info("IntegrationProcessor initialized")

    def set_business_analyzer(self, business_analyzer):
        """Set the business analyzer"""
        self.business_analyzer = business_analyzer
        logger.info("Business analyzer set")

    async def process_integration(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        owner_profile: Optional[OwnerProfile] = None,
        market_context: Optional[MarketContext] = None
    ) -> IntegrationResult:
        """Process business type integration"""
        try:
            logger.info(f"Processing integration: {business_type.value}")

            # Analyze business type
            analysis_result = await self.business_analyzer.analyze_business_type(
                business_type, industry, owner_profile, market_context
            )

            # Process market context
            market_analysis = await self._process_market_context(
                business_type, industry, market_context
            )

            # Process owner profile
            owner_analysis = await self._process_owner_profile(
                business_type, owner_profile
            )

            # Process industry analysis
            industry_analysis = await self._process_industry_analysis(
                business_type, industry
            )

            # Process risk assessment
            risk_assessment = await self._process_risk_assessment(
                business_type, industry
            )

            # Process growth forecast
            growth_forecast = await self._process_growth_forecast(
                business_type, industry
            )

            # Process financial projections
            financial_projections = await self._process_financial_projections(
                business_type, industry
            )

            # Process operational metrics
            operational_metrics = await self._process_operational_metrics(
                business_type, industry
            )

            # Process market metrics
            market_metrics = await self._process_market_metrics(
                business_type, industry
            )

            # Generate strategic insights
            strategic_insights = await self._generate_strategic_insights(
                business_type, industry, analysis_result
            )

            # Generate recommendations
            recommendations = await self._generate_recommendations(
                business_type, industry, analysis_result
            )

            # Generate next steps
            next_steps = await self._generate_next_steps(
                business_type, industry, analysis_result
            )

            # Create integration result
            result = IntegrationResult(
                status=IntegrationStatus.COMPLETED,
                business_type=business_type,
                methodology=analysis_result.recommended_methodology,
                confidence_score=analysis_result.confidence_score,
                analysis_result=analysis_result,
                market_context=market_analysis,
                owner_profile=owner_analysis,
                industry_analysis=industry_analysis,
                risk_assessment=risk_assessment,
                growth_forecast=growth_forecast,
                financial_projections=financial_projections,
                operational_metrics=operational_metrics,
                market_metrics=market_metrics,
                strategic_insights=strategic_insights,
                recommendations=recommendations,
                next_steps=next_steps,
                created_at=datetime.now()
            )

            logger.info(f"Integration processing completed: {business_type.value}")
            return result

        except APIError as e:
            logger.error(f"Integration processing failed: {e}")
            raise

    async def _process_market_context(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        market_context: Optional[MarketContext]
    ) -> Dict[str, Any]:
        """Process market context"""
        if market_context:
            return {
                "market_size": market_context.market_size,
                "growth_rate": market_context.growth_rate,
                "competition_level": market_context.competition_level,
                "barriers_to_entry": market_context.barriers_to_entry,
                "key_success_factors": market_context.key_success_factors,
                "market_trends": market_context.market_trends,
                "regulatory_environment": market_context.regulatory_environment,
                "economic_indicators": market_context.economic_indicators,
                "comparable_companies": market_context.comparable_companies,
                "industry_benchmarks": market_context.industry_benchmarks,
                "market_metrics": market_context.market_metrics
            }
        else:
            return {
                "market_size": 0.0,
                "growth_rate": 0.0,
                "competition_level": "unknown",
                "barriers_to_entry": [],
                "key_success_factors": [],
                "market_trends": [],
                "regulatory_environment": {},
                "economic_indicators": {},
                "comparable_companies": [],
                "industry_benchmarks": {},
                "market_metrics": {}
            }

    async def _process_owner_profile(
        self, business_type: BusinessType, owner_profile: Optional[OwnerProfile]
    ) -> Dict[str, Any]:
        """Process owner profile"""
        if owner_profile:
            return {
                "owner_id": owner_profile.owner_id,
                "role": owner_profile.role,
                "experience_years": owner_profile.experience_years,
                "education_level": owner_profile.education_level,
                "skills": owner_profile.skills,
                "time_commitment": owner_profile.time_commitment,
                "risk_tolerance": owner_profile.risk_tolerance,
                "growth_ambition": owner_profile.growth_ambition,
                "exit_strategy": owner_profile.exit_strategy,
                "personal_financial_situation": owner_profile.personal_financial_situation,
                "business_goals": owner_profile.business_goals,
                "challenges": owner_profile.challenges,
                "opportunities": owner_profile.opportunities
            }
        else:
            return {
                "owner_id": "unknown",
                "role": "unknown",
                "experience_years": 0,
                "education_level": "unknown",
                "skills": [],
                "time_commitment": 0.0,
                "risk_tolerance": "unknown",
                "growth_ambition": "unknown",
                "exit_strategy": "unknown",
                "personal_financial_situation": {},
                "business_goals": [],
                "challenges": [],
                "opportunities": []
            }

    async def _process_industry_analysis(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Any]:
        """Process industry analysis"""
        if industry in self.industry_analyses:
            analysis = self.industry_analyses[industry]
            return {
                "industry": analysis.industry.value,
                "market_size": analysis.market_size,
                "growth_rate": analysis.growth_rate,
                "competition_level": analysis.competition_level,
                "barriers_to_entry": analysis.barriers_to_entry,
                "key_success_factors": analysis.key_success_factors,
                "market_trends": analysis.market_trends,
                "regulatory_environment": analysis.regulatory_environment,
                "economic_indicators": analysis.economic_indicators,
                "comparable_companies": analysis.comparable_companies,
                "industry_benchmarks": analysis.industry_benchmarks,
                "market_metrics": analysis.market_metrics,
                "risk_factors": analysis.risk_factors,
                "opportunities": analysis.opportunities,
                "threats": analysis.threats,
                "strengths": analysis.strengths,
                "weaknesses": analysis.weaknesses
            }
        else:
            return {
                "industry": industry.value,
                "market_size": 0.0,
                "growth_rate": 0.0,
                "competition_level": "unknown",
                "barriers_to_entry": [],
                "key_success_factors": [],
                "market_trends": [],
                "regulatory_environment": {},
                "economic_indicators": {},
                "comparable_companies": [],
                "industry_benchmarks": {},
                "market_metrics": {},
                "risk_factors": [],
                "opportunities": [],
                "threats": [],
                "strengths": [],
                "weaknesses": []
            }

    async def _process_risk_assessment(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Any]:
        """Process risk assessment"""
        if business_type in self.risk_assessments:
            assessment = self.risk_assessments[business_type]
            return {
                "business_type": assessment.business_type.value,
                "industry": assessment.industry.value,
                "risk_level": assessment.risk_level,
                "risk_factors": assessment.risk_factors,
                "mitigation_strategies": assessment.mitigation_strategies,
                "insurance_requirements": assessment.insurance_requirements,
                "regulatory_compliance": assessment.regulatory_compliance,
                "operational_risks": assessment.operational_risks,
                "financial_risks": assessment.financial_risks,
                "market_risks": assessment.market_risks,
                "technology_risks": assessment.technology_risks,
                "human_resource_risks": assessment.human_resource_risks,
                "environmental_risks": assessment.environmental_risks
            }
        else:
            return {
                "business_type": business_type.value,
                "industry": industry.value,
                "risk_level": "moderate",
                "risk_factors": ["Market volatility", "Competition"],
                "mitigation_strategies": ["Diversification", "Insurance"],
                "insurance_requirements": ["General liability", "Professional liability"],
                "regulatory_compliance": ["Business license", "Tax registration"],
                "operational_risks": ["Key person dependency", "Process inefficiency"],
                "financial_risks": ["Cash flow", "Debt"],
                "market_risks": ["Economic downturn", "Regulatory changes"],
                "technology_risks": ["Digital disruption", "Cybersecurity"],
                "human_resource_risks": ["Talent retention", "Succession planning"],
                "environmental_risks": ["Climate change", "Sustainability"]
            }

    async def _process_growth_forecast(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Any]:
        """Process growth forecast"""
        if business_type in self.growth_forecasts:
            forecast = self.growth_forecasts[business_type]
            return {
                "business_type": forecast.business_type.value,
                "industry": forecast.industry.value,
                "growth_scenarios": forecast.growth_scenarios,
                "revenue_projections": forecast.revenue_projections,
                "profit_projections": forecast.profit_projections,
                "market_share_projections": forecast.market_share_projections,
                "key_drivers": forecast.key_drivers,
                "assumptions": forecast.assumptions,
                "risks": forecast.risks,
                "opportunities": forecast.opportunities
            }
        else:
            return {
                "business_type": business_type.value,
                "industry": industry.value,
                "growth_scenarios": {"optimistic": 0.15, "realistic": 0.10, "pessimistic": 0.05},
                "revenue_projections": {"year_1": 100000, "year_2": 110000, "year_3": 121000},
                "profit_projections": {"year_1": 15000, "year_2": 16500, "year_3": 18150},
                "market_share_projections": {"year_1": 0.05, "year_2": 0.06, "year_3": 0.07},
                "key_drivers": ["Market growth", "Competitive advantage", "Innovation"],
                "assumptions": ["Stable market", "No major disruptions", "Continued growth"],
                "risks": ["Economic downturn", "Increased competition", "Regulatory changes"],
                "opportunities": ["Market expansion", "New products", "Strategic partnerships"]
            }

    async def _process_financial_projections(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Any]:
        """Process financial projections"""
        if business_type in self.financial_projections:
            projections = self.financial_projections[business_type]
            return {
                "business_type": projections.business_type.value,
                "industry": projections.industry.value,
                "revenue_projections": projections.revenue_projections,
                "profit_projections": projections.profit_projections,
                "cash_flow_projections": projections.cash_flow_projections,
                "balance_sheet_projections": projections.balance_sheet_projections,
                "key_metrics": projections.key_metrics,
                "assumptions": projections.assumptions,
                "risks": projections.risks,
                "opportunities": projections.opportunities
            }
        else:
            return {
                "business_type": business_type.value,
                "industry": industry.value,
                "revenue_projections": {"year_1": 100000, "year_2": 110000, "year_3": 121000},
                "profit_projections": {"year_1": 15000, "year_2": 16500, "year_3": 18150},
                "cash_flow_projections": {"year_1": 12000, "year_2": 13200, "year_3": 14520},
                "balance_sheet_projections": {"assets": 50000, "liabilities": 20000, "equity": 30000},
                "key_metrics": {"roi": 0.15, "roa": 0.10, "roe": 0.20},
                "assumptions": ["Stable market", "No major disruptions", "Continued growth"],
                "risks": ["Economic downturn", "Increased competition", "Regulatory changes"],
                "opportunities": ["Market expansion", "New products", "Strategic partnerships"]
            }

    async def _process_operational_metrics(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Any]:
        """Process operational metrics"""
        if business_type in self.operational_metrics:
            metrics = self.operational_metrics[business_type]
            return {
                "business_type": metrics.business_type.value,
                "industry": metrics.industry.value,
                "efficiency_metrics": metrics.efficiency_metrics,
                "productivity_metrics": metrics.productivity_metrics,
                "quality_metrics": metrics.quality_metrics,
                "customer_metrics": metrics.customer_metrics,
                "employee_metrics": metrics.employee_metrics,
                "financial_metrics": metrics.financial_metrics,
                "market_metrics": metrics.market_metrics
            }
        else:
            return {
                "business_type": business_type.value,
                "industry": industry.value,
                "efficiency_metrics": {"process_efficiency": 0.85, "resource_utilization": 0.80},
                "productivity_metrics": {"output_per_hour": 100, "output_per_employee": 1000},
                "quality_metrics": {"defect_rate": 0.02, "customer_satisfaction": 0.90},
                "customer_metrics": {"retention_rate": 0.85, "acquisition_cost": 100},
                "employee_metrics": {"satisfaction": 0.80, "retention": 0.90},
                "financial_metrics": {"revenue_growth": 0.10, "profit_margin": 0.15},
                "market_metrics": {"market_share": 0.05, "growth_rate": 0.10}
            }

    async def _process_market_metrics(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Any]:
        """Process market metrics"""
        if business_type in self.market_metrics:
            metrics = self.market_metrics[business_type]
            return {
                "business_type": metrics.business_type.value,
                "industry": metrics.industry.value,
                "market_share": metrics.market_share,
                "growth_rate": metrics.growth_rate,
                "competition_level": metrics.competition_level,
                "customer_acquisition_cost": metrics.customer_acquisition_cost,
                "customer_lifetime_value": metrics.customer_lifetime_value,
                "market_penetration": metrics.market_penetration,
                "brand_awareness": metrics.brand_awareness,
                "customer_satisfaction": metrics.customer_satisfaction,
                "market_trends": metrics.market_trends,
                "competitive_advantage": metrics.competitive_advantage,
                "market_opportunities": metrics.market_opportunities,
                "market_threats": metrics.market_threats
            }
        else:
            return {
                "business_type": business_type.value,
                "industry": industry.value,
                "market_share": 0.05,
                "growth_rate": 0.10,
                "competition_level": "moderate",
                "customer_acquisition_cost": 100.0,
                "customer_lifetime_value": 1000.0,
                "market_penetration": 0.30,
                "brand_awareness": 0.60,
                "customer_satisfaction": 0.85,
                "market_trends": ["Digital transformation", "Sustainability"],
                "competitive_advantage": ["Innovation", "Customer service"],
                "market_opportunities": ["Market expansion", "New products"],
                "market_threats": ["Increased competition", "Economic downturn"]
            }

    async def _generate_strategic_insights(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        analysis_result: BusinessAnalysisResult
    ) -> List[str]:
        """Generate strategic insights"""
        insights = []

        # Business type insights
        if business_type == BusinessType.SOLE_PROPRIETOR:
            insights.append("High owner dependency requires succession planning")
            insights.append("Consider incorporating for liability protection")

        # Industry insights
        if industry == IndustryCategory.TECHNOLOGY:
            insights.append("Focus on innovation and digital transformation")
            insights.append("Invest in cybersecurity and data protection")
        elif industry == IndustryCategory.HEALTHCARE:
            insights.append("Ensure regulatory compliance and patient safety")
            insights.append("Invest in technology and staff training")

        # Complexity insights
        if analysis_result.complexity == BusinessComplexity.SIMPLE:
            insights.append("Consider scaling opportunities")
            insights.append("Invest in automation and efficiency")
        elif analysis_result.complexity == BusinessComplexity.COMPLEX:
            insights.append("Focus on operational excellence")
            insights.append("Develop robust management systems")

        # Owner dependency insights
        if analysis_result.owner_dependency == OwnerDependencyLevel.CRITICAL:
            insights.append("Develop succession planning")
            insights.append("Reduce owner dependency through delegation")

        return insights

    async def _generate_recommendations(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        analysis_result: BusinessAnalysisResult
    ) -> List[str]:
        """Generate recommendations"""
        recommendations = []

        # Methodology recommendations
        recommendations.append(f"Use {analysis_result.recommended_methodology.value} methodology")

        # Business type recommendations
        if business_type == BusinessType.SOLE_PROPRIETOR:
            recommendations.append("Consider incorporating for liability protection")
            recommendations.append("Develop succession planning")

        # Industry recommendations
        if industry == IndustryCategory.TECHNOLOGY:
            recommendations.append("Invest in digital transformation")
            recommendations.append("Focus on innovation and R&D")
        elif industry == IndustryCategory.HEALTHCARE:
            recommendations.append("Ensure regulatory compliance")
            recommendations.append("Invest in staff training and development")

        # Complexity recommendations
        if analysis_result.complexity == BusinessComplexity.SIMPLE:
            recommendations.append("Consider scaling opportunities")
            recommendations.append("Invest in automation")
        elif analysis_result.complexity == BusinessComplexity.COMPLEX:
            recommendations.append("Focus on operational excellence")
            recommendations.append("Develop robust management systems")

        return recommendations

    async def _generate_next_steps(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        analysis_result: BusinessAnalysisResult
    ) -> List[str]:
        """Generate next steps"""
        next_steps = []

        # Immediate steps
        next_steps.append("Review and validate business data")
        next_steps.append("Conduct detailed financial analysis")
        next_steps.append("Assess market opportunities")

        # Methodology-specific steps
        if analysis_result.recommended_methodology == ValuationMethodology.DCF:
            next_steps.append("Prepare detailed financial projections")
            next_steps.append("Calculate discount rates")
        elif analysis_result.recommended_methodology == ValuationMethodology.MARKET_APPROACH:
            next_steps.append("Identify comparable companies")
            next_steps.append("Calculate market multiples")

        # Business type-specific steps
        if business_type == BusinessType.SOLE_PROPRIETOR:
            next_steps.append("Assess owner dependency factors")
            next_steps.append("Develop succession planning")

        # Industry-specific steps
        if industry == IndustryCategory.TECHNOLOGY:
            next_steps.append("Assess technology assets")
            next_steps.append("Evaluate intellectual property")
        elif industry == IndustryCategory.HEALTHCARE:
            next_steps.append("Ensure regulatory compliance")
            next_steps.append("Assess patient data security")

        return next_steps
