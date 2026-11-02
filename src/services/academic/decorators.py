"""
Academic Provenance Decorators

Decorators for automatic tracking of academic provenance in calculations.

Usage:
    @track_academic_provenance(
        calculation_id="ebitda_multiple_adjustment",
        section_name="Valuation Methodology"
    )
    async def calculate_adjusted_multiple(self, context):
        # calculation logic
        return result

Author: Upswitch CTO Team
Date: December 2025
Status: Production Ready
"""

from functools import wraps
from typing import Any, Callable, Dict, Optional
from datetime import datetime
import inspect

from src.services.academic.calculation_provenance_tracker import get_current_tracker
from src.services.academic.academic_metadata_service import get_academic_metadata_service
from src.utils.logging import get_logger
from src.utils.exceptions import (
    ValuationEngineError,
    ExternalServiceError,
    DataValidationError,
    CalculationError,
)

logger = get_logger(__name__)


def track_academic_provenance(
    calculation_id: str,
    section_name: Optional[str] = None,
    step_number: Optional[int] = None,
    extract_inputs: Optional[Callable] = None,
    extract_outputs: Optional[Callable] = None
):
    """
    Decorator to automatically track academic provenance for calculations
    
    Args:
        calculation_id: ID of calculation (links to CalculationMetadata)
        section_name: Section name where calculation occurs
        step_number: Step number in valuation process
        extract_inputs: Optional function to extract inputs from args/kwargs
        extract_outputs: Optional function to extract outputs from result
    
    Example:
        @track_academic_provenance(
            calculation_id="ebitda_multiple_adjustment",
            section_name="Multiples Valuation",
            extract_inputs=lambda args, kwargs: {'base_multiple': args[1]},
            extract_outputs=lambda result: {'adjusted_multiple': result['multiple']}
        )
        async def calculate_adjusted_multiple(self, base_multiple):
            # calculation logic
            return {'multiple': adjusted_value}
    """
    def decorator(func: Callable) -> Callable:
        # Handle both async and sync functions
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await _execute_with_tracking(
                    func, args, kwargs, calculation_id, section_name, 
                    step_number, extract_inputs, extract_outputs, is_async=True
                )
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return _execute_with_tracking_sync(
                    func, args, kwargs, calculation_id, section_name,
                    step_number, extract_inputs, extract_outputs
                )
            return sync_wrapper
    
    return decorator


async def _execute_with_tracking(
    func: Callable,
    args: tuple,
    kwargs: dict,
    calculation_id: str,
    section_name: Optional[str],
    step_number: Optional[int],
    extract_inputs: Optional[Callable],
    extract_outputs: Optional[Callable],
    is_async: bool
) -> Any:
    """Execute async function with provenance tracking"""
    
    tracker = get_current_tracker()
    
    # If no tracker, just execute function normally
    if tracker is None:
        return await func(*args, **kwargs)
    
    # Extract inputs
    inputs = {}
    if extract_inputs:
        try:
            inputs = extract_inputs(args, kwargs)
        except (TypeError, AttributeError, KeyError, ValueError) as e:
            # Handle data extraction errors gracefully
            logger.warning(f"Failed to extract inputs for {calculation_id}: {e}")
        except ValuationEngineError:
            # Re-raise valuation engine errors
            raise
    
    # Execute function
    start_time = datetime.now()
    try:
        result = await func(*args, **kwargs)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Extract outputs
        outputs = {'execution_time_seconds': execution_time}
        if extract_outputs:
            try:
                extracted = extract_outputs(result)
                outputs.update(extracted)
            except (TypeError, AttributeError, KeyError, ValueError) as e:
                # Handle data extraction errors gracefully
                logger.warning(f"Failed to extract outputs for {calculation_id}: {e}")
            except ValuationEngineError:
                # Re-raise valuation engine errors
                raise
        
        # Record provenance
        tracker.record_calculation(
            calculation_id=calculation_id,
            inputs=inputs,
            outputs=outputs,
            section_name=section_name,
            step_number=step_number
        )
        
        return result
        
    except (CalculationError, DataValidationError, ExternalServiceError) as e:
        # Re-raise specific valuation errors after recording
        execution_time = (datetime.now() - start_time).total_seconds()
        tracker.record_calculation(
            calculation_id=calculation_id,
            inputs=inputs,
            outputs={
                'error': str(e),
                'error_type': type(e).__name__,
                'execution_time_seconds': execution_time,
                'success': False
            },
            section_name=section_name,
            step_number=step_number
        )
        raise
    except ValuationEngineError as e:
        # Re-raise all valuation engine errors
        execution_time = (datetime.now() - start_time).total_seconds()
        tracker.record_calculation(
            calculation_id=calculation_id,
            inputs=inputs,
            outputs={
                'error': str(e),
                'error_type': type(e).__name__,
                'execution_time_seconds': execution_time,
                'success': False
            },
            section_name=section_name,
            step_number=step_number
        )
        raise


def _execute_with_tracking_sync(
    func: Callable,
    args: tuple,
    kwargs: dict,
    calculation_id: str,
    section_name: Optional[str],
    step_number: Optional[int],
    extract_inputs: Optional[Callable],
    extract_outputs: Optional[Callable]
) -> Any:
    """Execute sync function with provenance tracking"""
    
    tracker = get_current_tracker()
    
    # If no tracker, just execute function normally
    if tracker is None:
        return func(*args, **kwargs)
    
    # Extract inputs
    inputs = {}
    if extract_inputs:
        try:
            inputs = extract_inputs(args, kwargs)
        except (TypeError, AttributeError, KeyError, ValueError) as e:
            # Handle data extraction errors gracefully
            logger.warning(f"Failed to extract inputs for {calculation_id}: {e}")
        except ValuationEngineError:
            # Re-raise valuation engine errors
            raise
    
    # Execute function
    start_time = datetime.now()
    try:
        result = func(*args, **kwargs)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Extract outputs
        outputs = {'execution_time_seconds': execution_time}
        if extract_outputs:
            try:
                extracted = extract_outputs(result)
                outputs.update(extracted)
            except (TypeError, AttributeError, KeyError, ValueError) as e:
                # Handle data extraction errors gracefully
                logger.warning(f"Failed to extract outputs for {calculation_id}: {e}")
            except ValuationEngineError:
                # Re-raise valuation engine errors
                raise
        
        # Record provenance
        tracker.record_calculation(
            calculation_id=calculation_id,
            inputs=inputs,
            outputs=outputs,
            section_name=section_name,
            step_number=step_number
        )
        
        return result
        
    except (CalculationError, DataValidationError, ExternalServiceError) as e:
        # Re-raise specific valuation errors after recording
        execution_time = (datetime.now() - start_time).total_seconds()
        tracker.record_calculation(
            calculation_id=calculation_id,
            inputs=inputs,
            outputs={
                'error': str(e),
                'error_type': type(e).__name__,
                'execution_time_seconds': execution_time,
                'success': False
            },
            section_name=section_name,
            step_number=step_number
        )
        raise
    except ValuationEngineError as e:
        # Re-raise all valuation engine errors
        execution_time = (datetime.now() - start_time).total_seconds()
        tracker.record_calculation(
            calculation_id=calculation_id,
            inputs=inputs,
            outputs={
                'error': str(e),
                'error_type': type(e).__name__,
                'execution_time_seconds': execution_time,
                'success': False
            },
            section_name=section_name,
            step_number=step_number
        )
        raise


def validate_against_academic_standards(
    calculation_id: str,
    value_extractor: Optional[Callable] = None
):
    """
    Decorator to validate calculation results against academic standards
    
    Args:
        calculation_id: ID of calculation to validate
        value_extractor: Function to extract value to validate from result
    
    Example:
        @validate_against_academic_standards(
            calculation_id="ebitda_multiple_adjustment",
            value_extractor=lambda result: result['multiple']
        )
        def calculate_multiple(base_multiple, adjustment):
            return {'multiple': base_multiple * (1 + adjustment)}
    """
    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)
                _validate_result(calculation_id, result, value_extractor)
                return result
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                _validate_result(calculation_id, result, value_extractor)
                return result
            return sync_wrapper
    
    return decorator


def _validate_result(
    calculation_id: str,
    result: Any,
    value_extractor: Optional[Callable]
):
    """Validate result against academic validation rules"""
    
    academic_service = get_academic_metadata_service()
    validation_rules = academic_service.get_validation_rules_for_calculation(calculation_id)
    
    if not validation_rules:
        return  # No validation rules defined
    
    # Extract value to validate
    if value_extractor:
        try:
            value = value_extractor(result)
        except (TypeError, AttributeError, KeyError, ValueError) as e:
            # Handle data extraction errors gracefully
            logger.warning(f"Failed to extract value for validation: {e}")
            return
        except ValuationEngineError:
            # Re-raise valuation engine errors
            raise
    else:
        value = result
    
    # Run validations
    for rule in validation_rules:
        validation_result = rule.validate(value)
        
        if not validation_result['passed']:
            logger.warning(
                f"Academic validation failed for {calculation_id}",
                extra={
                    'rule': rule.rule_name,
                    'errors': validation_result['errors'],
                    'value': value
                }
            )
        
        if validation_result['warnings']:
            logger.info(
                f"Academic validation warning for {calculation_id}",
                extra={
                    'rule': rule.rule_name,
                    'warnings': validation_result['warnings'],
                    'value': value
                }
            )


def track_methodology_selection(func: Callable) -> Callable:
    """
    Decorator specifically for methodology selection tracking
    
    Example:
        @track_methodology_selection
        async def select_methodology(business_context, financial_data):
            # selection logic
            return {'methodology': 'MULTIPLES', 'confidence': 0.85}
    """
    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            _record_methodology_selection(result)
            return result
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            _record_methodology_selection(result)
            return result
        return sync_wrapper


def _record_methodology_selection(result: Any):
    """Record methodology selection in provenance tracker"""
    tracker = get_current_tracker()
    if tracker and isinstance(result, dict):
        tracker.record_methodology_selection(
            methodology=result.get('methodology', 'UNKNOWN'),
            rationale=result.get('rationale', result.get('reasoning', '')),
            confidence_score=result.get('confidence', result.get('confidence_score', 0.5)),
            factors=result.get('factors', {})
        )

