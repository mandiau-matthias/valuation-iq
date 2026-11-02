"""
Data Integrator - Stateless Stub Implementation

BRAIN & MUSCLE ARCHITECTURE:
ValuationIQ (The Muscle) is a stateless calculation engine.
Historical data and learning models live in Titan.

This module provides a stub implementation that:
- Satisfies imports from business_intelligence_service, business_data_integrator
- Returns empty/default values (no database/cache queries)
- Allows the app to start and run in stateless mode

For full data integration with DB/Redis, implement the real DataIntegrator
that queries historical valuations and manages cache.

@author UpSwitch CTO Team
@version 2.0.0 - Brain & Muscle Stateless Stub
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


class DataIntegrator:
    """
    No-op data integrator for stateless mode.

    Returns empty/default values for all methods.
    Callers have fallback logic for missing historical/learning data.
    """

    def __init__(self, db: Any = None, redis_client: Any = None):
        """
        Initialize data integrator.

        Args:
            db: Database session (unused in stateless mode)
            redis_client: Redis client (unused in stateless mode)
        """
        self.db = db
        self.redis_client = redis_client
        self._metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "warnings": 0,
            "avg_query_time": Decimal("0"),
        }

    async def analyze_historical_data(self, business_type: str) -> Dict[str, Any]:
        """
        Return empty historical analysis (stateless - no DB).

        Callers use this for methodology weight calculation;
        empty dict triggers fallback logic in intelligence_processor.
        """
        return {
            "insights": {},
            "trends": {},
            "patterns": {},
            "historical_valuations": [],
            "statistics": {},
            "data_quality": Decimal("0"),
        }

    async def store_business_type_analysis(self, analysis_result: Dict[str, Any]) -> bool:
        """No-op - stateless mode does not persist analysis."""
        return True

    async def get_system_metrics(self) -> Dict[str, Any]:
        """Return minimal metrics for status reporting."""
        return {
            "cache_hits": self._metrics["cache_hits"],
            "cache_misses": self._metrics["cache_misses"],
            "errors": self._metrics["errors"],
            "warnings": self._metrics["warnings"],
            "avg_query_time": float(self._metrics["avg_query_time"]),
        }

    async def get_learning_data(
        self,
        business_type: str,
        learning_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Return empty learning data (stateless - no DB).

        Used for ML model training; empty list triggers fallback.
        """
        return []
