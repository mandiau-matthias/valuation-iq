"""Custom exceptions for report generation infrastructure."""


class ReportGenerationError(Exception):
    """Base exception for all report generation errors."""

    def __init__(
        self,
        message: str,
        company_name: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.company_name = company_name
        self.correlation_id = correlation_id
        self.message = message

    def __str__(self) -> str:
        base_msg = self.message
        if self.company_name:
            base_msg += f" (Company: {self.company_name})"
        if self.correlation_id:
            base_msg += f" (Correlation ID: {self.correlation_id})"
        return base_msg


class TemplateRenderingError(ReportGenerationError):
    """Template rendering failed."""

    pass


class DataTransformationError(ReportGenerationError):
    """Data transformation failed."""

    pass


class ValidationError(ReportGenerationError):
    """Data validation failed."""

    pass


class DataValidationError(ValidationError):
    """Data validation failed (alias for ValidationError for compatibility)."""

    pass


class MissingDataError(DataTransformationError):
    """Required data missing from response."""

    def __init__(
        self,
        message: str,
        missing_fields: list[str] | None = None,
        company_name: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message, company_name=company_name, correlation_id=correlation_id)
        self.missing_fields = missing_fields or []


class StepDataError(DataTransformationError):
    """Error building step data."""

    pass


class WaterfallDataError(DataTransformationError):
    """Error building waterfall data."""

    pass
