"""
ML Tasks Module

Provides background task management for ML operations
including embedding generation, feature extraction, and model updates.

Components:
- MLTaskManager: Background task orchestration
- EmbeddingTasks: Async embedding generation
- FeatureTasks: Batch feature extraction
- ModelTasks: Model update and training tasks
"""

from .ml_task_manager import MLTaskManager, get_ml_task_manager
from .embedding_tasks import EmbeddingTasks, get_embedding_tasks
from .feature_tasks import FeatureTasks, get_feature_tasks
from .model_tasks import ModelTasks, get_model_tasks

__all__ = [
    'MLTaskManager',
    'get_ml_task_manager',
    'EmbeddingTasks',
    'get_embedding_tasks',
    'FeatureTasks',
    'get_feature_tasks',
    'ModelTasks',
    'get_model_tasks'
]
