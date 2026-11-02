"""
Academic Source Extractor

Extracts academic sources for steps from provenance tracker.
"""

from typing import List, Dict, Any, Optional

from src.utils.logging import get_logger
from src.utils.exceptions import ExternalServiceError, ValuationEngineError

# WORLD-CLASS: Import academic services for dynamic source display
try:
    from src.services.academic.calculation_provenance_tracker import get_current_tracker
    ACADEMIC_SERVICES_AVAILABLE = True
except ImportError:
    ACADEMIC_SERVICES_AVAILABLE = False
    get_current_tracker = None

logger = get_logger(__name__)


class AcademicSourceExtractor:
    """Extracts academic sources for steps."""

    @staticmethod
    def extract_sources(step_number: int) -> tuple[List[str], Optional[List[Dict[str, Any]]]]:
        """
        Extract academic sources for a step from provenance tracker.

        Args:
            step_number: Step number (0-11)

        Returns:
            Tuple of (academic_source_ids, academic_sources)
            - academic_source_ids: List of source IDs
            - academic_sources: List of source dictionaries or None
        """
        academic_source_ids: List[str] = []
        academic_sources: Optional[List[Dict[str, Any]]] = None

        if not ACADEMIC_SERVICES_AVAILABLE or not get_current_tracker:
            return academic_source_ids, academic_sources

        try:
            tracker = get_current_tracker()
            if not tracker:
                return academic_source_ids, academic_sources

            # Find provenance records for this step
            records = AcademicSourceExtractor._get_records(tracker)

            # Find record for this step
            for record in records:
                if record.step_number == step_number:
                    academic_source_ids = record.academic_source_ids

                    # Get full source details for display
                    if academic_source_ids:
                        academic_sources = AcademicSourceExtractor._build_source_list(
                            tracker, academic_source_ids
                        )
                    break
        except (AttributeError, KeyError, TypeError) as e:
            # Handle data structure errors gracefully
            logger.warning(
                f"Failed to get academic sources for step {step_number}: {e}",
                exc_info=True
            )
        except ExternalServiceError as e:
            # Re-raise external service errors
            logger.error(
                f"External service error getting academic sources for step {step_number}: {e}",
                exc_info=True
            )
            raise
        except ValuationEngineError as e:
            # Re-raise valuation engine errors
            raise

        return academic_source_ids, academic_sources

    @staticmethod
    def _get_records(tracker) -> List:
        """Get provenance records from tracker."""
        if hasattr(tracker, 'get_all_records'):
            return tracker.get_all_records()
        elif hasattr(tracker, 'provenance_records'):
            return tracker.provenance_records
        else:
            return []

    @staticmethod
    def _build_source_list(tracker, academic_source_ids: List[str]) -> List[Dict[str, Any]]:
        """Build list of source dictionaries from source IDs."""
        # Get all used sources from tracker and match by source_id
        used_sources = tracker.get_used_academic_sources()
        source_dict = {source.source_id: source for source in used_sources}

        academic_sources = []
        for source_id in academic_source_ids:
            if source_id in source_dict:
                source = source_dict[source_id]
                academic_sources.append({
                    'source_id': source.source_id,
                    'author': source.author,
                    'year': source.year,
                    'title': source.title,
                    'publisher': getattr(source, 'publisher', None),
                    'pages': getattr(source, 'pages', None),
                    'relevance': getattr(source, 'relevance', None),
                    'citation': (
                        source.format_citation()
                        if hasattr(source, 'format_citation')
                        else f"{source.author} ({source.year})"
                    ),
                })

        return academic_sources

