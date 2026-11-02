from collections.abc import Mapping

from src.utils.exceptions import DataValidationError

"""
ValuationLogger: Guaranteed Logging with Fallback

CTO-LEVEL ROBUSTNESS:
- Guarantees log delivery even if structlog fails
- Fallback to print() ensures logs always appear
- Startup verification ensures logging is working
- Correlation IDs for end-to-end tracing
- Structured + plain text for compatibility

USAGE:
    from src.utils.valuation_logger import ValuationLogger

    logger = ValuationLogger(__name__)
    logger.info("Critical message", extra={'key': 'value'})
    # printf-style: pass format args before keyword-only extra/exc_info (same as stdlib logging):
    # logger.warning("msg %s", err, exc_info=True)
"""

import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

# Import correlation context for auto-injection
try:
    from src.utils.correlation_context import get_correlation_id

    CORRELATION_CONTEXT_AVAILABLE = True
except ImportError:
    CORRELATION_CONTEXT_AVAILABLE = False
    get_correlation_id = None

# Try to import the standard logger, but don't fail if it's not available
try:
    from src.utils.logging import get_logger as get_standard_logger

    STANDARD_LOGGER_AVAILABLE = True
except ImportError:
    STANDARD_LOGGER_AVAILABLE = False
    get_standard_logger = None

# Global flag to track if we've verified logging works
_logging_verified = False


def _normalize_extra(extra: Optional[Any]) -> Optional[Dict[str, Any]]:
    """Ensure `extra` is a dict for structlog/stdlib; never treat exceptions/objects as mappings."""
    if extra is None:
        return None
    if isinstance(extra, Mapping):
        return dict(extra)
    return {"non_dict_extra": repr(extra)}


def _format_message(message: str, args: Tuple[Any, ...]) -> str:
    """Stdlib-style message % args; safe fallback if formatting fails."""
    if not args:
        return message
    try:
        return message % args
    except (TypeError, ValueError):
        return message + "".join(str(a) for a in args)


class ValuationLogger:
    """
    Guaranteed logging with fallback to print().

    This logger ensures that critical debug information is ALWAYS captured,
    even if the standard logging infrastructure fails.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._standard_logger = None
        self._use_fallback = False

        # Try to get standard logger
        if STANDARD_LOGGER_AVAILABLE:
            try:
                self._standard_logger = get_standard_logger(name)
                self._test_logger()
            except Exception as e:  # noqa: BLE001 - logger init must never raise
                # `except ValuationEngineError` previously here was dead code:
                # structlog/import failures raise plain Exception subclasses, not
                # the domain type — they were leaking up and crashing the caller.
                self._use_fallback = True
                self._fallback_print(
                    f"WARNING: Standard logger failed for {name}, using fallback: {e}",
                    level="WARNING",
                )
        else:
            self._use_fallback = True

    def _test_logger(self) -> None:
        """
        Verify the standard logger has the methods we need. Silent — does not emit
        a record (would otherwise show up at every ``ValuationLogger(__name__)``
        module-level instantiation, of which there are 41).
        """
        try:
            if not hasattr(self._standard_logger, "debug") and not hasattr(
                self._standard_logger, "info"
            ):
                self._use_fallback = True
        except Exception:  # noqa: BLE001 - never let probing crash construction
            self._use_fallback = True

    def _fallback_print(
        self, message: str, level: str = "INFO", extra: Optional[Dict[str, Any]] = None
    ):
        """
        Fallback logging using print() - GUARANTEED to work.

        This ensures logs always appear even if structlog/logging fails.
        """
        timestamp = datetime.now(timezone.utc).isoformat() + "Z"
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "logger": self.name,
            "message": message,
        }

        if extra:
            log_entry["extra"] = extra

        # Print as JSON for structured parsing, but also human-readable
        print(f"[{level}] {timestamp} [{self.name}] {message}", file=sys.stderr)
        if extra:
            print(f"  EXTRA: {json.dumps(extra, default=str)}", file=sys.stderr)

    def _log(self, level: str, message: str, extra: Optional[Any] = None, exc_info: bool = False):
        """
        Emit one log record via the standard logger; only fall back to ``print()`` if
        the standard logger genuinely fails.

        Previous design double-emitted any message containing "🔍" / "STEP" / "DB Lookup"
        (one stderr ``print()`` plus one structlog event), to guarantee delivery even if
        structlog was broken. With structlog stable, that doubled the log volume on
        ~219 call sites — including the orchestrator HTML-SERVICE-INIT path that fires on
        every request. Production stdout was littered with both shapes.

        Contract now: exactly one record per call when the standard logger works;
        a single fallback print otherwise. The fallback also catches the broad
        ``Exception`` (not just the domain ``ValuationEngineError``) — structlog can
        raise plain ``TypeError`` / ``RuntimeError``, which the prior ``except
        ValuationEngineError`` clause silently passed through.
        """
        extra_dict = _normalize_extra(extra)

        # Auto-inject correlation ID from context if available
        if CORRELATION_CONTEXT_AVAILABLE:
            try:
                correlation_id = get_correlation_id()
                if correlation_id:
                    if extra_dict is None:
                        extra_dict = {}
                    # Only add if not already present (allow manual override)
                    if "correlation_id" not in extra_dict:
                        extra_dict["correlation_id"] = correlation_id
            except Exception:  # noqa: BLE001 - logging must never raise
                pass

        if self._use_fallback or self._standard_logger is None:
            self._fallback_print(message, level, extra_dict)
            return

        log_method = getattr(self._standard_logger, level.lower(), None)
        if log_method is None:
            self._fallback_print(message, level, extra_dict)
            return

        try:
            if extra_dict:
                log_method(message, extra=extra_dict, exc_info=exc_info)
            else:
                log_method(message, exc_info=exc_info)
        except Exception:  # noqa: BLE001 - logging must never raise; fall back to stderr
            self._fallback_print(message, level, extra_dict)

    def info(
        self,
        message: str,
        *args: Any,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Log at INFO level with guaranteed delivery (supports message % args like stdlib)."""
        self._log("INFO", _format_message(message, args), extra, exc_info)

    def warning(
        self,
        message: str,
        *args: Any,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Log at WARNING level with guaranteed delivery (supports message % args like stdlib)."""
        self._log("WARNING", _format_message(message, args), extra, exc_info)

    def error(
        self,
        message: str,
        *args: Any,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Log at ERROR level with guaranteed delivery (supports message % args like stdlib)."""
        self._log("ERROR", _format_message(message, args), extra, exc_info)

    def debug(
        self,
        message: str,
        *args: Any,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Log at DEBUG level with guaranteed delivery (supports message % args like stdlib)."""
        self._log("DEBUG", _format_message(message, args), extra, exc_info)

    def critical(
        self,
        message: str,
        *args: Any,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """Log at CRITICAL level with guaranteed delivery (supports message % args like stdlib)."""
        self._log("CRITICAL", _format_message(message, args), extra, exc_info)


def verify_logging_at_startup():
    """
    Verify that logging is working at application startup.

    This should be called during application initialization to ensure
    logs will be captured throughout the application lifecycle.
    """
    global _logging_verified

    test_logger = ValuationLogger("startup_verification")
    # DEBUG: logging-verification scaffolding fires every boot; only matters
    # if INFO logging is broken (in which case we wouldn't see it anyway).
    test_logger.debug("✅ Logging verification: Standard logger test")
    test_logger.debug("🔍 Logging verification: Debug logger test (with emoji)")

    # Verify log level allows INFO
    try:
        from src.config import get_settings

        settings = get_settings()
        log_level = getattr(settings, "log_level", "info").upper()

        # Map string levels to numeric
        level_map = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}

        current_level = level_map.get(log_level, 20)
        info_level = 20

        if current_level > info_level:
            test_logger.warning(
                f"⚠️ Log level '{log_level}' may suppress INFO logs. Current level: {current_level}, INFO requires: {info_level}",
                extra={
                    "log_level": log_level,
                    "current_level": current_level,
                    "info_level": info_level,
                },
            )
        else:
            test_logger.info(
                f"✅ Log level '{log_level}' allows INFO logs",
                extra={"log_level": log_level, "current_level": current_level},
            )
    except DataValidationError as e:
        test_logger.warning(
            f"⚠️ Could not verify log level configuration: {e}", extra={"error": str(e)}
        )

    _logging_verified = True
    return True
