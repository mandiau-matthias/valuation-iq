"""
Discount Validator

Validates discount adjustments against academic standards.

Author: Upswitch CTO Team
Date: December 2025
"""

from typing import Dict, Any
from src.services.academic.validation_rules import VALIDATION_RULES_REGISTRY


class DiscountValidator:
    """Validator for discount adjustments"""
    
    @staticmethod
    def validate_size_discount(discount: float, revenue: float = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate size discount"""
        result = VALIDATION_RULES_REGISTRY.SIZE_DISCOUNT_RANGE.validate(discount, context)
        
        # Additional validation for small SMEs
        if revenue and revenue < 5_000_000:
            small_sme_result = VALIDATION_RULES_REGISTRY.SIZE_DISCOUNT_SMALL_SME.validate(discount, context)
            if not small_sme_result['passed']:
                result['warnings'].extend(small_sme_result['errors'])
        
        return result
    
    @staticmethod
    def validate_owner_dependency_discount(discount: float, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate owner dependency discount"""
        return VALIDATION_RULES_REGISTRY.OWNER_DEPENDENCY_DISCOUNT_RANGE.validate(discount, context)
    
    @staticmethod
    def validate_liquidity_discount(discount: float, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate liquidity discount"""
        return VALIDATION_RULES_REGISTRY.LIQUIDITY_DISCOUNT_RANGE.validate(discount, context)
    
    @staticmethod
    def validate_customer_concentration_discount(discount: float, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate customer concentration discount"""
        return VALIDATION_RULES_REGISTRY.CUSTOMER_CONCENTRATION_DISCOUNT_RANGE.validate(discount, context)
    
    # === SME-SPECIFIC DISCOUNT VALIDATORS ===
    
    @staticmethod
    def validate_sme_private_company_discount(discount: float, revenue: float = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate SME private company discount"""
        result = VALIDATION_RULES_REGISTRY.SME_PRIVATE_COMPANY_DISCOUNT.validate(discount, context)
        
        # Add context-aware warnings
        if revenue:
            if revenue < 1_000_000 and discount < 0.25:
                result['warnings'].append(f"Small SMEs (<€1M) typically require 25%+ private company discount")
            elif revenue > 20_000_000 and discount > 0.20:
                result['warnings'].append(f"Larger SMEs (>€20M) may have lower private company discounts (15-20%)")
        
        return result
    
    @staticmethod
    def validate_sme_marketability_discount(discount: float, owner_concentration: float = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate SME marketability discount"""
        result = VALIDATION_RULES_REGISTRY.SME_MARKETABILITY_DISCOUNT.validate(discount, context)
        
        # Adjust for owner concentration
        if owner_concentration and owner_concentration > 0.8:
            if discount < 0.30:
                result['warnings'].append(f"High owner concentration (>80%) typically requires 30%+ marketability discount")
        
        return result
    
    @staticmethod
    def validate_family_business_discount(discount: float, is_minority: bool = False, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate family business control/minority discount"""
        result = VALIDATION_RULES_REGISTRY.FAMILY_BUSINESS_CONTROL_DISCOUNT.validate(discount, context)
        
        # Only apply if minority stake
        if not is_minority and discount > 0:
            result['warnings'].append(f"Control premiums should not apply to controlling interests")
        
        return result
    
    @staticmethod
    def validate_information_asymmetry_discount(discount: float, has_audit: bool = False, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate information asymmetry discount"""
        result = VALIDATION_RULES_REGISTRY.SME_INFORMATION_ASYMMETRY_DISCOUNT.validate(discount, context)
        
        # Adjust for audit status
        if has_audit and discount > 0.10:
            result['warnings'].append(f"Audited financials reduce information asymmetry discount (typically ≤10%)")
        elif not has_audit and discount < 0.10:
            result['warnings'].append(f"Unaudited SME financials typically require 10%+ information discount")
        
        return result
    
    @staticmethod
    def validate_combined_sme_discounts(discounts: Dict[str, float], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate combined SME discount waterfall to avoid double-counting"""
        results = {'passed': True, 'errors': [], 'warnings': []}
        
        # Calculate total discount
        total_discount = sum(discounts.values())
        
        # Check for excessive total discount
        if total_discount > 0.60:  # 60%
            results['warnings'].append(
                f"Combined discounts of {total_discount:.1%} may include double-counting. "
                f"Verify discount waterfall logic per Trugman (2017)."
            )
        
        # Check for overlapping discounts
        if 'private_company' in discounts and 'marketability' in discounts:
            if discounts['private_company'] > 0 and discounts['marketability'] > 0:
                results['warnings'].append(
                    "Private company discount and marketability discount overlap. "
                    "Use one or the other, not both (per Hitchner 2017)."
                )
        
        return results

