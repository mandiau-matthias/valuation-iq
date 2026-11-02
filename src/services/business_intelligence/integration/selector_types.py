"""
Methodology Selector - Type Definitions

Defines all data structures, enums, and types used in the intelligent
methodology selection service for valuation approach determination.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal


class MethodologyType(str, Enum):
    """Valuation methodology types"""
    DCF = "dcf"
    MULTIPLES = "multiples"
    ASSET_BASED = "asset_based"
    SYNTHESIZED = "synthesized"


@dataclass
class BusinessContext:
    """Business context for methodology selection"""
    industry: str  # IndustryCategory
    business_type: str  # BusinessType
    revenue: Decimal
    ebitda: Decimal
    growth_rate: Decimal
    business_age: int
    employee_count: int
    market_position: str
    competitive_advantage: str


@dataclass
class FinancialScore:
    """Financial health score for methodology selection"""
    dcf_score: Decimal
    multiples_score: Decimal
    overall_health: Decimal
    revenue_stability: Decimal
    ebitda_consistency: Decimal
    cash_flow_stability: Decimal


@dataclass
class OwnerScore:
    """Owner dependency score for methodology selection"""
    dependency_score: Decimal
    succession_readiness: Decimal
    transferability_risk: Decimal
    dcf_impact: Decimal
    multiples_impact: Decimal


@dataclass
class MarketScore:
    """Market context score for methodology selection"""
    comparable_companies_count: int
    market_data_quality: Decimal
    industry_benchmarks_available: bool
    market_data_freshness: Decimal
    dcf_score: Decimal
    multiples_score: Decimal


@dataclass
class MethodologySelection:
    """Complete methodology selection result"""
    dcf_weight: Decimal
    multiples_weight: Decimal
    confidence_score: Decimal
    reasoning: str
    recommendations: List[str]
    next_questions: List[str]
    methodology_notes: str


@dataclass
class MethodologyPreference:
    """Methodology preference during conversation"""
    preferred_methodology: str
    confidence_score: Decimal
    reasoning: str
    recommendations: List[str]
    next_questions: List[str]


@dataclass
class SelectionRequest:
    """Request for methodology selection"""
    business_context: BusinessContext
    financial_data: Dict[str, Any]
    owner_profile: Optional[Dict[str, Any]] = None
    market_context: Optional[Dict[str, Any]] = None
    include_recommendations: bool = True
    include_questions: bool = True


@dataclass
class SelectionResponse:
    """Response from methodology selection"""
    selection: MethodologySelection
    business_score: Dict[str, Decimal]
    financial_score: FinancialScore
    owner_score: Optional[OwnerScore]
    market_score: Optional[MarketScore]
    industry_score: Dict[str, Decimal]
    processing_time: Decimal
    confidence_level: str


class ConfidenceLevel(Enum):
    """Confidence levels for methodology selection"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class SelectionStatus(Enum):
    """Selection processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BusinessRules:
    """Business rules for methodology selection"""
    dcf_preference_rules: Dict[str, Any]
    multiples_preference_rules: Dict[str, Any]
    exclusion_rules: Dict[str, Any]


@dataclass
class IndustryRules:
    """Industry-specific rules for methodology selection"""
    technology: Dict[str, Any]
    retail: Dict[str, Any]
    manufacturing: Dict[str, Any]
    services: Dict[str, Any]


@dataclass
class FinancialRules:
    """Financial rules for methodology selection"""
    dcf_suitability_factors: Dict[str, Any]
    multiples_suitability_factors: Dict[str, Any]


@dataclass
class OwnerRules:
    """Owner dependency rules for methodology selection"""
    dcf_impact_rules: Dict[str, Any]
    multiples_impact_rules: Dict[str, Any]


@dataclass
class MarketRules:
    """Market context rules for methodology selection"""
    market_data_quality_threshold: Decimal
    comparable_companies_min: int
    market_data_freshness_days: int
    industry_benchmarks_quality: Decimal


# Default business rules configuration
DEFAULT_BUSINESS_RULES = {
    "dcf_preference_rules": {
        "revenue_threshold": 1_000_000,
        "ebitda_threshold": 100_000,
        "growth_rate_threshold": Decimal('0.05'),
        "historical_data_years": 3,
        "stability_threshold": Decimal('0.7'),
        "business_age_min": 3
    },
    "multiples_preference_rules": {
        "comparable_companies_min": 3,
        "market_data_freshness_days": 180,
        "industry_benchmarks_quality": Decimal('0.8'),
        "business_stability_threshold": Decimal('0.8')
    },
    "exclusion_rules": {
        "dcf_exclusion": {
            "revenue_volatility_threshold": Decimal('0.3'),
            "ebitda_negative_years_max": 1,
            "owner_dependency_threshold": Decimal('0.8'),
            "business_age_min": 3
        },
        "multiples_exclusion": {
            "comparable_companies_min": 2,
            "market_data_quality_threshold": Decimal('0.6'),
            "business_uniqueness_threshold": Decimal('0.8')
        }
    }
}

# Default industry rules configuration
DEFAULT_INDUSTRY_RULES = {
    "technology": {
        "dcf_preference": {
            "recurring_revenue_threshold": Decimal('0.7'),
            "customer_acquisition_cost_threshold": Decimal('0.3'),
            "growth_rate_threshold": Decimal('0.1'),
            "saas_metrics_available": True
        },
        "multiples_preference": {
            "saas_metrics_available": True,
            "market_comparables_quality": Decimal('0.8'),
            "recurring_revenue_percentage": Decimal('0.6')
        }
    },
    "retail": {
        "dcf_preference": {
            "location_value_threshold": Decimal('0.2'),
            "foot_traffic_stability": Decimal('0.7'),
            "inventory_turnover_consistency": Decimal('0.8')
        },
        "multiples_preference": {
            "location_value_available": True,
            "foot_traffic_data_quality": Decimal('0.8'),
            "market_comparables_quality": Decimal('0.9')
        }
    },
    "manufacturing": {
        "dcf_preference": {
            "capex_threshold": Decimal('0.1'),
            "production_capacity_utilization": Decimal('0.8'),
            "supply_chain_stability": Decimal('0.7'),
            "equipment_value_threshold": Decimal('0.2')
        },
        "multiples_preference": {
            "equipment_value_available": True,
            "production_metrics_quality": Decimal('0.8'),
            "industry_benchmarks_quality": Decimal('0.9')
        }
    },
    "services": {
        "dcf_preference": {
            "hourly_rate_consistency": Decimal('0.8'),
            "client_retention_rate": Decimal('0.7'),
            "service_capacity_utilization": Decimal('0.8'),
            "recurring_revenue_percentage": Decimal('0.5')
        },
        "multiples_preference": {
            "hourly_rate_data_available": True,
            "client_metrics_quality": Decimal('0.8'),
            "market_comparables_quality": Decimal('0.8')
        }
    }
}

# Default financial rules configuration
DEFAULT_FINANCIAL_RULES = {
    "dcf_suitability_factors": {
        "revenue_growth_weight": Decimal('0.4'),
        "ebitda_margin_weight": Decimal('0.3'),
        "stability_weight": Decimal('0.3'),
        "growth_threshold": Decimal('0.05'),
        "margin_threshold": Decimal('0.1'),
        "stability_threshold": Decimal('0.7')
    },
    "multiples_suitability_factors": {
        "stability_weight": Decimal('0.6'),
        "consistency_weight": Decimal('0.4'),
        "stability_threshold": Decimal('0.8'),
        "consistency_threshold": Decimal('0.7')
    }
}

# Default owner rules configuration
DEFAULT_OWNER_RULES = {
    "dcf_impact_rules": {
        "high_dependency_threshold": Decimal('0.8'),
        "medium_dependency_threshold": Decimal('0.6'),
        "high_dependency_impact": Decimal('0.3'),
        "medium_dependency_impact": Decimal('0.6'),
        "low_dependency_impact": Decimal('1.0')
    },
    "multiples_impact_rules": {
        "high_dependency_boost": Decimal('1.2'),
        "medium_dependency_boost": Decimal('1.1'),
        "low_dependency_boost": Decimal('1.0')
    }
}

# Default market rules configuration
DEFAULT_MARKET_RULES = {
    "market_data_quality_threshold": Decimal('0.8'),
    "comparable_companies_min": 3,
    "market_data_freshness_days": 180,
    "industry_benchmarks_quality": Decimal('0.8')
}

# Industry categories
INDUSTRY_CATEGORIES = {
    "technology": ["saas", "software", "webdev", "itsupport", "mobile-app", "ecommerce"],
    "retail": ["retail", "fashion", "jewelry", "electronics", "books", "toys"],
    "manufacturing": ["manufacturing", "construction", "engineering", "logistics"],
    "services": ["consulting", "legal", "accounting", "hr", "marketing", "advertising"],
    "healthcare": ["healthcare", "dental", "veterinary", "mental-health", "physical-therapy"],
    "food_beverage": ["restaurant", "catering", "bakery", "coffee-shop", "food-truck"],
    "real_estate": ["realestate", "property-management", "construction", "architecture"],
    "education": ["education", "training", "coaching", "tutoring", "language-school"],
    "transportation": ["transportation", "logistics", "delivery", "moving", "taxi"],
    "entertainment": ["entertainment", "events", "wedding-planning", "party-rental", "dj"],
    "agriculture": ["agriculture", "farming", "livestock", "dairy", "poultry"],
    "energy": ["energy", "solar", "wind", "utilities", "waste-management"],
    "financial": ["fintech", "insurance", "investment", "banking", "accounting"],
    "other": ["other", "b2c", "b2b", "nonprofit", "government"]
}

# Market position levels
MARKET_POSITION_LEVELS = {
    "market_leader": Decimal('1.0'),
    "established": Decimal('0.8'),
    "growing": Decimal('0.6'),
    "stable": Decimal('0.4'),
    "declining": Decimal('0.2')
}

# Competitive advantage levels
COMPETITIVE_ADVANTAGE_LEVELS = {
    "strong": Decimal('1.0'),
    "moderate": Decimal('0.7'),
    "weak": Decimal('0.4'),
    "none": Decimal('0.1')
}

# Weight distribution for methodology calculation
METHODOLOGY_WEIGHTS = {
    "business_characteristics": Decimal('0.30'),
    "financial_health": Decimal('0.40'),
    "owner_dependency": Decimal('0.20'),
    "market_context": Decimal('0.05'),
    "industry_rules": Decimal('0.05')
}

# Confidence thresholds
CONFIDENCE_THRESHOLDS = {
    "high": Decimal('0.8'),
    "medium": Decimal('0.6'),
    "low": Decimal('0.4'),
    "very_low": Decimal('0.2')
}