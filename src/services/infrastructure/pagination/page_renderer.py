"""
Page Renderer

Wraps paginated content blocks in <div class="page"> containers
for final HTML output.

Generates clean, properly structured HTML that matches the existing
.page container format from base.html.
"""

from typing import List
from .smart_paginator import Page

from src.utils.logging import get_logger

logger = get_logger(__name__)


class PageRenderer:
    """
    Renders paginated content blocks into final HTML with page containers.
    
    Generates HTML that matches the existing page container structure:
    <div class="final-report">
        <div class="page">
            <!-- Page 1 content -->
        </div>
        <div class="page">
            <!-- Page 2 content -->
        </div>
    </div>
    """
    
    def __init__(self, preserve_metadata: bool = True):
        """
        Initialize renderer.
        
        Args:
            preserve_metadata: If True, preserve <head> metadata from original HTML
        """
        self.preserve_metadata = preserve_metadata
    
    def render(self, pages: List[Page], original_html: str = "") -> str:
        """
        Render pages into final HTML.
        
        Args:
            pages: List of Page objects from SmartPaginator
            original_html: Original HTML (for extracting <head> if needed)
        
        Returns:
            Final paginated HTML string
        """
        if not pages:
            logger.warning("[PAGINATION-RENDERER] No pages to render")
            return original_html
        
        logger.info(
            f"🔍 [PAGINATION-RENDERER] Rendering {len(pages)} pages",
            extra={"page_count": len(pages)}
        )
        
        # Extract <head> section from original HTML if preserving metadata
        head_section = ""
        if self.preserve_metadata and original_html:
            head_section = self._extract_head(original_html)
        
        # Build paginated HTML
        html_parts = []
        
        # Add DOCTYPE and opening tags if we have head section
        if head_section:
            html_parts.append('<!DOCTYPE html>')
            html_parts.append('<html lang="en">')
            html_parts.append(head_section)
            html_parts.append('<body>')
        
        # Start final-report container
        html_parts.append('<div class="final-report">')
        
        # Render each page
        for page in pages:
            html_parts.append(self._render_page(page))
        
        # Close final-report container
        html_parts.append('</div>')
        
        # Close document if we added head section
        if head_section:
            html_parts.append('</body>')
            html_parts.append('</html>')
        
        final_html = '\n'.join(html_parts)
        
        logger.info(
            f"✅ [PAGINATION-RENDERER] Generated {len(final_html)} characters",
            extra={
                "html_length": len(final_html),
                "page_count": len(pages)
            }
        )
        
        return final_html
    
    def _extract_head(self, html: str) -> str:
        """
        Extract <head> section from HTML.
        
        Args:
            html: Original HTML string
        
        Returns:
            <head>...</head> section
        """
        # Simple extraction (could use BeautifulSoup if needed)
        start = html.find('<head>')
        end = html.find('</head>')
        
        if start != -1 and end != -1:
            return html[start:end + 7]  # Include </head> tag
        
        return ""
    
    def _render_page(self, page: Page) -> str:
        """
        Render a single page with its content blocks.
        
        Args:
            page: Page object with blocks
        
        Returns:
            HTML string for the page
        """
        # Start page container
        page_html = ['<div class="page">']
        
        # Add all blocks
        for block in page.blocks:
            page_html.append(block.html)
        
        # Close page container
        page_html.append('</div>')
        
        return '\n'.join(page_html)
    
    def render_simple(self, pages: List[Page]) -> str:
        """
        Render pages without metadata (just the page containers).
        
        Useful for when the original HTML head/metadata should be preserved
        by wrapping this output in the original document structure.
        
        Args:
            pages: List of Page objects
        
        Returns:
            HTML string with just .page containers (NO .final-report wrapper)
        """
        if not pages:
            return ""
        
        html_parts = []
        
        for page in pages:
            html_parts.append(self._render_page(page))
        
        return '\n'.join(html_parts)
