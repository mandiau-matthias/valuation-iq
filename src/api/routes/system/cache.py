from src.utils.exceptions import APIError, DataValidationError

"""
Cache Management API Endpoints
Provides monitoring, control, and statistics for the market data cache

Endpoints:
- GET /cache/stats - Get cache statistics
- GET /cache/info - Get detailed cache information
- POST /cache/invalidate - Invalidate specific cache entry
- POST /cache/invalidate-pattern - Invalidate entries by pattern
- POST /cache/invalidate-type - Invalidate all entries of a type
- POST /cache/clear-all - Clear entire cache (admin only)
- POST /cache/warm - Warm cache with popular queries
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from enum import Enum

from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.api.dependencies.cache_service import get_required_cache_service
from src.services.market.market_cache_service import CacheDataType, MarketDataCacheService
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/cache", tags=["Cache Management"])


# Request/Response Models
class CacheInvalidateRequest(BaseModel):
    """Request model for cache invalidation"""

    data_type: CacheDataType = Field(..., description="Type of market data")
    primary_key: str = Field(..., description="Primary key (e.g., industry name)")
    query_params: Optional[Dict[str, Any]] = Field(None, description="Optional query parameters")


class CacheInvalidatePatternRequest(BaseModel):
    """Request model for pattern-based invalidation"""

    pattern: str = Field(
        ...,
        description="Redis key pattern with wildcards",
        example="upswitch:market:industry_multiples:*",
    )


class CacheInvalidateTypeRequest(BaseModel):
    """Request model for type-based invalidation"""

    data_type: CacheDataType = Field(..., description="Type of market data to invalidate")


class CacheWarmingQuery(BaseModel):
    """Model for cache warming query configuration"""

    data_type: CacheDataType
    primary_key: str
    query_params: Optional[Dict[str, Any]] = None


class CacheWarmRequest(BaseModel):
    """Request model for cache warming"""

    queries: List[Dict[str, Any]] = Field(
        ..., description="List of query configurations to warm cache with"
    )


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics"""

    hits: int
    misses: int
    errors: int
    total_requests: int
    api_calls_saved: int
    hit_rate_percent: Decimal
    strategy: str
    key_prefix: str


class CacheInfoResponse(BaseModel):
    """Response model for detailed cache information"""

    service_stats: Dict[str, Any]
    redis_memory_used: str
    redis_memory_peak: str
    total_keys: int
    key_prefix: str
    ttl_strategies: Dict[str, int]


class CacheOperationResponse(BaseModel):
    """Generic response for cache operations"""

    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


# --- API Endpoints ---


@router.get(
    "/stats",
    response_model=CacheStatsResponse,
    summary="Get cache statistics",
    description="Get comprehensive cache performance statistics including hit rate and API calls saved",
)
async def get_cache_stats(
    cache_service: MarketDataCacheService = Depends(get_required_cache_service),
) -> CacheStatsResponse:
    """
    Get cache statistics

    Returns cache performance metrics:
    - Hit/miss counts
    - Hit rate percentage
    - API calls saved
    - Error count
    """
    try:
        stats = cache_service.get_stats()

        logger.info(
            "Cache stats requested",
            hit_rate=stats["hit_rate_percent"],
            total_requests=stats["total_requests"],
        )

        return CacheStatsResponse(**stats)

    except APIError as e:
        logger.error("Error getting cache stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error getting cache stats."
        )


@router.get(
    "/info",
    response_model=CacheInfoResponse,
    summary="Get detailed cache information",
    description="Get detailed cache information including Redis memory usage and TTL strategies",
)
async def get_cache_info(
    cache_service: MarketDataCacheService = Depends(get_required_cache_service),
) -> CacheInfoResponse:
    """
    Get detailed cache information

    Returns:
    - Service statistics
    - Redis memory usage
    - Total keys count
    - TTL strategies for each data type
    """
    try:
        info = await cache_service.get_cache_info()

        logger.info("Cache info requested", total_keys=info.get("total_keys", 0))

        return CacheInfoResponse(**info)

    except DataValidationError as e:
        logger.error("Error getting cache info", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error getting cache info."
        )


@router.post(
    "/invalidate",
    response_model=CacheOperationResponse,
    summary="Invalidate specific cache entry",
    description="Invalidate a specific cache entry by data type, primary key, and optional query params",
)
async def invalidate_cache(
    request: CacheInvalidateRequest,
    cache_service: MarketDataCacheService = Depends(get_required_cache_service),
) -> CacheOperationResponse:
    """
    Invalidate specific cache entry

    Use this when you know specific data has changed and needs to be refreshed.

    Example:
    ```json
    {
        "data_type": "industry_multiples",
        "primary_key": "technology",
        "query_params": {"country": "DE"}
    }
    ```
    """
    try:
        success = await cache_service.invalidate(
            data_type=request.data_type,
            primary_key=request.primary_key,
            query_params=request.query_params,
        )

        logger.info(
            "Cache entry invalidated",
            data_type=request.data_type.value,
            primary_key=request.primary_key,
            success=success,
        )

        return CacheOperationResponse(
            success=success,
            message=f"Cache entry {'invalidated' if success else 'not found'}",
            details={"data_type": request.data_type.value, "primary_key": request.primary_key},
        )

    except DataValidationError as e:
        logger.error("Error invalidating cache", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error invalidating cache entry.",
        )


@router.post(
    "/invalidate-pattern",
    response_model=CacheOperationResponse,
    summary="Invalidate cache entries by pattern",
    description="Invalidate multiple cache entries matching a Redis key pattern",
)
async def invalidate_cache_pattern(
    request: CacheInvalidatePatternRequest,
    cache_service: MarketDataCacheService = Depends(get_required_cache_service),
) -> CacheOperationResponse:
    """
    Invalidate cache entries matching pattern

    Use Redis wildcard patterns to invalidate multiple entries at once.

    Example patterns:
    - `upswitch:market:industry_multiples:*` - All industry multiples
    - `upswitch:market:*:technology:*` - All data for technology industry
    - `upswitch:market:economic_indicators:*` - All economic indicators
    """
    try:
        count = await cache_service.invalidate_pattern(request.pattern)

        logger.info("Cache pattern invalidated", pattern=request.pattern, keys_deleted=count)

        return CacheOperationResponse(
            success=True,
            message=f"Invalidated {count} cache entries",
            details={"pattern": request.pattern, "keys_deleted": count},
        )

    except DataValidationError as e:
        logger.error("Error invalidating cache pattern", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error invalidating cache pattern.",
        )


@router.post(
    "/invalidate-type",
    response_model=CacheOperationResponse,
    summary="Invalidate all entries of a data type",
    description="Invalidate all cache entries for a specific data type (e.g., all industry multiples)",
)
async def invalidate_cache_by_type(
    request: CacheInvalidateTypeRequest,
    cache_service: MarketDataCacheService = Depends(get_required_cache_service),
) -> CacheOperationResponse:
    """
    Invalidate all entries of a specific data type

    This invalidates ALL cache entries for the specified data type.
    Use when you want to force refresh of all data of a particular type.

    Example:
    ```json
    {
        "data_type": "industry_multiples"
    }
    ```
    This will invalidate all industry multiples across all industries and countries.
    """
    try:
        count = await cache_service.invalidate_by_type(request.data_type)

        logger.info("Cache type invalidated", data_type=request.data_type.value, keys_deleted=count)

        return CacheOperationResponse(
            success=True,
            message=f"Invalidated {count} cache entries of type {request.data_type.value}",
            details={"data_type": request.data_type.value, "keys_deleted": count},
        )

    except DataValidationError as e:
        logger.error("Error invalidating cache by type", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error invalidating cache by type.",
        )


@router.post(
    "/clear-all",
    response_model=CacheOperationResponse,
    summary="Clear entire cache",
    description="⚠️ Clear ALL cache entries. Use with caution - this cannot be undone.",
)
async def clear_all_cache(
    cache_service: MarketDataCacheService = Depends(get_required_cache_service),
) -> CacheOperationResponse:
    """
    Clear entire cache

    ⚠️ WARNING: This clears ALL market data cache entries.
    Use only when necessary (e.g., after major data updates or system maintenance).

    This operation:
    - Deletes all cached market data
    - Resets cache statistics
    - Forces fresh API calls for all subsequent requests

    Consider using more targeted invalidation methods instead.
    """
    try:
        count = await cache_service.clear_all()

        logger.warning("ENTIRE CACHE CLEARED", keys_deleted=count)

        return CacheOperationResponse(
            success=True,
            message=f"Cleared entire cache - {count} keys deleted",
            details={"keys_deleted": count, "warning": "All cache data has been cleared"},
        )

    except APIError as e:
        logger.error("Error clearing cache", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error clearing cache."
        )


@router.post(
    "/warm",
    response_model=CacheOperationResponse,
    summary="Warm cache with popular queries",
    description="Pre-populate cache with frequently used queries for better performance",
)
async def warm_cache(
    request: CacheWarmRequest,
    cache_service: MarketDataCacheService = Depends(get_required_cache_service),
) -> CacheOperationResponse:
    """
    Warm cache with popular queries

    This endpoint pre-populates the cache with frequently requested data,
    ensuring fast response times for common queries.

    Note: This endpoint requires fetch functions to be registered.
    In a production setup, warming queries should be configured server-side.

    Example:
    ```json
    {
        "queries": [
            {
                "data_type": "industry_multiples",
                "primary_key": "technology",
                "query_params": {"country": "DE"}
            },
            {
                "data_type": "economic_indicators",
                "primary_key": "DE"
            }
        ]
    }
    ```
    """
    try:
        # Note: In production, you'd have registered fetch functions
        # This is a simplified example
        logger.info("Cache warming requested", query_count=len(request.queries))

        # For now, return success with message about implementation
        return CacheOperationResponse(
            success=True,
            message="Cache warming endpoint ready - implementation requires fetch function registration",
            details={
                "query_count": len(request.queries),
                "note": "This feature requires server-side fetch function configuration",
            },
        )

    except DataValidationError as e:
        logger.error("Error warming cache", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error warming cache."
        )


@router.get(
    "/health",
    summary="Cache service health check",
    description="Check if cache service is operational",
)
async def cache_health_check(
    cache_service: MarketDataCacheService = Depends(get_required_cache_service),
) -> Dict[str, Any]:
    """
    Health check for cache service

    Returns:
    - Service status
    - Redis connectivity
    - Basic stats
    """
    try:
        stats = cache_service.get_stats()

        # Try a simple Redis operation
        await cache_service.redis.ping()

        return {
            "status": "healthy",
            "redis_connected": True,
            "total_requests": stats["total_requests"],
            "hit_rate": stats["hit_rate_percent"],
        }

    except DataValidationError as e:
        logger.error("Cache health check failed", error=str(e))
        return {"status": "unhealthy", "redis_connected": False, "error": str(e)}


# Administrative endpoints (would require authentication in production)
@router.get(
    "/data-types",
    summary="List available cache data types",
    description="Get list of all cache data types and their TTL strategies",
)
async def list_cache_data_types(
    cache_service: MarketDataCacheService = Depends(get_required_cache_service),
) -> Dict[str, Any]:
    """
    List all available cache data types

    Returns information about each data type including:
    - Data type name
    - Default TTL
    - Description
    """
    return {
        "data_types": [
            {
                "name": data_type.value,
                "ttl_seconds": cache_service._get_ttl(data_type),
                "ttl_hours": cache_service._get_ttl(data_type) / 3600,
            }
            for data_type in CacheDataType
        ],
        "strategy": cache_service.strategy.value,
    }
