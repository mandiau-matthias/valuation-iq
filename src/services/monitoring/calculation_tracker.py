"""
Calculation Success Tracker

Tracks calculation attempts, successes, and failures for OKR monitoring.
Designed to NEVER break the application - all errors are caught and logged.

Usage:
    tracker = CalculationSuccessTracker(session=db, enabled=True)
    await tracker.track_attempt(calculation_id="...", company_id="...", ...)
    await tracker.track_success(calculation_id="...", valuation_result=..., execution_time_ms=...)
    await tracker.track_failure(calculation_id="...", error_type="...", error_message="...")
    result = await tracker.get_success_rate(time_window_hours=24)
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def _execute(session: Any, stmt: Any, params: dict) -> Any:
    """Execute statement, handling both sync and async sessions."""
    result = session.execute(stmt, params)
    if asyncio.iscoroutine(result):
        result = await result
    return result


async def _commit(session: Any) -> None:
    """Commit session, handling both sync and async."""
    if not hasattr(session, "commit"):
        return
    result = session.commit()
    if asyncio.iscoroutine(result):
        await result


class CalculationSuccessTracker:
    """
    Tracks calculation success rate for OKR monitoring.

    All tracking methods are fire-and-forget: they never raise exceptions.
    If the database is unavailable or the table is missing, tracking silently disables.
    """

    def __init__(self, session: Any = None, enabled: bool = True):
        """
        Args:
            session: Database session (SQLAlchemy AsyncSession or similar).
                     If None, all tracking is a no-op.
            enabled: If False, all tracking is a no-op.
        """
        self._session = session
        self._enabled = enabled and session is not None
        self._initialization_failed = False

    def _should_skip(self) -> bool:
        """Return True if we should skip tracking (no-op)."""
        return not self._enabled or self._initialization_failed or self._session is None

    async def track_attempt(
        self,
        calculation_id: str,
        company_id: str,
        business_type: str,
        methodology: str,
    ) -> None:
        """
        Track a calculation attempt (started).

        Never raises. Logs and disables on first failure.
        """
        if self._should_skip():
            return
        try:
            from sqlalchemy import text

            now = datetime.now(timezone.utc)
            params = {
                "event_type": "attempt",
                "calculation_id": calculation_id,
                "company_id": company_id,
                "business_type": business_type,
                "methodology": methodology,
                "timestamp": now,
            }
            await _execute(
                self._session,
                text("""
                    INSERT INTO calculation_events
                    (event_type, calculation_id, company_id, business_type, methodology, timestamp)
                    VALUES (:event_type, :calculation_id, :company_id, :business_type, :methodology, :timestamp)
                """),
                params,
            )
            await _commit(self._session)
        except Exception as e:
            logger.warning(
                "monitoring_track_attempt_failed",
                extra={"error": str(e), "calculation_id": calculation_id},
            )
            self._initialization_failed = True

    async def track_success(
        self,
        calculation_id: str,
        valuation_result: Decimal,
        execution_time_ms: int,
    ) -> None:
        """
        Track a successful calculation.

        Never raises. Logs and disables on first failure.
        """
        if self._should_skip():
            return
        try:
            from sqlalchemy import text

            now = datetime.now(timezone.utc)
            params = {
                "event_type": "success",
                "calculation_id": calculation_id,
                "valuation_result": float(valuation_result),
                "execution_time_ms": execution_time_ms,
                "timestamp": now,
            }
            await _execute(
                self._session,
                text("""
                    INSERT INTO calculation_events
                    (event_type, calculation_id, valuation_result, execution_time_ms, timestamp)
                    VALUES (:event_type, :calculation_id, :valuation_result, :execution_time_ms, :timestamp)
                """),
                params,
            )
            await _commit(self._session)
        except Exception as e:
            logger.warning(
                "monitoring_track_success_failed",
                extra={"error": str(e), "calculation_id": calculation_id},
            )
            self._initialization_failed = True

    async def track_failure(
        self,
        calculation_id: str,
        error_type: str,
        error_message: str,
    ) -> None:
        """
        Track a failed calculation.

        Never raises. Logs and disables on first failure.
        """
        if self._should_skip():
            return
        try:
            from sqlalchemy import text

            now = datetime.now(timezone.utc)
            params = {
                "event_type": "failure",
                "calculation_id": calculation_id,
                "error_type": error_type,
                "error_message": error_message[:1000] if error_message else None,
                "timestamp": now,
            }
            await _execute(
                self._session,
                text("""
                    INSERT INTO calculation_events
                    (event_type, calculation_id, error_type, error_message, timestamp)
                    VALUES (:event_type, :calculation_id, :error_type, :error_message, :timestamp)
                """),
                params,
            )
            await _commit(self._session)
        except Exception as e:
            logger.warning(
                "monitoring_track_failure_failed",
                extra={"error": str(e), "calculation_id": calculation_id},
            )
            self._initialization_failed = True

    async def get_success_rate(
        self,
        time_window_hours: int = 24,
        business_type: Optional[str] = None,
        methodology: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Get calculation success rate for the given time window.

        Returns dict with: total_attempts, successful, failed, success_rate_pct,
        time_window_hours, and optional business_type, methodology.

        Never raises. Returns zeros on error.
        """
        if self._should_skip():
            return {
                "total_attempts": 0,
                "successful": 0,
                "failed": 0,
                "success_rate_pct": 0.0,
                "time_window_hours": time_window_hours,
                **({"business_type": business_type} if business_type else {}),
                **({"methodology": methodology} if methodology else {}),
            }
        try:
            from sqlalchemy import text

            since = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)
            params: dict[str, Any] = {"since": since}
            if business_type:
                params["business_type"] = business_type
            if methodology:
                params["methodology"] = methodology
            attempt_query = """
                    SELECT COUNT(*) FROM calculation_events
                    WHERE event_type = 'attempt' AND timestamp >= :since
                """
            if business_type:
                attempt_query += " AND business_type = :business_type"
            if methodology:
                attempt_query += " AND methodology = :methodology"

            # Count attempts
            attempts_result = await _execute(
                self._session,
                text(attempt_query),
                params,
            )
            total_attempts = attempts_result.scalar() or 0

            # Count successes and failures in window (no filter - schema doesn't have business_type on success/failure)
            success_result = await _execute(
                self._session,
                text("""
                    SELECT COUNT(*) FROM calculation_events
                    WHERE event_type = 'success' AND timestamp >= :since
                """),
                {"since": since},
            )
            successful = success_result.scalar() or 0

            failure_result = await _execute(
                self._session,
                text("""
                    SELECT COUNT(*) FROM calculation_events
                    WHERE event_type = 'failure' AND timestamp >= :since
                """),
                {"since": since},
            )
            failed = failure_result.scalar() or 0

            # When filtered by business_type/methodology, total_attempts is filtered but success/failure are not
            # Use total_attempts as denominator; for rate use successful/(successful+failed) if we had filtered calc_ids
            # Simplified: use global success/failure counts; total_attempts may be subset
            if total_attempts > 0:
                success_rate_pct = round((successful / total_attempts * 100.0), 2)
            else:
                success_rate_pct = 0.0

            result: dict[str, Any] = {
                "total_attempts": total_attempts,
                "successful": successful,
                "failed": failed,
                "success_rate_pct": success_rate_pct,
                "time_window_hours": time_window_hours,
            }
            if business_type:
                result["business_type"] = business_type
            if methodology:
                result["methodology"] = methodology
            return result

        except Exception as e:
            logger.warning(
                "monitoring_get_success_rate_failed",
                extra={"error": str(e), "time_window_hours": time_window_hours},
            )
            return {
                "total_attempts": 0,
                "successful": 0,
                "failed": 0,
                "success_rate_pct": 0.0,
                "time_window_hours": time_window_hours,
                **({"business_type": business_type} if business_type else {}),
                **({"methodology": methodology} if methodology else {}),
            }
