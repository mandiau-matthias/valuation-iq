"""
System API Routes Package

This package contains all system-related API endpoints including:
- Health check endpoints
- Cache management endpoints
- System status endpoints

Routes are organized under /health/* and /api/v1/cache/* prefixes.
"""

from .health import router as health_router
from .cache import router as cache_router

__all__ = [
    "health_router",
    "cache_router",
]
