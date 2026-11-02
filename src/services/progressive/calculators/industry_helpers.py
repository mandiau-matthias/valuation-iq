"""
Industry Helpers Module

RESPONSIBILITIES:
- Provide industry-specific multiples
- Map industries to default multiples
- SME-aware multiple selection using academic sources

REFACTORING NOTE:
Extracted from section_calculations.py to improve maintainability and reduce file size.

ACADEMIC SOURCES:
- Trugman (2017): AICPA SME valuation standard
- Coulon (2021): European SME specialist
- VFB Belgium (2024): Belgian market data
- Pepperdine (2024): SME transaction database
"""

from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

# Import SME selector for academic-based multiples
try:
    from src.services.academic.sme_multiple_selector import get_sme_selector

    SME_SELECTOR_AVAILABLE = True
except ImportError:
    SME_SELECTOR_AVAILABLE = False

DEFAULT_REVENUE_MULTIPLE = Decimal("1.5")
DEFAULT_EBITDA_MULTIPLE = Decimal("8.0")
DEFAULT_INDUSTRY_FALLBACK_MULTIPLES: Mapping[str, tuple[Decimal, Decimal]] = {
    "software": (Decimal("3.5"), Decimal("12.0")),
    "saas": (Decimal("5.0"), Decimal("15.0")),
    "technology": (Decimal("3.0"), Decimal("10.0")),
    "ecommerce": (Decimal("1.5"), Decimal("8.0")),
    "retail": (Decimal("0.5"), Decimal("6.0")),
    "services": (Decimal("1.0"), Decimal("7.0")),
    "manufacturing": (Decimal("0.8"), Decimal("6.5")),
    "healthcare": (Decimal("2.0"), Decimal("9.0")),
}


class IndustryHelpers:
    """
    Provides industry-specific multiples with SME-awareness.

    Uses academic sources (Trugman, Coulon, VFB Belgium) for SME valuations.
    Falls back to large company multiples for companies > €50M revenue.
    """

    @staticmethod
    def get_industry_revenue_multiple(industry: str, revenue: Optional[Decimal] = None) -> Decimal:
        """
        Get revenue multiple for industry with SME-awareness.

        If revenue provided and company is SME (< €50M), uses academic SME sources:
        - Trugman (2017): SME revenue multiples
        - West (2012): Small business valuation

        Otherwise, uses large company defaults.

        Args:
            industry: Industry name
            revenue: Optional annual revenue for SME classification

        Returns:
            Revenue multiple
        """
        # Use SME selector if revenue provided and SME selector available
        if revenue is not None and SME_SELECTOR_AVAILABLE:
            selector = get_sme_selector()
            sme_class = selector.classify_sme(revenue)

            # Use SME multiples for micro, small, medium
            if sme_class in ["micro", "small", "medium"]:
                multiple, rationale = selector.get_sme_revenue_multiple(revenue, industry)
                return multiple

        # Fallback to large company multiples
        revenue_multiple, _ = DEFAULT_INDUSTRY_FALLBACK_MULTIPLES.get(
            industry.lower(),
            (DEFAULT_REVENUE_MULTIPLE, DEFAULT_EBITDA_MULTIPLE),
        )
        return revenue_multiple

    @staticmethod
    def get_industry_ebitda_multiple(
        industry: str,
        revenue: Optional[Decimal] = None,
        country: str = "Belgium",  # WORLD-CLASS: Belgium-first geographic strategy
        business_type: Optional[
            str
        ] = None,  # WORLD-CLASS: Business type ID for business-type-specific multiples
        founded_year: Optional[
            int
        ] = None,  # WORLD-CLASS: Founded year for growth stage determination
        current_year: Optional[
            int
        ] = None,  # WORLD-CLASS: Current year for growth stage determination
        historical_data: Optional[
            List[Dict[str, Any]]
        ] = None,  # WORLD-CLASS: Historical data for growth stage determination
    ) -> Decimal:
        """
        Get EBITDA multiple for industry with SME-awareness.

        WORLD-CLASS BUSINESS TYPE INTEGRATION:
        - Uses business_type for business-type-specific multiple selection
        - Applies owner dependency adjustments
        - Uses business-type-specific margin adjustments

        If revenue provided and company is SME (< €50M), uses academic SME sources:
        - VFB Belgium (2024): Belgian SME market data
        - Vlerick (2023): Belgian M&A research
        - Pepperdine (2024): SME transaction database
        - Coulon (2021): European SME specialist

        Otherwise, uses large company defaults.

        Args:
            industry: Industry name
            revenue: Optional annual revenue for SME classification
            country: Country for market-specific multiples (default: Belgium)
            business_type: Optional business type ID for business-type-specific multiples

        Returns:
            EBITDA multiple
        """
        # Use SME selector if revenue provided and SME selector available
        if revenue is not None and SME_SELECTOR_AVAILABLE:
            selector = get_sme_selector()
            sme_class = selector.classify_sme(revenue)

            # Use SME multiples for micro, small, medium
            if sme_class in ["micro", "small", "medium"]:
                # WORLD-CLASS: Pass business_type, founded_year, and historical_data for comprehensive adjustments
                multiple, _sources, _rationale = selector.get_sme_ebitda_multiple(
                    revenue,
                    industry,
                    business_type=business_type,  # WORLD-CLASS: Business type integration
                    country=country,  # WORLD-CLASS: Belgium-first geographic strategy
                    founded_year=founded_year,  # WORLD-CLASS: Growth stage determination
                    current_year=current_year,  # WORLD-CLASS: Growth stage determination
                    historical_data=historical_data,  # WORLD-CLASS: Growth stage determination
                )
                return multiple

        # Fallback to large company multiples
        _, ebitda_multiple = DEFAULT_INDUSTRY_FALLBACK_MULTIPLES.get(
            industry.lower(),
            (DEFAULT_REVENUE_MULTIPLE, DEFAULT_EBITDA_MULTIPLE),
        )
        return ebitda_multiple
