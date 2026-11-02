"""
ML Types

This module defines shared data structures and enums for the ML valuation engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

if TYPE_CHECKING:
    import numpy as np


class MLModelType(str, Enum):
    """Machine learning model types"""

    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    DIMENSIONALITY_REDUCTION = "dimensionality_reduction"
    ENSEMBLE = "ensemble"
    DEEP_LEARNING = "deep_learning"
    REINFORCEMENT_LEARNING = "reinforcement_learning"


class ValuationMethodology(str, Enum):
    """Valuation methodology types"""

    DCF = "dcf"
    MULTIPLES = "multiples"
    ASSET_BASED = "asset_based"
    MARKET = "market"
    INCOME = "income"
    COST = "cost"
    HYBRID = "hybrid"


class ModelStatus(str, Enum):
    """Model training and deployment status"""

    TRAINING = "training"
    TRAINED = "trained"
    VALIDATING = "validating"
    DEPLOYED = "deployed"
    RETIRED = "retired"
    ERROR = "error"


class DataQuality(str, Enum):
    """Data quality levels"""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNUSABLE = "unusable"


@dataclass
class MLPredictionResult:
    """ML prediction result"""

    prediction: Any
    confidence: Decimal
    probability: Optional[Decimal] = None
    model_name: Optional[str] = None
    features_used: Optional[List[str]] = None
    prediction_time: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ModelMetrics:
    """Model performance metrics"""

    accuracy: Decimal
    precision: Decimal
    recall: Decimal
    f1_score: Decimal
    auc_roc: Decimal
    mse: Optional[Decimal] = None
    rmse: Optional[Decimal] = None
    mae: Optional[Decimal] = None
    r2_score: Optional[Decimal] = None
    training_time: Optional[timedelta] = None
    inference_time: Optional[timedelta] = None


@dataclass
class TrainingData:
    """Training data structure"""

    features: np.ndarray
    labels: np.ndarray
    feature_names: List[str]
    data_quality: DataQuality
    sample_count: int
    feature_count: int
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ModelConfiguration:
    """Model configuration"""

    model_type: MLModelType
    algorithm: str
    hyperparameters: Dict[str, Any]
    feature_engineering: Dict[str, Any]
    preprocessing: Dict[str, Any]
    validation_strategy: str
    performance_threshold: Decimal
    created_at: datetime


@dataclass
class EnsembleModel:
    """Ensemble model structure"""

    base_models: List[str]
    meta_model: Optional[str] = None
    voting_strategy: str = "hard"
    weights: Optional[List[Decimal]] = None
    performance_metrics: Optional[ModelMetrics] = None
    created_at: Optional[datetime] = None


@dataclass
class DeepLearningModel:
    """Deep learning model structure"""

    architecture: List[Dict[str, Any]]
    optimizer: str
    loss_function: str
    activation_functions: List[str]
    regularization: Dict[str, Any]
    training_epochs: int
    batch_size: int
    learning_rate: Decimal
    dropout_rate: Decimal


@dataclass
class ReinforcementLearningModel:
    """Reinforcement learning model structure"""

    algorithm: str
    state_space: Dict[str, Any]
    action_space: Dict[str, Any]
    reward_function: str
    exploration_strategy: str
    learning_rate: Decimal
    discount_factor: Decimal
    epsilon: Decimal
    epsilon_decay: Decimal


@dataclass
class FeatureImportance:
    """Feature importance analysis"""

    feature_name: str
    importance_score: Decimal
    rank: int
    category: str
    description: Optional[str] = None


@dataclass
class ModelExplanation:
    """Model explanation and interpretability"""

    model_id: str
    explanation_type: str
    feature_contributions: List[FeatureImportance]
    decision_path: Optional[List[str]] = None
    confidence_interval: Optional[Tuple[float, float]] = None
    uncertainty_measures: Optional[Dict[str, Decimal]] = None


@dataclass
class DataPreprocessing:
    """Data preprocessing configuration"""

    scaling_method: str
    encoding_method: str
    feature_selection: List[str]
    outlier_detection: bool
    missing_value_strategy: str
    feature_engineering: List[str]
    validation_split: Decimal


@dataclass
class ModelValidation:
    """Model validation results"""

    validation_type: str
    cross_validation_scores: List[Decimal]
    holdout_performance: ModelMetrics
    feature_importance: List[FeatureImportance]
    confusion_matrix: Optional[np.ndarray] = None
    roc_curve: Optional[Tuple[np.ndarray, np.ndarray]] = None
    precision_recall_curve: Optional[Tuple[np.ndarray, np.ndarray]] = None


@dataclass
class ModelDeployment:
    """Model deployment configuration"""

    model_id: str
    version: str
    deployment_environment: str
    scaling_configuration: Dict[str, Any]
    monitoring_configuration: Dict[str, Any]
    rollback_strategy: str
    performance_thresholds: Dict[str, Decimal]
    created_at: datetime


@dataclass
class ModelMonitoring:
    """Model monitoring metrics"""

    model_id: str
    timestamp: datetime
    prediction_count: int
    average_confidence: Decimal
    data_drift_score: Decimal
    model_drift_score: Decimal
    performance_metrics: ModelMetrics
    alerts: List[str]
    recommendations: List[str]


@dataclass
class TransferLearningConfig:
    """Transfer learning configuration"""

    source_domain: str
    target_domain: str
    pre_trained_model: str
    fine_tuning_layers: List[int]
    learning_rate_schedule: str
    freeze_layers: List[int]
    adaptation_strategy: str


@dataclass
class HyperparameterOptimization:
    """Hyperparameter optimization configuration"""

    optimization_method: str
    parameter_space: Dict[str, Any]
    optimization_metric: str
    max_iterations: int
    cross_validation_folds: int
    early_stopping: bool
    patience: int


@dataclass
class ModelComparison:
    """Model comparison results"""

    model_a: str
    model_b: str
    comparison_metrics: Dict[str, Decimal]
    statistical_significance: bool
    p_value: Decimal
    recommendation: str
    confidence_level: Decimal


@dataclass
class ModelEnsemble:
    """Model ensemble configuration"""

    ensemble_id: str
    base_models: List[str]
    combination_method: str
    weight_assignment: str
    performance_threshold: Decimal
    diversity_requirement: Decimal
    created_at: datetime


@dataclass
class ModelPipeline:
    """ML pipeline configuration"""

    pipeline_id: str
    stages: List[Dict[str, Any]]
    data_flow: List[str]
    dependencies: Dict[str, List[str]]
    error_handling: Dict[str, Any]
    monitoring_points: List[str]
    created_at: datetime


@dataclass
class ModelArtifact:
    """Model artifact information"""

    artifact_id: str
    model_id: str
    artifact_type: str
    file_path: str
    file_size: int
    checksum: str
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ModelVersion:
    """Model version information"""

    version_id: str
    model_id: str
    version_number: str
    status: ModelStatus
    performance_metrics: ModelMetrics
    training_data_hash: str
    model_artifacts: List[ModelArtifact]
    created_at: datetime
    deployed_at: Optional[datetime] = None
    retired_at: Optional[datetime] = None


@dataclass
class ModelRegistry:
    """Model registry entry"""

    model_id: str
    model_name: str
    model_type: MLModelType
    current_version: str
    versions: List[ModelVersion]
    tags: List[str]
    description: str
    created_at: datetime
    updated_at: datetime


@dataclass
class ModelExperiment:
    """Model experiment tracking"""

    experiment_id: str
    experiment_name: str
    objective: str
    models_tested: List[str]
    best_model: str
    best_metrics: ModelMetrics
    hyperparameters_tested: Dict[str, List[Any]]
    results_summary: str
    created_at: datetime
    completed_at: Optional[datetime] = None


@dataclass
class ModelPerformance:
    """Model performance tracking"""

    model_id: str
    timestamp: datetime
    metric_name: str
    metric_value: Decimal
    threshold: Decimal
    status: str
    trend: str
    alert_triggered: bool


@dataclass
class ModelRetraining:
    """Model retraining configuration"""

    model_id: str
    retraining_trigger: str
    new_data_available: bool
    performance_degradation: bool
    data_drift_detected: bool
    scheduled_retraining: bool
    retraining_frequency: str
    last_retraining: Optional[datetime] = None
    next_retraining: Optional[datetime] = None


# Export all types for backward compatibility
__all__ = [
    "MLModelType",
    "ValuationMethodology",
    "ModelStatus",
    "DataQuality",
    "MLPredictionResult",
    "ModelMetrics",
    "TrainingData",
    "ModelConfiguration",
    "EnsembleModel",
    "DeepLearningModel",
    "ReinforcementLearningModel",
    "FeatureImportance",
    "ModelExplanation",
    "DataPreprocessing",
    "ModelValidation",
    "ModelDeployment",
    "ModelMonitoring",
    "TransferLearningConfig",
    "HyperparameterOptimization",
    "ModelComparison",
    "ModelEnsemble",
    "ModelPipeline",
    "ModelArtifact",
    "ModelVersion",
    "ModelRegistry",
    "ModelExperiment",
    "ModelPerformance",
    "ModelRetraining",
]
