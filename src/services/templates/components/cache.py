"""
Template Cache Service

Multi-level template caching with Redis support and memory fallback.
"""

from typing import Optional, Dict, Any
import hashlib
import json
import logging
import time
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = logging.getLogger(__name__)


class TemplateCacheService:
    """Multi-level template caching"""

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.memory_cache: Dict[str, Dict[str, Any]] = {}  # {key: {value, expiry}}
        self.logger = logging.getLogger(f"{__name__}.TemplateCacheService")

        # Cache statistics
        self.stats = {"hits": 0, "misses": 0, "sets": 0, "errors": 0}

    async def get(self, key: str) -> Optional[str]:
        """Get cached template"""
        try:
            # Try Redis first if available
            if self.redis:
                value = await self.redis.get(key)
                if value:
                    self.stats["hits"] += 1
                    self.logger.debug(f"Redis cache hit: {key}")
                    return value.decode() if isinstance(value, bytes) else value

            # Fallback to memory cache
            if key in self.memory_cache:
                cache_entry = self.memory_cache[key]
                if cache_entry["expiry"] > time.time():
                    self.stats["hits"] += 1
                    self.logger.debug(f"Memory cache hit: {key}")
                    return cache_entry["value"]
                else:
                    # Expired entry
                    del self.memory_cache[key]

            self.stats["misses"] += 1
            self.logger.debug(f"Cache miss: {key}")
            return None

        except Exception as e:
            self.stats["errors"] += 1
            self.logger.warning(f"Cache get error for {key}: {e}")
            return None

    async def set(self, key: str, value: str, ttl: int = 3600):
        """Cache template"""
        try:
            # Try Redis first if available
            if self.redis:
                await self.redis.setex(key, ttl, value)
                self.stats["sets"] += 1
                self.logger.debug(f"Cached in Redis: {key}")
                return

            # Fallback to memory cache
            expiry = time.time() + ttl
            self.memory_cache[key] = {"value": value, "expiry": expiry}
            self.stats["sets"] += 1
            self.logger.debug(f"Cached in memory: {key}")

        except Exception as e:
            self.stats["errors"] += 1
            self.logger.warning(f"Cache set error for {key}: {e}")

    async def delete(self, key: str):
        """Delete cached template"""
        try:
            if self.redis:
                await self.redis.delete(key)

            if key in self.memory_cache:
                del self.memory_cache[key]

            self.logger.debug(f"Deleted cache: {key}")

        except Exception as e:
            self.logger.warning(f"Cache delete error for {key}: {e}")

    async def invalidate(self, pattern: str):
        """Invalidate cache by pattern"""
        try:
            deleted_count = 0

            if self.redis:
                keys = await self.redis.keys(pattern)
                if keys:
                    await self.redis.delete(*keys)
                    deleted_count = len(keys)

            # Also clean memory cache
            keys_to_delete = [k for k in self.memory_cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self.memory_cache[key]
                deleted_count += 1

            self.logger.info(f"Invalidated {deleted_count} cache entries matching: {pattern}")

        except Exception as e:
            self.logger.warning(f"Cache invalidation error for pattern {pattern}: {e}")

    def generate_cache_key(self, component: str, data: Dict[str, Any]) -> str:
        """Generate deterministic cache key"""
        # Create deterministic hash of data
        data_str = json.dumps(data, sort_keys=True, default=str)
        hash_str = hashlib.md5(data_str.encode(), usedforsecurity=False).hexdigest()
        return f"template:{component}:{hash_str}"

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        return {
            **self.stats,
            "hit_rate_percent": round(hit_rate, 2),
            "memory_cache_size": len(self.memory_cache),
            "redis_available": self.redis is not None,
        }

    def clear_stats(self):
        """Clear cache statistics"""
        self.stats = {"hits": 0, "misses": 0, "sets": 0, "errors": 0}

    async def clear_all(self):
        """Clear all cache"""
        try:
            if self.redis:
                # Clear all template cache keys
                keys = await self.redis.keys("template:*")
                if keys:
                    await self.redis.delete(*keys)

            self.memory_cache.clear()
            self.logger.info("Cleared all cache")

        except Exception as e:
            self.logger.warning(f"Cache clear error: {e}")

    def cleanup_expired(self):
        """Clean up expired memory cache entries"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.memory_cache.items() if entry["expiry"] <= current_time
        ]

        for key in expired_keys:
            del self.memory_cache[key]

        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
