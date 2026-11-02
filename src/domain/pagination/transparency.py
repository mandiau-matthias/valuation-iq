"""
Pagination Transparency Value Objects

Bank-grade audit trail for pagination decisions.

Every pagination calculation must be traceable:
- Why was a page created?
- What rule was applied?
- What blocks were moved?
- How long did pagination take?

Academic Reference:
    McKinsey Valuation (2020) - Chapter on Transparency
    "Every valuation calculation must be fully traceable and auditable"

Bank-Grade Standards:
    - Immutable transparency records
    - Timestamp every decision
    - Full provenance tracking
    - Integration with audit logs
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Tuple
from decimal import Decimal

from .value_objects import Height


@dataclass(frozen=True)
class OverflowEvent:
    """
    Immutable record of a pagination overflow event.
    
    Tracks when a block didn't fit and what rule was applied.
    
    Example:
        >>> event = OverflowEvent(
        ...     block_index=5,
        ...     block_type='heading',
        ...     rule_applied='RULE 1: Heading overflow',
        ...     page_before=1,
        ...     page_after=2,
        ...     timestamp=datetime.now(timezone.utc)
        ... )
    """
    block_index: int
    block_type: str
    rule_applied: str  # "RULE 1: Heading overflow", etc.
    page_before: int
    page_after: int
    height_overflow: Height
    timestamp: datetime
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/API response."""
        return {
            'block_index': self.block_index,
            'block_type': self.block_type,
            'rule_applied': self.rule_applied,
            'page_before': self.page_before,
            'page_after': self.page_after,
            'height_overflow_pt': str(self.height_overflow.points),
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass(frozen=True)
class PageMetadata:
    """
    Metadata for a single page in pagination.
    
    Tracks page-level statistics for transparency.
    """
    page_number: int
    block_count: int
    total_height: Height
    utilization_percentage: Decimal  # % of max height used
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/API response."""
        return {
            'page_number': self.page_number,
            'block_count': self.block_count,
            'total_height_pt': str(self.total_height.points),
            'utilization_pct': str(self.utilization_percentage),
        }


@dataclass(frozen=True)
class PaginationTransparency:
    """
    Complete audit trail for a pagination calculation.
    
    Immutable record of all pagination decisions for compliance.
    
    Bank-Grade Requirements:
        - Full traceability of every decision
        - Timestamp for calculation time
        - Performance metrics
        - Integration with ValuationTransparency
    
    Example:
        >>> transparency = PaginationTransparency(
        ...     total_blocks=50,
        ...     total_pages=5,
        ...     overflow_events=[...],
        ...     page_metadata=[...],
        ...     calculation_time_ms=145,
        ...     timestamp=datetime.now(timezone.utc)
        ... )
    """
    total_blocks: int
    total_pages: int
    overflow_events: Tuple[OverflowEvent, ...]
    page_metadata: Tuple[PageMetadata, ...]
    calculation_time_ms: int
    timestamp: datetime
    
    # Pagination configuration used
    max_page_height_pt: str
    safety_buffer_ratio: str
    
    def to_dict(self) -> dict:
        """
        Convert to dictionary for audit logs and API responses.
        
        Returns:
            Dictionary with full pagination transparency data
        """
        return {
            'total_blocks': self.total_blocks,
            'total_pages': self.total_pages,
            'overflow_events': [e.to_dict() for e in self.overflow_events],
            'page_metadata': [p.to_dict() for p in self.page_metadata],
            'calculation_time_ms': self.calculation_time_ms,
            'timestamp': self.timestamp.isoformat(),
            'configuration': {
                'max_page_height_pt': self.max_page_height_pt,
                'safety_buffer_ratio': self.safety_buffer_ratio,
            },
            'summary': {
                'overflow_count': len(self.overflow_events),
                'avg_blocks_per_page': (
                    round(self.total_blocks / self.total_pages, 2)
                    if self.total_pages > 0 else 0
                ),
                'avg_utilization_pct': (
                    str(sum(
                        p.utilization_percentage for p in self.page_metadata
                    ) / len(self.page_metadata))
                    if self.page_metadata else "0"
                ),
            }
        }
    
    def get_rule_statistics(self) -> dict:
        """
        Get statistics on which pagination rules were applied.
        
        Returns:
            Dictionary mapping rule names to occurrence counts
        """
        rule_counts = {}
        for event in self.overflow_events:
            rule = event.rule_applied
            rule_counts[rule] = rule_counts.get(rule, 0) + 1
        return rule_counts


class TransparencyBuilder:
    """
    Builder for creating PaginationTransparency records.
    
    Mutable builder pattern for constructing immutable transparency.
    
    Example:
        >>> builder = TransparencyBuilder(dims)
        >>> builder.record_overflow(...)
        >>> builder.record_page(...)
        >>> transparency = builder.build()  # Immutable result
    """
    
    def __init__(self, page_dimensions: 'PageDimensions'):
        """
        Initialize transparency builder.
        
        Args:
            page_dimensions: PageDimensions used for pagination
        """
        self.page_dimensions = page_dimensions
        self.overflow_events: List[OverflowEvent] = []
        self.page_metadata: List[PageMetadata] = []
        self.start_time = datetime.now(timezone.utc)
        self.total_blocks = 0
    
    def record_overflow(
        self,
        block_index: int,
        block_type: str,
        rule_applied: str,
        page_before: int,
        page_after: int,
        height_overflow: Height
    ) -> 'TransparencyBuilder':
        """
        Record an overflow event.
        
        Args:
            block_index: Index of overflowing block
            block_type: Type of block
            rule_applied: Which pagination rule was applied
            page_before: Page number before overflow
            page_after: Page number after overflow
            height_overflow: Amount of height overflow
        
        Returns:
            Self for chaining
        """
        event = OverflowEvent(
            block_index=block_index,
            block_type=block_type,
            rule_applied=rule_applied,
            page_before=page_before,
            page_after=page_after,
            height_overflow=height_overflow,
            timestamp=datetime.now(timezone.utc)
        )
        self.overflow_events.append(event)
        return self
    
    def record_page(
        self,
        page_number: int,
        block_count: int,
        total_height: Height,
        max_height: Height
    ) -> 'TransparencyBuilder':
        """
        Record metadata for a completed page.
        
        Args:
            page_number: Page number
            block_count: Number of blocks on page
            total_height: Total height of content
            max_height: Maximum allowed height
        
        Returns:
            Self for chaining
        """
        utilization = (
            (total_height.points / max_height.points * Decimal('100'))
            if max_height.points > 0
            else Decimal('0')
        )
        
        metadata = PageMetadata(
            page_number=page_number,
            block_count=block_count,
            total_height=total_height,
            utilization_percentage=utilization,
        )
        self.page_metadata.append(metadata)
        return self
    
    def set_total_blocks(self, count: int) -> 'TransparencyBuilder':
        """
        Set total number of blocks processed.
        
        Args:
            count: Total block count
        
        Returns:
            Self for chaining
        """
        self.total_blocks = count
        return self
    
    def build(self) -> PaginationTransparency:
        """
        Build immutable PaginationTransparency record.
        
        Returns:
            Frozen PaginationTransparency value object
        """
        end_time = datetime.now(timezone.utc)
        calculation_time_ms = int((end_time - self.start_time).total_seconds() * 1000)
        
        return PaginationTransparency(
            total_blocks=self.total_blocks,
            total_pages=len(self.page_metadata),
            overflow_events=tuple(self.overflow_events),
            page_metadata=tuple(self.page_metadata),
            calculation_time_ms=calculation_time_ms,
            timestamp=self.start_time,
            max_page_height_pt=str(self.page_dimensions.safe_height.points),
            safety_buffer_ratio=str(self.page_dimensions.safety_buffer_ratio),
        )


def calculate_page_statistics(pages: List['Page']) -> List[PageMetadata]:
    """
    Calculate metadata for all pages.
    
    Pure function for extracting page statistics.
    
    Args:
        pages: List of Page entities
    
    Returns:
        List of PageMetadata for each page
    """
    return [
        PageMetadata(
            page_number=page.number,
            block_count=len(page.blocks),
            total_height=page.current_height,
            utilization_percentage=(
                (page.current_height.points / page.max_height.points * Decimal('100'))
                if page.max_height.points > 0
                else Decimal('0')
            ),
        )
        for page in pages
    ]






