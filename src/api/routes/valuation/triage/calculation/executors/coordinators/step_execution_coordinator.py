"""
Step Execution Coordinator

Handles core step execution logic: dependency checking, triage decision, and step execution.
Extracted from step_executor.py to improve modularity.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
"""

from typing import Any, Dict

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.schemas import ValuationRequest
from src.utils.valuation_logger import ValuationLogger

from ....business_type_triage import BusinessTypeTriageEngine
from ...utils.result_sanitizer import ResultSanitizer
from ..dependency_checker import DependencyChecker
from ..triage_decision_engine import TriageDecisionEngine

logger = ValuationLogger(__name__)


class StepExecutionCoordinator:
    """
    Coordinates core step execution logic.
    
    Responsibilities:
    - Dependency checking
    - Triage decision logic
    - Step execution
    - Input preparation
    """
    
    def __init__(
        self,
        dependency_checker: DependencyChecker,
        triage_engine: TriageDecisionEngine,
        business_type_triage: BusinessTypeTriageEngine,
        result_sanitizer: ResultSanitizer,
        logger_instance,
    ):
        """
        Initialize step execution coordinator.
        
        Args:
            dependency_checker: DependencyChecker instance
            triage_engine: TriageDecisionEngine instance
            business_type_triage: BusinessTypeTriageEngine instance
            result_sanitizer: ResultSanitizer instance
            logger_instance: Logger instance
        """
        self.dependency_checker = dependency_checker
        self.triage_engine = triage_engine
        self.business_type_triage = business_type_triage
        self.result_sanitizer = result_sanitizer
        self.logger = logger_instance
    
    async def execute_step(
        self,
        step: CalculationStep,
        request: ValuationRequest,
        previous_results: Dict[int, StepOutput],
        context: Dict[str, Any],
    ) -> StepOutput:
        """
        Execute a step with dependency checking and triage logic.
        
        Args:
            step: The step to execute
            request: The valuation request
            previous_results: Results from previous steps
            context: Additional context
            
        Returns:
            StepOutput with results or skip/failure status
        """
        # Create step input
        input_data = StepInput(
            request=request, previous_results=previous_results, context=context
        )
        
        # Check dependencies using DependencyChecker
        dependencies_met, can_execute_with_degraded = (
            self.dependency_checker.validate_dependencies(step, previous_results, context)
        )
        
        if not dependencies_met and not can_execute_with_degraded:
            # Log dependency failure
            self.dependency_checker.log_dependency_failure(step, previous_results, context)
            
            return StepOutput(
                step_number=step.step_number,
                step_name=step.step_name,
                status=StepStatus.SKIPPED,
                result={},
                metadata={
                    "reason": "Dependencies not met",
                    "required_dependencies": step.dependencies,
                },
            )
        
        # Triage decision: should this step execute?
        should_execute, skip_output = self.triage_engine.should_execute_step(
            step, input_data, request, previous_results, context
        )
        
        if not should_execute:
            return skip_output
        
        # Execute the step
        business_category = self.business_type_triage.get_business_type_category(
            getattr(request, "business_type_id", None),
            getattr(request, "business_model", None),
            getattr(request, "industry", None),
            category_id=getattr(request, "category_id", None),
        )
        
        # Log step input data (sanitized for privacy)
        input_summary = self.result_sanitizer.sanitize_input_for_logging(
            request, previous_results
        )
        
        self.logger.debug(
            f"▶️  Executing Step {step.step_number}: {step.step_name}",
            extra={
                "step_number": step.step_number,
                "step_name": step.step_name,
                "business_category": business_category.value,
                "company": request.company_name,
                "correlation_id": context.get("correlation_id"),
                "dependencies": step.dependencies,
                "available_previous_steps": list(previous_results.keys()),
                "input_summary": input_summary,
            },
        )
        
        # Log detailed input data at DEBUG level
        self.logger.debug(
            f"📥 Step {step.step_number} input data",
            extra={
                "step_number": step.step_number,
                "step_name": step.step_name,
                "request_data": self.result_sanitizer.sanitize_request_data(request),
                "previous_results_summary": self.result_sanitizer.summarize_previous_results(
                    previous_results
                ),
                "context_keys": list(context.keys()),
            },
        )
        
        # Execute the step
        output = await step.execute(input_data)
        
        return output

