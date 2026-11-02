from src.utils.exceptions import DataValidationError, DatabaseError

"""
Database connection and session management

Handles SQLAlchemy engine creation, session management, and connection pooling.

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) is a stateless calculation engine.
When STATELESS_MODE=true, all database connections are disabled.
Data should come from Titan (The Brain) via payload.
"""

from functools import wraps
from typing import AsyncIterator, Generator, Optional, Any, Callable, TypeVar
from src.utils.logging import get_logger, log_calculation_step
from src.utils.logging_context import get_current_context
from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import declarative_base, Session, sessionmaker
from sqlalchemy.pool import QueuePool
from datetime import datetime
import os

from src.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


# =============================================================================
# STATELESS MODE SUPPORT
# =============================================================================


class StatelessModeError(RuntimeError):
    """Raised when database access is attempted in stateless mode."""

    pass


def is_stateless_mode() -> bool:
    """
    Check if ValuationIQ is running in stateless mode.

    In stateless mode:
    - All database connections are disabled
    - Data must come from Titan via request payload
    - Returns True if STATELESS_MODE=true env var is set or typed settings enable it
    """
    return os.getenv("STATELESS_MODE", "").lower() == "true" or settings.stateless_mode


T = TypeVar("T")


def require_stateful(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator that blocks function execution in stateless mode.

    Use this to wrap any function that requires database access.
    Raises StatelessModeError if called when STATELESS_MODE=true.

    Example:
        @require_stateful
        def get_valuation_from_db(valuation_id: str) -> Valuation:
            return db.query(Valuation).get(valuation_id)
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        if is_stateless_mode():
            raise StatelessModeError(
                f"{func.__name__} requires database access, but STATELESS_MODE=true. "
                f"Data should come from Titan via request payload."
            )
        return func(*args, **kwargs)

    return wrapper


# Lazy engine creation to avoid import-time failures
_engine = None
_SessionLocal = None
_stateless_mode_logged = (
    False  # Log STATELESS_MODE only once per process to avoid health-check spam
)


def _get_engine() -> Optional[Engine]:
    """
    Lazy engine creation.

    Returns None if:
    - STATELESS_MODE=true (Brain & Muscle architecture)
    - DATABASE_URL is not configured
    - database_optional is True and require_external_data is True
    - Database connection fails
    """
    global _engine, _stateless_mode_logged
    if _engine is None:
        # BRAIN & MUSCLE: Check stateless mode first
        if is_stateless_mode():
            if not _stateless_mode_logged:
                logger.info("🔒 STATELESS_MODE=true - database connections disabled")
                _stateless_mode_logged = True
            return None

        # Check if database is optional (ValuationIQ in stateless mode)
        if settings.require_external_data and settings.database_optional:
            logger.info("Database is optional - running in stateless mode with Titan data")
            return None

        # Check if DATABASE_URL is configured
        if not settings.database_url or settings.database_url == "":
            logger.info("No DATABASE_URL configured - running in stateless mode")
            return None

        try:
            _engine = create_engine(
                settings.database_url,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,  # Verify connections before using
                echo=settings.debug,  # Log SQL queries in debug mode
            )
        except Exception as e:
            logger.warning(f"Failed to create database engine: {e}")
            # Return None to allow app to continue without database
            _engine = None
    return _engine


def _get_session_local() -> Optional[sessionmaker]:
    """Lazy session factory creation."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = _get_engine()
        if engine is not None:
            _SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=engine,
            )
    return _SessionLocal


# For backward compatibility, try to create engine at import time
# but handle errors gracefully
try:
    engine = _get_engine()
    SessionLocal = _get_session_local()
except DatabaseError as e:
    logger.warning(f"Database connection not available at import time: {e}")
    engine = None
    SessionLocal = None

# Base class for all models
Base = declarative_base()

# Business types database connection (separate database)
# Use BUSINESS_TYPES_DATABASE_URL if provided, otherwise fall back to main database
_business_types_engine = None
_BusinessTypesSessionLocal = None
_business_types_stateless_logged = False


def _get_business_types_engine() -> Optional[Engine]:
    """
    Lazy business types engine creation.

    Returns None if:
    - STATELESS_MODE=true (Brain & Muscle architecture)
    - BUSINESS_TYPES_DATABASE_URL is not configured
    - require_external_data is True (data comes from Titan)
    - Database connection fails
    """
    global _business_types_engine, _business_types_stateless_logged
    if _business_types_engine is None:
        # BRAIN & MUSCLE: Check stateless mode first
        if is_stateless_mode():
            if not _business_types_stateless_logged:
                # DEBUG: dup of the main "🔒 STATELESS_MODE=true - database
                # connections disabled" boot banner emitted by the primary
                # DB connection guard.
                logger.debug("🔒 STATELESS_MODE=true - business types database connections disabled")
                _business_types_stateless_logged = True
            return None

        # Check if external data mode is enabled (business types come from Titan)
        if settings.require_external_data:
            logger.info("External data mode enabled - business types come from Titan API")
            return None

        # Get the database URL
        business_types_url = settings.business_types_database_url or settings.database_url

        # Check if URL is configured
        if not business_types_url or business_types_url == "":
            logger.info("No business types database URL configured")
            return None

        try:
            _business_types_engine = create_engine(
                business_types_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                echo=settings.debug,
                connect_args=(
                    {
                        "connect_timeout": 10,  # 10 second connection timeout
                        "options": "-c statement_timeout=5000",  # 5 second query timeout (in milliseconds)
                    }
                    if "postgresql" in business_types_url
                    else {}
                ),
            )
        except Exception as e:
            logger.warning(f"Failed to create business types database engine: {e}")
            _business_types_engine = None
    return _business_types_engine


def _get_business_types_session_local() -> Optional[sessionmaker]:
    """Lazy business types session factory creation."""
    global _BusinessTypesSessionLocal
    if _BusinessTypesSessionLocal is None:
        engine = _get_business_types_engine()
        if engine is not None:
            _BusinessTypesSessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=engine,
            )
    return _BusinessTypesSessionLocal


# For backward compatibility, try to create engines at import time
# but handle errors gracefully
try:
    business_types_engine = _get_business_types_engine()
    BusinessTypesSessionLocal = _get_business_types_session_local()
except DatabaseError as e:
    logger.warning(f"Business types database connection not available at import time: {e}")
    business_types_engine = None
    BusinessTypesSessionLocal = None


# Event listeners for connection management
# Only register if engine is available
if engine is not None:

    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_conn: Any, connection_record: Any) -> None:
        """Log database connections with enhanced logging"""
        # Get current logging context
        logging_context = get_current_context()
        session_id = (
            getattr(logging_context, "current_session_id", None) if logging_context else None
        )

        # Log database connection
        log_calculation_step(
            "database_connection_established",
            inputs={"connection_id": id(dbapi_conn)},
            outputs={"connection_time": datetime.now().isoformat()},
            formula="DB_Connection = Create_Connection + Log_Event + Track_Performance",
        )

        logger.info(
            "Database connection established",
            session_id=session_id,
            connection_id=id(dbapi_conn),
            timestamp=datetime.now().isoformat(),
        )

    @event.listens_for(engine, "close")
    def receive_close(dbapi_conn: Any, connection_record: Any) -> None:
        """Log database disconnections with enhanced logging"""
        # Get current logging context
        logging_context = get_current_context()
        session_id = (
            getattr(logging_context, "current_session_id", None) if logging_context else None
        )

        # Log database disconnection
        log_calculation_step(
            "database_connection_closed",
            inputs={"connection_id": id(dbapi_conn)},
            outputs={"disconnection_time": datetime.now().isoformat()},
            formula="DB_Disconnection = Close_Connection + Log_Event + Track_Performance",
        )

        logger.info(
            "Database connection closed",
            session_id=session_id,
            connection_id=id(dbapi_conn),
            timestamp=datetime.now().isoformat(),
        )


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection for database sessions

    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()

    Yields:
        Session: SQLAlchemy database session

    Raises:
        StatelessModeError: If STATELESS_MODE=true
        RuntimeError: If database connection not available
    """
    # BRAIN & MUSCLE: Block in stateless mode
    if is_stateless_mode():
        raise StatelessModeError(
            "Database access disabled in STATELESS_MODE=true. "
            "Data should come from Titan via request payload."
        )

    if SessionLocal is None:
        raise RuntimeError("Database connection not available")
    db = SessionLocal()
    try:
        yield db
    except DatabaseError as e:
        logger.error("Database session error", extra={"error": str(e)})
        db.rollback()
        raise
    finally:
        db.close()


def get_business_types_db() -> Generator[Session, None, None]:
    """
    Dependency injection for business types database sessions

    Usage:
        @app.get("/industries")
        def get_industries(db: Session = Depends(get_business_types_db)):
            return db.query(BusinessType).all()

    Yields:
        Session: SQLAlchemy database session for business types

    Raises:
        StatelessModeError: If STATELESS_MODE=true
        RuntimeError: If database connection not available
    """
    # BRAIN & MUSCLE: Block in stateless mode
    if is_stateless_mode():
        raise StatelessModeError(
            "Business types database access disabled in STATELESS_MODE=true. "
            "Data should come from Titan via request payload."
        )

    if BusinessTypesSessionLocal is None:
        raise RuntimeError("Business types database connection not available")
    db = BusinessTypesSessionLocal()
    try:
        yield db
    except DatabaseError as e:
        logger.error("Business types database session error", extra={"error": str(e)})
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database tables

    Creates all tables defined in models if they don't exist.
    For production, use Alembic migrations instead.
    """
    engine = _get_engine()
    if engine is None:
        raise RuntimeError("Database connection not available")
    logger.info("Initializing database tables")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def check_db_connection() -> bool:
    """
    Check if database connection is healthy

    Returns:
        bool: True if connection is healthy, False otherwise
    """
    if is_stateless_mode():
        return False  # No DB in stateless mode - skip without attempting connection
    try:
        engine = _get_engine()
        if engine is None:
            return False
        with engine.connect() as conn:
            from sqlalchemy import text

            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(
            "Database connection check failed",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        return False


def check_business_types_db_connection() -> bool:
    """
    Check if business types database connection is healthy

    Returns:
        bool: True if connection is healthy, False otherwise
    """
    if is_stateless_mode():
        return False  # No DB in stateless mode - skip without attempting connection
    try:
        engine = _get_business_types_engine()
        if engine is None:
            return False
        with engine.connect() as conn:
            from sqlalchemy import text

            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(
            "Business types database connection check failed",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        return False


# Async session support for testing
try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from contextlib import asynccontextmanager

    _async_engine = None
    _AsyncSessionLocal = None

    def _get_async_engine() -> Any:
        """Lazy async engine creation."""
        global _async_engine
        if _async_engine is None and settings.database_url:
            try:
                # Convert postgresql:// to postgresql+asyncpg://
                async_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
                _async_engine = create_async_engine(
                    async_url,
                    pool_pre_ping=True,
                    echo=settings.debug,
                )
            except Exception as e:
                logger.warning(f"Failed to create async database engine: {e}")
                _async_engine = None
        return _async_engine

    @asynccontextmanager
    async def get_async_session() -> AsyncIterator[AsyncSession]:
        """
        Async context manager for database sessions (for testing).

        Usage:
            async with get_async_session() as db:
                result = await db.execute(...)
        """
        engine = _get_async_engine()
        if engine is None:
            raise RuntimeError("Async database connection not available")

        async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

except ImportError:
    # asyncpg not available - provide a stub
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def get_async_session() -> AsyncIterator[Any]:
        """Stub for when asyncpg is not installed."""
        should_yield = False
        if should_yield:
            yield None
        raise RuntimeError(
            "Async database support requires asyncpg. Install with: pip install asyncpg"
        )
