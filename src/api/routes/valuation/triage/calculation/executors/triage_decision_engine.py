"""
Triage Decision Engine Module

RESPONSIBILITIES:
- Determine if a step should execute based on multi-layer triage logic
- Handle Step 11 special case (must always execute)
- Apply business-type-aware triage rules

REFACTORING NOTE:
Extracted from step_executor.py to improve maintainability and reduce file size.
"""

from typing import Any, Dict, Optional

from src.api.routes.valuation.steps.base_step import (
    CalculationStep,
    StepInput,
    StepOutput,
    StepStatus,
)
from src.api.schemas import ValuationRequest
from src.errors import ConfigurationError, ValidationError

from ...business_type_triage import BusinessTypeTriageEngine


class TriageDecisionEngine:
    """
    Handles triage decision logic for calculation steps
    """

    def __init__(self, logger, business_type_triage: BusinessTypeTriageEngine):
        """
        Initialize triage decision engine

        Args:
            logger: Logger instance
            business_type_triage: Business type triage engine
        """
        self.logger = logger
        self.business_type_triage = business_type_triage

    def should_execute_step(
        self,
        step: CalculationStep,
        input_data: StepInput,
        request: ValuationRequest,
        previous_results: Dict[int, StepOutput],
        context: Dict[str, Any],
    ) -> tuple[bool, Optional[StepOutput]]:
        """
        Determine if step should execute using multi-layer triage logic

        Args:
            step: The calculation step
            input_data: Step input data
            request: Valuation request
            previous_results: Results from previous steps
            context: Additional context

        Returns:
            Tuple of (should_execute, skip_output)
            - should_execute: True if step should execute, False if should skip
            - skip_output: StepOutput if skipped, None if should execute
        """
        # CRITICAL: Step 11 must always execute (bypass all triage checks)
        is_step11 = step.step_number == 11

        if is_step11:
            return True, None

        # Layer 1: Check step's own should_execute logic
        layer1_result = self._check_step_logic(step, input_data, context)
        if layer1_result is not None:
            return False, layer1_result

        # Layer 2: Check business-type-aware triage logic
        layer2_result = self._check_business_type_triage(step, request, previous_results, context)
        if layer2_result is not None:
            return False, layer2_result

        # All checks passed - step should execute
        return True, None

    def _check_step_logic(
        self, step: CalculationStep, input_data: StepInput, context: Dict[str, Any]
    ) -> Optional[StepOutput]:
        """
        Layer 1: Check step's own should_execute logic

        Args:
            step: The calculation step
            input_data: Step input data
            context: Additional context

        Returns:
            StepOutput if step should be skipped, None if should execute
        """
        step_should_execute = step.should_execute(input_data)

        # Log the decision
        if step_should_execute:
            self.logger.debug(
                f"🔍 DIAGNOSTIC Step {step.step_number} should_execute check",
                extra={
                    "step_number": step.step_number,
                    "step_name": step.step_name,
                    "should_execute": step_should_execute,
                    "correlation_id": context.get("correlation_id"),
                },
            )
        else:
            self.logger.debug(
                f"⏭️ Step {step.step_number} should_execute returned False",
                extra={
                    "step_number": step.step_number,
                    "step_name": step.step_name,
                    "should_execute": step_should_execute,
                    "correlation_id": context.get("correlation_id"),
                },
            )

        if not step_should_execute:
            # Step 2 is foundational; other skips are often expected
            # eligibility outcomes (e.g. Step 4.5 without history, Step 8 on
            # a 100% sale) and should not pollute warning feeds.
            log_func = self.logger.warning if step.step_number == 2 else self.logger.info
            log_func(
                f"⏭️  Step {step.step_number} skipped by step logic",
                extra={
                    "step_name": step.step_name,
                    "step_number": step.step_number,
                    "correlation_id": (
                        context.get("correlation_id") if step.step_number == 2 else None
                    ),
                },
            )
            return StepOutput(
                step_number=step.step_number,
                step_name=step.step_name,
                status=StepStatus.SKIPPED,
                result={},
                metadata={"reason": "Step should_execute returned False"},
            )

        return None

    def _check_business_type_triage(
        self,
        step: CalculationStep,
        request: ValuationRequest,
        previous_results: Dict[int, StepOutput],
        context: Dict[str, Any],
    ) -> Optional[StepOutput]:
        """
        Layer 2: Check business-type-aware triage logic

        Args:
            step: The calculation step
            request: Valuation request
            previous_results: Results from previous steps
            context: Additional context

        Returns:
            StepOutput if step should be skipped, None if should execute
        """
        try:
            execution_rule = self.business_type_triage.get_step_execution_rule(
                step.step_number, request
            )

            business_category = self.business_type_triage.get_business_type_category(
                getattr(request, "business_type_id", None),
                getattr(request, "business_model", None),
                getattr(request, "industry", None),
                category_id=getattr(request, "category_id", None),
            )

            should_execute = self.business_type_triage.should_execute_step(
                step.step_number, request, previous_results, execution_rule
            )

            if not should_execute:
                # Enhanced logging for Step 2 business-type triage skip
                log_level = self.logger.error if step.step_number == 2 else self.logger.info
                log_level(
                    f"⏭️  Step {step.step_number} skipped by business-type triage",
                    extra={
                        "step_name": step.step_name,
                        "step_number": step.step_number,
                        "business_category": business_category.value,
                        "execution_rule": execution_rule.value,
                        "correlation_id": (
                            context.get("correlation_id") if step.step_number == 2 else None
                        ),
                    },
                )
                return StepOutput(
                    step_number=step.step_number,
                    step_name=step.step_name,
                    status=StepStatus.SKIPPED,
                    result={},
                    metadata={
                        "reason": "Business-type triage condition not met",
                        "business_category": business_category.value,
                        "execution_rule": execution_rule.value,
                    },
                )

        except (ValidationError, ConfigurationError, ValueError, TypeError, AttributeError) as e:
            # Fail-safe: if triage logic fails, log warning but allow execution
            self.logger.warning(
                f"⚠️  Business-type triage check failed for step {step.step_number}, allowing execution",
                extra={
                    "step_name": step.step_name,
                    "step_number": step.step_number,
                    "error": str(e),
                },
                exc_info=True,
            )
            # Continue with execution (fail-safe)

        return None
