"""
Simple Page Renderer

Renders pages as <div class="page"> containers WITHOUT document metadata.

Single Responsibility:
    Convert Page entities → HTML page containers
    
Use Case:
    When original HTML already has <head>, <body> structure
    and we just need to replace the .final-report content.
"""

from typing import List

from src.domain.pagination import Page
from src.utils.logging import get_logger

from .page_container_renderer import render_page_container

logger = get_logger(__name__)


class SimplePageRenderer:
    """
    Renders pages as simple page containers.

    Generates:
        <div class="page">
            <!-- Page 1 content -->
        </div>
        <div class="page">
            <!-- Page 2 content -->
        </div>

    Does NOT wrap in .final-report or add <html>/<body> tags.
    """

    def render(self, pages: List[Page]) -> str:
        """
        Render pages as simple page containers.

        Args:
            pages: List of Page entities

        Returns:
            HTML string with page containers (no document structure)

        Example:
            >>> renderer = SimplePageRenderer()
            >>> html = renderer.render(pages)
            >>> '<div class="page">' in html
            True
        """
        if not pages:
            logger.warning("[SIMPLE-RENDERER] No pages to render")
            return ""

        logger.info(
            f"🔍 [SIMPLE-RENDERER] Rendering {len(pages)} pages", extra={"page_count": len(pages)}
        )

        html_parts = []

        for page in pages:
            html_parts.append(render_page_container(page))

        result = "\n".join(html_parts)

        logger.info(
            f"✅ [SIMPLE-RENDERER] Generated {len(result)} characters",
            extra={
                "html_length": len(result),
                "page_count": len(pages),
            },
        )

        return result
