"""
Valuation Routes - Refactored Orchestrator

DEPRECATED: This router is NOT wired into ``main.py`` and is therefore dead
code.  The production API uses the routers registered in ``main.py`` directly
(``valuation/``, ``stateless/``, ``reports/``).  Safe to delete once confirmed
no external scripts import it.
"""

from fastapi import APIRouter
from src.utils.logging import get_logger

# Import route modules
from . import quick_valuation_routes
from . import comprehensive_valuation_routes
from . import valuation_status_routes
from . import valuation_history_routes

logger = get_logger(__name__)

# Create main router
router = APIRouter()

# Include all route modules
router.include_router(
    quick_valuation_routes.router,
    tags=["quick-valuation"]
)

router.include_router(
    comprehensive_valuation_routes.router,
    tags=["comprehensive-valuation"]
)

router.include_router(
    valuation_status_routes.router,
    prefix="/status",
    tags=["valuation-status"]
)

router.include_router(
    valuation_history_routes.router,
    prefix="/history",
    tags=["valuation-history"]
)

logger.info(
    "Valuation routes refactored orchestrator initialized",
    routes_included=["quick", "comprehensive", "status", "history"]
)


# Export router for backward compatibility
__all__ = ["router"]
