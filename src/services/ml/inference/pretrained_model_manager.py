from src.utils.exceptions import CacheError, ConfigurationError, DataValidationError

"""
Pre-trained Model Manager

This module manages pre-trained models for transfer learning, including
model registry, loading, caching, and transfer ability scoring.

Author: Upswitch CTO Team
Date: October 2025
Status: Production Ready
"""

import os
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import json

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.ml.model_artifact_io import load_trusted_joblib
from ..training.transfer_learning_types import (
    PreTrainedModel, TransferLearningTask, DEFAULT_PRETRAINED_MODELS
)

logger = get_logger(__name__)


class PreTrainedModelManager:
    """Manages pre-trained models for transfer learning"""

    def __init__(self, model_cache_dir: str = "models/pretrained"):
        """Initialize pre-trained model manager"""
        self.model_cache_dir = model_cache_dir
        self.model_registry = {}
        self.model_cache = {}
        self.feature_extractors = {}
        self.transfer_scores = {}

        # Ensure cache directory exists
        os.makedirs(self.model_cache_dir, exist_ok=True)

        # Initialize with default models
        self._initialize_default_models()

        logger.info("✅ PreTrainedModelManager initialized")

    def _initialize_default_models(self):
        """Initialize default pre-trained models"""

        try:
            logger.info("🔄 Initializing default pre-trained models")

            for model_name, model_config in DEFAULT_PRETRAINED_MODELS.items():
                self.model_registry[model_name] = model_config
                logger.info(f"📦 Registered model: {model_name}")

            logger.info(f"✅ Initialized {len(self.model_registry)} default models")

        except DataValidationError as e:
            logger.error(f"❌ Default model initialization failed: {str(e)}")

    def register_model(self, model: PreTrainedModel) -> bool:
        """Register a new pre-trained model"""

        try:
            logger.info(f"📦 Registering model: {model.name}")

            # Validate model configuration
            if not self._validate_model_config(model):
                logger.error(f"❌ Invalid model configuration: {model.name}")
                return False

            # Add to registry
            self.model_registry[model.name] = model

            # Compute transfer ability score if not provided
            if model.transfer_ability_score == 0.0:
                model.transfer_ability_score = self._compute_transfer_ability_score(model)

            logger.info(f"✅ Model registered: {model.name}")
            return True

        except ValuationEngineError as e:
            logger.error(f"❌ Model registration failed: {str(e)}")
            return False

    def get_model(self, model_name: str) -> Optional[PreTrainedModel]:
        """Get pre-trained model by name"""

        try:
            if model_name in self.model_registry:
                return self.model_registry[model_name]
            else:
                logger.warning(f"⚠️ Model not found: {model_name}")
                return None

        except DataValidationError as e:
            logger.error(f"❌ Model retrieval failed: {str(e)}")
            return None

    def load_model(self, model_name: str, force_reload: bool = False) -> Optional[Any]:
        """Load pre-trained model from disk"""

        try:
            logger.info(f"📂 Loading model: {model_name}")

            # Check cache first
            if not force_reload and model_name in self.model_cache:
                logger.info(f"✅ Model loaded from cache: {model_name}")
                return self.model_cache[model_name]

            # Get model configuration
            model_config = self.get_model(model_name)
            if not model_config:
                logger.error(f"❌ Model configuration not found: {model_name}")
                return None

            # Load model from file
            if os.path.exists(model_config.model_path):
                model = load_trusted_joblib(
                    model_config.model_path,
                    allowed_roots=[self.model_cache_dir],
                )
                self.model_cache[model_name] = model
                logger.info(f"✅ Model loaded from disk: {model_name}")
                return model
            else:
                logger.warning(f"⚠️ Model file not found: {model_config.model_path}")
                return self._create_mock_model(model_config)

        except DataValidationError as e:
            logger.error(f"❌ Model loading failed: {str(e)}")
            return None

    def load_feature_extractor(self, model_name: str, force_reload: bool = False) -> Optional[Any]:
        """Load feature extractor for pre-trained model"""

        try:
            logger.info(f"📂 Loading feature extractor: {model_name}")

            # Check cache first
            if not force_reload and model_name in self.feature_extractors:
                logger.info(f"✅ Feature extractor loaded from cache: {model_name}")
                return self.feature_extractors[model_name]

            # Get model configuration
            model_config = self.get_model(model_name)
            if not model_config:
                logger.error(f"❌ Model configuration not found: {model_name}")
                return None

            # Load feature extractor from file
            if os.path.exists(model_config.feature_extractor_path):
                feature_extractor = load_trusted_joblib(
                    model_config.feature_extractor_path,
                    allowed_roots=[self.model_cache_dir],
                )
                self.feature_extractors[model_name] = feature_extractor
                logger.info(f"✅ Feature extractor loaded from disk: {model_name}")
                return feature_extractor
            else:
                logger.warning(f"⚠️ Feature extractor file not found: {model_config.feature_extractor_path}")
                return self._create_mock_feature_extractor(model_config)

        except ConfigurationError as e:
            logger.error(f"❌ Feature extractor loading failed: {str(e)}")
            return None

    def get_best_model_for_task(
        self,
        task: TransferLearningTask,
        min_transfer_score: Decimal = Decimal('0.5')
    ) -> Optional[PreTrainedModel]:
        """Get best pre-trained model for specific task"""

        try:
            logger.info(f"🔍 Finding best model for task: {task}")

            suitable_models = []

            for model_name, model_config in self.model_registry.items():
                # Check if model is suitable for task
                if self._is_model_suitable_for_task(model_config, task):
                    # Check transfer ability score
                    if model_config.transfer_ability_score >= min_transfer_score:
                        suitable_models.append((model_config, model_config.transfer_ability_score))

            if not suitable_models:
                logger.warning(f"⚠️ No suitable models found for task: {task}")
                return None

            # Sort by transfer ability score
            suitable_models.sort(key=lambda x: x[1], reverse=True)
            best_model = suitable_models[0][0]

            logger.info(f"✅ Best model for {task}: {best_model.name} (score: {best_model.transfer_ability_score:.3f})")
            return best_model

        except ValuationEngineError as e:
            logger.error(f"❌ Best model selection failed: {str(e)}")
            return None

    def get_all_models(self) -> List[PreTrainedModel]:
        """Get all registered models"""

        try:
            models = list(self.model_registry.values())
            logger.info(f"📦 Retrieved {len(models)} models")
            return models

        except ValuationEngineError as e:
            logger.error(f"❌ Model list retrieval failed: {str(e)}")
            return []

    def get_models_by_domain(self, domain: str) -> List[PreTrainedModel]:
        """Get models by source domain"""

        try:
            logger.info(f"🔍 Finding models for domain: {domain}")

            domain_models = [
                model for model in self.model_registry.values()
                if model.source_domain == domain
            ]

            logger.info(f"✅ Found {len(domain_models)} models for domain: {domain}")
            return domain_models

        except ValuationEngineError as e:
            logger.error(f"❌ Domain model search failed: {str(e)}")
            return []

    def update_model_performance(
        self,
        model_name: str,
        performance_metrics: Dict[str, Decimal]
    ) -> bool:
        """Update model performance metrics"""

        try:
            logger.info(f"📊 Updating performance for model: {model_name}")

            if model_name not in self.model_registry:
                logger.error(f"❌ Model not found: {model_name}")
                return False

            # Update performance metrics
            model = self.model_registry[model_name]
            model.performance_metrics.update(performance_metrics)
            model.last_updated = datetime.now()

            # Recompute transfer ability score
            model.transfer_ability_score = self._compute_transfer_ability_score(model)

            logger.info(f"✅ Performance updated for model: {model_name}")
            return True

        except ValuationEngineError as e:
            logger.error(f"❌ Performance update failed: {str(e)}")
            return False

    def compute_transfer_ability_score(self, model_name: str) -> Decimal:
        """Compute transfer ability score for model"""

        try:
            logger.info(f"📊 Computing transfer ability score for: {model_name}")

            if model_name not in self.model_registry:
                logger.error(f"❌ Model not found: {model_name}")
                return Decimal('0.0')

            model = self.model_registry[model_name]
            score = self._compute_transfer_ability_score(model)

            # Update model with new score
            model.transfer_ability_score = score
            self.transfer_scores[model_name] = score

            logger.info(f"✅ Transfer ability score computed: {score:.3f}")
            return score

        except DataValidationError as e:
            logger.error(f"❌ Transfer ability score computation failed: {str(e)}")
            return Decimal('0.0')

    def _validate_model_config(self, model: PreTrainedModel) -> bool:
        """Validate model configuration"""

        try:
            # Check required fields
            required_fields = ['name', 'model_type', 'source_domain', 'target_domain', 'model_path']
            for field in required_fields:
                if not hasattr(model, field) or getattr(model, field) is None:
                    logger.error(f"❌ Missing required field: {field}")
                    return False

            # Check file existence
            if not os.path.exists(model.model_path):
                logger.warning(f"⚠️ Model file not found: {model.model_path}")

            if not os.path.exists(model.feature_extractor_path):
                logger.warning(f"⚠️ Feature extractor file not found: {model.feature_extractor_path}")

            return True

        except DataValidationError as e:
            logger.error(f"❌ Model validation failed: {str(e)}")
            return False

    def _compute_transfer_ability_score(self, model: PreTrainedModel) -> Decimal:
        """Compute transfer ability score for model"""

        try:
            # Base score from performance metrics
            base_score = Decimal('0.0')
            if model.performance_metrics:
                # Average of all performance metrics
                scores = list(model.performance_metrics.values())
                base_score = sum(scores) / len(scores)

            # Domain similarity bonus
            domain_bonus = Decimal('0.0')
            if model.source_domain == model.target_domain:
                domain_bonus = Decimal('0.2')
            elif self._are_domains_similar(model.source_domain, model.target_domain):
                domain_bonus = Decimal('0.1')

            # Model type bonus
            type_bonus = Decimal('0.0')
            if model.model_type in ['classification', 'regression']:
                type_bonus = Decimal('0.1')

            # Recency bonus
            recency_bonus = Decimal('0.0')
            if model.last_updated:
                days_old = (datetime.now() - model.last_updated).days
                if days_old < 30:  # Recent model
                    recency_bonus = Decimal('0.1')
                elif days_old < 90:  # Moderately recent
                    recency_bonus = Decimal('0.05')

            # Compute final score
            final_score = min(Decimal('1.0'), base_score + domain_bonus + type_bonus + recency_bonus)

            return final_score

        except DataValidationError as e:
            logger.error(f"❌ Transfer ability score computation failed: {str(e)}")
            return Decimal('0.5')  # Default score

    def _are_domains_similar(self, domain1: str, domain2: str) -> bool:
        """Check if two domains are similar"""

        # Simple similarity check based on keywords
        domain1_keywords = set(domain1.lower().split('_'))
        domain2_keywords = set(domain2.lower().split('_'))

        # Check for common keywords
        common_keywords = domain1_keywords.intersection(domain2_keywords)
        similarity_ratio = len(common_keywords) / max(len(domain1_keywords), len(domain2_keywords))

        return similarity_ratio > Decimal('0.3')

    def _is_model_suitable_for_task(self, model: PreTrainedModel, task: TransferLearningTask) -> bool:
        """Check if model is suitable for specific task"""

        try:
            # Task-specific suitability checks
            if task == TransferLearningTask.METHODOLOGY_SELECTION:
                return model.model_type in ['classification', 'regression']
            elif task == TransferLearningTask.QUESTION_ROUTING:
                return model.model_type == 'classification'
            elif task == TransferLearningTask.OWNER_DEPENDENCY:
                return model.model_type in ['classification', 'regression']
            elif task == TransferLearningTask.VALUATION_ACCURACY:
                return model.model_type == 'regression'
            elif task == TransferLearningTask.USER_SATISFACTION:
                return model.model_type in ['classification', 'regression']
            else:
                return True  # Default to suitable

        except DataValidationError as e:
            logger.error(f"❌ Task suitability check failed: {str(e)}")
            return False

    def _create_mock_model(self, model_config: PreTrainedModel) -> Any:
        """Create mock model when file is not found"""

        try:
            logger.info(f"🔧 Creating mock model: {model_config.name}")

            if model_config.model_type == 'classification':
                from sklearn.linear_model import LogisticRegression
                mock_model = LogisticRegression(random_state=42)
            elif model_config.model_type == 'regression':
                from sklearn.linear_model import LinearRegression
                mock_model = LinearRegression()
            else:
                from sklearn.linear_model import LogisticRegression
                mock_model = LogisticRegression(random_state=42)

            # Store in cache
            self.model_cache[model_config.name] = mock_model

            logger.info(f"✅ Mock model created: {model_config.name}")
            return mock_model

        except CacheError as e:
            logger.error(f"❌ Mock model creation failed: {str(e)}")
            return None

    def _create_mock_feature_extractor(self, model_config: PreTrainedModel) -> Any:
        """Create mock feature extractor when file is not found"""

        try:
            logger.info(f"🔧 Creating mock feature extractor: {model_config.name}")

            from sklearn.preprocessing import StandardScaler
            mock_extractor = StandardScaler()

            # Store in cache
            self.feature_extractors[model_config.name] = mock_extractor

            logger.info(f"✅ Mock feature extractor created: {model_config.name}")
            return mock_extractor

        except CacheError as e:
            logger.error(f"❌ Mock feature extractor creation failed: {str(e)}")
            return None

    def get_model_statistics(self) -> Dict[str, Any]:
        """Get statistics about registered models"""

        try:
            logger.info("📊 Computing model statistics")

            total_models = len(self.model_registry)
            model_types = {}
            domains = {}
            transfer_scores = []

            for model in self.model_registry.values():
                # Count by type
                model_type = model.model_type
                model_types[model_type] = model_types.get(model_type, 0) + 1

                # Count by domain
                domain = model.source_domain
                domains[domain] = domains.get(domain, 0) + 1

                # Collect transfer scores
                transfer_scores.append(model.transfer_ability_score)

            statistics = {
                "total_models": total_models,
                "model_types": model_types,
                "domains": domains,
                "avg_transfer_score": np.mean(transfer_scores) if transfer_scores else Decimal('0.0'),
                "max_transfer_score": np.max(transfer_scores) if transfer_scores else Decimal('0.0'),
                "min_transfer_score": np.min(transfer_scores) if transfer_scores else Decimal('0.0'),
                "cached_models": len(self.model_cache),
                "cached_extractors": len(self.feature_extractors)
            }

            logger.info(f"✅ Model statistics computed: {total_models} models")
            return statistics

        except CacheError as e:
            logger.error(f"❌ Model statistics computation failed: {str(e)}")
            return {
                "total_models": 0,
                "model_types": {},
                "domains": {},
                "avg_transfer_score": Decimal('0.0'),
                "max_transfer_score": Decimal('0.0'),
                "min_transfer_score": Decimal('0.0'),
                "cached_models": 0,
                "cached_extractors": 0
            }

    def clear_cache(self):
        """Clear model and feature extractor cache"""

        try:
            logger.info("🧹 Clearing model cache")

            self.model_cache.clear()
            self.feature_extractors.clear()

            logger.info("✅ Model cache cleared")

        except CacheError as e:
            logger.error(f"❌ Cache clearing failed: {str(e)}")

    def save_registry(self, registry_path: str = "models/pretrained/registry.json") -> bool:
        """Save model registry to file"""

        try:
            logger.info(f"💾 Saving model registry: {registry_path}")

            # Convert models to serializable format
            serializable_registry = {}
            for name, model in self.model_registry.items():
                serializable_registry[name] = {
                    "name": model.name,
                    "model_type": model.model_type,
                    "source_domain": model.source_domain,
                    "target_domain": model.target_domain,
                    "model_path": model.model_path,
                    "feature_extractor_path": model.feature_extractor_path,
                    "performance_metrics": model.performance_metrics,
                    "transfer_ability_score": model.transfer_ability_score,
                    "created_at": model.created_at.isoformat(),
                    "last_updated": model.last_updated.isoformat(),
                    "version": model.version
                }

            # Save to file
            with open(registry_path, 'w') as f:
                json.dump(serializable_registry, f, indent=2)

            logger.info(f"✅ Model registry saved: {registry_path}")
            return True

        except ValuationEngineError as e:
            logger.error(f"❌ Registry saving failed: {str(e)}")
            return False

    def load_registry(self, registry_path: str = "models/pretrained/registry.json") -> bool:
        """Load model registry from file"""

        try:
            logger.info(f"📂 Loading model registry: {registry_path}")

            if not os.path.exists(registry_path):
                logger.warning(f"⚠️ Registry file not found: {registry_path}")
                return False

            # Load from file
            with open(registry_path, 'r') as f:
                serializable_registry = json.load(f)

            # Convert back to PreTrainedModel objects
            for name, model_data in serializable_registry.items():
                model = PreTrainedModel(
                    name=model_data["name"],
                    model_type=model_data["model_type"],
                    source_domain=model_data["source_domain"],
                    target_domain=model_data["target_domain"],
                    model_path=model_data["model_path"],
                    feature_extractor_path=model_data["feature_extractor_path"],
                    performance_metrics=model_data["performance_metrics"],
                    transfer_ability_score=model_data["transfer_ability_score"],
                    created_at=datetime.fromisoformat(model_data["created_at"]),
                    last_updated=datetime.fromisoformat(model_data["last_updated"]),
                    version=model_data["version"]
                )
                self.model_registry[name] = model

            logger.info(f"✅ Model registry loaded: {len(self.model_registry)} models")
            return True

        except ValuationEngineError as e:
            logger.error(f"❌ Registry loading failed: {str(e)}")
            return False
