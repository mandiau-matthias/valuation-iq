"""SDE multiple lookup helpers.

Maps a company's business-type id / industry + revenue size onto the empirical
SDE multiple in ``SDE_MULTIPLES_BY_INDUSTRY``. The calibration cascade remains
in ``services.reports.sde_channel``.
"""

from decimal import Decimal
from typing import Dict, Optional

from src.domain.sde_engine import SDE_MULTIPLES_BY_INDUSTRY
from src.utils.logging import get_logger

logger = get_logger(__name__)

_SDE_INDUSTRY_ALIAS: Dict[str, str] = {
    "tech-digital": "technology",
    "saas-platform": "saas",
    "saas_software": "saas",
    "software": "technology",
    "food-beverage": "restaurant",
    "food-distribution": "food-services",
    "catering": "food-services",
    "bakery": "food-services",
    "professional-services": "professional-services",
    "beauty-wellness": "beauty-wellness",
    "home-property": "home-services",
    "cleaning": "home-services",
    "landscaping": "home-services",
    "plumbing": "home-services",
    "electrical": "construction",
    "hvac": "construction",
    "ecommerce-retail": "ecommerce",
    "gym": "fitness",
    "personaltraining": "fitness",
    "pilates-studio": "fitness",
    "yoga-studio": "fitness",
    "dental": "dental",
    "veterinary": "veterinary",
    "accounting": "accounting",
    "bookkeeping": "accounting",
    "legal": "legal",
    "notary": "legal",
    "consulting": "consulting",
    "manufacturing": "manufacturing",
    "retail": "retail",
    "healthcare": "healthcare",
    "construction": "construction",
}

_GENERIC_SDE_MULTIPLES: Dict[str, Decimal] = {
    "micro": Decimal("1.5"),
    "small": Decimal("1.8"),
    "lower_middle": Decimal("2.2"),
}


def _classify_sde_size(revenue: float) -> str:
    """Bucket revenue into the SDE size tier used for the multiple lookup."""
    if revenue < 500_000:
        return "micro"
    if revenue < 2_000_000:
        return "small"
    return "lower_middle"


def resolve_sde_multiple(
    revenue: float,
    business_type_id: Optional[str],
    industry: Optional[str],
) -> Decimal:
    """Look up the base SDE multiple from industry-specific transaction data."""
    size_class = _classify_sde_size(revenue)

    if business_type_id and business_type_id in SDE_MULTIPLES_BY_INDUSTRY:
        return SDE_MULTIPLES_BY_INDUSTRY[business_type_id][size_class]

    resolved_industry: Optional[str] = None
    if business_type_id:
        resolved_industry = _SDE_INDUSTRY_ALIAS.get(business_type_id)
    if resolved_industry is None and industry:
        resolved_industry = _SDE_INDUSTRY_ALIAS.get(industry.lower(), industry.lower())

    if resolved_industry and resolved_industry in SDE_MULTIPLES_BY_INDUSTRY:
        return SDE_MULTIPLES_BY_INDUSTRY[resolved_industry][size_class]

    fallback = SDE_MULTIPLES_BY_INDUSTRY.get("other", _GENERIC_SDE_MULTIPLES)
    logger.debug(
        "SDE: no industry match for type=%s industry=%s, using generic %s tier",
        business_type_id,
        industry,
        size_class,
    )
    return fallback[size_class]
