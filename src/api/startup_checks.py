import logging
import os

from src.database.connection import is_stateless_mode
from src.utils.exceptions import DataValidationError


def log_jwt_configuration(logger: logging.Logger) -> None:
    """Log startup JWT configuration without leaking secret values."""
    jwt_secret = os.getenv("JWT_SECRET", "")
    jwt_secret_key = os.getenv("JWT_SECRET_KEY", "")
    supabase_jwt = os.getenv("SUPABASE_JWT_SECRET", "")

    # Keep the presence/absence audit visible without logging secret values.
    logger.info(
        "🔐 JWT Configuration Check",
        extra={
            "jwt_secret_set": bool(jwt_secret),
            "jwt_secret_key_set": bool(jwt_secret_key),
            "supabase_jwt_set": bool(supabase_jwt),
            "auth_will_use": (
                "JWT_SECRET" if jwt_secret else ("JWT_SECRET_KEY" if jwt_secret_key else "NONE")
            ),
        },
    )

    if not jwt_secret:
        logger.error("❌ JWT_SECRET not set - authentication will fail!")
    else:
        debug = getattr(logger, "debug", logger.info)
        debug("✅ JWT_SECRET configured for authentication")


async def initialize_redis_pool(logger: logging.Logger) -> None:
    """Initialize Redis when available; tolerate stateless-mode fallback."""
    try:
        from src.database.redis_client import initialize_redis

        await initialize_redis()
        logger.info("✅ Redis connection pool initialized")
    except RuntimeError as exc:
        if "stateless mode" in str(exc).lower():
            logger.info(
                "ℹ️ Redis skipped - ValuationIQ running in stateless mode (session state managed by Titan)"
            )
            return
        raise
    except DataValidationError as exc:
        logger.warning("⚠️ Redis initialization failed - using in-memory fallback: %s", exc)


def validate_database_or_stateless_cache(logger: logging.Logger) -> None:
    """Validate stateful database connections or the stateless business-type cache."""
    try:
        if is_stateless_mode():
            validate_synced_business_types_cache(logger)
            return

        validate_stateful_database_connections(logger)
    except Exception as exc:
        logger.warning("⚠️ Database connection check failed - continuing without database: %s", exc)


def validate_synced_business_types_cache(logger: logging.Logger) -> None:
    """Check the Titan-synced business-type cache used in stateless mode."""
    logger.info("ℹ️ Database checks skipped - ValuationIQ running in stateless mode")
    try:
        from src.database.business_types_repository import get_synced_business_types_diagnostics

        cache_diagnostics: dict[str, object] = get_synced_business_types_diagnostics()
        count = cache_diagnostics.get("count", 0)
        if cache_diagnostics.get("loaded") and isinstance(count, int) and count > 0:
            logger.debug("✅ Synced business types cache validated", extra=cache_diagnostics)
            return

        logger.error(
            "❌ Synced business types cache unavailable or empty - startup is degraded",
            extra=cache_diagnostics,
        )
    except Exception as cache_error:
        logger.error(
            "❌ Failed to validate synced business types cache at startup",
            extra={"error_type": type(cache_error).__name__, "error": str(cache_error)},
        )


def validate_stateful_database_connections(logger: logging.Logger) -> None:
    """Check primary and business-type database connectivity for stateful deployments."""
    try:
        from src.database.connection import check_business_types_db_connection, check_db_connection

        if check_db_connection():
            logger.info("✅ Database connection established")
        else:
            logger.warning("⚠️ Database connection check failed - continuing without database")

        if check_business_types_db_connection():
            logger.info("✅ Business types database connection established")
            return

        logger.warning("⚠️ Business types database connection check failed")
    except DataValidationError as exc:
        logger.warning("⚠️ Database connection failed - continuing without database: %s", exc)


async def warm_country_data_cache(logger: logging.Logger) -> None:
    """
    Warm the country-data cache from Delphi.

    Failures are logged and do not raise; the engine continues with the static
    bootstrap dict in dcf_data_adapter.py.
    """
    try:
        from src.services.country_data_service import get_country_data_service

        loaded = await get_country_data_service().refresh()
        logger.debug("✅ CountryDataService warmed at startup", extra={"countries_loaded": loaded})
    except Exception as exc:  # pragma: no cover - defensive startup guard
        logger.warning(
            "⚠️ CountryDataService startup refresh failed (using bootstrap fallback): %s",
            exc,
        )


def warm_academic_metadata(logger: logging.Logger) -> None:
    """
    Eager-init the academic metadata singletons at startup so the first
    /calculate request doesn't pay the YAML-parsing latency.

    Without this, both ``AcademicSourceRegistry`` (36 entries) and
    ``CalculationMetadataRegistry`` (16 entries) lazy-load inside the first
    valuation request — adding ~10ms and producing two "Loaded N entries"
    INFO logs in the middle of the calculation flow.

    Failures are logged and do not raise; the engine continues without
    academic provenance, which gracefully degrades to skipped validations.
    """
    try:
        from src.services.academic.academic_metadata_service import (
            get_academic_metadata_service,
        )

        service = get_academic_metadata_service()
        summary = service.get_metadata_summary()
        logger.info(
            "✅ Academic metadata warmed at startup",
            extra={
                "sources": summary.get("total_sources"),
                "calculations": summary.get("total_calculations"),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive startup guard
        logger.warning(
            "⚠️ Academic metadata startup warmup failed (will lazy-load on first request): %s",
            exc,
        )
