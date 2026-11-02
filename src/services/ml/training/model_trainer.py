from src.utils.exceptions import (
    CalculationError,
    ConfigurationError,
    DataQualityError,
    DataValidationError,
)

"""
Model Trainer

This module handles model training, validation, and performance evaluation.
"""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from src.services.ml.model_artifact_io import dump_trusted_joblib, load_trusted_joblib
from src.utils.logging import get_logger

from ..pipelines.ml_types import (
    DataQuality,
    FeatureImportance,
    MLModelType,
    ModelMetrics,
    ModelValidation,
    TrainingData,
)
from .data_quality_assessment import assess_training_data_quality

logger = get_logger(__name__)


class ModelTrainer:
    """Handles model training and validation"""

    def __init__(self, models_path: str = "models/trained"):
        from sklearn.preprocessing import LabelEncoder, StandardScaler

        self.models_path = Path(models_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()

    def prepare_training_data(
        self,
        features: np.ndarray,
        labels: np.ndarray,
        feature_names: List[str],
        test_size: Decimal = Decimal("0.2"),
        random_state: int = 42,
    ) -> Tuple[TrainingData, TrainingData]:
        """Prepare training and validation data"""
        try:
            from sklearn.model_selection import train_test_split

            # Split the data
            X_train, X_test, y_train, y_test = train_test_split(
                features, labels, test_size=test_size, random_state=random_state
            )

            # Create training data objects
            train_data = TrainingData(
                features=X_train,
                labels=y_train,
                feature_names=feature_names,
                data_quality=self._assess_data_quality(X_train, y_train),
                sample_count=len(X_train),
                feature_count=X_train.shape[1],
                created_at=datetime.now(),
            )

            test_data = TrainingData(
                features=X_test,
                labels=y_test,
                feature_names=feature_names,
                data_quality=self._assess_data_quality(X_test, y_test),
                sample_count=len(X_test),
                feature_count=X_test.shape[1],
                created_at=datetime.now(),
            )

            logger.info(
                f"Prepared training data: {len(X_train)} samples, {X_train.shape[1]} features"
            )
            return train_data, test_data

        except DataQualityError as e:
            logger.error(f"Error preparing training data: {e}")
            raise

    def _assess_data_quality(self, features: np.ndarray, labels: np.ndarray) -> DataQuality:
        """Assess the quality of the training data"""
        try:
            return assess_training_data_quality(features)

        except (DataQualityError, TypeError, ValueError, FloatingPointError) as e:
            logger.error(f"Error assessing data quality: {e}")
            return DataQuality.POOR

    def train_classification_model(
        self, train_data: TrainingData, model_type: MLModelType, hyperparameters: Dict[str, Any]
    ) -> Any:
        """Train a classification model"""
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.neural_network import MLPClassifier

            if model_type == MLModelType.CLASSIFICATION:
                model = RandomForestClassifier(**hyperparameters)
            elif model_type == MLModelType.DEEP_LEARNING:
                model = MLPClassifier(**hyperparameters)
            elif model_type == MLModelType.ENSEMBLE:
                model = RandomForestClassifier(**hyperparameters)
            else:
                raise ValueError(f"Unsupported model type for classification: {model_type}")

            # Scale features if needed
            if model_type == MLModelType.DEEP_LEARNING:
                X_scaled = self.scaler.fit_transform(train_data.features)
            else:
                X_scaled = train_data.features

            # Train the model
            start_time = datetime.now()
            model.fit(X_scaled, train_data.labels)
            training_time = datetime.now() - start_time

            logger.info(f"Trained {model_type.value} model in {training_time}")
            return model

        except ConfigurationError as e:
            logger.error(f"Error training classification model: {e}")
            raise

    def train_regression_model(
        self, train_data: TrainingData, model_type: MLModelType, hyperparameters: Dict[str, Any]
    ) -> Any:
        """Train a regression model"""
        try:
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.neural_network import MLPRegressor

            if model_type == MLModelType.REGRESSION:
                model = RandomForestRegressor(**hyperparameters)
            elif model_type == MLModelType.DEEP_LEARNING:
                model = MLPRegressor(**hyperparameters)
            elif model_type == MLModelType.ENSEMBLE:
                model = RandomForestRegressor(**hyperparameters)
            else:
                raise ValueError(f"Unsupported model type for regression: {model_type}")

            # Scale features if needed
            if model_type == MLModelType.DEEP_LEARNING:
                X_scaled = self.scaler.fit_transform(train_data.features)
            else:
                X_scaled = train_data.features

            # Train the model
            start_time = datetime.now()
            model.fit(X_scaled, train_data.labels)
            training_time = datetime.now() - start_time

            logger.info(f"Trained {model_type.value} model in {training_time}")
            return model

        except DataValidationError as e:
            logger.error(f"Error training regression model: {e}")
            raise

    def validate_model(
        self, model: Any, test_data: TrainingData, model_type: MLModelType
    ) -> ModelValidation:
        """Validate a trained model"""
        try:
            from sklearn.metrics import (
                accuracy_score,
                f1_score,
                mean_absolute_error,
                mean_squared_error,
                precision_score,
                r2_score,
                recall_score,
                roc_auc_score,
            )

            # Prepare test data
            if model_type == MLModelType.DEEP_LEARNING:
                X_test = self.scaler.transform(test_data.features)
            else:
                X_test = test_data.features

            # Make predictions
            start_time = datetime.now()
            predictions = model.predict(X_test)
            inference_time = datetime.now() - start_time

            # Calculate metrics
            if model_type in [MLModelType.CLASSIFICATION, MLModelType.DEEP_LEARNING]:
                # Classification metrics
                accuracy = accuracy_score(test_data.labels, predictions)
                precision = precision_score(test_data.labels, predictions, average="weighted")
                recall = recall_score(test_data.labels, predictions, average="weighted")
                f1 = f1_score(test_data.labels, predictions, average="weighted")

                # ROC AUC (if binary classification)
                if len(np.unique(test_data.labels)) == 2:
                    try:
                        auc_roc = roc_auc_score(test_data.labels, predictions)
                    except (ValueError, TypeError, AttributeError):
                        auc_roc = Decimal("0.0")
                else:
                    auc_roc = Decimal("0.0")

                metrics = ModelMetrics(
                    accuracy=accuracy,
                    precision=precision,
                    recall=recall,
                    f1_score=f1,
                    auc_roc=auc_roc,
                    inference_time=inference_time,
                )

            else:
                # Regression metrics
                mse = mean_squared_error(test_data.labels, predictions)
                rmse = np.sqrt(mse)
                mae = mean_absolute_error(test_data.labels, predictions)
                r2 = r2_score(test_data.labels, predictions)

                metrics = ModelMetrics(
                    accuracy=Decimal("0.0"),  # Not applicable for regression
                    precision=Decimal("0.0"),
                    recall=Decimal("0.0"),
                    f1_score=Decimal("0.0"),
                    auc_roc=Decimal("0.0"),
                    mse=mse,
                    rmse=rmse,
                    mae=mae,
                    r2_score=r2,
                    inference_time=inference_time,
                )

            # Cross-validation scores
            cv_scores = self._cross_validate_model(model, test_data, model_type)

            # Feature importance
            feature_importance = self._calculate_feature_importance(
                model, test_data.feature_names, model_type
            )

            validation = ModelValidation(
                validation_type="holdout",
                cross_validation_scores=cv_scores,
                holdout_performance=metrics,
                feature_importance=feature_importance,
            )

            logger.info(f"Model validation completed: {metrics}")
            return validation

        except DataValidationError as e:
            logger.error(f"Error validating model: {e}")
            raise

    def _cross_validate_model(
        self, model: Any, test_data: TrainingData, model_type: MLModelType
    ) -> List[Decimal]:
        """Perform cross-validation"""
        try:
            from sklearn.model_selection import cross_val_score

            if model_type == MLModelType.DEEP_LEARNING:
                X_scaled = self.scaler.transform(test_data.features)
            else:
                X_scaled = test_data.features

            # Use appropriate scoring metric based on model type
            if model_type in [MLModelType.CLASSIFICATION, MLModelType.DEEP_LEARNING]:
                scoring = "accuracy"
            else:
                scoring = "r2"  # For regression models

            cv_scores = cross_val_score(model, X_scaled, test_data.labels, cv=5, scoring=scoring)

            return cv_scores.tolist()

        except DataValidationError as e:
            logger.error(f"Error in cross-validation: {e}")
            return []

    def _calculate_feature_importance(
        self, model: Any, feature_names: List[str], model_type: MLModelType
    ) -> List[FeatureImportance]:
        """Calculate feature importance"""
        try:
            from src.utils.decimal_helpers import to_decimal

            importance_scores = []

            if hasattr(model, "feature_importances_"):
                importances = model.feature_importances_
            elif hasattr(model, "coef_"):
                importances = np.abs(model.coef_[0])
            else:
                # Default to equal importance if not available
                importances = np.ones(len(feature_names)) / len(feature_names)

            # Create feature importance objects
            for i, (name, importance) in enumerate(zip(feature_names, importances)):
                importance_scores.append(
                    FeatureImportance(
                        feature_name=name,
                        importance_score=to_decimal(importance),
                        rank=i + 1,
                        category="feature",
                    )
                )

            # Sort by importance
            importance_scores.sort(key=lambda x: x.importance_score, reverse=True)

            # Update ranks
            for i, score in enumerate(importance_scores):
                score.rank = i + 1

            return importance_scores

        except CalculationError as e:
            logger.error(f"Error calculating feature importance: {e}")
            return []

    def save_model(self, model: Any, model_id: str, version: str, metadata: Dict[str, Any]) -> str:
        """Save a trained model to disk"""
        try:
            model_dir = self.models_path / model_id / version
            model_dir.mkdir(parents=True, exist_ok=True)

            # Save the model
            model_path = model_dir / "model.joblib"
            dump_trusted_joblib(model, model_path, allowed_roots=[self.models_path])

            # Save metadata
            metadata_path = model_dir / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            # Save scaler if it was fitted (check if it has mean_ attribute)
            if (
                hasattr(self, "scaler")
                and self.scaler is not None
                and hasattr(self.scaler, "mean_")
            ):
                scaler_path = model_dir / "scaler.joblib"
                dump_trusted_joblib(self.scaler, scaler_path, allowed_roots=[self.models_path])

            logger.info(f"Saved model {model_id} v{version} to {model_path}")
            return str(model_path)

        except DataValidationError as e:
            logger.error(f"Error saving model: {e}")
            raise

    def load_model(self, model_id: str, version: str) -> Tuple[Any, Dict[str, Any]]:
        """Load a trained model from disk"""
        try:
            model_dir = self.models_path / model_id / version
            model_path = model_dir / "model.joblib"
            metadata_path = model_dir / "metadata.json"

            if not model_path.exists():
                raise FileNotFoundError(f"Model {model_id} v{version} not found")

            # Load model from a trusted artifact root only. joblib is pickle-backed.
            model = load_trusted_joblib(model_path, allowed_roots=[self.models_path])

            # Load metadata
            metadata = {}
            if metadata_path.exists():
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)

            # Load scaler if exists
            scaler_path = model_dir / "scaler.joblib"
            if scaler_path.exists():
                self.scaler = load_trusted_joblib(scaler_path, allowed_roots=[self.models_path])

            logger.info(f"Loaded model {model_id} v{version}")
            return model, metadata

        except DataValidationError as e:
            logger.error(f"Error loading model: {e}")
            raise

    def get_model_performance_summary(self, validation: ModelValidation) -> Dict[str, Any]:
        """Get a summary of model performance"""
        try:
            metrics = validation.holdout_performance

            summary = {
                "accuracy": metrics.accuracy,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
                "auc_roc": metrics.auc_roc,
                "mse": metrics.mse,
                "rmse": metrics.rmse,
                "mae": metrics.mae,
                "r2_score": metrics.r2_score,
                "cross_validation_mean": np.mean(validation.cross_validation_scores),
                "cross_validation_std": np.std(validation.cross_validation_scores),
                "top_features": [
                    {"name": f.feature_name, "importance": f.importance_score, "rank": f.rank}
                    for f in validation.feature_importance[:5]
                ],
            }

            return summary

        except DataValidationError as e:
            logger.error(f"Error getting performance summary: {e}")
            return {}
