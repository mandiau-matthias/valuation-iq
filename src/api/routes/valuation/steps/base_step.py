"""
Base classes and types for the modular calculation step system.

This module defines the abstract base class and data structures used by all
calculation steps in the modular valuation pipeline.
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from src.api.schemas import ValuationRequest
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StepStatus(Enum):
    """Status of a calculation step"""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class StepInput:
    """Input data for a calculation step

    Attributes:
        request: The valuation request containing financial data
        previous_results: Results from all previous steps (indexed by step number)
        context: Additional context and configuration data
        step_number: Optional step number for diagnostic/logging purposes
    """

    request: ValuationRequest
    previous_results: Dict[int, "StepOutput"]
    context: Dict[str, Any] = field(default_factory=dict)
    step_number: Optional[int] = None


@dataclass
class StepOutput:
    """Output data from a calculation step

    Attributes:
        step_number: The step number (0-10)
        step_name: Human-readable name of the step
        status: Current status of the step
        result: The calculation results from this step
        metadata: Additional metadata about the calculation
        error: Error message if the step failed
        execution_time_ms: Time taken to execute the step in milliseconds
    """

    step_number: int
    step_name: str
    status: StepStatus
    result: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: Decimal = Decimal("0.0")

    def __post_init__(self):
        if isinstance(self.status, str):
            try:
                self.status = StepStatus(self.status)
            except ValueError:
                self.status = StepStatus.FAILED


class CalculationStep(ABC):
    """
    Abstract base class for all calculation steps.

    Each step in the modular valuation pipeline inherits from this class and
    implements the required abstract methods.

    The step system follows these principles:
    1. Single Responsibility: Each step does one thing well
    2. Dependency Injection: Steps receive all needed data via StepInput
    3. Conditional Execution: Steps can be skipped based on triage logic
    4. Transparency: Each step returns detailed results and metadata
    5. Testability: Steps can be unit tested independently

    Concurrency:
        Step instances are reused for the lifetime of a ``CalculationTriage``. Do not
        store per-request data on ``self`` for use on a later ``execute`` call; pass
        everything through ``StepInput`` (``request``, ``context``, ``previous_results``).
        Shared collaborators (validators, clients) must themselves be safe for the
        execution model (typically one valuation at a time per triage instance).
    """

    @property
    @abstractmethod
    def step_number(self) -> int:
        """Return the step number (0-10)"""
        pass

    @property
    @abstractmethod
    def step_name(self) -> str:
        """Return human-readable step name"""
        pass

    @property
    @abstractmethod
    def dependencies(self) -> List[int]:
        """
        Return list of step numbers that must complete before this step.

        These are REQUIRED dependencies - the step will not execute if any are missing.

        Returns:
            List of step numbers (e.g., [2, 3] means steps 2 and 3 must complete first)
        """
        pass

    @property
    def optional_dependencies(self) -> List[int]:
        """
        Return list of optional step numbers that enhance this step if available.

        These are OPTIONAL dependencies - the step will execute even if they're missing,
        but may produce degraded results.

        Returns:
            List of optional step numbers (empty list by default)
        """
        return []

    @abstractmethod
    def should_execute(self, input_data: StepInput) -> bool:
        """
        Determine if this step should execute based on triage logic.

        Args:
            input_data: Input data including request and previous results

        Returns:
            True if step should execute, False to skip
        """
        pass

    @abstractmethod
    async def execute(self, input_data: StepInput) -> StepOutput:
        """
        Execute the calculation step.

        Args:
            input_data: Input data including request and previous results

        Returns:
            StepOutput with results, metadata, and status
        """
        pass

    def validate_dependencies(self, previous_results: Dict[int, StepOutput]) -> bool:
        """
        Check if all required dependencies have been satisfied.

        This only checks REQUIRED dependencies (from self.dependencies).
        Optional dependencies are not checked here.

        Args:
            previous_results: Results from all previous steps

        Returns:
            True if all required dependencies are met, False otherwise
        """
        for dep in self.dependencies:
            if dep not in previous_results:
                return False
            if previous_results[dep].status != StepStatus.COMPLETED:
                return False
        return True

    def get_available_optional_dependencies(
        self, previous_results: Dict[int, StepOutput]
    ) -> List[int]:
        """
        Get list of optional dependencies that are available and completed.

        Args:
            previous_results: Results from all previous steps

        Returns:
            List of optional dependency step numbers that are available
        """
        available = []
        for dep in self.optional_dependencies:
            if dep in previous_results and previous_results[dep].status == StepStatus.COMPLETED:
                available.append(dep)
        return available

    def get_missing_optional_dependencies(
        self, previous_results: Dict[int, StepOutput]
    ) -> List[int]:
        """
        Get list of optional dependencies that are missing or not completed.

        Args:
            previous_results: Results from all previous steps

        Returns:
            List of optional dependency step numbers that are missing
        """
        missing = []
        for dep in self.optional_dependencies:
            if dep not in previous_results or previous_results[dep].status != StepStatus.COMPLETED:
                missing.append(dep)
        return missing

    def get_dependency_info(self, previous_results: Dict[int, StepOutput]) -> Dict[str, Any]:
        """
        Get comprehensive information about dependency status.

        Args:
            previous_results: Results from all previous steps

        Returns:
            Dictionary with dependency information
        """
        return {
            "required_dependencies": self.dependencies,
            "optional_dependencies": self.optional_dependencies,
            "required_satisfied": self.validate_dependencies(previous_results),
            "available_optional": self.get_available_optional_dependencies(previous_results),
            "missing_optional": self.get_missing_optional_dependencies(previous_results),
            "all_available_steps": list(previous_results.keys()),
        }

    def get_previous_step_result(
        self, step_number: int, previous_results: Dict[int, StepOutput]
    ) -> Optional[Dict[str, Any]]:
        """
        Helper method to safely get results from a previous step.

        Args:
            step_number: The step number to retrieve
            previous_results: All previous step results

        Returns:
            The result dictionary or None if step doesn't exist or failed
        """
        if step_number not in previous_results:
            return None

        step_output = previous_results[step_number]
        if step_output.status != StepStatus.COMPLETED:
            return None

        return step_output.result

    def sanitize_step_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize step result dictionary by replacing NaN/Infinity values with safe defaults.

        Args:
            result: Result dictionary that may contain NaN/Infinity values

        Returns:
            Sanitized result dictionary
        """

        def sanitize_value(value: Any, field_path: str = "") -> Any:
            """Recursively sanitize NaN/Infinity values"""
            if isinstance(value, Decimal):
                if value.is_nan() or value.is_infinite():
                    field_name = field_path.split(".")[-1] if "." in field_path else field_path
                    logger.warning(f"⚠️ Step {self.step_number}: Replacing Decimal NaN/Infinity in {field_path}")
                    return Decimal("0.0")
                return value

            if isinstance(value, (int, float)):
                if math.isnan(value) or math.isinf(value):
                    # Determine safe default based on field name
                    field_name = field_path.split(".")[-1] if "." in field_path else field_path
                    if (
                        "value" in field_name.lower()
                        or "equity" in field_name.lower()
                        or "enterprise" in field_name.lower()
                    ):
                        default = Decimal("0.0")
                    elif "multiple" in field_name.lower() or "ratio" in field_name.lower():
                        default = Decimal("1.0")
                    elif (
                        "percentage" in field_name.lower()
                        or "percent" in field_name.lower()
                        or "pct" in field_name.lower()
                    ):
                        default = Decimal("0.0")
                    elif "score" in field_name.lower() or "confidence" in field_name.lower():
                        default = Decimal("50.0")  # Default to medium confidence
                    else:
                        default = Decimal("0.0")

                    logger.warning(
                        f"⚠️ Step {self.step_number}: Replacing NaN/Infinity in {field_path} with default {default}",
                        extra={
                            "step_number": self.step_number,
                            "step_name": self.step_name,
                            "field_path": field_path,
                            "original_value": value,
                            "default": default,
                        },
                    )
                    return default
            elif isinstance(value, dict):
                return {
                    k: sanitize_value(v, f"{field_path}.{k}" if field_path else k)
                    for k, v in value.items()
                }
            elif isinstance(value, list):
                return [sanitize_value(item, f"{field_path}[{i}]") for i, item in enumerate(value)]
            return value

        sanitized = sanitize_value(result, "")
        return sanitized
