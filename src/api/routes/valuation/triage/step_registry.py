"""
Step registry for auto-discovery and registration of calculation steps.

UPDATED 2025-12-20: Support for decimal step numbers (e.g., 4.5) to allow
intermediate steps between major calculation steps.
"""

from typing import Dict, Type, Union

from src.api.routes.valuation.steps.base_step import CalculationStep


class StepRegistry:
    """
    Registry for calculation steps.

    This class handles registration and discovery of all calculation steps.
    Steps are registered automatically when imported.
    
    UPDATED 2025-12-20: Supports both integer and float step numbers to allow
    for intermediate steps (e.g., Step 4.5: Revenue Trend Adjustment).
    """

    def __init__(self):
        # Support both int and float step numbers (e.g., 4, 4.5, 5)
        self._steps: Dict[Union[int, float], Type[CalculationStep]] = {}

    def register(self, step_class: Type[CalculationStep]) -> None:
        """
        Register a step class.

        Args:
            step_class: The step class to register
        """
        # Create a temporary instance to get step number
        temp_instance = step_class()
        step_number = temp_instance.step_number

        if step_number in self._steps:
            existing = self._steps[step_number]
            # Allow re-registration if it's the same class (handles import conflicts)
            if existing is step_class or existing.__name__ == step_class.__name__:
                return  # Already registered, skip
            raise ValueError(f"Step {step_number} already registered by {existing.__name__}")

        self._steps[step_number] = step_class

    def get_step(self, step_number: Union[int, float]) -> Type[CalculationStep]:
        """
        Get a step class by number.

        Args:
            step_number: The step number to retrieve (int or float, e.g., 4 or 4.5)

        Returns:
            The step class

        Raises:
            KeyError: If step number not registered
        """
        if step_number not in self._steps:
            raise KeyError(f"Step {step_number} not registered")
        return self._steps[step_number]

    def get_all_steps(self) -> Dict[Union[int, float], Type[CalculationStep]]:
        """
        Get all registered steps.

        Returns:
            Dictionary mapping step numbers (int or float) to step classes
        """
        return self._steps.copy()

    def is_registered(self, step_number: Union[int, float]) -> bool:
        """
        Check if a step number is registered.

        Args:
            step_number: The step number to check (int or float)

        Returns:
            True if registered, False otherwise
        """
        return step_number in self._steps


# Global registry instance: mutated only from @register_step during step module imports,
# then treated as read-only while serving requests (no per-request registration).
_global_registry = StepRegistry()


def register_step(step_class: Type[CalculationStep]) -> Type[CalculationStep]:
    """
    Decorator to register a step class.

    Usage:
        @register_step
        class Step1Example(CalculationStep):
            ...

    Args:
        step_class: The step class to register

    Returns:
        The same step class (for chaining)
    """
    _global_registry.register(step_class)
    return step_class


def get_global_registry() -> StepRegistry:
    """Get the global step registry."""
    return _global_registry
