"""
Confidence Scoring Coordinators Package

This package contains coordinator classes that handle confidence scoring logic,
following the Single Responsibility Principle.

Coordinators:
- FactorCalculationCoordinator: Handles 8-factor confidence calculation
- ComprehensiveAssessmentCoordinator: Handles data completeness, financial health, and market data quality assessments
"""

from .factor_calculation_coordinator import FactorCalculationCoordinator
from .comprehensive_assessment_coordinator import ComprehensiveAssessmentCoordinator

__all__ = [
    "FactorCalculationCoordinator",
    "ComprehensiveAssessmentCoordinator",
]

