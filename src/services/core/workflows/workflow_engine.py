from src.utils.exceptions import APIError, ValuationTimeoutError

"""
Workflow Engine

This module handles workflow definition, execution, service coordination,
and parallel execution management for valuation processing.
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from src.utils.logging import get_logger
from ..orchestration.orchestrator_types import (
    WorkflowStep, ProcessingStatus, ValuationContext,
    ServiceDependency, SERVICE_DEPENDENCIES
)

logger = get_logger(__name__)


class WorkflowEngine:
    """
    Workflow execution engine for valuation processing

    Handles:
    - Workflow step execution
    - Dependency resolution
    - Parallel execution
    - Error handling and retries
    """

    def __init__(self):
        """Initialize the workflow engine"""
        self.logger = logger
        self.service_dependencies = {dep.service_name: dep for dep in SERVICE_DEPENDENCIES}
        self.active_workflows: Dict[str, List[WorkflowStep]] = {}

        self.logger.info("WorkflowEngine initialized")

    async def execute_workflow(
        self,
        workflow_steps: List[WorkflowStep],
        context: ValuationContext,
        step_handlers: Dict[str, Callable]
    ) -> Dict[str, Any]:
        """
        Execute a complete workflow

        Args:
            workflow_steps: List of workflow steps to execute
            context: Valuation context
            step_handlers: Dictionary of step handlers (step_id -> handler function)

        Returns:
            Dictionary of step results
        """
        try:
            self.logger.info(
                "Starting workflow execution",
                request_id=context.request_id,
                total_steps=len(workflow_steps)
            )

            # Store workflow
            self.active_workflows[context.request_id] = workflow_steps

            # Build dependency graph
            dependency_graph = self._build_dependency_graph(workflow_steps)

            # Execute steps based on dependencies
            results = await self._execute_steps_with_dependencies(
                workflow_steps,
                dependency_graph,
                step_handlers,
                context
            )

            self.logger.info(
                "Workflow execution completed",
                request_id=context.request_id,
                completed_steps=len([s for s in workflow_steps if s.status == ProcessingStatus.COMPLETED])
            )

            return results

        except APIError as e:
            self.logger.error(f"Workflow execution failed: {e}", request_id=context.request_id)
            raise
        finally:
            # Cleanup
            if context.request_id in self.active_workflows:
                del self.active_workflows[context.request_id]

    async def execute_parallel_tasks(
        self,
        tasks: List[Callable],
        context: ValuationContext,
        return_exceptions: bool = True
    ) -> List[Any]:
        """
        Execute multiple tasks in parallel

        Args:
            tasks: List of async tasks to execute
            context: Valuation context
            return_exceptions: Whether to return exceptions or raise them

        Returns:
            List of task results
        """
        try:
            self.logger.info(
                "Executing parallel tasks",
                request_id=context.request_id,
                task_count=len(tasks)
            )

            results = await asyncio.gather(*tasks, return_exceptions=return_exceptions)

            self.logger.info(
                "Parallel tasks completed",
                request_id=context.request_id,
                successful_tasks=len([r for r in results if not isinstance(r, Exception)])
            )

            return results

        except APIError as e:
            self.logger.error(f"Parallel task execution failed: {e}")
            raise

    def _build_dependency_graph(self, workflow_steps: List[WorkflowStep]) -> Dict[str, List[str]]:
        """Build dependency graph from workflow steps"""
        graph = {}
        for step in workflow_steps:
            graph[step.step_id] = step.dependencies
        return graph

    async def _execute_steps_with_dependencies(
        self,
        workflow_steps: List[WorkflowStep],
        dependency_graph: Dict[str, List[str]],
        step_handlers: Dict[str, Callable],
        context: ValuationContext
    ) -> Dict[str, Any]:
        """Execute steps respecting dependencies"""
        results = {}
        completed_steps = set()

        # Create step lookup
        step_lookup = {step.step_id: step for step in workflow_steps}

        while len(completed_steps) < len(workflow_steps):
            # Find steps ready to execute
            ready_steps = []
            for step in workflow_steps:
                if step.step_id not in completed_steps:
                    if all(dep in completed_steps for dep in step.dependencies):
                        ready_steps.append(step)

            if not ready_steps:
                # No more steps can be executed
                break

            # Execute ready steps in parallel
            tasks = []
            for step in ready_steps:
                if step.step_id in step_handlers:
                    tasks.append(self._execute_step(step, step_handlers[step.step_id], context))

            if tasks:
                step_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for i, step in enumerate(ready_steps):
                    result = step_results[i]
                    if isinstance(result, Exception):
                        step.status = ProcessingStatus.FAILED
                        step.error_message = str(result)
                        if step.critical:
                            raise result
                    else:
                        step.status = ProcessingStatus.COMPLETED
                        results[step.step_id] = result

                    completed_steps.add(step.step_id)

        return results

    async def _execute_step(
        self,
        step: WorkflowStep,
        handler: Callable,
        context: ValuationContext
    ) -> Any:
        """Execute a single workflow step"""
        step.start_time = datetime.utcnow()
        step.status = ProcessingStatus.IN_PROGRESS

        try:
            self.logger.info(f"Executing step: {step.step_name}", request_id=context.request_id)

            # Execute with timeout
            result = await asyncio.wait_for(
                handler(context),
                timeout=step.timeout_seconds
            )

            step.end_time = datetime.utcnow()
            step.status = ProcessingStatus.COMPLETED

            return result

        except asyncio.TimeoutError:
            step.status = ProcessingStatus.FAILED
            step.error_message = f"Step timed out after {step.timeout_seconds} seconds"
            self.logger.error(f"Step timeout: {step.step_name}")
            raise
        except ValuationTimeoutError as e:
            step.status = ProcessingStatus.FAILED
            step.error_message = str(e)
            self.logger.error(f"Step failed: {step.step_name} - {e}")

            if step.retryable:
                # Retry logic would go here
                pass

            raise

    def get_workflow_status(self, request_id: str) -> Optional[List[WorkflowStep]]:
        """Get current workflow status"""
        return self.active_workflows.get(request_id)
