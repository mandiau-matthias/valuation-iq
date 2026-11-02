"""
Summary Generation Coordinators Package

This package contains coordinator classes that handle summary generation logic,
following the Single Responsibility Principle.

Coordinators:
- SummaryGenerationCoordinator: Handles summary text generation
- ValueDriversExtractionCoordinator: Handles value drivers extraction
- RiskFactorsExtractionCoordinator: Handles risk factors extraction
- MethodologyNotesCoordinator: Handles methodology notes generation
"""

from .summary_generation_coordinator import SummaryGenerationCoordinator
from .value_drivers_extraction_coordinator import ValueDriversExtractionCoordinator
from .risk_factors_extraction_coordinator import RiskFactorsExtractionCoordinator
from .methodology_notes_coordinator import MethodologyNotesCoordinator

__all__ = [
    "SummaryGenerationCoordinator",
    "ValueDriversExtractionCoordinator",
    "RiskFactorsExtractionCoordinator",
    "MethodologyNotesCoordinator",
]

