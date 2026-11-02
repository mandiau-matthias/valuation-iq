"""
Multiples Engine Coordinators

Specialized coordinators that orchestrate complex operations within the multiples engine.
These coordinators reuse existing services and utilities to avoid code duplication.

Architecture:
- MarketMultiplesRetrievalCoordinator: Orchestrates market multiples retrieval from comparables or benchmarks
- DiscountCalculationCoordinator: Orchestrates discount and adjustment calculations
- ValuationCalculationCoordinator: Orchestrates weighted EV and equity value calculations
- ConfidenceAssessmentCoordinator: Orchestrates confidence assessment and quality scoring
"""

from .market_multiples_retrieval_coordinator import MarketMultiplesRetrievalCoordinator
from .discount_calculation_coordinator import DiscountCalculationCoordinator
from .valuation_calculation_coordinator import ValuationCalculationCoordinator
from .confidence_assessment_coordinator import ConfidenceAssessmentCoordinator

__all__ = [
    'MarketMultiplesRetrievalCoordinator',
    'DiscountCalculationCoordinator',
    'ValuationCalculationCoordinator',
    'ConfidenceAssessmentCoordinator',
]

