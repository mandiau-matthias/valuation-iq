"""Domain-owned business-type taxonomy for valuation decisions."""

from enum import Enum
from typing import Tuple


class BusinessTypeCategory(Enum):
    """Business type categories for valuation logic."""

    SAAS_SOFTWARE = "saas_software"
    ECOMMERCE = "ecommerce"
    PROFESSIONAL_SERVICES = "professional_services"
    RETAIL_FOOD = "retail_food"
    MANUFACTURING = "manufacturing"
    CONSTRUCTION = "construction"
    HEALTHCARE = "healthcare"
    FINANCIAL_SERVICES = "financial_services"
    REAL_ESTATE = "real_estate"
    TRANSPORTATION = "transportation"
    OTHER = "other"


class StepExecutionRule(Enum):
    """Rules for valuation step execution."""

    ALWAYS = "always"
    CONDITIONAL_DATA = "conditional_data"
    CONDITIONAL_BUSINESS_TYPE = "conditional_business_type"
    CONDITIONAL_SIZE = "conditional_size"
    CONDITIONAL_SDE = "conditional_sde"
    CONDITIONAL_ASSET_BASED = "conditional_asset_based"
    NEVER = "never"


IndustryCategoryRule = Tuple[Tuple[str, ...], BusinessTypeCategory]

INDUSTRY_CATEGORY_FALLBACKS: Tuple[IndustryCategoryRule, ...] = (
    (("software", "saas", "tech"), BusinessTypeCategory.SAAS_SOFTWARE),
    (("ecommerce", "online", "digital"), BusinessTypeCategory.ECOMMERCE),
    (("consulting", "professional", "services"), BusinessTypeCategory.PROFESSIONAL_SERVICES),
    (("retail", "food", "restaurant", "bakery"), BusinessTypeCategory.RETAIL_FOOD),
    (("manufacturing", "industrial"), BusinessTypeCategory.MANUFACTURING),
    (("construction", "building"), BusinessTypeCategory.CONSTRUCTION),
    (("healthcare", "medical"), BusinessTypeCategory.HEALTHCARE),
    (("financial", "fintech", "banking"), BusinessTypeCategory.FINANCIAL_SERVICES),
    (("real estate", "property"), BusinessTypeCategory.REAL_ESTATE),
    (("transportation", "logistics", "shipping"), BusinessTypeCategory.TRANSPORTATION),
)

INDUSTRY_TEXT_CATEGORY_RULES: Tuple[IndustryCategoryRule, ...] = (
    (("software", "saas", "tech", "technology"), BusinessTypeCategory.SAAS_SOFTWARE),
    (
        ("ecommerce", "e-commerce", "online", "digital", "retail-online"),
        BusinessTypeCategory.ECOMMERCE,
    ),
    (
        ("consulting", "professional", "services", "services-professional"),
        BusinessTypeCategory.PROFESSIONAL_SERVICES,
    ),
    (
        ("creative", "media", "advertising", "marketing", "design", "creative-media"),
        BusinessTypeCategory.PROFESSIONAL_SERVICES,
    ),
    (
        ("retail", "food", "restaurant", "bakery", "hospitality"),
        BusinessTypeCategory.RETAIL_FOOD,
    ),
    (("manufacturing", "industrial"), BusinessTypeCategory.MANUFACTURING),
    (("construction", "building"), BusinessTypeCategory.CONSTRUCTION),
    (("healthcare", "medical"), BusinessTypeCategory.HEALTHCARE),
    (("financial", "fintech", "banking", "finance"), BusinessTypeCategory.FINANCIAL_SERVICES),
    (("real estate", "property", "real-estate"), BusinessTypeCategory.REAL_ESTATE),
    (("transportation", "logistics", "shipping"), BusinessTypeCategory.TRANSPORTATION),
)

__all__ = [
    "BusinessTypeCategory",
    "IndustryCategoryRule",
    "INDUSTRY_CATEGORY_FALLBACKS",
    "INDUSTRY_TEXT_CATEGORY_RULES",
    "StepExecutionRule",
]
