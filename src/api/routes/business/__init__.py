"""
Business Analysis API Routes Package

This package contains all business analysis-related API endpoints including:
- Business types management endpoints
- Methodology recommendation endpoints

Routes are organized under /api/v1/business-type/* prefix.
"""

from .business_types import router as business_types_router

__all__ = [
    "business_types_router",
]
