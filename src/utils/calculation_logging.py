"""Calculation-aware logger wrapper and custom log levels."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Optional, Protocol


class LoggerBackend(Protocol):
    """Minimal logger surface shared by structlog and stdlib loggers."""

    def info(self, message: str, *args: object, **kwargs: object) -> object: ...
    def debug(self, message: str, *args: object, **kwargs: object) -> object: ...
    def warning(self, message: str, *args: object, **kwargs: object) -> object: ...
    def error(self, message: str, *args: object, **kwargs: object) -> object: ...
    def critical(self, message: str, *args: object, **kwargs: object) -> object: ...


def _logger_name(logger: object) -> str:
    context = getattr(logger, "_context", None)
    if isinstance(context, Mapping):
        name = context.get("name")
        if isinstance(name, str) and name:
            return name
    return "unknown"


def _percent_format_message(message: str, args: tuple[object, ...]) -> str:
    """Apply printf-style ``message % args`` when args are given; never raises."""
    if not args:
        return message
    try:
        return str(message % args)
    except (TypeError, ValueError):
        return message


CALCULATION_LEVEL = 25
VALIDATION_LEVEL = 26
AUDIT_LEVEL = 27


def register_calculation_log_levels() -> None:
    """Register custom calculation-specific stdlib log levels."""
    logging.addLevelName(CALCULATION_LEVEL, "CALCULATION")
    logging.addLevelName(VALIDATION_LEVEL, "VALIDATION")
    logging.addLevelName(AUDIT_LEVEL, "AUDIT")


register_calculation_log_levels()


class CalculationLogger:
    """Custom logger for calculation-specific logging."""

    def __init__(self, logger: LoggerBackend) -> None:
        self.logger = logger

    def info(self, message: Optional[str], *args: object, **kwargs: object) -> None:
        """Log an info message with stdlib-style ``fmt % args`` support."""
        if message is None:
            message = "Info logged (no message provided)"
        elif not isinstance(message, str):
            message = f"Info logged (invalid message type: {type(message).__name__})"
        elif not message.strip():
            message = "Info logged (no message provided)"

        message = _percent_format_message(message, args)
        try:
            self.logger.info(message, **kwargs)
        except Exception:
            logging.getLogger(_logger_name(self.logger)).info(message)

    def debug(self, message: Optional[str], *args: object, **kwargs: object) -> None:
        """Log a debug message with stdlib-style ``fmt % args`` support."""
        if message is None:
            message = "Debug logged (no message provided)"
        elif not isinstance(message, str):
            message = f"Debug logged (invalid message type: {type(message).__name__})"
        elif not message.strip():
            message = "Debug logged (no message provided)"

        message = _percent_format_message(message, args)
        try:
            self.logger.debug(message, **kwargs)
        except Exception:
            logging.getLogger(_logger_name(self.logger)).debug(message)

    def warning(self, message: Optional[str], *args: object, **kwargs: object) -> None:
        """Log a warning message with stdlib-style ``fmt % args`` support."""
        if message is None:
            message = "Warning occurred (no message provided)"
        elif not isinstance(message, str):
            message = f"Warning occurred (invalid message type: {type(message).__name__})"
        elif not message.strip():
            message = "Warning occurred (no message provided)"

        if kwargs.get("exc_info") and (not message or not message.strip()):
            message = "Warning occurred (exception logged without message)"

        message = _percent_format_message(message, args)
        try:
            self.logger.warning(message, **kwargs)
        except Exception:
            logging.getLogger(_logger_name(self.logger)).warning(message)

    def error(self, message: Optional[str], *args: object, **kwargs: object) -> None:
        """Log an error message with stdlib-style ``fmt % args`` support."""
        if message is None:
            message = "Error occurred (no message provided)"
        elif not isinstance(message, str):
            message = f"Error occurred (invalid message type: {type(message).__name__})"
        elif not message.strip():
            message = "Error occurred (no message provided)"

        if kwargs.get("exc_info") and (not message or not message.strip()):
            message = "Error occurred (exception logged without message)"

        message = _percent_format_message(message, args)
        try:
            self.logger.error(message, **kwargs)
        except Exception:
            logging.getLogger(_logger_name(self.logger)).error(message)

    def exception(self, message: Optional[str], *args: object, **kwargs: object) -> None:
        """Log an error message with exception info."""
        if message is None:
            message = "Exception occurred (no message provided)"
        elif not isinstance(message, str):
            message = f"Exception occurred (invalid message type: {type(message).__name__})"
        elif not message.strip():
            message = "Exception occurred (no message provided)"

        message = _percent_format_message(message, args)
        kwargs.setdefault("exc_info", True)
        try:
            self.logger.error(message, **kwargs)
        except Exception:
            logging.getLogger(_logger_name(self.logger)).error(message, exc_info=True)

    def critical(self, message: str, *args: object, **kwargs: object) -> None:
        """Log a critical message with stdlib-style ``fmt % args`` support."""
        message = _percent_format_message(message, args)
        try:
            self.logger.critical(message, **kwargs)
        except Exception:
            logging.getLogger(_logger_name(self.logger)).critical(message)

    def calculation(self, message: str, **kwargs: object) -> None:
        """Log a calculation step."""
        logging.getLogger(_logger_name(self.logger)).log(CALCULATION_LEVEL, message, extra=kwargs)

    def validation(self, message: str, **kwargs: object) -> None:
        """Log a validation step."""
        logging.getLogger(_logger_name(self.logger)).log(VALIDATION_LEVEL, message, extra=kwargs)

    def audit(self, message: str, **kwargs: object) -> None:
        """Log an audit event."""
        logging.getLogger(_logger_name(self.logger)).log(AUDIT_LEVEL, message, extra=kwargs)

    def log_calculation_step(self, message: str, **kwargs: object) -> None:
        """Alias for calculation method."""
        self.calculation(message, **kwargs)

    def log_validation_step(self, message: str, **kwargs: object) -> None:
        """Alias for validation method."""
        self.validation(message, **kwargs)
