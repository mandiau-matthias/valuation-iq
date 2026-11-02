"""
Pagination Renderers

Interface-segregated renderers following ISP (Interface Segregation Principle).

Architecture:
    - HTMLRenderer (Protocol) - Abstract interface
    - SimplePageRenderer - Renders only page containers
    - FullDocumentRenderer - Renders complete HTML document
    - MetadataExtractor - Extracts <head> from HTML

Each renderer has ONE responsibility, can be tested in isolation.
"""

from .full_document_renderer import FullDocumentRenderer
from .html_renderer import HTMLRenderer
from .metadata_extractor import MetadataExtractor
from .page_container_renderer import render_page_container
from .simple_page_renderer import SimplePageRenderer

__all__ = [
    "HTMLRenderer",
    "SimplePageRenderer",
    "FullDocumentRenderer",
    "MetadataExtractor",
    "render_page_container",
]
