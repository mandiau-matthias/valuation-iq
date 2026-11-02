"""
Redis Client for Upswitch Valuation Engine
Provides async Redis connection management

Used by:
- Market Data Cache Service
- Session management
- Rate limiting
- Feature store (future)
"""

import asyncio
import redis.asyncio as redis
from typing import Optional
from src.utils.logging import get_logger

from src.config import settings

logger = get_logger(__name__)


class RedisClient:
    """
    Async Redis client wrapper with connection pooling

    Features:
    - Connection pooling
    - Auto-reconnect
    - Health checks
    - Graceful shutdown
    """

    def __init__(
        self,
        url: Optional[str] = None,
        max_connections: Optional[int] = None,
        decode_responses: bool = True
    ) -> None:
        """
        Initialize Redis client

        Args:
            url: Redis connection URL (defaults to settings.redis_url)
            max_connections: Max connections in pool (defaults to settings.redis_max_connections)
            decode_responses: Auto-decode responses to strings
        """
        self.url = url or settings.redis_url
        self.max_connections = max_connections or settings.redis_max_connections
        self.decode_responses = decode_responses

        self._client: Optional[redis.Redis] = None
        self._connection_pool: Optional[redis.ConnectionPool] = None

        # Demoted to DEBUG: __init__ creates the wrapper but does NOT connect.
        # In stateless mode the subsequent connect() raises before any pool is
        # built, so an INFO "Redis client initialized" line misleads the
        # operator into thinking Redis is live.
        logger.debug(
            "Redis client initialized",
            url=self._sanitize_url(self.url),
            max_connections=self.max_connections
        )

    def _sanitize_url(self, url: str) -> str:
        """Sanitize URL for logging (hide password)"""
        if '@' in url:
            # redis://username:password@host:port/db -> redis://***@host:port/db
            parts = url.split('@')
            return f"{parts[0].split(':')[0]}://***@{parts[1]}"
        return url

    async def connect(self) -> redis.Redis:
        """
        Create and return Redis connection with retry logic

        Returns:
            Redis client instance
            
        Raises:
            RuntimeError: If Redis is optional and not configured
        """
        # Check if Redis is optional (Brain & Muscle stateless mode)
        if settings.redis_optional or settings.is_stateless:
            logger.info("Redis is optional - running in stateless mode without Redis")
            raise RuntimeError("Redis is optional in stateless mode. Session state is managed by Titan.")
        
        if self._client is not None:
            return self._client

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                # Create connection pool with Railway-optimized settings
                self._connection_pool = redis.ConnectionPool.from_url(
                    self.url,
                    max_connections=self.max_connections,
                    decode_responses=self.decode_responses,
                    socket_timeout=settings.redis_socket_timeout,
                    socket_connect_timeout=settings.redis_socket_connect_timeout,
                    retry_on_timeout=settings.redis_retry_on_timeout,
                    health_check_interval=settings.redis_health_check_interval
                )

                # Create Redis client
                self._client = redis.Redis(connection_pool=self._connection_pool)

                # Test connection with ping
                await self._client.ping()

                logger.info(
                    "Redis connection established",
                    url=self._sanitize_url(self.url),
                    attempt=attempt + 1
                )

                return self._client

            except redis.RedisError as e:
                logger.warning(
                    f"Redis connection attempt {attempt + 1} failed",
                    error=str(e),
                    url=self._sanitize_url(self.url),
                    attempt=attempt + 1,
                    max_retries=max_retries
                )

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
                else:
                    logger.error(
                        "All Redis connection attempts failed",
                        error=str(e),
                        url=self._sanitize_url(self.url)
                    )
                    raise
            except Exception as e:
                logger.error(
                    "Unexpected error connecting to Redis",
                    error=str(e),
                    attempt=attempt + 1
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    raise

    async def disconnect(self) -> None:
        """Close Redis connection and cleanup"""
        if self._client is not None:
            try:
                await self._client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error("Error closing Redis connection", error=str(e))
            finally:
                self._client = None

        if self._connection_pool is not None:
            try:
                await self._connection_pool.disconnect()
            except Exception as e:
                logger.error("Error closing Redis connection pool", error=str(e))
            finally:
                self._connection_pool = None

    async def health_check(self) -> bool:
        """
        Check Redis connection health

        Returns:
            True if healthy, False otherwise
        """
        try:
            if self._client is None:
                return False

            await self._client.ping()
            return True

        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return False

    async def get_info(self) -> dict:
        """
        Get Redis server info

        Returns:
            Redis server info dictionary
        """
        try:
            if self._client is None:
                await self.connect()

            info = await self._client.info()
            return info

        except Exception as e:
            logger.error("Error getting Redis info", error=str(e))
            return {}

    def get_client(self) -> Optional[redis.Redis]:
        """
        Get the Redis client instance

        Returns:
            Redis client or None if not connected
        """
        return self._client


_redis_client: Optional[RedisClient] = None
_redis_lock = asyncio.Lock()


async def get_redis_client() -> redis.Redis:
    """
    Get or create global Redis client

    This is a dependency that can be injected into FastAPI routes.

    Returns:
        Redis client instance

    Example:
        ```python
        from src.database.redis_client import get_redis_client

        @router.get("/example")
        async def example(redis: redis.Redis = Depends(get_redis_client)):
            await redis.set("key", "value")
            value = await redis.get("key")
            return {"value": value}
        ```
    """
    global _redis_client

    if _redis_client is None:
        async with _redis_lock:
            if _redis_client is None:
                _redis_client = RedisClient()

    client = await _redis_client.connect()
    return client


async def initialize_redis() -> RedisClient:
    """
    Initialize Redis client for application startup

    Call this in FastAPI startup event.

    Returns:
        RedisClient instance

    Example:
        ```python
        from src.database.redis_client import initialize_redis

        @app.on_event("startup")
        async def startup():
            redis_client = await initialize_redis()
            app.state.redis_client = redis_client
        ```
    """
    global _redis_client

    # Demoted to DEBUG: in stateless mode connect() raises immediately, so
    # the "Initializing..." headline appears even though no connection is
    # established. The startup_checks layer logs the real outcome
    # ("✅ Redis connection pool initialized" or "ℹ️ Redis skipped").
    logger.debug("Initializing Redis connection...")

    _redis_client = RedisClient()
    await _redis_client.connect()

    logger.info("Redis initialization complete")

    return _redis_client


async def shutdown_redis() -> None:
    """
    Shutdown Redis client for application shutdown

    Call this in FastAPI shutdown event.

    Example:
        ```python
        from src.database.redis_client import shutdown_redis

        @app.on_event("shutdown")
        async def shutdown():
            await shutdown_redis()
        ```
    """
    global _redis_client

    if _redis_client is not None:
        logger.info("Shutting down Redis connection...")
        await _redis_client.disconnect()
        _redis_client = None
        logger.info("Redis shutdown complete")


async def test_redis_connection() -> bool:
    """
    Test Redis connection

    Returns:
        True if connection successful, False otherwise
    """
    try:
        client = RedisClient()
        redis_instance = await client.connect()

        # Test basic operations
        await redis_instance.set("test_key", "test_value", ex=10)
        value = await redis_instance.get("test_key")
        await redis_instance.delete("test_key")

        await client.disconnect()

        logger.info("Redis connection test successful")
        return True

    except Exception as e:
        logger.error("Redis connection test failed", error=str(e))
        return False
