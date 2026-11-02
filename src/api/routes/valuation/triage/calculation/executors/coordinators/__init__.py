"""
Step Execution Coordinators Package

This package contains coordinator classes that handle step execution,
following the Single Responsibility Principle.

Coordinators:
- FoundationStepCoordinator: Executes foundation steps (0-3)
- DiscountStepCoordinator: Executes discount steps (4-6) with cascading
- FinalStepCoordinator: Executes final steps (7-11)
- Step11FallbackCoordinator: Handles Step 11 fallback guarantee logic
- StepExecutionCoordinator: Handles core step execution (dependency checking, triage, execution)
- StepResultValidationCoordinator: Handles result validation (especially Step 2)
- StepResultSanitizationCoordinator: Handles result sanitization (NaN/Infinity handling)
- StepErrorHandlingCoordinator: Handles error handling for step execution
"""

from .foundation_step_coordinator import FoundationStepCoordinator
from .discount_step_coordinator import DiscountStepCoordinator
from .final_step_coordinator import FinalStepCoordinator
from .step11_fallback_coordinator import Step11FallbackCoordinator
from .step_execution_coordinator import StepExecutionCoordinator
from .step_result_validation_coordinator import StepResultValidationCoordinator
from .step_result_sanitization_coordinator import StepResultSanitizationCoordinator
from .step_error_handling_coordinator import StepErrorHandlingCoordinator

__all__ = [
    "FoundationStepCoordinator",
    "DiscountStepCoordinator",
    "FinalStepCoordinator",
    "Step11FallbackCoordinator",
    "StepExecutionCoordinator",
    "StepResultValidationCoordinator",
    "StepResultSanitizationCoordinator",
    "StepErrorHandlingCoordinator",
]

