
from src.utils.exceptions import (
    CacheError,
    CalculationError,
    DataValidationError,
    ValuationRangeError
)

"""
Model Predictor

This module handles model inference, prediction, and result interpretation.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
from pathlib import Path

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.ml.model_artifact_io import load_trusted_joblib
from ..pipelines.ml_types import (
    MLPredictionResult, ModelExplanation, FeatureImportance,
    MLModelType, ModelMetrics
)

logger = get_logger(__name__)


class ModelPredictor:
    """Handles model inference and prediction"""

    def __init__(self, models_path: str = "models/trained"):
        self.models_path = Path(models_path)
        self.loaded_models = {}
        self.model_metadata = {}

    def load_model(
        self,
        model_id: str,
        version: str,
        model_type: MLModelType
    ) -> bool:
        """Load a model for prediction"""
        try:
            model_dir = self.models_path / model_id / version
            model_path = model_dir / "model.joblib"
            metadata_path = model_dir / "metadata.json"

            if not model_path.exists():
                logger.error(f"Model {model_id} v{version} not found")
                return False

            # Load model from a trusted artifact root only. joblib is pickle-backed.
            model = load_trusted_joblib(model_path, allowed_roots=[self.models_path])

            # Load metadata
            metadata = {}
            if metadata_path.exists():
                import json
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)

            # Load scaler if exists
            scaler = None
            scaler_path = model_dir / "scaler.joblib"
            if scaler_path.exists():
                scaler = load_trusted_joblib(scaler_path, allowed_roots=[self.models_path])

            # Store model info
            model_key = f"{model_id}_{version}"
            self.loaded_models[model_key] = {
                'model': model,
                'scaler': scaler,
                'model_type': model_type,
                'metadata': metadata
            }

            logger.info(f"Loaded model {model_id} v{version} for prediction")
            return True

        except Exception as e:
            logger.error(f"Error loading model {model_id} v{version}: {e}")
            return False

    def predict(
        self,
        model_id: str,
        version: str,
        features: np.ndarray,
        feature_names: List[str],
        return_probabilities: bool = False
    ) -> MLPredictionResult:
        """Make a prediction using a loaded model"""
        try:
            model_key = f"{model_id}_{version}"

            if model_key not in self.loaded_models:
                raise ValueError(f"Model {model_id} v{version} not loaded")

            model_info = self.loaded_models[model_key]
            model = model_info['model']
            scaler = model_info['scaler']
            model_type = model_info['model_type']

            # Prepare features
            if scaler is not None:
                features_scaled = scaler.transform(features.reshape(1, -1))
            else:
                features_scaled = features.reshape(1, -1)

            # Make prediction
            start_time = datetime.now()
            prediction = model.predict(features_scaled)[0]
            prediction_time = datetime.now() - start_time

            # Get confidence/probability if available
            confidence = Decimal('0.0')
            probability = None

            if hasattr(model, 'predict_proba'):
                try:
                    probabilities = model.predict_proba(features_scaled)[0]
                    confidence = to_decimal(np.max(probabilities))
                    probability = to_decimal(probabilities[0]) if len(probabilities) == 2 else None
                except (ValueError, TypeError, AttributeError, IndexError):
                    confidence = Decimal('0.0')
            elif hasattr(model, 'decision_function'):
                try:
                    decision_scores = model.decision_function(features_scaled)[0]
                    confidence = to_decimal(np.abs(decision_scores))
                except (ValueError, TypeError, AttributeError, IndexError):
                    confidence = Decimal('0.0')

            # Create result
            result = MLPredictionResult(
                prediction=prediction,
                confidence=confidence,
                probability=probability,
                model_name=f"{model_id}_v{version}",
                features_used=feature_names,
                prediction_time=prediction_time,
                metadata={
                    'model_type': model_type.value,
                    'prediction_timestamp': datetime.now().isoformat(),
                    'feature_count': len(feature_names)
                }
            )

            logger.info(f"Prediction completed: {prediction} (confidence: {confidence:.3f})")
            return result

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(f"Validation error making prediction: {e}", extra={'error_type': type(e).__name__})
            raise DataValidationError(f"Invalid input for prediction: {e}") from e
        except DataValidationError as e:
            logger.error(f"Error making prediction: {e}", extra={'error_type': type(e).__name__})
            raise CalculationError(
                f"Failed to make prediction: {e}",
                calculation_type="ML Prediction",
                context={'model_id': model_id, 'version': version, 'error_type': type(e).__name__}
            ) from e

    def predict_batch(
        self,
        model_id: str,
        version: str,
        features_batch: np.ndarray,
        feature_names: List[str]
    ) -> List[MLPredictionResult]:
        """Make predictions for a batch of samples"""
        try:
            results = []

            for i, features in enumerate(features_batch):
                result = self.predict(
                    model_id, version, features, feature_names
                )
                result.metadata['batch_index'] = i
                results.append(result)

            logger.info(f"Batch prediction completed: {len(results)} predictions")
            return results

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(f"Validation error in batch prediction: {e}", extra={'error_type': type(e).__name__})
            raise DataValidationError(f"Invalid input for batch prediction: {e}") from e
        except DataValidationError as e:
            logger.error(f"Error in batch prediction: {e}", extra={'error_type': type(e).__name__})
            raise CalculationError(
                f"Failed to make batch prediction: {e}",
                calculation_type="ML Batch Prediction",
                context={'model_id': model_id, 'version': version, 'error_type': type(e).__name__}
            ) from e

    def explain_prediction(
        self,
        model_id: str,
        version: str,
        features: np.ndarray,
        feature_names: List[str]
    ) -> ModelExplanation:
        """Explain a model prediction"""
        try:
            model_key = f"{model_id}_{version}"

            if model_key not in self.loaded_models:
                raise ValueError(f"Model {model_id} v{version} not loaded")

            model_info = self.loaded_models[model_key]
            model = model_info['model']
            scaler = model_info['scaler']

            # Prepare features
            if scaler is not None:
                features_scaled = scaler.transform(features.reshape(1, -1))
            else:
                features_scaled = features.reshape(1, -1)

            # Get feature importance
            feature_contributions = self._get_feature_contributions(
                model, features_scaled[0], feature_names
            )

            # Create explanation
            explanation = ModelExplanation(
                model_id=model_id,
                explanation_type="feature_contribution",
                feature_contributions=feature_contributions,
                decision_path=self._get_decision_path(model, features_scaled[0]),
                confidence_interval=self._get_confidence_interval(
                    model, features_scaled[0]
                ),
                uncertainty_measures=self._get_uncertainty_measures(
                    model, features_scaled[0]
                )
            )

            logger.info(f"Prediction explanation generated for {model_id} v{version}")
            return explanation

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error(f"Validation error explaining prediction: {e}", extra={'error_type': type(e).__name__})
            raise DataValidationError(f"Invalid input for prediction explanation: {e}") from e
        except DataValidationError as e:
            logger.error(f"Error explaining prediction: {e}", extra={'error_type': type(e).__name__})
            raise CalculationError(
                f"Failed to explain prediction: {e}",
                calculation_type="ML Prediction Explanation",
                context={'model_id': model_id, 'version': version, 'error_type': type(e).__name__}
            ) from e

    def _get_feature_contributions(
        self,
        model: Any,
        features: np.ndarray,
        feature_names: List[str]
    ) -> List[FeatureImportance]:
        """Get feature contributions for a prediction"""
        try:
            contributions = []

            if hasattr(model, 'feature_importances_'):
                # Tree-based models
                importances = model.feature_importances_
            elif hasattr(model, 'coef_'):
                # Linear models
                importances = np.abs(model.coef_[0])
            else:
                # Default to equal contribution
                importances = np.ones(len(feature_names)) / len(feature_names)

            # Create contribution objects
            for i, (name, importance) in enumerate(zip(feature_names, importances)):
                contributions.append(FeatureImportance(
                    feature_name=name,
                    importance_score=to_decimal(importance),
                    rank=i + 1,
                    category="contribution"
                ))

            # Sort by importance
            contributions.sort(key=lambda x: x.importance_score, reverse=True)

            # Update ranks
            for i, contrib in enumerate(contributions):
                contrib.rank = i + 1

            return contributions

        except Exception as e:
            logger.error(f"Error getting feature contributions: {e}")
            return []

    def _get_decision_path(
        self,
        model: Any,
        features: np.ndarray
    ) -> List[str]:
        """Get decision path for tree-based models"""
        try:
            if hasattr(model, 'decision_path'):
                # Get decision path for the first tree
                path = model.decision_path(features.reshape(1, -1))
                return [f"Node {node}" for node in path.indices]
            else:
                return ["Linear decision boundary"]

        except ValuationRangeError as e:
            logger.error(f"Error getting decision path: {e}")
            return ["Decision path not available"]

    def _get_confidence_interval(
        self,
        model: Any,
        features: np.ndarray
    ) -> Tuple[float, float]:
        """Get confidence interval for prediction"""
        try:
            if hasattr(model, 'predict_proba'):
                probabilities = model.predict_proba(features.reshape(1, -1))[0]
                max_prob = np.max(probabilities)
                # Simple confidence interval based on probability
                lower = max(0, max_prob - Decimal('0.1'))
                upper = min(1, max_prob + Decimal('0.1'))
                return (lower, upper)
            else:
                # Default confidence interval
                return (Decimal('0.5'), Decimal('0.8'))

        except ValuationRangeError as e:
            logger.error(f"Error getting confidence interval: {e}")
            return (Decimal('0.0'), Decimal('1.0'))

    def _get_uncertainty_measures(
        self,
        model: Any,
        features: np.ndarray
    ) -> Dict[str, Decimal]:
        """Get uncertainty measures for prediction"""
        try:
            uncertainty = {}

            if hasattr(model, 'predict_proba'):
                probabilities = model.predict_proba(features.reshape(1, -1))[0]

                # Entropy as uncertainty measure
                entropy = -np.sum(probabilities * np.log(probabilities + 1e-10))
                uncertainty['entropy'] = to_decimal(entropy)

                # Max probability as confidence
                max_prob = np.max(probabilities)
                uncertainty['max_probability'] = to_decimal(max_prob)

                # Variance as uncertainty
                variance = np.var(probabilities)
                uncertainty['variance'] = to_decimal(variance)

            return uncertainty

        except Exception as e:
            logger.error(f"Error getting uncertainty measures: {e}")
            return {}

    def get_model_info(
        self,
        model_id: str,
        version: str
    ) -> Dict[str, Any]:
        """Get information about a loaded model"""
        try:
            model_key = f"{model_id}_{version}"

            if model_key not in self.loaded_models:
                return {}

            model_info = self.loaded_models[model_key]

            return {
                'model_id': model_id,
                'version': version,
                'model_type': model_info['model_type'].value,
                'metadata': model_info['metadata'],
                'has_scaler': model_info['scaler'] is not None,
                'loaded_at': datetime.now().isoformat()
            }

        except CacheError as e:
            logger.error(f"Error getting model info: {e}")
            return {}

    def unload_model(
        self,
        model_id: str,
        version: str
    ) -> bool:
        """Unload a model from memory"""
        try:
            model_key = f"{model_id}_{version}"

            if model_key in self.loaded_models:
                del self.loaded_models[model_key]
                logger.info(f"Unloaded model {model_id} v{version}")
                return True
            else:
                logger.warning(f"Model {model_id} v{version} not loaded")
                return False

        except Exception as e:
            logger.error(f"Error unloading model: {e}")
            return False

    def get_loaded_models(self) -> List[str]:
        """Get list of loaded models"""
        return list(self.loaded_models.keys())

    def clear_all_models(self) -> int:
        """Clear all loaded models"""
        count = len(self.loaded_models)
        self.loaded_models.clear()
        logger.info(f"Cleared {count} loaded models")
        return count
