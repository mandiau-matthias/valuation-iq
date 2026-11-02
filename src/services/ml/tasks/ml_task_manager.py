from src.utils.exceptions import DataValidationError

"""
ML Task Manager for Background ML Operations

Orchestrates background ML tasks including embedding generation,
feature extraction, model updates, and training data preparation.
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import time

from src.utils.logging import get_logger
from .embedding_tasks import get_embedding_tasks
from .feature_tasks import get_feature_tasks
from .model_tasks import get_model_tasks
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


class MLTaskManager:
    """
    Background ML task manager

    Features:
    - Async embedding generation
    - Batch feature extraction
    - Periodic model updates
    - Training data preparation
    - Task monitoring and health checks
    """

    def __init__(self):
        """Initialize ML task manager"""
        self.embedding_tasks = get_embedding_tasks()
        self.feature_tasks = get_feature_tasks()
        self.model_tasks = get_model_tasks()

        # Task management
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.task_stats: Dict[str, Any] = {}
        self.is_running = False

        # Task configuration
        self.embedding_interval = 300  # 5 minutes
        self.feature_interval = 600    # 10 minutes
        self.model_interval = 3600     # 1 hour

        logger.info("MLTaskManager initialized", 
                   embedding_interval=self.embedding_interval,
                   feature_interval=self.feature_interval,
                   model_interval=self.model_interval)

    async def start_background_tasks(self) -> bool:
        """Start all background ML tasks"""
        try:
            if self.is_running:
                logger.warning("Background tasks already running")
                return True

            # Start embedding generation task
            embedding_task = asyncio.create_task(
                self._run_embedding_tasks(),
                name="embedding_tasks"
            )
            self.running_tasks["embedding_tasks"] = embedding_task

            # Start feature extraction task
            feature_task = asyncio.create_task(
                self._run_feature_tasks(),
                name="feature_tasks"
            )
            self.running_tasks["feature_tasks"] = feature_task

            # Start model update task
            model_task = asyncio.create_task(
                self._run_model_tasks(),
                name="model_tasks"
            )
            self.running_tasks["model_tasks"] = model_task

            self.is_running = True
            logger.info("Background ML tasks started", 
                       tasks=list(self.running_tasks.keys()))

            return True

        except Exception as e:
            logger.error(f"Error starting background tasks: {e}")
            return False

    async def stop_background_tasks(self) -> bool:
        """Stop all background ML tasks"""
        try:
            if not self.is_running:
                logger.warning("Background tasks not running")
                return True

            # Cancel all running tasks
            for task_name, task in self.running_tasks.items():
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        logger.debug(f"Task {task_name} cancelled")

            self.running_tasks.clear()
            self.is_running = False

            logger.info("Background ML tasks stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping background tasks: {e}")
            return False

    async def _run_embedding_tasks(self):
        """Run embedding generation tasks"""
        while self.is_running:
            try:
                start_time = time.time()

                # Generate embeddings for recent conversations
                await self.embedding_tasks.generate_embeddings_batch()

                # Update task stats
                duration = time.time() - start_time
                self.task_stats["embedding_tasks"] = {
                    "last_run": datetime.now().isoformat(),
                    "duration_seconds": duration,
                    "status": "completed"
                }

                logger.debug("Embedding tasks completed", duration=duration)

                # Wait for next interval
                await asyncio.sleep(self.embedding_interval)

            except asyncio.CancelledError:
                logger.info("Embedding tasks cancelled")
                break
            except Exception as e:
                logger.error(f"Error in embedding tasks: {e}")
                self.task_stats["embedding_tasks"] = {
                    "last_run": datetime.now().isoformat(),
                    "status": "error",
                    "error": str(e)
                }
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def _run_feature_tasks(self):
        """Run feature extraction tasks"""
        while self.is_running:
            try:
                start_time = time.time()

                # Extract features for recent conversations
                await self.feature_tasks.extract_features_batch()

                # Update task stats
                duration = time.time() - start_time
                self.task_stats["feature_tasks"] = {
                    "last_run": datetime.now().isoformat(),
                    "duration_seconds": duration,
                    "status": "completed"
                }

                logger.debug("Feature tasks completed", duration=duration)

                # Wait for next interval
                await asyncio.sleep(self.feature_interval)

            except asyncio.CancelledError:
                logger.info("Feature tasks cancelled")
                break
            except Exception as e:
                logger.error(f"Error in feature tasks: {e}")
                self.task_stats["feature_tasks"] = {
                    "last_run": datetime.now().isoformat(),
                    "status": "error",
                    "error": str(e)
                }
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def _run_model_tasks(self):
        """Run model update tasks"""
        while self.is_running:
            try:
                start_time = time.time()

                # Update models if needed
                await self.model_tasks.update_models_if_needed()

                # Update task stats
                duration = time.time() - start_time
                self.task_stats["model_tasks"] = {
                    "last_run": datetime.now().isoformat(),
                    "duration_seconds": duration,
                    "status": "completed"
                }

                logger.debug("Model tasks completed", duration=duration)

                # Wait for next interval
                await asyncio.sleep(self.model_interval)

            except asyncio.CancelledError:
                logger.info("Model tasks cancelled")
                break
            except Exception as e:
                logger.error(f"Error in model tasks: {e}")
                self.task_stats["model_tasks"] = {
                    "last_run": datetime.now().isoformat(),
                    "status": "error",
                    "error": str(e)
                }
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def run_immediate_tasks(self) -> Dict[str, Any]:
        """Run immediate ML tasks (not background)"""
        try:
            results = {}

            # Run embedding generation
            embedding_result = await self.embedding_tasks.generate_embeddings_batch()
            results["embedding_tasks"] = embedding_result

            # Run feature extraction
            feature_result = await self.feature_tasks.extract_features_batch()
            results["feature_tasks"] = feature_result

            # Run model updates
            model_result = await self.model_tasks.update_models_if_needed()
            results["model_tasks"] = model_result

            logger.info("Immediate ML tasks completed", 
                       results=results)

            return results

        except Exception as e:
            logger.error(f"Error running immediate tasks: {e}")
            return {"error": str(e)}

    async def get_task_status(self) -> Dict[str, Any]:
        """Get status of all background tasks"""
        try:
            status = {
                "is_running": self.is_running,
                "running_tasks": len(self.running_tasks),
                "task_stats": self.task_stats.copy()
            }

            # Add individual task status
            for task_name, task in self.running_tasks.items():
                status[f"{task_name}_status"] = {
                    "running": not task.done(),
                    "cancelled": task.cancelled(),
                    "exception": task.exception() if task.done() and not task.cancelled() else None
                }

            return status

        except DataValidationError as e:
            logger.error(f"Error getting task status: {e}")
            return {"error": str(e)}

    async def health_check(self) -> Dict[str, Any]:
        """Check ML task manager health"""
        try:
            # Check if tasks are running
            running_count = sum(1 for task in self.running_tasks.values() if not task.done())

            # Check task stats for errors
            error_tasks = [
                name for name, stats in self.task_stats.items() 
                if stats.get("status") == "error"
            ]

            status = "healthy" if running_count > 0 and not error_tasks else "unhealthy"

            return {
                "status": status,
                "is_running": self.is_running,
                "running_tasks": running_count,
                "total_tasks": len(self.running_tasks),
                "error_tasks": error_tasks,
                "task_stats": self.task_stats,
                "intervals": {
                    "embedding": self.embedding_interval,
                    "feature": self.feature_interval,
                    "model": self.model_interval
                }
            }

        except DataValidationError as e:
            logger.error(f"ML task manager health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def get_stats(self) -> Dict[str, Any]:
        """Get ML task manager statistics"""
        try:
            # Calculate task performance metrics
            total_runs = sum(1 for stats in self.task_stats.values() if stats.get("status") == "completed")
            error_runs = sum(1 for stats in self.task_stats.values() if stats.get("status") == "error")

            avg_duration = 0.0
            if self.task_stats:
                durations = [stats.get("duration_seconds", 0) for stats in self.task_stats.values() if "duration_seconds" in stats]
                if durations:
                    avg_duration = sum(durations) / len(durations)

            return {
                "is_running": self.is_running,
                "running_tasks": len(self.running_tasks),
                "total_runs": total_runs,
                "error_runs": error_runs,
                "success_rate": total_runs / max(total_runs + error_runs, 1),
                "avg_duration_seconds": avg_duration,
                "task_stats": self.task_stats,
                "intervals": {
                    "embedding": self.embedding_interval,
                    "feature": self.feature_interval,
                    "model": self.model_interval
                }
            }

        except Exception as e:
            logger.error(f"Error getting ML task manager stats: {e}")
            return {"error": str(e)}


# Global instance
_ml_task_manager: Optional[MLTaskManager] = None


def get_ml_task_manager() -> MLTaskManager:
    """Get global ML task manager instance"""
    global _ml_task_manager
    if _ml_task_manager is None:
        _ml_task_manager = MLTaskManager()
    return _ml_task_manager
