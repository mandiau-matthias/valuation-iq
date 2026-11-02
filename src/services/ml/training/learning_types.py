"""
Learning System Types

This module defines all data structures, enums, and types for the learning system service.
It centralizes type definitions to improve maintainability and type safety.

Author: Upswitch CTO Team
Date: October 2025
Status: Production Ready
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal


class ModelType(str, Enum):
    """Types of machine learning models"""
    METHODOLOGY_SELECTION = "methodology_selection"
    QUESTION_ROUTING = "question_routing"
    OWNER_DEPENDENCY = "owner_dependency"
    MARKET_CONTEXT = "market_context"
    VALUATION_ACCURACY = "valuation_accuracy"


class LearningStatus(str, Enum):
    """Learning system status"""
    TRAINING = "training"
    TRAINED = "trained"
    DEPLOYED = "deployed"
    FAILED = "failed"
    UPDATING = "updating"


class LearningSource(str, Enum):
    """Source of learning data"""
    USER_FEEDBACK = "user_feedback"
    AUTOMATIC_COLLECTION = "automatic_collection"
    MANUAL_ANNOTATION = "manual_annotation"
    EXTERNAL_DATA = "external_data"
    SIMULATION = "simulation"


@dataclass
class ModelPerformance:
    """Model performance metrics"""
    model_id: str
    model_type: str
    accuracy: Decimal
    precision: Decimal
    recall: Decimal
    f1_score: Decimal
    cross_val_score: Decimal
    training_samples: int
    test_samples: int
    last_trained: datetime
    version: str


@dataclass
class PredictionResult:
    """Prediction result from model"""
    prediction: Dict[str, Any]
    confidence: Decimal
    model_version: str
    features_used: List[str]
    prediction_timestamp: datetime


@dataclass
class LearningData:
    """Learning data for model training"""
    business_type: str
    input_features: Dict[str, Any]
    output_prediction: Dict[str, Any]
    actual_outcome: Optional[Dict[str, Any]]
    user_id: Optional[str]
    session_id: Optional[str]
    timestamp: datetime


@dataclass
class TrainingConfig:
    """Configuration for model training"""
    model_type: ModelType
    business_type: str
    force_retrain: bool = False
    min_samples: int = 50
    test_size: Decimal = Decimal('0.2')
    random_state: int = 42
    max_samples: int = 5000


@dataclass
class ModelConfig:
    """Configuration for specific model types"""
    n_estimators: int = 100
    max_depth: Optional[int] = None
    min_samples_split: int = 2
    min_samples_leaf: int = 1
    random_state: int = 42
    n_jobs: int = -1


@dataclass
class ABTestConfig:
    """Configuration for A/B testing"""
    test_percentage: Decimal = Decimal('0.1')
    min_sample_size: int = 100
    confidence_level: Decimal = Decimal('0.95')
    test_duration_days: int = 7


@dataclass
class PerformanceThresholds:
    """Performance thresholds for model evaluation"""
    min_accuracy: Decimal = Decimal('0.6')
    min_precision: Decimal = Decimal('0.6')
    min_recall: Decimal = Decimal('0.6')
    min_f1_score: Decimal = Decimal('0.6')
    min_cross_val_score: Decimal = Decimal('0.6')


# Default configurations
DEFAULT_MODEL_CONFIGS = {
    ModelType.METHODOLOGY_SELECTION: ModelConfig(n_estimators=100, max_depth=10),
    ModelType.QUESTION_ROUTING: ModelConfig(n_estimators=100, max_depth=8),
    ModelType.OWNER_DEPENDENCY: ModelConfig(n_estimators=100, max_depth=12),
    ModelType.MARKET_CONTEXT: ModelConfig(n_estimators=100, max_depth=10),
    ModelType.VALUATION_ACCURACY: ModelConfig(n_estimators=100, max_depth=15)
}

DEFAULT_PERFORMANCE_THRESHOLDS = PerformanceThresholds()

DEFAULT_AB_TEST_CONFIG = ABTestConfig()

# Feature extraction configurations
FEATURE_CONFIGS = {
    ModelType.METHODOLOGY_SELECTION: {
        "common_features": ["revenue", "ebitda", "growth_rate", "owner_dependency", "market_data_quality"],
        "specific_features": ["comparable_companies_count", "industry_benchmarks_available", "business_stage"]
    },
    ModelType.QUESTION_ROUTING: {
        "common_features": ["revenue", "ebitda", "growth_rate", "owner_dependency", "market_data_quality"],
        "specific_features": ["data_completeness", "missing_fields_count", "conversation_step"]
    },
    ModelType.OWNER_DEPENDENCY: {
        "common_features": ["revenue", "ebitda", "growth_rate", "owner_dependency", "market_data_quality"],
        "specific_features": ["owner_hours_per_week", "owner_technical_skills", "succession_plan"]
    },
    ModelType.MARKET_CONTEXT: {
        "common_features": ["revenue", "ebitda", "growth_rate", "owner_dependency", "market_data_quality"],
        "specific_features": ["market_size", "competition_level", "industry_growth"]
    },
    ModelType.VALUATION_ACCURACY: {
        "common_features": ["revenue", "ebitda", "growth_rate", "owner_dependency", "market_data_quality"],
        "specific_features": ["data_quality_score", "methodology_confidence", "market_volatility"]
    }
}

# Target extraction configurations
TARGET_CONFIGS = {
    ModelType.METHODOLOGY_SELECTION: ["dcf_weight", "multiples_weight"],
    ModelType.QUESTION_ROUTING: ["next_question_priority"],
    ModelType.OWNER_DEPENDENCY: ["dependency_score"],
    ModelType.MARKET_CONTEXT: ["market_score"],
    ModelType.VALUATION_ACCURACY: ["accuracy_score"]
}

# Default predictions for fallback
DEFAULT_PREDICTIONS = {
    ModelType.METHODOLOGY_SELECTION: {"dcf_weight": Decimal('0.5'), "multiples_weight": 0.5},
    ModelType.QUESTION_ROUTING: {"next_question_priority": 0.5},
    ModelType.OWNER_DEPENDENCY: {"dependency_score": 0.5},
    ModelType.MARKET_CONTEXT: {"market_score": 0.5},
    ModelType.VALUATION_ACCURACY: {"accuracy_score": 0.5}
}
