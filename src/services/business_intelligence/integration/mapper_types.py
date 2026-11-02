"""
Business Type Methodology Mapper - Type Definitions

Defines all data structures, enums, and types used in the business type
to methodology mapping system.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal


class ValuationMethodology(Enum):
    """Available valuation methodologies"""
    DCF = "dcf"  # Discounted Cash Flow
    MULTIPLES = "multiples"  # Market Multiples
    ASSET_BASED = "asset_based"  # Asset-based valuation
    ARR_MULTIPLES = "arr_multiples"  # ARR/MRR multiples for SaaS
    REVENUE_MULTIPLES = "revenue_multiples"  # Revenue multiples
    EBITDA_MULTIPLES = "ebitda_multiples"  # EBITDA multiples
    HYBRID = "hybrid"  # Combination of methods


@dataclass
class MethodologyDecision:
    """Decision on optimal valuation methodology"""
    primary_methodology: ValuationMethodology
    secondary_methodology: Optional[ValuationMethodology]
    confidence_score: Decimal  # 0-1
    reasoning: str
    key_factors: List[str]
    special_considerations: List[str]
    expected_accuracy: Decimal  # 0-1
    time_estimate: str
    multiple_types: List[str]  # Types of multiples to use
    growth_weighted: bool = False
    asset_intensity: str = "medium"  # low, medium, high


@dataclass
class BusinessTypeConfig:
    """Configuration for a specific business type"""
    primary: ValuationMethodology
    secondary: Optional[ValuationMethodology]
    multiple_types: List[str]
    asset_intensity: str
    key_factors: List[str]
    special_considerations: List[str]
    growth_weighted: bool
    reasoning: str


@dataclass
class IndustryFactors:
    """Industry-specific factors that influence methodology selection"""
    growth_potential: str  # low, medium, high
    asset_intensity: str  # low, medium, high
    revenue_predictability: str  # low, medium, high
    key_metrics: List[str]


@dataclass
class BusinessCharacteristics:
    """Detailed characteristics for a business type"""
    business_type: str
    category: str
    asset_intensity: str
    growth_potential: str
    revenue_predictability: str
    key_success_factors: List[str]
    common_risks: List[str]
    optimal_methodology: str
    alternative_methodology: Optional[str]


class BusinessCategory(Enum):
    """Business categories for classification"""
    FOOD_BEVERAGE = "food_beverage"
    TECHNOLOGY = "technology"
    INDUSTRIAL = "industrial"
    SERVICES = "services"
    RETAIL = "retail"
    HEALTHCARE = "healthcare"
    REAL_ESTATE = "real_estate"
    CONSTRUCTION = "construction"
    OTHER = "other"


class AssetIntensity(Enum):
    """Asset intensity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GrowthPotential(Enum):
    """Growth potential levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RevenuePredictability(Enum):
    """Revenue predictability levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class RefinementFactors:
    """Factors used to refine methodology decisions"""
    industry: Optional[str] = None
    revenue: Optional[Decimal] = None
    years_in_operation: Optional[int] = None
    country_code: str = "BE"


@dataclass
class TimeEstimate:
    """Time estimates for different methodologies"""
    MULTIPLES = "1-2 hours"
    ASSET_BASED = "1-2 hours"
    DCF = "2-4 hours"
    ARR_MULTIPLES = "2-3 hours"
    HYBRID = "3-5 hours"
    DEFAULT = "2-3 hours"


# Business type normalization mappings
BUSINESS_TYPE_VARIATIONS = {
    'saas': 'saas',
    'software_as_a_service': 'saas',
    'restaurant': 'restaurant',
    'cafe': 'coffee_shop',
    'coffee shop': 'coffee_shop',
    'brewery': 'brewery',
    'brewing': 'brewery',
    'manufacturing': 'manufacturing',
    'manufacturer': 'manufacturing',
    'consulting': 'consulting',
    'consultant': 'consulting',
    'retail': 'retail',
    'retailer': 'retail',
    'ecommerce': 'ecommerce',
    'e-commerce': 'ecommerce',
    'online retail': 'ecommerce'
}

# Business category mappings
BUSINESS_CATEGORIES = {
    'restaurant': BusinessCategory.FOOD_BEVERAGE,
    'catering': BusinessCategory.FOOD_BEVERAGE,
    'brewery': BusinessCategory.FOOD_BEVERAGE,
    'coffee_shop': BusinessCategory.FOOD_BEVERAGE,
    'saas': BusinessCategory.TECHNOLOGY,
    'ecommerce': BusinessCategory.TECHNOLOGY,
    'mobile_app': BusinessCategory.TECHNOLOGY,
    'manufacturing': BusinessCategory.INDUSTRIAL,
    'consulting': BusinessCategory.SERVICES,
    'legal': BusinessCategory.SERVICES,
    'retail': BusinessCategory.RETAIL,
    'medical_practice': BusinessCategory.HEALTHCARE,
    'real_estate': BusinessCategory.REAL_ESTATE,
    'construction': BusinessCategory.CONSTRUCTION
}