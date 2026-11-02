"""Contracts and configuration for HTML report generation."""

from typing import Protocol

TemplateData = dict[str, object]


class ReportServiceLogger(Protocol):
    def debug(self, message: str, *args: object, **kwargs: object) -> None: ...

    def info(self, message: str, *args: object, **kwargs: object) -> None: ...

    def warning(self, message: str, *args: object, **kwargs: object) -> None: ...

    def error(self, message: str, *args: object, **kwargs: object) -> None: ...


class HTMLReportConfig:
    """Configuration constants for HTML report generation."""

    TRANSFORMATION_TIMEOUT_SECONDS = 30.0
    RENDERING_TIMEOUT_SECONDS = 60.0
    MIN_HTML_CONTENT_LENGTH = 100


__all__ = ["HTMLReportConfig", "ReportServiceLogger", "TemplateData"]
