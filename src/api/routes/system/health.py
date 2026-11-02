from src.utils.exceptions import APIError, DataValidationError

"""
Health Monitoring Endpoints for System Services

This module provides health check endpoints for monitoring the system,
including cache status and system resources.

BRAIN & MUSCLE ARCHITECTURE:
AI/LLM services have been moved to Titan (The Brain).
For AI health, check Titan's /api/v2/ai/health endpoint.
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List
from datetime import datetime

from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.api.dependencies.cache_service import get_optional_cache_service

router = APIRouter()


@router.get("/health/ai")
async def get_ai_health() -> Dict[str, Any]:
    """
    Get AI system health status

    BRAIN & MUSCLE ARCHITECTURE:
    AI services have been moved to Titan. This endpoint returns a deprecation notice.
    For AI health, use Titan's /api/v2/ai/health endpoint.
    """
    return {
        "status": "deprecated",
        "message": "AI services have been moved to Titan (The Brain). Use Titan's /api/v2/ai/health endpoint.",
        "architecture": "brain_muscle",
        "titan_endpoint": "/api/v2/ai/health",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health/ai/detailed")
async def get_detailed_ai_health() -> Dict[str, Any]:
    """
    Get detailed AI system health with circuit breaker diagnostics

    BRAIN & MUSCLE ARCHITECTURE:
    AI services have been moved to Titan.
    """
    return {
        "status": "deprecated",
        "message": "AI services have been moved to Titan (The Brain). Use Titan's /api/v2/ai/health endpoint.",
        "architecture": "brain_muscle",
        "titan_endpoint": "/api/v2/ai/health",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health/ai/circuit-breakers")
async def get_circuit_breaker_status() -> Dict[str, Any]:
    """
    Get detailed circuit breaker status for all AI models

    BRAIN & MUSCLE ARCHITECTURE:
    AI services have been moved to Titan.
    """
    return {
        "status": "deprecated",
        "message": "AI services have been moved to Titan (The Brain). Circuit breakers are now managed by Titan.",
        "architecture": "brain_muscle",
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/health/ai/reset-circuit-breaker/{model_name}")
async def reset_circuit_breaker(model_name: str) -> Dict[str, Any]:
    """
    Manually reset a circuit breaker for a specific model

    BRAIN & MUSCLE ARCHITECTURE:
    AI services have been moved to Titan.
    """
    return {
        "status": "deprecated",
        "message": "AI services have been moved to Titan (The Brain). Circuit breaker reset is now managed by Titan.",
        "model_name": model_name,
        "architecture": "brain_muscle",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health/cache")
async def get_cache_health(request: Request) -> Dict[str, Any]:
    """
    Get Market Data Cache health status (Aphrodite pattern)

    Returns:
        - Cache availability
        - Hit/miss rates
        - Performance metrics
        - Memory usage
        - TTL strategies
    """
    try:
        # Check if cache service is available
        cache_service = await get_optional_cache_service(request)
        if cache_service is None:
            return {
                "status": "unavailable",
                "message": "Cache service not initialized",
                "timestamp": datetime.now().isoformat(),
            }

        # Get comprehensive cache statistics
        cache_stats = cache_service.get_stats()
        cache_info = await cache_service.get_cache_info()

        # Calculate health status
        hit_rate = cache_stats.get("hit_rate_percent", 0)
        status = "healthy" if hit_rate > 80 else "degraded" if hit_rate > 50 else "unhealthy"

        return {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "performance": {
                "hit_rate_percent": hit_rate,
                "total_requests": cache_stats.get("total_requests", 0),
                "cache_hits": cache_stats.get("hits", 0),
                "cache_misses": cache_stats.get("misses", 0),
                "api_calls_saved": cache_stats.get("api_calls_saved", 0),
                "errors": cache_stats.get("errors", 0),
            },
            "redis": {
                "memory_used": cache_info.get("redis_memory_used", "N/A"),
                "memory_peak": cache_info.get("redis_memory_peak", "N/A"),
                "total_keys": cache_info.get("total_keys", 0),
            },
            "configuration": {
                "strategy": cache_stats.get("strategy", "balanced"),
                "key_prefix": cache_stats.get("key_prefix", "upswitch:market:"),
                "ttl_strategies": cache_info.get("ttl_strategies", {}),
            },
            "recommendations": _get_cache_recommendations(cache_stats),
        }

    except APIError as e:
        raise HTTPException(status_code=500, detail="Failed to get cache health status.")


def _get_cache_recommendations(stats: Dict[str, Any]) -> List[str]:
    """Generate cache optimization recommendations"""
    recommendations = []

    hit_rate = stats.get("hit_rate_percent", 0)
    total_requests = stats.get("total_requests", 0)
    errors = stats.get("errors", 0)

    if hit_rate < 50:
        recommendations.append("Low hit rate detected - consider warming cache with common queries")
    elif hit_rate < 80:
        recommendations.append("Moderate hit rate - cache is working but could be optimized")

    if total_requests > 0 and errors / total_requests > 0.1:
        recommendations.append("High error rate detected - check Redis connectivity")

    if total_requests == 0:
        recommendations.append("No cache requests yet - cache may not be integrated properly")

    if not recommendations:
        recommendations.append("Cache operating optimally - 95%+ hit rate target achieved")

    return recommendations
