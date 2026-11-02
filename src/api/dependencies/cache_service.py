"""Cache-service dependencies backed by FastAPI application state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from fastapi import HTTPException, Request, status

if TYPE_CHECKING:
    from src.services.market.market_cache_service import MarketDataCacheService


CACHE_SERVICE_STATE_KEY = "cache_service"


async def get_optional_cache_service(request: Request) -> Optional[MarketDataCacheService]:
    """Return the market-data cache service when it has been initialized."""
    return getattr(request.app.state, CACHE_SERVICE_STATE_KEY, None)


async def get_required_cache_service(request: Request) -> MarketDataCacheService:
    """Return the cache service or fail with the API's standard unavailable response."""
    cache_service = await get_optional_cache_service(request)
    if cache_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service not initialized",
        )
    return cache_service
