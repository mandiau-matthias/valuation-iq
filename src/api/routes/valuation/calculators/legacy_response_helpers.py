"""
Legacy Response Helpers

Utility functions for building legacy API format responses from modular step results.
Extracted from multiples_calculator.py to improve modularity and maintainability.

BANK-GRADE QUALITY:
- Full type hints
- Comprehensive error handling
- Detailed logging
- No code duplication
"""

from decimal import Decimal

from src.api.schemas import ValuationRequest
from src.domain.models import ConfidenceLevel
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.valuation_logger import ValuationLogger

logger = ValuationLogger(__name__)


def get_primary_method_reason(primary_method: str) -> str:
    """
    Get human-readable reason for primary method selection.
    
    Args:
        primary_method: The primary method ("EV/Revenue" or "EV/EBITDA")
        
    Returns:
        Human-readable explanation string
    """
    if primary_method == "EV/Revenue":
        return "Revenue multiple used as primary (business type or low EBITDA margin <10%)"
    else:
        return "EBITDA multiple used as primary (standard for profitable companies with >10% margin)"


def build_owner_concentration_dict(
    step_4_result: dict[str, object], request: ValuationRequest
) -> dict[str, object] | None:
    """
    Build owner concentration dictionary for backward compatibility.
    
    Args:
        step_4_result: Step 4 result dictionary
        request: Valuation request
        
    Returns:
        Owner concentration dictionary or None
    """
    if not step_4_result:
        return None

    # CRITICAL FIX: Convert adjustment_percentage to decimal format for adjustment_factor
    # Step 4 sends adjustment_percentage as percentage (-20.0) and owner_concentration_adjustment as decimal (-0.2)
    # Frontend expects adjustment_factor as decimal format for calculations
    adjustment_factor = None
    if step_4_result.get("owner_concentration_adjustment") is not None:
        # Priority 1: Use owner_concentration_adjustment if available (already in decimal format)
        adjustment_factor = step_4_result.get("owner_concentration_adjustment")
    elif step_4_result.get("adjustment_percentage") is not None:
        # Priority 2: Convert adjustment_percentage from percentage to decimal
        adjustment_percentage = step_4_result.get("adjustment_percentage")
        adjustment_factor = adjustment_percentage / Decimal("100.0")

    owner_conc_dict = {
        "ratio": step_4_result.get("owner_employee_ratio"),
        "adjustment_factor": adjustment_factor,
        "number_of_owners": getattr(request, "number_of_owners", None),
        "number_of_employees": getattr(request, "number_of_employees", None),
        "risk_level": step_4_result.get("risk_level"),
        # The owner-risk ledger is projected from THIS dict (synthesizer
        # `_build_owner_risk_ledger_safely`), not from the raw step-4 result.
        # Without these three keys the ledger showed a discount with no basis
        # and the page could not say whether the headcount behind it was
        # confirmed by a human or read off a registry — which is the whole
        # point of the corroboration gate.
        "adjustment_percentage": step_4_result.get("adjustment_percentage"),
        "evidence_grade": step_4_result.get("evidence_grade"),
        "input_basis": step_4_result.get("input_basis"),
        "calibration": {
            "business_type_id": getattr(request, "business_type_id", None),
            "calibration_type": "universal",
            "risk_level": step_4_result.get("risk_level"),
            "tier_used": step_4_result.get("risk_level"),
            "owner_dependency_impact": None,
        },
    }

    # ENHANCEMENT (2025): Include detailed explanation if available
    detailed_explanation = step_4_result.get("detailed_explanation")
    if detailed_explanation:
        owner_conc_dict["detailed_explanation"] = detailed_explanation

    return owner_conc_dict


def get_industry_default_multiple(industry: str, multiple_type: str) -> Decimal:
    """
    Get industry default multiples as fallback.
    
    Args:
        industry: Industry/business type ID
        multiple_type: 'revenue' or 'ebitda'
        
    Returns:
        Default multiple for the industry as Decimal
    """
    # Industry-specific defaults based on market data (using Decimal for precision)
    defaults = {
        "home-services": {"revenue": to_decimal("0.5"), "ebitda": to_decimal("5.0")},
        "professional-services": {"revenue": to_decimal("1.2"), "ebitda": to_decimal("6.0")},
        "manufacturing": {"revenue": to_decimal("0.8"), "ebitda": to_decimal("7.0")},
        "technology": {"revenue": to_decimal("2.0"), "ebitda": to_decimal("10.0")},
        "retail": {"revenue": to_decimal("0.4"), "ebitda": to_decimal("6.0")},
        "healthcare": {"revenue": to_decimal("1.0"), "ebitda": to_decimal("8.0")},
        "construction": {"revenue": to_decimal("0.6"), "ebitda": to_decimal("5.5")},
        "hospitality": {"revenue": to_decimal("0.7"), "ebitda": to_decimal("6.5")},
        "consulting": {"revenue": to_decimal("1.5"), "ebitda": to_decimal("7.0")},
        "education": {"revenue": to_decimal("0.8"), "ebitda": to_decimal("6.0")},
        "electrical": {
            "revenue": to_decimal("0.5"),
            "ebitda": to_decimal("5.0"),
        },  # Same as home-services
        "general-business": {
            "revenue": to_decimal("1.0"),
            "ebitda": to_decimal("5.0"),
        },  # Generic fallback
    }

    # Get industry defaults or use general-business as ultimate fallback
    industry_defaults = defaults.get(industry, defaults["general-business"])
    multiple = industry_defaults.get(
        multiple_type, to_decimal("1.0") if multiple_type == "revenue" else to_decimal("5.0")
    )

    logger.info(
        f"📊 Using default {multiple_type} multiple for industry",
        extra={
            "industry": industry,
            "multiple_type": multiple_type,
            "default_value": from_decimal(multiple, precision=2),
        },
    )

    return multiple


def map_confidence_level(level_str: str) -> ConfidenceLevel:
    """
    Map string confidence level to ConfidenceLevel enum.
    
    Args:
        level_str: Confidence level string ("HIGH", "MEDIUM", "LOW")
        
    Returns:
        ConfidenceLevel enum value
    """
    mapping = {
        "HIGH": ConfidenceLevel.HIGH,
        "MEDIUM": ConfidenceLevel.MEDIUM,
        "LOW": ConfidenceLevel.LOW,
    }
    return mapping.get(level_str, ConfidenceLevel.MEDIUM)
