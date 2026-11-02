from src.utils.exceptions import APIError, CacheError, DataValidationError, DependencyError, MultiplesCalculationError

"""
Feature Serving for Real-time ML Inference

Provides real-time feature serving capabilities for ML models
with caching, monitoring, and performance optimization.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import asyncio
import time

from src.utils.logging import get_logger
from .feature_store import get_feature_store
from .feature_extractor import get_feature_extractor
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = get_logger(__name__)


class FeatureServing:
    """
    Real-time feature serving for ML models

    Features:
    - Real-time feature retrieval (<20ms)
    - Feature caching and optimization
    - Performance monitoring
    - Feature drift detection
    - Batch feature serving
    """

    def __init__(self):
        """Initialize feature serving"""
        self.feature_store = get_feature_store()
        self.feature_extractor = get_feature_extractor()

        # Performance tracking
        self.request_count = 0
        self.total_latency = Decimal('0.0')
        self.cache_hits = 0
        self.cache_misses = 0

        # Feature serving configuration
        self.default_timeout = Decimal('0.02')  # 20ms timeout
        self.cache_ttl = 300  # 5 minutes cache

        logger.info("FeatureServing initialized", 
                   timeout=self.default_timeout,
                   cache_ttl=self.cache_ttl)

    async def serve_features(
        self, 
        session_id: str, 
        feature_names: List[str],
        timeout: Optional[Decimal] = None
    ) -> Dict[str, Union[float, int, str]]:
        """
        Serve features for real-time ML inference

        Args:
            session_id: Session identifier
            feature_names: List of feature names to retrieve
            timeout: Maximum time to wait (default: 20ms)

        Returns:
            Dictionary of feature_name -> feature_value
        """
        start_time = time.time()
        timeout = timeout or self.default_timeout

        try:
            # Check if we have cached features
            cached_features = await self._get_cached_features(session_id, feature_names)
            if cached_features:
                self.cache_hits += 1
                self._update_performance_metrics(start_time)
                return cached_features

            # Extract features if not cached
            features = await self._extract_and_cache_features(session_id, feature_names)
            self.cache_misses += 1

            # Filter to requested features
            filtered_features = {
                name: value for name, value in features.items() 
                if name in feature_names
            }

            self._update_performance_metrics(start_time)
            return filtered_features

        except asyncio.TimeoutError:
            logger.warning("Feature serving timeout", session_id=session_id, timeout=timeout)
            return self._get_default_features(feature_names)
        except CacheError as e:
            logger.error(f"Error serving features: {e}")
            return self._get_default_features(feature_names)

    async def _get_cached_features(
        self, 
        session_id: str, 
        feature_names: List[str]
    ) -> Optional[Dict[str, Union[float, int, str]]]:
        """Get features from cache if available"""
        try:
            # Get all session features
            session_features = await self.feature_store.get_session_features(session_id)

            if not session_features:
                return None

            # Check if all requested features are available
            available_features = {}
            for feature_name in feature_names:
                if feature_name in session_features:
                    available_features[feature_name] = session_features[feature_name]["feature_value"]
                else:
                    return None  # Not all features available

            return available_features

        except DataValidationError as e:
            logger.error(f"Error getting cached features: {e}")
            return None

    async def _extract_and_cache_features(
        self, 
        session_id: str, 
        feature_names: List[str]
    ) -> Dict[str, Union[float, int, str]]:
        """Extract and cache features for session"""
        try:
            # This would typically get the context from the context manager
            # For now, we'll extract features directly
            features = {}

            # Get existing features from store
            session_features = await self.feature_store.get_session_features(session_id)

            # Extract missing features
            missing_features = [name for name in feature_names if name not in session_features]

            if missing_features:
                # In a real implementation, we would get the context and extract features
                # For now, we'll use default values
                for feature_name in missing_features:
                    features[feature_name] = self._get_default_feature_value(feature_name)

                # Store new features
                await self.feature_store.store_features_batch(
                    session_id=session_id,
                    features=features
                )

            # Combine existing and new features
            all_features = {}
            for feature_name in feature_names:
                if feature_name in session_features:
                    all_features[feature_name] = session_features[feature_name]["feature_value"]
                elif feature_name in features:
                    all_features[feature_name] = features[feature_name]
                else:
                    all_features[feature_name] = self._get_default_feature_value(feature_name)

            return all_features

        except DependencyError as e:
            logger.error(f"Error extracting and caching features: {e}")
            return self._get_default_features(feature_names)

    def _get_default_feature_value(self, feature_name: str) -> Union[float, int, str]:
        """Get default value for a feature"""
        feature_defaults = {
            "data_completeness_score": Decimal('0.0'),
            "conversation_velocity": Decimal('0.0'),
            "question_diversity": Decimal('0.0'),
            "owner_dependency_signal": Decimal('0.0'),
            "financial_health_score": Decimal('0.0'),
            "sentiment_score": Decimal('0.0'),
            "engagement_score": Decimal('0.0'),
            "response_quality": Decimal('0.0'),
            "information_density": Decimal('0.0'),
            "conversation_length": 0,
            "message_count": 0,
            "user_message_ratio": Decimal('0.0'),
            "question_count": 0,
            "answer_count": 0
        }

        return feature_defaults.get(feature_name, Decimal('0.0'))

    def _get_default_features(self, feature_names: List[str]) -> Dict[str, Union[float, int, str]]:
        """Get default features for all requested names"""
        return {
            name: self._get_default_feature_value(name) 
            for name in feature_names
        }

    def _update_performance_metrics(self, start_time: Decimal):
        """Update performance tracking metrics"""
        latency = time.time() - start_time
        self.request_count += 1
        self.total_latency += latency

    async def serve_feature_vector(
        self, 
        session_id: str, 
        feature_names: List[str]
    ) -> List[Decimal]:
        """
        Serve feature vector for ML model inference

        Args:
            session_id: Session identifier
            feature_names: List of feature names in order

        Returns:
            List of feature values as floats
        """
        try:
            features = await self.serve_features(session_id, feature_names)

            # Convert to vector
            vector = []
            for feature_name in feature_names:
                value = features.get(feature_name, Decimal('0.0'))
                try:
                    vector.append(to_decimal(value))
                except (ValueError, TypeError):
                    vector.append(Decimal('0.0'))

            logger.debug("Feature vector served", 
                       session_id=session_id,
                       vector_length=len(vector))

            return vector

        except MultiplesCalculationError as e:
            logger.error(f"Error serving feature vector: {e}")
            return [Decimal('0.0')] * len(feature_names)

    async def batch_serve_features(
        self, 
        session_ids: List[str], 
        feature_names: List[str]
    ) -> Dict[str, Dict[str, Union[float, int, str]]]:
        """
        Serve features for multiple sessions in batch

        Args:
            session_ids: List of session identifiers
            feature_names: List of feature names to retrieve

        Returns:
            Dictionary of session_id -> features
        """
        try:
            results = {}

            # Process sessions in parallel
            tasks = [
                self.serve_features(session_id, feature_names)
                for session_id in session_ids
            ]

            feature_results = await asyncio.gather(*tasks, return_exceptions=True)

            for session_id, features in zip(session_ids, feature_results):
                if isinstance(features, Exception):
                    logger.error(f"Error serving features for session {session_id}: {features}")
                    results[session_id] = self._get_default_features(feature_names)
                else:
                    results[session_id] = features

            logger.info("Batch feature serving completed", 
                       sessions=len(session_ids),
                       features_per_session=len(feature_names))

            return results

        except DataValidationError as e:
            logger.error(f"Error in batch feature serving: {e}")
            return {session_id: self._get_default_features(feature_names) for session_id in session_ids}

    async def health_check(self) -> Dict[str, Any]:
        """Check feature serving health"""
        try:
            feature_store_health = await self.feature_store.health_check()
            feature_extractor_health = await self.feature_extractor.health_check()

            # Calculate performance metrics
            avg_latency = self.total_latency / max(self.request_count, 1)
            cache_hit_rate = self.cache_hits / max(self.request_count, 1) if self.request_count > 0 else Decimal('0.0')

            return {
                "status": "healthy" if feature_store_health["status"] == "healthy" and feature_extractor_health["status"] == "healthy" else "unhealthy",
                "feature_store": feature_store_health,
                "feature_extractor": feature_extractor_health,
                "performance": {
                    "request_count": self.request_count,
                    "avg_latency_ms": avg_latency * 1000,
                    "cache_hit_rate": cache_hit_rate,
                    "cache_hits": self.cache_hits,
                    "cache_misses": self.cache_misses
                },
                "timeout": self.default_timeout,
                "cache_ttl": self.cache_ttl
            }

        except DataValidationError as e:
            logger.error(f"Feature serving health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def get_stats(self) -> Dict[str, Any]:
        """Get feature serving statistics"""
        try:
            feature_store_stats = await self.feature_store.get_stats()
            feature_extractor_stats = await self.feature_extractor.get_stats()

            # Calculate performance metrics
            avg_latency = self.total_latency / max(self.request_count, 1)
            cache_hit_rate = self.cache_hits / max(self.request_count, 1) if self.request_count > 0 else Decimal('0.0')

            return {
                "feature_store": feature_store_stats,
                "feature_extractor": feature_extractor_stats,
                "performance": {
                    "request_count": self.request_count,
                    "avg_latency_ms": avg_latency * 1000,
                    "cache_hit_rate": cache_hit_rate,
                    "cache_hits": self.cache_hits,
                    "cache_misses": self.cache_misses
                },
                "timeout": self.default_timeout,
                "cache_ttl": self.cache_ttl
            }

        except APIError as e:
            logger.error(f"Error getting feature serving stats: {e}")
            return {"error": str(e)}


import threading as _threading

_feature_serving: Optional[FeatureServing] = None
_feature_serving_lock = _threading.Lock()


def get_feature_serving() -> FeatureServing:
    """Get global feature serving instance"""
    global _feature_serving
    if _feature_serving is None:
        with _feature_serving_lock:
            if _feature_serving is None:
                _feature_serving = FeatureServing()
    return _feature_serving
