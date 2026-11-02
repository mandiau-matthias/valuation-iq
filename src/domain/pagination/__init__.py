"""
Pagination Domain Layer

Bank-grade pagination domain logic with:
- Immutable value objects (Height, SectionId, PageDimensions)
- Pure pagination functions
- Type safety throughout
- Zero infrastructure dependencies

Architecture:
    - value_objects.py: Domain value objects (Height, SectionId, etc.)
    - entities.py: Domain entities (Page, ContentBlock)
    - pagination_engine.py: Pure pagination function
    - section_grouper.py: Domain service for section grouping
    - transparency.py: Audit trail value objects
"""

from .value_objects import Height, SectionId, PageDimensions
from .section_grouper import SectionGrouper
from .entities import Page
from .pagination_engine import paginate_content
from .transparency import (
    PaginationTransparency,
    OverflowEvent,
    PageMetadata,
    TransparencyBuilder,
    calculate_page_statistics,
)

__all__ = [
    'Height',
    'SectionId',
    'PageDimensions',
    'SectionGrouper',
    'Page',
    'paginate_content',
    'PaginationTransparency',
    'OverflowEvent',
    'PageMetadata',
    'TransparencyBuilder',
    'calculate_page_statistics',
]






