"""
Debug endpoints for ValuationIQ - Brain & Muscle Architecture

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) is a stateless calculation engine.
Debug endpoints provide system status and configuration info.

Session context debugging is handled by Titan (The Brain).
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging
import sys
import os

from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug", tags=["debug"])
settings = get_settings()


@router.get("/status")
async def get_debug_status() -> Dict[str, Any]:
    """Get ValuationIQ debug status (only available in debug mode)"""
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "service": "ValuationIQ",
        "role": "The Muscle (Stateless Calculation Engine)",
        "architecture": "Brain & Muscle",
        "stateless_mode": settings.stateless_mode,
        "python_version": sys.version,
        "environment": settings.environment,
        "endpoints": {
            "stateless_calculate": "/api/v2/stateless/calculate",
            "stateless_validate": "/api/v2/stateless/validate",
            "stateless_report": "/api/v2/stateless/generate-report",
        },
        "note": "Session context debugging is handled by Titan (The Brain)"
    }


@router.get("/config")
async def get_debug_config() -> Dict[str, Any]:
    """Get non-sensitive configuration for debugging (only available in debug mode)"""
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "stateless_mode": settings.stateless_mode,
        "database_optional": settings.database_optional,
        "redis_optional": settings.redis_optional,
        "environment": settings.environment,
        "log_level": settings.log_level,
        "titan_api_url": settings.titan_api_url,
    }


@router.get("/imports")
async def check_imports() -> Dict[str, Any]:
    """Check that core imports work correctly (only available in debug mode)"""
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")

    results = {}
    
    # Check core imports
    try:
        from src.services.core import ValuationMCPService
        results["ValuationMCPService"] = "OK"
    except Exception as e:
        results["ValuationMCPService"] = f"FAILED: {str(e)}"
    
    try:
        from src.services.triage import GapAnalysisService
        results["GapAnalysisService"] = "OK"
    except Exception as e:
        results["GapAnalysisService"] = f"FAILED: {str(e)}"
    
    try:
        from src.api.routes.stateless_router import router as stateless_router
        results["stateless_router"] = "OK"
    except Exception as e:
        results["stateless_router"] = f"FAILED: {str(e)}"
    
    try:
        from src.api.schemas.stateless_api import CalculateRequest, CalculateResponse
        results["stateless_schemas"] = "OK"
    except Exception as e:
        results["stateless_schemas"] = f"FAILED: {str(e)}"
    
    all_ok = all(v == "OK" for v in results.values())
    
    return {
        "status": "healthy" if all_ok else "unhealthy",
        "imports": results,
        "all_imports_ok": all_ok
    }
