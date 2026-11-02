from src.utils.exceptions import DataValidationError

"""
Model Registry

This module handles model registration, versioning, and metadata management.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import hashlib
import os
from pathlib import Path

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from ..pipelines.ml_types import (
    ModelRegistry, ModelVersion, ModelArtifact, ModelStatus,
    ModelMetrics, MLModelType
)

logger = get_logger(__name__)


class ModelRegistryManager:
    """Manages model registry operations"""

    def __init__(self, registry_path: str = "models/registry"):
        self.registry_path = Path(registry_path)
        self.registry_path.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.registry_path / "registry.json"
        self._load_registry()

    def _load_registry(self) -> None:
        """Load the model registry from disk"""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, 'r') as f:
                    data = json.load(f)
                    self.registry = {
                        model_id: ModelRegistry(**model_data)
                        for model_id, model_data in data.items()
                    }
            except Exception as e:
                logger.error(f"Error loading registry: {e}")
                self.registry = {}
        else:
            self.registry = {}

    def _save_registry(self) -> None:
        """Save the model registry to disk"""
        try:
            registry_data = {
                model_id: {
                    'model_id': model.model_id,
                    'model_name': model.model_name,
                    'model_type': model.model_type.value,
                    'current_version': model.current_version,
                    'versions': [
                        {
                            'version_id': version.version_id,
                            'model_id': version.model_id,
                            'version_number': version.version_number,
                            'status': version.status.value,
                            'performance_metrics': {
                                'accuracy': version.performance_metrics.accuracy,
                                'precision': version.performance_metrics.precision,
                                'recall': version.performance_metrics.recall,
                                'f1_score': version.performance_metrics.f1_score,
                                'auc_roc': version.performance_metrics.auc_roc,
                                'mse': version.performance_metrics.mse,
                                'rmse': version.performance_metrics.rmse,
                                'mae': version.performance_metrics.mae,
                                'r2_score': version.performance_metrics.r2_score,
                                'training_time': version.performance_metrics.training_time.total_seconds() if version.performance_metrics.training_time else None,
                                'inference_time': version.performance_metrics.inference_time.total_seconds() if version.performance_metrics.inference_time else None
                            },
                            'training_data_hash': version.training_data_hash,
                            'model_artifacts': [
                                {
                                    'artifact_id': artifact.artifact_id,
                                    'model_id': artifact.model_id,
                                    'artifact_type': artifact.artifact_type,
                                    'file_path': artifact.file_path,
                                    'file_size': artifact.file_size,
                                    'checksum': artifact.checksum,
                                    'created_at': artifact.created_at.isoformat(),
                                    'metadata': artifact.metadata
                                }
                                for artifact in version.model_artifacts
                            ],
                            'created_at': version.created_at.isoformat(),
                            'deployed_at': version.deployed_at.isoformat() if version.deployed_at else None,
                            'retired_at': version.retired_at.isoformat() if version.retired_at else None
                        }
                        for version in model.versions
                    ],
                    'tags': model.tags,
                    'description': model.description,
                    'created_at': model.created_at.isoformat(),
                    'updated_at': model.updated_at.isoformat()
                }
                for model_id, model in self.registry.items()
            }

            with open(self.registry_file, 'w') as f:
                json.dump(registry_data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving registry: {e}")

    def register_model(
        self,
        model_id: str,
        model_name: str,
        model_type: MLModelType,
        description: str = "",
        tags: List[str] = None
    ) -> ModelRegistry:
        """Register a new model"""
        if model_id in self.registry:
            raise ValueError(f"Model {model_id} already exists")

        if tags is None:
            tags = []

        model_registry = ModelRegistry(
            model_id=model_id,
            model_name=model_name,
            model_type=model_type,
            current_version="",
            versions=[],
            tags=tags,
            description=description,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        self.registry[model_id] = model_registry
        self._save_registry()

        logger.info(f"Registered model: {model_id}")
        return model_registry

    def add_model_version(
        self,
        model_id: str,
        version_number: str,
        performance_metrics: ModelMetrics,
        training_data_hash: str,
        model_artifacts: List[ModelArtifact],
        status: ModelStatus = ModelStatus.TRAINED
    ) -> ModelVersion:
        """Add a new version to an existing model"""
        if model_id not in self.registry:
            raise ValueError(f"Model {model_id} not found")

        version_id = f"{model_id}_v{version_number}"

        model_version = ModelVersion(
            version_id=version_id,
            model_id=model_id,
            version_number=version_number,
            status=status,
            performance_metrics=performance_metrics,
            training_data_hash=training_data_hash,
            model_artifacts=model_artifacts,
            created_at=datetime.now()
        )

        self.registry[model_id].versions.append(model_version)
        self.registry[model_id].current_version = version_number
        self.registry[model_id].updated_at = datetime.now()

        self._save_registry()

        logger.info(f"Added version {version_number} to model {model_id}")
        return model_version

    def get_model(self, model_id: str) -> Optional[ModelRegistry]:
        """Get a model by ID"""
        return self.registry.get(model_id)

    def get_model_version(self, model_id: str, version_number: str) -> Optional[ModelVersion]:
        """Get a specific model version"""
        model = self.get_model(model_id)
        if not model:
            return None

        for version in model.versions:
            if version.version_number == version_number:
                return version

        return None

    def list_models(self, model_type: Optional[MLModelType] = None) -> List[ModelRegistry]:
        """List all models, optionally filtered by type"""
        models = list(self.registry.values())

        if model_type:
            models = [m for m in models if m.model_type == model_type]

        return models

    def update_model_status(
        self,
        model_id: str,
        version_number: str,
        status: ModelStatus
    ) -> bool:
        """Update the status of a model version"""
        model = self.get_model(model_id)
        if not model:
            return False

        for version in model.versions:
            if version.version_number == version_number:
                version.status = status
                self.registry[model_id].updated_at = datetime.now()
                self._save_registry()

                logger.info(f"Updated status for {model_id} v{version_number} to {status.value}")
                return True

        return False

    def deploy_model(
        self,
        model_id: str,
        version_number: str
    ) -> bool:
        """Deploy a model version"""
        model = self.get_model(model_id)
        if not model:
            return False

        for version in model.versions:
            if version.version_number == version_number:
                version.status = ModelStatus.DEPLOYED
                version.deployed_at = datetime.now()
                self.registry[model_id].updated_at = datetime.now()
                self._save_registry()

                logger.info(f"Deployed model {model_id} v{version_number}")
                return True

        return False

    def retire_model(
        self,
        model_id: str,
        version_number: str
    ) -> bool:
        """Retire a model version"""
        model = self.get_model(model_id)
        if not model:
            return False

        for version in model.versions:
            if version.version_number == version_number:
                version.status = ModelStatus.RETIRED
                version.retired_at = datetime.now()
                self.registry[model_id].updated_at = datetime.now()
                self._save_registry()

                logger.info(f"Retired model {model_id} v{version_number}")
                return True

        return False

    def get_model_artifacts(
        self,
        model_id: str,
        version_number: str
    ) -> List[ModelArtifact]:
        """Get artifacts for a specific model version"""
        version = self.get_model_version(model_id, version_number)
        if not version:
            return []

        return version.model_artifacts

    def calculate_artifact_checksum(self, file_path: str) -> str:
        """Calculate checksum for a model artifact"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()
        except DataValidationError as e:
            logger.error(f"Error calculating checksum for {file_path}: {e}")
            return ""

    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes"""
        try:
            return os.path.getsize(file_path)
        except DataValidationError as e:
            logger.error(f"Error getting file size for {file_path}: {e}")
            return 0

    def cleanup_old_versions(
        self,
        model_id: str,
        keep_versions: int = 5
    ) -> int:
        """Clean up old model versions, keeping only the most recent ones"""
        model = self.get_model(model_id)
        if not model:
            return 0

        if len(model.versions) <= keep_versions:
            return 0

        # Sort versions by creation date (newest first)
        sorted_versions = sorted(
            model.versions,
            key=lambda v: v.created_at,
            reverse=True
        )

        # Keep the most recent versions
        versions_to_keep = sorted_versions[:keep_versions]
        versions_to_remove = sorted_versions[keep_versions:]

        # Remove old versions
        self.registry[model_id].versions = versions_to_keep
        self.registry[model_id].updated_at = datetime.now()

        self._save_registry()

        logger.info(f"Cleaned up {len(versions_to_remove)} old versions for model {model_id}")
        return len(versions_to_remove)

    def get_model_performance_history(
        self,
        model_id: str
    ) -> List[ModelMetrics]:
        """Get performance history for a model"""
        model = self.get_model(model_id)
        if not model:
            return []

        return [version.performance_metrics for version in model.versions]

    def search_models(
        self,
        query: str,
        model_type: Optional[MLModelType] = None,
        tags: Optional[List[str]] = None
    ) -> List[ModelRegistry]:
        """Search models by name, description, or tags"""
        results = []

        for model in self.registry.values():
            # Filter by type if specified
            if model_type and model.model_type != model_type:
                continue

            # Filter by tags if specified
            if tags and not any(tag in model.tags for tag in tags):
                continue

            # Search in name and description
            if (query.lower() in model.model_name.lower() or
                query.lower() in model.description.lower()):
                results.append(model)

        return results
