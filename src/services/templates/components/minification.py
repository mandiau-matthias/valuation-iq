
"""
Minification Service

HTML and CSS minification for template optimization.
"""

import re
from typing import Optional
import logging
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal

logger = logging.getLogger(__name__)


class MinificationService:
    """HTML and CSS minification"""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.MinificationService")

        # Compile regex patterns for performance
        self.html_comment_pattern = re.compile(r'<!--.*?-->', re.DOTALL)
        self.html_whitespace_pattern = re.compile(r'>\s+<')
        self.html_leading_trailing_pattern = re.compile(r'^\s+|\s+$', re.MULTILINE)
        self.html_multiple_spaces_pattern = re.compile(r'\s{2,}')

        self.css_comment_pattern = re.compile(r'/\*.*?\*/', re.DOTALL)
        self.css_whitespace_pattern = re.compile(r'\s+')
        self.css_cleanup_pattern = re.compile(r'\s*([{}:;,])\s*')

    def minify_html(self, html: str) -> str:
        """Minify HTML by removing unnecessary whitespace"""
        if not html:
            return html

        try:
            # Remove HTML comments
            html = self.html_comment_pattern.sub('', html)

            # Remove whitespace between tags
            html = self.html_whitespace_pattern.sub('><', html)

            # Remove leading/trailing whitespace
            html = self.html_leading_trailing_pattern.sub('', html)

            # Collapse multiple spaces
            html = self.html_multiple_spaces_pattern.sub(' ', html)

            return html.strip()

        except Exception as e:
            self.logger.warning(f"HTML minification failed: {e}")
            return html

    def minify_css(self, css: str) -> str:
        """Minify CSS"""
        if not css:
            return css

        try:
            # Remove CSS comments
            css = self.css_comment_pattern.sub('', css)

            # Remove excessive whitespace
            css = self.css_whitespace_pattern.sub(' ', css)

            # Clean up around CSS syntax
            css = self.css_cleanup_pattern.sub(r'\1', css)

            return css.strip()

        except Exception as e:
            self.logger.warning(f"CSS minification failed: {e}")
            return css

    def minify_section(self, html: str, preserve_formatting: bool = False) -> str:
        """Minify section HTML"""
        if not html:
            return html

        if preserve_formatting:
            # Only remove comments and excessive whitespace
            html = self.html_comment_pattern.sub('', html)
            html = self.html_multiple_spaces_pattern.sub(' ', html)
            return html

        return self.minify_html(html)

    def minify_inline_css(self, html: str) -> str:
        """Minify inline CSS in HTML"""
        if not html:
            return html

        try:
            # Find and minify style attributes
            style_pattern = re.compile(r'style="([^"]*)"')

            def minify_style(match):
                css = match.group(1)
                minified_css = self.minify_css(css)
                return f'style="{minified_css}"'

            return style_pattern.sub(minify_style, html)

        except Exception as e:
            self.logger.warning(f"Inline CSS minification failed: {e}")
            return html

    def minify_script_content(self, html: str) -> str:
        """Minify JavaScript content in script tags"""
        if not html:
            return html

        try:
            # Find and minify script content
            script_pattern = re.compile(r'<script[^>]*>(.*?)</script>', re.DOTALL)

            def minify_script(match):
                js_content = match.group(1)
                # Basic JS minification - remove comments and excessive whitespace
                js_content = re.sub(r'//.*?\n', '', js_content)  # Single line comments
                js_content = re.sub(r'/\*.*?\*/', '', js_content, flags=re.DOTALL)  # Multi-line comments
                js_content = re.sub(r'\s+', ' ', js_content)  # Multiple whitespace
                return f'<script>{js_content.strip()}</script>'

            return script_pattern.sub(minify_script, html)

        except Exception as e:
            self.logger.warning(f"Script minification failed: {e}")
            return html

    def minify_complete(self, html: str, preserve_formatting: bool = False) -> str:
        """Complete minification pipeline"""
        if not html:
            return html

        try:
            # Apply all minification steps
            html = self.minify_html(html)
            html = self.minify_inline_css(html)
            html = self.minify_script_content(html)

            return html

        except Exception as e:
            self.logger.warning(f"Complete minification failed: {e}")
            return html

    def get_minification_stats(self, original: str, minified: str) -> dict:
        """Get minification statistics"""
        if not original:
            return {"original_size": 0, "minified_size": 0, "savings_percent": 0}

        original_size = len(original)
        minified_size = len(minified)
        savings = original_size - minified_size
        savings_percent = (savings / original_size * 100) if original_size > 0 else 0

        return {
            "original_size": original_size,
            "minified_size": minified_size,
            "savings_bytes": savings,
            "savings_percent": round(savings_percent, 2)
        }
