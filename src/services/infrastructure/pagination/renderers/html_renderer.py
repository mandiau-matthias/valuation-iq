"""
HTML Renderer Protocol

Abstract interface for pagination renderers.

Follows Interface Segregation Principle (ISP):
    Clients depend only on methods they use.
"""

from typing import Protocol, List
from src.domain.pagination import Page


class HTMLRenderer(Protocol):
    """
    Protocol for rendering paginated content to HTML.
    
    Implementations:
        - SimplePageRenderer: Just page containers
        - FullDocumentRenderer: Complete HTML document
    
    Design Pattern:
        Protocol (structural subtyping) - Pythonic interface
    """
    
    def render(self, pages: List[Page]) -> str:
        """
        Render pages to HTML string.
        
        Args:
            pages: List of Page entities from pagination
        
        Returns:
            HTML string
        """
        ...






