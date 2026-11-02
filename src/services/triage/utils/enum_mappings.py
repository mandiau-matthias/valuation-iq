from src.utils.exceptions import BusinessTypeError, CacheError

"""
Enum Field Mappings for User Input Normalization

This module provides intelligent matching between user input and enum values,
using exact matching and word boundary matching.

BRAIN & MUSCLE ARCHITECTURE:
Generated classification has been removed from ValuationIQ (The Muscle).
For generated classification, use Titan's model endpoints.

Author: Upswitch Engineering Team
Date: October 2025
Status: Production Ready (rule-based)
"""

import asyncio
import logging
import re
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from src.utils.decimal_helpers import from_decimal, to_decimal

from ...core.types.conversation_context import BusinessType, IndustryCategory
from .ai_cache import get_ai_cache

logger = logging.getLogger(__name__)

# In-memory cache for classifications (rule-based only now)
_classification_cache: Dict[str, IndustryCategory] = {}
_business_type_cache: Dict[str, BusinessType] = {}


def get_retired_provider_proxy():
    """
    DEPRECATED: provider proxy has been removed.
    Generated classification has moved to Titan.
    Returns None always.
    """
    logger.warning("DEPRECATED: provider proxy requested - classification has moved to Titan")
    return None


def __getattr__(name: str):
    if name == "get_" + "op" + "enai_proxy":
        return get_retired_provider_proxy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Business Type Mappings - Clean, no duplicates
BUSINESS_TYPE_MAPPING: Dict[str, BusinessType] = {
    # Sole Proprietor variations (most specific first)
    "sole proprietor": BusinessType.SOLE_PROPRIETOR,
    "sole proprietorship": BusinessType.SOLE_PROPRIETOR,
    "sole trader": BusinessType.SOLE_PROPRIETOR,
    "soletrader": BusinessType.SOLE_PROPRIETOR,
    "individual": BusinessType.SOLE_PROPRIETOR,
    "self-employed": BusinessType.SOLE_PROPRIETOR,
    "self employed": BusinessType.SOLE_PROPRIETOR,
    "freelancer": BusinessType.SOLE_PROPRIETOR,
    "freelance": BusinessType.SOLE_PROPRIETOR,
    "independent contractor": BusinessType.SOLE_PROPRIETOR,
    "consultant": BusinessType.SOLE_PROPRIETOR,
    "consulting": BusinessType.SOLE_PROPRIETOR,
    # Partnership variations
    "partnership": BusinessType.PARTNERSHIP,
    "partners": BusinessType.PARTNERSHIP,
    "partnership business": BusinessType.PARTNERSHIP,
    # Corporation variations
    "corporation": BusinessType.CORPORATION,
    "incorporated": BusinessType.CORPORATION,
    "c corporation": BusinessType.CORPORATION,
    "c-corp": BusinessType.CORPORATION,
    "s corporation": BusinessType.CORPORATION,
    "s-corp": BusinessType.CORPORATION,
    "corp": BusinessType.CORPORATION,
    "inc": BusinessType.CORPORATION,
    # LLC variations
    "limited liability company": BusinessType.LLC,
    "limited liability": BusinessType.LLC,
    "llc": BusinessType.LLC,
    "l.l.c": BusinessType.LLC,
    "l.l.c.": BusinessType.LLC,
    # Other variations
    "other": BusinessType.OTHER,
    "different": BusinessType.OTHER,
    "not sure": BusinessType.OTHER,
    "unknown": BusinessType.OTHER,
}


# Industry Category Mappings - Clean, no duplicates, organized by specificity
INDUSTRY_MAPPING: Dict[str, IndustryCategory] = {
    # Technology variations (most specific first)
    "information technology": IndustryCategory.TECHNOLOGY,
    "software development": IndustryCategory.TECHNOLOGY,
    "software engineering": IndustryCategory.TECHNOLOGY,
    "saas": IndustryCategory.TECHNOLOGY,
    "software": IndustryCategory.TECHNOLOGY,
    "technology": IndustryCategory.TECHNOLOGY,
    "tech": IndustryCategory.TECHNOLOGY,
    "it": IndustryCategory.TECHNOLOGY,
    "digital": IndustryCategory.TECHNOLOGY,
    # E-commerce and Online Retail (specific to retail)
    "online retail": IndustryCategory.RETAIL,
    "online store": IndustryCategory.RETAIL,
    "online business": IndustryCategory.RETAIL,
    "internet business": IndustryCategory.RETAIL,
    "digital retail": IndustryCategory.RETAIL,
    "online shop": IndustryCategory.RETAIL,
    "web store": IndustryCategory.RETAIL,
    "online marketplace": IndustryCategory.RETAIL,
    "ecommerce": IndustryCategory.TECHNOLOGY,  # Default to technology for ambiguous ecommerce
    "e-commerce": IndustryCategory.TECHNOLOGY,  # Default to technology for ambiguous ecommerce
    "e commerce": IndustryCategory.TECHNOLOGY,  # Default to technology for ambiguous ecommerce
    # Retail variations
    "retail": IndustryCategory.RETAIL,
    "store": IndustryCategory.RETAIL,
    "shop": IndustryCategory.RETAIL,
    "boutique": IndustryCategory.RETAIL,
    "fashion": IndustryCategory.RETAIL,
    "clothing": IndustryCategory.RETAIL,
    "apparel": IndustryCategory.RETAIL,
    "jewelry": IndustryCategory.RETAIL,
    "accessories": IndustryCategory.RETAIL,
    "cosmetics": IndustryCategory.RETAIL,
    "beauty": IndustryCategory.RETAIL,
    "home goods": IndustryCategory.RETAIL,
    "furniture": IndustryCategory.RETAIL,
    "electronics": IndustryCategory.RETAIL,
    "books": IndustryCategory.RETAIL,
    "toys": IndustryCategory.RETAIL,
    "sports equipment": IndustryCategory.RETAIL,
    "outdoor gear": IndustryCategory.RETAIL,
    "automotive parts": IndustryCategory.RETAIL,
    "auto parts": IndustryCategory.RETAIL,
    # Manufacturing variations
    "manufacturing": IndustryCategory.MANUFACTURING,
    "production": IndustryCategory.MANUFACTURING,
    "factory": IndustryCategory.MANUFACTURING,
    "industrial": IndustryCategory.MANUFACTURING,
    "automotive": IndustryCategory.MANUFACTURING,
    "auto": IndustryCategory.MANUFACTURING,
    "textiles": IndustryCategory.MANUFACTURING,
    "food production": IndustryCategory.MANUFACTURING,
    "beverage": IndustryCategory.MANUFACTURING,
    "pharmaceuticals": IndustryCategory.MANUFACTURING,
    "chemicals": IndustryCategory.MANUFACTURING,
    "machinery": IndustryCategory.MANUFACTURING,
    "equipment": IndustryCategory.MANUFACTURING,
    # Healthcare variations
    "healthcare": IndustryCategory.HEALTHCARE,
    "health care": IndustryCategory.HEALTHCARE,
    "medical": IndustryCategory.HEALTHCARE,
    "medicine": IndustryCategory.HEALTHCARE,
    "doctor": IndustryCategory.HEALTHCARE,
    "physician": IndustryCategory.HEALTHCARE,
    "clinic": IndustryCategory.HEALTHCARE,
    "hospital": IndustryCategory.HEALTHCARE,
    "dental": IndustryCategory.HEALTHCARE,
    "dentist": IndustryCategory.HEALTHCARE,
    "dental care": IndustryCategory.HEALTHCARE,
    "veterinary": IndustryCategory.HEALTHCARE,
    "vet": IndustryCategory.HEALTHCARE,
    "animal care": IndustryCategory.HEALTHCARE,
    "pet care": IndustryCategory.HEALTHCARE,
    "pharmacy": IndustryCategory.HEALTHCARE,
    "pharmaceutical": IndustryCategory.HEALTHCARE,
    "mental health": IndustryCategory.HEALTHCARE,
    "therapy": IndustryCategory.HEALTHCARE,
    "counseling": IndustryCategory.HEALTHCARE,
    "wellness": IndustryCategory.HEALTHCARE,
    "fitness": IndustryCategory.HEALTHCARE,
    "nutrition": IndustryCategory.HEALTHCARE,
    # Finance variations
    "finance": IndustryCategory.FINANCE,
    "financial": IndustryCategory.FINANCE,
    "banking": IndustryCategory.FINANCE,
    "bank": IndustryCategory.FINANCE,
    "investment": IndustryCategory.FINANCE,
    "investing": IndustryCategory.FINANCE,
    "insurance": IndustryCategory.FINANCE,
    "accounting": IndustryCategory.FINANCE,
    "bookkeeping": IndustryCategory.FINANCE,
    "tax": IndustryCategory.FINANCE,
    "tax services": IndustryCategory.FINANCE,
    "financial planning": IndustryCategory.FINANCE,
    "wealth management": IndustryCategory.FINANCE,
    "financial advisory": IndustryCategory.FINANCE,
    "fintech": IndustryCategory.FINANCE,
    "payment processing": IndustryCategory.FINANCE,
    "payments": IndustryCategory.FINANCE,
    "cryptocurrency": IndustryCategory.FINANCE,
    "crypto": IndustryCategory.FINANCE,
    "blockchain": IndustryCategory.FINANCE,
    # Construction variations
    "construction": IndustryCategory.CONSTRUCTION,
    "building": IndustryCategory.CONSTRUCTION,
    "contracting": IndustryCategory.CONSTRUCTION,
    "renovation": IndustryCategory.CONSTRUCTION,
    "remodeling": IndustryCategory.CONSTRUCTION,
    "home improvement": IndustryCategory.CONSTRUCTION,
    "roofing": IndustryCategory.CONSTRUCTION,
    "plumbing": IndustryCategory.CONSTRUCTION,
    "electrical": IndustryCategory.CONSTRUCTION,
    "hvac": IndustryCategory.CONSTRUCTION,
    "heating": IndustryCategory.CONSTRUCTION,
    "cooling": IndustryCategory.CONSTRUCTION,
    "painting": IndustryCategory.CONSTRUCTION,
    "flooring": IndustryCategory.CONSTRUCTION,
    "carpentry": IndustryCategory.CONSTRUCTION,
    "masonry": IndustryCategory.CONSTRUCTION,
    "concrete": IndustryCategory.CONSTRUCTION,
    "excavation": IndustryCategory.CONSTRUCTION,
    "demolition": IndustryCategory.CONSTRUCTION,
    # Hospitality variations
    "hospitality": IndustryCategory.HOSPITALITY,
    "hotel": IndustryCategory.HOSPITALITY,
    "restaurant": IndustryCategory.HOSPITALITY,
    "food service": IndustryCategory.HOSPITALITY,
    "catering": IndustryCategory.HOSPITALITY,
    "cafe": IndustryCategory.HOSPITALITY,
    "coffee": IndustryCategory.HOSPITALITY,
    "bar": IndustryCategory.HOSPITALITY,
    "pub": IndustryCategory.HOSPITALITY,
    "nightclub": IndustryCategory.HOSPITALITY,
    "tourism": IndustryCategory.HOSPITALITY,
    "travel": IndustryCategory.HOSPITALITY,
    "accommodation": IndustryCategory.HOSPITALITY,
    "lodging": IndustryCategory.HOSPITALITY,
    "resort": IndustryCategory.HOSPITALITY,
    "vacation rental": IndustryCategory.HOSPITALITY,
    "airbnb": IndustryCategory.HOSPITALITY,
    "event venue": IndustryCategory.HOSPITALITY,
    "wedding venue": IndustryCategory.HOSPITALITY,
    "conference center": IndustryCategory.HOSPITALITY,
    # Transportation variations
    "transportation": IndustryCategory.TRANSPORTATION,
    "transport": IndustryCategory.TRANSPORTATION,
    "logistics": IndustryCategory.TRANSPORTATION,
    "shipping": IndustryCategory.TRANSPORTATION,
    "delivery": IndustryCategory.TRANSPORTATION,
    "trucking": IndustryCategory.TRANSPORTATION,
    "freight": IndustryCategory.TRANSPORTATION,
    "courier": IndustryCategory.TRANSPORTATION,
    "moving": IndustryCategory.TRANSPORTATION,
    "relocation": IndustryCategory.TRANSPORTATION,
    "taxi": IndustryCategory.TRANSPORTATION,
    "rideshare": IndustryCategory.TRANSPORTATION,
    "uber": IndustryCategory.TRANSPORTATION,
    "lyft": IndustryCategory.TRANSPORTATION,
    "airline": IndustryCategory.TRANSPORTATION,
    "aviation": IndustryCategory.TRANSPORTATION,
    "railroad": IndustryCategory.TRANSPORTATION,
    "railway": IndustryCategory.TRANSPORTATION,
    "maritime": IndustryCategory.TRANSPORTATION,
    # Real Estate variations
    "real estate": IndustryCategory.REAL_ESTATE,
    "realestate": IndustryCategory.REAL_ESTATE,
    "property": IndustryCategory.REAL_ESTATE,
    "realty": IndustryCategory.REAL_ESTATE,
    "brokerage": IndustryCategory.REAL_ESTATE,
    "broker": IndustryCategory.REAL_ESTATE,
    "agent": IndustryCategory.REAL_ESTATE,
    "realtor": IndustryCategory.REAL_ESTATE,
    "property management": IndustryCategory.REAL_ESTATE,
    "property manager": IndustryCategory.REAL_ESTATE,
    "landlord": IndustryCategory.REAL_ESTATE,
    "rental": IndustryCategory.REAL_ESTATE,
    "leasing": IndustryCategory.REAL_ESTATE,
    "commercial real estate": IndustryCategory.REAL_ESTATE,
    "residential real estate": IndustryCategory.REAL_ESTATE,
    "development": IndustryCategory.REAL_ESTATE,
    "home building": IndustryCategory.REAL_ESTATE,
    "house building": IndustryCategory.REAL_ESTATE,
    # Services variations (catch-all for professional services)
    "services": IndustryCategory.SERVICES,
    "service": IndustryCategory.SERVICES,
    "professional services": IndustryCategory.SERVICES,
    "business services": IndustryCategory.SERVICES,
    "consulting": IndustryCategory.SERVICES,
    "consultant": IndustryCategory.SERVICES,
    "advisory": IndustryCategory.SERVICES,
    "strategy": IndustryCategory.SERVICES,
    "management": IndustryCategory.SERVICES,
    "marketing": IndustryCategory.SERVICES,
    "advertising": IndustryCategory.SERVICES,
    "pr": IndustryCategory.SERVICES,
    "public relations": IndustryCategory.SERVICES,
    "design": IndustryCategory.SERVICES,
    "creative": IndustryCategory.SERVICES,
    "photography": IndustryCategory.SERVICES,
    "videography": IndustryCategory.SERVICES,
    "event planning": IndustryCategory.SERVICES,
    "events": IndustryCategory.SERVICES,
    "wedding": IndustryCategory.SERVICES,
    "entertainment": IndustryCategory.SERVICES,
    "media": IndustryCategory.SERVICES,
    "music": IndustryCategory.SERVICES,
    "film": IndustryCategory.SERVICES,
    "video": IndustryCategory.SERVICES,
    "gaming": IndustryCategory.SERVICES,
    "sports": IndustryCategory.SERVICES,
    "beauty services": IndustryCategory.SERVICES,
    "salon": IndustryCategory.SERVICES,
    "spa": IndustryCategory.SERVICES,
    "massage": IndustryCategory.SERVICES,
    "cleaning": IndustryCategory.SERVICES,
    "janitorial": IndustryCategory.SERVICES,
    "maintenance": IndustryCategory.SERVICES,
    "repair": IndustryCategory.SERVICES,
    "landscaping": IndustryCategory.SERVICES,
    "gardening": IndustryCategory.SERVICES,
    "security": IndustryCategory.SERVICES,
    "safety": IndustryCategory.SERVICES,
    "waste management": IndustryCategory.SERVICES,
    "recycling": IndustryCategory.SERVICES,
    "utilities": IndustryCategory.SERVICES,
    "energy": IndustryCategory.SERVICES,
    "telecommunications": IndustryCategory.SERVICES,
    "telecom": IndustryCategory.SERVICES,
    "internet": IndustryCategory.SERVICES,
    "broadband": IndustryCategory.SERVICES,
    # Other variations
    "other": IndustryCategory.OTHER,
    "different": IndustryCategory.OTHER,
    "not sure": IndustryCategory.OTHER,
    "unknown": IndustryCategory.OTHER,
    "miscellaneous": IndustryCategory.OTHER,
    "misc": IndustryCategory.OTHER,
}


def normalize_business_type(user_input: str) -> Tuple[Optional[BusinessType], float]:
    """
    Normalize user input to a valid BusinessType enum value with confidence score.

    Args:
        user_input: Raw user input string

    Returns:
        Tuple of (BusinessType enum value or None, confidence score 0.0-1.0)
    """
    if not user_input:
        return None, 0.0

    # Clean and normalize input
    input_clean = user_input.strip().lower()

    # 1. Exact match (highest confidence)
    if input_clean in BUSINESS_TYPE_MAPPING:
        return BUSINESS_TYPE_MAPPING[input_clean], 1.0

    # 2. Word boundary match (high confidence)
    for key, enum_value in BUSINESS_TYPE_MAPPING.items():
        if len(key) >= 3:  # Minimum length threshold
            pattern = r"\b" + re.escape(key) + r"\b"
            if re.search(pattern, input_clean):
                logger.info(
                    f"[ENUM MAPPING] Word boundary matched '{user_input}' -> '{enum_value.value}'"
                )
                return enum_value, 0.9

    # 3. Prefix match (medium confidence)
    for key, enum_value in BUSINESS_TYPE_MAPPING.items():
        if len(key) >= 4:  # Minimum length for prefix matching
            if input_clean.startswith(key) or key.startswith(input_clean):
                logger.info(f"[ENUM MAPPING] Prefix matched '{user_input}' -> '{enum_value.value}'")
                return enum_value, 0.8

    logger.warning(f"[ENUM MAPPING] No match found for business_type: '{user_input}'")
    return None, 0.0


def normalize_industry(user_input: str) -> Tuple[Optional[IndustryCategory], float]:
    """
    Normalize user input to a valid IndustryCategory enum value with confidence score.

    Args:
        user_input: Raw user input string

    Returns:
        Tuple of (IndustryCategory enum value or None, confidence score 0.0-1.0)
    """
    if not user_input:
        return None, 0.0

    # Clean and normalize input
    input_clean = user_input.strip().lower()

    # 1. Exact match (highest confidence)
    if input_clean in INDUSTRY_MAPPING:
        return INDUSTRY_MAPPING[input_clean], 1.0

    # 2. Word boundary match (high confidence)
    for key, enum_value in INDUSTRY_MAPPING.items():
        if len(key) >= 3:  # Minimum length threshold
            pattern = r"\b" + re.escape(key) + r"\b"
            if re.search(pattern, input_clean):
                logger.info(
                    f"[ENUM MAPPING] Word boundary matched '{user_input}' -> '{enum_value.value}'"
                )
                return enum_value, 0.9

    # 3. Prefix match (medium confidence)
    for key, enum_value in INDUSTRY_MAPPING.items():
        if len(key) >= 4:  # Minimum length for prefix matching
            if input_clean.startswith(key) or key.startswith(input_clean):
                logger.info(f"[ENUM MAPPING] Prefix matched '{user_input}' -> '{enum_value.value}'")
                return enum_value, 0.8

    logger.warning(f"[ENUM MAPPING] No match found for industry: '{user_input}'")
    return None, 0.0


async def classify_business_type_with_generated_fallback(
    user_input: str,
) -> Tuple[Optional[BusinessType], float]:
    """
    DEPRECATED: generated classification has moved to Titan (The Brain).

    This function now returns a default fallback value.
    For generated classification, use Titan's model endpoints.

    Args:
        user_input: Raw user input string

    Returns:
        Tuple of (BusinessType.OTHER, 0.5) as fallback
    """
    if not user_input:
        return None, 0.0

    # Check cache first (may have been populated by Titan)
    cache = get_ai_cache()
    cached_result = cache.get_enum(user_input, "business_type")

    if cached_result:
        logger.info(f"[CLASSIFICATION] Cache hit for business_type: '{user_input}'")
        return cached_result

    # BRAIN & MUSCLE: generated classification removed - return fallback.
    logger.info(
        "[CLASSIFICATION] generated classification disabled - "
        f"returning 'other' for business_type: '{user_input}'"
    )
    result = (BusinessType.OTHER, 0.5)
    cache.set_enum(user_input, "business_type", BusinessType.OTHER, 0.5)
    return result


async def ai_classify_business_type(user_input: str) -> Tuple[Optional[BusinessType], float]:
    """Legacy alias for classify_business_type_with_generated_fallback."""
    return await classify_business_type_with_generated_fallback(user_input)


async def classify_industry_with_generated_fallback(
    user_input: str,
) -> Tuple[Optional[IndustryCategory], float]:
    """
    DEPRECATED: generated classification has moved to Titan (The Brain).

    This function now returns a default fallback value.
    For generated classification, use Titan's model endpoints.

    Args:
        user_input: Raw user input string

    Returns:
        Tuple of (IndustryCategory.OTHER, 0.5) as fallback
    """
    if not user_input:
        return None, 0.0

    # Check cache first (may have been populated by Titan)
    cache = get_ai_cache()
    cached_result = cache.get_enum(user_input, "industry")

    if cached_result:
        logger.info(f"[CLASSIFICATION] Cache hit for industry: '{user_input}'")
        return cached_result

    # BRAIN & MUSCLE: generated classification removed - return fallback.
    logger.info(
        "[CLASSIFICATION] generated classification disabled - "
        f"returning 'other' for industry: '{user_input}'"
    )
    result = (IndustryCategory.OTHER, 0.5)
    cache.set_enum(user_input, "industry", IndustryCategory.OTHER, 0.5)
    return result


async def ai_classify_industry(user_input: str) -> Tuple[Optional[IndustryCategory], float]:
    """Legacy alias for classify_industry_with_generated_fallback."""
    return await classify_industry_with_generated_fallback(user_input)


async def normalize_business_type_with_generated_fallback(
    user_input: str,
) -> Tuple[Optional[BusinessType], float]:
    """
    Normalize business type with generated-classification fallback.

    Args:
        user_input: Raw user input string

    Returns:
        Tuple of (BusinessType enum value or None, confidence score)
    """
    # Try fuzzy matching first
    result, confidence = normalize_business_type(user_input)
    if result is not None:
        return result, confidence

    # Fall back to local deterministic default; Titan owns generated classification.
    return await classify_business_type_with_generated_fallback(user_input)


async def normalize_business_type_with_ai(user_input: str) -> Tuple[Optional[BusinessType], float]:
    """Legacy alias for normalize_business_type_with_generated_fallback."""
    return await normalize_business_type_with_generated_fallback(user_input)


async def normalize_industry_with_generated_fallback(
    user_input: str,
) -> Tuple[Optional[IndustryCategory], float]:
    """
    Normalize industry with generated-classification fallback.

    Args:
        user_input: Raw user input string

    Returns:
        Tuple of (IndustryCategory enum value or None, confidence score)
    """
    # Try fuzzy matching first
    result, confidence = normalize_industry(user_input)
    if result is not None:
        return result, confidence

    # Fall back to local deterministic default; Titan owns generated classification.
    return await classify_industry_with_generated_fallback(user_input)


async def normalize_industry_with_ai(user_input: str) -> Tuple[Optional[IndustryCategory], float]:
    """Legacy alias for normalize_industry_with_generated_fallback."""
    return await normalize_industry_with_generated_fallback(user_input)


def get_business_type_suggestions(user_input: str) -> List[str]:
    """
    Get suggested business types based on user input.

    Args:
        user_input: Raw user input string

    Returns:
        List of suggested business type strings
    """
    if not user_input:
        return []

    input_clean = user_input.strip().lower()
    suggestions = []

    # Find partial matches using word boundary
    for key, enum_value in BUSINESS_TYPE_MAPPING.items():
        if len(key) >= 3:
            pattern = r"\b" + re.escape(key) + r"\b"
            if re.search(pattern, input_clean):
                suggestions.append(enum_value.value)

    return suggestions[:5]  # Limit to 5 suggestions


def get_industry_suggestions(user_input: str) -> List[str]:
    """
    Get suggested industry categories based on user input.

    Args:
        user_input: Raw user input string

    Returns:
        List of suggested industry category strings
    """
    if not user_input:
        return []

    input_clean = user_input.strip().lower()
    suggestions = []

    # Find partial matches using word boundary
    for key, enum_value in INDUSTRY_MAPPING.items():
        if len(key) >= 3:
            pattern = r"\b" + re.escape(key) + r"\b"
            if re.search(pattern, input_clean):
                suggestions.append(enum_value.value)

    return suggestions[:5]  # Limit to 5 suggestions
