"""
Pagination Value Objects

Immutable domain value objects for pagination calculations.

All value objects are:
- Frozen dataclasses (immutable)
- Self-validating (fail fast on invalid state)
- Type-safe (full type hints)
- Pure (no side effects)

Academic Reference:
    Domain-Driven Design (Eric Evans, 2003)
    Value Objects chapter - immutable, self-validating domain concepts

Bank-Grade Standards:
    - Decimal arithmetic for all numeric calculations
    - Banker's rounding (ROUND_HALF_EVEN)
    - Explicit validation in __post_init__
    - No silent failures
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from typing import ClassVar


@dataclass(frozen=True)
class Height:
    """
    Value object for content height in points.
    
    Represents a measured or calculated height for pagination.
    Uses Decimal for precision (no float arithmetic).
    
    Business Rules:
        - Height must be non-negative
        - Precision: 2 decimal places
        - Unit: Points (pt)
    
    Example:
        >>> h1 = Height(Decimal('100.50'))
        >>> h2 = Height(Decimal('50.25'))
        >>> h3 = h1 + h2
        >>> print(h3.points)
        Decimal('150.75')
    """
    points: Decimal
    
    def __post_init__(self):
        """Validate height on creation."""
        if self.points < Decimal('0'):
            raise ValueError(f'Height must be non-negative, got: {self.points}')
        
        # Quantize to 2 decimal places with banker's rounding
        object.__setattr__(
            self,
            'points',
            self.points.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
        )
    
    def __add__(self, other: 'Height') -> 'Height':
        """
        Add two heights together.
        
        Args:
            other: Height to add
        
        Returns:
            New Height with sum of points
        """
        if not isinstance(other, Height):
            raise TypeError(f'Cannot add Height and {type(other).__name__}')
        
        return Height(self.points + other.points)
    
    def __sub__(self, other: 'Height') -> 'Height':
        """
        Subtract height from this height.
        
        Args:
            other: Height to subtract
        
        Returns:
            New Height with difference
        
        Raises:
            ValueError: If result would be negative
        """
        if not isinstance(other, Height):
            raise TypeError(f'Cannot subtract {type(other).__name__} from Height')
        
        result = self.points - other.points
        if result < Decimal('0'):
            raise ValueError(f'Height subtraction would be negative: {self.points} - {other.points}')
        
        return Height(result)
    
    def fits_in(self, container: 'Height') -> bool:
        """
        Check if this height fits within a container height.
        
        Args:
            container: Container height
        
        Returns:
            True if this height <= container height
        """
        return self.points <= container.points
    
    def __str__(self) -> str:
        """String representation for logging."""
        return f'{self.points}pt'
    
    def __repr__(self) -> str:
        """Developer representation."""
        return f'Height({self.points!r})'
    
    @classmethod
    def zero(cls) -> 'Height':
        """Create a zero height."""
        return cls(Decimal('0'))
    
    @classmethod
    def from_float(cls, value: float) -> 'Height':
        """
        Create Height from float (for backward compatibility).
        
        WARNING: Use sparingly - prefer Decimal for precision.
        
        Args:
            value: Float value in points
        
        Returns:
            Height value object
        """
        return cls(Decimal(str(value)))


@dataclass(frozen=True)
class SectionId:
    """
    Value object for section identifier.
    
    Groups content blocks under the same heading/section.
    
    Business Rules:
        - Cannot be empty string
        - Trimmed of whitespace
        - Case-sensitive
    
    Example:
        >>> section = SectionId('executive-summary')
        >>> print(section.value)
        'executive-summary'
    """
    value: str
    
    def __post_init__(self):
        """Validate section ID on creation."""
        # Trim whitespace
        trimmed = self.value.strip()
        object.__setattr__(self, 'value', trimmed)
        
        if not self.value:
            raise ValueError('SectionId cannot be empty')
    
    def __str__(self) -> str:
        """String representation for logging."""
        return self.value
    
    def __repr__(self) -> str:
        """Developer representation."""
        return f'SectionId({self.value!r})'


@dataclass(frozen=True)
class PageDimensions:
    """
    Value object for A4 page dimensions with safety buffer.
    
    Encapsulates page size constraints and safety margins for pagination.
    
    Business Rules:
        - Based on A4 standard (210mm × 297mm)
        - Content height excludes margins (2cm top + 2cm bottom)
        - Safety buffer prevents micro-overflows (default 75%)
    
    Academic Reference:
        ISO 216 standard for A4 paper size
        WeasyPrint documentation for PDF rendering
    
    Calibration Data:
        - A4 content height: 728.5pt (after 2cm top/bottom margins)
        - Safe height: 546.37pt (75% of content height)
    
    Example:
        >>> dims = PageDimensions.a4_standard()
        >>> print(dims.safe_height)
        546.37pt
    """
    content_height: Height
    safety_buffer_ratio: Decimal = Decimal('0.75')
    
    # A4 standard dimensions (class constants)
    A4_CONTENT_HEIGHT_PT: ClassVar[Decimal] = Decimal('728.50')
    DEFAULT_SAFETY_BUFFER: ClassVar[Decimal] = Decimal('0.75')
    
    def __post_init__(self):
        """Validate page dimensions on creation."""
        if not (Decimal('0') < self.safety_buffer_ratio <= Decimal('1')):
            raise ValueError(
                f'Safety buffer ratio must be between 0 and 1, got: {self.safety_buffer_ratio}'
            )
        
        # Quantize safety buffer to 2 decimal places
        object.__setattr__(
            self,
            'safety_buffer_ratio',
            self.safety_buffer_ratio.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)
        )
    
    @property
    def safe_height(self) -> Height:
        """
        Calculate safe content height with buffer applied.
        
        Returns:
            Height value with safety buffer applied
        """
        safe_points = self.content_height.points * self.safety_buffer_ratio
        return Height(safe_points)
    
    @classmethod
    def a4_standard(cls) -> 'PageDimensions':
        """
        Create standard A4 page dimensions.
        
        Returns:
            PageDimensions with A4 content height and 75% safety buffer
        """
        return cls(
            content_height=Height(cls.A4_CONTENT_HEIGHT_PT),
            safety_buffer_ratio=cls.DEFAULT_SAFETY_BUFFER,
        )
    
    @classmethod
    def a4_with_buffer(cls, buffer_ratio: Decimal) -> 'PageDimensions':
        """
        Create A4 dimensions with custom safety buffer.
        
        Args:
            buffer_ratio: Safety buffer ratio (0 < ratio <= 1)
        
        Returns:
            PageDimensions with custom buffer
        """
        return cls(
            content_height=Height(cls.A4_CONTENT_HEIGHT_PT),
            safety_buffer_ratio=buffer_ratio,
        )
    
    def __str__(self) -> str:
        """String representation for logging."""
        return f'PageDimensions(content={self.content_height}, safe={self.safe_height}, buffer={self.safety_buffer_ratio:.0%})'
    
    def __repr__(self) -> str:
        """Developer representation."""
        return f'PageDimensions(content_height={self.content_height!r}, safety_buffer_ratio={self.safety_buffer_ratio!r})'






