"""
Dependency Manager

Handles dependency resolution and execution eligibility checking for calculation steps.
"""

from decimal import Decimal
from typing import Any, Dict, List

from src.api.routes.valuation.steps.base_step import CalculationStep, StepOutput, StepStatus
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)


class DependencyManager:
    """
    Manager for step dependency resolution.

    Responsibilities:
    - Check required dependencies
    - Check optional dependencies
    - Determine execution eligibility
    - Handle degraded execution scenarios
    """

    def __init__(self):
        """Initialize DependencyManager."""
        self.logger = logger

    def validate_dependencies(
        self, step: CalculationStep, previous_results: Dict[int, StepOutput]
    ) -> bool:
        """
        Validate that all required dependencies are met.

        Args:
            step: The calculation step
            previous_results: Results from previous steps

        Returns:
            True if all required dependencies are met, False otherwise
        """
        return step.validate_dependencies(previous_results)

    def can_execute_with_degraded(
        self, step: CalculationStep, previous_results: Dict[int, StepOutput]
    ) -> bool:
        """
        Check if step can execute with degraded dependencies.

        Some steps (like Step 2) can work with partial data.

        Args:
            step: The calculation step
            previous_results: Results from previous steps

        Returns:
            True if step can execute with degraded dependencies
        """
        # Special handling for Step 2 - allow execution with degraded dependencies
        # Step 2 can work with partial data (especially database multiples don't require Step 0)
        if step.step_number == 2:
            # Step 2 can execute if:
            # 1. Step 1 is completed (required for input validation)
            # 2. Step 0 may have failed, but we can use fallback quality score
            step_1_completed = (
                1 in previous_results
                and hasattr(previous_results[1], "status")
                and previous_results[1].status == StepStatus.COMPLETED
            )
            step_0_exists = 0 in previous_results

            return step_1_completed and step_0_exists

        return False

    def get_missing_dependencies(
        self, step: CalculationStep, previous_results: Dict[int, StepOutput]
    ) -> List[int]:
        """
        Get list of missing required dependencies.

        Args:
            step: The calculation step
            previous_results: Results from previous steps

        Returns:
            List of missing dependency step numbers
        """
        missing = []
        for dep in step.dependencies:
            if dep not in previous_results or previous_results[dep].status != StepStatus.COMPLETED:
                missing.append(dep)
        return missing

    def get_available_optional_dependencies(
        self, step: CalculationStep, previous_results: Dict[int, StepOutput]
    ) -> List[int]:
        """
        Get list of available optional dependencies.

        Args:
            step: The calculation step
            previous_results: Results from previous steps

        Returns:
            List of available optional dependency step numbers
        """
        if not step.optional_dependencies:
            return []

        available = []
        for dep in step.optional_dependencies:
            if dep in previous_results and previous_results[dep].status == StepStatus.COMPLETED:
                available.append(dep)
        return available

    def get_missing_optional_dependencies(
        self, step: CalculationStep, previous_results: Dict[int, StepOutput]
    ) -> List[int]:
        """
        Get list of missing optional dependencies.

        Args:
            step: The calculation step
            previous_results: Results from previous steps

        Returns:
            List of missing optional dependency step numbers
        """
        if not step.optional_dependencies:
            return []

        missing = []
        for dep in step.optional_dependencies:
            if dep not in previous_results or previous_results[dep].status != StepStatus.COMPLETED:
                missing.append(dep)
        return missing
