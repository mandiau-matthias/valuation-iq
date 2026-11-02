"""
Calculation Provenance Tracker

Runtime tracking of which methodologies are used in each valuation.
Builds complete audit trail from methodology selection → calculation → academic source.

Author: Upswitch CTO Team
Date: December 2025
Status: Production Ready
"""

from collections import defaultdict
from datetime import datetime
from threading import RLock
from typing import Any, Dict, List, Optional
import uuid

from src.services.academic.models import ProvenanceRecord, AcademicSource
from src.services.academic.academic_metadata_service import get_academic_metadata_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CalculationProvenanceTracker:
    """
    Tracks calculation provenance during valuation execution

    For each valuation, maintains:
    - List of calculations performed
    - Academic sources used for each calculation
    - Inputs and outputs of each calculation
    - Validation results
    - Complete audit trail
    """

    def __init__(self, valuation_id: Optional[str] = None):
        """
        Initialize provenance tracker

        Args:
            valuation_id: Optional ID of valuation being tracked
        """
        self.valuation_id = valuation_id or str(uuid.uuid4())
        self.provenance_records: List[ProvenanceRecord] = []
        self.calculation_count: Dict[str, int] = defaultdict(int)
        self.academic_metadata_service = get_academic_metadata_service()
        self.start_time = datetime.now()
        self.logger = logger
        self._records_lock = RLock()

        # DEBUG: dup of "[ACADEMIC] Provenance tracking initialized" emitted
        # by the orchestrator; the valuation_id appears in every other
        # request-scoped INFO line.
        self.logger.debug(
            f"Calculation Provenance Tracker initialized for valuation {self.valuation_id}"
        )

    def record_calculation(
        self,
        calculation_id: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        section_name: Optional[str] = None,
        step_number: Optional[int] = None,
        validation_results: Optional[List[Dict[str, Any]]] = None,
    ) -> ProvenanceRecord:
        """
        Record a calculation with its provenance

        Args:
            calculation_id: ID of calculation (links to CalculationMetadata)
            inputs: Input values for calculation
            outputs: Output values from calculation
            section_name: Section name where calculation occurred
            step_number: Step number in valuation process
            validation_results: Results from academic validation

        Returns:
            Created ProvenanceRecord
        """
        # Get academic sources for this calculation
        academic_source_ids = []
        metadata = self.academic_metadata_service.get_calculation_metadata(calculation_id)
        if metadata:
            academic_source_ids = [source.source_id for source in metadata.academic_sources]

        with self._records_lock:
            record_id = (
                f"{self.valuation_id}_{calculation_id}_{self.calculation_count[calculation_id]}"
            )
            self.calculation_count[calculation_id] += 1

            # Create provenance record
            record = ProvenanceRecord(
                record_id=record_id,
                calculation_id=calculation_id,
                timestamp=datetime.now(),
                inputs=inputs,
                outputs=outputs,
                academic_source_ids=academic_source_ids,
                validation_results=validation_results or [],
                valuation_id=self.valuation_id,
                section_name=section_name,
                step_number=step_number,
            )

            self.provenance_records.append(record)

        # DEBUG: per-record provenance log; "[ACADEMIC] Validation passed"
        # at the end of the request rolls up the count.
        self.logger.debug(
            f"Recorded calculation: {calculation_id}",
            extra={
                "record_id": record_id,
                "section": section_name,
                "sources_count": len(academic_source_ids),
            },
        )

        return record

    def record_methodology_selection(
        self,
        methodology: str,
        rationale: str,
        confidence_score: float,
        factors: Optional[Dict[str, Any]] = None,
    ):
        """
        Record methodology selection decision

        Args:
            methodology: Selected methodology (DCF, MULTIPLES, etc.)
            rationale: Why this methodology was selected
            confidence_score: Confidence in selection (0-1)
            factors: Factors influencing selection
        """
        self.record_calculation(
            calculation_id="methodology_selection",
            inputs={"methodology": methodology, "factors": factors or {}},
            outputs={
                "selected_methodology": methodology,
                "rationale": rationale,
                "confidence_score": confidence_score,
            },
            section_name="Methodology Selection",
            step_number=0,
        )

    def get_all_records(self) -> List[ProvenanceRecord]:
        """Get all provenance records for this valuation"""
        with self._records_lock:
            return list(self.provenance_records)

    def get_records_by_calculation(self, calculation_id: str) -> List[ProvenanceRecord]:
        """Get all records for a specific calculation"""
        return [
            record for record in self.get_all_records() if record.calculation_id == calculation_id
        ]

    def get_records_by_section(self, section_name: str) -> List[ProvenanceRecord]:
        """Get all records for a specific section"""
        return [record for record in self.get_all_records() if record.section_name == section_name]

    def get_used_academic_sources(self) -> List[AcademicSource]:
        """
        Get all academic sources actually used in this valuation

        Returns:
            List of unique AcademicSource objects
        """
        source_ids_set = set()
        for record in self.get_all_records():
            source_ids_set.update(record.academic_source_ids)

        sources = []
        for source_id in source_ids_set:
            source = self.academic_metadata_service.get_source(source_id)
            if source:
                sources.append(source)

        return sources

    def get_used_calculations(self) -> List[str]:
        """Get list of unique calculation IDs used in this valuation"""
        return list(set(record.calculation_id for record in self.get_all_records()))

    def get_audit_trail(self) -> Dict[str, Any]:
        """
        Get complete audit trail for transparency

        Returns:
            Comprehensive audit trail dictionary
        """
        records = self.get_all_records()
        return {
            "valuation_id": self.valuation_id,
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "total_calculations": len(records),
            "unique_calculations": len(set(record.calculation_id for record in records)),
            "academic_sources_used": len(self.get_used_academic_sources()),
            "calculations_by_section": self._get_calculations_by_section(records),
            "provenance_records": [record.to_dict() for record in records],
        }

    def get_transparency_summary(self) -> Dict[str, Any]:
        """
        Get high-level transparency summary for reports

        Returns:
            Summary dictionary suitable for report inclusion
        """
        records = self.get_all_records()
        used_sources = self.get_used_academic_sources()

        return {
            "total_calculations": len(records),
            "methodologies_used": self._get_methodologies_used(records),
            "academic_sources_count": len(used_sources),
            "academic_sources": [
                {
                    "author": source.author,
                    "year": source.year,
                    "title": source.title,
                    "relevance": source.relevance,
                }
                for source in used_sources
            ],
            "calculation_categories": self._get_calculation_categories(records),
            "confidence_levels": self._get_confidence_levels(records),
        }

    def _get_calculations_by_section(
        self, records: Optional[List[ProvenanceRecord]] = None
    ) -> Dict[str, int]:
        """Count calculations per section"""
        records = records if records is not None else self.get_all_records()
        counts: Dict[str, int] = defaultdict(int)
        for record in records:
            if record.section_name:
                counts[record.section_name] += 1
        return dict(counts)

    def _get_methodologies_used(
        self, records: Optional[List[ProvenanceRecord]] = None
    ) -> List[str]:
        """Get list of methodologies used"""
        records = records if records is not None else self.get_all_records()
        methodologies = set()
        for record in records:
            metadata = self.academic_metadata_service.get_calculation_metadata(
                record.calculation_id
            )
            if metadata and metadata.category:
                methodologies.add(metadata.category)
        return list(methodologies)

    def _get_calculation_categories(
        self, records: Optional[List[ProvenanceRecord]] = None
    ) -> Dict[str, int]:
        """Count calculations by category"""
        records = records if records is not None else self.get_all_records()
        counts: Dict[str, int] = defaultdict(int)
        for record in records:
            metadata = self.academic_metadata_service.get_calculation_metadata(
                record.calculation_id
            )
            if metadata and metadata.category:
                counts[metadata.category] += 1
        return dict(counts)

    def _get_confidence_levels(
        self, records: Optional[List[ProvenanceRecord]] = None
    ) -> Dict[str, int]:
        """Count calculations by confidence level"""
        records = records if records is not None else self.get_all_records()
        counts: Dict[str, int] = defaultdict(int)
        for record in records:
            metadata = self.academic_metadata_service.get_calculation_metadata(
                record.calculation_id
            )
            if metadata:
                confidence = metadata.confidence_level.value
                counts[confidence] += 1
        return dict(counts)

    def export_to_dict(self) -> Dict[str, Any]:
        """Export complete tracker state to dictionary"""
        return {
            "valuation_id": self.valuation_id,
            "audit_trail": self.get_audit_trail(),
            "transparency_summary": self.get_transparency_summary(),
            "used_sources": [source.to_dict() for source in self.get_used_academic_sources()],
        }


# Async-safe per-request storage using contextvars (not a global variable).
# Each asyncio Task (i.e. each concurrent request) gets its own tracker instance,
# preventing cross-request data leakage under concurrent load.
from contextvars import ContextVar

_current_tracker_var: ContextVar[Optional[CalculationProvenanceTracker]] = ContextVar(
    "current_provenance_tracker", default=None
)


def get_current_tracker() -> Optional[CalculationProvenanceTracker]:
    """Get current provenance tracker (async-safe, per-request)."""
    return _current_tracker_var.get()


def set_current_tracker(tracker: Optional[CalculationProvenanceTracker]):
    """Set current provenance tracker (async-safe, per-request)."""
    _current_tracker_var.set(tracker)


def create_tracker(valuation_id: Optional[str] = None) -> CalculationProvenanceTracker:
    """Create and set new provenance tracker for the current async context."""
    tracker = CalculationProvenanceTracker(valuation_id)
    set_current_tracker(tracker)
    return tracker


def record_calculation_safe(
    calculation_id: str,
    value: Any,
    *,
    step_number: Optional[int] = None,
    section_name: Optional[str] = None,
    inputs: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Record a calculation against the current per-request tracker if one exists.

    Single value -> `outputs={"value": value}` so AcademicValidationEngine's
    `validate_from_provenance` picks it up. Never raises: the validation
    infrastructure is observability-only and must not break a valuation run.
    """
    tracker = get_current_tracker()
    if tracker is None:
        return
    try:
        tracker.record_calculation(
            calculation_id=calculation_id,
            inputs=inputs or {},
            outputs={"value": value},
            section_name=section_name,
            step_number=step_number,
        )
    except Exception as exc:  # noqa: BLE001 — non-fatal observability path
        logger.warning(
            "record_calculation_safe failed (non-fatal)",
            extra={"calculation_id": calculation_id, "error": str(exc)},
        )
