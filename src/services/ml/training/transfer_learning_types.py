"""
Transfer Learning Types

This module defines all data structures, enums, and types for the transfer learning system.
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


class TransferLearningTask(str, Enum):
    """Transfer learning tasks"""
    METHODOLOGY_SELECTION = "methodology_selection"
    QUESTION_ROUTING = "question_routing"
    OWNER_DEPENDENCY = "owner_dependency"
    VALUATION_ACCURACY = "valuation_accuracy"
    USER_SATISFACTION = "user_satisfaction"


class TransferLearningMethod(str, Enum):
    """Transfer learning methods"""
    FINE_TUNING = "fine_tuning"
    FEATURE_EXTRACTION = "feature_extraction"
    DOMAIN_ADAPTATION = "domain_adaptation"
    KNOWLEDGE_DISTILLATION = "knowledge_distillation"
    META_LEARNING = "meta_learning"


class DomainAdaptationMethod(str, Enum):
    """Domain adaptation methods"""
    LINEAR = "linear"
    NONLINEAR = "nonlinear"
    CORAL = "coral"  # Correlation Alignment
    DANN = "dann"    # Domain Adversarial Neural Networks


class MetaLearningAlgorithm(str, Enum):
    """Meta-learning algorithms"""
    MAML = "maml"           # Model-Agnostic Meta-Learning
    PROTONET = "protonet"   # Prototypical Networks
    MATCHING = "matching"   # Matching Networks
    META_SGD = "meta_sgd"   # Meta-SGD


@dataclass
class PreTrainedModel:
    """Pre-trained model configuration"""
    name: str
    model_type: str
    source_domain: str
    target_domain: str
    model_path: str
    feature_extractor_path: str
    performance_metrics: Dict[str, Decimal]
    transfer_ability_score: Decimal
    created_at: datetime
    last_updated: datetime
    version: str = "1.0"


@dataclass
class TransferLearningResult:
    """Transfer learning result"""
    task: TransferLearningTask
    method: TransferLearningMethod
    source_model: str
    target_model: str
    performance_improvement: Decimal
    transfer_effectiveness: Decimal
    adaptation_time: Decimal
    final_accuracy: Decimal
    training_samples: int
    test_samples: int
    created_at: datetime


@dataclass
class DomainAdaptationConfig:
    """Domain adaptation configuration"""
    method: DomainAdaptationMethod
    learning_rate: Decimal = Decimal('0.01')
    max_iterations: int = 1000
    regularization: Decimal = Decimal('0.001')
    convergence_threshold: Decimal = 1e-6


@dataclass
class KnowledgeDistillationConfig:
    """Knowledge distillation configuration"""
    temperature: Decimal = Decimal('3.0')
    alpha: Decimal = Decimal('0.7')  # Weight for soft targets
    beta: Decimal = Decimal('0.3')  # Weight for hard targets
    distillation_epochs: int = 10
    learning_rate: Decimal = Decimal('0.01')


@dataclass
class MetaLearningConfig:
    """Meta-learning configuration"""
    algorithm: MetaLearningAlgorithm
    meta_learning_rate: Decimal = Decimal('0.01')
    inner_learning_rate: Decimal = Decimal('0.1')
    adaptation_steps: int = 5
    support_set_size: int = 5
    query_set_size: int = 15


@dataclass
class TransferLearningConfig:
    """Transfer learning configuration"""
    task: TransferLearningTask
    method: TransferLearningMethod
    source_model_name: str
    target_data_size: int
    adaptation_config: Optional[DomainAdaptationConfig] = None
    distillation_config: Optional[KnowledgeDistillationConfig] = None
    meta_config: Optional[MetaLearningConfig] = None


# Default configurations
DEFAULT_DOMAIN_ADAPTATION_CONFIG = DomainAdaptationConfig(
    method=DomainAdaptationMethod.LINEAR,
    learning_rate=Decimal('0.01'),
    max_iterations=1000,
    regularization=Decimal('0.001'),
    convergence_threshold=1e-6
)

DEFAULT_KNOWLEDGE_DISTILLATION_CONFIG = KnowledgeDistillationConfig(
    temperature=Decimal('3.0'),
    alpha=Decimal('0.7'),
    beta=Decimal('0.3'),
    distillation_epochs=10,
    learning_rate=Decimal('0.01')
)

DEFAULT_META_LEARNING_CONFIG = MetaLearningConfig(
    algorithm=MetaLearningAlgorithm.MAML,
    meta_learning_rate=Decimal('0.01'),
    inner_learning_rate=Decimal('0.1'),
    adaptation_steps=5,
    support_set_size=5,
    query_set_size=15
)

# Pre-trained model configurations
DEFAULT_PRETRAINED_MODELS = {
    "business_classifier": PreTrainedModel(
        name="business_classifier",
        model_type="classification",
        source_domain="general_business",
        target_domain="valuation",
        model_path="models/pretrained/business_classifier.pkl",
        feature_extractor_path="models/pretrained/business_feature_extractor.pkl",
        performance_metrics={"accuracy": Decimal('0.85'), "f1_score": 0.82},
        transfer_ability_score=Decimal('0.78'),
        created_at=datetime.now(),
        last_updated=datetime.now()
    ),
    "financial_analyzer": PreTrainedModel(
        name="financial_analyzer",
        model_type="regression",
        source_domain="financial_analysis",
        target_domain="valuation",
        model_path="models/pretrained/financial_analyzer.pkl",
        feature_extractor_path="models/pretrained/financial_feature_extractor.pkl",
        performance_metrics={"r2_score": Decimal('0.88'), "mae": 0.12},
        transfer_ability_score=Decimal('0.85'),
        created_at=datetime.now(),
        last_updated=datetime.now()
    ),
    "market_analyzer": PreTrainedModel(
        name="market_analyzer",
        model_type="classification",
        source_domain="market_analysis",
        target_domain="valuation",
        model_path="models/pretrained/market_analyzer.pkl",
        feature_extractor_path="models/pretrained/market_feature_extractor.pkl",
        performance_metrics={"accuracy": Decimal('0.82'), "f1_score": 0.79},
        transfer_ability_score=Decimal('0.73'),
        created_at=datetime.now(),
        last_updated=datetime.now()
    )
}

# Transfer learning method configurations
TRANSFER_METHOD_CONFIGS = {
    TransferLearningMethod.FINE_TUNING: {
        "learning_rate": Decimal('0.001'),
        "epochs": 10,
        "batch_size": 32,
        "freeze_layers": 0
    },
    TransferLearningMethod.FEATURE_EXTRACTION: {
        "extract_layers": -2,  # Second to last layer
        "classifier_type": "logistic_regression",
        "regularization": Decimal('0.01')
    },
    TransferLearningMethod.DOMAIN_ADAPTATION: {
        "adaptation_method": "linear",
        "learning_rate": Decimal('0.01'),
        "max_iterations": 1000
    },
    TransferLearningMethod.KNOWLEDGE_DISTILLATION: {
        "temperature": Decimal('3.0'),
        "alpha": Decimal('0.7'),
        "distillation_epochs": 10
    },
    TransferLearningMethod.META_LEARNING: {
        "meta_learning_rate": Decimal('0.01'),
        "inner_learning_rate": Decimal('0.1'),
        "adaptation_steps": 5
    }
}

# Task-specific configurations
TASK_CONFIGS = {
    TransferLearningTask.METHODOLOGY_SELECTION: {
        "target_classes": 2,  # DCF vs Multiples
        "feature_dim": 8,
        "evaluation_metric": "accuracy"
    },
    TransferLearningTask.QUESTION_ROUTING: {
        "target_classes": 5,  # Different question types
        "feature_dim": 6,
        "evaluation_metric": "f1_score"
    },
    TransferLearningTask.OWNER_DEPENDENCY: {
        "target_classes": 3,  # Low, Medium, High dependency
        "feature_dim": 7,
        "evaluation_metric": "accuracy"
    },
    TransferLearningTask.VALUATION_ACCURACY: {
        "target_classes": 1,  # Regression
        "feature_dim": 10,
        "evaluation_metric": "r2_score"
    },
    TransferLearningTask.USER_SATISFACTION: {
        "target_classes": 5,  # 1-5 satisfaction scale
        "feature_dim": 8,
        "evaluation_metric": "mae"
    }
}

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "min_accuracy": Decimal('0.6'),
    "min_f1_score": Decimal('0.6'),
    "min_r2_score": Decimal('0.5'),
    "max_mae": Decimal('0.3'),
    "min_transfer_effectiveness": Decimal('0.3')
}

# Transfer learning effectiveness scoring
TRANSFER_EFFECTIVENESS_SCORES = {
    "excellent": Decimal('0.8'),
    "good": Decimal('0.6'),
    "fair": Decimal('0.4'),
    "poor": Decimal('0.2')
}
