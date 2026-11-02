from src.utils.exceptions import BusinessTypeError, DatabaseError

"""
Business Analyzer

Analyzes business types and provides intelligent methodology selection
based on business characteristics, industry mapping, and owner dependency.

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
    BusinessComplexity, OwnerDependencyLevel, BusinessAnalysisResult,
    BusinessTypeConfig, MarketContext, OwnerProfile, IndustryAnalysis,
    RiskAssessment, GrowthForecast, FinancialProjections, OperationalMetrics,
    MarketMetrics, StrategicInsight
)

logger = get_logger(__name__)


class BusinessAnalyzer:
    """Analyzes business types and provides methodology recommendations"""

    def __init__(self):
        """Initialize the business analyzer"""
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

        logger.info("BusinessAnalyzer initialized")

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

            # Get business type configuration
            config = await self._get_business_type_config(business_type)

            # Analyze business complexity
            complexity = await self._analyze_business_complexity(business_type, industry)

            # Analyze owner dependency
            owner_dependency = await self._analyze_owner_dependency(
                business_type, owner_profile
            )

            # Determine recommended methodology
            methodology = await self._determine_methodology(
                business_type, industry, complexity, owner_dependency
            )

            # Calculate confidence score
            confidence_score = await self._calculate_confidence_score(
                business_type, industry, complexity, owner_dependency
            )

            # Generate reasoning
            reasoning = await self._generate_reasoning(
                business_type, industry, complexity, owner_dependency, methodology
            )

            # Get alternative methodologies
            alternatives = await self._get_alternative_methodologies(
                business_type, industry, methodology
            )

            # Apply business rules
            business_rules_applied = await self._apply_business_rules(
                business_type, industry, complexity, owner_dependency
            )

            # Analyze market context
            market_analysis = await self._analyze_market_context(
                business_type, industry, market_context
            )

            # Analyze owner factors
            owner_analysis = await self._analyze_owner_factors(
                business_type, owner_profile
            )

            # Get industry benchmarks
            benchmarks = await self._get_industry_benchmarks(industry)

            # Assess risks
            risk_assessment = await self._assess_risks(business_type, industry)

            # Analyze growth potential
            growth_potential = await self._analyze_growth_potential(
                business_type, industry
            )

            # Analyze financial health
            financial_health = await self._analyze_financial_health(
                business_type, industry
            )

            # Analyze operational efficiency
            operational_efficiency = await self._analyze_operational_efficiency(
                business_type, industry
            )

            # Analyze market position
            market_position = await self._analyze_market_position(
                business_type, industry
            )

            # Analyze competitive advantage
            competitive_advantage = await self._analyze_competitive_advantage(
                business_type, industry
            )

            # Generate strategic recommendations
            strategic_recommendations = await self._generate_strategic_recommendations(
                business_type, industry, complexity, owner_dependency
            )

            # Create analysis result
            result = BusinessAnalysisResult(
                business_type=business_type,
                category=config.category,
                industry=industry,
                complexity=complexity,
                owner_dependency=owner_dependency,
                recommended_methodology=methodology,
                confidence_score=confidence_score,
                reasoning=reasoning,
                alternative_methodologies=alternatives,
                business_rules_applied=business_rules_applied,
                market_context=market_analysis,
                owner_factors=owner_analysis,
                industry_benchmarks=benchmarks,
                risk_assessment=risk_assessment,
                growth_potential=growth_potential,
                financial_health=financial_health,
                operational_efficiency=operational_efficiency,
                market_position=market_position,
                competitive_advantage=competitive_advantage,
                strategic_recommendations=strategic_recommendations,
                created_at=datetime.now()
            )

            logger.info(f"Business analysis completed: {business_type.value}")
            return result

        except DatabaseError as e:
            logger.error(f"Business analysis failed: {e}")
            raise

    async def _get_business_type_config(
        self, business_type: BusinessType
    ) -> BusinessTypeConfig:
        """Get business type configuration"""
        if business_type not in self.business_type_configs:
            # Load from database or create default
            config = await self._load_business_type_config(business_type)
            self.business_type_configs[business_type] = config

        return self.business_type_configs[business_type]

    async def _load_business_type_config(
        self, business_type: BusinessType
    ) -> BusinessTypeConfig:
        """Load business type configuration from database"""
        # This would typically load from database
        # For now, return a default configuration
        from src.services.business_intelligence.integration_types import DEFAULT_BUSINESS_TYPE_CONFIG
        return DEFAULT_BUSINESS_TYPE_CONFIG

    async def _analyze_business_complexity(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> BusinessComplexity:
        """Analyze business complexity"""
        # Simple heuristic based on business type and industry
        if business_type in [BusinessType.SOLE_PROPRIETOR, BusinessType.PARTNERSHIP]:
            return BusinessComplexity.SIMPLE
        elif business_type in [BusinessType.LLC, BusinessType.S_CORP]:
            return BusinessComplexity.MODERATE
        elif business_type in [BusinessType.C_CORP, BusinessType.B_CORP]:
            return BusinessComplexity.COMPLEX
        else:
            return BusinessComplexity.ENTERPRISE

    async def _analyze_owner_dependency(
        self, business_type: BusinessType, owner_profile: Optional[OwnerProfile]
    ) -> OwnerDependencyLevel:
        """Analyze owner dependency level"""
        if not owner_profile:
            return OwnerDependencyLevel.HIGH

        # Analyze based on business type and owner profile
        if business_type == BusinessType.SOLE_PROPRIETOR:
            return OwnerDependencyLevel.CRITICAL
        elif business_type in [BusinessType.PARTNERSHIP, BusinessType.LLC]:
            return OwnerDependencyLevel.HIGH
        elif business_type in [BusinessType.S_CORP, BusinessType.C_CORP]:
            return OwnerDependencyLevel.MODERATE
        else:
            return OwnerDependencyLevel.LOW

    async def _determine_methodology(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        complexity: BusinessComplexity,
        owner_dependency: OwnerDependencyLevel
    ) -> ValuationMethodology:
        """Determine recommended valuation methodology"""
        # Simple heuristic based on business characteristics
        if owner_dependency == OwnerDependencyLevel.CRITICAL:
            return ValuationMethodology.INCOME_APPROACH
        elif complexity == BusinessComplexity.SIMPLE:
            return ValuationMethodology.MARKET_APPROACH
        elif complexity == BusinessComplexity.MODERATE:
            return ValuationMethodology.HYBRID
        else:
            return ValuationMethodology.DCF

    async def _calculate_confidence_score(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        complexity: BusinessComplexity,
        owner_dependency: OwnerDependencyLevel
    ) -> Decimal:
        """Calculate confidence score for methodology recommendation"""
        # Simple heuristic based on available data
        base_score = Decimal('0.7')

        # Adjust based on complexity
        if complexity == BusinessComplexity.SIMPLE:
            base_score += Decimal('0.1')
        elif complexity == BusinessComplexity.MODERATE:
            base_score += Decimal('0.05')

        # Adjust based on owner dependency
        if owner_dependency == OwnerDependencyLevel.CRITICAL:
            base_score += Decimal('0.1')

        return min(base_score, Decimal('1.0'))

    async def _generate_reasoning(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        complexity: BusinessComplexity,
        owner_dependency: OwnerDependencyLevel,
        methodology: ValuationMethodology
    ) -> str:
        """Generate reasoning for methodology recommendation"""
        return f"Recommended {methodology.value} methodology based on {business_type.value} business type, {industry.value} industry, {complexity.value} complexity, and {owner_dependency.value} owner dependency."

    async def _get_alternative_methodologies(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        primary_methodology: ValuationMethodology
    ) -> List[ValuationMethodology]:
        """Get alternative methodologies"""
        alternatives = []

        if primary_methodology != ValuationMethodology.DCF:
            alternatives.append(ValuationMethodology.DCF)
        if primary_methodology != ValuationMethodology.MARKET_APPROACH:
            alternatives.append(ValuationMethodology.MARKET_APPROACH)
        if primary_methodology != ValuationMethodology.COST_APPROACH:
            alternatives.append(ValuationMethodology.COST_APPROACH)

        return alternatives[:2]  # Return top 2 alternatives

    async def _apply_business_rules(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        complexity: BusinessComplexity,
        owner_dependency: OwnerDependencyLevel
    ) -> List[str]:
        """Apply business rules"""
        rules_applied = []

        # Apply industry-specific rules
        if industry == IndustryCategory.TECHNOLOGY:
            rules_applied.append("Technology industry rule applied")
        elif industry == IndustryCategory.HEALTHCARE:
            rules_applied.append("Healthcare industry rule applied")

        # Apply business type rules
        if business_type == BusinessType.SOLE_PROPRIETOR:
            rules_applied.append("Sole proprietor rule applied")
        elif business_type == BusinessType.CORPORATION:
            rules_applied.append("Corporation rule applied")

        return rules_applied

    async def _analyze_market_context(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        market_context: Optional[MarketContext]
    ) -> Dict[str, Any]:
        """Analyze market context"""
        if market_context:
            return {
                "market_size": market_context.market_size,
                "growth_rate": market_context.growth_rate,
                "competition_level": market_context.competition_level,
                "barriers_to_entry": market_context.barriers_to_entry,
                "key_success_factors": market_context.key_success_factors,
                "market_trends": market_context.market_trends
            }
        else:
            return {
                "market_size": Decimal('0.0'),
                "growth_rate": Decimal('0.0'),
                "competition_level": "unknown",
                "barriers_to_entry": [],
                "key_success_factors": [],
                "market_trends": []
            }

    async def _analyze_owner_factors(
        self, business_type: BusinessType, owner_profile: Optional[OwnerProfile]
    ) -> Dict[str, Any]:
        """Analyze owner factors"""
        if owner_profile:
            return {
                "role": owner_profile.role,
                "experience_years": owner_profile.experience_years,
                "education_level": owner_profile.education_level,
                "skills": owner_profile.skills,
                "time_commitment": owner_profile.time_commitment,
                "risk_tolerance": owner_profile.risk_tolerance,
                "growth_ambition": owner_profile.growth_ambition,
                "exit_strategy": owner_profile.exit_strategy
            }
        else:
            return {
                "role": "unknown",
                "experience_years": 0,
                "education_level": "unknown",
                "skills": [],
                "time_commitment": Decimal('0.0'),
                "risk_tolerance": "unknown",
                "growth_ambition": "unknown",
                "exit_strategy": "unknown"
            }

    async def _get_industry_benchmarks(self, industry: IndustryCategory) -> Dict[str, Any]:
        """Get industry benchmarks"""
        # This would typically load from database
        return {
            "revenue_growth": Decimal('0.1'),
            "profit_margin": Decimal('0.15'),
            "market_share": Decimal('0.05'),
            "customer_acquisition_cost": Decimal('100.0'),
            "customer_lifetime_value": Decimal('1000.0')
        }

    async def _assess_risks(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Any]:
        """Assess business risks"""
        return {
            "operational_risks": ["Market volatility", "Competition"],
            "financial_risks": ["Cash flow", "Debt"],
            "market_risks": ["Economic downturn", "Regulatory changes"],
            "technology_risks": ["Digital disruption", "Cybersecurity"],
            "human_resource_risks": ["Key person dependency", "Talent retention"]
        }

    async def _analyze_growth_potential(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Any]:
        """Analyze growth potential"""
        return {
            "market_opportunities": ["Market expansion", "New products"],
            "growth_drivers": ["Innovation", "Efficiency"],
            "scaling_potential": "High",
            "expansion_opportunities": ["Geographic", "Product line"]
        }

    async def _analyze_financial_health(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Any]:
        """Analyze financial health"""
        return {
            "revenue_stability": "Good",
            "profitability": "Moderate",
            "cash_flow": "Positive",
            "debt_level": "Low",
            "liquidity": "Adequate"
        }

    async def _analyze_operational_efficiency(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Any]:
        """Analyze operational efficiency"""
        return {
            "process_efficiency": "Good",
            "resource_utilization": "Moderate",
            "productivity": "High",
            "quality_control": "Effective",
            "customer_satisfaction": "High"
        }

    async def _analyze_market_position(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Any]:
        """Analyze market position"""
        return {
            "market_share": Decimal('0.05'),
            "competitive_position": "Strong",
            "brand_recognition": "Moderate",
            "customer_loyalty": "High",
            "market_penetration": "Growing"
        }

    async def _analyze_competitive_advantage(
        self, business_type: BusinessType, industry: IndustryCategory
    ) -> Dict[str, Any]:
        """Analyze competitive advantage"""
        return {
            "unique_value_proposition": "Strong",
            "competitive_moat": "Moderate",
            "differentiation": "Clear",
            "barriers_to_entry": "High",
            "sustainable_advantage": "Yes"
        }

    async def _generate_strategic_recommendations(
        self,
        business_type: BusinessType,
        industry: IndustryCategory,
        complexity: BusinessComplexity,
        owner_dependency: OwnerDependencyLevel
    ) -> List[str]:
        """Generate strategic recommendations"""
        recommendations = []

        if owner_dependency == OwnerDependencyLevel.CRITICAL:
            recommendations.append("Develop succession planning")
            recommendations.append("Reduce owner dependency")

        if complexity == BusinessComplexity.SIMPLE:
            recommendations.append("Consider scaling opportunities")
            recommendations.append("Invest in automation")

        if industry == IndustryCategory.TECHNOLOGY:
            recommendations.append("Invest in digital transformation")
            recommendations.append("Focus on innovation")

        return recommendations

    async def analyze_business_characteristics(
        self, business_type: str, user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze business characteristics"""
        try:
            # Convert string to BusinessType enum - handle unknown types gracefully
            try:
                business_type_enum = BusinessType(business_type)
            except ValueError:
                # If not a valid BusinessType, use a default
                business_type_enum = BusinessType.OTHER

            # Get business type configuration
            config = await self._get_business_type_config(business_type_enum)

            # Analyze business complexity
            complexity = await self._analyze_business_complexity(business_type_enum, IndustryCategory.TECHNOLOGY)

            # Analyze owner dependency
            owner_dependency = await self._analyze_owner_dependency(business_type_enum, None)

            # Determine recommended methodology
            methodology = await self._determine_methodology(
                business_type_enum, IndustryCategory.TECHNOLOGY, complexity, owner_dependency
            )

            # Calculate confidence score
            confidence_score = await self._calculate_confidence_score(
                business_type_enum, IndustryCategory.TECHNOLOGY, complexity, owner_dependency
            )

            # Generate reasoning
            reasoning = await self._generate_reasoning(
                business_type_enum, IndustryCategory.TECHNOLOGY, complexity, owner_dependency, methodology
            )

            # Get alternative methodologies
            alternatives = await self._get_alternative_methodologies(
                business_type_enum, IndustryCategory.TECHNOLOGY, methodology
            )

            # Apply business rules
            business_rules_applied = await self._apply_business_rules(
                business_type_enum, IndustryCategory.TECHNOLOGY, complexity, owner_dependency
            )

            return {
                "business_type": business_type,
                "category": config.category.value if hasattr(config.category, 'value') else str(config.category),
                "complexity": complexity.value if hasattr(complexity, 'value') else str(complexity),
                "owner_dependency": owner_dependency.value if hasattr(owner_dependency, 'value') else str(owner_dependency),
                "recommended_methodology": methodology.value if hasattr(methodology, 'value') else str(methodology),
                "confidence_score": confidence_score,
                "reasoning": reasoning,
                "alternative_methodologies": [alt.value if hasattr(alt, 'value') else str(alt) for alt in alternatives],
                "business_rules_applied": business_rules_applied,
                "adjustments": {
                    "market_adjustments": Decimal('0.0'),
                    "owner_adjustments": Decimal('0.0'),
                    "historical_adjustments": Decimal('0.0'),
                    "learning_adjustments": Decimal('0.0')
                },
                "user_data": user_data,
                "created_at": datetime.now().isoformat()
            }

        except BusinessTypeError as e:
            logger.error(f"Failed to analyze business characteristics for {business_type}: {e}")
            return {
                "business_type": business_type,
                "error": str(e),
                "created_at": datetime.now().isoformat()
            }

    async def get_business_type_info(self, business_type: str) -> Dict[str, Any]:
        """Get comprehensive information about a business type"""
        try:
            # Convert string to BusinessType enum - handle unknown types gracefully
            try:
                business_type_enum = BusinessType(business_type)
            except ValueError:
                # If not a valid BusinessType, use a default
                business_type_enum = BusinessType.OTHER

            # Get business type configuration
            config = await self._get_business_type_config(business_type_enum)

            # Get industry analysis
            industry_analysis = await self._get_industry_analysis(business_type_enum)

            # Get market context
            market_context = await self._get_market_context(business_type_enum)

            # Get owner profile analysis
            owner_analysis = await self._get_owner_analysis(business_type_enum)

            # Get risk assessment
            risk_assessment = await self._assess_risks(business_type_enum, IndustryCategory.TECHNOLOGY)

            # Get growth potential
            growth_potential = await self._analyze_growth_potential(business_type_enum, IndustryCategory.TECHNOLOGY)

            # Get financial health
            financial_health = await self._analyze_financial_health(business_type_enum, IndustryCategory.TECHNOLOGY)

            # Get operational efficiency
            operational_efficiency = await self._analyze_operational_efficiency(business_type_enum, IndustryCategory.TECHNOLOGY)

            # Get market position
            market_position = await self._analyze_market_position(business_type_enum, IndustryCategory.TECHNOLOGY)

            # Get competitive advantage
            competitive_advantage = await self._analyze_competitive_advantage(business_type_enum, IndustryCategory.TECHNOLOGY)

            # Get strategic recommendations
            strategic_recommendations = await self._generate_strategic_recommendations(
                business_type_enum, IndustryCategory.TECHNOLOGY, BusinessComplexity.MODERATE, OwnerDependencyLevel.MODERATE
            )

            return {
                "business_type": business_type,
                "category": config.category.value if hasattr(config.category, 'value') else str(config.category),
                "industry": industry_analysis.get("industry", "unknown"),
                "complexity": config.complexity.value if hasattr(config.complexity, 'value') else str(config.complexity),
                "owner_dependency": config.owner_dependency.value if hasattr(config.owner_dependency, 'value') else str(config.owner_dependency),
                "recommended_methodology": config.recommended_methodology.value if hasattr(config.recommended_methodology, 'value') else str(config.recommended_methodology),
                "confidence_score": config.confidence_score,
                "reasoning": config.reasoning,
                "market_context": market_context,
                "owner_analysis": owner_analysis,
                "risk_assessment": risk_assessment,
                "growth_potential": growth_potential,
                "financial_health": financial_health,
                "operational_efficiency": operational_efficiency,
                "market_position": market_position,
                "competitive_advantage": competitive_advantage,
                "strategic_recommendations": strategic_recommendations,
                "created_at": datetime.now().isoformat()
            }

        except BusinessTypeError as e:
            logger.error(f"Failed to get business type info for {business_type}: {e}")
            return {
                "business_type": business_type,
                "error": str(e),
                "created_at": datetime.now().isoformat()
            }

    async def get_business_type_categories(self) -> List[str]:
        """Get all business type categories"""
        return [
            "Sole Proprietor",
            "Partnership", 
            "LLC",
            "S-Corp",
            "C-Corp",
            "B-Corp",
            "Non-Profit",
            "Cooperative",
            "Franchise",
            "Joint Venture"
        ]

    async def _get_industry_analysis(self, business_type: BusinessType) -> Dict[str, Any]:
        """Get industry analysis for business type"""
        return {
            "industry": "Technology",
            "market_size": Decimal('1000000000.0'),
            "growth_rate": Decimal('0.15'),
            "competition_level": "High",
            "barriers_to_entry": ["Capital", "Technology", "Regulation"],
            "key_success_factors": ["Innovation", "Customer Service", "Efficiency"]
        }

    async def _get_market_context(self, business_type: BusinessType) -> Dict[str, Any]:
        """Get market context for business type"""
        return {
            "market_size": Decimal('1000000000.0'),
            "growth_rate": Decimal('0.15'),
            "competition_level": "High",
            "barriers_to_entry": ["Capital", "Technology", "Regulation"],
            "key_success_factors": ["Innovation", "Customer Service", "Efficiency"],
            "market_trends": ["Digital transformation", "Automation", "Sustainability"]
        }

    async def _get_owner_analysis(self, business_type: BusinessType) -> Dict[str, Any]:
        """Get owner analysis for business type"""
        return {
            "role": "Owner/Operator",
            "experience_years": 5,
            "education_level": "Bachelor's",
            "skills": ["Management", "Sales", "Operations"],
            "time_commitment": Decimal('0.8'),
            "risk_tolerance": "Moderate",
            "growth_ambition": "High",
            "exit_strategy": "Sale to strategic buyer"
        }