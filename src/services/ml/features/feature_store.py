from src.utils.exceptions import CacheError, DataValidationError, MissingDataError

"""
Feature Store for ML Features

Provides Redis-backed storage and retrieval of ML features
extracted from conversation contexts for real-time inference.
"""

import json
import hashlib
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from src.utils.logging import get_logger
from src.config import settings
from src.database.redis_client import get_redis_client
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


class FeatureStore:
    """
    Redis-backed feature store for ML features

    Features:
    - Store ML features in Redis DB 1 (separate namespace)
    - Feature versioning for reproducibility
    - Real-time feature serving (<20ms)
    - Feature monitoring and drift detection
    - Batch feature operations
    """

    def __init__(self):
        """Initialize feature store"""
        self.redis_client: Optional[redis.Redis] = None
        self.key_prefix = "features"
        self.version_prefix = "feature_versions"
        self.cache_ttl = settings.context_guest_ttl  # Use same TTL as context

        # Feature schema version
        self.schema_version = "1.0"

        logger.info("FeatureStore initialized", 
                   cache_ttl=self.cache_ttl,
                   schema_version=self.schema_version)

    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client for features (DB 1)"""
        if not self.redis_client:
            try:
                # Use DB 1 for features (separate from context DB 0)
                self.redis_client = await get_redis_client()
                # Note: Redis client should be configured for DB 1 in config
            except DataValidationError as e:
                logger.error(f"Failed to get Redis client: {e}")
                return None
        return self.redis_client

    def _get_feature_key(self, session_id: str, feature_name: str) -> str:
        """Generate Redis key for feature"""
        return f"{self.key_prefix}:session:{session_id}:{feature_name}"

    def _get_session_features_key(self, session_id: str) -> str:
        """Generate Redis key for session features list"""
        return f"{self.key_prefix}:session:{session_id}:all"

    def _get_version_key(self, feature_name: str) -> str:
        """Generate Redis key for feature version"""
        return f"{self.version_prefix}:{feature_name}"

    async def store_feature(
        self, 
        session_id: str, 
        feature_name: str, 
        feature_value: Union[float, int, str, List, Dict],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store a feature value for a session

        Args:
            session_id: Session identifier
            feature_name: Name of the feature
            feature_value: Feature value (numeric, string, list, dict)
            metadata: Optional metadata (timestamp, confidence, etc.)

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for feature storage")
                return False

            # Prepare feature data
            feature_data = {
                "session_id": session_id,
                "feature_name": feature_name,
                "feature_value": feature_value,
                "feature_type": type(feature_value).__name__,
                "schema_version": self.schema_version,
                "created_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }

            # Store individual feature
            key = self._get_feature_key(session_id, feature_name)
            await redis_client.setex(
                key, 
                self.cache_ttl, 
                json.dumps(feature_data)
            )

            # Add to session features list
            session_key = self._get_session_features_key(session_id)
            await redis_client.sadd(session_key, feature_name)
            await redis_client.expire(session_key, self.cache_ttl)

            # Update feature version
            version_key = self._get_version_key(feature_name)
            await redis_client.hset(version_key, "latest", self.schema_version)
            await redis_client.hset(version_key, "updated_at", datetime.now().isoformat())
            await redis_client.expire(version_key, self.cache_ttl)

            logger.debug("Feature stored", 
                        session_id=session_id, 
                        feature_name=feature_name,
                        feature_type=type(feature_value).__name__)

            return True

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error storing feature: {e}")
            return False
        except CacheError as e:
            logger.error(f"Unexpected error storing feature: {e}")
            return False

    async def get_feature(
        self, 
        session_id: str, 
        feature_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a feature value for a session

        Args:
            session_id: Session identifier
            feature_name: Name of the feature

        Returns:
            Feature data with metadata or None if not found
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for feature retrieval")
                return None

            key = self._get_feature_key(session_id, feature_name)
            data = await redis_client.get(key)

            if not data:
                logger.debug("Feature not found", session_id=session_id, feature_name=feature_name)
                return None

            feature_data = json.loads(data)
            logger.debug("Feature retrieved", 
                        session_id=session_id, 
                        feature_name=feature_name)

            return feature_data

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error retrieving feature: {e}")
            return None
        except CacheError as e:
            logger.error(f"Unexpected error retrieving feature: {e}")
            return None

    async def get_session_features(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieve all features for a session

        Args:
            session_id: Session identifier

        Returns:
            Dictionary of feature_name -> feature_data
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for session features")
                return {}

            # Get all feature names for the session
            session_key = self._get_session_features_key(session_id)
            feature_names = await redis_client.smembers(session_key)

            if not feature_names:
                logger.debug("No features found for session", session_id=session_id)
                return {}

            # Retrieve features for each name
            features = {}
            for feature_name in feature_names:
                feature_name_str = feature_name.decode() if isinstance(feature_name, bytes) else feature_name
                feature_data = await self.get_feature(session_id, feature_name_str)
                if feature_data:
                    features[feature_name_str] = feature_data

            logger.debug("Session features retrieved", 
                        session_id=session_id, 
                        count=len(features))

            return features

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error retrieving session features: {e}")
            return {}
        except CacheError as e:
            logger.error(f"Unexpected error retrieving session features: {e}")
            return {}

    async def store_features_batch(
        self, 
        session_id: str, 
        features: Dict[str, Union[float, int, str, List, Dict]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store multiple features for a session in batch

        Args:
            session_id: Session identifier
            features: Dictionary of feature_name -> feature_value
            metadata: Optional metadata for all features

        Returns:
            True if all stored successfully, False otherwise
        """
        try:
            success_count = 0
            total_count = len(features)

            for feature_name, feature_value in features.items():
                success = await self.store_feature(
                    session_id=session_id,
                    feature_name=feature_name,
                    feature_value=feature_value,
                    metadata=metadata
                )
                if success:
                    success_count += 1

            logger.info("Batch feature storage completed", 
                       session_id=session_id,
                       successful=success_count,
                       total=total_count)

            return success_count == total_count

        except Exception as e:
            logger.error(f"Error in batch feature storage: {e}")
            return False

    async def get_feature_vector(
        self, 
        session_id: str, 
        feature_names: List[str]
    ) -> List[Decimal]:
        """
        Get feature vector for ML model inference

        Args:
            session_id: Session identifier
            feature_names: List of feature names to retrieve

        Returns:
            List of feature values in order (None for missing features)
        """
        try:
            features = await self.get_session_features(session_id)
            feature_vector = []

            for feature_name in feature_names:
                if feature_name in features:
                    feature_value = features[feature_name]["feature_value"]
                    # Convert to float if possible
                    try:
                        if isinstance(feature_value, (int, float)):
                            feature_vector.append(to_decimal(feature_value))
                        elif isinstance(feature_value, str):
                            # Try to convert string to float
                            feature_vector.append(to_decimal(feature_value))
                        else:
                            feature_vector.append(Decimal('0.0'))  # Default for non-numeric
                    except (ValueError, TypeError):
                        feature_vector.append(Decimal('0.0'))  # Default for conversion errors
                else:
                    feature_vector.append(Decimal('0.0'))  # Default for missing features

            logger.debug("Feature vector generated", 
                        session_id=session_id,
                        vector_length=len(feature_vector),
                        features_requested=len(feature_names))

            return feature_vector

        except MissingDataError as e:
            logger.error(f"Error generating feature vector: {e}")
            return [Decimal('0.0')] * len(feature_names)

    async def delete_session_features(self, session_id: str) -> bool:
        """
        Delete all features for a session

        Args:
            session_id: Session identifier

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for feature deletion")
                return False

            # Get all feature names for the session
            session_key = self._get_session_features_key(session_id)
            feature_names = await redis_client.smembers(session_key)

            # Delete individual features
            keys_to_delete = []
            for feature_name in feature_names:
                feature_name_str = feature_name.decode() if isinstance(feature_name, bytes) else feature_name
                key = self._get_feature_key(session_id, feature_name_str)
                keys_to_delete.append(key)

            # Delete all keys at once
            if keys_to_delete:
                await redis_client.delete(*keys_to_delete)

            # Delete session key
            await redis_client.delete(session_key)

            logger.debug("Session features deleted", 
                        session_id=session_id, 
                        count=len(keys_to_delete))

            return True

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error deleting features: {e}")
            return False
        except DataValidationError as e:
            logger.error(f"Unexpected error deleting features: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check feature store health"""
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
                "connected_clients": info.get("connected_clients", 0),
                "schema_version": self.schema_version,
                "cache_ttl": self.cache_ttl
            }

        except DataValidationError as e:
            logger.error(f"Feature store health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def get_stats(self) -> Dict[str, Any]:
        """Get feature store statistics"""
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return {"error": "Redis client unavailable"}

            # Count feature keys
            pattern = f"{self.key_prefix}:session:*:*"
            keys = await redis_client.keys(pattern)
            feature_count = len(keys)

            # Count session keys
            session_pattern = f"{self.key_prefix}:session:*:all"
            session_keys = await redis_client.keys(session_pattern)
            session_count = len(session_keys)

            # Count version keys
            version_pattern = f"{self.version_prefix}:*"
            version_keys = await redis_client.keys(version_pattern)
            version_count = len(version_keys)

            return {
                "total_features": feature_count,
                "total_sessions": session_count,
                "total_versions": version_count,
                "schema_version": self.schema_version,
                "cache_ttl": self.cache_ttl,
                "redis_memory_usage": await redis_client.memory_usage()
            }

        except DataValidationError as e:
            logger.error(f"Error getting feature store stats: {e}")
            return {"error": str(e)}


# Global instance
_feature_store: Optional[FeatureStore] = None


def get_feature_store() -> FeatureStore:
    """Get global feature store instance"""
    global _feature_store
    if _feature_store is None:
        _feature_store = FeatureStore()
    return _feature_store
