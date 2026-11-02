"""
Metadata Extractor

Extracts <head> section and document metadata from HTML.

Single Responsibility:
    Parse HTML to extract document metadata
"""

from typing import Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


class MetadataExtractor:
    """
    Extracts document metadata from HTML.
    
    Responsible for:
        - Extracting <head> section
        - Extracting DOCTYPE
        - Preserving scripts and styles
    """
    
    def extract_head(self, html: str) -> str:
        """
        Extract <head> section from HTML.
        
        Args:
            html: Original HTML string
        
        Returns:
            <head>...</head> section including tags
            Empty string if not found
        
        Example:
            >>> extractor = MetadataExtractor()
            >>> head = extractor.extract_head(html)
            >>> '<head>' in head
            True
        """
        if not html:
            return ""
        
        # Find <head> tags
        start = html.find('<head>')
        end = html.find('</head>')
        
        if start != -1 and end != -1:
            head_section = html[start:end + 7]  # Include </head> tag
            logger.debug(
                "[METADATA-EXTRACTOR] Extracted <head> section",
                extra={"head_length": len(head_section)}
            )
            return head_section
        
        logger.warning("[METADATA-EXTRACTOR] No <head> section found")
        return ""
    
    def extract_doctype(self, html: str) -> str:
        """
        Extract DOCTYPE declaration from HTML.
        
        Args:
            html: Original HTML string
        
        Returns:
            DOCTYPE declaration or default
        """
        if not html:
            return '<!DOCTYPE html>'
        
        # Find DOCTYPE
        if html.strip().startswith('<!DOCTYPE'):
            end = html.find('>')
            if end != -1:
                return html[:end + 1]
        
        return '<!DOCTYPE html>'
    
    def extract_html_attributes(self, html: str) -> str:
        """
        Extract attributes from <html> tag.
        
        Args:
            html: Original HTML string
        
        Returns:
            Attributes string (e.g., 'lang="en"')
        """
        start = html.find('<html')
        if start == -1:
            return 'lang="en"'
        
        end = html.find('>', start)
        if end == -1:
            return 'lang="en"'
        
        html_tag = html[start:end]
        
        # Extract attributes (simple regex-free approach)
        if 'lang=' in html_tag:
            lang_start = html_tag.find('lang=')
            lang_end = html_tag.find(' ', lang_start)
            if lang_end == -1:
                lang_end = len(html_tag)
            return html_tag[lang_start:lang_end].strip()
        
        return 'lang="en"'






