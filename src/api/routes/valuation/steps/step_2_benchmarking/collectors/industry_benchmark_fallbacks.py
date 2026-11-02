"""Fallback multiple policies for the Step 2 industry benchmark collector."""

import re
from decimal import Decimal
from typing import Callable, Dict, Optional

from src.api.routes.valuation.triage.business_type_triage import BusinessTypeCategory

from .industry_benchmark_defaults import BUSINESS_TYPE_DEFAULTS, INDUSTRY_DEFAULTS

MultipleDefaults = Dict[str, Decimal]
FallbackMultiples = Dict[str, object]

CATEGORY_ID_BY_BUSINESS_TYPE: Dict[BusinessTypeCategory, str] = {
    BusinessTypeCategory.SAAS_SOFTWARE: "saas-software",
    BusinessTypeCategory.ECOMMERCE: "ecommerce",
    BusinessTypeCategory.PROFESSIONAL_SERVICES: "professional-services",
    BusinessTypeCategory.RETAIL_FOOD: "food-beverage",
    BusinessTypeCategory.MANUFACTURING: "manufacturing",
    BusinessTypeCategory.CONSTRUCTION: "construction",
    BusinessTypeCategory.HEALTHCARE: "healthcare",
    BusinessTypeCategory.FINANCIAL_SERVICES: "financial-services",
    BusinessTypeCategory.REAL_ESTATE: "real-estate",
    BusinessTypeCategory.TRANSPORTATION: "transportation",
    BusinessTypeCategory.OTHER: "other",
}

HARDCODED_CATEGORY_DEFAULTS: Dict[BusinessTypeCategory, MultipleDefaults] = {
    BusinessTypeCategory.SAAS_SOFTWARE: {
        "ev_ebitda": Decimal("7.0"),
        "ev_revenue": Decimal("2.5"),
        "pe": Decimal("18"),
    },
    BusinessTypeCategory.ECOMMERCE: {
        "ev_ebitda": Decimal("5.0"),
        "ev_revenue": Decimal("1.5"),
        "pe": Decimal("15"),
    },
    BusinessTypeCategory.PROFESSIONAL_SERVICES: {
        "ev_ebitda": Decimal("5.5"),
        "ev_revenue": Decimal("1.1"),
        "pe": Decimal("14"),
    },
    BusinessTypeCategory.RETAIL_FOOD: {
        "ev_ebitda": Decimal("3.5"),
        "ev_revenue": Decimal("0.8"),
        "pe": Decimal("12"),
    },
    BusinessTypeCategory.MANUFACTURING: {
        "ev_ebitda": Decimal("4.5"),
        "ev_revenue": Decimal("0.9"),
        "pe": Decimal("12"),
    },
    BusinessTypeCategory.CONSTRUCTION: {
        "ev_ebitda": Decimal("4.0"),
        "ev_revenue": Decimal("0.6"),
        "pe": Decimal("10"),
    },
    BusinessTypeCategory.HEALTHCARE: {
        "ev_ebitda": Decimal("6.0"),
        "ev_revenue": Decimal("1.8"),
        "pe": Decimal("14"),
    },
    BusinessTypeCategory.FINANCIAL_SERVICES: {
        "ev_ebitda": Decimal("6.5"),
        "ev_revenue": Decimal("2.0"),
        "pe": Decimal("16"),
    },
    BusinessTypeCategory.REAL_ESTATE: {
        "ev_ebitda": Decimal("6.5"),
        "ev_revenue": Decimal("2.0"),
        "pe": Decimal("15"),
    },
    BusinessTypeCategory.TRANSPORTATION: {
        "ev_ebitda": Decimal("4.0"),
        "ev_revenue": Decimal("0.6"),
        "pe": Decimal("10"),
    },
    BusinessTypeCategory.OTHER: {
        "ev_ebitda": Decimal("5.0"),
        "ev_revenue": Decimal("1.0"),
        "pe": Decimal("13"),
    },
}


INDUSTRY_KEY_ALIASES = {
    "food-and-beverage": "food-beverage",
    "food-bev": "food-beverage",
    "food-services": "food-beverage",
}


def normalize_industry_key(industry: Optional[str]) -> Optional[str]:
    """Normalize frontend/backend industry ids into static fallback keys."""
    if industry is None:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "-", str(industry).strip().lower()).strip("-")
    if not normalized:
        return None
    return INDUSTRY_KEY_ALIASES.get(normalized, normalized)


def category_id_for_business_type_category(category: BusinessTypeCategory) -> Optional[str]:
    """Map triage category enum values to the synced database category id."""
    return CATEGORY_ID_BY_BUSINESS_TYPE.get(category)


def hardcoded_category_defaults(category: BusinessTypeCategory) -> Optional[MultipleDefaults]:
    """Legacy category defaults kept for disclosed fallback paths."""
    return HARDCODED_CATEGORY_DEFAULTS.get(category)


def build_fallback_multiples(
    *,
    business_category: Optional[BusinessTypeCategory],
    industry: Optional[str],
    business_type_id: Optional[str],
    category_defaults_resolver: Callable[[BusinessTypeCategory], Optional[MultipleDefaults]],
) -> FallbackMultiples:
    """Build disclosed fallback multiples using the collector's legacy priority order."""
    if business_type_id and business_type_id in BUSINESS_TYPE_DEFAULTS:
        defaults = BUSINESS_TYPE_DEFAULTS[business_type_id]
        return {
            "ev_ebitda": defaults["ev_ebitda"],
            "ev_revenue": defaults.get("ev_revenue", defaults["ev_ebitda"] * Decimal("0.12")),
            "pe": defaults.get("pe", Decimal("15.0")),
            "data_source": "fallback_business_type_defaults",
        }

    if business_category:
        category_defaults = category_defaults_resolver(business_category)
        if category_defaults:
            return {
                "ev_ebitda": category_defaults["ev_ebitda"],
                "ev_revenue": category_defaults.get(
                    "ev_revenue", category_defaults["ev_ebitda"] * Decimal("0.12")
                ),
                "pe": category_defaults.get("pe", Decimal("15.0")),
                "data_source": "fallback_business_category_defaults",
            }

    if industry:
        industry_key = normalize_industry_key(industry)
        industry_defaults = INDUSTRY_DEFAULTS.get(industry_key) if industry_key else None
        if industry_defaults:
            ev_ebitda = industry_defaults.get("ev_ebitda", Decimal("5.0"))
            return {
                "ev_ebitda": ev_ebitda,
                "ev_revenue": ev_ebitda * Decimal("0.12"),
                "pe": industry_defaults.get("pe", Decimal("15.0")),
                "data_source": "fallback_industry_defaults",
            }

    return {
        "ev_ebitda": Decimal("5.0"),
        "ev_revenue": Decimal("1.0"),
        "pe": Decimal("13.0"),
        "data_source": "fallback_generic_defaults",
    }
