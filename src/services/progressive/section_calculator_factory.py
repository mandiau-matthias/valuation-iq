"""
Section Calculator Factory

Responsibility: Create and manage section-specific calculators.

Single Responsibility: Calculator creation and management only.
"""

from typing import Dict, Any, Optional
from src.utils.logging import get_logger
from src.services.progressive.calculators.industry_helpers import IndustryHelpers
from src.services.progressive.coordinators import (
    ValuationCalculationCoordinator,
    DataCompletenessCoordinator,
    IndustryAnalysisCoordinator,
)

logger = get_logger(__name__)


class SectionCalculatorFactory:
    """
    Factory for creating section-specific calculators.
    
    Single Responsibility: Calculator creation only.
    """

    def __init__(
        self,
        industry_helpers: Optional[IndustryHelpers] = None,
        valuation_coordinator: Optional[ValuationCalculationCoordinator] = None,
        completeness_coordinator: Optional[DataCompletenessCoordinator] = None,
        industry_coordinator: Optional[IndustryAnalysisCoordinator] = None,
    ):
        """
        Initialize factory with injected dependencies
        
        Args:
            industry_helpers: Industry helpers instance
            valuation_coordinator: Valuation calculation coordinator
            completeness_coordinator: Data completeness coordinator
            industry_coordinator: Industry analysis coordinator
        """
        self.industry_helpers = industry_helpers or IndustryHelpers()
        self.valuation_coordinator = valuation_coordinator or ValuationCalculationCoordinator()
        self.completeness_coordinator = completeness_coordinator or DataCompletenessCoordinator()
        self.industry_coordinator = industry_coordinator or IndustryAnalysisCoordinator()
        self.logger = logger

    def create_business_type_info_extractor(self) -> "BusinessTypeInfoExtractor":
        """Create business type info extractor"""
        from .business_type_info_extractor import BusinessTypeInfoExtractor
        return BusinessTypeInfoExtractor()

