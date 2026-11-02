"""
Base Report Strategy - Abstract Base Class

Defines the interface and common functionality for report generation strategies.
Implements Strategy Pattern for different report types.

BANK-GRADE DESIGN:
- Protocol/ABC for type safety
- Common validation logic
- Shared error handling patterns
- Consistent logging structure
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.services.infrastructure.exceptions import (
    MissingDataError,
    DataTransformationError,
    TemplateRenderingError,
    ValidationError,
)
from src.services.infrastructure.report_generation.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
)
from src.services.infrastructure.report_generation.retry_handler import (
    RetryHandler,
    RetryConfig,
)
from src.services.infrastructure.report_generation.fallback_generator import (
    FallbackGenerator,
)
from src.services.infrastructure.report_generation.metrics_collector import (
    MetricsCollector,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ReportStrategy(ABC):
    """
    Protocol/ABC for report generation strategies.
    
    BANK-GRADE INTERFACE:
    - Single Responsibility: Each strategy generates one report type
    - Open/Closed: Easy to extend with new report types
    - Dependency Inversion: Depend on abstractions
    """
    
    @abstractmethod
    async def generate(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        context: Dict[str, Optional[str]],
        template_service: Any,
        transform_func: Callable,
        render_method: str,
    ) -> Optional[str]:
        """
        Generate report HTML.
        
        Args:
            response: ValuationResponse with calculation results
            request: Original ValuationRequest for context
            context: Context dictionary with company_name and correlation_id
            template_service: TemplateService instance for rendering
            transform_func: Function to transform response to template data
            render_method: Name of render method on template_service
            
        Returns:
            HTML string, or None if generation fails
            
        Raises:
            MissingDataError: If required inputs are missing
            DataTransformationError: If data transformation fails
            TemplateRenderingError: If template rendering fails
        """
        pass
    
    @abstractmethod
    def validate_inputs(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        report_type: str,
    ) -> None:
        """
        Validate inputs at boundary.
        
        Args:
            response: ValuationResponse to validate
            request: ValuationRequest to validate
            report_type: Type of report (for error messages)
            
        Raises:
            MissingDataError: If required inputs are missing or invalid
        """
        pass
    
    @abstractmethod
    def get_timeout_seconds(self) -> float:
        """
        Return timeout for this report type.
        
        Returns:
            Timeout in seconds
        """
        pass
    
    @abstractmethod
    def get_min_content_length(self) -> int:
        """
        Return minimum HTML content length for validation.
        
        Returns:
            Minimum content length in characters
        """
        pass
    
    @abstractmethod
    def get_report_type(self) -> str:
        """
        Return report type name.
        
        Returns:
            Report type name (e.g., "Accountant View", "Info Tab")
        """
        pass


class BaseReportStrategy(ReportStrategy):
    """
    Base implementation with common functionality.
    
    BANK-GRADE BASE CLASS:
    - DRY: Shared validation, error handling, logging
    - Consistent patterns across all strategies
    - Common timeout and validation logic
    """
    
    def __init__(
        self,
        logger_instance=None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        retry_handler: Optional[RetryHandler] = None,
        retry_config: Optional[RetryConfig] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize base strategy.
        
        Args:
            logger_instance: Optional logger instance (creates default if not provided)
            circuit_breaker: Optional circuit breaker instance (creates default if not provided)
            circuit_breaker_config: Optional circuit breaker configuration
            retry_handler: Optional retry handler instance (creates default if not provided)
            retry_config: Optional retry configuration
        """
        self.logger = logger_instance or logger
        
        # BANK-GRADE: Initialize circuit breaker for this strategy
        if circuit_breaker is not None:
            self.circuit_breaker = circuit_breaker
        else:
            # Create circuit breaker with default or provided config
            breaker_config = circuit_breaker_config or CircuitBreakerConfig(
                failure_threshold=5,
                timeout_seconds=60.0,
                success_threshold=2,
                failure_window_seconds=60.0,
            )
            self.circuit_breaker = CircuitBreaker(
                name=self.get_report_type().lower().replace(" ", "_"),
                config=breaker_config,
            )
        
        # BANK-GRADE: Initialize retry handler for this strategy
        if retry_handler is not None:
            self.retry_handler = retry_handler
        else:
            # Create retry handler with default or provided config
            retry_cfg = retry_config or RetryConfig(
                max_attempts=3,
                backoff_base=1.0,
                max_backoff=8.0,
                jitter=True,
            )
            self.retry_handler = RetryHandler(config=retry_cfg, logger=self.logger)
        
        # BANK-GRADE: Initialize fallback generator
        self.fallback_generator = FallbackGenerator()
        
        # BANK-GRADE: Initialize metrics collector (optional)
        self.metrics_collector = metrics_collector
    
    def validate_inputs(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol,
        report_type: str,
    ) -> None:
        """
        BANK-GRADE: Validate inputs at service boundary.
        
        Args:
            response: ValuationResponse to validate
            request: ValuationRequest to validate
            report_type: Type of report being generated (for error messages)
            
        Raises:
            MissingDataError: If required inputs are missing or invalid
        """
        if not response:
            raise MissingDataError(
                f"ValuationResponse is required but was None for {report_type}",
                missing_fields=['response'],
                company_name=None,
                correlation_id=None
            )
        if not request:
            raise MissingDataError(
                f"ValuationRequest is required but was None for {report_type}",
                missing_fields=['request'],
                company_name=None,
                correlation_id=None
            )
        if not hasattr(response, 'company_name') or not response.company_name:
            raise MissingDataError(
                f"ValuationResponse missing required field: company_name for {report_type}",
                missing_fields=['company_name'],
                company_name=None,
                correlation_id=getattr(request, "correlation_id", None)
            )
    
    def _get_context(
        self,
        response: ValuationResponseProtocol,
        request: ValuationRequestProtocol
    ) -> Dict[str, Optional[str]]:
        """
        BANK-GRADE: Extract common context for logging and error handling.
        
        Args:
            response: ValuationResponse
            request: ValuationRequest
            
        Returns:
            Dictionary with company_name and correlation_id
        """
        return {
            "company_name": getattr(response, "company_name", "unknown") if response else "unknown",
            "correlation_id": getattr(request, "correlation_id", None) if request else None,
        }
    
    def _log_entry(
        self,
        method_name: str,
        context: Dict[str, Optional[str]],
        report_type: str,
        template_service: Any,
    ) -> None:
        """
        BANK-GRADE: Structured logging at method entry.
        
        Args:
            method_name: Name of the method being called
            context: Context dictionary with company_name and correlation_id
            report_type: Type of report being generated
            template_service: TemplateService instance for availability check
        """
        self.logger.info(
            f"🔍 [REPORT-STRATEGY] {method_name}() called for {report_type}",
            extra={
                "company": context["company_name"],
                "correlation_id": context["correlation_id"],
                "report_type": report_type,
                "template_service_available": template_service is not None,
                "template_service_type": type(template_service).__name__ if template_service else "None",
            },
        )
    
    def _check_template_service_available(
        self,
        context: Dict[str, Optional[str]],
        report_type: str,
        template_service: Any,
    ) -> bool:
        """
        BANK-GRADE: Check if template service is available.
        
        Args:
            context: Context dictionary for logging
            report_type: Type of report being generated
            template_service: TemplateService instance to check
            
        Returns:
            True if template service is available, False otherwise
        """
        if template_service is None:
            self.logger.warning(
                f"⚠️ [REPORT-STRATEGY] Template service not available for {report_type}",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "template_service_is_none": True,
                },
            )
            return False
        return True
    
    def _validate_html_content(
        self,
        html_content: Optional[str],
        context: Dict[str, Optional[str]],
        report_type: str,
        min_length: int,
    ) -> bool:
        """
        BANK-GRADE: Validate HTML content meets minimum requirements.
        
        Args:
            html_content: Generated HTML content
            context: Context dictionary for logging
            report_type: Type of report being generated
            min_length: Minimum content length required
            
        Returns:
            True if content is valid, False otherwise
        """
        if html_content and isinstance(html_content, str) and len(html_content) >= min_length:
            self.logger.info(
                f"✅ [REPORT-STRATEGY] {report_type} HTML content validated",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "html_content_length": len(html_content),
                    "minimum_required_length": min_length,
                },
            )
            return True
        else:
            # CRITICAL: Log validation failures at ERROR level for Info Tab (critical for frontend)
            log_level = self.logger.error if report_type == "Info Tab" else self.logger.warning
            log_level(
                f"⚠️ [REPORT-STRATEGY] {report_type} HTML generation returned empty or too short content",
                extra={
                    "company": context["company_name"],
                    "correlation_id": context["correlation_id"],
                    "report_type": report_type,
                    "html_content_is_none": html_content is None,
                    "html_content_type": type(html_content).__name__ if html_content else "None",
                    "html_content_length": len(html_content) if html_content else 0,
                    "minimum_required_length": min_length,
                    "validation_failed": True,
                    "impact": "Frontend will show 'Info Tab Not Available' error" if report_type == "Info Tab" else None,
                    "diagnosis": [
                        "HTML content is None - check template rendering logs",
                        "HTML content is too short - check template data transformation",
                        "Template may have failed silently - check template service logs"
                    ] if report_type == "Info Tab" else None,
                },
            )
            return False

