from src.utils.exceptions import CacheError, DataValidationError, DatabaseError

"""
Model Registry for ML Model Management

Provides model versioning, metadata tracking, and deployment management
for ML models in the prediction system.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import json
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from src.utils.logging import get_logger
from src.database.redis_client import get_redis_client

logger = get_logger(__name__)


class ModelRegistry:
    """
    Model registry for ML model management

    Features:
    - Model versioning and metadata
    - Model deployment tracking
    - Performance monitoring
    - A/B testing support
    - Model rollback capabilities
    """

    def __init__(self):
        """Initialize model registry"""
        self.redis_client: Optional[redis.Redis] = None
        self.registry_prefix = "ml:registry"
        self.model_prefix = "ml:model"
        self.deployment_prefix = "ml:deployment"

        logger.info("ModelRegistry initialized")

    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client for model registry (DB 3)"""
        if not self.redis_client:
            try:
                self.redis_client = await get_redis_client()
            except DatabaseError as e:
                logger.error(f"Failed to get Redis client: {e}")
                return None
        return self.redis_client

    def _get_model_registry_key(self, model_name: str) -> str:
        """Generate Redis key for model registry"""
        return f"{self.registry_prefix}:{model_name}"

    def _get_deployment_key(self, model_name: str, environment: str = "production") -> str:
        """Generate Redis key for model deployment"""
        return f"{self.deployment_prefix}:{model_name}:{environment}"

    async def register_model(
        self, 
        model_name: str, 
        version: str,
        model_type: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Register a new model version

        Args:
            model_name: Name of the model
            version: Model version (e.g., "1.0.0")
            model_type: Type of model (e.g., "classification", "regression")
            description: Optional model description
            metadata: Optional model metadata

        Returns:
            True if registered successfully, False otherwise
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for model registration")
                return False

            # Prepare model data
            model_data = {
                "model_name": model_name,
                "version": version,
                "model_type": model_type,
                "description": description or "",
                "registered_at": datetime.now().isoformat(),
                "status": "registered",
                "metadata": metadata or {}
            }

            # Store model registry entry
            registry_key = self._get_model_registry_key(model_name)
            await redis_client.hset(registry_key, version, json.dumps(model_data))
            await redis_client.hset(registry_key, "latest", version)
            await redis_client.hset(registry_key, "updated_at", datetime.now().isoformat())

            logger.info("Model registered", 
                       model_name=model_name,
                       version=version,
                       model_type=model_type)

            return True

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error registering model: {e}")
            return False
        except CacheError as e:
            logger.error(f"Unexpected error registering model: {e}")
            return False

    async def deploy_model(
        self, 
        model_name: str, 
        version: str,
        environment: str = "production",
        deployment_config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Deploy a model version to an environment

        Args:
            model_name: Name of the model
            version: Model version to deploy
            environment: Deployment environment
            deployment_config: Optional deployment configuration

        Returns:
            True if deployed successfully, False otherwise
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for model deployment")
                return False

            # Prepare deployment data
            deployment_data = {
                "model_name": model_name,
                "version": version,
                "environment": environment,
                "deployed_at": datetime.now().isoformat(),
                "status": "deployed",
                "config": deployment_config or {}
            }

            # Store deployment
            deployment_key = self._get_deployment_key(model_name, environment)
            await redis_client.set(deployment_key, json.dumps(deployment_data))

            # Update model registry
            registry_key = self._get_model_registry_key(model_name)
            await redis_client.hset(registry_key, f"deployed_{environment}", version)

            logger.info("Model deployed", 
                       model_name=model_name,
                       version=version,
                       environment=environment)

            return True

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error deploying model: {e}")
            return False
        except CacheError as e:
            logger.error(f"Unexpected error deploying model: {e}")
            return False

    async def get_deployed_model(
        self, 
        model_name: str, 
        environment: str = "production"
    ) -> Optional[Dict[str, Any]]:
        """
        Get currently deployed model for environment

        Args:
            model_name: Name of the model
            environment: Deployment environment

        Returns:
            Deployment data or None if not found
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for model retrieval")
                return None

            deployment_key = self._get_deployment_key(model_name, environment)
            data = await redis_client.get(deployment_key)

            if not data:
                logger.debug("No deployed model found", 
                           model_name=model_name,
                           environment=environment)
                return None

            deployment_data = json.loads(data)
            logger.debug("Deployed model retrieved", 
                        model_name=model_name,
                        environment=environment)

            return deployment_data

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error retrieving deployed model: {e}")
            return None
        except CacheError as e:
            logger.error(f"Unexpected error retrieving deployed model: {e}")
            return None

    async def list_model_versions(self, model_name: str) -> List[Dict[str, Any]]:
        """
        List all versions of a model

        Args:
            model_name: Name of the model

        Returns:
            List of model versions
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for model listing")
                return []

            registry_key = self._get_model_registry_key(model_name)
            versions = await redis_client.hgetall(registry_key)

            model_versions = []
            for version, data in versions.items():
                if version not in ["latest", "updated_at"]:
                    try:
                        version_data = json.loads(data)
                        model_versions.append(version_data)
                    except json.JSONDecodeError:
                        continue

            # Sort by registration date
            model_versions.sort(key=lambda x: x.get("registered_at", ""), reverse=True)

            logger.debug("Model versions listed", 
                        model_name=model_name,
                        count=len(model_versions))

            return model_versions

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error listing model versions: {e}")
            return []
        except CacheError as e:
            logger.error(f"Unexpected error listing model versions: {e}")
            return []

    async def rollback_model(
        self, 
        model_name: str, 
        target_version: str,
        environment: str = "production"
    ) -> bool:
        """
        Rollback model to a previous version

        Args:
            model_name: Name of the model
            target_version: Version to rollback to
            environment: Deployment environment

        Returns:
            True if rollback successful, False otherwise
        """
        try:
            # Get target version data
            versions = await self.list_model_versions(model_name)
            target_model = next((v for v in versions if v["version"] == target_version), None)

            if not target_model:
                logger.error("Target version not found", 
                           model_name=model_name,
                           target_version=target_version)
                return False

            # Deploy target version
            success = await self.deploy_model(
                model_name=model_name,
                version=target_version,
                environment=environment,
                deployment_config={"rollback": True, "rollback_from": "latest"}
            )

            if success:
                logger.info("Model rollback completed", 
                           model_name=model_name,
                           target_version=target_version,
                           environment=environment)

            return success

        except DataValidationError as e:
            logger.error(f"Error rolling back model: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check model registry health"""
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return {
                    "status": "unhealthy",
                    "error": "Redis client unavailable"
                }

            # Test Redis connection
            await redis_client.ping()

            # Get basic stats
            info = await redis_client.info()

            return {
                "status": "healthy",
                "redis_connected": True,
                "memory_usage": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0)
            }

        except DataValidationError as e:
            logger.error(f"Model registry health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def get_stats(self) -> Dict[str, Any]:
        """Get model registry statistics"""
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return {"error": "Redis client unavailable"}

            # Count registry keys
            registry_pattern = f"{self.registry_prefix}:*"
            registry_keys = await redis_client.keys(registry_pattern)
            total_models = len(registry_keys)

            # Count deployment keys
            deployment_pattern = f"{self.deployment_prefix}:*"
            deployment_keys = await redis_client.keys(deployment_pattern)
            total_deployments = len(deployment_keys)

            return {
                "total_models": total_models,
                "total_deployments": total_deployments,
                "redis_memory_usage": await redis_client.memory_usage()
            }

        except CacheError as e:
            logger.error(f"Error getting model registry stats: {e}")
            return {"error": str(e)}


# Global instance
_model_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Get global model registry instance"""
    global _model_registry
    if _model_registry is None:
        _model_registry = ModelRegistry()
    return _model_registry
