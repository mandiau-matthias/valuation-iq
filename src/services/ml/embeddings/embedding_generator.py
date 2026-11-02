"""
Embedding Generator - DEPRECATED COMPATIBILITY SHIM

BRAIN & MUSCLE ARCHITECTURE:
Provider-backed embedding generation has been removed from ValuationIQ
(The Muscle). For generated embeddings, use Titan's embedding endpoints.

This module is retained for API compatibility but returns empty values.
"""

import hashlib
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.exceptions import RedisError

from src.utils.logging import get_logger
from src.config import settings
from src.database.redis_client import get_redis_client
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


class EmbeddingGenerator:
    """
    DEPRECATED: provider-backed embedding generation has moved to Titan.

    This class is retained for API compatibility but returns empty values.
    For generated embeddings, use Titan's embedding endpoints.
    """

    def __init__(self):
        """Initialize deprecated embedding generator"""
        logger.warning("DEPRECATED: EmbeddingGenerator initialized - generation has moved to Titan")
        self.cache_ttl = 86400 * 7
        self.cache_prefix = "embedding_cache"
        self.redis_client: Optional[redis.Redis] = None
        self.daily_cost = 0.0
        self.daily_limit = 10.0

    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client for caching"""
        if not self.redis_client:
            try:
                self.redis_client = await get_redis_client()
            except Exception as e:
                logger.error(f"Failed to get Redis client: {e}")
                return None
        return self.redis_client

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        # Create hash of text for consistent caching
        text_hash = hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()
        return f"{self.cache_prefix}:{text_hash}"

    async def _get_cached_embedding(self, text: str) -> Optional[List[Decimal]]:
        """Get embedding from cache"""
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return None

            cache_key = self._get_cache_key(text)
            cached_data = await redis_client.get(cache_key)

            if cached_data:
                import json

                data = json.loads(cached_data)
                logger.debug("Embedding retrieved from cache", text_length=len(text))
                return data.get("embedding")

            return None

        except Exception as e:
            logger.error(f"Error retrieving cached embedding: {e}")
            return None

    async def _cache_embedding(self, text: str, embedding: List[Decimal]) -> bool:
        """Cache embedding in Redis"""
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return False

            cache_key = self._get_cache_key(text)
            cache_data = {
                "embedding": embedding,
                "text_length": len(text),
                "cached_at": datetime.now().isoformat(),
                "model": "legacy_cached_vector",
            }

            import json

            await redis_client.setex(cache_key, self.cache_ttl, json.dumps(cache_data))

            logger.debug("Embedding cached", text_length=len(text))
            return True

        except Exception as e:
            logger.error(f"Error caching embedding: {e}")
            return False

    async def generate_embedding(self, text: str) -> Optional[List[Decimal]]:
        """
        DEPRECATED: Embedding generation has moved to Titan.

        Args:
            text: Text to embed

        Returns:
            None - AI has been removed
        """
        logger.warning("DEPRECATED: generate_embedding called - generation has moved to Titan")

        # Check cache first (may contain pre-computed embeddings)
        cached_embedding = await self._get_cached_embedding(text)
        if cached_embedding:
            return cached_embedding

        # AI has been removed - return None
        return None

    async def _call_retired_provider(self, text: str) -> Optional[List[Decimal]]:
        """
        DEPRECATED: external provider calls have been removed.

        This method returns None. For generated embeddings, use Titan.
        """
        logger.warning(
            "DEPRECATED: retired provider call requested - generation has moved to Titan"
        )
        return None

    async def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[Decimal]]]:
        """
        DEPRECATED: Batch embedding generation has moved to Titan.

        Args:
            texts: List of texts to embed

        Returns:
            List of None values - AI has been removed
        """
        logger.warning(
            "DEPRECATED: generate_embeddings_batch called - generation has moved to Titan"
        )
        return [None] * len(texts)

    async def health_check(self) -> Dict[str, Any]:
        """Check embedding generator health"""
        # DEPRECATED: provider check removed
        return {
            "status": "deprecated",
            "message": "Embedding generation has moved to Titan",
            "provider_configured": False,
            "cache_ttl": self.cache_ttl,
        }

    async def get_stats(self) -> Dict[str, Any]:
        """Get embedding generator statistics"""
        try:
            redis_client = await self._get_redis_client()
            if not redis_client:
                return {"error": "Redis client unavailable"}

            # Count cached embeddings
            pattern = f"{self.cache_prefix}:*"
            keys = await redis_client.keys(pattern)
            cache_count = len(keys)

            return {
                "cached_embeddings": cache_count,
                "daily_cost": self.daily_cost,
                "daily_limit": self.daily_limit,
                "cost_remaining": self.daily_limit - self.daily_cost,
                "cache_ttl": self.cache_ttl,
            }

        except Exception as e:
            logger.error(f"Error getting embedding generator stats: {e}")
            return {"error": str(e)}


# Global instance
_embedding_generator: Optional[EmbeddingGenerator] = None


def get_embedding_generator() -> EmbeddingGenerator:
    """Get global embedding generator instance"""
    global _embedding_generator
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    return _embedding_generator
