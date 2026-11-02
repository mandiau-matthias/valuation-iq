"""
Citation Formatter

Formats academic citations in various styles (APA, Chicago, Harvard, MLA).

Author: Upswitch CTO Team
Date: December 2025
Status: Production Ready
"""

from typing import Dict, Any
from src.services.academic.models import AcademicSource, CitationStyle, SourceType


class CitationFormatter:
    """
    Formatter for academic citations in multiple styles
    """
    
    @staticmethod
    def format_citation(source: AcademicSource, style: CitationStyle = CitationStyle.APA) -> str:
        """
        Format citation in specified style
        
        Args:
            source: Academic source to format
            style: Citation style
            
        Returns:
            Formatted citation string
        """
        if style == CitationStyle.APA:
            return CitationFormatter._format_apa(source)
        elif style == CitationStyle.CHICAGO:
            return CitationFormatter._format_chicago(source)
        elif style == CitationStyle.HARVARD:
            return CitationFormatter._format_harvard(source)
        elif style == CitationStyle.MLA:
            return CitationFormatter._format_mla(source)
        else:
            return CitationFormatter._format_apa(source)  # Default to APA
    
    @staticmethod
    def _format_apa(source: AcademicSource) -> str:
        """Format in APA 7th edition style"""
        citation = f"{source.author} ({source.year}). *{source.title}*."
        
        if source.source_type == SourceType.PEER_REVIEWED_JOURNAL and source.journal:
            citation += f" *{source.journal}*"
            if source.volume:
                citation += f", *{source.volume}*"
            if source.pages:
                citation += f", {source.pages}"
        elif source.publisher:
            citation += f" {source.publisher}"
        
        if source.doi:
            citation += f" https://doi.org/{source.doi}"
        elif source.url:
            citation += f" {source.url}"
        
        citation += "."
        return citation
    
    @staticmethod
    def _format_chicago(source: AcademicSource) -> str:
        """Format in Chicago Manual of Style"""
        citation = f"{source.author}. *{source.title}*."
        
        if source.source_type == SourceType.PEER_REVIEWED_JOURNAL and source.journal:
            citation += f" *{source.journal}*"
            if source.volume:
                citation += f" {source.volume}"
            citation += f" ({source.year})"
            if source.pages:
                citation += f": {source.pages}"
        elif source.publisher:
            citation += f" {source.publisher}, {source.year}"
        
        citation += "."
        return citation
    
    @staticmethod
    def _format_harvard(source: AcademicSource) -> str:
        """Format in Harvard style"""
        citation = f"{source.author} {source.year}, '{source.title}'"
        
        if source.source_type == SourceType.PEER_REVIEWED_JOURNAL and source.journal:
            citation += f", *{source.journal}*"
            if source.volume:
                citation += f", vol. {source.volume}"
            if source.pages:
                citation += f", pp. {source.pages}"
        elif source.publisher:
            citation += f", {source.publisher}"
        
        citation += "."
        return citation
    
    @staticmethod
    def _format_mla(source: AcademicSource) -> str:
        """Format in MLA 9th edition style"""
        # Extract last name (simplified)
        author_parts = source.author.split(',')
        if len(author_parts) > 1:
            citation = f"{author_parts[0]}, {author_parts[1].strip()}."
        else:
            citation = f"{source.author}."
        
        citation += f" \"{source.title}.\""
        
        if source.source_type == SourceType.PEER_REVIEWED_JOURNAL and source.journal:
            citation += f" *{source.journal}*"
            if source.volume:
                citation += f", vol. {source.volume}"
            if source.year:
                citation += f", {source.year}"
            if source.pages:
                citation += f", pp. {source.pages}"
        elif source.publisher:
            citation += f" {source.publisher}, {source.year}"
        
        citation += "."
        return citation
    
    @staticmethod
    def format_inline_citation(source: AcademicSource, style: CitationStyle = CitationStyle.APA) -> str:
        """
        Format short inline citation
        
        Args:
            source: Academic source
            style: Citation style
            
        Returns:
            Short inline citation (e.g., "(Damodaran, 2012)")
        """
        # Extract last name for inline citation
        author_last = source.author.split(',')[0].split('&')[0].strip()
        
        if style in [CitationStyle.APA, CitationStyle.HARVARD]:
            return f"({author_last}, {source.year})"
        elif style == CitationStyle.CHICAGO:
            return f"({author_last} {source.year})"
        elif style == CitationStyle.MLA:
            return f"({author_last})"
        else:
            return f"({author_last}, {source.year})"

