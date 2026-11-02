"""
DCF Validator

Validates DCF parameters against academic standards.

Author: Upswitch CTO Team
Date: December 2025
"""

from typing import Dict, Any
from src.services.academic.validation_rules import VALIDATION_RULES_REGISTRY


class DCFValidator:
    """Validator for DCF valuation"""
    
    @staticmethod
    def validate_terminal_growth_rate(growth_rate: float, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate terminal growth rate"""
        return VALIDATION_RULES_REGISTRY.DCF_TERMINAL_GROWTH_RATE.validate(growth_rate, context)
    
    @staticmethod
    def validate_wacc(wacc: float, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate WACC"""
        return VALIDATION_RULES_REGISTRY.DCF_WACC_RANGE.validate(wacc, context)
    
    @staticmethod
    def validate_beta(beta: float, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate beta"""
        return VALIDATION_RULES_REGISTRY.DCF_BETA_RANGE.validate(beta, context)
    
    # === SME-SPECIFIC DCF VALIDATORS ===
    
    @staticmethod
    def validate_sme_wacc(wacc: float, revenue: float = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate SME WACC with size premium consideration"""
        # Use SME-specific range (12-25%)
        result = VALIDATION_RULES_REGISTRY.SME_WACC_RANGE.validate(wacc, context)
        
        # Add guidance based on company size
        if revenue:
            if revenue < 1_000_000 and wacc < 0.18:
                result['warnings'].append(
                    f"Micro SMEs (<€1M) typically have WACC of 18-25% due to high risk (per Trugman 2017)"
                )
            elif revenue > 10_000_000 and wacc > 0.18:
                result['warnings'].append(
                    f"Medium SMEs (>€10M) typically have WACC of 12-18% (per Duff & Phelps 2024)"
                )
        
        # Below sector-band floor: advisory warning only (sector bands may be 8–13%).
        if 0.08 <= wacc < 0.12:
            result['warnings'].append(
                "WACC below 12% — verify against sector band and size premium (SME guidance 12–25%)."
            )
        elif wacc < 0.08:
            result['errors'].append(
                "WACC below 8% — outside defensible range for private SME valuations."
            )
            result['passed'] = False

        return result

