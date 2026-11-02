"""
Transparency Tracker Protocol

Protocol definition for transparency tracking.
This allows domain layer to track calculations without
depending on service layer implementations.
"""

from typing import Protocol, Optional, Any, Dict, List
from decimal import Decimal
from datetime import datetime


class TransparencyTrackerProtocol(Protocol):
    """Protocol for transparency tracker."""
    
    def track_calculation(
        self,
        step_name: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        formula: Optional[str] = None,
        sources: Optional[List[str]] = None,
    ) -> None:
        """
        Track a calculation step.
        
        Args:
            step_name: Name of the calculation step
            inputs: Input values
            outputs: Output values
            formula: Optional formula used
            sources: Optional data sources
        """
        ...
    
    def get_transparency_data(self) -> Dict[str, Any]:
        """
        Get all transparency data.
        
        Returns:
            Dictionary with transparency data
        """
        ...

