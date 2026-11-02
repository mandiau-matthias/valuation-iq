"""
AI Response Caching for Validation and Enum Classification
Reduces API calls and improves performance
"""

import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from src.utils.decimal_helpers import from_decimal, to_decimal

logger = logging.getLogger(__name__)


@dataclass
class CachedResponse:
    """Cached AI response with metadata"""

    response: Any
    timestamp: Decimal
    confidence: Decimal
    hit_count: int = 0


class AIResponseCache:
    """
    LRU cache for AI responses with TTL
    Caches validation responses and enum classifications
    """

    def __init__(self, max_size: int = 10000, ttl_seconds: int = 604800):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds  # 7 days default
        self._lock = threading.Lock()
        self.validation_cache: Dict[str, CachedResponse] = {}
        self.enum_cache: Dict[str, CachedResponse] = {}
        self.stats = {
            "validation_hits": 0,
            "validation_misses": 0,
            "enum_hits": 0,
            "enum_misses": 0,
        }

    def _generate_cache_key(self, field: str, value: Any, context_hash: str = "") -> str:
        """Generate cache key from field, value, and context"""
        key_str = f"{field}:{value}:{context_hash}"
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    def _is_expired(self, cached: CachedResponse) -> bool:
        """Check if cache entry is expired"""
        return time.time() - cached.timestamp > self.ttl_seconds

    def _evict_lru(self, cache: Dict[str, CachedResponse]):
        """Evict least recently used entry"""
        if len(cache) >= self.max_size:
            # Find entry with lowest hit_count
            lru_key = min(cache.keys(), key=lambda k: cache[k].hit_count)
            del cache[lru_key]
            logger.debug(f"Evicted LRU cache entry: {lru_key}")

    def get_validation(self, field: str, value: Any, context_summary: str = "") -> Optional[Any]:
        """Get cached validation response"""
        cache_key = self._generate_cache_key(field, value, context_summary)

        with self._lock:
            if cache_key in self.validation_cache:
                cached = self.validation_cache[cache_key]

                if self._is_expired(cached):
                    del self.validation_cache[cache_key]
                    self.stats["validation_misses"] += 1
                    return None

                cached.hit_count += 1
                self.stats["validation_hits"] += 1
                logger.debug(f"Validation cache hit: {field}={value} (hits: {cached.hit_count})")
                return cached.response

            self.stats["validation_misses"] += 1
            return None

    def set_validation(
        self, field: str, value: Any, response: Any, confidence: Decimal, context_summary: str = ""
    ):
        """Cache validation response"""
        cache_key = self._generate_cache_key(field, value, context_summary)

        with self._lock:
            self._evict_lru(self.validation_cache)
            self.validation_cache[cache_key] = CachedResponse(
                response=response, timestamp=time.time(), confidence=confidence, hit_count=0
            )
        logger.debug(f"Cached validation: {field}={value}")

    def get_enum(self, user_input: str, enum_type: str) -> Optional[Tuple[Any, float]]:
        """Get cached enum classification"""
        cache_key = self._generate_cache_key(enum_type, user_input)

        with self._lock:
            if cache_key in self.enum_cache:
                cached = self.enum_cache[cache_key]

                if self._is_expired(cached):
                    del self.enum_cache[cache_key]
                    self.stats["enum_misses"] += 1
                    return None

                cached.hit_count += 1
                self.stats["enum_hits"] += 1
                logger.debug(f"Enum cache hit: {enum_type}={user_input} (hits: {cached.hit_count})")
                return cached.response

            self.stats["enum_misses"] += 1
            return None

    def set_enum(self, user_input: str, enum_type: str, enum_value: Any, confidence: Decimal):
        """Cache enum classification"""
        cache_key = self._generate_cache_key(enum_type, user_input)

        with self._lock:
            self._evict_lru(self.enum_cache)
            self.enum_cache[cache_key] = CachedResponse(
                response=(enum_value, confidence),
                timestamp=time.time(),
                confidence=confidence,
                hit_count=0,
            )
        logger.debug(f"Cached enum: {enum_type}={user_input} -> {enum_value}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        validation_total = self.stats["validation_hits"] + self.stats["validation_misses"]
        enum_total = self.stats["enum_hits"] + self.stats["enum_misses"]

        return {
            **self.stats,
            "validation_hit_rate": (
                self.stats["validation_hits"] / validation_total if validation_total > 0 else 0
            ),
            "enum_hit_rate": self.stats["enum_hits"] / enum_total if enum_total > 0 else 0,
            "validation_cache_size": len(self.validation_cache),
            "enum_cache_size": len(self.enum_cache),
        }


_ai_cache: Optional[AIResponseCache] = None
_ai_cache_lock = threading.Lock()


def get_ai_cache() -> AIResponseCache:
    """Get or create global AI cache instance"""
    global _ai_cache
    if _ai_cache is None:
        with _ai_cache_lock:
            if _ai_cache is None:
                _ai_cache = AIResponseCache()
                logger.info("AI response cache initialized")
    return _ai_cache
