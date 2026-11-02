"""
Dependency Checker Module

RESPONSIBILITIES:
- Validate step dependencies before execution
- Handle special cases (e.g., Step 2 degraded execution)
- Identify missing required dependencies

REFACTORING NOTE:
Extracted from step_executor.py to improve maintainability and reduce file size.
"""

from src.api.routes.valuation.steps.base_step import CalculationStep, StepOutput, StepStatus

from .degraded_dependency_policy import can_execute_with_degraded_dependencies


class DependencyChecker:
    """
    Handles dependency validation for calculation steps
    """

    def __init__(self, logger):
        """
        Initialize dependency checker

        Args:
            logger: Logger instance
        """
        self.logger = logger

    def check_degraded_execution(
        self,
        step: CalculationStep,
        previous_results: dict[int, StepOutput],
        context: dict[str, object],
    ) -> bool:
        """
        Check if step can execute with degraded dependencies

        Special handling:
        - Step 2: can execute if Step 1 is completed (Step 0 may have failed)
        - Steps 8-9: can execute if Step 7 failed but Step 6 EV is available as fallback

        Args:
            step: The calculation step
            previous_results: Results from previous steps
            context: Additional context

        Returns:
            True if can execute with degraded dependencies, False otherwise
        """
        return can_execute_with_degraded_dependencies(
            self.logger,
            step,
            previous_results,
            context,
        )

    def get_missing_dependencies(
        self, step: CalculationStep, previous_results: dict[int, StepOutput]
    ) -> list[int]:
        """
        Get list of missing required dependencies

        Args:
            step: The calculation step
            previous_results: Results from previous steps

        Returns:
            List of missing dependency step numbers
        """
        return [
            dep
            for dep in step.dependencies
            if dep not in previous_results or previous_results[dep].status != StepStatus.COMPLETED
        ]

    def validate_dependencies(
        self,
        step: CalculationStep,
        previous_results: dict[int, StepOutput],
        context: dict[str, object],
    ) -> tuple[bool, bool]:
        """
        Validate if step dependencies are met

        Args:
            step: The calculation step
            previous_results: Results from previous steps
            context: Additional context

        Returns:
            Tuple of (dependencies_met, can_execute_degraded)
        """
        # Check for degraded execution first
        can_execute_with_degraded = self.check_degraded_execution(step, previous_results, context)

        # Validate normal dependencies
        dependencies_met = step.validate_dependencies(previous_results)

        return dependencies_met, can_execute_with_degraded

    def log_dependency_failure(
        self,
        step: CalculationStep,
        previous_results: dict[int, StepOutput],
        context: dict[str, object],
    ):
        """
        Log dependency validation failure with appropriate detail

        Args:
            step: The calculation step
            previous_results: Results from previous steps
            context: Additional context
        """
        missing_deps = self.get_missing_dependencies(step, previous_results)

        # Enhanced logging for Step 2 dependency failures
        if step.step_number == 2:
            self.logger.error(
                "❌ CRITICAL: Step 2 cannot execute - dependencies not met",
                extra={
                    "step_name": step.step_name,
                    "step_number": 2,
                    "required_dependencies": step.dependencies,
                    "available_steps": list(previous_results.keys()),
                    "missing_required": missing_deps,
                    "step_0_status": (
                        previous_results[0].status.value
                        if 0 in previous_results and hasattr(previous_results[0], "status")
                        else "missing"
                    ),
                    "step_1_status": (
                        previous_results[1].status.value
                        if 1 in previous_results and hasattr(previous_results[1], "status")
                        else "missing"
                    ),
                    "correlation_id": context.get("correlation_id"),
                },
            )

        # General logging for all steps
        self.logger.error(
            f"❌ Step {step.step_number} cannot execute: required dependencies not met",
            extra={
                "step_name": step.step_name,
                "step_number": step.step_number,
                "required_dependencies": step.dependencies,
                "available_steps": list(previous_results.keys()),
                "missing_required": missing_deps,
            },
        )
