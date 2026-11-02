"""
Registry API Routes Package

This package contains all company registry-related API endpoints including:
- Company search endpoints
- Company details endpoints
- Financial data endpoints
- Registry status endpoints

Routes are organized under /api/registry/* prefix. Belgian KBO reads are
proxied to Titan by ``registry_router``.
"""

from .registry import router as registry_router
from .registry_types import *

__all__ = [
    "registry_router",
]
