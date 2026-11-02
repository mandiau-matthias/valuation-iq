"""
ML Prediction Cache

Provides Redis-backed caching for ML model predictions
to reduce inference latency and improve performance.
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


class PredictionCache:
    """
    Redis-backed prediction cache for ML models

    Features:
    - Cache ML predictions with TTL
    - Model version tracking
    - Prediction metadata storage
    - Cache invalidation strategies
    - Performance monitoring
    """

    def __init__(self):
        """Initialize prediction cache"""
        self.redis_client: Optional[redis.Redis] = None
        self.key_prefix = "ml:prediction"
        self.model_prefix = "ml:model"
        self.cache_ttl = 3600  # 1 hour default TTL

        # Cache statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_requests = 0

        logger.info("PredictionCache initialized", cache_ttl=self.cache_ttl)

    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client for predictions (DB 3)"""
        if not self.redis_client:
            try:
                # Use DB 3 for predictions (separate from context DB 0, features DB 1)
                self.redis_client = await get_redis_client()
                # Note: Redis client should be configured for DB 3 in config
            except Exception as e:
                logger.error(f"Failed to get Redis client: {e}")
                return None
        return self.redis_client

    def _get_prediction_key(self, model_name: str, input_hash: str) -> str:
        """Generate Redis key for prediction"""
        return f"{self.key_prefix}:{model_name}:{input_hash}"

    def _get_model_key(self, model_name: str) -> str:
        """Generate Redis key for model metadata"""
        return f"{self.model_prefix}:{model_name}"

    def _hash_input(self, input_data: Union[Dict, List, str]) -> str:
        """Generate hash for input data"""
        try:
            if isinstance(input_data, dict):
                # Sort keys for consistent hashing
                sorted_data = json.dumps(input_data, sort_keys=True)
            else:
                sorted_data = json.dumps(input_data)

            return hashlib.md5(sorted_data.encode(), usedforsecurity=False).hexdigest()
        except Exception as e:
            logger.error(f"Error hashing input: {e}")
            return hashlib.md5(
                str(input_data).encode(),
                usedforsecurity=False,
            ).hexdigest()

    async def cache_prediction(
        self,
        model_name: str,
        input_data: Union[Dict, List, str],
        prediction: Any,
        model_version: str = "1.0.0",
        confidence: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache ML prediction

        Args:
            model_name: Name of the ML model
            input_data: Input data used for prediction
            prediction: Model prediction result
            model_version: Version of the model
            confidence: Prediction confidence score
            metadata: Optional metadata
            ttl: Time to live in seconds (default: 1 hour)

        Returns:
            True if cached successfully, False otherwise
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for prediction caching")
                return False

            # Generate input hash
            input_hash = self._hash_input(input_data)

            # Prepare prediction data
            prediction_data = {
                "model_name": model_name,
                "model_version": model_version,
                "input_hash": input_hash,
                "prediction": prediction,
                "confidence": confidence,
                "created_at": datetime.now().isoformat(),
                "metadata": metadata or {},
            }

            # Store prediction
            key = self._get_prediction_key(model_name, input_hash)
            cache_ttl = ttl or self.cache_ttl

            await redis_client.setex(key, cache_ttl, json.dumps(prediction_data))

            # Update model metadata
            model_key = self._get_model_key(model_name)
            await redis_client.hset(model_key, "latest_version", model_version)
            await redis_client.hset(model_key, "last_prediction", datetime.now().isoformat())
            await redis_client.expire(model_key, cache_ttl)

            logger.debug(
                "Prediction cached", model_name=model_name, input_hash=input_hash[:8], ttl=cache_ttl
            )

            return True

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error caching prediction: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error caching prediction: {e}")
            return False

    async def get_prediction(
        self, model_name: str, input_data: Union[Dict, List, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached prediction

        Args:
            model_name: Name of the ML model
            input_data: Input data used for prediction

        Returns:
            Prediction data with metadata or None if not found
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for prediction retrieval")
                return None

            # Generate input hash
            input_hash = self._hash_input(input_data)

            # Get prediction
            key = self._get_prediction_key(model_name, input_hash)
            data = await redis_client.get(key)

            if not data:
                self.cache_misses += 1
                self.total_requests += 1
                logger.debug(
                    "Prediction not found in cache",
                    model_name=model_name,
                    input_hash=input_hash[:8],
                )
                return None

            prediction_data = json.loads(data)
            self.cache_hits += 1
            self.total_requests += 1

            logger.debug(
                "Prediction retrieved from cache", model_name=model_name, input_hash=input_hash[:8]
            )

            return prediction_data

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error retrieving prediction: {e}")
            self.cache_misses += 1
            self.total_requests += 1
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving prediction: {e}")
            self.cache_misses += 1
            self.total_requests += 1
            return None

    async def invalidate_model_cache(self, model_name: str) -> bool:
        """
        Invalidate all cached predictions for a model

        Args:
            model_name: Name of the model

        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                logger.warning("Redis unavailable for cache invalidation")
                return False

            # Find all keys for this model
            pattern = f"{self.key_prefix}:{model_name}:*"
            keys = await redis_client.keys(pattern)

            if keys:
                await redis_client.delete(*keys)
                logger.info(
                    "Model cache invalidated", model_name=model_name, keys_deleted=len(keys)
                )
            else:
                logger.debug("No cache entries found for model", model_name=model_name)

            return True

        except (RedisError, ConnectionError, TimeoutError) as e:
            logger.error(f"Redis error invalidating model cache: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error invalidating model cache: {e}")
            return False

    async def get_model_stats(self, model_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific model

        Args:
            model_name: Name of the model

        Returns:
            Model statistics
        """
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return {"error": "Redis client unavailable"}

            # Get model metadata
            model_key = self._get_model_key(model_name)
            model_data = await redis_client.hgetall(model_key)

            # Count cached predictions
            pattern = f"{self.key_prefix}:{model_name}:*"
            keys = await redis_client.keys(pattern)
            prediction_count = len(keys)

            return {
                "model_name": model_name,
                "latest_version": model_data.get("latest_version", "unknown"),
                "last_prediction": model_data.get("last_prediction", "never"),
                "cached_predictions": prediction_count,
                "cache_hit_rate": (
                    self.cache_hits / max(self.total_requests, 1)
                    if self.total_requests > 0
                    else 0.0
                ),
            }

        except Exception as e:
            logger.error(f"Error getting model stats: {e}")
            return {"error": str(e)}

    async def health_check(self) -> Dict[str, Any]:
        """Check prediction cache health"""
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return {"status": "unhealthy", "error": "Redis client unavailable"}

            # Test Redis connection
            await redis_client.ping()

            # Get basic stats
            info = await redis_client.info()

            return {
                "status": "healthy",
                "redis_connected": True,
                "memory_usage": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "cache_ttl": self.cache_ttl,
                "cache_hit_rate": (
                    self.cache_hits / max(self.total_requests, 1)
                    if self.total_requests > 0
                    else 0.0
                ),
                "total_requests": self.total_requests,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
            }

        except Exception as e:
            logger.error(f"Prediction cache health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def get_stats(self) -> Dict[str, Any]:
        """Get prediction cache statistics"""
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return {"error": "Redis client unavailable"}

            # Count all prediction keys
            pattern = f"{self.key_prefix}:*"
            keys = await redis_client.keys(pattern)
            total_predictions = len(keys)

            # Count model keys
            model_pattern = f"{self.model_prefix}:*"
            model_keys = await redis_client.keys(model_pattern)
            total_models = len(model_keys)

            return {
                "total_predictions": total_predictions,
                "total_models": total_models,
                "cache_hit_rate": (
                    self.cache_hits / max(self.total_requests, 1)
                    if self.total_requests > 0
                    else 0.0
                ),
                "total_requests": self.total_requests,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "cache_ttl": self.cache_ttl,
                "redis_memory_usage": await redis_client.memory_usage(),
            }

        except Exception as e:
            logger.error(f"Error getting prediction cache stats: {e}")
            return {"error": str(e)}


import threading as _threading

_prediction_cache: Optional[PredictionCache] = None
_prediction_cache_lock = _threading.Lock()


def get_prediction_cache() -> PredictionCache:
    """Get global prediction cache instance"""
    global _prediction_cache
    if _prediction_cache is None:
        with _prediction_cache_lock:
            if _prediction_cache is None:
                _prediction_cache = PredictionCache()
    return _prediction_cache
