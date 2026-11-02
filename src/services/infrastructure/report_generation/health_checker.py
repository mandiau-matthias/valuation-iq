"""
Health Checker for Report Generation

Performs periodic health checks of template service and transformation pipeline.
Provides proactive monitoring and early issue detection.

BANK-GRADE DESIGN:
- Periodic health checks of template service
- Check template file availability
- Validate template syntax
- Check transformation pipeline
- Report health status via metrics
"""

import time
from typing import Dict, Optional, Any, List
from enum import Enum
from dataclasses import dataclass


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    status: HealthStatus
    component: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: float = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "component": self.component,
            "message": self.message,
            "details": self.details or {},
            "timestamp": self.timestamp,
        }


class HealthChecker:
    """
    Performs health checks for report generation components.
    
    BANK-GRADE RESPONSIBILITIES:
    - Check template service availability
    - Validate template files
    - Check transformation pipeline
    - Report health status
    """
    
    def __init__(self, template_service: Any, logger=None):
        """
        Initialize health checker.
        
        Args:
            template_service: TemplateService instance to check
            logger: Logger instance for logging health checks
        """
        self.template_service = template_service
        self.logger = logger
    
    def check_template_service(self) -> HealthCheckResult:
        """
        Check template service health.
        
        Returns:
            HealthCheckResult with template service status
        """
        if self.template_service is None:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="template_service",
                message="Template service is not available",
                details={"service_available": False},
            )
        
        try:
            # Check if template service has required methods
            required_methods = [
                "render_accountant_view_report",
                "render_main_report",  # 5-page bank-grade report
                "render_main_report_pdf",  # PDF-optimized launch path
            ]
            optional_methods = [
                "render_simplified_report",  # Simplified 5-page template
            ]
            
            missing_methods = []
            for method in required_methods:
                if not hasattr(self.template_service, method):
                    missing_methods.append(method)
            
            if missing_methods:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    component="template_service",
                    message=f"Template service missing methods: {', '.join(missing_methods)}",
                    details={"missing_methods": missing_methods},
                )
            
            # Try to check template initialization (if available)
            if hasattr(self.template_service, "is_initialized"):
                if not self.template_service.is_initialized():
                    return HealthCheckResult(
                        status=HealthStatus.DEGRADED,
                        component="template_service",
                        message="Template service not initialized",
                        details={"initialized": False},
                    )
            
            if hasattr(self.template_service, "validate_required_templates"):
                template_validation = self.template_service.validate_required_templates()
                missing_templates = [
                    name for name, exists in template_validation.items() if not exists
                ]
                if missing_templates:
                    return HealthCheckResult(
                        status=HealthStatus.DEGRADED,
                        component="template_service",
                        message="Template service is available but some required templates are missing",
                        details={
                            "service_available": True,
                            "missing_templates": missing_templates,
                        },
                    )

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                component="template_service",
                message="Template service is healthy",
                details={
                    "service_available": True,
                    "has_required_methods": True,
                },
            )
            
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="template_service",
                message=f"Template service health check failed: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
    
    def check_transformation_pipeline(self) -> HealthCheckResult:
        """
        Check transformation pipeline health.
        
        Returns:
            HealthCheckResult with transformation pipeline status
        """
        try:
            # Check if transformation functions are importable
            from src.services.infrastructure.report_data_transformer import (
                transform_valuation_response,
            )
            # Check for new simplified transformer
            from src.services.infrastructure.simplified_report_transformer import (
                get_simplified_report_transformer,
            )
            
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                component="transformation_pipeline",
                message="Transformation pipeline is healthy",
                details={
                    "transform_valuation_response_available": True,
                    "simplified_report_transformer_available": True,
                },
            )
            
        except ImportError as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="transformation_pipeline",
                message=f"Transformation pipeline import failed: {str(e)}",
                details={
                    "error_type": "ImportError",
                    "error_message": str(e),
                },
            )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                component="transformation_pipeline",
                message=f"Transformation pipeline check failed: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
    
    def check_all(self) -> Dict[str, HealthCheckResult]:
        """
        Perform all health checks.
        
        Returns:
            Dictionary mapping component names to health check results
        """
        results = {
            "template_service": self.check_template_service(),
            "transformation_pipeline": self.check_transformation_pipeline(),
        }
        
        # Log results
        if self.logger:
            for component, result in results.items():
                log_level = (
                    "error" if result.status == HealthStatus.UNHEALTHY
                    else "warning" if result.status == HealthStatus.DEGRADED
                    else "info"
                )
                getattr(self.logger, log_level)(
                    f"🏥 [HEALTH-CHECK] {component}: {result.status.value}",
                    extra={
                        "component": component,
                        "status": result.status.value,
                        "message": result.message,
                        "details": result.details,
                    },
                )
        
        return results
    
    def get_overall_status(self) -> HealthStatus:
        """
        Get overall health status.
        
        Returns:
            Overall HealthStatus (worst status from all checks)
        """
        results = self.check_all()
        return self._derive_overall_status(results)

    def _derive_overall_status(
        self, results: Dict[str, HealthCheckResult]
    ) -> HealthStatus:
        """Derive the worst-case overall status from already-computed results."""
        statuses = [result.status for result in results.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif HealthStatus.HEALTHY in statuses:
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN
    
    def get_health_summary(self) -> Dict:
        """
        Get health check summary.
        
        Returns:
            Dictionary with overall status and component details
        """
        results = self.check_all()
        overall_status = self._derive_overall_status(results)
        
        return {
            "overall_status": overall_status.value,
            "components": {
                component: result.to_dict()
                for component, result in results.items()
            },
            "timestamp": time.time(),
        }

