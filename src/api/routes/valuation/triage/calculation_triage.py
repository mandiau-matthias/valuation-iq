"""
Main calculation triage orchestrator.

This module coordinates the execution of all 10 calculation steps with intelligent
routing based on data quality and company characteristics.

REFACTORED: Extracted executors, managers, handlers, and utilities into modular structure.
"""

import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.schemas import ValuationRequest

# Built-in exceptions don't need to be imported from src.errors
from src.errors import ConfigurationError, ValidationError
from src.utils.correlation import ensure_correlation_id
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

from .business_type_triage import BusinessTypeTriageEngine
from .calculation.executors.parallel_executor import ParallelExecutor
from .calculation.executors.sequential_executor import SequentialExecutor

# Import refactored modules
from .calculation.executors.step_executor import StepExecutor
from .calculation.handlers.fallback_handler import FallbackHandler
from .calculation.managers.dependency_manager import DependencyManager
from .calculation.managers.execution_orchestrator import ExecutionOrchestrator
from .calculation.utils.result_sanitizer import ResultSanitizer
from .calculation.utils.value_chain_logger import ValueChainLogger
from .step_registry import get_global_registry
from .triage_types import TriageDecision, TriageReason

logger = ValuationLogger(__name__)


class CalculationTriage:
    """
    Intelligent triage orchestrator for the modular step pipeline.

    This class coordinates the execution of all calculation steps, handling:
    - Step registration and discovery
    - Dependency management
    - Conditional execution based on triage logic
    - Error handling and recovery
    - Performance monitoring
    - Parallel execution of independent steps

    Architecture:
        The triage system acts as a coordinator between the ValuationOrchestrator
        and the individual calculation steps. It ensures steps execute in the
        correct order, handles failures gracefully, and optimizes performance.

    Concurrency:
        ``self.steps`` holds singleton step instances per process. ``execute_full_calculation``
        must not be invoked concurrently on the same ``CalculationTriage`` instance from
        overlapping tasks. Independent asyncio tasks each with their own triage (or
        serialized awaits) are safe.
    """

    def __init__(self):
        """Initialize the triage system and register all steps."""
        self.logger = logger
        self.steps: Dict[int, CalculationStep] = {}
        self.business_type_triage = BusinessTypeTriageEngine()

        # Initialize utility modules
        self.result_sanitizer = ResultSanitizer()
        self.value_chain_logger = ValueChainLogger()
        self.fallback_handler = FallbackHandler()

        # Initialize managers
        self.dependency_manager = DependencyManager()

        # Initialize executors (with dependencies)
        self.step_executor = StepExecutor(
            logger_instance=self.logger,
            business_type_triage=self.business_type_triage,
            result_sanitizer=self.result_sanitizer,
            value_chain_logger=self.value_chain_logger,
            fallback_handler=self.fallback_handler,
        )

        self.parallel_executor = ParallelExecutor(step_executor=self.step_executor)

        self.sequential_executor = SequentialExecutor(
            logger_instance=self.logger,
            business_type_triage=self.business_type_triage,
            step_executor=self.step_executor,
            fallback_handler=self.fallback_handler,
        )

        # Initialize orchestrator
        self.execution_orchestrator = ExecutionOrchestrator(
            logger_instance=self.logger,
            business_type_triage=self.business_type_triage,
            sequential_executor=self.sequential_executor,
            fallback_handler=self.fallback_handler,
        )

        self._register_steps()

        self.logger.debug(
            "🎯 CalculationTriage initialized", extra={"registered_steps": len(self.steps)}
        )

    def _register_steps(self) -> None:
        """
        Register all calculation steps from the registry.

        Steps are auto-discovered when their modules are imported.
        This method instantiates each registered step class.

        LOGGING: Logs every step registration with full details for traceability.
        """
        registry = get_global_registry()
        all_step_classes = registry.get_all_steps()

        self.logger.debug(
            "📋 Starting step registration process",
            extra={
                "total_steps_found": len(all_step_classes),
                "step_numbers": sorted(all_step_classes.keys()),
            },
        )

        registered_count = 0
        failed_count = 0

        for step_number, step_class in all_step_classes.items():
            try:
                self.steps[step_number] = step_class()
                registered_count += 1

                # Log successful registration with step details
                self.logger.debug(
                    f"✅ Registered Step {step_number}: {self.steps[step_number].step_name}",
                    extra={
                        "step_number": step_number,
                        "step_name": self.steps[step_number].step_name,
                        "dependencies": self.steps[step_number].dependencies,
                        "step_class": step_class.__name__,
                    },
                )
            except (
                ConfigurationError,
                ValidationError,
                ValueError,
                TypeError,
                AttributeError,
            ) as e:
                failed_count += 1
                self.logger.error(
                    f"❌ Failed to register step {step_number}: {e}",
                    extra={
                        "step_number": step_number,
                        "step_class": step_class.__name__ if step_class else "unknown",
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )

        # Log registration summary
        self.logger.debug(
            "📋 Step registration complete",
            extra={
                "total_steps": len(all_step_classes),
                "registered": registered_count,
                "failed": failed_count,
                "registered_step_numbers": sorted(self.steps.keys()),
                "registered_step_names": [s.step_name for s in self.steps.values()],
            },
        )

    async def execute_full_calculation(
        self, request: ValuationRequest, context: Optional[Dict[str, Any]] = None
    ) -> Dict[int, StepOutput]:
        """
        Execute the complete modular calculation pipeline with intelligent triage.

        Args:
            request: The valuation request containing financial data
            context: Additional context and configuration (may include 'correlation_id')

        Returns:
            Dictionary mapping step numbers to their outputs
        """
        # Delegate to ExecutionOrchestrator
        return await self.execution_orchestrator.execute_full_calculation(
            steps=self.steps, request=request, context=context
        )

    async def execute_parallel_steps(
        self,
        step_numbers: List[int],
        request: ValuationRequest,
        previous_results: Dict[int, StepOutput],
        context: Dict[str, Any],
    ) -> Dict[int, StepOutput]:
        """
        Execute multiple independent steps in parallel.

        This method can be used for steps that don't depend on each other,
        such as Steps 4, 5, and 6 (owner concentration, size discount, liquidity discount).

        Args:
            step_numbers: List of step numbers to execute in parallel
            request: The valuation request
            previous_results: Results from previous steps
            context: Additional context

        Returns:
            Dictionary mapping step numbers to their outputs
        """
        # Delegate to ParallelExecutor
        return await self.parallel_executor.execute_parallel_steps(
            steps=self.steps,
            step_numbers=step_numbers,
            request=request,
            previous_results=previous_results,
            context=context,
        )

    def get_triage_decision(self, request: ValuationRequest) -> TriageDecision:
        """
        Make a triage decision about which methodologies to use.

        This method analyzes the request and determines whether to use
        DCF, Multiples, or both methodologies based on data quality and
        company characteristics.

        Args:
            request: The valuation request

        Returns:
            TriageDecision with methodology recommendations
        """
        # This will be implemented by Step 0 (Data Quality Assessment)
        # For now, return a default decision
        return TriageDecision(
            use_dcf=False,
            use_multiples=True,
            multiples_primary=True,
            reason=TriageReason.ALWAYS_EXECUTE,
            data_quality_score=None,
        )
