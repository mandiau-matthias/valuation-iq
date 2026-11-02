"""
Academic Validation Service

BANK-GRADE: Single Responsibility - Validate calculations against academic standards

RESPONSIBILITY:
- Run post-calculation academic validation
- Check calculation provenance against academic references
- Report validation failures and warnings
- Log validation results

DOES NOT:
- Perform calculations (delegated to calculators)
- Generate HTML (delegated to HTML generator)
- Transform data (delegated to transformers)
- Determine phases (delegated to phase determiner)

SRP Compliance: This service has ONE reason to change - academic validation requirements
"""

from typing import Dict, Any, Optional
from src.utils.logging import get_logger
from src.utils.exceptions import (
    ValidationError,
    ExternalServiceError,
    ValuationEngineError,
)

logger = get_logger(__name__)


class AcademicValidationService:
    """
    BANK-GRADE: Validates calculations against academic standards.
    
    SINGLE RESPONSIBILITY: Academic validation only
    
    This service focuses solely on validating that calculations:
    - Follow academic methodologies
    - Reference appropriate sources
    - Meet quality standards
    - Are traceable to academic literature
    
    Design Pattern: Service Pattern
    - Separates validation from calculation
    - Enables independent testing of validation logic
    - Allows validation rules to change without affecting calculations
    """
    
    def __init__(self, academic_tracker_manager: Optional["AcademicTrackerManager"] = None):
        """
        Initialize academic validation service.
        
        Args:
            academic_tracker_manager: Academic tracker manager instance (injected)
        """
        # Lazy import to avoid circular dependency
        if academic_tracker_manager is None:
            from .academic_tracker_manager import AcademicTrackerManager
            self.academic_tracker_manager = AcademicTrackerManager()
        else:
            self.academic_tracker_manager = academic_tracker_manager
        
        # DEBUG: per-request service init; the validation result line
        # ([ACADEMIC-VALIDATION] Validation passed/failed) carries signal.
        logger.debug("✅ [ACADEMIC-VALIDATION] AcademicValidationService initialized")
    
    def validate_calculation(self) -> Dict[str, Any]:
        """
        Run post-calculation academic validation.
        
        BANK-GRADE: Validates calculations against academic standards and
        reports any deviations or warnings.
        
        SRP: Only validates, doesn't calculate or transform data
        
        Returns:
            Validation report with status, passed checks, failed checks, warnings
            
        Example:
            {
                'status': 'passed',
                'passed': 12,
                'failed': 0,
                'warnings': []
            }
        """
        tracker = self.academic_tracker_manager.academic_tracker
        validation_engine = self.academic_tracker_manager.get_validation_engine()
        
        # Check if validation is enabled
        if not self.academic_tracker_manager.academic_tracking_enabled or not tracker:
            logger.debug("[ACADEMIC-VALIDATION] Validation disabled or tracker unavailable")
            return {
                "status": "disabled",
                "passed": 0,
                "failed": 0,
                "warnings": []
            }
        
        try:
            # Run validation engine
            validation_report = validation_engine.validate_from_provenance(tracker)
            
            # Log results
            failed_count = validation_report.get('failed', 0)
            passed_count = validation_report.get('passed', 0)
            
            if failed_count > 0:
                logger.warning(
                    "[ACADEMIC-VALIDATION] Validation failures detected",
                    extra={
                        "passed": passed_count,
                        "failed": failed_count,
                        "warnings": validation_report.get('warnings', [])
                    }
                )
            else:
                logger.info(
                    "[ACADEMIC-VALIDATION] Validation passed",
                    extra={"checks_passed": passed_count}
                )
            
            return validation_report
            
        except (ValidationError, ExternalServiceError) as e:
            # Re-raise specific validation errors
            logger.error(
                "[ACADEMIC-VALIDATION] Validation error",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise
            
        except ValuationEngineError as e:
            # Re-raise valuation engine errors
            logger.error(
                "[ACADEMIC-VALIDATION] Valuation engine error during validation",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise
            
        except (AttributeError, TypeError, KeyError) as e:
            # Handle data structure errors gracefully
            logger.error(
                "[ACADEMIC-VALIDATION] Data structure error during validation",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            return {
                "status": "error",
                "error": str(e),
                "passed": 0,
                "failed": 0,
                "warnings": [f"Validation failed due to data structure error: {str(e)}"]
            }
    
    def is_enabled(self) -> bool:
        """
        Check if academic validation is enabled.
        
        Returns:
            True if validation is enabled and tracker is available
        """
        return (
            self.academic_tracker_manager.academic_tracking_enabled and
            self.academic_tracker_manager.academic_tracker is not None
        )
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """
        Get summary of validation configuration.
        
        Returns:
            Dictionary with validation status and configuration
        """
        return {
            "enabled": self.is_enabled(),
            "tracker_available": self.academic_tracker_manager.academic_tracker is not None,
            "tracking_enabled": self.academic_tracker_manager.academic_tracking_enabled,
        }
