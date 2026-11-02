"""
Section Calculations Coordinators

Specialized coordinators that orchestrate common calculation patterns used across section calculations.
These coordinators reuse existing services and utilities to avoid code duplication.

Architecture:
- ValuationCalculationCoordinator: Common valuation calculation patterns (revenue, EBITDA, DCF, multiples)
- DataCompletenessCoordinator: Data completeness checks and validation
- IndustryAnalysisCoordinator: Industry comparison and benchmark operations
"""

from .valuation_calculation_coordinator import ValuationCalculationCoordinator
from .data_completeness_coordinator import DataCompletenessCoordinator
from .industry_analysis_coordinator import IndustryAnalysisCoordinator

__all__ = [
    'ValuationCalculationCoordinator',
    'DataCompletenessCoordinator',
    'IndustryAnalysisCoordinator',
]
