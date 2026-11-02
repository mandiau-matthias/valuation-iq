"""
Parallel Executor

Handles parallel execution of independent calculation steps.
"""

import asyncio
from typing import Any, Dict, List

from src.api.routes.valuation.steps.base_step import CalculationStep, StepOutput, StepStatus
from src.api.schemas import ValuationRequest
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)


class ParallelExecutor:
    """
    Executor for parallel step execution.

    Responsibilities:
    - Execute multiple independent steps in parallel
    - Handle task coordination and error handling
    """

    def __init__(self, step_executor):
        """
        Initialize ParallelExecutor.

        Args:
            step_executor: StepExecutor instance for executing individual steps
        """
        self.logger = logger
        self.step_executor = step_executor

    async def execute_parallel_steps(
        self,
        steps: Dict[int, CalculationStep],
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
            steps: Dictionary of all registered steps
            step_numbers: List of step numbers to execute in parallel
            request: The valuation request
            previous_results: Results from previous steps
            context: Additional context

        Returns:
            Dictionary mapping step numbers to their outputs
        """
        self.logger.info(
            f"🔀 Executing steps in parallel: {step_numbers}",
            extra={"parallel_steps": step_numbers},
        )

        # Create tasks for each step
        tasks = []
        for step_num in step_numbers:
            step = steps.get(step_num)
            if step:
                task = self.step_executor.execute(step, request, previous_results, context)
                tasks.append((step_num, task))

        # Execute all tasks in parallel
        results = {}
        if tasks:
            task_results = await asyncio.gather(
                *[task for _, task in tasks], return_exceptions=True
            )

            for (step_num, _), result in zip(tasks, task_results):
                if isinstance(result, Exception):
                    self.logger.error(
                        f"Parallel step {step_num} raised exception: {result}",
                        extra={
                            "step_number": step_num,
                            "step_name": (
                                steps[step_num].step_name if step_num in steps else "unknown"
                            ),
                            "error": str(result),
                            "error_type": type(result).__name__,
                        },
                        exc_info=True,
                    )
                    results[step_num] = StepOutput(
                        step_number=step_num,
                        step_name=(
                            steps[step_num].step_name if step_num in steps else f"Step {step_num}"
                        ),
                        status=StepStatus.FAILED,
                        result={},
                        error=str(result),
                        metadata={"error_type": type(result).__name__},
                    )
                else:
                    results[step_num] = result

                    # Log individual step completion
                    if result.status == StepStatus.COMPLETED:
                        self.logger.debug(
                            f"✓ Parallel step {step_num} completed",
                            extra={
                                "step_number": step_num,
                                "step_name": result.step_name,
                                "status": result.status.value,
                            },
                        )
                    elif result.status == StepStatus.SKIPPED:
                        self.logger.debug(
                            f"⏭️  Parallel step {step_num} skipped",
                            extra={
                                "step_number": step_num,
                                "step_name": result.step_name,
                                "reason": result.metadata.get("reason", "unknown"),
                            },
                        )

        return results
