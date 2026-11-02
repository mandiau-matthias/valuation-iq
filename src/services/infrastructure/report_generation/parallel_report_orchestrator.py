"""
Parallel Report Orchestrator

BANK-GRADE: Orchestrates parallel generation of multiple reports with independent
failure isolation, comprehensive error handling, and full audit trails.

DRY PRINCIPLE: Extracted from HTMLReportService.generate_both_reports() to reduce
complexity and improve maintainability.

ARCHITECTURE:
- Handles parallel execution of multiple report strategies
- Provides independent failure isolation per report
- Comprehensive error logging and diagnostics
- Graceful degradation when reports fail
"""

import asyncio
from typing import Dict, Optional, Any, TYPE_CHECKING
from decimal import Decimal

if TYPE_CHECKING:
    from src.api.schemas import ValuationResponse, ValuationRequest

from src.services.interfaces.request_response_protocol import (
    ValuationRequestProtocol,
    ValuationResponseProtocol,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ParallelReportOrchestrator:
    """
    BANK-GRADE: Orchestrates parallel generation of multiple reports.
    
    RESPONSIBILITIES:
    - Execute multiple report strategies in parallel
    - Handle independent failures for each report
    - Provide comprehensive error diagnostics
    - Return results with proper context
    
    DESIGN PATTERN: Orchestrator Pattern
    - Coordinates multiple strategies
    - Doesn't implement business logic
    - Focuses on parallel execution coordination
    """
    
    def __init__(self, logger_instance: Optional[Any] = None):
        """
        Initialize parallel report orchestrator.
        
        Args:
            logger_instance: Optional logger instance for dependency injection
        """
        self.logger = logger_instance or get_logger(__name__)
    
    async def execute_parallel(
        self,
        tasks: Dict[str, Any],
        context: Dict[str, Optional[str]],
        timeout: float = 60.0
    ) -> Dict[str, Optional[str]]:
        """
        Execute multiple report generation tasks in parallel.
        
        BANK-GRADE: Runs tasks concurrently with timeout protection and
        independent failure isolation.
        
        Args:
            tasks: Dictionary mapping result keys to async tasks/coroutines
                   Example: {'html_report': main_report_task}
            context: Context dictionary with company_name and correlation_id
            timeout: Timeout in seconds for all tasks (default: 60s)
            
        Returns:
            Dictionary mapping result keys to generated HTML strings (or None if failed)
            
        Example:
            orchestrator = ParallelReportOrchestrator()
            tasks = {
                'html_report': main_report_strategy.generate(...)
            }
            results = await orchestrator.execute_parallel(tasks, context)
            # results = {'html_report': '<html>...'}
        """
        self.logger.info(
            "Starting parallel report generation",
            extra={
                "company": context.get("company_name", "unknown"),
                "correlation_id": context.get("correlation_id"),
                "task_count": len(tasks),
                "task_keys": list(tasks.keys()),
                "timeout_seconds": timeout,
                "html_report_task_is_none": tasks.get('html_report') is None,
            }
        )
        
        # Validate all tasks are coroutines or None
        task_list = []
        task_keys = []
        for key, task in tasks.items():
            if task is None:
                self.logger.error(
                    f"❌ [PARALLEL-ORCHESTRATOR] Task '{key}' is None - cannot execute",
                    extra={
                        "company": context.get("company_name", "unknown"),
                        "correlation_id": context.get("correlation_id"),
                        "task_key": key,
                    }
                )
                # Create a coroutine that returns None
                async def _failed_task():
                    return None
                task_list.append(_failed_task())
            else:
                # CRITICAL: Validate task is a coroutine before adding to execution list
                is_coroutine = asyncio.iscoroutine(task)
                is_coroutine_function = asyncio.iscoroutinefunction(task) if callable(task) else False
                
                # DIAGNOSTIC: Log task details before adding to list
                self.logger.info(
                    f"🔍 [PARALLEL-ORCHESTRATOR] Adding task '{key}' to execution list",
                    extra={
                        "company": context.get("company_name", "unknown"),
                        "correlation_id": context.get("correlation_id"),
                        "task_key": key,
                        "task_type": type(task).__name__,
                        "is_coroutine": is_coroutine,
                        "is_coroutinefunction": is_coroutine_function,
                        "task_repr": repr(task)[:200] if task else "None",
                        "critical_note": "If not a coroutine, task will fail during execution" if not is_coroutine and not is_coroutine_function else None,
                    }
                )
                
                # CRITICAL: If task is not a coroutine and not a coroutine function, wrap it
                if not is_coroutine and not is_coroutine_function:
                    self.logger.error(
                        f"❌ [PARALLEL-ORCHESTRATOR] CRITICAL: Task '{key}' is not a coroutine - wrapping it",
                        extra={
                            "company": context.get("company_name", "unknown"),
                            "correlation_id": context.get("correlation_id"),
                            "task_key": key,
                            "task_type": type(task).__name__,
                            "impact": "Task may fail during execution if not properly wrapped",
                        }
                    )
                    # Try to wrap it as a coroutine
                    async def _wrapped_task(task=task, key=key):
                        try:
                            if callable(task):
                                return await task() if asyncio.iscoroutinefunction(task) else task()
                            return task
                        except Exception as e:
                            self.logger.error(
                                f"❌ [PARALLEL-ORCHESTRATOR] Wrapped task '{key}' raised exception",
                                extra={
                                    "company": context.get("company_name", "unknown"),
                                    "correlation_id": context.get("correlation_id"),
                                    "task_key": key,
                                    "error_type": type(e).__name__,
                                    "error_message": str(e),
                                },
                                exc_info=True
                            )
                            raise
                    task_list.append(_wrapped_task())
                else:
                    task_list.append(task)
            task_keys.append(key)
        
        # Execute all tasks in parallel with timeout
        try:
            self.logger.debug(
                "[PARALLEL-ORCHESTRATOR] Calling asyncio.gather()",
                extra={
                    "company": context.get("company_name", "unknown"),
                    "correlation_id": context.get("correlation_id"),
                    "task_count": len(task_list),
                }
            )
            
            # BANK-GRADE: Structured logging for parallel task execution
            self.logger.debug(
                "[PARALLEL-ORCHESTRATOR] About to execute parallel tasks",
                extra={
                    "task_count": len(task_list),
                    "tasks": [{"index": i, "type": type(task).__name__, "is_coroutine": asyncio.iscoroutine(task)} 
                             for i, task in enumerate(task_list)]
                }
            )
            
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*task_list, return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                raise
            except Exception as gather_error:
                raise

            self.logger.info(
                "Parallel execution complete",
                extra={
                    "company": context.get("company_name", "unknown"),
                    "correlation_id": context.get("correlation_id"),
                    "results_count": len(results),
                    "results": [
                        {
                            "index": i,
                            "is_exception": isinstance(result, Exception),
                            "is_none": result is None,
                            "type": type(result).__name__,
                            "length": len(result) if isinstance(result, str) else None
                        }
                        for i, result in enumerate(results)
                    ]
                }
            )

        except asyncio.TimeoutError:
            self.logger.error(
                f"❌ [PARALLEL-ORCHESTRATOR] Parallel execution timed out after {timeout}s",
                extra={
                    "company": context.get("company_name", "unknown"),
                    "correlation_id": context.get("correlation_id"),
                    "timeout_seconds": timeout,
                }
            )
            # Return None for all tasks on timeout
            return {key: None for key in task_keys}
        
        except Exception as e:
            self.logger.error(
                "❌ [PARALLEL-ORCHESTRATOR] Parallel execution failed",
                extra={
                    "company": context.get("company_name", "unknown"),
                    "correlation_id": context.get("correlation_id"),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True
            )
            # Return None for all tasks on error
            return {key: None for key in task_keys}
        
        processed_results = {}
        for i, (key, result) in enumerate(zip(task_keys, results)):
            # DIAGNOSTIC: Log raw result before processing
            # BANK-GRADE: Safe length calculation - only for strings
            result_length = len(result) if isinstance(result, str) else (0 if result is None else None)
            self.logger.error(
                f"🔍 [PARALLEL-ORCHESTRATOR] Processing result for task '{key}'",
                extra={
                    "company": context.get("company_name", "unknown"),
                    "correlation_id": context.get("correlation_id"),
                    "task_key": key,
                    "result_is_exception": isinstance(result, Exception),
                    "result_is_none": result is None,
                    "result_type": type(result).__name__ if result is not None else "None",
                    "result_length": result_length,
                }
            )
            
            if isinstance(result, Exception):
                # Log exception for any failed task
                self.logger.error(
                    f"❌ [PARALLEL-ORCHESTRATOR] Task '{key}' raised exception",
                    extra={
                        "company": context.get("company_name", "unknown"),
                        "correlation_id": context.get("correlation_id"),
                        "task_key": key,
                        "exception_type": type(result).__name__,
                        "exception_message": str(result),
                        "exception_traceback": self._format_exception_traceback(result) if hasattr(result, '__traceback__') else None,
                    },
                    exc_info=result
                )
                processed_results[key] = None
            elif result is None:
                # Log None returns for any task
                self.logger.error(
                    f"❌ [PARALLEL-ORCHESTRATOR] CRITICAL: Task '{key}' returned None",
                    extra={
                        "company": context.get("company_name", "unknown"),
                        "correlation_id": context.get("correlation_id"),
                        "task_key": key,
                        "diagnosis_note": "Check earlier logs for validation failures, template errors, or circuit breaker state",
                    }
                )
                processed_results[key] = None
            else:
                result_length = len(result) if isinstance(result, str) else 0
                self.logger.info(
                    f"✅ [PARALLEL-ORCHESTRATOR] Task '{key}' succeeded",
                    extra={
                        "company": context.get("company_name", "unknown"),
                        "correlation_id": context.get("correlation_id"),
                        "task_key": key,
                        "result_length": result_length,
                    }
                )
                processed_results[key] = result
        
        success_count = sum(1 for v in processed_results.values() if v is not None)

        self.logger.info(
            "Parallel execution results processed",
            extra={
                "company": context.get("company_name", "unknown"),
                "correlation_id": context.get("correlation_id"),
                "total_tasks": len(processed_results),
                "successful_tasks": success_count,
                "failed_tasks": len(processed_results) - success_count,
                "html_report_is_none": processed_results.get('html_report') is None,
            }
        )
        
        return processed_results
    
    def _format_exception_traceback(self, exception: Exception) -> Optional[str]:
        """Format exception traceback for logging."""
        import traceback
        if hasattr(exception, '__traceback__') and exception.__traceback__:
            return ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        return None
