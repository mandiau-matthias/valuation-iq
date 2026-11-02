"""
Data Source Tracker

Utility class to track all external data fetches during valuation calculations.
Provides complete audit trail of where data came from, when it was fetched,
and its confidence level.

ARCHITECTURE:
- Thread-safe tracking of data sources
- Automatic timestamp generation
- Integration with transparency models
- Support for caching metadata

USAGE:
    tracker = DataSourceTracker()

    # Track a data source
    tracker.track_source(
        name="Risk-Free Rate",
        value="2.5%",
        source="European Central Bank",
        confidence=Decimal('95.0'),  # Bank-grade: Decimal confidence (0-100 scale)
        api_url="https://api.ecb.europa.eu/stats/...",
        cache_status="Fresh (< 24 hours)"
    )

    # Get all tracked sources
    sources = tracker.get_sources()
"""

from datetime import datetime
from decimal import Decimal
from threading import Lock
from typing import Any, Dict, List, Optional

from src.domain.owner_models.transparency import DataSource
from src.utils.decimal_helpers import from_decimal, to_decimal


class DataSourceTracker:
    """
    Thread-safe tracker for external data sources used in valuation

    This class maintains a list of all external data fetches, including
    timestamps, sources, and confidence levels. It provides a complete
    audit trail for transparency and debugging.

    Attributes:
        sources: List of tracked DataSource objects
        _lock: Thread lock for safe concurrent access
    """

    def __init__(self):
        """Initialize the data source tracker"""
        self.sources: List[DataSource] = []
        self._lock = Lock()

    def track_source(
        self,
        name: str,
        value: Any,
        source: str,
        confidence: Decimal,
        api_url: Optional[str] = None,
        cache_status: Optional[str] = None,
        **kwargs,
    ) -> DataSource:
        """
        Track a data source fetch

        Args:
            name: Human-readable name of the data point
            value: The actual value fetched
            source: Source system/API name (e.g., "European Central Bank")
            confidence: Confidence score 0-100
            api_url: Optional API endpoint URL
            cache_status: Optional cache status description
            **kwargs: Additional metadata

        Returns:
            The created DataSource object

        Example:
            tracker.track_source(
                name="Risk-Free Rate",
                value=0.025,
                source="ECB API",
                confidence=Decimal('95.0'),  # Bank-grade: Decimal confidence (0-100 scale)
                api_url="https://api.ecb.europa.eu/stats/...",
                cache_status="Fresh"
            )
        """
        with self._lock:
            data_source = DataSource(
                name=name,
                value=value,
                source=source,
                timestamp=datetime.utcnow().isoformat() + "Z",
                confidence=confidence,
                api_url=api_url,
                cache_status=cache_status,
            )
            self.sources.append(data_source)
            return data_source

    def track_api_call(
        self,
        name: str,
        value: Any,
        api_name: str,
        endpoint: str,
        confidence: Decimal,
        cache_hit: bool = False,
    ) -> DataSource:
        """
        Convenience method to track an API call

        Args:
            name: Data point name
            value: Value fetched
            api_name: API service name
            endpoint: API endpoint URL
            confidence: Confidence score 0-100
            cache_hit: Whether this was a cache hit

        Returns:
            The created DataSource object
        """
        cache_status = "Cache Hit" if cache_hit else "Live API Call"
        return self.track_source(
            name=name,
            value=value,
            source=api_name,
            confidence=confidence,
            api_url=endpoint,
            cache_status=cache_status,
        )

    def track_database_fetch(
        self,
        name: str,
        value: Any,
        database: str,
        query_type: str,
        confidence: Decimal,
        record_count: Optional[int] = None,
    ) -> DataSource:
        """
        Convenience method to track a database fetch

        Args:
            name: Data point name
            value: Value fetched
            database: Database name (e.g., "KBO Database")
            query_type: Type of query (e.g., "Comparable Company Search")
            confidence: Confidence score 0-100
            record_count: Number of records returned

        Returns:
            The created DataSource object
        """
        cache_status = f"{query_type}"
        if record_count is not None:
            cache_status += f" ({record_count} records)"

        return self.track_source(
            name=name,
            value=value,
            source=database,
            confidence=confidence,
            cache_status=cache_status,
        )

    def track_calculation_input(
        self, name: str, value: Any, source: str = "User Input", confidence: Decimal = 100.0
    ) -> DataSource:
        """
        Track a user-provided input value

        Args:
            name: Input field name
            value: Input value
            source: Source description (default: "User Input")
            confidence: Confidence score (default: 100.0 for user inputs)

        Returns:
            The created DataSource object
        """
        return self.track_source(
            name=name,
            value=value,
            source=source,
            confidence=confidence,
            cache_status="Direct Input",
        )

    def track_default_value(
        self, name: str, value: Any, reason: str, confidence: Decimal = 50.0
    ) -> DataSource:
        """
        Track a default/fallback value being used

        Args:
            name: Parameter name
            value: Default value
            reason: Why default is being used
            confidence: Confidence score (typically lower for defaults)

        Returns:
            The created DataSource object
        """
        return self.track_source(
            name=name,
            value=value,
            source="Default Value",
            confidence=confidence,
            cache_status=f"Fallback: {reason}",
        )

    def get_sources(
        self,
        name: Optional[str] = None,
        source: Optional[str] = None,
        min_confidence: Optional[Decimal] = None,
    ) -> List[DataSource]:
        """
        Get tracked data sources, optionally filtered

        Args:
            name: Filter by exact data source name
            source: Filter by source system/API name
            min_confidence: Filter by minimum confidence score

        Returns:
            List of matching DataSource objects in chronological order
        """
        with self._lock:
            result = self.sources.copy()

        if name is not None:
            result = [s for s in result if s.name == name]
        if source is not None:
            result = [s for s in result if s.source == source]
        if min_confidence is not None:
            result = [s for s in result if s.confidence >= min_confidence]

        return result

    def get_sources_by_type(self, source_type: str) -> List[DataSource]:
        """
        Get data sources filtered by source type

        Args:
            source_type: Source type to filter by (e.g., "ECB API", "KBO Database")

        Returns:
            List of matching DataSource objects
        """
        with self._lock:
            return [s for s in self.sources if s.source == source_type]

    def get_average_confidence(self) -> Decimal:
        """
        Calculate average confidence across all data sources

        Returns:
            Average confidence score 0-100, or 0 if no sources tracked
        """
        with self._lock:
            if not self.sources:
                return 0.0
            return sum(s.confidence for s in self.sources) / len(self.sources)

    def get_source_summary(self) -> Dict[str, Any]:
        """
        Get a summary of tracked data sources

        Returns:
            Dict with source statistics
        """
        with self._lock:
            return {
                "total_sources": len(self.sources),
                "average_confidence": self.get_average_confidence(),
                "source_types": list(set(s.source for s in self.sources)),
                "api_calls": len([s for s in self.sources if s.api_url is not None]),
                "cache_hits": len(
                    [
                        s
                        for s in self.sources
                        if s.cache_status and "cache" in s.cache_status.lower()
                    ]
                ),
                "live_calls": len(
                    [s for s in self.sources if s.cache_status and "live" in s.cache_status.lower()]
                ),
            }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about tracked data sources

        Returns:
            Dict with total_sources, sources_by_type, and average_confidence
        """
        with self._lock:
            sources_by_type: Dict[str, int] = {}
            for s in self.sources:
                sources_by_type[s.source] = sources_by_type.get(s.source, 0) + 1

            avg_confidence = None
            if self.sources:
                avg_confidence = sum(s.confidence for s in self.sources) / len(self.sources)

            return {
                "total_sources": len(self.sources),
                "sources_by_type": sources_by_type,
                "average_confidence": avg_confidence,
            }

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a human-readable summary of tracked data sources

        Returns:
            Dict with total_sources and the list of sources
        """
        with self._lock:
            return {
                "total_sources": len(self.sources),
                "sources": [s.model_dump() for s in self.sources],
            }

    def clear(self):
        """Clear all tracked sources"""
        with self._lock:
            self.sources.clear()

    def __len__(self) -> int:
        """Return number of tracked sources"""
        return len(self.sources)

    def __repr__(self) -> str:
        """String representation of tracker"""
        return f"DataSourceTracker(sources={len(self.sources)}, avg_confidence={self.get_average_confidence():.1f})"
