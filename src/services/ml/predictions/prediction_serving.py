from src.utils.exceptions import BusinessTypeError, CacheError, DCFCalculationError, DataValidationError, MethodologyError

"""
Prediction Serving for Real-time ML Inference

Provides real-time prediction serving with caching, monitoring,
and performance optimization for ML models.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import asyncio
import time

from src.utils.logging import get_logger
from .prediction_cache import get_prediction_cache
from .model_registry import get_model_registry
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


class PredictionServing:
    """
    Real-time prediction serving for ML models

    Features:
    - Real-time prediction serving with caching
    - Model version management
    - Performance monitoring
    - A/B testing support
    - Batch prediction serving
    """

    def __init__(self):
        """Initialize prediction serving"""
        self.prediction_cache = get_prediction_cache()
        self.model_registry = get_model_registry()

        # Performance tracking
        self.request_count = 0
        self.total_latency = Decimal('0.0')
        self.cache_hits = 0
        self.cache_misses = 0
        self.model_errors = 0

        # Serving configuration
        self.default_timeout = Decimal('0.1')  # 100ms timeout
        self.cache_ttl = 3600  # 1 hour cache TTL

        logger.info("PredictionServing initialized", 
                   timeout=self.default_timeout,
                   cache_ttl=self.cache_ttl)

    async def predict(
        self, 
        model_name: str, 
        input_data: Union[Dict, List, str],
        environment: str = "production",
        use_cache: bool = True,
        timeout: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Get prediction from ML model

        Args:
            model_name: Name of the ML model
            input_data: Input data for prediction
            environment: Model environment (production, staging, etc.)
            use_cache: Whether to use cached predictions
            timeout: Maximum time to wait (default: 100ms)

        Returns:
            Prediction result with metadata
        """
        start_time = time.time()
        timeout = timeout or self.default_timeout

        try:
            # Check cache first if enabled
            if use_cache:
                cached_prediction = await self.prediction_cache.get_prediction(
                    model_name=model_name,
                    input_data=input_data
                )

                if cached_prediction:
                    self.cache_hits += 1
                    self._update_performance_metrics(start_time)
                    return {
                        "prediction": cached_prediction["prediction"],
                        "confidence": cached_prediction.get("confidence"),
                        "model_version": cached_prediction["model_version"],
                        "cached": True,
                        "latency_ms": (time.time() - start_time) * 1000
                    }

            # Get deployed model
            deployed_model = await self.model_registry.get_deployed_model(
                model_name=model_name,
                environment=environment
            )

            if not deployed_model:
                logger.error("No deployed model found", 
                           model_name=model_name,
                           environment=environment)
                self.model_errors += 1
                return self._get_error_prediction("Model not deployed")

            # Make prediction (this would call the actual model)
            prediction_result = await self._make_model_prediction(
                model_name=model_name,
                model_version=deployed_model["version"],
                input_data=input_data,
                timeout=timeout
            )

            if prediction_result.get("error"):
                self.model_errors += 1
                return prediction_result

            # Cache prediction if successful
            if use_cache:
                await self.prediction_cache.cache_prediction(
                    model_name=model_name,
                    input_data=input_data,
                    prediction=prediction_result["prediction"],
                    model_version=deployed_model["version"],
                    confidence=prediction_result.get("confidence"),
                    ttl=self.cache_ttl
                )

            self.cache_misses += 1
            self._update_performance_metrics(start_time)

            return {
                "prediction": prediction_result["prediction"],
                "confidence": prediction_result.get("confidence"),
                "model_version": deployed_model["version"],
                "cached": False,
                "latency_ms": (time.time() - start_time) * 1000
            }

        except asyncio.TimeoutError:
            logger.warning("Prediction timeout", 
                           model_name=model_name, 
                           timeout=timeout)
            return self._get_error_prediction("Prediction timeout")
        except CacheError as e:
            logger.error(f"Error in prediction serving: {e}")
            self.model_errors += 1
            return self._get_error_prediction(str(e))

    async def _make_model_prediction(
        self, 
        model_name: str, 
        model_version: str,
        input_data: Union[Dict, List, str],
        timeout: Decimal
    ) -> Dict[str, Any]:
        """
        Make actual model prediction (placeholder implementation)

        In a real implementation, this would:
        1. Load the model
        2. Preprocess input data
        3. Run inference
        4. Postprocess output
        """
        try:
            # Simulate model inference delay
            await asyncio.sleep(0.01)  # 10ms simulation - asyncio.sleep requires float, not Decimal

            # Placeholder prediction logic based on model name
            if model_name == "risk_assessment":
                return await self._predict_risk_assessment(input_data)
            elif model_name == "methodology_selector":
                return await self._predict_methodology_selector(input_data)
            elif model_name == "owner_dependency":
                return await self._predict_owner_dependency(input_data)
            else:
                return self._get_error_prediction(f"Unknown model: {model_name}")

        except MethodologyError as e:
            logger.error(f"Error in model prediction: {e}")
            return self._get_error_prediction(str(e))

    async def _predict_risk_assessment(self, input_data: Union[Dict, List, str]) -> Dict[str, Any]:
        """Placeholder risk assessment prediction"""
        try:
            # Extract features from input data
            if isinstance(input_data, dict):
                revenue = input_data.get("revenue", 0)
                ebitda = input_data.get("ebitda", 0)
                debt = input_data.get("total_debt", 0)
                assets = input_data.get("total_assets", 1)
            else:
                # Default values for non-dict input
                revenue = 1000000
                ebitda = 100000
                debt = 500000
                assets = 2000000

            # Simple risk calculation
            if assets > 0:
                debt_ratio = debt / assets
                if debt_ratio < 0.3:
                    risk_score = Decimal('0.2')  # Low risk
                elif debt_ratio < 0.6:
                    risk_score = Decimal('0.5')  # Medium risk
                else:
                    risk_score = Decimal('0.8')  # High risk
            else:
                risk_score = Decimal('0.9')  # Very high risk

            return {
                "prediction": risk_score,
                "confidence": Decimal('0.85'),
                "model_type": "risk_assessment"
            }

        except BusinessTypeError as e:
            return self._get_error_prediction(str(e))

    async def _predict_methodology_selector(self, input_data: Union[Dict, List, str]) -> Dict[str, Any]:
        """Placeholder methodology selector prediction"""
        try:
            # Extract features from input data
            if isinstance(input_data, dict):
                business_type = input_data.get("business_type", "unknown")
                revenue = input_data.get("revenue", 0)
                ebitda = input_data.get("ebitda", 0)
            else:
                business_type = "unknown"
                revenue = 1000000
                ebitda = 100000

            # Simple methodology selection
            if revenue > 10000000:  # > $10M revenue
                methodology = "dcf"
                confidence = Decimal('0.9')
            elif business_type in ["saas", "technology", "software"]:
                methodology = "multiples"
                confidence = Decimal('0.8')
            else:
                methodology = "dcf"
                confidence = Decimal('0.7')

            return {
                "prediction": methodology,
                "confidence": confidence,
                "model_type": "methodology_selector"
            }

        except DCFCalculationError as e:
            return self._get_error_prediction(str(e))

    async def _predict_owner_dependency(self, input_data: Union[Dict, List, str]) -> Dict[str, Any]:
        """Placeholder owner dependency prediction"""
        try:
            # Extract features from input data
            if isinstance(input_data, dict):
                owner_hours = input_data.get("owner_hours", 40)
                employee_count = input_data.get("employee_count", 1)
                delegation = input_data.get("delegation_capability", Decimal('0.5'))
            else:
                owner_hours = 40
                employee_count = 1
                delegation = Decimal('0.5')

            # Simple dependency calculation
            if employee_count > 10 and delegation > 0.7:
                dependency_score = Decimal('0.2')  # Low dependency
            elif owner_hours > 60:
                dependency_score = Decimal('0.8')  # High dependency
            else:
                dependency_score = Decimal('0.5')  # Medium dependency

            return {
                "prediction": dependency_score,
                "confidence": Decimal('0.75'),
                "model_type": "owner_dependency"
            }

        except CacheError as e:
            return self._get_error_prediction(str(e))

    def _get_error_prediction(self, error_message: str) -> Dict[str, Any]:
        """Get error prediction response"""
        return {
            "prediction": None,
            "confidence": Decimal('0.0'),
            "error": error_message,
            "cached": False,
            "latency_ms": Decimal('0.0')
        }

    def _update_performance_metrics(self, start_time: Decimal):
        """Update performance tracking metrics"""
        latency = time.time() - start_time
        self.request_count += 1
        self.total_latency += latency

    async def batch_predict(
        self, 
        model_name: str, 
        input_data_list: List[Union[Dict, List, str]],
        environment: str = "production",
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get predictions for multiple inputs in batch

        Args:
            model_name: Name of the ML model
            input_data_list: List of input data
            environment: Model environment
            use_cache: Whether to use cached predictions

        Returns:
            List of prediction results
        """
        try:
            # Process predictions in parallel
            tasks = [
                self.predict(
                    model_name=model_name,
                    input_data=input_data,
                    environment=environment,
                    use_cache=use_cache
                )
                for input_data in input_data_list
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle exceptions
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error in batch prediction {i}: {result}")
                    processed_results.append(self._get_error_prediction(str(result)))
                else:
                    processed_results.append(result)

            logger.info("Batch prediction completed", 
                       model_name=model_name,
                       input_count=len(input_data_list),
                       successful=len([r for r in processed_results if not r.get("error")]))

            return processed_results

        except DataValidationError as e:
            logger.error(f"Error in batch prediction: {e}")
            return [self._get_error_prediction(str(e)) for _ in input_data_list]

    async def health_check(self) -> Dict[str, Any]:
        """Check prediction serving health"""
        try:
            prediction_cache_health = await self.prediction_cache.health_check()
            model_registry_health = await self.model_registry.health_check()

            # Calculate performance metrics
            avg_latency = self.total_latency / max(self.request_count, 1)
            cache_hit_rate = self.cache_hits / max(self.request_count, 1) if self.request_count > 0 else Decimal('0.0')
            error_rate = self.model_errors / max(self.request_count, 1) if self.request_count > 0 else Decimal('0.0')

            return {
                "status": "healthy" if prediction_cache_health["status"] == "healthy" and model_registry_health["status"] == "healthy" else "unhealthy",
                "prediction_cache": prediction_cache_health,
                "model_registry": model_registry_health,
                "performance": {
                    "request_count": self.request_count,
                    "avg_latency_ms": avg_latency * 1000,
                    "cache_hit_rate": cache_hit_rate,
                    "error_rate": error_rate,
                    "cache_hits": self.cache_hits,
                    "cache_misses": self.cache_misses,
                    "model_errors": self.model_errors
                },
                "timeout": self.default_timeout,
                "cache_ttl": self.cache_ttl
            }

        except DataValidationError as e:
            logger.error(f"Prediction serving health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def get_stats(self) -> Dict[str, Any]:
        """Get prediction serving statistics"""
        try:
            prediction_cache_stats = await self.prediction_cache.get_stats()
            model_registry_stats = await self.model_registry.get_stats()

            # Calculate performance metrics
            avg_latency = self.total_latency / max(self.request_count, 1)
            cache_hit_rate = self.cache_hits / max(self.request_count, 1) if self.request_count > 0 else Decimal('0.0')
            error_rate = self.model_errors / max(self.request_count, 1) if self.request_count > 0 else Decimal('0.0')

            return {
                "prediction_cache": prediction_cache_stats,
                "model_registry": model_registry_stats,
                "performance": {
                    "request_count": self.request_count,
                    "avg_latency_ms": avg_latency * 1000,
                    "cache_hit_rate": cache_hit_rate,
                    "error_rate": error_rate,
                    "cache_hits": self.cache_hits,
                    "cache_misses": self.cache_misses,
                    "model_errors": self.model_errors
                },
                "timeout": self.default_timeout,
                "cache_ttl": self.cache_ttl
            }

        except CacheError as e:
            logger.error(f"Error getting prediction serving stats: {e}")
            return {"error": str(e)}


import threading as _threading

_prediction_serving: Optional[PredictionServing] = None
_prediction_serving_lock = _threading.Lock()


def get_prediction_serving() -> PredictionServing:
    """Get global prediction serving instance"""
    global _prediction_serving
    if _prediction_serving is None:
        with _prediction_serving_lock:
            if _prediction_serving is None:
                _prediction_serving = PredictionServing()
    return _prediction_serving
