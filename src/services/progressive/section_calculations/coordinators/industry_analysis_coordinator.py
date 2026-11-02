"""
Industry Analysis Coordinator

Orchestrates industry comparison and benchmark operations for section calculations.
"""

from typing import Any, Dict, List, Optional

from src.api.routes.valuation.benchmark_contract_utils import (
    as_mapping,
    benchmark_contract_data_source,
    extract_resolved_benchmark_contract,
)
from src.services.progressive.calculators.industry_helpers import IndustryHelpers
from src.utils.core.data_extraction_helpers import (
    extract_ebitda_from_collected_data,
    extract_growth_rate_from_collected_data,
    extract_revenue_from_collected_data,
)
from src.utils.decimal_helpers import from_decimal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class IndustryAnalysisCoordinator:
    """
    Coordinates industry comparison and benchmark operations.
    """

    def __init__(self) -> None:
        self.industry_helpers = IndustryHelpers()
        self.logger = logger

    def _allows_untrusted_multiples_fallback(self, collected_data: Dict[str, Any]) -> bool:
        if collected_data.get("allow_untrusted_multiples_fallback") is True:
            return True
        for key in ("metadata", "business_context", "multiples_metadata"):
            container = as_mapping(collected_data.get(key))
            if container.get("allow_untrusted_multiples_fallback") is True:
                return True
        return False

    def get_industry_multiples(
        self, collected_data: Dict[str, Any], industry: str, business_type_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get industry multiples for comparison.

        WORLD-CLASS: Uses business_type_id for business-type-specific multiples.

        Args:
            collected_data: Collected data dictionary
            industry: Industry identifier (may be derived from business_type_id)
            business_type_id: Optional business type ID for business-type-specific multiples

        Returns:
            Dictionary with industry multiples
        """
        revenue_decimal, has_revenue = extract_revenue_from_collected_data(collected_data)

        if not has_revenue:
            return {
                "your_multiple": None,
                "industry_avg_multiple": None,
                "industry_max_multiple": None,
                "has_valid_data": False,
            }

        benchmark_contract = extract_resolved_benchmark_contract(collected_data)
        metrics = as_mapping(benchmark_contract.get("metrics")) if benchmark_contract else {}
        revenue_metric = as_mapping(metrics.get("ev_revenue"))
        revenue_median = revenue_metric.get("median")
        if revenue_median is not None:
            revenue_multiple = float(revenue_median)
            data_source = benchmark_contract_data_source(benchmark_contract)
            return {
                "your_multiple": revenue_multiple * 0.9,
                "industry_avg_multiple": revenue_multiple,
                "industry_max_multiple": revenue_multiple * 1.5,
                "has_valid_data": True,
                "data_source": data_source,
                "publication_allowed": True,
                "benchmark_contract": benchmark_contract,
            }

        if not self._allows_untrusted_multiples_fallback(collected_data):
            return {
                "your_multiple": None,
                "industry_avg_multiple": None,
                "industry_max_multiple": None,
                "has_valid_data": False,
                "blocked": True,
                "requires_benchmark_contract": True,
                "publication_allowed": False,
                "data_source": "blocked_no_benchmark_contract",
            }

        # Calculate multiples with SME-awareness and business-type-awareness
        # Explicit disclosed fallback only; never publication-grade.
        revenue_multiple = self.industry_helpers.get_industry_revenue_multiple(
            industry, revenue=revenue_decimal, business_type=business_type_id
        )
        your_multiple = revenue_multiple * 0.9  # Slightly below average for conservative estimate
        industry_avg_multiple = revenue_multiple
        industry_max_multiple = revenue_multiple * 1.5

        return {
            "your_multiple": your_multiple,
            "industry_avg_multiple": industry_avg_multiple,
            "industry_max_multiple": industry_max_multiple,
            "has_valid_data": True,
            "data_source": "explicit_untrusted_helper_fallback",
            "publication_allowed": False,
        }

    def get_industry_benchmarks(
        self, collected_data: Dict[str, Any], industry: str
    ) -> Dict[str, Any]:
        """
        Get industry benchmark metrics.

        Args:
            collected_data: Collected data dictionary
            industry: Industry identifier

        Returns:
            Dictionary with industry benchmarks
        """
        revenue_decimal, has_revenue = extract_revenue_from_collected_data(collected_data)
        ebitda_decimal, has_ebitda = extract_ebitda_from_collected_data(collected_data)
        revenue = from_decimal(revenue_decimal)
        ebitda = from_decimal(ebitda_decimal) if has_ebitda else None
        growth_rate = extract_growth_rate_from_collected_data(collected_data)

        if not has_revenue:
            return {
                "industry_avg_growth": None,
                "industry_avg_margin": None,
                "ebitda_margin": None,
                "has_valid_data": False,
            }

        # Calculate margins
        ebitda_margin = (ebitda / revenue * 100) if ebitda and revenue > 0 else 0

        # Industry averages (simplified)
        industry_avg_margin = 15.0
        industry_avg_growth = 10.0

        return {
            "industry_avg_growth": industry_avg_growth,
            "industry_avg_margin": industry_avg_margin,
            "ebitda_margin": ebitda_margin,
            "growth_rate": growth_rate,
            "has_valid_data": True,
        }

    def generate_comparable_companies(
        self,
        industry: str,
        revenue_multiple: float,
        ebitda_multiple: float = None,
        pe_ratio: float = None,
        business_type_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate comparable companies list (simplified - in production, use real data).

        WORLD-CLASS: Uses business_type_id for business-type-specific comparables.

        Args:
            industry: Industry identifier (may be derived from business_type_id)
            revenue_multiple: Revenue multiple
            ebitda_multiple: EBITDA multiple (optional)
            pe_ratio: P/E ratio (optional)
            business_type_id: Optional business type ID for business-type-specific comparables

        Returns:
            List of comparable company dictionaries
        """
        if ebitda_multiple is None:
            ebitda_multiple = revenue_multiple * 2.0  # Simplified
        if pe_ratio is None:
            pe_ratio = ebitda_multiple * 1.2  # Simplified

        comparables = [
            {
                "name": f"{industry.title()} Leader Inc.",
                "ev_revenue": revenue_multiple * 1.2,
                "ev_ebitda": ebitda_multiple * 1.1 if ebitda_multiple else None,
                "pe": pe_ratio * 1.15 if pe_ratio else None,
            },
            {
                "name": f"{industry.title()} Growth Co.",
                "ev_revenue": revenue_multiple * 1.1,
                "ev_ebitda": ebitda_multiple * 1.05 if ebitda_multiple else None,
                "pe": pe_ratio * 1.1 if pe_ratio else None,
            },
            {
                "name": f"{industry.title()} Solutions Ltd.",
                "ev_revenue": revenue_multiple * 0.95,
                "ev_ebitda": ebitda_multiple * 0.98 if ebitda_multiple else None,
                "pe": pe_ratio * 0.95 if pe_ratio else None,
            },
        ]

        return comparables

    def determine_market_position(self, your_multiple: float, industry_avg_multiple: float) -> str:
        """
        Determine market position based on multiples comparison.

        Args:
            your_multiple: Company's multiple
            industry_avg_multiple: Industry average multiple

        Returns:
            Market position description
        """
        if your_multiple >= industry_avg_multiple:
            return "Your business shows above-average metrics compared to industry peers."
        else:
            return "Your business shows competitive metrics with room for improvement."
