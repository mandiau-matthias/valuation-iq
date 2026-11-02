"""
Shared page-container rendering for pagination renderers.

Both simple and full-document renderers emit identical ``.page`` containers;
this helper keeps that markup contract in one place.
"""

from src.domain.pagination import Page


def render_page_container(page: Page) -> str:
    """Render one paginated page and its content blocks."""
    page_html = ['<div class="page">']
    page_html.extend(block.html for block in page.blocks)
    page_html.append("</div>")
    return "\n".join(page_html)
