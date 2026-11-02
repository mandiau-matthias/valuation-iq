"""
Data Completeness Coordinator

Orchestrates data completeness checks and validation for section calculations.
"""

from typing import Any, Dict, List

from src.utils.core.data_extraction_helpers import (
    extract_ebitda_from_collected_data,
    extract_revenue_from_collected_data,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DataCompletenessCoordinator:
    """
    Coordinates data completeness checks and validation operations.
    """
    
    def __init__(self) -> None:
        self.logger = logger
    
    def calculate_data_completeness(
        self, collected_data: Dict[str, Any], required_fields: List[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate data completeness score.
        
        Args:
            collected_data: Collected data dictionary
            required_fields: List of required field names (defaults to standard set)
            
        Returns:
            Dictionary with completeness data
        """
        if required_fields is None:
            required_fields = [
                'company_name', 'industry', 'revenue', 'ebitda', 'growth_rate',
                'country', 'founding_year', 'employees'
            ]
        
        collected_count = sum(
            1 for field in required_fields if collected_data.get(field) is not None
        )
        data_completeness = int((collected_count / len(required_fields)) * 100)
        
        return {
            'data_completeness': data_completeness,
            'data_collected': collected_count,
            'data_total': len(required_fields),
            'missing_fields': [
                field for field in required_fields if collected_data.get(field) is None
            ],
        }
    
    def has_minimum_data_for_valuation(self, collected_data: Dict[str, Any]) -> bool:
        """
        Check if minimum data exists for basic valuation.
        
        Args:
            collected_data: Collected data dictionary
            
        Returns:
            True if minimum data exists, False otherwise
        """
        revenue_decimal, has_revenue = extract_revenue_from_collected_data(collected_data)
        return has_revenue and revenue_decimal > 0
    
    def has_data_for_ebitda_valuation(self, collected_data: Dict[str, Any]) -> bool:
        """
        Check if data exists for EBITDA-based valuation.
        
        Args:
            collected_data: Collected data dictionary
            
        Returns:
            True if EBITDA data exists, False otherwise
        """
        ebitda_decimal, has_ebitda = extract_ebitda_from_collected_data(collected_data)
        return has_ebitda and ebitda_decimal and ebitda_decimal > 0
    
    def generate_preliminary_estimate(
        self, collected_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate preliminary value estimate from available data.
        
        Args:
            collected_data: Collected data dictionary
            
        Returns:
            Dictionary with preliminary estimate data
        """
        from decimal import Decimal
        from src.utils.decimal_helpers import from_decimal
        
        revenue_decimal, has_revenue = extract_revenue_from_collected_data(collected_data)
        
        if has_revenue:
            estimated_value_low_decimal = revenue_decimal * Decimal('1.5')
            estimated_value_mid_decimal = revenue_decimal * Decimal('3.0')
            estimated_value_high_decimal = revenue_decimal * Decimal('5.0')
            
            return {
                'estimated_value_low': from_decimal(estimated_value_low_decimal),
                'estimated_value_mid': from_decimal(estimated_value_mid_decimal),
                'estimated_value_high': from_decimal(estimated_value_high_decimal),
                'has_valuation_estimate': True,
            }
        else:
            return {
                'estimated_value_low': None,
                'estimated_value_mid': None,
                'estimated_value_high': None,
                'has_valuation_estimate': False,
            }

