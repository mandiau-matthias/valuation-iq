
from src.errors.error_types import MarketDataError, ValidationError
from src.utils.exceptions import DataQualityError, MultiplesCalculationError

"""
Industry Multiples Database

Based on 2024-2025 market data from:
- McKinsey Global Institute
- PwC Global M&A Survey 2024
- Deloitte Industry Analysis 2024
- EY Valuation Practices Survey 2024

Author: Senior CTO
Version: 1.0.0
"""

from decimal import Decimal
from typing import Dict, Tuple

from src.utils.decimal_helpers import bank_round, from_decimal, to_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


# Industry-specific multiples — SME-calibrated for Belgian/Benelux market.
# Secondary fallback (rarely reached); values should be SME-appropriate since
# the primary consumer is a Belgian SME valuation tool.
# Sources: Pepperdine 2024, BizBuySell 2024, VFB Belgium 2024,
# BDO Belgium M&A Monitor 2024.
INDUSTRY_MULTIPLES = {
    # Technology & Software (SME SaaS/software, not enterprise)
    "technology": {
        "revenue": Decimal("2.0"),
        "ebitda": Decimal("7.0"),
        "description": "General technology companies",
    },
    "saas": {
        "revenue": Decimal("2.5"),
        "ebitda": Decimal("8.0"),
        "description": "Software as a Service companies",
    },
    "software": {
        "revenue": Decimal("2.2"),
        "ebitda": Decimal("7.0"),
        "description": "Software companies",
    },
    "fintech": {
        "revenue": Decimal("2.0"),
        "ebitda": Decimal("7.0"),
        "description": "Financial technology",
    },
    "ecommerce": {
        "revenue": Decimal("0.7"),
        "ebitda": Decimal("3.5"),
        "description": "E-commerce platforms",
    },
    # Professional Services
    "services": {
        "revenue": Decimal("1.0"),
        "ebitda": Decimal("5.0"),
        "description": "Professional services",
    },
    "consulting": {
        "revenue": Decimal("1.2"),
        "ebitda": Decimal("5.5"),
        "description": "Management consulting",
    },
    "legal": {"revenue": Decimal("1.5"), "ebitda": Decimal("5.0"), "description": "Legal services"},
    "accounting": {
        "revenue": Decimal("1.0"),
        "ebitda": Decimal("5.5"),
        "description": "Accounting services",
    },
    "marketing": {
        "revenue": Decimal("1.5"),
        "ebitda": Decimal("5.0"),
        "description": "Marketing agencies",
    },
    # Manufacturing & Industrial
    "manufacturing": {
        "revenue": Decimal("0.8"),
        "ebitda": Decimal("4.5"),
        "description": "Manufacturing companies",
    },
    "automotive": {
        "revenue": Decimal("0.6"),
        "ebitda": Decimal("3.5"),
        "description": "Automotive industry",
    },
    "aerospace": {
        "revenue": Decimal("1.2"),
        "ebitda": Decimal("6.0"),
        "description": "Aerospace & defense",
    },
    "construction": {
        "revenue": Decimal("0.7"),
        "ebitda": Decimal("4.0"),
        "description": "Construction companies",
    },
    "materials": {
        "revenue": Decimal("0.9"),
        "ebitda": Decimal("5.0"),
        "description": "Materials & chemicals",
    },
    # Retail & Consumer
    "retail": {
        "revenue": Decimal("0.5"),
        "ebitda": Decimal("4.0"),
        "description": "Retail companies",
    },
    "fashion": {
        "revenue": Decimal("0.8"),
        "ebitda": Decimal("4.5"),
        "description": "Fashion & apparel",
    },
    "food_beverage": {
        "revenue": Decimal("0.8"),
        "ebitda": Decimal("3.5"),
        "description": "Food & beverage",
    },
    "food-beverage": {
        "revenue": Decimal("0.8"),
        "ebitda": Decimal("3.5"),
        "description": "Food & beverage",
    },
    "restaurant": {
        "revenue": Decimal("0.6"),
        "ebitda": Decimal("3.5"),
        "description": "Restaurants and dining",
    },
    "restaurants": {
        "revenue": Decimal("0.6"),
        "ebitda": Decimal("3.5"),
        "description": "Restaurants and dining",
    },
    "consumer_goods": {
        "revenue": Decimal("1.0"),
        "ebitda": Decimal("5.0"),
        "description": "Consumer goods",
    },
    # Healthcare & Life Sciences
    "healthcare": {
        "revenue": Decimal("1.5"),
        "ebitda": Decimal("6.0"),
        "description": "Healthcare services",
    },
    "pharma": {
        "revenue": Decimal("2.0"),
        "ebitda": Decimal("7.0"),
        "description": "Pharmaceuticals",
    },
    "biotech": {
        "revenue": Decimal("2.0"),
        "ebitda": Decimal("7.0"),
        "description": "Biotechnology",
    },
    "medical_devices": {
        "revenue": Decimal("1.8"),
        "ebitda": Decimal("6.5"),
        "description": "Medical devices",
    },
    "telemedicine": {
        "revenue": Decimal("1.8"),
        "ebitda": Decimal("6.0"),
        "description": "Telemedicine platforms",
    },
    # Financial Services
    "banking": {
        "revenue": Decimal("1.5"),
        "ebitda": Decimal("6.5"),
        "description": "Banking services",
    },
    "insurance": {
        "revenue": Decimal("1.2"),
        "ebitda": Decimal("6.0"),
        "description": "Insurance companies",
    },
    "investment": {
        "revenue": Decimal("1.8"),
        "ebitda": Decimal("6.0"),
        "description": "Investment firms",
    },
    "real_estate": {
        "revenue": Decimal("0.8"),
        "ebitda": Decimal("5.5"),
        "description": "Real estate",
    },
    # Energy & Utilities
    "energy": {
        "revenue": Decimal("1.0"),
        "ebitda": Decimal("5.5"),
        "description": "Energy companies",
    },
    "renewable": {
        "revenue": Decimal("1.5"),
        "ebitda": Decimal("6.5"),
        "description": "Renewable energy",
    },
    "utilities": {
        "revenue": Decimal("0.8"),
        "ebitda": Decimal("5.0"),
        "description": "Utility companies",
    },
    # Transportation & Logistics
    "logistics": {
        "revenue": Decimal("0.9"),
        "ebitda": Decimal("4.5"),
        "description": "Logistics & shipping",
    },
    "transportation": {
        "revenue": Decimal("0.7"),
        "ebitda": Decimal("4.0"),
        "description": "Transportation",
    },
    "aviation": {
        "revenue": Decimal("0.8"),
        "ebitda": Decimal("5.0"),
        "description": "Aviation industry",
    },
    # Media & Entertainment
    "media": {
        "revenue": Decimal("1.2"),
        "ebitda": Decimal("5.0"),
        "description": "Media companies",
    },
    "entertainment": {
        "revenue": Decimal("1.0"),
        "ebitda": Decimal("5.0"),
        "description": "Entertainment",
    },
    "gaming": {
        "revenue": Decimal("1.5"),
        "ebitda": Decimal("6.0"),
        "description": "Gaming companies",
    },
    "publishing": {
        "revenue": Decimal("1.0"),
        "ebitda": Decimal("4.5"),
        "description": "Publishing",
    },
    # Education & Training
    "education": {
        "revenue": Decimal("1.0"),
        "ebitda": Decimal("4.5"),
        "description": "Education services",
    },
    "edtech": {
        "revenue": Decimal("1.8"),
        "ebitda": Decimal("6.0"),
        "description": "Educational technology",
    },
    "training": {
        "revenue": Decimal("1.0"),
        "ebitda": Decimal("4.5"),
        "description": "Training services",
    },
    # Agriculture & Food Production
    "agriculture": {
        "revenue": Decimal("0.6"),
        "ebitda": Decimal("3.5"),
        "description": "Agriculture",
    },
    "food_production": {
        "revenue": Decimal("0.8"),
        "ebitda": Decimal("4.0"),
        "description": "Food production",
    },
    # Default fallback (Pepperdine 2024 cross-industry SME median)
    "default": {
        "revenue": Decimal("1.0"),
        "ebitda": Decimal("5.0"),
        "description": "General business",
    },
}


def get_industry_multiples(industry: str) -> Dict[str, Decimal]:
    """
    Get industry-specific multiples for valuation.

    Args:
        industry: Industry code (e.g., 'technology', 'services', 'manufacturing')

    Returns:
        Dict with 'revenue' and 'ebitda' multiples as Decimal

    Raises:
        ValueError: If industry not found and no default available
    """
    try:
        # Normalize industry name
        industry_normalized = industry.lower().strip()

        # Direct lookup
        if industry_normalized in INDUSTRY_MULTIPLES:
            multiples = INDUSTRY_MULTIPLES[industry_normalized]
            logger.info(
                f"Using industry multiples for {industry_normalized}",
                revenue_multiple=multiples["revenue"],
                ebitda_multiple=multiples["ebitda"],
            )
            return {
                "revenue": to_decimal(multiples["revenue"]),
                "ebitda": to_decimal(multiples["ebitda"]),
            }

        # Try partial matching for common variations
        for key, data in INDUSTRY_MULTIPLES.items():
            if (
                industry_normalized in key
                or key in industry_normalized
                or industry_normalized.replace("_", " ") in key.replace("_", " ")
            ):
                multiples = data
                logger.info(
                    f"Using matched industry multiples for {industry_normalized} -> {key}",
                    revenue_multiple=multiples["revenue"],
                    ebitda_multiple=multiples["ebitda"],
                )
                return {
                    "revenue": to_decimal(multiples["revenue"]),
                    "ebitda": to_decimal(multiples["ebitda"]),
                }

        # Fallback to default
        logger.warning(f"Industry '{industry}' not found, using default multiples")
        default_multiples = INDUSTRY_MULTIPLES["default"]
        return {
            "revenue": to_decimal(default_multiples["revenue"]),
            "ebitda": to_decimal(default_multiples["ebitda"]),
        }

    except (ValueError, TypeError, AttributeError, KeyError) as e:
        logger.error(
            f"Error getting industry multiples for {industry}: {e}",
            extra={"error_type": type(e).__name__, "error": str(e), "industry": industry},
        )
        # Emergency fallback
        return {"revenue": Decimal("1.0"), "ebitda": Decimal("6.0")}
    except MultiplesCalculationError as e:
        logger.error(
            f"Unexpected error getting industry multiples for {industry}: {e}",
            extra={"error_type": type(e).__name__, "error": str(e), "industry": industry},
        )
        return {"revenue": Decimal("1.0"), "ebitda": Decimal("6.0")}


def get_industry_description(industry: str) -> str:
    """
    Get human-readable description for an industry.

    Args:
        industry: Industry code

    Returns:
        Human-readable description
    """
    try:
        industry_normalized = industry.lower().strip()

        if industry_normalized in INDUSTRY_MULTIPLES:
            return INDUSTRY_MULTIPLES[industry_normalized]["description"]

        # Try partial matching
        for key, data in INDUSTRY_MULTIPLES.items():
            if industry_normalized in key or key in industry_normalized:
                return data["description"]

        return "General business"

    except (ValueError, TypeError, AttributeError, KeyError) as e:
        logger.error(
            f"Error getting industry description for {industry}: {e}",
            extra={"error_type": type(e).__name__, "error": str(e), "industry": industry},
        )
        return "Unknown industry"
    except MultiplesCalculationError as e:
        logger.error(
            f"Unexpected error getting industry description for {industry}: {e}",
            extra={"error_type": type(e).__name__, "error": str(e), "industry": industry},
        )
        return "Unknown industry"


def get_all_industries() -> Dict[str, Dict[str, any]]:
    """
    Get all available industries and their multiples.

    Returns:
        Dict of all industries with their multiples and descriptions
    """
    return INDUSTRY_MULTIPLES.copy()


def validate_industry(industry: str) -> bool:
    """
    Validate if an industry code is supported.

    Args:
        industry: Industry code to validate

    Returns:
        True if industry is supported, False otherwise
    """
    try:
        industry_normalized = industry.lower().strip()
        return industry_normalized in INDUSTRY_MULTIPLES or any(
            industry_normalized in key for key in INDUSTRY_MULTIPLES.keys()
        )
    except (ValueError, TypeError, AttributeError, KeyError):
        return False
    except MultiplesCalculationError:
        # Unexpected error in validation, return False for safety
        return False
