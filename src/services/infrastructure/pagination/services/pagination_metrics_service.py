"""
Pagination Metrics Service

BANK-GRADE: Single Responsibility - Track pagination performance metrics

RESPONSIBILITY:
- Track pagination performance
- Collect metrics
- Calculate statistics
- Generate performance reports

DOES NOT:
- Perform pagination (delegated to PaginationService)
- Parse content (delegated to ContentBlockParser)
- Render pages (delegated to PageRenderer)
- Handle errors (delegated to PaginationErrorHandler)

SRP Compliance: This service has ONE reason to change - metrics requirements
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import time

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PaginationMetrics:
    """Metrics for a single pagination operation"""
    
    # Timing
    total_time: float  # seconds
    parsing_time: float = 0.0
    pagination_time: float = 0.0
    rendering_time: float = 0.0
    
    # Content
    total_blocks: int = 0
    total_pages: int = 0
    content_size: int = 0  # bytes
    
    # Performance
    blocks_per_second: float = 0.0
    pages_per_second: float = 0.0
    bytes_per_second: float = 0.0
    
    # Quality
    orphan_violations: int = 0
    overflow_warnings: int = 0
    page_breaks: int = 0
    
    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: Optional[str] = None


class PaginationMetricsService:
    """
    BANK-GRADE SRP-COMPLIANT: Tracks pagination performance metrics.
    
    SINGLE RESPONSIBILITY: Performance metrics tracking
    
    This service focuses solely on metrics:
    - Tracking timing data
    - Calculating performance statistics
    - Collecting quality metrics
    - Generating reports
    
    Design Pattern: Service Pattern
    - Separates metrics from pagination logic
    - Enables testing metrics independently
    - Allows extending with new metrics
    """
    
    def __init__(self, enable_detailed_metrics: bool = True):
        """
        Initialize pagination metrics service.
        
        Args:
            enable_detailed_metrics: Whether to track detailed metrics
        """
        self.logger = logger
        self.enable_detailed_metrics = enable_detailed_metrics
        
        # Metrics storage
        self._metrics_history: List[PaginationMetrics] = []
        self._max_history = 1000  # Keep last 1000 operations
        
        # Current operation tracking
        self._current_operation: Optional[Dict[str, Any]] = None
        
        self.logger.info(
            "✅ [PAGINATION-METRICS] PaginationMetricsService initialized (SRP-compliant)",
            extra={'detailed_metrics': enable_detailed_metrics}
        )
    
    def start_operation(self, session_id: Optional[str] = None) -> None:
        """
        Start tracking a pagination operation.
        
        Args:
            session_id: Optional session identifier
        """
        if not self.enable_detailed_metrics:
            return
        
        self._current_operation = {
            'start_time': time.time(),
            'session_id': session_id,
            'timings': {},
            'counters': {},
            'quality': {}
        }
        
        self.logger.debug(
            "🔄 [PAGINATION-METRICS] Started operation tracking",
            extra={'session_id': session_id}
        )
    
    def record_timing(self, phase: str, duration: float) -> None:
        """
        Record timing for a pagination phase.
        
        Args:
            phase: Phase name (parsing, pagination, rendering)
            duration: Duration in seconds
        """
        if not self.enable_detailed_metrics or not self._current_operation:
            return
        
        self._current_operation['timings'][phase] = duration
        
        self.logger.debug(
            f"⏱️ [PAGINATION-METRICS] {phase}: {duration:.3f}s"
        )
    
    def record_counter(self, name: str, value: int) -> None:
        """
        Record a counter metric.
        
        Args:
            name: Counter name (total_blocks, total_pages, etc.)
            value: Counter value
        """
        if not self.enable_detailed_metrics or not self._current_operation:
            return
        
        self._current_operation['counters'][name] = value
    
    def record_quality_metric(self, name: str, value: int) -> None:
        """
        Record a quality metric.
        
        Args:
            name: Metric name (orphan_violations, overflow_warnings, etc.)
            value: Metric value
        """
        if not self.enable_detailed_metrics or not self._current_operation:
            return
        
        self._current_operation['quality'][name] = value
    
    def end_operation(self) -> Optional[PaginationMetrics]:
        """
        End operation tracking and calculate metrics.
        
        Returns:
            PaginationMetrics instance or None if tracking disabled
        """
        if not self.enable_detailed_metrics or not self._current_operation:
            return None
        
        # Calculate total time
        total_time = time.time() - self._current_operation['start_time']
        
        # Extract timings
        timings = self._current_operation['timings']
        counters = self._current_operation['counters']
        quality = self._current_operation['quality']
        
        # Create metrics instance
        metrics = PaginationMetrics(
            total_time=total_time,
            parsing_time=timings.get('parsing', 0.0),
            pagination_time=timings.get('pagination', 0.0),
            rendering_time=timings.get('rendering', 0.0),
            total_blocks=counters.get('total_blocks', 0),
            total_pages=counters.get('total_pages', 0),
            content_size=counters.get('content_size', 0),
            orphan_violations=quality.get('orphan_violations', 0),
            overflow_warnings=quality.get('overflow_warnings', 0),
            page_breaks=quality.get('page_breaks', 0),
            session_id=self._current_operation.get('session_id')
        )
        
        # Calculate performance metrics
        if total_time > 0:
            metrics.blocks_per_second = metrics.total_blocks / total_time
            metrics.pages_per_second = metrics.total_pages / total_time
            metrics.bytes_per_second = metrics.content_size / total_time
        
        # Store in history
        self._add_to_history(metrics)
        
        # Log summary
        self.logger.info(
            "✅ [PAGINATION-METRICS] Operation complete",
            extra={
                'total_time': f"{total_time:.3f}s",
                'total_pages': metrics.total_pages,
                'total_blocks': metrics.total_blocks,
                'blocks_per_second': f"{metrics.blocks_per_second:.1f}",
                'orphan_violations': metrics.orphan_violations
            }
        )
        
        # Clear current operation
        self._current_operation = None
        
        return metrics
    
    def _add_to_history(self, metrics: PaginationMetrics) -> None:
        """
        Add metrics to history.
        
        Args:
            metrics: PaginationMetrics instance
        """
        self._metrics_history.append(metrics)
        
        # Trim history if needed
        if len(self._metrics_history) > self._max_history:
            self._metrics_history = self._metrics_history[-self._max_history:]
    
    def get_statistics(self, last_n: Optional[int] = None) -> Dict[str, Any]:
        """
        Get performance statistics.
        
        Args:
            last_n: Number of recent operations to analyze (None = all)
            
        Returns:
            Statistics dictionary
        """
        if not self._metrics_history:
            return {'error': 'No metrics available'}
        
        # Select metrics to analyze
        metrics_to_analyze = (
            self._metrics_history[-last_n:] if last_n
            else self._metrics_history
        )
        
        # Calculate statistics
        total_operations = len(metrics_to_analyze)
        
        avg_total_time = sum(m.total_time for m in metrics_to_analyze) / total_operations
        avg_parsing_time = sum(m.parsing_time for m in metrics_to_analyze) / total_operations
        avg_pagination_time = sum(m.pagination_time for m in metrics_to_analyze) / total_operations
        avg_rendering_time = sum(m.rendering_time for m in metrics_to_analyze) / total_operations
        
        avg_blocks = sum(m.total_blocks for m in metrics_to_analyze) / total_operations
        avg_pages = sum(m.total_pages for m in metrics_to_analyze) / total_operations
        avg_blocks_per_second = sum(m.blocks_per_second for m in metrics_to_analyze) / total_operations
        
        total_orphan_violations = sum(m.orphan_violations for m in metrics_to_analyze)
        total_overflow_warnings = sum(m.overflow_warnings for m in metrics_to_analyze)
        
        return {
            'operations_analyzed': total_operations,
            'timing': {
                'avg_total_time': round(avg_total_time, 3),
                'avg_parsing_time': round(avg_parsing_time, 3),
                'avg_pagination_time': round(avg_pagination_time, 3),
                'avg_rendering_time': round(avg_rendering_time, 3)
            },
            'content': {
                'avg_blocks': round(avg_blocks, 1),
                'avg_pages': round(avg_pages, 1)
            },
            'performance': {
                'avg_blocks_per_second': round(avg_blocks_per_second, 1)
            },
            'quality': {
                'total_orphan_violations': total_orphan_violations,
                'total_overflow_warnings': total_overflow_warnings,
                'orphan_violation_rate': round(
                    total_orphan_violations / total_operations, 3
                )
            }
        }
    
    def get_recent_metrics(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent metrics.
        
        Args:
            count: Number of recent metrics to return
            
        Returns:
            List of metrics dictionaries
        """
        recent = self._metrics_history[-count:]
        
        return [
            {
                'timestamp': m.timestamp,
                'total_time': round(m.total_time, 3),
                'total_pages': m.total_pages,
                'total_blocks': m.total_blocks,
                'blocks_per_second': round(m.blocks_per_second, 1),
                'orphan_violations': m.orphan_violations
            }
            for m in recent
        ]
    
    def clear_history(self) -> None:
        """Clear metrics history."""
        self._metrics_history.clear()
        self.logger.info("✅ [PAGINATION-METRICS] History cleared")
