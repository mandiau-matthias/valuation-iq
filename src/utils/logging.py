"""
Enhanced Logging Configuration

Sets up comprehensive structured logging using structlog with financial data formatting,
context management, and audit trail capabilities for the valuation engine.

ARCHITECTURE:
- Enhanced structlog configuration with custom processors
- Financial data formatters with precision control
- Context-aware logging with correlation IDs
- Audit trail logging for compliance
- Performance metrics integration
- Secure log storage with rotation

FEATURES:
- Calculation-specific log levels (CALCULATION, VALIDATION, AUDIT)
- Financial data formatters (with precision control)
"""

import gzip
import json
import logging
import os
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from logging import LogRecord
from pathlib import Path
from typing import Optional, Union

import structlog
from structlog.processors import JSONRenderer, TimeStamper, add_log_level

from src.config import get_settings
from src.config.public_adaptive_local_migration import public_adaptive_stdout_log_level
from src.utils.calculation_logging import (
    AUDIT_LEVEL,
    CALCULATION_LEVEL,
    VALIDATION_LEVEL,
    CalculationLogger,
    LoggerBackend,
    _percent_format_message,
)
from src.utils.log_formatters import create_formatters
from src.utils.logging_context import get_current_context

# Decimal formatting is handled by log_formatters.py which uses lazy imports
# to avoid circular dependencies. This module works directly with Decimal types.

settings = get_settings()


LogEvent = dict[str, object]
LogPayload = dict[str, object]


def _drop_empty_event(logger: object, method_name: str, event_dict: LogEvent) -> LogEvent:
    """
    Drop log records whose event/message payload is empty or whitespace-only.

    Apr 2026 incident (Three Towers Capital telemetry review): Railway stdout
    was littered with empty ``[inf]`` / ``[wrn]`` lines — hot-loop call sites
    were emitting structlog events with no rendered text, producing blank
    platform-log entries that buried real signal. The empty-message guards
    on ``CalculationLogger.warning/error`` already exist; this processor is
    the structlog-side backstop so anything reaching the renderer has a
    non-empty event field.
    """
    event = event_dict.get("event", "")
    if event is None:
        raise structlog.DropEvent
    if isinstance(event, str) and not event.strip():
        raise structlog.DropEvent
    return event_dict


def _rename_event_to_message(logger: object, method_name: str, event_dict: LogEvent) -> LogEvent:
    """
    Rename structlog's ``event`` key to ``message`` for JSON output.

    Cloud Run / Railway / Datadog / Cloud Logging all auto-extract the
    ``message`` field from structured logs to populate the rendered log
    line. structlog's default key is ``event``, which these platforms
    treat as opaque metadata — leaving the visible log entry blank.

    JSON branch only (ConsoleRenderer in dev still expects ``event``).
    """
    event = event_dict.pop("event", None)
    if event is not None:
        # Coerce non-strings safely so JSON serialization can't blow up
        event_dict["message"] = event if isinstance(event, str) else str(event)
    return event_dict


class FinancialDataProcessor:
    """Custom processor for financial data formatting"""

    def __init__(self, precision: int = 2, privacy_mode: bool = False) -> None:
        """
        Initialize financial data processor.

        Args:
            precision: Decimal precision for financial data
            privacy_mode: Enable privacy mode for sensitive data
        """
        self.formatters = create_formatters(precision=precision, privacy_mode=privacy_mode)

    def __call__(self, logger: object, method_name: str, event_dict: LogEvent) -> LogEvent:
        """Process log event with financial data formatting"""
        try:
            # Add context from logging context
            context = get_current_context()
            if context:
                context_data = context.get_context()
                if context_data:
                    event_dict.update(context_data)
        except Exception:
            # Silently continue if context fails - don't break logging
            pass

        try:
            # Format financial data if present
            if "financial_data" in event_dict:
                event_dict["financial_data"] = self.formatters["financial"].format_financial_data(
                    event_dict["financial_data"]
                )
        except Exception:
            # Continue without financial formatting if it fails
            pass

        try:
            # Format calculation steps if present
            if "calculation_step" in event_dict:
                event_dict["calculation_step"] = self.formatters[
                    "calculation"
                ].format_calculation_step(**event_dict["calculation_step"])
        except Exception:
            # Continue without calculation formatting if it fails
            pass

        try:
            # Format performance metrics if present
            if "performance_metric" in event_dict:
                event_dict["performance_metric"] = self.formatters[
                    "performance"
                ].format_performance_metric(**event_dict["performance_metric"])
        except Exception:
            # Continue without performance formatting if it fails
            pass

        return event_dict


class AuditTrailProcessor:
    """Custom processor for audit trail logging"""

    def __call__(self, logger: object, method_name: str, event_dict: LogEvent) -> LogEvent:
        """Process log event for audit trail"""
        try:
            # Add audit metadata
            event_dict["audit_timestamp"] = datetime.now(timezone.utc).isoformat()
            event_dict["audit_level"] = "compliance"
        except Exception:
            # Continue without audit metadata if it fails
            pass

        try:
            # Add context for audit trail
            context = get_current_context()
            if context:
                request_id = context.get_request_id()
                if request_id:
                    event_dict["request_id"] = request_id
                user_id = context.get_user_id()
                if user_id:
                    event_dict["user_id"] = user_id
                correlation_id = context.get_correlation_id()
                if correlation_id:
                    event_dict["correlation_id"] = correlation_id
        except Exception:
            # Continue without context if it fails
            pass

        return event_dict


class SecureFileHandler(logging.Handler):
    """Secure file handler with rotation and compression"""

    def __init__(
        self,
        filename: Union[str, Path],
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        encoding: str = "utf-8",
    ) -> None:
        super().__init__()
        self.filename = filename
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.encoding = encoding
        self.current_size = 0

        # Ensure log directory exists
        Path(filename).parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record: LogRecord) -> None:
        """Emit a log record"""
        try:
            # Check if rotation is needed
            if self.current_size > self.max_bytes:
                self.rotate()

            # Write to file
            with open(self.filename, "a", encoding=self.encoding) as f:
                f.write(self.format(record) + "\n")
                self.current_size = f.tell()

        except Exception:
            self.handleError(record)

    def rotate(self) -> None:
        """Rotate log files"""
        if os.path.exists(self.filename):
            # Compress current file
            with open(self.filename, "rb") as f_in:
                with gzip.open(f"{self.filename}.gz", "wb") as f_out:
                    f_out.writelines(f_in)

            # Remove original file
            os.remove(self.filename)

            # Rotate old compressed files
            for i in range(self.backup_count - 1, 0, -1):
                old_file = f"{self.filename}.{i}.gz"
                new_file = f"{self.filename}.{i + 1}.gz"
                if os.path.exists(old_file):
                    if i == self.backup_count - 1:
                        os.remove(old_file)
                    else:
                        os.rename(old_file, new_file)

            # Move current compressed file
            os.rename(f"{self.filename}.gz", f"{self.filename}.1.gz")

            # Reset size counter
            self.current_size = 0


def setup_logging() -> None:
    """
    Configure enhanced structured logging for the valuation engine

    Features:
    - Calculation-specific log levels
    - Financial data formatting
    - Context-aware logging
    - Audit trail capabilities
    - Secure file storage with rotation
    """
    # Validate log level allows INFO (critical for debug logs)
    log_level_str = public_adaptive_stdout_log_level(getattr(settings, "log_level", "info")).upper()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    log_level = level_map.get(log_level_str, logging.INFO)

    # Ensure INFO level is allowed (warn if it's not)
    if log_level > logging.INFO:
        print(
            f"⚠️ WARNING: Log level '{log_level_str}' ({log_level}) may suppress INFO logs. "
            f"INFO logs require level <= {logging.INFO}. Consider using 'INFO' or 'DEBUG'.",
            file=sys.stderr,
        )

    # Configure standard logging. ``force=True`` clears any handler that an earlier
    # transitive import installed via ``basicConfig`` — without this, our format and
    # stream settings are silently dropped because ``basicConfig`` is a no-op once
    # root has handlers. (Apr 28 2026 audit: ``api/v1/endpoints/credits.py`` had a
    # rogue module-level ``basicConfig`` that would have done exactly this.)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,
    )

    # Create formatters
    formatters = create_formatters(
        precision=getattr(settings, "log_precision", 2),
        privacy_mode=getattr(settings, "log_privacy_mode", False),
    )

    # Create processors
    processors = [
        structlog.contextvars.merge_contextvars,
        TimeStamper(fmt="iso"),
        add_log_level,
        FinancialDataProcessor(
            precision=getattr(settings, "log_precision", 2),
            privacy_mode=getattr(settings, "log_privacy_mode", False),
        ),
        AuditTrailProcessor(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Backstop for the Three Towers Capital empty-line incident:
        # drop records that would render as blank in the platform stream.
        _drop_empty_event,
    ]

    # Use JSON renderer in production or Railway (container) environments.
    # ConsoleRenderer produces multi-line output that clutters Railway logs.
    is_deployed = (
        settings.is_production
        or os.environ.get("RAILWAY_ENVIRONMENT")
        or os.environ.get("RAILWAY_SERVICE_NAME")
    )
    if is_deployed:
        # Rename event → message so the platform's JSON parser populates the
        # visible log line (Railway/Cloud Run/Datadog look for "message").
        processors.append(_rename_event_to_message)
        processors.append(JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    # Configure structlog with custom levels (use validated log_level)
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # PDF / WeasyPrint stack: tune stdlib loggers AFTER root handlers exist (basicConfig above).
    # Loading weasyprint_env runs configure_once (warning filters); reapply restores levels after
    # structlog/other code that might mutate loggers — see reapply_pdf_vendor_logging_levels().
    # Plus: attach VendorNoiseFilter to root handlers. The level clamp alone is insufficient
    # because vendor packages reset their own logger levels on import (weasyprint/logger.py
    # forces WARNING, which lets "Ignored 'box-shadow' …" CSS-warning records propagate to
    # root and Railway stdout). The filter on the handler catches them regardless.
    try:
        from src.services.infrastructure.weasyprint_env import (
            attach_vendor_noise_filter_to_root_handlers,
            reapply_pdf_vendor_logging_levels,
        )

        reapply_pdf_vendor_logging_levels()
        attach_vendor_noise_filter_to_root_handlers()
    except ImportError:
        # Sandbox / partial tree without valuation-iq packages
        pass

    # Set up secure file logging for audit logs
    if getattr(settings, "audit_logging_enabled", True):
        audit_handler = SecureFileHandler(
            filename=getattr(settings, "audit_log_file", "logs/audit.log"),
            max_bytes=getattr(settings, "audit_log_max_bytes", 10 * 1024 * 1024),
            backup_count=getattr(settings, "audit_log_backup_count", 5),
        )

        audit_logger = logging.getLogger("audit")
        audit_logger.addHandler(audit_handler)
        audit_logger.setLevel(AUDIT_LEVEL)
        # Custom AUDIT_LEVEL (27) propagating to root can render as empty [wrn] on some hosts (e.g. Railway).
        audit_logger.propagate = False


def get_logger(name: str) -> CalculationLogger:
    """
    Get an enhanced structured logger instance with calculation capabilities

    Args:
        name: Logger name (usually __name__)

    Returns:
        Enhanced structured logger instance with calculation methods
    """
    try:
        base_logger = structlog.get_logger(name)
        return CalculationLogger(base_logger)
    except Exception:
        # Fallback to basic logging if structlog fails completely
        import logging

        basic_logger = logging.getLogger(name)
        return CalculationLogger(basic_logger)


def get_audit_logger() -> logging.Logger:
    """Get a dedicated audit logger for compliance logging"""
    return logging.getLogger("audit")


def test_logging_system() -> bool:
    """
    Test if the logging system is working properly

    Returns:
        True if logging works, False otherwise
    """
    try:
        test_logger = get_logger("logging_test")
        test_logger.info("Logging system test", test_param="working")
        return True
    except Exception as e:
        print(f"Logging test failed: {e}")
        return False


def log_calculation_step(
    step_name: str,
    inputs: Mapping[str, object],
    outputs: Mapping[str, object],
    formula: Optional[str] = None,
    validation: Optional[Mapping[str, object]] = None,
) -> None:
    """Log a calculation step with structured data"""
    logger = get_logger(__name__)
    logger.calculation(
        f"Calculation step: {step_name}",
        calculation_step={
            "step_name": step_name,
            "inputs": inputs,
            "outputs": outputs,
            "formula": formula,
            "validation": validation,
        },
    )


def log_calculation_formula(
    logger_instance: LoggerBackend,
    step_number: int,
    step_name: str,
    formula: str,
    inputs: Mapping[str, object],
    outputs: Mapping[str, object],
    intermediate_values: Optional[Mapping[str, object]] = None,
    academic_reference: Optional[str] = None,
) -> None:
    """
    Log a calculation formula with input → calculation → output format.

    This helper function provides standardized formula logging for all calculation steps,
    ensuring complete traceability and auditability per McKinsey/Bain standards.

    Args:
        logger_instance: Logger instance (from get_logger())
        step_number: Step number (0-11)
        step_name: Human-readable step name
        formula: Formula string (e.g., "EV = Revenue × EV/Revenue Multiple")
        inputs: Dictionary of input values
        outputs: Dictionary of output values
        intermediate_values: Optional dictionary of intermediate calculation values
        academic_reference: Optional academic reference (e.g., "McKinsey Valuation (2015)")

    Example:
        log_calculation_formula(
            logger,
            step_number=3,
            step_name="Base Enterprise Value",
            formula="EV = Revenue × EV/Revenue Multiple",
            inputs={'revenue': 1000000, 'ev_revenue_multiple': 1.5},
            outputs={'enterprise_value': 1500000},
            intermediate_values={'base_ev': 1500000},
            academic_reference="McKinsey Valuation (2015), Chapter 4"
        )
    """
    try:
        # Format formula with actual values for readability
        formula_with_values = formula
        if inputs and outputs:
            # Try to create a readable formula string with actual values
            try:
                # Extract key values for formula display
                input_strs = []
                for key, value in inputs.items():
                    if isinstance(value, (int, float)):
                        if abs(value) >= 1000:
                            input_strs.append(f"{key}={value:,.0f}")
                        else:
                            input_strs.append(f"{key}={value:.2f}")
                    else:
                        input_strs.append(f"{key}={value}")

                output_strs = []
                for key, value in outputs.items():
                    if isinstance(value, (int, float)):
                        if abs(value) >= 1000:
                            output_strs.append(f"{key}={value:,.0f}")
                        else:
                            output_strs.append(f"{key}={value:.2f}")
                    else:
                        output_strs.append(f"{key}={value}")

                if input_strs and output_strs:
                    formula_with_values = f"{formula} → Inputs: [{', '.join(input_strs)}] → Outputs: [{', '.join(output_strs)}]"
            except Exception:
                # If formatting fails, use original formula
                pass

        # Build structured log data
        log_data: LogPayload = {
            "step_number": step_number,
            "step_name": step_name,
            "formula": formula,
            "formula_with_values": formula_with_values,
            "inputs": inputs,
            "outputs": outputs,
        }

        if intermediate_values:
            log_data["intermediate_values"] = intermediate_values

        if academic_reference:
            log_data["academic_reference"] = academic_reference

        # Log at INFO level with structured data
        logger_instance.info(
            f"🧮 Step {step_number}: {step_name} - Formula: {formula}", extra=log_data
        )

    except Exception as e:
        # Fallback: log basic formula information if structured logging fails
        logger_instance.warning(
            f"Failed to log calculation formula for Step {step_number}: {e}",
            extra={
                "step_number": step_number,
                "step_name": step_name,
                "formula": formula,
                "error": str(e),
            },
        )


def log_validation_step(
    validation_name: str,
    data: Mapping[str, object],
    rules: list[str],
    results: Mapping[str, object],
) -> None:
    """Log a validation step with structured data"""
    logger = get_logger(__name__)
    logger.validation(
        f"Validation step: {validation_name}",
        validation_step={
            "validation_name": validation_name,
            "data": data,
            "rules": rules,
            "results": results,
        },
    )


def log_audit_event(
    event_type: str,
    actor: str,
    action: str,
    resource: str,
    data: Optional[Mapping[str, object]] = None,
    metadata: Optional[Mapping[str, object]] = None,
) -> None:
    """Log an audit event for compliance (structlog INFO on stdout; AUDIT_LEVEL to file handler only)."""
    payload: LogPayload = {
        "event_type": event_type,
        "actor": actor,
        "action": action,
        "resource": resource,
        "data": data,
        "metadata": metadata,
    }
    logger = get_logger(__name__)
    logger.info(
        f"Audit event: {event_type}",
        audit_event=payload,
    )
    audit_logger = get_audit_logger()
    if audit_logger.handlers:
        audit_logger.log(
            AUDIT_LEVEL,
            f"Audit event: {event_type}",
            extra={"audit_event": payload},
        )


def log_performance_metric(metric_name: str, value: Decimal, unit: Optional[str] = None) -> None:
    """Log a performance metric"""
    logger = get_logger(__name__)
    logger.info(
        f"Performance metric: {metric_name}",
        performance_metric={"metric_name": metric_name, "value": value, "unit": unit},
    )


def log_financial_data(operation: str, data: Mapping[str, object], precision: int = 2) -> None:
    """Log financial data with proper formatting"""
    logger = get_logger(__name__)
    logger.info(
        f"Financial operation: {operation}",
        financial_data=data,
        operation=operation,
        precision=precision,
    )
