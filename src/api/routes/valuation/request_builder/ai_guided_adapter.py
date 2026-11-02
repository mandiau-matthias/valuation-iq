"""
AI-Guided Adapter

Converts AI-guided conversation data to ValuationRequest.
Handles session data extraction, business type mapping, and data validation.
"""

import re
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.schemas import ValuationRequest, YearDataInput
from src.api.schemas.partial_valuation import PartialValuationRequest
from src.domain.asset_based_support import normalize_business_model
from src.domain.models import BusinessModel
from src.utils.decimal_helpers import optional_decimal, to_decimal
from src.utils.logging import get_logger

from .ai_guided_normalization import (
    business_context_from_sources,
    business_model_from_sources,
    business_structure_from_sources,
    business_type_from_sources,
    business_type_id_from_sources,
    company_name_from_sources,
    country_code_from_sources,
    employee_count_from_sources,
    industry_from_sources,
    normalize_shares_for_sale,
    owner_count_from_sources,
    registry_identity,
    sole_trader_from_sources,
)
from .ai_guided_partial import (
    optional_amount,
    partial_ai_guided_request,
    supplied_fiscal_year,
    supplied_founding_year,
)
from .ai_guided_request_assembly import (
    AIGuidedRequestParts,
    build_ai_guided_request,
    build_current_year_data,
    conversion_log_context,
    request_input_log_context,
)

logger = get_logger(__name__)


class AIGuidedAdapter:
    """
    Adapter for converting AI-guided conversation data to ValuationRequest.

    This adapter handles:
    - Session data extraction (conversation context)
    - Business type mapping (from AI-guided flow to calculation triage)
    - Data normalization and validation
    - Default value handling
    """

    @staticmethod
    def convert(
        session_data: Dict[str, Any],
        company_info: Optional[Dict[str, Any]] = None,
        collected_data: Optional[Dict[str, Any]] = None,
    ) -> ValuationRequest | PartialValuationRequest:
        """
        Convert AI-guided conversation data to ValuationRequest.

        Args:
            session_data: Session data from conversation
            company_info: Company information from conversation
            collected_data: Collected financial data from conversation

        Returns:
            ValuationRequest object ready for calculation

        Raises:
            ValueError: If required data is missing or invalid
        """
        # Merge all data sources
        company_info = (
            company_info if company_info is not None else session_data.get("company_info", {})
        )
        collected_data = (
            collected_data
            if collected_data is not None
            else session_data.get("collected_data", session_data)
        )

        company_name = company_name_from_sources(
            company_info=company_info,
            collected_data=collected_data,
        )

        # Extract country_code with validation
        # CRITICAL: Ensure country_code is always a valid 2-letter code
        country_resolution = country_code_from_sources(
            company_info=company_info,
            collected_data=collected_data,
        )
        partial = partial_ai_guided_request(
            collected_data,
            company_info,
            country=country_resolution.code,
            company_name=company_name,
        )
        if partial is not None:
            return partial

        logger.info(
            "Country code extracted and validated successfully",
            extra={
                "country_code_raw": country_resolution.raw,
                "country_code_final": country_resolution.code,
            },
        )

        industry = industry_from_sources(
            company_info=company_info,
            collected_data=collected_data,
        )

        # Extract business model
        business_model_str = business_model_from_sources(
            company_info=company_info,
            collected_data=collected_data,
        )
        business_model = AIGuidedAdapter._map_business_model(business_model_str)

        # Extract founding year
        founding_year = AIGuidedAdapter._extract_founding_year(collected_data, company_info)
        assert founding_year is not None

        # Extract current year financial data
        current_year = supplied_fiscal_year(collected_data)
        revenue = optional_amount(collected_data, "revenue")
        ebitda = optional_amount(collected_data, "ebitda")
        assert current_year is not None and revenue is not None and ebitda is not None
        assert country_resolution.code is not None

        current_year_data = build_current_year_data(
            collected_data=collected_data,
            current_year=current_year,
            revenue=revenue,
            ebitda=ebitda,
        )

        # Extract employee and owner data
        number_of_employees = employee_count_from_sources(
            company_info=company_info,
            collected_data=collected_data,
        )

        number_of_owners = owner_count_from_sources(collected_data=collected_data)

        # Extract shares_for_sale (percentage of equity being valued)
        shares_for_sale = normalize_shares_for_sale(collected_data.get("shares_for_sale"))

        # Extract recurring revenue percentage (default to 0.0)
        recurring_revenue_percentage = to_decimal(
            collected_data.get("recurring_revenue_percentage", Decimal("0.0"))
        )

        # Extract business type ID (for database-driven multiples)
        business_type_id = business_type_id_from_sources(
            session_data=session_data,
            company_info=company_info,
            collected_data=collected_data,
        )

        # Extract business_type from business_structure (like manual form does)
        # Map business_structure → business_type
        business_structure = business_structure_from_sources(
            company_info=company_info,
            collected_data=collected_data,
        )
        business_type = business_type_from_sources(
            business_structure=business_structure,
            company_info=company_info,
            collected_data=collected_data,
        )

        # Extract historical data (if provided)
        historical_years_data = AIGuidedAdapter._extract_historical_data(collected_data)

        # Determine is_sole_trader from business_structure or explicit flag
        # CRITICAL: This must match manual form logic exactly
        is_sole_trader = sole_trader_from_sources(
            business_structure=business_structure,
            collected_data=collected_data,
        )

        business_context = business_context_from_sources(
            session_data=session_data,
            company_info=company_info,
            collected_data=collected_data,
        )

        parts = AIGuidedRequestParts(
            company_name=company_name,
            country_code=country_resolution.code,
            industry=industry,
            business_model=business_model,
            founding_year=founding_year,
            current_year=current_year,
            revenue=revenue,
            ebitda=ebitda,
            current_year_data=current_year_data,
            number_of_employees=number_of_employees,
            number_of_owners=number_of_owners,
            recurring_revenue_percentage=recurring_revenue_percentage,
            business_type_id=business_type_id,
            business_type=business_type,
            shares_for_sale=shares_for_sale,
            registry_identity=registry_identity(
                collected_data=collected_data,
                company_info=company_info,
                session_data=session_data,
            ),
            business_context=business_context,
            is_sole_trader=is_sole_trader,
            historical_years_data=historical_years_data,
        )

        # Log all key values before building request
        logger.info(
            "Building ValuationRequest with extracted values",
            extra=request_input_log_context(parts),
        )

        request = build_ai_guided_request(parts)
        request.currency = (
            str(collected_data.get("currency", company_info.get("currency"))).strip().upper()
        )

        logger.info(
            "AI-guided data converted to ValuationRequest",
            extra=conversion_log_context(parts),
        )

        return request

    @staticmethod
    def _map_business_model(business_model_str: str) -> BusinessModel:
        """Map business model string to the shared normalized enum."""
        return normalize_business_model(business_model_str)

    _extract_founding_year = staticmethod(supplied_founding_year)

    @staticmethod
    def _extract_historical_data(collected_data: Dict[str, Any]) -> List[YearDataInput]:
        """
        Extract historical financial data from collected_data.

        Handles both:
        1. Pre-formatted historical_years_data list
        2. Year-specific fields like "2023_revenue", "2023_ebitda"

        Args:
            collected_data: Collected data dictionary

        Returns:
            List of YearDataInput objects
        """
        historical_years_data = []

        # Check if historical_years_data is already a list
        if "historical_years_data" in collected_data:
            hist_data = collected_data["historical_years_data"]
            if isinstance(hist_data, list):
                for year_data in hist_data:
                    if isinstance(year_data, dict):
                        # Convert dict to YearDataInput
                        historical_years_data.append(YearDataInput(**year_data))
                    elif isinstance(year_data, YearDataInput):
                        historical_years_data.append(year_data)

        # Check for year-specific fields (e.g., "2023_revenue", "2023_ebitda")
        explicit_years = {
            int(match.group(1))
            for key in collected_data
            if (match := re.fullmatch(r"(\d{4})_(?:revenue|ebitda)", key))
        }
        for year in sorted(explicit_years):
            year_str = str(year)

            revenue_key = f"{year_str}_revenue"
            ebitda_key = f"{year_str}_ebitda"

            if revenue_key in collected_data or ebitda_key in collected_data:
                revenue = optional_amount(collected_data, revenue_key)
                ebitda = optional_amount(collected_data, ebitda_key)
                if revenue is None or ebitda is None:
                    raise ValueError(
                        "Incomplete historical earnings must use the partial assessment path"
                    )
                historical_years_data.append(
                    YearDataInput(year=year, revenue=revenue, ebitda=ebitda)
                )

        years = [row.year for row in historical_years_data]
        if len(years) != len(set(years)):
            raise ValueError("Duplicate historical reporting periods")
        return sorted(historical_years_data, key=lambda row: row.year)

    _safe_decimal = staticmethod(optional_decimal)
