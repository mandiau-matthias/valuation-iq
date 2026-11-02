"""Application lifecycle registration for the ValuationIQ API."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI

from src.api.heavy_routes import load_heavy_routes
from src.api.startup_checks import (
    initialize_redis_pool,
    log_jwt_configuration,
    validate_database_or_stateless_cache,
    warm_academic_metadata,
    warm_country_data_cache,
)


class AppReadiness:
    """Mutable readiness state shared by startup and readiness probes."""

    def __init__(self) -> None:
        self._is_ready = False
        self.boot_id = str(uuid.uuid4())
        self.started_at = datetime.now(timezone.utc)
        self.ready_at: datetime | None = None

    def is_ready(self) -> bool:
        return self._is_ready

    def mark_ready(self) -> None:
        self._is_ready = True
        if self.ready_at is None:
            self.ready_at = datetime.now(timezone.utc)

    def mark_not_ready(self) -> None:
        self._is_ready = False

    def snapshot(self) -> dict[str, object]:
        """Stable per-process identity makes deploy restarts observable."""
        return {
            "boot_id": self.boot_id,
            "started_at": self.started_at.isoformat(),
            "ready_at": self.ready_at.isoformat() if self.ready_at else None,
            "ready": self._is_ready,
        }


def register_lifecycle_events(
    app: FastAPI,
    logger: logging.Logger,
    readiness: AppReadiness,
) -> None:
    """Register startup and shutdown handlers."""

    @app.on_event("startup")
    async def startup_event() -> None:
        # DEBUG: "🎉 Upswitch Valuation Engine API startup complete!" + the
        # Uvicorn ready line at the end is the canonical boot signal.
        # Every process start receives a new boot_id. Counting this explicit
        # status event distinguishes engine restarts from rejected or never-
        # dispatched valuation requests in cross-service telemetry.
        logger.info(
            "valuation_iq_process_status",
            extra={
                "status": "restarted",
                "boot_id": readiness.boot_id,
                "started_at": readiness.started_at.isoformat(),
            },
        )
        logger.info(
            "valuation_iq_starting",
            extra={
                "boot_id": readiness.boot_id,
                "started_at": readiness.started_at.isoformat(),
            },
        )

        # Load heavy routes before other init. This keeps weasyprint env setup
        # ahead of imports and keeps the route table stable before readiness.
        await load_heavy_routes(app, logger)

        log_jwt_configuration(logger)
        await initialize_redis_pool(logger)
        validate_database_or_stateless_cache(logger)

        logger.info(
            "✅ ValuationIQ started as stateless calculation engine (The Muscle)"
        )

        await warm_country_data_cache(logger)
        warm_academic_metadata(logger)

        readiness.mark_ready()
        # DEBUG: the next "🎉 ... startup complete!" line is the canonical INFO ready signal.
        logger.debug("✅ App marked ready after full startup completion")
        logger.info("valuation_iq_ready", extra=readiness.snapshot())

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        logger.info("valuation_iq_stopping", extra=readiness.snapshot())
        readiness.mark_not_ready()

        try:
            from src.database.redis_client import shutdown_redis

            await shutdown_redis()
            logger.info("✅ Redis connection pool closed")
        except Exception as exc:
            logger.warning(f"⚠️ Redis shutdown: {str(exc)}")

        logger.info("👋 ValuationIQ shutdown complete!")
