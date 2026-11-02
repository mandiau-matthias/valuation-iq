"""
Full Document Renderer

Renders complete HTML document with metadata, head section, and body.

Single Responsibility:
    Generate complete HTML document from pages + original metadata
"""

from typing import List

from src.domain.pagination import Page
from src.utils.logging import get_logger

from .metadata_extractor import MetadataExtractor
from .page_container_renderer import render_page_container

logger = get_logger(__name__)


class FullDocumentRenderer:
    """
    Renders complete HTML document with metadata.

    Generates:
        <!DOCTYPE html>
        <html lang="en">
        <head>...</head>
        <body>
            <div class="final-report">
                <div class="page">...</div>
                <div class="page">...</div>
            </div>
        </body>
        </html>

    Dependencies:
        - MetadataExtractor: Extracts <head> from original HTML
    """

    def __init__(self, metadata_extractor: MetadataExtractor):
        """
        Initialize renderer.

        Args:
            metadata_extractor: Service for extracting HTML metadata
        """
        self.metadata_extractor = metadata_extractor

    def render(self, pages: List[Page], original_html: str = "") -> str:
        """
        Render complete HTML document with pages.

        Args:
            pages: List of Page entities from pagination
            original_html: Original HTML (for extracting metadata)

        Returns:
            Complete HTML document string

        Example:
            >>> renderer = FullDocumentRenderer(MetadataExtractor())
            >>> html = renderer.render(pages, original_html)
            >>> html.startswith('<!DOCTYPE html>')
            True
        """
        if not pages:
            logger.warning("[FULL-RENDERER] No pages to render")
            return original_html

        logger.info(
            f"🔍 [FULL-RENDERER] Rendering complete document", extra={"page_count": len(pages)}
        )

        # Extract metadata from original HTML
        doctype = self.metadata_extractor.extract_doctype(original_html)
        head_section = self.metadata_extractor.extract_head(original_html)
        html_attrs = self.metadata_extractor.extract_html_attributes(original_html)

        # Build complete document
        html_parts = []

        # Document structure
        html_parts.append(doctype)
        html_parts.append(f"<html {html_attrs}>")

        if head_section:
            html_parts.append(head_section)
        else:
            # Fallback head
            html_parts.append('<head><meta charset="UTF-8"></head>')

        html_parts.append("<body>")

        # Wrap pages in final-report container
        html_parts.append('<div class="final-report">')

        # Render each page
        for page in pages:
            html_parts.append(render_page_container(page))

        html_parts.append("</div>")  # Close final-report
        html_parts.append("</body>")
        html_parts.append("</html>")

        result = "\n".join(html_parts)

        logger.info(
            f"✅ [FULL-RENDERER] Complete document generated",
            extra={
                "html_length": len(result),
                "page_count": len(pages),
                "has_head": bool(head_section),
            },
        )

        return result
