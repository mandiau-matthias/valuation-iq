"""Route registration helpers for the ValuationIQ API."""

import logging
from typing import Tuple

from fastapi import FastAPI

from src.config import Settings
from src.config.public_adaptive_local_migration import public_adaptive_local_migration_enabled

HEAVY_ROUTE_PREFIXES: Tuple[str, ...] = (
    "/api/v1/valuation",
    "/api/v1/reports",
    "/api/v1/buyer-ready-package",
    "/api/v2/stateless",
)


def is_heavy_route(path: str) -> bool:
    """Return True when a request path belongs to a startup-gated heavy router."""
    return any(path.startswith(prefix) for prefix in HEAVY_ROUTE_PREFIXES)


def register_lightweight_routes(app: FastAPI, logger: logging.Logger, settings: Settings) -> None:
    """Register routes that are safe to load before heavy startup checks."""
    if public_adaptive_local_migration_enabled():
        # The local bulk runner needs only the canonical stateless calculation
        # route, which is registered by ``load_heavy_routes`` after startup.
        # Operational health/metrics endpoints are registered independently by
        # the app factory. Avoid importing or exposing registry, business-type,
        # preflight, accounting, sellability, or AI-health handlers in this
        # fail-closed profile.
        logger.info("ValuationIQ local migration profile skipped non-canonical routes")
        return

    # Kept routers (The Muscle) - lightweight routers registered at load time.
    from src.api.routes.accounting_analysis import router as accounting_analysis_router
    from src.api.routes.acquisition_scenarios import router as acquisition_scenarios_router
    from src.api.routes.business.business_types import router as business_types_router
    from src.api.routes.preflight import router as preflight_router
    from src.api.routes.registry.registry import router as registry_router
    from src.api.routes.sellability import router as sellability_router
    from src.api.routes.system.health import router as health_router

    app.include_router(registry_router, prefix="/api/v1/registry")
    app.include_router(registry_router, prefix="/api/registry")
    app.include_router(business_types_router, prefix="/api/v1")
    app.include_router(accounting_analysis_router, prefix="/api/v1")
    app.include_router(health_router)
    if settings.debug:
        from src.api.routes.system.debug import router as debug_router

        app.include_router(debug_router)
    app.include_router(sellability_router, prefix="/api/v1")
    app.include_router(acquisition_scenarios_router, prefix="/api/v1")
    app.include_router(preflight_router, prefix="/api/v1")

    logger.debug("✅ Lightweight routers registered (Brain & Muscle Architecture)")
    logger.debug("✅ Registry router registered with backward compatibility")
