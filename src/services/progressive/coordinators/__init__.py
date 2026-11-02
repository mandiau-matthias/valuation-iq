"""
Progressive Valuation Service Coordinators

Specialized coordinators that orchestrate complex operations within the progressive valuation service.
These coordinators reuse existing services and utilities to avoid code duplication.

Architecture:
- HTMLGenerationCoordinator: Orchestrates HTML generation for instant previews
- MockCalculationCoordinator: Orchestrates mock calculations for development/testing
- SummaryGenerationCoordinator: Orchestrates executive summary and recommendations generation
- ValuationCalculationCoordinator: Common valuation calculation patterns (from section_calculations)
- DataCompletenessCoordinator: Data completeness checks (from section_calculations)
- IndustryAnalysisCoordinator: Industry comparison operations (from section_calculations)
"""

from .html_generation_coordinator import HTMLGenerationCoordinator
from .mock_calculation_coordinator import MockCalculationCoordinator
from .summary_generation_coordinator import SummaryGenerationCoordinator

# Import section calculation coordinators for backwards compatibility
# These are actually in section_calculations/coordinators/ but we re-export them here
try:
    from ..section_calculations.coordinators import (
        ValuationCalculationCoordinator,
        DataCompletenessCoordinator,
        IndustryAnalysisCoordinator,
    )
    _SECTION_CALC_COORDINATORS_AVAILABLE = True
except ImportError:
    # Fallback if section_calculations coordinators aren't available
    ValuationCalculationCoordinator = None
    DataCompletenessCoordinator = None
    IndustryAnalysisCoordinator = None
    _SECTION_CALC_COORDINATORS_AVAILABLE = False

__all__ = [
    'HTMLGenerationCoordinator',
    'MockCalculationCoordinator',
    'SummaryGenerationCoordinator',
    'ValuationCalculationCoordinator',
    'DataCompletenessCoordinator',
    'IndustryAnalysisCoordinator',
]

