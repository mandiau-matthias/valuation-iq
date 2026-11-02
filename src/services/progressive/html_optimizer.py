from src.errors.error_types import TemplateRenderError

"""
HTML Streaming Optimizer

Optimizes HTML for progressive rendering and streaming.
Applies compression, lazy loading, and chunking for better performance.
"""

import re
import logging
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = logging.getLogger(__name__)


class StreamingHTMLOptimizer:
    """Optimize HTML for progressive rendering and streaming"""

    def __init__(self):
        logger.info("[HTML_OPTIMIZER] StreamingHTMLOptimizer initialized")

    def optimize_for_streaming(self, html: str) -> str:
        """
        Apply streaming optimizations:
        1. Remove unnecessary whitespace
        2. Add lazy loading attributes
        3. Add progressive rendering hints
        4. Optimize for faster parsing
        """
        logger.debug("[HTML_OPTIMIZER] Optimizing HTML for streaming")

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove excessive whitespace
            html = re.sub(r'\s+', ' ', str(soup))

            # Re-parse for further optimizations
            soup = BeautifulSoup(html, 'html.parser')

            # Add progressive rendering hints
            if soup.body:
                soup.body['data-progressive'] = 'true'

            # Lazy load images
            for img in soup.find_all('img'):
                img['loading'] = 'lazy'
                # Add placeholder for better UX
                if not img.get('alt'):
                    img['alt'] = 'Loading...'

            # Defer non-critical scripts
            for script in soup.find_all('script', src=True):
                if 'critical' not in script.get('class', []):
                    script['defer'] = ''

            # Add streaming hints to sections
            for section in soup.find_all(['div', 'section'], class_=re.compile(r'section|phase')):
                section['data-streaming'] = 'true'

            optimized_html = str(soup)
            logger.debug(f"[HTML_OPTIMIZER] Optimized HTML size: {len(optimized_html)} chars")

            return optimized_html

        except TemplateRenderError as e:
            logger.error(f"[HTML_OPTIMIZER] Failed to optimize HTML: {e}")
            # Return original HTML if optimization fails
            return html

    def split_into_chunks(self, html: str, chunk_size: int = 8192) -> List[str]:
        """Split HTML into streamable chunks at safe boundaries"""
        logger.debug(f"[HTML_OPTIMIZER] Splitting HTML into chunks of {chunk_size} bytes")

        chunks = []
        current_chunk = ""

        # Split by lines to maintain HTML structure
        lines = html.split('\n')

        for line in lines:
            # If adding this line would exceed chunk size, start new chunk
            if len(current_chunk) + len(line) + 1 > chunk_size and current_chunk:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += line + '\n'

        # Add remaining content
        if current_chunk:
            chunks.append(current_chunk)

        logger.debug(f"[HTML_OPTIMIZER] Split into {len(chunks)} chunks")
        return chunks

    def add_loading_placeholders(self, html: str, section_ids: List[str]) -> str:
        """Add loading placeholders for sections that haven't been rendered yet"""
        logger.debug(f"[HTML_OPTIMIZER] Adding loading placeholders for {len(section_ids)} sections")

        try:
            soup = BeautifulSoup(html, 'html.parser')

            for section_id in section_ids:
                # Find or create placeholder div
                placeholder = soup.find('div', {'data-section': section_id})
                if not placeholder:
                    placeholder = soup.new_tag('div', **{
                        'data-section': section_id,
                        'class': 'section-loading',
                        'data-status': 'loading'
                    })
                    soup.body.append(placeholder)

                # Add loading content
                placeholder.string = f"Loading {section_id}..."

            return str(soup)

        except TemplateRenderError as e:
            logger.error(f"[HTML_OPTIMIZER] Failed to add loading placeholders: {e}")
            return html

    def compress_html(self, html: str) -> str:
        """Apply basic HTML compression"""
        logger.debug("[HTML_OPTIMIZER] Compressing HTML")

        # Remove comments
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

        # Remove extra whitespace
        html = re.sub(r'\s+', ' ', html)

        # Remove empty lines
        html = re.sub(r'\n\s*\n', '\n', html)

        logger.debug(f"[HTML_OPTIMIZER] Compressed HTML size: {len(html)} chars")
        return html

    def add_progressive_hints(self, html: str) -> str:
        """Add hints for progressive rendering"""
        logger.debug("[HTML_OPTIMIZER] Adding progressive rendering hints")

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Add meta tags for progressive rendering
            head = soup.find('head')
            if head:
                # Add progressive rendering meta
                meta_progressive = soup.new_tag('meta', attrs={
                    'name': 'progressive-rendering',
                    'content': 'enabled'
                })
                head.append(meta_progressive)

                # Add streaming hint
                meta_streaming = soup.new_tag('meta', attrs={
                    'name': 'streaming-content',
                    'content': 'true'
                })
                head.append(meta_streaming)

            # Add data attributes to sections
            for section in soup.find_all(['div', 'section'], class_=re.compile(r'section|phase')):
                section['data-progressive'] = 'true'
                section['data-streaming'] = 'true'

            return str(soup)

        except TemplateRenderError as e:
            logger.error(f"[HTML_OPTIMIZER] Failed to add progressive hints: {e}")
            return html

    def optimize_for_mobile(self, html: str) -> str:
        """Apply mobile-specific optimizations"""
        logger.debug("[HTML_OPTIMIZER] Applying mobile optimizations")

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Add viewport meta tag if missing
            head = soup.find('head')
            if head:
                viewport = soup.find('meta', attrs={'name': 'viewport'})
                if not viewport:
                    viewport = soup.new_tag('meta', attrs={
                        'name': 'viewport',
                        'content': 'width=device-width, initial-scale=1.0'
                    })
                    head.append(viewport)

            # Optimize images for mobile
            for img in soup.find_all('img'):
                # Add responsive classes
                img_classes = img.get('class', [])
                if 'img-responsive' not in img_classes:
                    img_classes.append('img-responsive')
                img['class'] = img_classes

                # Add mobile-specific attributes
                img['data-mobile-optimized'] = 'true'

            return str(soup)

        except TemplateRenderError as e:
            logger.error(f"[HTML_OPTIMIZER] Failed to optimize for mobile: {e}")
            return html

    def full_optimization(self, html: str, chunk_size: int = 8192) -> Dict[str, Any]:
        """Apply all optimizations and return optimized HTML with metadata"""
        logger.info("[HTML_OPTIMIZER] Applying full optimization pipeline")

        original_size = len(html)

        # Apply all optimizations
        optimized_html = self.optimize_for_streaming(html)
        optimized_html = self.compress_html(optimized_html)
        optimized_html = self.add_progressive_hints(optimized_html)
        optimized_html = self.optimize_for_mobile(optimized_html)

        # Split into chunks
        chunks = self.split_into_chunks(optimized_html, chunk_size)

        compression_ratio = (original_size - len(optimized_html)) / original_size * 100

        result = {
            'optimized_html': optimized_html,
            'chunks': chunks,
            'original_size': original_size,
            'optimized_size': len(optimized_html),
            'compression_ratio': compression_ratio,
            'chunk_count': len(chunks),
            'avg_chunk_size': sum(len(chunk) for chunk in chunks) / len(chunks) if chunks else 0
        }

        logger.info(f"[HTML_OPTIMIZER] Optimization complete | compression={compression_ratio:.1f}% | chunks={len(chunks)}")

        return result
