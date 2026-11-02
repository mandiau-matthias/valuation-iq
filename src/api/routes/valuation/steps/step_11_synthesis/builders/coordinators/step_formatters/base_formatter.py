"""
Base Formatter

Base class for step-specific formatters.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from src.utils.logging import get_logger

from ..types import StepOutput, PreviousResults

logger = get_logger(__name__)


class BaseStepFormatter(ABC):
    """Base class for step-specific formatters."""
    
    def __init__(self):
        self.logger = logger
    
    @abstractmethod
    def format(self, template: str, result: StepOutput, previous_results: PreviousResults) -> str:
        """
        Format step description with actual values.
        
        Args:
            template: Description template with placeholders
            result: Step result
            previous_results: All previous step results
            
        Returns:
            Formatted description string
        """
        pass
    
    def ensure_decimal(self, value: Any, field_name: str, default: Decimal) -> Decimal:
        """Ensure value is Decimal type."""
        from ..validation import BankGradeValidator
        return BankGradeValidator.ensure_decimal(value, field_name, default)
