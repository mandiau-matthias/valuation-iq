from src.utils.exceptions import DatabaseError

"""
Data Repository Layer

Provides data access methods for valuation operations.
Abstracts database operations from business logic.

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) is a stateless calculation engine.
When STATELESS_MODE=true, repository methods will raise StatelessModeError.
Data should come from Titan (The Brain) via payload.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from src.database.connection import StatelessModeError, is_stateless_mode, require_stateful
from src.database.models import AuditLog, Valuation, ValuationCache, ValuationResult
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StatefulRepository:
    """Base repository that enforces the ValuationIQ stateless boundary."""

    stateless_error_message = "Repository cannot be initialized in STATELESS_MODE=true."

    def __init__(self, db: Session) -> None:
        if is_stateless_mode():
            raise StatelessModeError(self.stateless_error_message)
        self.db = db


class ValuationRepository(StatefulRepository):
    """
    Repository for Valuation and ValuationResult operations

    BRAIN & MUSCLE ARCHITECTURE:
    All methods are guarded by stateless mode check.
    When STATELESS_MODE=true, methods will raise StatelessModeError.
    """

    stateless_error_message = (
        "ValuationRepository cannot be initialized in STATELESS_MODE=true. "
        "Data should come from Titan via request payload."
    )

    @require_stateful
    def create_valuation(self, valuation_data: Dict[str, Any]) -> Valuation:
        """
        Create a new valuation request

        Args:
            valuation_data: Dictionary containing valuation input data

        Returns:
            Valuation: Created valuation object
        """
        try:
            valuation = Valuation(**valuation_data)
            self.db.add(valuation)
            self.db.commit()
            self.db.refresh(valuation)

            logger.info(
                "Valuation created", valuation_id=str(valuation.id), company=valuation.company_name
            )
            return valuation

        except DatabaseError as e:
            logger.error("Failed to create valuation", error=str(e))
            self.db.rollback()
            raise

    @require_stateful
    def get_valuation(self, valuation_id: UUID) -> Optional[Valuation]:
        """
        Get valuation by ID

        Args:
            valuation_id: UUID of the valuation

        Returns:
            Valuation or None if not found
        """
        return self.db.query(Valuation).filter(Valuation.id == valuation_id).first()

    @require_stateful
    def get_valuations_by_user(
        self, user_id: str, limit: int = 10, offset: int = 0
    ) -> List[Valuation]:
        """
        Get all valuations for a user

        Args:
            user_id: User identifier
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of valuations
        """
        return (
            self.db.query(Valuation)
            .filter(Valuation.user_id == user_id)
            .order_by(desc(Valuation.created_at))
            .limit(limit)
            .offset(offset)
            .all()
        )

    @require_stateful
    def get_valuations_by_business(self, business_id: str) -> List[Valuation]:
        """
        Get all valuations for a business

        Args:
            business_id: Business identifier

        Returns:
            List of valuations
        """
        return (
            self.db.query(Valuation)
            .filter(Valuation.business_id == business_id)
            .order_by(desc(Valuation.created_at))
            .all()
        )

    @require_stateful
    def create_valuation_result(
        self, valuation_id: UUID, result_data: Dict[str, Any]
    ) -> ValuationResult:
        """
        Create a new valuation result

        Args:
            valuation_id: UUID of the parent valuation
            result_data: Dictionary containing result data

        Returns:
            ValuationResult: Created result object
        """
        try:
            result_data["valuation_id"] = valuation_id
            result = ValuationResult(**result_data)
            self.db.add(result)
            self.db.commit()
            self.db.refresh(result)

            logger.info(
                "Valuation result created",
                result_id=str(result.id),
                valuation_id=str(valuation_id),
                equity_value=result.equity_value_mid,
            )
            return result

        except DatabaseError as e:
            logger.error("Failed to create valuation result", error=str(e))
            self.db.rollback()
            raise

    @require_stateful
    def get_latest_result(self, valuation_id: UUID) -> Optional[ValuationResult]:
        """
        Get the most recent result for a valuation

        Args:
            valuation_id: UUID of the valuation

        Returns:
            ValuationResult or None
        """
        return (
            self.db.query(ValuationResult)
            .filter(ValuationResult.valuation_id == valuation_id)
            .order_by(desc(ValuationResult.created_at))
            .first()
        )

    @require_stateful
    def get_similar_valuations(
        self, country_code: str, industry: str, revenue_range: tuple, limit: int = 5
    ) -> List[Valuation]:
        """
        Find similar valuations for benchmarking

        Args:
            country_code: Country code
            industry: Industry sector
            revenue_range: (min_revenue, max_revenue)
            limit: Maximum number of results

        Returns:
            List of similar valuations
        """
        min_revenue, max_revenue = revenue_range

        return (
            self.db.query(Valuation)
            .filter(
                and_(
                    Valuation.country_code == country_code,
                    Valuation.industry == industry,
                    Valuation.revenue >= min_revenue,
                    Valuation.revenue <= max_revenue,
                )
            )
            .order_by(desc(Valuation.created_at))
            .limit(limit)
            .all()
        )


class CacheRepository(StatefulRepository):
    """
    Repository for caching external API data

    BRAIN & MUSCLE ARCHITECTURE:
    All methods are guarded by stateless mode check.
    """

    stateless_error_message = "CacheRepository cannot be initialized in STATELESS_MODE=true."

    @require_stateful
    def get_cached_data(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached data if not expired

        Args:
            cache_key: Unique cache identifier

        Returns:
            Cached data or None if not found/expired
        """
        cache_entry = (
            self.db.query(ValuationCache)
            .filter(
                and_(
                    ValuationCache.cache_key == cache_key,
                    ValuationCache.expires_at > datetime.utcnow(),
                )
            )
            .first()
        )

        if cache_entry:
            # Update hit count
            cache_entry.hit_count += 1
            self.db.commit()

            logger.info("Cache hit", cache_key=cache_key, hits=cache_entry.hit_count)
            return cache_entry.data

            logger.info("Cache miss", cache_key=cache_key)
        return None

    @require_stateful
    def set_cached_data(
        self,
        cache_key: str,
        data: Dict[str, Any],
        source: str,
        data_type: str,
        ttl_hours: int = 24,
        country_code: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> ValuationCache:
        """
        Store data in cache

        Args:
            cache_key: Unique cache identifier
            data: Data to cache
            source: Data source (oecd, ecb, fmp)
            data_type: Type of data (gdp, inflation, multiples)
            ttl_hours: Time to live in hours
            country_code: Optional country code
            industry: Optional industry

        Returns:
            ValuationCache: Created cache entry
        """
        try:
            # Delete existing entry if it exists
            self.db.query(ValuationCache).filter(ValuationCache.cache_key == cache_key).delete()

            expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

            cache_entry = ValuationCache(
                cache_key=cache_key,
                source=source,
                data_type=data_type,
                data=data,
                country_code=country_code,
                industry=industry,
                expires_at=expires_at,
            )

            self.db.add(cache_entry)
            self.db.commit()
            self.db.refresh(cache_entry)

            logger.info("Data cached", cache_key=cache_key, source=source, expires_at=expires_at)
            return cache_entry

        except DatabaseError as e:
            logger.error("Failed to cache data", error=str(e))
            self.db.rollback()
            raise

    @require_stateful
    def clear_expired_cache(self) -> int:
        """
        Remove all expired cache entries

        Returns:
            int: Number of entries deleted
        """
        try:
            deleted = (
                self.db.query(ValuationCache)
                .filter(ValuationCache.expires_at < datetime.utcnow())
                .delete()
            )
            self.db.commit()

            logger.info("Expired cache cleared", deleted_count=deleted)
            return deleted

        except DatabaseError as e:
            logger.error("Failed to clear cache", error=str(e))
            self.db.rollback()
            raise


class AuditRepository(StatefulRepository):
    """
    Repository for audit logging

    BRAIN & MUSCLE ARCHITECTURE:
    All methods are guarded by stateless mode check.
    Audit logging should be handled by Titan in stateless mode.
    """

    stateless_error_message = (
        "AuditRepository cannot be initialized in STATELESS_MODE=true. "
        "Audit logging should be handled by Titan."
    )

    @require_stateful
    def log_event(
        self,
        event_type: str,
        event_category: str,
        user_id: Optional[str] = None,
        request_ip: Optional[str] = None,
        endpoint: Optional[str] = None,
        http_method: Optional[str] = None,
        status_code: Optional[int] = None,
        request_data: Optional[Dict] = None,
        response_data: Optional[Dict] = None,
        error_details: Optional[Dict] = None,
        execution_time_ms: Optional[int] = None,
    ) -> AuditLog:
        """
        Create an audit log entry

        Args:
            event_type: Type of event (api_request, error, calculation)
            event_category: Category (valuation, health, admin)
            ... other optional parameters

        Returns:
            AuditLog: Created audit entry
        """
        try:
            audit_entry = AuditLog(
                event_type=event_type,
                event_category=event_category,
                user_id=user_id,
                request_ip=request_ip,
                endpoint=endpoint,
                http_method=http_method,
                status_code=status_code,
                request_data=request_data,
                response_data=response_data,
                error_details=error_details,
                execution_time_ms=execution_time_ms,
            )

            self.db.add(audit_entry)
            self.db.commit()

            return audit_entry

        except DatabaseError as e:
            logger.error("Failed to create audit log", error=str(e))
            self.db.rollback()
            # Don't raise - audit failures shouldn't break the application
            return None

    @require_stateful
    def get_recent_events(
        self, event_type: Optional[str] = None, limit: int = 100
    ) -> List[AuditLog]:
        """
        Get recent audit events

        Args:
            event_type: Optional filter by event type
            limit: Maximum number of results

        Returns:
            List of audit log entries
        """
        query = self.db.query(AuditLog)

        if event_type:
            query = query.filter(AuditLog.event_type == event_type)

        return query.order_by(desc(AuditLog.created_at)).limit(limit).all()
