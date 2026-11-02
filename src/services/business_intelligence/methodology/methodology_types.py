"""
Types and Enums for Business Type Methodology Mapping

This module contains all shared types, enums, and data classes
used across the business intelligence components.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any
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


class BusinessCategory(Enum):
    """Business categories for methodology selection"""
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
    """Asset intensity levels for methodology selection"""
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
class BusinessTypeCharacteristics:
    """Characteristics of a business type"""
    business_type: str
    category: BusinessCategory
    asset_intensity: AssetIntensity
    growth_potential: GrowthPotential
    revenue_predictability: RevenuePredictability
    key_success_factors: List[str]
    common_risks: List[str]
    optimal_methodology: ValuationMethodology
    alternative_methodology: Optional[ValuationMethodology]


@dataclass
class BusinessTypeConfig:
    """Configuration for a business type"""
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
    """Industry-specific factors for methodology selection"""
    industry_name: str
    typical_asset_intensity: AssetIntensity
    growth_characteristics: GrowthPotential
    revenue_patterns: RevenuePredictability
    key_valuation_drivers: List[str]
    common_multiple_types: List[str]
    methodology_preferences: List[ValuationMethodology]


# Import/Export compatibility
__all__ = [
    'ValuationMethodology',
    'BusinessCategory',
    'AssetIntensity',
    'GrowthPotential',
    'RevenuePredictability',
    'MethodologyDecision',
    'BusinessTypeCharacteristics',
    'BusinessTypeConfig',
    'IndustryFactors'
]
