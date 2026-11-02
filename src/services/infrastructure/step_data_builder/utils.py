"""
Utility functions for step data builder.

These are separated to avoid circular import issues.
"""

from typing import Dict, Any


def ensure_step_outputs_defaults(outputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure all template-accessed fields exist in outputs dictionary with safe defaults.
    
    This prevents Jinja2 Undefined errors when templates access nested paths.
    
    Args:
        outputs: Step outputs dictionary (may be empty or missing fields)
        
    Returns:
        Dictionary with all required fields initialized to None or safe defaults
    """
    if not isinstance(outputs, dict):
        outputs = {}
    
    # Common fields accessed in templates across all steps
    common_fields = {
        'discount_percentage': None,
        'adjustment_percentage': None,
        'adjusted_enterprise_value': None,
        'adjusted_enterprise_value_low': None,
        'adjusted_enterprise_value_high': None,
        'enterprise_value_low': None,
        'enterprise_value_mid': None,
        'enterprise_value_high': None,
        'equity_value_low': None,
        'equity_value_mid': None,
        'equity_value_high': None,
        'risk_level': None,
        'size_category': None,
        'size_discount_percentage': None,
        'liquidity_discount_percentage': None,
        'owner_concentration_adjustment': None,
        'owner_employee_ratio': None,
        'normalized_ratio': None,
        'overall_score': None,
        'confidence_score': None,
        'base_spread': None,
        'spread_percentage': None,
        'p25_multiple': None,
        'p50_multiple': None,
        'p75_multiple': None,
        'ebitda_multiple_p25': None,
        'ebitda_multiple_median': None,
        'ebitda_multiple_p75': None,
        'revenue_multiple_p25': None,
        'revenue_multiple_median': None,
        'revenue_multiple_p75': None,
        'initial_multiple': None,
        'unadjusted_multiple': None,
        'calibration_factor': None,
        'margin_premium': None,
        'revenue_growth_rate': None,
        'ebitda_growth_rate': None,
        'average_ebitda_margin': None,
        # BANK-GRADE: Add business_type_characteristics to prevent UndefinedError
        'business_type_characteristics': {
            'multiples_preference': None,
            'owner_dependency_impact': None,
            'typical_ebitda_margin_median': None,
        },
    }
    
    # Set defaults for all common fields if they don't exist
    for field, default_value in common_fields.items():
        if field not in outputs:
            outputs[field] = default_value
    
    return outputs

