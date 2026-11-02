"""
ML Predictions Module

Provides prediction caching and serving capabilities for ML models
to reduce inference latency and improve performance.

Components:
- PredictionCache: Redis-backed prediction caching
- ModelRegistry: Model version management
- PredictionServing: Real-time prediction serving
"""

from .prediction_cache import PredictionCache, get_prediction_cache
from .model_registry import ModelRegistry, get_model_registry
from .prediction_serving import PredictionServing, get_prediction_serving

__all__ = [
    'PredictionCache',
    'get_prediction_cache',
    'ModelRegistry',
    'get_model_registry',
    'PredictionServing',
    'get_prediction_serving'
]
