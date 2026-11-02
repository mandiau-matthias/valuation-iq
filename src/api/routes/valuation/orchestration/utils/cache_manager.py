"""
Cache Manager

Manages cache service initialization and injection into calculators.
"""

import asyncio
from threading import Lock as ThreadingLock
from typing import Optional, Any

from src.config import get_settings
from src.utils.valuation_logger import ValuationLogger


class CacheManager:
    """
    Manager for cache service initialization and injection.

    Responsibilities:
    - Cache service initialization
    - Cache service injection into calculators
    """

    def __init__(self, logger: Optional[ValuationLogger] = None):
        """
        Initialize cache manager.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or ValuationLogger(self.__class__.__name__)
        self._cache_service_initialized = False
        self._cache_init_sync_lock = ThreadingLock()
        self._cache_init_async_lock: Optional[asyncio.Lock] = None
        debug = getattr(self.logger, "debug", lambda *_args, **_kwargs: None)
        debug("✅ CacheManager initialized")

    @property
    def _cache_init_lock(self) -> asyncio.Lock:
        if self._cache_init_async_lock is None:
            with self._cache_init_sync_lock:
                if self._cache_init_async_lock is None:
                    self._cache_init_async_lock = asyncio.Lock()
        return self._cache_init_async_lock

    async def ensure_cache_service_initialized(
        self, cache_service: Optional[Any], multiples_calculator: Optional[Any] = None
    ) -> Optional[Any]:
        """
        Lazy initialization of cache service (requires async Redis connection).

        Args:
            cache_service: Current cache service (may be None)
            multiples_calculator: Optional MultiplesCalculator to inject cache into

        Returns:
            Cache service instance (or None if initialization fails)
        """
        if self._cache_service_initialized:
            return cache_service

        async with self._cache_init_lock:
            if self._cache_service_initialized:
                return cache_service

            if cache_service is None:
                settings = get_settings()
                # Stateless mode: skip Redis entirely - session state managed by Titan
                if settings.redis_optional or settings.is_stateless:
                    self.logger.info("ℹ️ Skipping cache init - running in stateless mode (no Redis)")
                else:
                    try:
                        from src.database.redis_client import get_redis_client
                        from src.services.market.market_cache_service import create_cache_service

                        redis_client = await get_redis_client()
                        if redis_client:
                            cache_service = create_cache_service(redis_client)
                            self.logger.info("✅ Market Data Cache Service initialized (lazy)")

                            # Update MultiplesCalculator with cache service
                            if multiples_calculator and hasattr(multiples_calculator, "cache_service"):
                                multiples_calculator.cache_service = cache_service
                                # Re-inject into Step 2
                                if hasattr(multiples_calculator, "_inject_dependencies_into_steps"):
                                    multiples_calculator._inject_dependencies_into_steps()
                        else:
                            self.logger.warning("⚠️ Redis client not available")
                    except ImportError as e:
                        # Redis/market_cache_service not available (e.g. optional deps, Docker env)
                        self.logger.warning(f"⚠️ Cache service import failed (continuing without cache): {e}")
                    except RuntimeError as e:
                        # Fallback: stateless mode detected via exception (e.g. from get_redis_client)
                        if "stateless mode" in str(e).lower() or "redis is optional" in str(e).lower():
                            self.logger.info("ℹ️ Skipping cache init - running in stateless mode (no Redis)")
                        else:
                            raise
                    except Exception as e:
                        self.logger.warning(f"⚠️ Cache service lazy initialization failed: {e}")

            self._cache_service_initialized = True
            return cache_service
