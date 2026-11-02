from src.utils.exceptions import BusinessTypeError, ConfigurationError, DataValidationError, DatabaseError

"""
Learning Orchestrator

This module orchestrates the learning pipeline, including training coordination,
model lifecycle management, A/B testing, and continuous learning loops.

Author: Upswitch CTO Team
Date: October 2025
Status: Production Ready
"""

import asyncio
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .learning_types import (
    ModelType, LearningData, TrainingConfig, ModelConfig, ABTestConfig,
    DEFAULT_MODEL_CONFIGS, DEFAULT_AB_TEST_CONFIG, FEATURE_CONFIGS, TARGET_CONFIGS
)
from ..evaluation.performance_tracker import PerformanceTracker

logger = get_logger(__name__)


class LearningOrchestrator:
    """
    Orchestrates the learning pipeline and model lifecycle
    """

    def __init__(self, performance_tracker: Optional[PerformanceTracker] = None):
        """Initialize learning orchestrator"""
        self.performance_tracker = performance_tracker or PerformanceTracker()
        self.model_configs = DEFAULT_MODEL_CONFIGS
        self.ab_test_config = DEFAULT_AB_TEST_CONFIG
        logger.info("✅ LearningOrchestrator initialized")

    async def orchestrate_training_pipeline(
        self,
        training_data: List[LearningData],
        config: TrainingConfig
    ) -> Dict[str, Any]:
        """Orchestrate the complete training pipeline"""

        try:
            logger.info(f"🧠 Orchestrating training pipeline for {config.model_type}")

            # Check data sufficiency
            if len(training_data) < config.min_samples:
                logger.warning(f"⚠️ Insufficient training data: {len(training_data)} samples")
                return self._get_insufficient_data_result(config)

            # Prepare features and targets
            X, y = self._prepare_training_data(training_data, config.model_type)

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=config.test_size, random_state=config.random_state
            )

            # Train model
            model, scaler = self._train_model_instance(
                config.model_type, X_train, y_train
            )

            # Evaluate model
            performance = self.performance_tracker.evaluate_model_performance(
                model, X_test, y_test, config.model_type, scaler
            )

            # Check performance thresholds
            threshold_check = self.performance_tracker.check_performance_thresholds(performance)

            result = {
                "model": model,
                "scaler": scaler,
                "performance": performance,
                "threshold_check": threshold_check,
                "training_samples": len(X_train),
                "test_samples": len(X_test),
                "success": threshold_check["overall_pass"]
            }

            logger.info(f"✅ Training pipeline orchestrated: {config.model_type}")
            return result

        except DataValidationError as e:
            logger.error(f"❌ Training pipeline orchestration failed: {str(e)}")
            return {
                "model": None,
                "scaler": None,
                "performance": None,
                "threshold_check": {"overall_pass": False},
                "training_samples": 0,
                "test_samples": 0,
                "success": False,
                "error": str(e)
            }

    def prepare_training_data(
        self,
        training_data: List[LearningData],
        model_type: ModelType
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare training data for model"""

        try:
            logger.info(f"📊 Preparing training data for {model_type}")

            X = []
            y = []

            for data in training_data:
                # Extract features
                features = self._extract_features(data.input_features, model_type)
                X.append(features)

                # Extract target
                target = self._extract_target(data.output_prediction, model_type)
                y.append(target)

            X_array = np.array(X)
            y_array = np.array(y)

            logger.info(f"✅ Training data prepared: {X_array.shape[0]} samples")
            return X_array, y_array

        except ConfigurationError as e:
            logger.error(f"❌ Training data preparation failed: {str(e)}")
            return np.array([]), np.array([])

    def train_model_instance(
        self,
        model_type: ModelType,
        X_train: np.ndarray,
        y_train: np.ndarray
    ) -> Tuple[Any, Optional[StandardScaler]]:
        """Train model instance with appropriate configuration"""

        try:
            logger.info(f"🧠 Training model instance for {model_type}")

            # Get model configuration
            config = self.model_configs.get(model_type, ModelConfig())

            # Create model based on type
            if model_type == ModelType.METHODOLOGY_SELECTION:
                model = RandomForestClassifier(
                    n_estimators=config.n_estimators,
                    max_depth=config.max_depth,
                    random_state=config.random_state,
                    n_jobs=config.n_jobs
                )
            elif model_type == ModelType.QUESTION_ROUTING:
                model = GradientBoostingClassifier(
                    n_estimators=config.n_estimators,
                    max_depth=config.max_depth,
                    random_state=config.random_state
                )
            elif model_type == ModelType.OWNER_DEPENDENCY:
                model = RandomForestClassifier(
                    n_estimators=config.n_estimators,
                    max_depth=config.max_depth,
                    random_state=config.random_state,
                    n_jobs=config.n_jobs
                )
            elif model_type == ModelType.MARKET_CONTEXT:
                model = RandomForestClassifier(
                    n_estimators=config.n_estimators,
                    max_depth=config.max_depth,
                    random_state=config.random_state,
                    n_jobs=config.n_jobs
                )
            elif model_type == ModelType.VALUATION_ACCURACY:
                model = RandomForestClassifier(
                    n_estimators=config.n_estimators,
                    max_depth=config.max_depth,
                    random_state=config.random_state,
                    n_jobs=config.n_jobs
                )
            else:
                model = RandomForestClassifier(
                    n_estimators=config.n_estimators,
                    random_state=config.random_state
                )

            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)

            # Train model
            model.fit(X_train_scaled, y_train)

            logger.info(f"✅ Model instance trained: {model_type}")
            return model, scaler

        except BusinessTypeError as e:
            logger.error(f"❌ Model instance training failed: {str(e)}")
            return None, None

    async def orchestrate_ab_test(
        self,
        model_type: ModelType,
        business_type: str,
        current_model: Any,
        new_model: Any,
        test_data: List[LearningData]
    ) -> Dict[str, Any]:
        """Orchestrate A/B test between current and new models"""

        try:
            logger.info(f"🧪 Orchestrating A/B test for {model_type} - {business_type}")

            if not test_data:
                return self._get_no_test_data_result()

            # Prepare test data
            X_test, y_test = self._prepare_training_data(test_data, model_type)

            if len(X_test) < self.ab_test_config.min_sample_size:
                return self._get_insufficient_test_data_result()

            # Run comparison
            comparison_results = await self._compare_models(
                current_model, new_model, X_test, y_test, model_type
            )

            # Determine recommendation
            recommendation = self._determine_ab_test_recommendation(comparison_results)

            result = {
                "comparison_results": comparison_results,
                "recommendation": recommendation,
                "test_samples": len(X_test),
                "statistical_significance": comparison_results.get("statistical_significance", False),
                "success": True
            }

            logger.info(f"✅ A/B test orchestrated: {model_type} - {business_type}")
            return result

        except BusinessTypeError as e:
            logger.error(f"❌ A/B test orchestration failed: {str(e)}")
            return {
                "comparison_results": {},
                "recommendation": "keep_current",
                "test_samples": 0,
                "statistical_significance": False,
                "success": False,
                "error": str(e)
            }

    async def orchestrate_continuous_learning(
        self,
        model_type: ModelType,
        business_type: str,
        new_feedback_data: List[LearningData],
        retrain_threshold: int = 100
    ) -> Dict[str, Any]:
        """Orchestrate continuous learning with new feedback"""

        try:
            logger.info(f"🔄 Orchestrating continuous learning for {model_type} - {business_type}")

            # Check if enough new data for retraining
            if len(new_feedback_data) < retrain_threshold:
                return {
                    "retrain_triggered": False,
                    "new_data_count": len(new_feedback_data),
                    "threshold": retrain_threshold,
                    "message": "Insufficient new data for retraining"
                }

            # Prepare retraining data
            X, y = self._prepare_training_data(new_feedback_data, model_type)

            # Train new model
            new_model, scaler = self._train_model_instance(model_type, X, y)

            # Evaluate new model
            performance = self.performance_tracker.evaluate_model_performance(
                new_model, X, y, model_type, scaler
            )

            result = {
                "retrain_triggered": True,
                "new_model": new_model,
                "scaler": scaler,
                "performance": performance,
                "new_data_count": len(new_feedback_data),
                "threshold": retrain_threshold,
                "success": True
            }

            logger.info(f"✅ Continuous learning orchestrated: {model_type} - {business_type}")
            return result

        except DatabaseError as e:
            logger.error(f"❌ Continuous learning orchestration failed: {str(e)}")
            return {
                "retrain_triggered": False,
                "new_data_count": len(new_feedback_data),
                "threshold": retrain_threshold,
                "success": False,
                "error": str(e)
            }

    def _extract_features(self, input_features: Dict[str, Any], model_type: ModelType) -> List[Decimal]:
        """Extract features for model training"""

        try:
            # Get feature configuration
            feature_config = FEATURE_CONFIGS.get(model_type, {
                "common_features": ["revenue", "ebitda", "growth_rate", "owner_dependency", "market_data_quality"],
                "specific_features": []
            })

            # Extract common features
            features = [
                input_features.get(feature, 0.0) 
                for feature in feature_config["common_features"]
            ]

            # Extract specific features
            features.extend([
                input_features.get(feature, 0.0) 
                for feature in feature_config["specific_features"]
            ])

            return features

        except ConfigurationError as e:
            logger.error(f"❌ Feature extraction failed: {str(e)}")
            return [0.0] * 8  # Default feature vector

    def _extract_target(self, output_prediction: Dict[str, Any], model_type: ModelType) -> List[Decimal]:
        """Extract target for model training"""

        try:
            # Get target configuration
            target_config = TARGET_CONFIGS.get(model_type, ["prediction"])

            # Extract targets
            targets = [
                output_prediction.get(target, 0.5) 
                for target in target_config
            ]

            return targets

        except ConfigurationError as e:
            logger.error(f"❌ Target extraction failed: {str(e)}")
            return [0.5]  # Default target

    async def _compare_models(
        self,
        current_model: Any,
        new_model: Any,
        X_test: np.ndarray,
        y_test: np.ndarray,
        model_type: ModelType
    ) -> Dict[str, Any]:
        """Compare current and new models"""

        try:
            # Evaluate current model
            current_performance = self.performance_tracker.evaluate_model_performance(
                current_model, X_test, y_test, model_type
            )

            # Evaluate new model
            new_performance = self.performance_tracker.evaluate_model_performance(
                new_model, X_test, y_test, model_type
            )

            # Calculate improvement
            improvement = new_performance.accuracy - current_performance.accuracy

            # Determine statistical significance (simplified)
            statistical_significance = abs(improvement) > 0.05  # 5% improvement threshold

            return {
                "current_model_performance": current_performance.accuracy,
                "new_model_performance": new_performance.accuracy,
                "improvement": improvement,
                "statistical_significance": statistical_significance,
                "current_metrics": {
                    "accuracy": current_performance.accuracy,
                    "precision": current_performance.precision,
                    "recall": current_performance.recall,
                    "f1_score": current_performance.f1_score
                },
                "new_metrics": {
                    "accuracy": new_performance.accuracy,
                    "precision": new_performance.precision,
                    "recall": new_performance.recall,
                    "f1_score": new_performance.f1_score
                }
            }

        except Exception as e:
            logger.error(f"❌ Model comparison failed: {str(e)}")
            return {
                "current_model_performance": 0.5,
                "new_model_performance": 0.5,
                "improvement": 0.0,
                "statistical_significance": False,
                "error": str(e)
            }

    def _determine_ab_test_recommendation(self, comparison_results: Dict[str, Any]) -> str:
        """Determine A/B test recommendation"""

        try:
            improvement = comparison_results.get("improvement", 0.0)
            statistical_significance = comparison_results.get("statistical_significance", False)

            if improvement > 0.05 and statistical_significance:
                return "deploy_new_model"
            elif improvement > 0.02:
                return "consider_new_model"
            else:
                return "keep_current_model"

        except ConfigurationError as e:
            logger.error(f"❌ A/B test recommendation failed: {str(e)}")
            return "keep_current_model"

    def _get_insufficient_data_result(self, config: TrainingConfig) -> Dict[str, Any]:
        """Get result for insufficient training data"""

        return {
            "model": None,
            "scaler": None,
            "performance": None,
            "threshold_check": {"overall_pass": False},
            "training_samples": 0,
            "test_samples": 0,
            "success": False,
            "error": "insufficient_data",
            "message": f"Need at least {config.min_samples} samples, got {config.min_samples - 1}"
        }

    def _get_no_test_data_result(self) -> Dict[str, Any]:
        """Get result for no test data"""

        return {
            "comparison_results": {},
            "recommendation": "keep_current",
            "test_samples": 0,
            "statistical_significance": False,
            "success": False,
            "error": "no_test_data"
        }

    def _get_insufficient_test_data_result(self) -> Dict[str, Any]:
        """Get result for insufficient test data"""

        return {
            "comparison_results": {},
            "recommendation": "keep_current",
            "test_samples": 0,
            "statistical_significance": False,
            "success": False,
            "error": "insufficient_test_data",
            "message": f"Need at least {self.ab_test_config.min_sample_size} test samples"
        }
