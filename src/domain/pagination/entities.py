"""
Pagination Domain Entities

Immutable domain entities for pagination.

Entities have identity and lifecycle, but in this domain they are
implemented as immutable value objects for bank-grade calculation purity.

Academic Reference:
    Domain-Driven Design (Eric Evans) - Entities vs Value Objects
    "An object fundamentally defined by its identity"

Bank-Grade Standards:
    - Frozen dataclasses (immutable)
    - Tuples instead of lists (immutability)
    - Copy-on-write pattern (functional)
    - Type safety throughout
"""

from dataclasses import dataclass, field
from typing import Tuple, Optional
from decimal import Decimal

from .value_objects import Height, PageDimensions, SectionId
from src.services.infrastructure.pagination.content_block_parser import ContentBlock


@dataclass(frozen=True)
class Page:
    """
    Immutable page entity with content blocks.
    
    Represents a single A4 page in the pagination calculation.
    Uses immutable tuple for blocks (not list) to ensure calculation purity.
    
    Business Rules:
        - Pages are numbered sequentially (1-indexed)
        - Total height cannot exceed max_height
        - Blocks are added via copy-on-write pattern
    
    Example:
        >>> dims = PageDimensions.a4_standard()
        >>> page = Page.empty(1, dims)
        >>> block = ContentBlock(...)
        >>> new_page = page.add_block(block)  # Returns NEW page
        >>> # Original page unchanged (immutable)
    """
    number: int
    blocks: Tuple[ContentBlock, ...] = field(default_factory=tuple)
    current_height: Height = field(default_factory=Height.zero)
    max_height: Height = field(default_factory=lambda: Height(Decimal('546.37')))
    
    def __post_init__(self):
        """Validate page on creation."""
        if self.number < 1:
            raise ValueError(f'Page number must be >= 1, got: {self.number}')
        
        # Validate current height doesn't exceed max
        # (Allow slight overflow for forced content, but warn)
        if self.current_height.points > self.max_height.points * Decimal('1.1'):
            # More than 10% overflow - likely an error
            raise ValueError(
                f'Page {self.number} height {self.current_height} exceeds max {self.max_height} by >10%'
            )
    
    @classmethod
    def empty(cls, number: int, dimensions: PageDimensions) -> 'Page':
        """
        Create an empty page.
        
        Args:
            number: Page number (1-indexed)
            dimensions: Page dimensions
        
        Returns:
            Empty page with no content
        """
        return cls(
            number=number,
            blocks=(),
            current_height=Height.zero(),
            max_height=dimensions.safe_height,
        )
    
    def can_fit(self, block: ContentBlock) -> bool:
        """
        Check if a block can fit on this page.
        
        Pure function - no mutation.
        
        Args:
            block: ContentBlock to check
        
        Returns:
            True if block fits within max_height
        """
        # Convert block height to Height value object
        block_height = Height.from_float(block.estimated_height)
        new_height = self.current_height + block_height
        return new_height.fits_in(self.max_height)
    
    def add_block(self, block: ContentBlock) -> 'Page':
        """
        Add a block to this page (immutable - returns NEW page).
        
        Copy-on-write pattern: Creates new Page with block added.
        Original page remains unchanged.
        
        Args:
            block: ContentBlock to add
        
        Returns:
            NEW Page instance with block added
        
        Example:
            >>> page1 = Page.empty(1, dims)
            >>> page2 = page1.add_block(block)
            >>> # page1.blocks == ()  (unchanged)
            >>> # page2.blocks == (block,)  (new page)
        """
        block_height = Height.from_float(block.estimated_height)
        new_height = self.current_height + block_height
        
        return Page(
            number=self.number,
            blocks=self.blocks + (block,),  # Tuple concatenation (immutable)
            current_height=new_height,
            max_height=self.max_height,
        )
    
    def remove_last_block(self) -> Tuple['Page', Optional[ContentBlock]]:
        """
        Remove last block from page (immutable - returns NEW page).
        
        Copy-on-write pattern: Creates new Page without last block.
        Original page remains unchanged.
        
        Returns:
            Tuple of (new_page, removed_block)
            If page is empty, returns (self, None)
        
        Example:
            >>> page1 = Page(..., blocks=(block1, block2))
            >>> page2, removed = page1.remove_last_block()
            >>> # page1.blocks == (block1, block2)  (unchanged)
            >>> # page2.blocks == (block1,)  (new page)
            >>> # removed == block2
        """
        if not self.blocks:
            return self, None
        
        removed_block = self.blocks[-1]
        new_blocks = self.blocks[:-1]
        
        # Recalculate height
        removed_height = Height.from_float(removed_block.estimated_height)
        new_height = self.current_height - removed_height
        
        new_page = Page(
            number=self.number,
            blocks=new_blocks,
            current_height=new_height,
            max_height=self.max_height,
        )
        
        return new_page, removed_block
    
    def is_empty(self) -> bool:
        """Check if page has no content."""
        return len(self.blocks) == 0
    
    def has_content(self) -> bool:
        """Check if page has content."""
        return len(self.blocks) > 0
    
    def get_last_block(self) -> Optional[ContentBlock]:
        """
        Get the last block on the page without removing it.
        
        Returns:
            Last ContentBlock or None if page is empty
        """
        if self.blocks:
            return self.blocks[-1]
        return None
    
    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f'Page {self.number}: {len(self.blocks)} blocks, '
            f'{self.current_height}/{self.max_height}'
        )
    
    def __repr__(self) -> str:
        """Developer representation."""
        return (
            f'Page(number={self.number}, blocks={len(self.blocks)}, '
            f'current_height={self.current_height!r}, max_height={self.max_height!r})'
        )






