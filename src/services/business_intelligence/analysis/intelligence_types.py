from src.utils.exceptions import APIError

"""
Business Intelligence Service - Type Definitions

Defines all data structures, enums, and types used in the business intelligence
service for business type analysis and methodology selection.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = logging.getLogger(__name__)


class LearningType(str, Enum):
    """Types of learning for business type analysis"""
    METHODOLOGY_SELECTION = "methodology_selection"
    QUESTION_ROUTING = "question_routing"
    OWNER_DEPENDENCY = "owner_dependency"
    MARKET_CONTEXT = "market_context"


@dataclass
class BusinessTypeAnalysis:
    """Business type analysis result"""
    business_type: str
    category: str
    industry: str
    dcf_success_rate: Decimal
    multiples_success_rate: Decimal
    avg_dcf_weight: Decimal
    avg_multiples_weight: Decimal
    avg_revenue: Decimal
    avg_ebitda_margin: Decimal
    avg_growth_rate: Decimal
    avg_owner_dependency: Decimal
    comparable_companies_count: int
    industry_benchmarks_available: bool
    market_data_quality: Decimal
    valuation_accuracy: Decimal
    user_satisfaction: Decimal
    completion_rate: Decimal
    confidence_score: Decimal

    # Enhanced attributes for API response
    recommended_methodology: Optional[str] = None
    key_factors: List[str] = field(default_factory=list)
    historical_insights: Dict[str, Any] = field(default_factory=dict)
    ml_adjustments: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    risk_assessment: Dict[str, Any] = field(default_factory=dict)
    growth_potential: Decimal = Decimal('0.5')
    owner_dependency_score: Decimal = Decimal('0.0')


@dataclass
class MethodologyWeights:
    """Methodology weights for business type"""
    dcf_weight: Decimal
    multiples_weight: Decimal
    confidence_score: Decimal
    reasoning: str
    business_type_factors: List[str]
    historical_analysis: Dict[str, Any]
    market_context_analysis: Dict[str, Any]


@dataclass
class LearnedAdjustments:
    """Learned adjustments from machine learning models"""
    dcf_adjustment: Decimal
    multiples_adjustment: Decimal
    confidence_score: Decimal
    model_version: str
    learning_source: str
    prediction_accuracy: Decimal


@dataclass
class BusinessTypeStatistics:
    """Statistics for business type from database"""
    business_type: str
    total_valuations: int
    avg_revenue: Decimal
    avg_ebitda: Decimal
    avg_equity_value: Decimal
    dcf_usage_rate: Decimal
    multiples_usage_rate: Decimal
    dcf_success_rate: Decimal
    multiples_success_rate: Decimal
    avg_owner_dependency: Decimal
    avg_market_context_score: Decimal


@dataclass
class HistoricalAnalysis:
    """Historical data analysis result"""
    dcf_success_rate: Decimal
    multiples_success_rate: Decimal
    avg_revenue: Decimal
    avg_ebitda: Decimal
    avg_equity_value: Decimal
    avg_growth_rate: Decimal
    avg_owner_dependency: Decimal
    comparable_companies_count: int
    industry_benchmarks_available: bool
    market_data_quality: Decimal
    valuation_accuracy: Decimal
    user_satisfaction: Decimal
    completion_rate: Decimal


@dataclass
class BusinessAdjustments:
    """Business characteristics adjustments"""
    dcf_factor: Decimal
    multiples_factor: Decimal
    revenue_factor: Decimal
    growth_factor: Decimal
    profitability_factor: Decimal


@dataclass
class MarketAdjustments:
    """Market context adjustments"""
    dcf_factor: Decimal
    multiples_factor: Decimal
    growth_expectations_factor: Decimal
    risk_factor: Decimal
    benchmark_availability_factor: Decimal


@dataclass
class OwnerAdjustments:
    """Owner dependency adjustments"""
    dcf_factor: Decimal
    multiples_factor: Decimal
    dependency_score: Decimal
    risk_mitigation_factor: Decimal


@dataclass
class LearningModel:
    """Learning model configuration"""
    model_type: str
    version: str
    accuracy: Decimal
    training_data_size: int
    last_updated: datetime
    features: List[str]
    target_variables: List[str]


@dataclass
class BusinessTypeConfig:
    """Business type configuration"""
    business_type: str
    category: str
    industry: str
    dcf_success_rate: Decimal
    multiples_success_rate: Decimal
    avg_dcf_weight: Decimal
    avg_multiples_weight: Decimal
    avg_revenue: Decimal
    avg_ebitda_margin: Decimal
    avg_growth_rate: Decimal
    avg_owner_dependency: Decimal
    comparable_companies_count: int
    industry_benchmarks_available: bool
    market_data_quality: Decimal
    valuation_accuracy: Decimal
    user_satisfaction: Decimal
    completion_rate: Decimal


@dataclass
class AnalysisRequest:
    """Request for business type analysis"""
    business_type: str
    user_data: Dict[str, Any]
    market_context: Dict[str, Any]
    owner_profile: Optional[Dict[str, Any]] = None
    include_ml_adjustments: bool = True
    include_historical_analysis: bool = True


@dataclass
class AnalysisResponse:
    """Response from business type analysis"""
    analysis: BusinessTypeAnalysis
    methodology_weights: MethodologyWeights
    learned_adjustments: LearnedAdjustments
    historical_analysis: HistoricalAnalysis
    processing_time: Decimal
    confidence_level: str
    recommendations: List[str]


class ConfidenceLevel(Enum):
    """Confidence levels for analysis"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AnalysisStatus(Enum):
    """Analysis processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProcessingMetrics:
    """Processing performance metrics"""
    total_time: Decimal
    database_time: Decimal
    ml_time: Decimal
    cache_hits: int
    cache_misses: int
    errors: int
    warnings: int


# Business type categories (auto-generated from database - run sync_business_types_api.py to update)
def load_business_type_categories():
    """Load business type categories from synced JSON file."""
    try:
        import json
        from pathlib import Path

        config_dir = Path(__file__).parent.parent.parent.parent / "config"
        categories_file = config_dir / "synced_business_categories.json"

        if categories_file.exists():
            with open(categories_file, 'r') as f:
                categories_data = json.load(f)

            # Convert API format to internal format
            categories = {}
            for category in categories_data:
                category_id = category.get('id', category.get('name', '').lower().replace(' ', '_'))
                categories[category_id] = [category_id]  # For now, just use the category ID

            return categories
        else:
            logger.warning("Synced business categories file not found, using fallback categories")
            return get_fallback_categories()
    except APIError as e:
        logger.error(f"Error loading business categories: {e}")
        return get_fallback_categories()

def get_fallback_categories():
    """Fallback categories if synced data is not available."""
    return {
        'food_beverage': ['restaurant', 'catering', 'bakery', 'coffee-shop', 'food-truck', 'brewery', 'winery'],
        'beauty_wellness': ['hairstyling', 'nail-salon', 'spa', 'massage', 'makeup', 'skincare-clinic'],
        'technology': ['saas', 'software', 'webdev', 'itsupport', 'mobile-app', 'ecommerce', 'marketplace'],
        'professional_services': ['consulting', 'legal', 'accounting', 'hr', 'marketing', 'advertising'],
        'retail_ecommerce': ['retail', 'fashion', 'jewelry', 'electronics', 'books', 'toys'],
        'health_medical': ['healthcare', 'dental', 'veterinary', 'mental-health', 'physical-therapy'],
        'manufacturing_industrial': ['manufacturing', 'construction', 'engineering', 'logistics', 'warehousing'],
        'real_estate_property': ['realestate', 'property-management', 'construction', 'architecture'],
        'education_training': ['education', 'training', 'coaching', 'tutoring', 'language-school'],
        'transportation_logistics': ['transportation', 'logistics', 'delivery', 'moving', 'taxi'],
        'entertainment_events': ['entertainment', 'events', 'wedding-planning', 'party-rental', 'dj'],
        'agriculture_food': ['agriculture', 'farming', 'livestock', 'dairy', 'poultry', 'aquaculture'],
        'energy_utilities': ['energy', 'solar', 'wind', 'utilities', 'waste-management', 'recycling'],
        'financial_services': ['fintech', 'insurance', 'investment', 'banking', 'accounting', 'bookkeeping']
    }

# Load business type categories from synced data
BUSINESS_TYPE_CATEGORIES = load_business_type_categories()

# Default configurations for business types
DEFAULT_BUSINESS_CONFIG = {
    "dcf_success_rate": Decimal('0.5'),
    "multiples_success_rate": Decimal('0.5'),
    "avg_dcf_weight": Decimal('0.5'),
    "avg_multiples_weight": Decimal('0.5'),
    "avg_revenue": 0,
    "avg_ebitda_margin": 0,
    "avg_growth_rate": 0,
    "avg_owner_dependency": Decimal('0.5'),
    "comparable_companies_count": 0,
    "industry_benchmarks_available": False,
    "market_data_quality": Decimal('0.5'),
    "valuation_accuracy": Decimal('0.5'),
    "user_satisfaction": Decimal('0.5'),
    "completion_rate": Decimal('0.5')
}

# ML model configuration
ML_MODEL_CONFIG = {
    "random_forest": {
        "n_estimators": 100,
        "random_state": 42,
        "max_depth": 10
    },
    "logistic_regression": {
        "random_state": 42,
        "max_iter": 1000
    },
    "min_training_samples": 10,
    "feature_scaling": True,
    "cross_validation_folds": 5
}