from src.utils.exceptions import APIError, BusinessTypeError, ConfigurationError, DatabaseError

"""
Business Type Integration Engine - Refactored

This service integrates with the current business type catalog from the frontend
and provides intelligent methodology selection based on business type
characteristics, industry mapping, and owner dependency analysis.

Features:
1. Business Type Configuration - current business type catalog from frontend
2. Industry Mapping - Technology, Food & Beverage, Professional Services, etc.
3. Business Rules Engine - Industry-specific rules for methodology selection
4. Owner Dependency Analysis - Human factor integration per business type
5. Market Context Integration - Industry benchmarks and comparable companies

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.business_intelligence.integration_types import (
    BusinessType, BusinessCategory, IndustryCategory, ValuationMethodology,
    BusinessComplexity, OwnerDependencyLevel, IntegrationResult,
    BusinessAnalysisResult, BusinessTypeConfig, MarketContext, OwnerProfile,
    IndustryAnalysis, RiskAssessment, GrowthForecast, FinancialProjections,
    OperationalMetrics, MarketMetrics, StrategicInsight, IntegrationStatus
)
from ..analysis.business_analyzer import BusinessAnalyzer
from src.services.business_intelligence.integration_processor import IntegrationProcessor

logger = get_logger(__name__)


class BusinessTypeIntegrationEngineRefactored:
    """Refactored business type integration engine"""

    def __init__(self):
        """Initialize the business type integration engine"""
        self.business_analyzer = BusinessAnalyzer()
        self.integration_processor = IntegrationProcessor()
        self.integration_processor.set_business_analyzer(self.business_analyzer)

        # Configuration data
        self.business_type_configs: Dict[BusinessType, BusinessTypeConfig] = {}
        self.industry_analyses: Dict[IndustryCategory, IndustryAnalysis] = {}
        self.market_contexts: Dict[IndustryCategory, MarketContext] = {}
        self.owner_profiles: Dict[str, OwnerProfile] = {}
        self.risk_assessments: Dict[BusinessType, RiskAssessment] = {}
        self.growth_forecasts: Dict[BusinessType, GrowthForecast] = {}
        self.financial_projections: Dict[BusinessType, FinancialProjections] = {}
        self.operational_metrics: Dict[BusinessType, OperationalMetrics] = {}
        self.market_metrics: Dict[BusinessType, MarketMetrics] = {}
        self.strategic_insights: Dict[BusinessType, List[StrategicInsight]] = {}

        # Integration metrics
        self.integration_metrics = {
            "total_integrations": 0,
            "successful_integrations": 0,
            "failed_integrations": 0,
            "average_processing_time": Decimal('0.0'),
            "success_rate": Decimal('0.0'),
            "error_rate": Decimal('0.0')
        }

        logger.info("BusinessTypeIntegrationEngineRefactored initialized")

    async def integrate_business_type(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        owner_profile: Optional[OwnerProfile] = None,
        market_context: Optional[MarketContext] = None
    ) -> IntegrationResult:
        """Integrate business type with valuation methodology"""
        try:
            start_time = datetime.now()
            logger.info(f"Integrating business type: {business_type.value}")

            # Process integration
            result = await self.integration_processor.process_integration(
                business_type, industry, owner_profile, market_context
            )

            # Update metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            await self._update_integration_metrics(True, processing_time)

            logger.info(f"Business type integration completed: {business_type.value}")
            return result

        except APIError as e:
            logger.error(f"Business type integration failed: {e}")
            await self._update_integration_metrics(False, Decimal('0.0'))
            raise

    async def analyze_business_type(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        owner_profile: Optional[OwnerProfile] = None,
        market_context: Optional[MarketContext] = None
    ) -> BusinessAnalysisResult:
        """Analyze business type and provide methodology recommendations"""
        try:
            logger.info(f"Analyzing business type: {business_type.value}")

            result = await self.business_analyzer.analyze_business_type(
                business_type, industry, owner_profile, market_context
            )

            logger.info(f"Business type analysis completed: {business_type.value}")
            return result

        except ConfigurationError as e:
            logger.error(f"Business type analysis failed: {e}")
            raise

    async def get_business_type_config(
        self, business_type: BusinessType
    ) -> BusinessTypeConfig:
        """Get business type configuration"""
        try:
            logger.info(f"Getting business type config: {business_type.value}")

            if business_type not in self.business_type_configs:
                config = await self._load_business_type_config(business_type)
                self.business_type_configs[business_type] = config

            return self.business_type_configs[business_type]

        except ConfigurationError as e:
            logger.error(f"Failed to get business type config: {e}")
            raise

    async def get_industry_analysis(
        self, industry: IndustryCategory
    ) -> IndustryAnalysis:
        """Get industry analysis"""
        try:
            logger.info(f"Getting industry analysis: {industry.value}")

            if industry not in self.industry_analyses:
                analysis = await self._load_industry_analysis(industry)
                self.industry_analyses[industry] = analysis

            return self.industry_analyses[industry]

        except ValuationEngineError as e:
            logger.error(f"Failed to get industry analysis: {e}")
            raise

    async def get_market_context(
        self, industry: IndustryCategory
    ) -> MarketContext:
        """Get market context"""
        try:
            logger.info(f"Getting market context: {industry.value}")

            if industry not in self.market_contexts:
                context = await self._load_market_context(industry)
                self.market_contexts[industry] = context

            return self.market_contexts[industry]

        except ValuationEngineError as e:
            logger.error(f"Failed to get market context: {e}")
            raise

    async def get_owner_profile(self, owner_id: str) -> Optional[OwnerProfile]:
        """Get owner profile"""
        try:
            logger.info(f"Getting owner profile: {owner_id}")

            if owner_id in self.owner_profiles:
                return self.owner_profiles[owner_id]

            profile = await self._load_owner_profile(owner_id)
            if profile:
                self.owner_profiles[owner_id] = profile

            return profile

        except BusinessTypeError as e:
            logger.error(f"Failed to get owner profile: {e}")
            return None

    async def get_risk_assessment(
        self, business_type: BusinessType
    ) -> RiskAssessment:
        """Get risk assessment"""
        try:
            logger.info(f"Getting risk assessment: {business_type.value}")

            if business_type not in self.risk_assessments:
                assessment = await self._load_risk_assessment(business_type)
                self.risk_assessments[business_type] = assessment

            return self.risk_assessments[business_type]

        except BusinessTypeError as e:
            logger.error(f"Failed to get risk assessment: {e}")
            raise

    async def get_growth_forecast(
        self, business_type: BusinessType
    ) -> GrowthForecast:
        """Get growth forecast"""
        try:
            logger.info(f"Getting growth forecast: {business_type.value}")

            if business_type not in self.growth_forecasts:
                forecast = await self._load_growth_forecast(business_type)
                self.growth_forecasts[business_type] = forecast

            return self.growth_forecasts[business_type]

        except BusinessTypeError as e:
            logger.error(f"Failed to get growth forecast: {e}")
            raise

    async def get_financial_projections(
        self, business_type: BusinessType
    ) -> FinancialProjections:
        """Get financial projections"""
        try:
            logger.info(f"Getting financial projections: {business_type.value}")

            if business_type not in self.financial_projections:
                projections = await self._load_financial_projections(business_type)
                self.financial_projections[business_type] = projections

            return self.financial_projections[business_type]

        except BusinessTypeError as e:
            logger.error(f"Failed to get financial projections: {e}")
            raise

    async def get_operational_metrics(
        self, business_type: BusinessType
    ) -> OperationalMetrics:
        """Get operational metrics"""
        try:
            logger.info(f"Getting operational metrics: {business_type.value}")

            if business_type not in self.operational_metrics:
                metrics = await self._load_operational_metrics(business_type)
                self.operational_metrics[business_type] = metrics

            return self.operational_metrics[business_type]

        except BusinessTypeError as e:
            logger.error(f"Failed to get operational metrics: {e}")
            raise

    async def get_market_metrics(
        self, business_type: BusinessType
    ) -> MarketMetrics:
        """Get market metrics"""
        try:
            logger.info(f"Getting market metrics: {business_type.value}")

            if business_type not in self.market_metrics:
                metrics = await self._load_market_metrics(business_type)
                self.market_metrics[business_type] = metrics

            return self.market_metrics[business_type]

        except BusinessTypeError as e:
            logger.error(f"Failed to get market metrics: {e}")
            raise

    async def get_strategic_insights(
        self, business_type: BusinessType
    ) -> List[StrategicInsight]:
        """Get strategic insights"""
        try:
            logger.info(f"Getting strategic insights: {business_type.value}")

            if business_type not in self.strategic_insights:
                insights = await self._load_strategic_insights(business_type)
                self.strategic_insights[business_type] = insights

            return self.strategic_insights[business_type]

        except APIError as e:
            logger.error(f"Failed to get strategic insights: {e}")
            return []

    async def get_integration_metrics(self) -> Dict[str, Any]:
        """Get integration metrics"""
        try:
            logger.info("Getting integration metrics")

            return {
                "total_integrations": self.integration_metrics["total_integrations"],
                "successful_integrations": self.integration_metrics["successful_integrations"],
                "failed_integrations": self.integration_metrics["failed_integrations"],
                "average_processing_time": self.integration_metrics["average_processing_time"],
                "success_rate": self.integration_metrics["success_rate"],
                "error_rate": self.integration_metrics["error_rate"],
                "business_type_configs": len(self.business_type_configs),
                "industry_analyses": len(self.industry_analyses),
                "market_contexts": len(self.market_contexts),
                "owner_profiles": len(self.owner_profiles),
                "risk_assessments": len(self.risk_assessments),
                "growth_forecasts": len(self.growth_forecasts),
                "financial_projections": len(self.financial_projections),
                "operational_metrics": len(self.operational_metrics),
                "market_metrics": len(self.market_metrics),
                "strategic_insights": len(self.strategic_insights)
            }

        except DatabaseError as e:
            logger.error(f"Failed to get integration metrics: {e}")
            return {}

    async def _load_business_type_config(
        self, business_type: BusinessType
    ) -> BusinessTypeConfig:
        """Load business type configuration from database"""
        # This would typically load from database
        # For now, return a default configuration
        from src.services.business_intelligence.integration_types import DEFAULT_BUSINESS_TYPE_CONFIG
        return DEFAULT_BUSINESS_TYPE_CONFIG

    async def _load_industry_analysis(
        self, industry: IndustryCategory
    ) -> IndustryAnalysis:
        """Load industry analysis from database"""
        # This would typically load from database
        # For now, return a default analysis
        return IndustryAnalysis(
            industry=industry,
            market_size=Decimal('1000000.0'),
            growth_rate=Decimal('0.10'),
            competition_level="moderate",
            barriers_to_entry=["Capital requirements", "Regulatory compliance"],
            key_success_factors=["Innovation", "Customer service"],
            market_trends=["Digital transformation", "Sustainability"],
            regulatory_environment={"compliance": "required"},
            economic_indicators={"gdp_growth": 0.03},
            comparable_companies=["Company A", "Company B"],
            industry_benchmarks={"revenue_growth": 0.10},
            market_metrics={"market_share": 0.05},
            risk_factors=["Market volatility", "Competition"],
            opportunities=["Market expansion", "New products"],
            threats=["Economic downturn", "Regulatory changes"],
            strengths=["Innovation", "Customer service"],
            weaknesses=["Limited resources", "Market penetration"],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    async def _load_market_context(
        self, industry: IndustryCategory
    ) -> MarketContext:
        """Load market context from database"""
        # This would typically load from database
        # For now, return a default context
        return MarketContext(
            industry=industry,
            market_size=Decimal('1000000.0'),
            growth_rate=Decimal('0.10'),
            competition_level="moderate",
            barriers_to_entry=["Capital requirements", "Regulatory compliance"],
            key_success_factors=["Innovation", "Customer service"],
            market_trends=["Digital transformation", "Sustainability"],
            regulatory_environment={"compliance": "required"},
            economic_indicators={"gdp_growth": 0.03},
            comparable_companies=["Company A", "Company B"],
            industry_benchmarks={"revenue_growth": 0.10},
            market_metrics={"market_share": 0.05},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    async def _load_owner_profile(self, owner_id: str) -> Optional[OwnerProfile]:
        """Load owner profile from database"""
        # This would typically load from database
        # For now, return None
        return None

    async def _load_risk_assessment(
        self, business_type: BusinessType
    ) -> RiskAssessment:
        """Load risk assessment from database"""
        # This would typically load from database
        # For now, return a default assessment
        return RiskAssessment(
            business_type=business_type,
            industry=IndustryCategory.OTHER,
            risk_level="moderate",
            risk_factors=["Market volatility", "Competition"],
            mitigation_strategies=["Diversification", "Insurance"],
            insurance_requirements=["General liability", "Professional liability"],
            regulatory_compliance=["Business license", "Tax registration"],
            operational_risks=["Key person dependency", "Process inefficiency"],
            financial_risks=["Cash flow", "Debt"],
            market_risks=["Economic downturn", "Regulatory changes"],
            technology_risks=["Digital disruption", "Cybersecurity"],
            human_resource_risks=["Talent retention", "Succession planning"],
            environmental_risks=["Climate change", "Sustainability"],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    async def _load_growth_forecast(
        self, business_type: BusinessType
    ) -> GrowthForecast:
        """Load growth forecast from database"""
        # This would typically load from database
        # For now, return a default forecast
        return GrowthForecast(
            business_type=business_type,
            industry=IndustryCategory.OTHER,
            growth_scenarios={"optimistic": Decimal('0.15'), "realistic": Decimal('0.10'), "pessimistic": 0.05},
            revenue_projections={"year_1": 100000, "year_2": 110000, "year_3": 121000},
            profit_projections={"year_1": 15000, "year_2": 16500, "year_3": 18150},
            market_share_projections={"year_1": Decimal('0.05'), "year_2": Decimal('0.06'), "year_3": 0.07},
            key_drivers=["Market growth", "Competitive advantage", "Innovation"],
            assumptions=["Stable market", "No major disruptions", "Continued growth"],
            risks=["Economic downturn", "Increased competition", "Regulatory changes"],
            opportunities=["Market expansion", "New products", "Strategic partnerships"],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    async def _load_financial_projections(
        self, business_type: BusinessType
    ) -> FinancialProjections:
        """Load financial projections from database"""
        # This would typically load from database
        # For now, return a default projections
        return FinancialProjections(
            business_type=business_type,
            industry=IndustryCategory.OTHER,
            revenue_projections={"year_1": 100000, "year_2": 110000, "year_3": 121000},
            profit_projections={"year_1": 15000, "year_2": 16500, "year_3": 18150},
            cash_flow_projections={"year_1": 12000, "year_2": 13200, "year_3": 14520},
            balance_sheet_projections={"assets": 50000, "liabilities": 20000, "equity": 30000},
            key_metrics={"roi": Decimal('0.15'), "roa": Decimal('0.10'), "roe": 0.20},
            assumptions=["Stable market", "No major disruptions", "Continued growth"],
            risks=["Economic downturn", "Increased competition", "Regulatory changes"],
            opportunities=["Market expansion", "New products", "Strategic partnerships"],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    async def _load_operational_metrics(
        self, business_type: BusinessType
    ) -> OperationalMetrics:
        """Load operational metrics from database"""
        # This would typically load from database
        # For now, return a default metrics
        return OperationalMetrics(
            business_type=business_type,
            industry=IndustryCategory.OTHER,
            efficiency_metrics={"process_efficiency": Decimal('0.85'), "resource_utilization": 0.80},
            productivity_metrics={"output_per_hour": 100, "output_per_employee": 1000},
            quality_metrics={"defect_rate": Decimal('0.02'), "customer_satisfaction": 0.90},
            customer_metrics={"retention_rate": Decimal('0.85'), "acquisition_cost": 100},
            employee_metrics={"satisfaction": Decimal('0.80'), "retention": 0.90},
            financial_metrics={"revenue_growth": Decimal('0.10'), "profit_margin": 0.15},
            market_metrics={"market_share": Decimal('0.05'), "growth_rate": 0.10},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    async def _load_market_metrics(
        self, business_type: BusinessType
    ) -> MarketMetrics:
        """Load market metrics from database"""
        # This would typically load from database
        # For now, return a default metrics
        return MarketMetrics(
            business_type=business_type,
            industry=IndustryCategory.OTHER,
            market_share=Decimal('0.05'),
            growth_rate=Decimal('0.10'),
            competition_level="moderate",
            customer_acquisition_cost=Decimal('100.0'),
            customer_lifetime_value=Decimal('1000.0'),
            market_penetration=Decimal('0.30'),
            brand_awareness=Decimal('0.60'),
            customer_satisfaction=Decimal('0.85'),
            market_trends=["Digital transformation", "Sustainability"],
            competitive_advantage=["Innovation", "Customer service"],
            market_opportunities=["Market expansion", "New products"],
            market_threats=["Increased competition", "Economic downturn"],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    async def _load_strategic_insights(
        self, business_type: BusinessType
    ) -> List[StrategicInsight]:
        """Load strategic insights from database"""
        # This would typically load from database
        # For now, return empty list
        return []

    async def _update_integration_metrics(
        self, success: bool, processing_time: Decimal
    ) -> None:
        """Update integration metrics"""
        try:
            self.integration_metrics["total_integrations"] += 1

            if success:
                self.integration_metrics["successful_integrations"] += 1
            else:
                self.integration_metrics["failed_integrations"] += 1

            # Update average processing time
            total_time = self.integration_metrics["average_processing_time"] * (
                self.integration_metrics["total_integrations"] - 1
            ) + processing_time
            self.integration_metrics["average_processing_time"] = (
                total_time / self.integration_metrics["total_integrations"]
            )

            # Update success rate
            self.integration_metrics["success_rate"] = (
                self.integration_metrics["successful_integrations"] /
                self.integration_metrics["total_integrations"]
            )

            # Update error rate
            self.integration_metrics["error_rate"] = (
                self.integration_metrics["failed_integrations"] /
                self.integration_metrics["total_integrations"]
            )

        except APIError as e:
            logger.error(f"Failed to update integration metrics: {e}")
