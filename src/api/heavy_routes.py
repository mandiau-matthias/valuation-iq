import logging
import os
from importlib import import_module

from fastapi import Depends, FastAPI

from src.config.public_adaptive_local_migration import (
    public_adaptive_local_migration_enabled,
)


async def load_heavy_routes(app: FastAPI, logger: logging.Logger) -> None:
    """
    Load and register heavy routers during startup.

    This keeps expensive imports off module import while ensuring the route
    table is stable before the application starts serving requests.
    """
    if public_adaptive_local_migration_enabled():
        if os.environ.get("STATELESS_MODE", "").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            raise RuntimeError("Public Adaptive local migration mode requires STATELESS_MODE=true")

        from src.api.routes.stateless_calculation_router import (
            router as stateless_calculation_router,
        )
        from src.middleware.auth import require_service_auth

        app.include_router(
            stateless_calculation_router,
            prefix="/api/v2/stateless",
            tags=["stateless", "brain-muscle"],
            dependencies=[Depends(require_service_auth)],
        )
        logger.info(
            "valuation_iq_local_migration_routes_ready",
            extra={
                "profile": "public_adaptive_stateless_calculation_only.v1",
                "reports_loaded": False,
                "legacy_routes_loaded": False,
            },
        )
        return

    # WeasyPrint: warning filters once + reapply vendor levels + root handler noise filter.
    import_module("src.services.infrastructure.weasyprint_env")
    from src.services.infrastructure.weasyprint_env import (
        attach_vendor_noise_filter_to_root_handlers,
        configure_weasyprint_env,
        reapply_pdf_vendor_logging_levels,
    )

    configure_weasyprint_env()
    reapply_pdf_vendor_logging_levels()
    attach_vendor_noise_filter_to_root_handlers()

    try:
        from src.api.routes.acquisition_shortlists import router as acquisition_shortlists_router
        from src.api.routes.buyer_ready_package import router as buyer_ready_package_router
        from src.api.routes.normalization import router as normalization_router
        from src.api.routes.reports import router as reports_router
        from src.api.routes.stateless_router import router as stateless_router
        from src.api.routes.valuation.valuation import router as valuation_router

        app.include_router(valuation_router, prefix="/api/v1")  # Legacy valuation API
        app.include_router(acquisition_shortlists_router, prefix="/api/v1")
        app.include_router(buyer_ready_package_router, prefix="/api/v1")  # Stage 5 package
        app.include_router(normalization_router, prefix="/api/v1")  # Normalization helpers
        app.include_router(reports_router, prefix="/api/v1")  # Reports (PDF from HTML)
        app.include_router(stateless_router)  # PRIMARY: Stateless calculation API

        validate_report_transformer(logger)
        log_pdf_generation_availability(logger)

        bound_port = os.environ.get("PORT", "8080")
        # DEBUG: "🎉 Upswitch Valuation Engine API startup complete!" + the
        # Uvicorn "Running on http://0.0.0.0:8080" line is the canonical
        # boot signal.
        logger.debug(
            "Heavy routes loaded",
            extra={"port": bound_port, "port_source": "env" if "PORT" in os.environ else "default"},
        )
    except Exception as exc:
        logger.error("❌ Failed to load heavy routes: %s", exc, exc_info=True)
        raise


def validate_report_transformer(logger: logging.Logger) -> None:
    """Validate lazy report-transformer imports early enough to fail deploys loudly."""
    try:
        from src.services.infrastructure.report_data_transformer import _get_orchestrator

        _get_orchestrator()
        logger.debug("✅ Valuation path imports validated (report transformer ready)")
    except (ImportError, ModuleNotFoundError) as exc:
        logger.warning(
            "⚠️ Report transformer lazy import failed (will fail on first valuation): %s",
            exc,
        )


def log_pdf_generation_availability(logger: logging.Logger) -> None:
    """Log WeasyPrint availability after route imports have loaded the PDF strategy."""
    try:
        from src.services.infrastructure.report_generation.strategies.pdf_strategy import (
            WEASYPRINT_AVAILABLE,
            WEASYPRINT_IMPORT_ERROR,
        )

        if WEASYPRINT_AVAILABLE:
            # DEBUG: WeasyPrint missing is loud-warning-worthy; presence is
            # the expected default and not worth a banner.
            logger.debug("✅ WeasyPrint available — PDF generation enabled")
            return

        err_msg = str(WEASYPRINT_IMPORT_ERROR) if WEASYPRINT_IMPORT_ERROR else "unknown"
        logger.warning(
            "⚠️ WeasyPrint unavailable — PDF generation will fail import_error=%s", err_msg
        )
    except ImportError:
        logger.warning("⚠️ WeasyPrint unavailable — PDF generation will fail")
