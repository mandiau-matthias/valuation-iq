"""
Business Type Integration Types

Shared data structures and enums for the business type integration engine.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias
from datetime import datetime
from decimal import Decimal

JsonMap: TypeAlias = dict[str, object]


class BusinessCategory(str, Enum):
    """Business categories from frontend"""

    FOOD_BEVERAGE = "food-beverage"
    BEAUTY_WELLNESS = "beauty-wellness"
    FITNESS_HEALTH = "fitness-health"
    PROFESSIONAL_SERVICES = "professional-services"
    TECHNOLOGY = "technology"
    RETAIL = "retail"
    CONSTRUCTION = "construction"
    TRANSPORTATION = "transportation"
    ENTERTAINMENT = "entertainment"
    EDUCATION = "education"
    REAL_ESTATE = "real-estate"
    FINANCE = "finance"
    MANUFACTURING = "manufacturing"
    AGRICULTURE = "agriculture"
    HOSPITALITY = "hospitality"
    CONSULTING = "consulting"
    MARKETING = "marketing"
    LEGAL = "legal"
    MEDICAL = "medical"
    DENTAL = "dental"
    VETERINARY = "veterinary"
    AUTOMOTIVE = "automotive"
    CLEANING = "cleaning"
    LANDSCAPING = "landscaping"
    SECURITY = "security"
    WASTE_MANAGEMENT = "waste-management"
    UTILITIES = "utilities"
    TELECOMMUNICATIONS = "telecommunications"
    INSURANCE = "insurance"
    OTHER = "other"


class BusinessType(str, Enum):
    """Business types from frontend"""

    SOLE_PROPRIETOR = "sole_proprietor"
    PARTNERSHIP = "partnership"
    LLC = "llc"
    CORPORATION = "corporation"
    S_CORP = "s_corp"
    C_CORP = "c_corp"
    B_CORP = "b_corp"
    NON_PROFIT = "non_profit"
    COOPERATIVE = "cooperative"
    JOINT_VENTURE = "joint_venture"
    FRANCHISE = "franchise"
    SUBSIDIARY = "subsidiary"
    HOLDING_COMPANY = "holding_company"
    TRUST = "trust"
    ESTATE = "estate"
    OTHER = "other"


class IndustryCategory(str, Enum):
    """Industry categories"""

    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    RETAIL = "retail"
    MANUFACTURING = "manufacturing"
    CONSTRUCTION = "construction"
    TRANSPORTATION = "transportation"
    ENTERTAINMENT = "entertainment"
    EDUCATION = "education"
    REAL_ESTATE = "real_estate"
    AGRICULTURE = "agriculture"
    HOSPITALITY = "hospitality"
    PROFESSIONAL_SERVICES = "professional_services"
    CONSULTING = "consulting"
    MARKETING = "marketing"
    LEGAL = "legal"
    MEDICAL = "medical"
    DENTAL = "dental"
    VETERINARY = "veterinary"
    AUTOMOTIVE = "automotive"
    CLEANING = "cleaning"
    LANDSCAPING = "landscaping"
    SECURITY = "security"
    WASTE_MANAGEMENT = "waste_management"
    UTILITIES = "utilities"
    TELECOMMUNICATIONS = "telecommunications"
    INSURANCE = "insurance"
    OTHER = "other"


class ValuationMethodology(str, Enum):
    """Valuation methodologies"""

    DCF = "dcf"
    MARKET_MULTIPLES = "market_multiples"
    ASSET_BASED = "asset_based"
    INCOME_APPROACH = "income_approach"
    MARKET_APPROACH = "market_approach"
    COST_APPROACH = "cost_approach"
    HYBRID = "hybrid"
    CUSTOM = "custom"


class BusinessComplexity(str, Enum):
    """Business complexity levels"""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    ENTERPRISE = "enterprise"


class OwnerDependencyLevel(str, Enum):
    """Owner dependency levels"""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class IntegrationStatus(str, Enum):
    """Integration status indicators"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BusinessTypeConfig:
    """Business type configuration"""

    business_type: BusinessType
    category: BusinessCategory
    industry: IndustryCategory
    complexity: BusinessComplexity
    owner_dependency: OwnerDependencyLevel
    recommended_methodology: ValuationMethodology
    alternative_methodologies: list[ValuationMethodology]
    business_rules: JsonMap
    market_context: JsonMap
    owner_factors: JsonMap
    industry_benchmarks: JsonMap
    comparable_companies: list[str]
    risk_factors: list[str]
    growth_indicators: list[str]
    financial_metrics: list[str]
    operational_metrics: list[str]
    market_metrics: list[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class BusinessAnalysisResult:
    """Business analysis result"""

    business_type: BusinessType
    category: BusinessCategory
    industry: IndustryCategory
    complexity: BusinessComplexity
    owner_dependency: OwnerDependencyLevel
    recommended_methodology: ValuationMethodology
    confidence_score: Decimal
    reasoning: str
    alternative_methodologies: list[ValuationMethodology]
    business_rules_applied: list[str]
    market_context: JsonMap
    owner_factors: JsonMap
    industry_benchmarks: JsonMap
    risk_assessment: JsonMap
    growth_potential: JsonMap
    financial_health: JsonMap
    operational_efficiency: JsonMap
    market_position: JsonMap
    competitive_advantage: JsonMap
    strategic_recommendations: list[str]
    created_at: datetime


@dataclass
class IntegrationResult:
    """Integration result"""

    status: IntegrationStatus
    business_type: BusinessType
    methodology: ValuationMethodology
    confidence_score: Decimal
    analysis_result: BusinessAnalysisResult
    market_context: JsonMap
    owner_profile: JsonMap
    industry_analysis: JsonMap
    risk_assessment: JsonMap
    growth_forecast: JsonMap
    financial_projections: JsonMap
    operational_metrics: JsonMap
    market_metrics: JsonMap
    strategic_insights: list[str]
    recommendations: list[str]
    next_steps: list[str]
    created_at: datetime


@dataclass
class BusinessRule:
    """Business rule definition"""

    rule_id: str
    name: str
    description: str
    business_type: BusinessType
    industry: IndustryCategory
    condition: str
    action: str
    priority: int
    weight: Decimal
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class MarketContext:
    """Market context data"""

    industry: IndustryCategory
    market_size: Decimal
    growth_rate: Decimal
    competition_level: str
    barriers_to_entry: list[str]
    key_success_factors: list[str]
    market_trends: list[str]
    regulatory_environment: JsonMap
    economic_indicators: JsonMap
    comparable_companies: list[str]
    industry_benchmarks: JsonMap
    market_metrics: JsonMap
    created_at: datetime
    updated_at: datetime


@dataclass
class OwnerProfile:
    """Owner profile data"""

    owner_id: str
    business_type: BusinessType
    role: str
    experience_years: int
    education_level: str
    skills: list[str]
    time_commitment: Decimal
    risk_tolerance: str
    growth_ambition: str
    exit_strategy: str
    personal_financial_situation: JsonMap
    business_goals: list[str]
    challenges: list[str]
    opportunities: list[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class IndustryAnalysis:
    """Industry analysis data"""

    industry: IndustryCategory
    market_size: Decimal
    growth_rate: Decimal
    competition_level: str
    barriers_to_entry: list[str]
    key_success_factors: list[str]
    market_trends: list[str]
    regulatory_environment: JsonMap
    economic_indicators: JsonMap
    comparable_companies: list[str]
    industry_benchmarks: JsonMap
    market_metrics: JsonMap
    risk_factors: list[str]
    opportunities: list[str]
    threats: list[str]
    strengths: list[str]
    weaknesses: list[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class RiskAssessment:
    """Risk assessment data"""

    business_type: BusinessType
    industry: IndustryCategory
    risk_level: str
    risk_factors: list[str]
    mitigation_strategies: list[str]
    insurance_requirements: list[str]
    regulatory_compliance: list[str]
    operational_risks: list[str]
    financial_risks: list[str]
    market_risks: list[str]
    technology_risks: list[str]
    human_resource_risks: list[str]
    environmental_risks: list[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class GrowthForecast:
    """Growth forecast data"""

    business_type: BusinessType
    industry: IndustryCategory
    growth_scenarios: JsonMap
    revenue_projections: JsonMap
    profit_projections: JsonMap
    market_share_projections: JsonMap
    key_drivers: list[str]
    assumptions: list[str]
    risks: list[str]
    opportunities: list[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class FinancialProjections:
    """Financial projections data"""

    business_type: BusinessType
    industry: IndustryCategory
    revenue_projections: JsonMap
    profit_projections: JsonMap
    cash_flow_projections: JsonMap
    balance_sheet_projections: JsonMap
    key_metrics: JsonMap
    assumptions: list[str]
    risks: list[str]
    opportunities: list[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class OperationalMetrics:
    """Operational metrics data"""

    business_type: BusinessType
    industry: IndustryCategory
    efficiency_metrics: JsonMap
    productivity_metrics: JsonMap
    quality_metrics: JsonMap
    customer_metrics: JsonMap
    employee_metrics: JsonMap
    financial_metrics: JsonMap
    market_metrics: JsonMap
    created_at: datetime
    updated_at: datetime


@dataclass
class MarketMetrics:
    """Market metrics data"""

    business_type: BusinessType
    industry: IndustryCategory
    market_share: Decimal
    growth_rate: Decimal
    competition_level: str
    customer_acquisition_cost: Decimal
    customer_lifetime_value: Decimal
    market_penetration: Decimal
    brand_awareness: Decimal
    customer_satisfaction: Decimal
    market_trends: list[str]
    competitive_advantage: list[str]
    market_opportunities: list[str]
    market_threats: list[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class StrategicInsight:
    """Strategic insight data"""

    insight_id: str
    business_type: BusinessType
    industry: IndustryCategory
    insight_type: str
    title: str
    description: str
    impact: str
    priority: str
    implementation: str
    timeline: str
    resources: list[str]
    risks: list[str]
    opportunities: list[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class IntegrationMetrics:
    """Integration metrics data"""

    total_integrations: int
    successful_integrations: int
    failed_integrations: int
    average_processing_time: Decimal
    success_rate: Decimal
    error_rate: Decimal
    performance_metrics: JsonMap
    quality_metrics: JsonMap
    user_satisfaction: Decimal
    created_at: datetime
    updated_at: datetime


# Default configurations
DEFAULT_BUSINESS_TYPE_CONFIG = BusinessTypeConfig(
    business_type=BusinessType.SOLE_PROPRIETOR,
    category=BusinessCategory.PROFESSIONAL_SERVICES,
    industry=IndustryCategory.CONSULTING,
    complexity=BusinessComplexity.SIMPLE,
    owner_dependency=OwnerDependencyLevel.HIGH,
    recommended_methodology=ValuationMethodology.INCOME_APPROACH,
    alternative_methodologies=[
        ValuationMethodology.MARKET_APPROACH,
        ValuationMethodology.COST_APPROACH,
    ],
    business_rules={},
    market_context={},
    owner_factors={},
    industry_benchmarks={},
    comparable_companies=[],
    risk_factors=[],
    growth_indicators=[],
    financial_metrics=[],
    operational_metrics=[],
    market_metrics=[],
    created_at=datetime.now(),
    updated_at=datetime.now(),
)

DEFAULT_BUSINESS_ANALYSIS_RESULT = BusinessAnalysisResult(
    business_type=BusinessType.SOLE_PROPRIETOR,
    category=BusinessCategory.PROFESSIONAL_SERVICES,
    industry=IndustryCategory.CONSULTING,
    complexity=BusinessComplexity.SIMPLE,
    owner_dependency=OwnerDependencyLevel.HIGH,
    recommended_methodology=ValuationMethodology.INCOME_APPROACH,
    confidence_score=Decimal("0.8"),
    reasoning="Standard sole proprietor analysis",
    alternative_methodologies=[ValuationMethodology.MARKET_APPROACH],
    business_rules_applied=[],
    market_context={},
    owner_factors={},
    industry_benchmarks={},
    risk_assessment={},
    growth_potential={},
    financial_health={},
    operational_efficiency={},
    market_position={},
    competitive_advantage={},
    strategic_recommendations=[],
    created_at=datetime.now(),
)

DEFAULT_INTEGRATION_RESULT = IntegrationResult(
    status=IntegrationStatus.COMPLETED,
    business_type=BusinessType.SOLE_PROPRIETOR,
    methodology=ValuationMethodology.INCOME_APPROACH,
    confidence_score=Decimal("0.8"),
    analysis_result=DEFAULT_BUSINESS_ANALYSIS_RESULT,
    market_context={},
    owner_profile={},
    industry_analysis={},
    risk_assessment={},
    growth_forecast={},
    financial_projections={},
    operational_metrics={},
    market_metrics={},
    strategic_insights=[],
    recommendations=[],
    next_steps=[],
    created_at=datetime.now(),
)
