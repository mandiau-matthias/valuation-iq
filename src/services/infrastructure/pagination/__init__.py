"""
Smart A4 Pagination System

Intelligent content-aware pagination that automatically flows HTML content
into A4 pages based on measured heights, ensuring headings start at page tops
and preventing content overflow.

Architecture:
    1. ContentBlockParser: Parse HTML into semantic blocks
    2. SmartPaginator: Flow blocks into A4 pages with intelligent rules
    3. PageRenderer: Wrap paginated blocks in page containers
    4. PaginationService: Orchestrate the pagination pipeline

Design Principles:
    - Works with existing Jinja2 templates (no refactoring needed)
    - Post-processing layer after template rendering
    - Heuristic-based height estimation (95%+ accuracy target)
    - Feature flag controlled
"""

from .content_block_parser import ContentBlockParser, ContentBlock
from .smart_paginator import SmartPaginator, Page
from .page_renderer import PageRenderer
from .pagination_service import PaginationService

__all__ = [
    'ContentBlockParser',
    'ContentBlock',
    'SmartPaginator',
    'Page',
    'PageRenderer',
    'PaginationService',
]
