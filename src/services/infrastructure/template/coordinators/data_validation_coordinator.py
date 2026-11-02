"""
Data Validation Coordinator

Handles data validation logic before rendering.
Extracted from template_service.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive validation
- Detailed logging
"""

from typing import Any, Dict, List

from src.services.infrastructure.report_validator import ReportDataValidator, ValidationLevel
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DataValidationCoordinator:
    """
    Coordinates data validation logic before rendering.
    
    Responsibilities:
    - Validate valuation data
    - Check required fields
    - Log validation results
    """
    
    def __init__(self, logger_instance=None):
        """
        Initialize data validation coordinator.
        
        Args:
            logger_instance: Logger instance (optional)
        """
        self.logger = logger_instance or logger
        self.validator = ReportDataValidator()
    
    def validate_accountant_view_data(self, valuation_data: Dict[str, Any]) -> None:
        """
        Validate data for Accountant View report generation.
        
        Args:
            valuation_data: Valuation data dictionary
            
        Raises:
            ValueError: If critical validation failures occur
        """
        self.logger.info("Step 1: Validating input data")
        validation_results = self.validator.validate_valuation_response(valuation_data)
        
        # Check for CRITICAL failures
        critical_failures = [r for r in validation_results if r.level == ValidationLevel.CRITICAL]
        if critical_failures:
            self.logger.error("CRITICAL VALIDATION FAILURES - STOPPING GENERATION")
            for failure in critical_failures:
                self.logger.error(f"  ✗ {failure.field_path}: {failure.message}")
            raise ValueError(f"Critical validation failures: {len(critical_failures)} errors")
        
        # Log warnings
        warnings = [r for r in validation_results if r.level == ValidationLevel.WARNING]
        if warnings:
            self.logger.warning(f"VALIDATION WARNINGS: {len(warnings)} fields with issues")
            for warning in warnings[:5]:  # Log first 5
                self.logger.warning(f"  ⚠ {warning.field_path}: {warning.message}")
            if len(warnings) > 5:
                self.logger.warning(f"  ... and {len(warnings) - 5} more warnings")
        
        # Log info
        info_results = [r for r in validation_results if r.level == ValidationLevel.INFO]
        self.logger.info(f"VALIDATION SUCCESS: {len(info_results)} fields validated")
        
        # Log data summary
        self.logger.info("Report Data Summary:")
        self.logger.info(f"  - Company: {valuation_data.get('company_name', 'N/A')}")
        self.logger.info(f"  - Valuation Date: {valuation_data.get('valuation_date', 'N/A')}")
        self.logger.info(f"  - Top-level keys: {list(valuation_data.keys())}")
        self.logger.info(f"  - Total data size: ~{len(str(valuation_data))} chars")
    
    def validate_info_tab_data(self, valuation_data: Dict[str, Any], validation_cache: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data for Info Tab report generation.
        
        Args:
            valuation_data: Valuation data dictionary
            validation_cache: Validation cache dictionary
            
        Returns:
            Validation result dictionary
        """
        # Optimized validation - cache validation results
        cache_key = f"validation_{id(valuation_data)}"
        if cache_key not in validation_cache:
            # Validate calculation steps before rendering
            calculation_steps = valuation_data.get('calculation_steps', [])
            validation_result = {
                'has_steps': bool(calculation_steps),
                'step_count': len(calculation_steps) if calculation_steps else 0,
                'is_valid': len(calculation_steps) == 12 if calculation_steps else False
            }
            
            if calculation_steps and len(calculation_steps) != 12:
                self.logger.warning(
                    f"Expected 12 calculation steps, got {len(calculation_steps)}",
                    extra={
                        'expected_steps': 12,
                        'actual_steps': len(calculation_steps),
                        'company_name': valuation_data.get('company_name', 'N/A')
                    }
                )
            
            validation_cache[cache_key] = validation_result
            # Limit cache size to prevent memory issues
            if len(validation_cache) > 100:
                # Remove oldest entries (simple FIFO)
                oldest_key = next(iter(validation_cache))
                del validation_cache[oldest_key]
        else:
            validation_result = validation_cache[cache_key]
        
        # Validate required sections
        required_sections = {
            'company_name': valuation_data.get('company_name'),
            'valuation_date': valuation_data.get('valuation_date'),
            'equity_value_mid': valuation_data.get('equity_value_mid')
        }
        missing_sections = [k for k, v in required_sections.items() if v is None]
        if missing_sections:
            self.logger.warning(
                f"⚠️ Missing required sections: {missing_sections}",
                extra={
                    'missing_sections': missing_sections,
                    'company_name': valuation_data.get('company_name', 'N/A')
                }
            )
        
        # Log which optional sections are present
        optional_sections = {
            'multiple_pipeline': valuation_data.get('multiple_pipeline'),
            'owner_concentration_analysis': valuation_data.get('owner_concentration_analysis'),
            'adjustments_summary': valuation_data.get('adjustments_summary'),
            'transparency': valuation_data.get('transparency'),
            'valuation_waterfall': valuation_data.get('valuation_waterfall')
        }
        present_sections = [k for k, v in optional_sections.items() if v is not None]
        self.logger.info(
            "Optional sections status",
            extra={
                'present_sections': present_sections,
                'missing_sections': [k for k in optional_sections.keys() if k not in present_sections],
                'company_name': valuation_data.get('company_name', 'N/A')
            }
        )
        
        return validation_result

