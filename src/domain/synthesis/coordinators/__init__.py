"""
Synthesis Coordinators Package

This package contains coordinator classes that handle synthesis logic,
following the Single Responsibility Principle.

Coordinators:
- ValidationCoordinator: Validates calculation results
- RangeCalculationCoordinator: Calculates valuation ranges
- ConfidenceCalculationCoordinator: Calculates confidence scores
- AskingPriceCalculationCoordinator: Calculates asking prices
- SummaryGenerationCoordinator: Generates summaries and notes
- OwnerDependencyCoordinator: Handles owner dependency adjustments
"""

from .validation_coordinator import ValidationCoordinator
from .range_calculation_coordinator import RangeCalculationCoordinator
from .confidence_calculation_coordinator import ConfidenceCalculationCoordinator
from .asking_price_calculation_coordinator import AskingPriceCalculationCoordinator
from .summary_generation_coordinator import SummaryGenerationCoordinator
from .owner_dependency_coordinator import OwnerDependencyCoordinator

__all__ = [
    "ValidationCoordinator",
    "RangeCalculationCoordinator",
    "ConfidenceCalculationCoordinator",
    "AskingPriceCalculationCoordinator",
    "SummaryGenerationCoordinator",
    "OwnerDependencyCoordinator",
]

