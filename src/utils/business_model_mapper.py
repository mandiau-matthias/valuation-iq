from src.utils.exceptions import ValuationRangeError

"""
Business Model Mapper

Maps frontend business model values to backend enum values.
Handles the mismatch between frontend form values and backend schema.
"""

from typing import Dict, Optional

from src.domain.models import BusinessModel, IndustryCode
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Frontend to backend business model mapping
BUSINESS_MODEL_MAPPING = {
    # Frontend values -> Backend enum values
    "restaurant": BusinessModel.SERVICES,
    "saas": BusinessModel.B2B_SAAS,
    "software": BusinessModel.B2B_SAAS,
    "technology": BusinessModel.B2B_SAAS,
    "ecommerce": BusinessModel.ECOMMERCE,
    "marketplace": BusinessModel.MARKETPLACE,
    "manufacturing": BusinessModel.MANUFACTURING,
    "services": BusinessModel.SERVICES,
    "b2c": BusinessModel.B2C,
    "b2b": BusinessModel.B2B_SAAS,
    "other": BusinessModel.OTHER,
    # Direct mappings (case insensitive)
    "b2b_saas": BusinessModel.B2B_SAAS,
    "b2c": BusinessModel.B2C,
    "marketplace": BusinessModel.MARKETPLACE,
    "ecommerce": BusinessModel.ECOMMERCE,
    "manufacturing": BusinessModel.MANUFACTURING,
    "services": BusinessModel.SERVICES,
    "other": BusinessModel.OTHER,
}

# Industry mapping (frontend to backend)
INDUSTRY_MAPPING = {
    "hospitality": IndustryCode.HOSPITALITY,
    "technology": IndustryCode.TECHNOLOGY,
    "saas": IndustryCode.TECHNOLOGY,
    "software": IndustryCode.TECHNOLOGY,
    "manufacturing": IndustryCode.MANUFACTURING,
    "retail": IndustryCode.RETAIL,
    "services": IndustryCode.SERVICES,
    "healthcare": IndustryCode.HEALTHCARE,
    "finance": IndustryCode.FINANCE,
    "real_estate": IndustryCode.REAL_ESTATE,
    "construction": IndustryCode.CONSTRUCTION,
    "other": IndustryCode.OTHER,
}


def map_business_model(frontend_value: str) -> BusinessModel:
    """
    Map frontend business model value to backend enum.

    Args:
        frontend_value: Business model value from frontend

    Returns:
        BusinessModel enum value

    Raises:
        ValueError: If mapping not found
    """
    if not frontend_value:
        return BusinessModel.OTHER

    # Normalize input
    normalized_value = frontend_value.lower().strip()

    # Direct mapping
    if normalized_value in BUSINESS_MODEL_MAPPING:
        mapped_value = BUSINESS_MODEL_MAPPING[normalized_value]
        logger.info(f"Mapped business model: '{frontend_value}' -> '{mapped_value.value}'")
        return mapped_value

    # Try partial matching
    for frontend_key, backend_value in BUSINESS_MODEL_MAPPING.items():
        if frontend_key in normalized_value or normalized_value in frontend_key:
            logger.info(
                f"Partial match business model: '{frontend_value}' -> '{backend_value.value}'"
            )
            return backend_value

    # Default fallback
    logger.warning(f"No mapping found for business model: '{frontend_value}', using OTHER")
    return BusinessModel.OTHER


def map_industry(frontend_value: str) -> IndustryCode:
    """
    Map frontend industry value to backend enum.

    Args:
        frontend_value: Industry value from frontend

    Returns:
        IndustryCode enum value

    Raises:
        ValueError: If mapping not found
    """
    if not frontend_value:
        return IndustryCode.OTHER

    # Normalize input
    normalized_value = frontend_value.lower().strip()

    # Direct mapping
    if normalized_value in INDUSTRY_MAPPING:
        mapped_value = INDUSTRY_MAPPING[normalized_value]
        logger.info(f"Mapped industry: '{frontend_value}' -> '{mapped_value.value}'")
        return mapped_value

    # Try partial matching
    for frontend_key, backend_value in INDUSTRY_MAPPING.items():
        if frontend_key in normalized_value or normalized_value in frontend_key:
            logger.info(f"Partial match industry: '{frontend_value}' -> '{backend_value.value}'")
            return backend_value

    # Default fallback
    logger.warning(f"No mapping found for industry: '{frontend_value}', using OTHER")
    return IndustryCode.OTHER


def validate_and_map_request_data(request_data: Dict) -> Dict:
    """
    Validate and map request data from frontend format to backend format.

    Args:
        request_data: Raw request data from frontend

    Returns:
        Mapped request data for backend processing
    """
    try:
        # Create a copy to avoid modifying original
        mapped_data = request_data.copy()

        # Map business model if present
        if "business_model" in mapped_data:
            original_value = mapped_data["business_model"]
            mapped_data["business_model"] = map_business_model(original_value).value

        # Map industry if present
        if "industry" in mapped_data:
            original_value = mapped_data["industry"]
            mapped_data["industry"] = map_industry(original_value).value

        # Add Phase 2 defaults if not present
        if "use_monte_carlo" not in mapped_data:
            mapped_data["use_monte_carlo"] = False
        if "use_intelligent_selection" not in mapped_data:
            mapped_data["use_intelligent_selection"] = False
        if "use_asymmetric_ranges" not in mapped_data:
            mapped_data["use_asymmetric_ranges"] = False

        logger.info(
            "Request data mapped successfully",
            original_business_model=request_data.get("business_model"),
            mapped_business_model=mapped_data.get("business_model"),
            original_industry=request_data.get("industry"),
            mapped_industry=mapped_data.get("industry"),
        )

        return mapped_data

    except ValuationRangeError as e:
        logger.error(f"Error mapping request data: {e}")
        # Return original data with defaults
        mapped_data = request_data.copy()
        mapped_data.setdefault("use_monte_carlo", False)
        mapped_data.setdefault("use_intelligent_selection", False)
        mapped_data.setdefault("use_asymmetric_ranges", False)
        return mapped_data


def get_mapping_suggestions(frontend_value: str, field_type: str = "business_model") -> list:
    """
    Get mapping suggestions for a frontend value.

    Args:
        frontend_value: Value to get suggestions for
        field_type: Type of field ("business_model" or "industry")

    Returns:
        List of suggested backend values
    """
    if field_type == "business_model":
        mapping = BUSINESS_MODEL_MAPPING
    elif field_type == "industry":
        mapping = INDUSTRY_MAPPING
    else:
        return []

    suggestions = []
    normalized_value = frontend_value.lower().strip()

    for frontend_key, backend_value in mapping.items():
        if frontend_key in normalized_value or normalized_value in frontend_key:
            suggestions.append(
                {
                    "frontend": frontend_key,
                    "backend": backend_value.value,
                    "match_type": "exact" if frontend_key == normalized_value else "partial",
                }
            )

    return suggestions
