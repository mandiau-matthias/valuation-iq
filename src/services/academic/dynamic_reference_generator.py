"""
Dynamic Academic Reference Generator

Generates academic references ONLY for methodologies actually used in specific valuation.
Replaces static reference approach with dynamic, context-aware citations.

Author: Upswitch CTO Team
Date: December 2025
Status: Production Ready
"""

from collections import defaultdict
from threading import Lock
from typing import Dict, List, Any, Optional, Set

from src.services.academic.models import AcademicSource, Citation, CitationStyle
from src.services.academic.academic_metadata_service import get_academic_metadata_service
from src.services.academic.calculation_provenance_tracker import CalculationProvenanceTracker
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DynamicReferenceGenerator:
    """
    Generates academic references dynamically based on actual usage
    
    Creates:
    - Inline citations
    - Section footnotes
    - Comprehensive bibliography
    - Only includes sources actually used in valuation
    """
    
    def __init__(self):
        """Initialize dynamic reference generator"""
        self.academic_service = get_academic_metadata_service()
        self.logger = logger
        self.logger.info("Dynamic Reference Generator initialized")
    
    def generate_citations_from_tracker(
        self,
        tracker: CalculationProvenanceTracker,
        style: CitationStyle = CitationStyle.APA
    ) -> Dict[str, Any]:
        """
        Generate all citations from provenance tracker
        
        Args:
            tracker: Calculation provenance tracker
            style: Citation style to use
            
        Returns:
            Dictionary with citations, footnotes, and bibliography
        """
        self.logger.info(f"Generating citations for valuation {tracker.valuation_id}")
        
        # Get all used sources
        used_sources = tracker.get_used_academic_sources()
        
        # Group sources by calculation
        sources_by_calculation = self._group_sources_by_calculation(tracker)
        
        # Generate citations
        citations = self._generate_citations(used_sources, sources_by_calculation, style)
        
        # Generate bibliography
        bibliography = self._generate_bibliography(used_sources, style)
        
        # Generate section footnotes
        footnotes_by_section = self._generate_section_footnotes(tracker, citations)
        
        return {
            'citations': citations,
            'bibliography': bibliography,
            'footnotes_by_section': footnotes_by_section,
            'total_sources': len(used_sources),
            'style': style.value
        }
    
    def generate_citations_from_calculations(
        self,
        calculation_ids: List[str],
        style: CitationStyle = CitationStyle.APA
    ) -> Dict[str, Any]:
        """
        Generate citations for specific calculations
        
        Args:
            calculation_ids: List of calculation IDs
            style: Citation style to use
            
        Returns:
            Dictionary with citations and bibliography
        """
        # Collect all sources for these calculations
        sources_set: Set[str] = set()
        sources_by_calculation: Dict[str, List[str]] = defaultdict(list)
        
        for calc_id in calculation_ids:
            sources = self.academic_service.get_sources_for_calculation(calc_id)
            for source in sources:
                sources_set.add(source.source_id)
                sources_by_calculation[calc_id].append(source.source_id)
        
        # Get source objects
        used_sources = [
            self.academic_service.get_source(source_id)
            for source_id in sources_set
            if self.academic_service.get_source(source_id)
        ]
        
        # Generate citations
        citations = self._generate_citations(used_sources, sources_by_calculation, style)
        
        # Generate bibliography
        bibliography = self._generate_bibliography(used_sources, style)
        
        return {
            'citations': citations,
            'bibliography': bibliography,
            'total_sources': len(used_sources),
            'style': style.value
        }
    
    def _generate_citations(
        self,
        sources: List[AcademicSource],
        sources_by_calculation: Dict[str, List[str]],
        style: CitationStyle
    ) -> List[Citation]:
        """Generate Citation objects"""
        citations = []
        
        # Sort sources by author and year for consistent numbering
        sorted_sources = sorted(sources, key=lambda s: (s.author, s.year))
        
        for idx, source in enumerate(sorted_sources, start=1):
            # Find calculations using this source
            calc_ids = [
                calc_id for calc_id, source_ids in sources_by_calculation.items()
                if source.source_id in source_ids
            ]
            
            citation = Citation(
                citation_id=f"cite_{source.source_id}",
                academic_source=source,
                citation_number=idx,
                calculation_ids=calc_ids
            )
            citations.append(citation)
        
        return citations
    
    def _generate_bibliography(
        self,
        sources: List[AcademicSource],
        style: CitationStyle
    ) -> List[Dict[str, Any]]:
        """Generate bibliography entries"""
        # Sort by author and year
        sorted_sources = sorted(sources, key=lambda s: (s.author, s.year))
        
        bibliography = []
        for idx, source in enumerate(sorted_sources, start=1):
            bibliography.append({
                'number': idx,
                'source_id': source.source_id,
                'citation': source.format_citation(style),
                'author': source.author,
                'year': source.year,
                'title': source.title,
                'relevance': source.relevance,
                'source_type': source.source_type.value
            })
        
        return bibliography
    
    def _generate_section_footnotes(
        self,
        tracker: CalculationProvenanceTracker,
        citations: List[Citation]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Generate footnotes organized by section"""
        footnotes_by_section: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # Create citation lookup
        citation_lookup = {cite.academic_source.source_id: cite for cite in citations}
        
        # Group by section
        for record in tracker.get_all_records():
            if not record.section_name:
                continue
            
            for source_id in record.academic_source_ids:
                if source_id in citation_lookup:
                    cite = citation_lookup[source_id]
                    
                    # Check if already added to this section
                    existing = [
                        f for f in footnotes_by_section[record.section_name]
                        if f['source_id'] == source_id
                    ]
                    
                    if not existing:
                        footnotes_by_section[record.section_name].append({
                            'number': cite.citation_number,
                            'source_id': source_id,
                            'citation': cite.format(inline=False),
                            'calculation_id': record.calculation_id
                        })
        
        return dict(footnotes_by_section)
    
    def _group_sources_by_calculation(
        self,
        tracker: CalculationProvenanceTracker
    ) -> Dict[str, List[str]]:
        """Group source IDs by calculation ID"""
        sources_by_calculation: Dict[str, List[str]] = defaultdict(list)
        
        for record in tracker.get_all_records():
            for source_id in record.academic_source_ids:
                if source_id not in sources_by_calculation[record.calculation_id]:
                    sources_by_calculation[record.calculation_id].append(source_id)
        
        return dict(sources_by_calculation)
    
    def generate_inline_citation_html(
        self,
        citation: Citation,
        text: str
    ) -> str:
        """
        Generate HTML for inline citation
        
        Args:
            citation: Citation object
            text: Text to append citation to
            
        Returns:
            HTML string with inline citation
        """
        return (
            f'{text}'
            f'<sup><a href="#ref-{citation.academic_source.source_id}" '
            f'class="citation-link">{citation.citation_number}</a></sup>'
        )
    
    def generate_footnote_html(
        self,
        citations: List[Citation],
        section_name: str
    ) -> str:
        """
        Generate HTML for section footnotes
        
        Args:
            citations: List of citations for this section
            section_name: Section name
            
        Returns:
            HTML string with footnotes
        """
        if not citations:
            return ""
        
        html = f'<div class="section-footnotes">\n'
        html += f'  <h4>Academic References for {section_name}</h4>\n'
        html += f'  <ol class="footnote-list">\n'
        
        for citation in sorted(citations, key=lambda c: c.citation_number):
            html += (
                f'    <li id="ref-{citation.academic_source.source_id}" '
                f'class="footnote-item">\n'
                f'      {citation.format(inline=False)}\n'
                f'    </li>\n'
            )
        
        html += '  </ol>\n'
        html += '</div>\n'
        
        return html
    
    def generate_bibliography_html(
        self,
        bibliography: List[Dict[str, Any]]
    ) -> str:
        """
        Generate HTML for complete bibliography
        
        Args:
            bibliography: Bibliography entries
            
        Returns:
            HTML string with complete bibliography
        """
        if not bibliography:
            return ""
        
        html = '<div class="bibliography">\n'
        html += '  <h3>Academic References</h3>\n'
        html += '  <p class="bibliography-intro">'
        html += 'This valuation is based on the following academic sources and professional methodologies:'
        html += '</p>\n'
        html += '  <ol class="bibliography-list">\n'
        
        for entry in bibliography:
            html += f'    <li id="ref-{entry["source_id"]}" class="bibliography-item">\n'
            html += f'      <strong>{entry["citation"]}</strong>\n'
            if entry.get('relevance'):
                html += f'      <br><em>Relevance: {entry["relevance"]}</em>\n'
            html += '    </li>\n'
        
        html += '  </ol>\n'
        html += '</div>\n'
        
        return html


# Global singleton instance
_reference_generator: Optional[DynamicReferenceGenerator] = None
_reference_generator_lock = Lock()


def get_reference_generator() -> DynamicReferenceGenerator:
    """Get or create the thread-safe singleton reference generator."""
    global _reference_generator
    if _reference_generator is None:
        with _reference_generator_lock:
            if _reference_generator is None:
                _reference_generator = DynamicReferenceGenerator()
    return _reference_generator


def get_references_for_report(
    tracker: Optional[CalculationProvenanceTracker] = None,
    calculation_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Convenience function to get references for report
    
    Args:
        tracker: Optional provenance tracker
        calculation_ids: Optional list of calculation IDs
        
    Returns:
        References dictionary
    """
    generator = get_reference_generator()
    
    if tracker:
        return generator.generate_citations_from_tracker(tracker)
    elif calculation_ids:
        return generator.generate_citations_from_calculations(calculation_ids)
    else:
        # Return empty references
        return {
            'citations': [],
            'bibliography': [],
            'footnotes_by_section': {},
            'total_sources': 0,
            'style': 'apa'
        }
