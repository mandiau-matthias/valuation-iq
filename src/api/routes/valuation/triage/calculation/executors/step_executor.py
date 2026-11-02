"""
Step Executor

Handles execution of individual calculation steps with triage logic, dependency checking,
error handling, and result sanitization.
"""

from __future__ import annotations

import time

from src.api.routes.valuation.steps.base_step import CalculationStep, StepOutput
from src.api.schemas import ValuationRequest
from src.utils.exceptions import CalculationError, DataQualityError, DomainError, ValidationError

from ...business_type_triage import BusinessTypeTriageEngine
from ..handlers.fallback_handler import FallbackHandler
from ..utils.result_sanitizer import ResultSanitizer
from ..utils.value_chain_logger import ValueChainLogger
from .coordinators import (
    StepErrorHandlingCoordinator,
    StepExecutionCoordinator,
    StepResultSanitizationCoordinator,
    StepResultValidationCoordinator,
)
from .step_execution_diagnostics import (
    assign_execution_time,
    log_optional_dependency_status,
    log_pre_storage_snapshot,
    log_step_completion,
    log_step_entry,
    preserve_step_2_result_before_return,
)


class StepExecutor:
    """
    Executor for individual calculation step execution.

    Responsibilities:
    - Execute single steps with dependency checking
    - Apply triage decision logic
    - Handle errors and recovery
    - Sanitize results
    - Provide diagnostic logging
    """

    def __init__(
        self,
        logger_instance,
        business_type_triage: BusinessTypeTriageEngine,
        result_sanitizer: ResultSanitizer,
        value_chain_logger: ValueChainLogger,
        fallback_handler: FallbackHandler,
    ):
        """
        Initialize StepExecutor.

        Args:
            logger_instance: Logger instance
            business_type_triage: Business type triage engine
            result_sanitizer: Result sanitizer utility
            value_chain_logger: Value chain logger utility
            fallback_handler: Fallback handler
        """
        self.logger = logger_instance
        self.business_type_triage = business_type_triage
        self.result_sanitizer = result_sanitizer
        self.value_chain_logger = value_chain_logger
        self.fallback_handler = fallback_handler

        # Initialize coordinators
        from .dependency_checker import DependencyChecker
        from .triage_decision_engine import TriageDecisionEngine

        dependency_checker = DependencyChecker(logger_instance)
        triage_engine = TriageDecisionEngine(logger_instance, business_type_triage)

        self.execution_coordinator = StepExecutionCoordinator(
            dependency_checker,
            triage_engine,
            business_type_triage,
            result_sanitizer,
            logger_instance,
        )
        self.validation_coordinator = StepResultValidationCoordinator(logger_instance)
        self.sanitization_coordinator = StepResultSanitizationCoordinator(logger_instance)
        self.error_coordinator = StepErrorHandlingCoordinator(
            logger_instance, business_type_triage, fallback_handler
        )

    async def execute(
        self,
        step: CalculationStep,
        request: ValuationRequest,
        previous_results: dict[int, StepOutput],
        context: dict[str, object],
    ) -> StepOutput:
        """
        Execute a single calculation step with triage logic.

        Args:
            step: The step to execute
            request: The valuation request
            previous_results: Results from previous steps
            context: Additional context

        Returns:
            StepOutput with results or skip/failure status
        """
        step_start = time.time()
        log_step_entry(self.logger, step, request, previous_results, context)

        try:
            output = await self.execution_coordinator.execute_step(
                step, request, previous_results, context
            )
            log_pre_storage_snapshot(self.logger, step, output)
            assign_execution_time(output, step_start, time.time())
            log_optional_dependency_status(self.logger, step, output, previous_results)
            log_step_completion(
                self.logger,
                self.result_sanitizer,
                self.value_chain_logger,
                self.business_type_triage,
                step,
                request,
                previous_results,
                context,
                output,
            )
            output = self.validation_coordinator.validate_step_result(step, output, context)
            output = self.sanitization_coordinator.sanitize_step_result(step, output, context)
            return preserve_step_2_result_before_return(self.logger, step, output, context)

        except (
            CalculationError,
            ValidationError,
            DataQualityError,
            DomainError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
        ) as e:
            # Handle error using StepErrorHandlingCoordinator
            return self.error_coordinator.handle_step_error(
                step, request, previous_results, context, e, step_start
            )
