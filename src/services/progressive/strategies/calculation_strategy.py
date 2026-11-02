"""
Base Strategy for Section Calculations

Defines the interface for all calculation strategies using the Strategy Pattern.

SOLID PRINCIPLES:
- Single Responsibility: Each strategy calculates ONE section
- Open/Closed: Easy to add new strategies without modification
- Liskov Substitution: All strategies are interchangeable
- Dependency Inversion: Depend on abstraction (CalculationStrategy)

Author: UpSwitch CTO Team
Date: December 9, 2025
Status: Production Ready
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class CalculationStrategy(ABC):
    """
    Abstract base class for section calculation strategies.
    
    DESIGN PATTERN: Strategy Pattern
    
    Each concrete strategy encapsulates the algorithm for calculating
    a specific section of the progressive valuation report.
    
    BANK-GRADE DESIGN:
    - Clear interface contract
    - Type hints for safety
    - Comprehensive docstrings
    - Academic provenance tracking support
    """
    
    @abstractmethod
    async def calculate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate section data.
        
        This method must be implemented by all concrete strategies.
        
        Args:
            context: Conversation context dictionary containing:
                - collected_data: User-provided business data
                - session_id: Session identifier
                - Any other contextual information
                
        Returns:
            Dictionary with section data for template rendering.
            Structure varies by section but typically includes:
                - Calculated values
                - Metadata (timestamp, phase, confidence)
                - Business type information
                - Quick insights or recommendations
                
        Raises:
            ValueError: If required data is missing
            CalculationError: If calculation fails
        """
        pass
    
    def _validate_context(self, context: Dict[str, Any]) -> None:
        """
        Validate that context has required fields.
        
        Override in subclass for section-specific validation.
        
        Args:
            context: Context dictionary to validate
            
        Raises:
            ValueError: If validation fails
        """
        if not isinstance(context, dict):
            raise ValueError(f"Context must be a dictionary, got {type(context)}")
        
        if 'collected_data' not in context:
            raise ValueError("Context must contain 'collected_data'")
