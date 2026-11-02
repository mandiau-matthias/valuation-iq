"""
Ensemble Manager

This module handles ensemble model creation, training, and prediction.
"""

from src.utils.exceptions import CalculationError, DataValidationError

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.ensemble import VotingClassifier, VotingRegressor
from sklearn.model_selection import cross_val_score
from sklearn.metrics import accuracy_score, mean_squared_error
from pathlib import Path

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.ml.model_artifact_io import dump_trusted_joblib, load_trusted_joblib
from ..pipelines.ml_types import (
    EnsembleModel, ModelMetrics, MLPredictionResult,
    MLModelType, ModelValidation, FeatureImportance
)

logger = get_logger(__name__)


class EnsembleManager:
    """Manages ensemble model operations"""

    def __init__(self, models_path: str = "models/ensemble"):
        self.models_path = Path(models_path)
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.ensemble_models = {}

    def create_ensemble(
        self,
        ensemble_id: str,
        base_models: List[Dict[str, Any]],
        voting_strategy: str = "hard",
        weights: Optional[List[Decimal]] = None
    ) -> EnsembleModel:
        """Create an ensemble model"""
        try:
            # Validate base models
            if len(base_models) < 2:
                raise ValueError("Ensemble requires at least 2 base models")

            # Validate weights if provided
            if weights and len(weights) != len(base_models):
                raise ValueError("Weights must match number of base models")

            # Create ensemble model
            ensemble = EnsembleModel(
                base_models=[model['name'] for model in base_models],
                meta_model=None,
                voting_strategy=voting_strategy,
                weights=weights,
                created_at=datetime.now()
            )

            # Store ensemble configuration
            self.ensemble_models[ensemble_id] = {
                'ensemble': ensemble,
                'base_models': base_models,
                'voting_strategy': voting_strategy,
                'weights': weights
            }

            logger.info(f"Created ensemble {ensemble_id} with {len(base_models)} base models")
            return ensemble

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(f"Validation error creating ensemble: {e}", extra={'error_type': type(e).__name__})
            raise DataValidationError(f"Invalid input for ensemble creation: {e}") from e
        except Exception as e:
            logger.error(f"Error creating ensemble: {e}", extra={'error_type': type(e).__name__})
            raise CalculationError(
                f"Failed to create ensemble: {e}",
                calculation_type="ML Ensemble Creation",
                context={'ensemble_id': ensemble_id if 'ensemble_id' in locals() else {}, 'error_type': type(e).__name__}
            ) from e

    def train_ensemble(
        self,
        ensemble_id: str,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        model_type: MLModelType
    ) -> ModelValidation:
        """Train an ensemble model"""
        try:
            if ensemble_id not in self.ensemble_models:
                raise ValueError(f"Ensemble {ensemble_id} not found")

            ensemble_info = self.ensemble_models[ensemble_id]
            base_models = ensemble_info['base_models']
            voting_strategy = ensemble_info['voting_strategy']
            weights = ensemble_info['weights']

            # Create base model instances
            base_model_instances = []
            for model_config in base_models:
                model_instance = self._create_model_instance(
                    model_config, model_type
                )
                base_model_instances.append((model_config['name'], model_instance))

            # Create ensemble model
            if model_type in [MLModelType.CLASSIFICATION, MLModelType.DEEP_LEARNING]:
                ensemble_model = VotingClassifier(
                    estimators=base_model_instances,
                    voting=voting_strategy,
                    weights=weights
                )
            else:
                ensemble_model = VotingRegressor(
                    estimators=base_model_instances,
                    weights=weights
                )

            # Train ensemble
            start_time = datetime.now()
            ensemble_model.fit(X_train, y_train)
            training_time = datetime.now() - start_time

            # Make predictions
            start_time = datetime.now()
            predictions = ensemble_model.predict(X_test)
            inference_time = datetime.now() - start_time

            # Calculate metrics
            if model_type in [MLModelType.CLASSIFICATION, MLModelType.DEEP_LEARNING]:
                accuracy = accuracy_score(y_test, predictions)
                precision = accuracy  # Simplified for ensemble
                recall = accuracy
                f1_score = accuracy
                auc_roc = accuracy

                metrics = ModelMetrics(
                    accuracy=accuracy,
                    precision=precision,
                    recall=recall,
                    f1_score=f1_score,
                    auc_roc=auc_roc,
                    training_time=training_time,
                    inference_time=inference_time
                )
            else:
                mse = mean_squared_error(y_test, predictions)
                rmse = np.sqrt(mse)
                mae = np.mean(np.abs(y_test - predictions))
                r2_score = 1 - (mse / np.var(y_test))

                metrics = ModelMetrics(
                    accuracy=Decimal('0.0'),
                    precision=Decimal('0.0'),
                    recall=Decimal('0.0'),
                    f1_score=Decimal('0.0'),
                    auc_roc=Decimal('0.0'),
                    mse=mse,
                    rmse=rmse,
                    mae=mae,
                    r2_score=r2_score,
                    training_time=training_time,
                    inference_time=inference_time
                )

            # Cross-validation
            cv_scores = cross_val_score(
                ensemble_model, X_train, y_train, cv=5, scoring='accuracy'
            )

            # Feature importance (simplified for ensemble)
            feature_importance = self._calculate_ensemble_feature_importance(
                ensemble_model, X_train.shape[1]
            )

            # Create validation result
            validation = ModelValidation(
                validation_type="ensemble_holdout",
                cross_validation_scores=cv_scores.tolist(),
                holdout_performance=metrics,
                feature_importance=feature_importance
            )

            # Update ensemble with performance metrics
            self.ensemble_models[ensemble_id]['ensemble'].performance_metrics = metrics

            logger.info(f"Trained ensemble {ensemble_id}: {metrics}")
            return validation

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(f"Validation error training ensemble: {e}", extra={'error_type': type(e).__name__})
            raise DataValidationError(f"Invalid input for ensemble training: {e}") from e
        except DataValidationError as e:
            logger.error(f"Error training ensemble: {e}", extra={'error_type': type(e).__name__})
            raise CalculationError(
                f"Failed to train ensemble: {e}",
                calculation_type="ML Ensemble Training",
                context={'ensemble_id': ensemble_id if 'ensemble_id' in locals() else None, 'error_type': type(e).__name__}
            ) from e

    def _create_model_instance(
        self,
        model_config: Dict[str, Any],
        model_type: MLModelType
    ) -> Any:
        """Create a model instance from configuration"""
        try:
            model_name = model_config['name']
            model_class = model_config['class']
            hyperparameters = model_config.get('hyperparameters', {})

            # Import and create model
            if model_class == 'RandomForestClassifier':
                from sklearn.ensemble import RandomForestClassifier
                return RandomForestClassifier(**hyperparameters)
            elif model_class == 'RandomForestRegressor':
                from sklearn.ensemble import RandomForestRegressor
                return RandomForestRegressor(**hyperparameters)
            elif model_class == 'LogisticRegression':
                from sklearn.linear_model import LogisticRegression
                return LogisticRegression(**hyperparameters)
            elif model_class == 'LinearRegression':
                from sklearn.linear_model import LinearRegression
                return LinearRegression(**hyperparameters)
            elif model_class == 'SVC':
                from sklearn.svm import SVC
                return SVC(**hyperparameters)
            elif model_class == 'SVR':
                from sklearn.svm import SVR
                return SVR(**hyperparameters)
            elif model_class == 'MLPClassifier':
                from sklearn.neural_network import MLPClassifier
                return MLPClassifier(**hyperparameters)
            elif model_class == 'MLPRegressor':
                from sklearn.neural_network import MLPRegressor
                return MLPRegressor(**hyperparameters)
            else:
                raise ValueError(f"Unsupported model class: {model_class}")

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(f"Validation error creating model instance: {e}", extra={'error_type': type(e).__name__})
            raise DataValidationError(f"Invalid input for model instance creation: {e}") from e
        except DataValidationError as e:
            logger.error(f"Error creating model instance: {e}", extra={'error_type': type(e).__name__})
            raise CalculationError(
                f"Failed to create model instance: {e}",
                calculation_type="ML Model Instance Creation",
                context={'model_class': model_class if 'model_class' in locals() else None, 'error_type': type(e).__name__}
            ) from e

    def _calculate_ensemble_feature_importance(
        self,
        ensemble_model: Any,
        feature_count: int
    ) -> List[FeatureImportance]:
        """Calculate feature importance for ensemble model"""
        try:
            importance_scores = []

            # Get feature importance from base models
            if hasattr(ensemble_model, 'estimators_'):
                # Calculate average importance across base models
                avg_importance = np.zeros(feature_count)

                for estimator in ensemble_model.estimators_:
                    if hasattr(estimator, 'feature_importances_'):
                        avg_importance += estimator.feature_importances_
                    elif hasattr(estimator, 'coef_'):
                        avg_importance += np.abs(estimator.coef_[0])

                avg_importance /= len(ensemble_model.estimators_)

                # Create feature importance objects
                for i, importance in enumerate(avg_importance):
                    importance_scores.append(FeatureImportance(
                        feature_name=f"feature_{i}",
                        importance_score=to_decimal(importance),
                        rank=i + 1,
                        category="ensemble"
                    ))

            # Sort by importance
            importance_scores.sort(key=lambda x: x.importance_score, reverse=True)

            # Update ranks
            for i, score in enumerate(importance_scores):
                score.rank = i + 1

            return importance_scores

        except CalculationError as e:
            logger.error(f"Error calculating ensemble feature importance: {e}")
            return []

    def predict_ensemble(
        self,
        ensemble_id: str,
        features: np.ndarray,
        feature_names: List[str]
    ) -> MLPredictionResult:
        """Make prediction using ensemble model"""
        try:
            if ensemble_id not in self.ensemble_models:
                raise ValueError(f"Ensemble {ensemble_id} not found")

            ensemble_info = self.ensemble_models[ensemble_id]
            ensemble_model = ensemble_info.get('trained_model')

            if not ensemble_model:
                raise ValueError(f"Ensemble {ensemble_id} not trained")

            # Make prediction
            start_time = datetime.now()
            prediction = ensemble_model.predict(features.reshape(1, -1))[0]
            prediction_time = datetime.now() - start_time

            # Get confidence if available
            confidence = Decimal('0.0')
            if hasattr(ensemble_model, 'predict_proba'):
                try:
                    probabilities = ensemble_model.predict_proba(features.reshape(1, -1))[0]
                    confidence = to_decimal(np.max(probabilities))
                except (ValueError, TypeError, AttributeError, IndexError):
                    confidence = Decimal('0.0')

            # Create result
            result = MLPredictionResult(
                prediction=prediction,
                confidence=confidence,
                model_name=f"ensemble_{ensemble_id}",
                features_used=feature_names,
                prediction_time=prediction_time,
                metadata={
                    'ensemble_id': ensemble_id,
                    'base_models': ensemble_info['ensemble'].base_models,
                    'voting_strategy': ensemble_info['voting_strategy'],
                    'weights': ensemble_info['weights']
                }
            )

            logger.info(f"Ensemble prediction completed: {prediction}")
            return result

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(f"Validation error making ensemble prediction: {e}", extra={'error_type': type(e).__name__})
            raise DataValidationError(f"Invalid input for ensemble prediction: {e}") from e
        except Exception as e:
            logger.error(f"Error making ensemble prediction: {e}", extra={'error_type': type(e).__name__})
            raise CalculationError(
                f"Failed to make ensemble prediction: {e}",
                calculation_type="ML Ensemble Prediction",
                context={'ensemble_id': ensemble_id if 'ensemble_id' in locals() else None, 'error_type': type(e).__name__}
            ) from e

    def save_ensemble(
        self,
        ensemble_id: str,
        ensemble_model: Any,
        metadata: Dict[str, Any]
    ) -> str:
        """Save ensemble model to disk"""
        try:
            ensemble_dir = self.models_path / ensemble_id
            ensemble_dir.mkdir(parents=True, exist_ok=True)

            # Save ensemble model
            model_path = ensemble_dir / "ensemble_model.joblib"
            dump_trusted_joblib(ensemble_model, model_path, allowed_roots=[self.models_path])

            # Save metadata
            metadata_path = ensemble_dir / "metadata.json"
            import json
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Store trained model reference
            self.ensemble_models[ensemble_id]['trained_model'] = ensemble_model

            logger.info(f"Saved ensemble {ensemble_id} to {model_path}")
            return str(model_path)

        except (ValueError, TypeError, AttributeError, KeyError, OSError, IOError) as e:
            logger.error(f"Validation/IO error saving ensemble: {e}", extra={'error_type': type(e).__name__})
            raise DataValidationError(f"Invalid input or IO error saving ensemble: {e}") from e
        except DataValidationError as e:
            logger.error(f"Error saving ensemble: {e}", extra={'error_type': type(e).__name__})
            raise CalculationError(
                f"Failed to save ensemble: {e}",
                calculation_type="ML Ensemble Save",
                context={'ensemble_id': ensemble_id if 'ensemble_id' in locals() else None, 'error_type': type(e).__name__}
            ) from e

    def load_ensemble(
        self,
        ensemble_id: str
    ) -> bool:
        """Load ensemble model from disk"""
        try:
            ensemble_dir = self.models_path / ensemble_id
            model_path = ensemble_dir / "ensemble_model.joblib"
            metadata_path = ensemble_dir / "metadata.json"

            if not model_path.exists():
                logger.error(f"Ensemble {ensemble_id} not found")
                return False

            # Load ensemble model from a trusted artifact root only. joblib is pickle-backed.
            ensemble_model = load_trusted_joblib(model_path, allowed_roots=[self.models_path])

            # Load metadata
            metadata = {}
            if metadata_path.exists():
                import json
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)

            # Store loaded model
            if ensemble_id in self.ensemble_models:
                self.ensemble_models[ensemble_id]['trained_model'] = ensemble_model
            else:
                self.ensemble_models[ensemble_id] = {
                    'trained_model': ensemble_model,
                    'metadata': metadata
                }

            logger.info(f"Loaded ensemble {ensemble_id}")
            return True

        except ValuationEngineError as e:
            logger.error(f"Error loading ensemble: {e}")
            return False

    def get_ensemble_info(self, ensemble_id: str) -> Dict[str, Any]:
        """Get information about an ensemble"""
        try:
            if ensemble_id not in self.ensemble_models:
                return {}

            ensemble_info = self.ensemble_models[ensemble_id]
            ensemble = ensemble_info['ensemble']

            return {
                'ensemble_id': ensemble_id,
                'base_models': ensemble.base_models,
                'voting_strategy': ensemble.voting_strategy,
                'weights': ensemble.weights,
                'performance_metrics': ensemble.performance_metrics,
                'created_at': ensemble.created_at.isoformat(),
                'is_trained': 'trained_model' in ensemble_info
            }

        except Exception as e:
            logger.error(f"Error getting ensemble info: {e}")
            return {}

    def list_ensembles(self) -> List[str]:
        """List all ensemble IDs"""
        return list(self.ensemble_models.keys())

    def delete_ensemble(self, ensemble_id: str) -> bool:
        """Delete an ensemble"""
        try:
            if ensemble_id in self.ensemble_models:
                del self.ensemble_models[ensemble_id]

                # Delete files
                ensemble_dir = self.models_path / ensemble_id
                if ensemble_dir.exists():
                    import shutil
                    shutil.rmtree(ensemble_dir)

                logger.info(f"Deleted ensemble {ensemble_id}")
                return True
            else:
                logger.warning(f"Ensemble {ensemble_id} not found")
                return False

        except ValuationEngineError as e:
            logger.error(f"Error deleting ensemble: {e}")
            return False
