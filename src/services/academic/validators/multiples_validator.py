"""
Multiples Validator

Validates EBITDA and revenue multiples against academic standards.

Author: Upswitch CTO Team
Date: December 2025
"""

from decimal import Decimal
from typing import Dict, Any
from src.services.academic.validation_rules import VALIDATION_RULES_REGISTRY


class MultiplesValidator:
    """Validator for multiples-based valuation"""
    
    @staticmethod
    def validate_ebitda_multiple(multiple: float, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate EBITDA multiple"""
        result = VALIDATION_RULES_REGISTRY.EBITDA_MULTIPLE_RANGE.validate(multiple, context)
        
        # Additional SME-specific validation
        sme_result = VALIDATION_RULES_REGISTRY.EBITDA_MULTIPLE_SME_RANGE.validate(multiple, context)
        if not sme_result['passed']:
            result['warnings'].extend(sme_result['errors'])
        
        return result
    
    @staticmethod
    def validate_revenue_multiple(multiple: float, industry: str = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate revenue multiple"""
        result = VALIDATION_RULES_REGISTRY.REVENUE_MULTIPLE_RANGE.validate(multiple, context)
        
        # Industry-specific validation
        if industry and 'saas' in industry.lower():
            saas_result = VALIDATION_RULES_REGISTRY.REVENUE_MULTIPLE_SAAS_RANGE.validate(multiple, context)
            if not saas_result['passed']:
                result['errors'].extend(saas_result['errors'])
                result['passed'] = False
        
        return result
    
    @staticmethod
    def validate_sme_ebitda_multiple(multiple: float, revenue: float = None, market: str = 'general', context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate SME-specific EBITDA multiple with market consideration"""
        # General SME range
        result = VALIDATION_RULES_REGISTRY.EBITDA_MULTIPLE_SME_RANGE.validate(multiple, context)
        
        # Belgian/European market validation
        if market and market.lower() in ['belgian', 'belgium', 'european', 'europe']:
            belgian_result = VALIDATION_RULES_REGISTRY.BELGIAN_SME_EBITDA_MULTIPLE.validate(multiple, context)
            if not belgian_result['passed']:
                result['warnings'].append(f"Belgian market multiples typically 4.0x-8.0x (VFB/Vlerick research)")
        
        # Transaction database comparison
        transaction_result = VALIDATION_RULES_REGISTRY.SME_TRANSACTION_EBITDA_MULTIPLE.validate(multiple, context)
        if not transaction_result['passed']:
            result['warnings'].append(f"Actual SME transactions show 3.5x-7.5x multiples (Pepperdine/BizComps)")
        
        return result
    
    @staticmethod
    def validate_sme_transaction_multiple(ebitda_multiple: float = None, revenue_multiple: float = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate multiples against SME transaction databases"""
        results = {'passed': True, 'errors': [], 'warnings': []}
        
        if ebitda_multiple is not None:
            ebitda_result = VALIDATION_RULES_REGISTRY.SME_TRANSACTION_EBITDA_MULTIPLE.validate(ebitda_multiple, context)
            if not ebitda_result['passed']:
                results['errors'].extend(ebitda_result['errors'])
                results['passed'] = False
            results['warnings'].extend(ebitda_result.get('warnings', []))
        
        if revenue_multiple is not None:
            revenue_result = VALIDATION_RULES_REGISTRY.SME_TRANSACTION_REVENUE_MULTIPLE.validate(revenue_multiple, context)
            if not revenue_result['passed']:
                results['errors'].extend(revenue_result['errors'])
                results['passed'] = False
            results['warnings'].extend(revenue_result.get('warnings', []))
        
        return results

