"""
Section Calculation Orchestrator

Orchestrates section calculation strategies using the Strategy Pattern.

SINGLE RESPONSIBILITY: Route calculation requests to appropriate strategy.
OPEN/CLOSED: Easy to add new strategies without modification.

Author: UpSwitch CTO Team
Date: December 9, 2025
Status: Production Ready
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.progressive.strategies.calculation_strategy import CalculationStrategy
    from src.services.progressive.section_calculations.coordinators import (
        DataCompletenessCoordinator,
        ValuationCalculationCoordinator,
        IndustryAnalysisCoordinator,
    )
    from src.services.progressive.business_type_info_extractor import BusinessTypeInfoExtractor
    from src.services.progressive.calculators.industry_helpers import IndustryHelpers

from src.services.progressive.strategies import (
    InstantOverviewStrategy,
    RevenueAnalysisStrategy,
)

logger = logging.getLogger(__name__)


class SectionCalculationOrchestrator:
    """
    Orchestrates section calculation strategies.
    
    SINGLE RESPONSIBILITY: Route calculation requests to appropriate strategy.
    
    OPEN/CLOSED PRINCIPLE:
    - Open for extension (add new strategies via register_strategy())
    - Closed for modification (no need to change this class)
    
    BANK-GRADE DESIGN:
    - Strategy Pattern for extensibility
    - Registry pattern for dynamic lookup
    - Dependency injection for testability
    - Comprehensive error handling
    - Detailed logging
    """
    
    def __init__(
        self,
        completeness_coordinator: "DataCompletenessCoordinator",
        business_type_extractor: "BusinessTypeInfoExtractor",
        industry_helpers: "IndustryHelpers",
        valuation_coordinator: Optional["ValuationCalculationCoordinator"] = None,
        industry_coordinator: Optional["IndustryAnalysisCoordinator"] = None,
    ):
        """
        Initialize with dependencies.
        
        All dependencies are injected for:
        - Testability (easy to mock)
        - Flexibility (easy to swap implementations)
        - SOLID compliance (dependency inversion)
        
        Args:
            completeness_coordinator: Data completeness coordinator
            business_type_extractor: Business type extractor
            industry_helpers: Industry helpers
            valuation_coordinator: Valuation calculation coordinator (optional)
            industry_coordinator: Industry analysis coordinator (optional)
        """
        self.completeness_coordinator = completeness_coordinator
        self.business_type_extractor = business_type_extractor
        self.industry_helpers = industry_helpers
        self.valuation_coordinator = valuation_coordinator
        self.industry_coordinator = industry_coordinator
        
        # Initialize strategy registry
        self.strategies: Dict[str, "CalculationStrategy"] = {}
        self._register_default_strategies()
    
    def _register_default_strategies(self) -> None:
        """
        Register default calculation strategies.
        
        BANK-GRADE DESIGN:
        - All strategies initialized with proper dependencies
        - Centralized registration for easier maintenance
        """
        # Register available strategies
        self.strategies['instant_overview'] = InstantOverviewStrategy(
            completeness_coordinator=self.completeness_coordinator,
            business_type_extractor=self.business_type_extractor,
        )
        
        self.strategies['revenue_analysis'] = RevenueAnalysisStrategy(
            business_type_extractor=self.business_type_extractor,
            industry_helpers=self.industry_helpers,
        )
        
        # Additional strategies can be registered here as they're implemented
        # self.strategies['industry_comparison'] = IndustryComparisonStrategy(...)
        # self.strategies['ebitda_analysis'] = EBITDAAnalysisStrategy(...)
        # etc.
        
        logger.info(
            f"[ORCHESTRATOR] Registered {len(self.strategies)} calculation strategies"
        )
    
    async def calculate_section(
        self, 
        section_name: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate section data using appropriate strategy.
        
        BANK-GRADE ERROR HANDLING:
        - Validates section name
        - Provides helpful error messages
        - Logs all calculations
        - Graceful error recovery
        
        Args:
            section_name: Name of section to calculate (e.g., 'instant_overview')
            context: Conversation context with collected_data
            
        Returns:
            Dictionary with section data for template rendering
            
        Raises:
            ValueError: If section_name is unknown
            CalculationError: If calculation fails
        """
        logger.info(f"[ORCHESTRATOR] Calculating section: {section_name}")
        
        # Get strategy from registry
        strategy = self.strategies.get(section_name)
        
        if not strategy:
            available = ', '.join(self.strategies.keys())
            error_msg = (
                f"Unknown section: '{section_name}'. "
                f"Available sections: {available}"
            )
            logger.error(f"[ORCHESTRATOR] {error_msg}")
            raise ValueError(error_msg)
        
        # Delegate to strategy
        try:
            result = await strategy.calculate(context)
            logger.info(
                f"[ORCHESTRATOR] Section '{section_name}' calculated successfully"
            )
            return result
            
        except Exception as e:
            logger.error(
                f"[ORCHESTRATOR] Error calculating section '{section_name}': {e}",
                exc_info=True
            )
            raise
    
    def register_strategy(
        self, 
        section_name: str, 
        strategy: "CalculationStrategy"
    ) -> None:
        """
        Register a new calculation strategy.
        
        OPEN/CLOSED PRINCIPLE:
        - Allows adding new strategies WITHOUT modifying orchestrator code
        - Strategies can be registered at runtime
        - Supports dynamic extension
        
        Args:
            section_name: Name of section (e.g., 'custom_analysis')
            strategy: Strategy instance to register
            
        Example:
            ```python
            orchestrator = SectionCalculationOrchestrator(...)
            orchestrator.register_strategy(
                'custom_analysis', 
                CustomAnalysisStrategy(...)
            )
            ```
        """
        logger.info(f"[ORCHESTRATOR] Registering strategy: {section_name}")
        self.strategies[section_name] = strategy
    
    def unregister_strategy(self, section_name: str) -> None:
        """
        Unregister a calculation strategy.
        
        Args:
            section_name: Name of section to unregister
        """
        if section_name in self.strategies:
            logger.info(f"[ORCHESTRATOR] Unregistering strategy: {section_name}")
            del self.strategies[section_name]
    
    def get_available_sections(self) -> list:
        """
        Get list of available section names.
        
        Returns:
            List of section names that can be calculated
        """
        return list(self.strategies.keys())
    
    def is_section_available(self, section_name: str) -> bool:
        """
        Check if section calculation is available.
        
        Args:
            section_name: Name of section to check
            
        Returns:
            True if section can be calculated, False otherwise
        """
        return section_name in self.strategies
    
    def get_strategy_count(self) -> int:
        """
        Get number of registered strategies.
        
        Returns:
            Count of registered strategies
        """
        return len(self.strategies)
