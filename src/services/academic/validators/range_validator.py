"""
Range Validator

Validates valuation range methodology against academic standards.

Author: Upswitch CTO Team
Date: December 2025
"""

from typing import Dict, Any
from src.services.academic.validation_rules import VALIDATION_RULES_REGISTRY


class RangeValidator:
    """Validator for valuation range"""
    
    @staticmethod
    def validate_range_width(range_width: float, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate valuation range width"""
        return VALIDATION_RULES_REGISTRY.VALUATION_RANGE_WIDTH.validate(range_width, context)
    
    @staticmethod
    def validate_confidence_score(confidence: float, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate confidence score"""
        return VALIDATION_RULES_REGISTRY.CONFIDENCE_SCORE_RANGE.validate(confidence, context)

