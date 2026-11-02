"""
Sole Trader Detection Utility

Detects and validates sole trader status from multiple data sources.
Used throughout the valuation engine to optimize calculations for sole traders.
"""

from typing import Any, Dict, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


class SoleTraderDetector:
    """
    Utility class for detecting sole trader status.

    Sole traders are identified by:
    1. business_structure == "sole-trader"
    2. business_type == "sole_proprietor" or contains "sole"
    3. number_of_owners == 1 AND (number_of_employees == 0 OR number_of_employees == 1)
    4. Explicit is_sole_trader flag

    Detection is prioritized in this order to handle various input sources.
    """

    @staticmethod
    def detect(
        business_structure: Optional[str] = None,
        business_type: Optional[str] = None,
        number_of_owners: Optional[int] = None,
        number_of_employees: Optional[int] = None,
        is_sole_trader: Optional[bool] = None,
        business_context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Detect if the business is a sole trader.

        Detection priority:
        1. Explicit is_sole_trader flag (highest priority)
        2. business_structure == "sole-trader"
        3. business_type contains "sole" or "sole_proprietor"
        4. number_of_owners == 1 AND (number_of_employees == 0 OR 1)
        5. business_context metadata

        Args:
            business_structure: Business structure type ("sole-trader", "company", etc.)
            business_type: Business type string (may contain "sole_proprietor", etc.)
            number_of_owners: Number of operational owners
            number_of_employees: Number of employees (FTE)
            is_sole_trader: Explicit flag (if provided, takes highest priority)
            business_context: Additional business context dict

        Returns:
            True if sole trader detected, False otherwise
        """
        # Priority 1: Explicit flag (highest priority)
        if is_sole_trader is not None:
            logger.debug("Sole trader detected from explicit flag", is_sole_trader=is_sole_trader)
            return is_sole_trader

        # Priority 2: business_structure field
        if business_structure:
            business_structure_lower = business_structure.lower().strip().replace(" ", "-")
            if business_structure_lower in [
                "sole-trader",
                "sole_trader",
                "soletrader",
                "sole_proprietor",
                "sole-proprietor",
                "soleproprietor",
            ]:
                logger.debug(
                    "Sole trader detected from business_structure",
                    business_structure=business_structure,
                )
                return True

        # Priority 3: business_type field
        if business_type:
            business_type_lower = str(business_type).lower().strip()
            if any(
                keyword in business_type_lower
                for keyword in [
                    "sole_proprietor",
                    "sole-proprietor",
                    "sole proprietor",
                    "sole_trader",
                    "sole-trader",
                    "soletrader",
                    "sole",
                    "self-employed",
                    "self_employed",
                    "freelancer",
                ]
            ):
                logger.debug("Sole trader detected from business_type", business_type=business_type)
                return True

        # Priority 4: Infer from ownership/employee structure
        # Sole traders: 1 owner, 0-1 employees
        if number_of_owners is not None and number_of_employees is not None:
            if number_of_owners == 1 and number_of_employees <= 1:
                logger.debug(
                    "Sole trader inferred from ownership structure",
                    number_of_owners=number_of_owners,
                    number_of_employees=number_of_employees,
                )
                return True

        # Priority 5: Check business_context metadata
        if business_context:
            # Check for explicit sole trader flag in context
            if business_context.get("is_sole_trader") is True:
                logger.debug("Sole trader detected from business_context")
                return True

            # Check for business_structure in context
            context_structure = business_context.get("business_structure")
            if context_structure and isinstance(context_structure, str):
                context_structure_lower = context_structure.lower().strip()
                if context_structure_lower in ["sole-trader", "sole_trader", "soletrader"]:
                    logger.debug("Sole trader detected from business_context.business_structure")
                    return True

        # Default: not a sole trader
        return False

    @staticmethod
    def validate_consistency(
        is_sole_trader: bool,
        number_of_owners: Optional[int] = None,
        number_of_employees: Optional[int] = None,
        business_structure: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate consistency of sole trader status with other fields.

        Validation rules:
        - Sole traders should have number_of_owners == 1 (or None)
        - Sole traders typically have 0-1 employees
        - business_structure should be "sole-trader" if is_sole_trader is True

        Args:
            is_sole_trader: Detected sole trader status
            number_of_owners: Number of owners
            number_of_employees: Number of employees
            business_structure: Business structure type

        Returns:
            Dict with validation results:
            - is_valid: bool
            - warnings: List[str] - warnings about inconsistencies
            - recommendations: List[str] - recommendations for fixes
        """
        warnings = []
        recommendations = []

        if is_sole_trader:
            # Validate number_of_owners
            if number_of_owners is not None and number_of_owners != 1:
                warnings.append(
                    f"Sole trader detected but number_of_owners={number_of_owners} " f"(expected 1)"
                )
                recommendations.append("Set number_of_owners=1 for sole traders")

            # Validate number_of_employees (should be 0-1, but allow flexibility)
            if number_of_employees is not None and number_of_employees > 1:
                warnings.append(
                    f"Sole trader detected but number_of_employees={number_of_employees} "
                    f"(typically 0-1 for sole traders)"
                )
                # Note: This is a warning, not an error (some sole traders have 1 employee)

            # Validate business_structure
            if business_structure and business_structure.lower() not in [
                "sole-trader",
                "sole_trader",
                "soletrader",
            ]:
                warnings.append(
                    f"Sole trader detected but business_structure='{business_structure}' "
                    f"(expected 'sole-trader')"
                )
                recommendations.append("Set business_structure='sole-trader' for consistency")
        else:
            # If not sole trader, check for inconsistencies
            if (
                number_of_owners == 1
                and number_of_employees is not None
                and number_of_employees <= 1
            ):
                # Might be a sole trader but not flagged
                warnings.append(
                    "Business structure suggests sole trader "
                    f"(1 owner, {number_of_employees} employees) but is_sole_trader=False"
                )
                recommendations.append(
                    "Consider setting is_sole_trader=True or business_structure='sole-trader'"
                )

        is_valid = len(warnings) == 0

        result = {"is_valid": is_valid, "warnings": warnings, "recommendations": recommendations}

        if warnings:
            logger.warning(
                "Sole trader validation warnings", is_sole_trader=is_sole_trader, warnings=warnings
            )

        return result
