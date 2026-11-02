"""
Academic Validation Engine

Post-calculation validation against academic standards.
Ensures all calculations align with peer-reviewed methodologies and industry best practices.

Author: Upswitch CTO Team
Date: December 2025
Status: Production Ready
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from decimal import Decimal
from threading import Lock

from src.services.academic.models import ValidationRule, ConfidenceLevel
from src.services.academic.academic_metadata_service import get_academic_metadata_service
from src.services.academic.calculation_provenance_tracker import CalculationProvenanceTracker
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ValidationResult:
    """Result of academic validation"""
    
    def __init__(self, calculation_id: str, rule_id: str):
        self.calculation_id = calculation_id
        self.rule_id = rule_id
        self.passed = True
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.value_validated: Optional[Any] = None
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'calculation_id': self.calculation_id,
            'rule_id': self.rule_id,
            'passed': self.passed,
            'warnings': self.warnings,
            'errors': self.errors,
            'value_validated': str(self.value_validated) if self.value_validated is not None else None,
            'timestamp': self.timestamp.isoformat()
        }


class AcademicValidationEngine:
    """
    Engine for validating calculations against academic standards
    
    Validates:
    - Value ranges per academic research
    - Formula correctness
    - Assumption reasonableness
    - Internal consistency
    """
    
    def __init__(self):
        """Initialize validation engine"""
        self.academic_service = get_academic_metadata_service()
        self.validation_results: List[ValidationResult] = []
        self._results_lock = Lock()
        self.logger = logger
        self.logger.debug("Academic Validation Engine initialized")
    
    def validate_calculation(
        self,
        calculation_id: str,
        value: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ValidationResult]:
        """
        Validate a single calculation against academic rules
        
        Args:
            calculation_id: ID of calculation to validate
            value: Value to validate
            context: Additional context for validation
            
        Returns:
            List of validation results (one per rule)
        """
        rules = self.academic_service.get_validation_rules_for_calculation(calculation_id)
        
        if not rules:
            self.logger.debug(f"No validation rules defined for {calculation_id}")
            return []
        
        results = []
        for rule in rules:
            result = ValidationResult(calculation_id, rule.rule_id)
            result.value_validated = value
            
            # Run validation
            validation_output = rule.validate(value, context)
            result.passed = validation_output.get('passed', True)
            result.warnings = validation_output.get('warnings', [])
            result.errors = validation_output.get('errors', [])
            
            results.append(result)
            with self._results_lock:
                self.validation_results.append(result)
            
            # Log results
            if not result.passed:
                self.logger.warning(
                    f"Validation failed: {calculation_id}",
                    extra={
                        'rule': rule.rule_name,
                        'errors': result.errors,
                        'value': value
                    }
                )
            elif result.warnings:
                self.logger.info(
                    f"Validation warning: {calculation_id}",
                    extra={
                        'rule': rule.rule_name,
                        'warnings': result.warnings,
                        'value': value
                    }
                )
        
        return results
    
    def validate_valuation_results(
        self,
        valuation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate complete valuation results
        
        Args:
            valuation_data: Complete valuation data dictionary
            
        Returns:
            Validation report
        """
        self.logger.info("Validating complete valuation results")
        
        validation_report = {
            'timestamp': datetime.now().isoformat(),
            'total_validations': 0,
            'passed': 0,
            'failed': 0,
            'warnings': 0,
            'validations_by_category': {},
            'critical_issues': [],
            'warnings_list': [],
            'passed_validations': []
        }
        
        # Validate EBITDA multiple if present
        if 'ebitda_multiple' in valuation_data:
            results = self.validate_calculation(
                'ebitda_multiple_adjustment',
                valuation_data['ebitda_multiple']
            )
            self._aggregate_results(results, validation_report, 'multiples')
        
        # Validate size discount if present
        if 'size_discount' in valuation_data:
            results = self.validate_calculation(
                'size_discount',
                valuation_data['size_discount']
            )
            self._aggregate_results(results, validation_report, 'discounts')
        
        # Validate owner dependency if present
        if 'owner_dependency_discount' in valuation_data:
            results = self.validate_calculation(
                'owner_dependency_discount',
                valuation_data['owner_dependency_discount']
            )
            self._aggregate_results(results, validation_report, 'discounts')
        
        # Validate DCF parameters if present
        if 'dcf' in valuation_data:
            dcf_data = valuation_data['dcf']
            
            if 'terminal_growth_rate' in dcf_data:
                results = self.validate_calculation(
                    'dcf_terminal_growth',
                    dcf_data['terminal_growth_rate']
                )
                self._aggregate_results(results, validation_report, 'dcf')
            
            if 'wacc' in dcf_data:
                results = self.validate_calculation(
                    'dcf_wacc',
                    dcf_data['wacc']
                )
                self._aggregate_results(results, validation_report, 'dcf')
        
        # Validate valuation range if present
        if 'valuation_range' in valuation_data:
            range_data = valuation_data['valuation_range']
            if 'low' in range_data and 'high' in range_data and 'mid' in range_data:
                # Calculate range width
                mid = Decimal(str(range_data['mid']))
                low = Decimal(str(range_data['low']))
                high = Decimal(str(range_data['high']))
                
                if mid > 0:
                    range_width = ((high - low) / mid) / Decimal('2')
                    results = self.validate_calculation(
                        'valuation_range',
                        float(range_width)
                    )
                    self._aggregate_results(results, validation_report, 'range')
        
        # Calculate summary statistics
        validation_report['overall_status'] = 'PASSED' if validation_report['failed'] == 0 else 'FAILED'
        if validation_report['total_validations'] > 0:
            validation_report['pass_rate'] = validation_report['passed'] / validation_report['total_validations']
        else:
            validation_report['pass_rate'] = 1.0
        
        self.logger.info(
            f"Validation complete: {validation_report['passed']}/{validation_report['total_validations']} passed",
            extra={'failed': validation_report['failed'], 'warnings': validation_report['warnings']}
        )
        
        return validation_report
    
    def validate_from_provenance(
        self,
        tracker: CalculationProvenanceTracker
    ) -> Dict[str, Any]:
        """
        Validate calculations from provenance tracker
        
        Args:
            tracker: Calculation provenance tracker with recorded calculations
            
        Returns:
            Validation report
        """
        self.logger.info(f"Validating from provenance tracker: {tracker.valuation_id}")
        
        validation_report = {
            'valuation_id': tracker.valuation_id,
            'timestamp': datetime.now().isoformat(),
            'total_validations': 0,
            'passed': 0,
            'failed': 0,
            'warnings': 0,
            'validations_by_calculation': {},
            'critical_issues': [],
            'warnings_list': []
        }
        
        # Validate each recorded calculation
        for record in tracker.get_all_records():
            # Extract value from outputs
            output_values = record.outputs
            
            # Try to find main output value
            value_to_validate = None
            if 'result' in output_values:
                value_to_validate = output_values['result']
            elif 'value' in output_values:
                value_to_validate = output_values['value']
            elif len(output_values) == 1:
                value_to_validate = list(output_values.values())[0]
            
            if value_to_validate is not None:
                results = self.validate_calculation(
                    record.calculation_id,
                    value_to_validate,
                    context=record.inputs
                )
                
                # Aggregate results
                calc_key = record.calculation_id
                if calc_key not in validation_report['validations_by_calculation']:
                    validation_report['validations_by_calculation'][calc_key] = {
                        'total': 0,
                        'passed': 0,
                        'failed': 0,
                        'warnings': 0
                    }
                
                for result in results:
                    validation_report['total_validations'] += 1
                    validation_report['validations_by_calculation'][calc_key]['total'] += 1
                    
                    if result.passed:
                        validation_report['passed'] += 1
                        validation_report['validations_by_calculation'][calc_key]['passed'] += 1
                    else:
                        validation_report['failed'] += 1
                        validation_report['validations_by_calculation'][calc_key]['failed'] += 1
                        validation_report['critical_issues'].extend(result.errors)
                    
                    if result.warnings:
                        validation_report['warnings'] += len(result.warnings)
                        validation_report['validations_by_calculation'][calc_key]['warnings'] += len(result.warnings)
                        validation_report['warnings_list'].extend(result.warnings)
        
        # Calculate summary
        validation_report['overall_status'] = 'PASSED' if validation_report['failed'] == 0 else 'FAILED'
        if validation_report['total_validations'] > 0:
            validation_report['pass_rate'] = validation_report['passed'] / validation_report['total_validations']
        else:
            validation_report['pass_rate'] = 1.0
        
        return validation_report
    
    def _aggregate_results(
        self,
        results: List[ValidationResult],
        report: Dict[str, Any],
        category: str
    ):
        """Aggregate validation results into report"""
        if category not in report['validations_by_category']:
            report['validations_by_category'][category] = {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'warnings': 0
            }
        
        for result in results:
            report['total_validations'] += 1
            report['validations_by_category'][category]['total'] += 1
            
            if result.passed:
                report['passed'] += 1
                report['validations_by_category'][category]['passed'] += 1
                report['passed_validations'].append({
                    'calculation_id': result.calculation_id,
                    'rule_id': result.rule_id,
                    'category': category
                })
            else:
                report['failed'] += 1
                report['validations_by_category'][category]['failed'] += 1
                report['critical_issues'].extend(result.errors)
            
            if result.warnings:
                report['warnings'] += len(result.warnings)
                report['validations_by_category'][category]['warnings'] += len(result.warnings)
                report['warnings_list'].extend(result.warnings)
    
    def get_all_validation_results(self) -> List[ValidationResult]:
        """Get all validation results"""
        with self._results_lock:
            return list(self.validation_results)
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of all validations performed"""
        with self._results_lock:
            results = list(self.validation_results)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        warnings = sum(len(r.warnings) for r in results)
        
        return {
            'total_validations': total,
            'passed': passed,
            'failed': failed,
            'warnings': warnings,
            'pass_rate': passed / total if total > 0 else 1.0
        }


# Global singleton instance
_validation_engine: Optional[AcademicValidationEngine] = None
_validation_engine_lock = Lock()


def get_validation_engine() -> AcademicValidationEngine:
    """Get or create the thread-safe singleton validation engine."""
    global _validation_engine
    if _validation_engine is None:
        with _validation_engine_lock:
            if _validation_engine is None:
                _validation_engine = AcademicValidationEngine()
    return _validation_engine
