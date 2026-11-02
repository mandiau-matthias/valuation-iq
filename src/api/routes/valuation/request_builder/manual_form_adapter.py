"""
Manual Form Adapter

Converts manual form data to ValuationRequest.
Handles form field mapping, data type conversion, and validation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.schemas import ValuationRequest, YearDataInput
from src.domain.asset_based_support import normalize_business_model
from src.domain.models import BusinessModel
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.fiscal_year import get_current_filing_year
from src.utils.logging import get_logger

from .valuation_request_builder import ValuationRequestBuilder

logger = get_logger(__name__)


class ManualFormAdapter:
    """
    Adapter for converting manual form data to ValuationRequest.

    This adapter handles:
    - Form field mapping (frontend → backend schema)
    - Data type conversion (string → int/float)
    - Historical data processing
    - Default value handling
    """

    @staticmethod
    def convert(form_data: Dict[str, Any]) -> ValuationRequest:
        """
        Convert manual form data to ValuationRequest.

        Args:
            form_data: Form data from frontend

        Returns:
            ValuationRequest object ready for calculation

        Raises:
            ValueError: If required data is missing or invalid
        """
        # Extract company information
        company_name = form_data.get("company_name", "").strip()
        country_code = form_data.get("country_code", "BE").upper()
        industry = form_data.get("industry", "professional-services")

        # Extract business model
        business_model_str = form_data.get("business_model", "service_based")
        business_model = ManualFormAdapter._map_business_model(business_model_str)

        # Extract founding year
        founding_year = int(form_data.get("founding_year", datetime.now().year - 5))

        # Extract current year financial data
        current_year = get_current_filing_year()
        revenue = to_decimal(form_data.get("revenue", 0))
        ebitda = to_decimal(form_data.get("ebitda", 0))

        # Build current year data with optional fields
        current_year_data = YearDataInput(
            year=current_year,
            revenue=revenue,
            ebitda=ebitda,
            net_income=ManualFormAdapter._safe_float(form_data.get("net_income")),
            total_assets=ManualFormAdapter._safe_float(form_data.get("total_assets")),
            total_liabilities=ManualFormAdapter._safe_float(form_data.get("total_debt")),
            cash=ManualFormAdapter._safe_float(form_data.get("cash")),
        )

        # Extract historical data
        historical_years_data = ManualFormAdapter._extract_historical_data(form_data)

        # Extract employee and owner data
        number_of_employees = ManualFormAdapter._safe_int(
            form_data.get("number_of_employees") or form_data.get("employee_count")
        )
        number_of_owners = ManualFormAdapter._safe_int(form_data.get("number_of_owners"))

        # Extract recurring revenue percentage
        recurring_revenue_percentage = to_decimal(
            form_data.get("recurring_revenue_percentage", Decimal("0.0"))
        )

        # Extract business type ID
        business_type_id = form_data.get("business_type_id")

        # Extract business structure (form field) → business_type (schema field)
        business_structure = form_data.get("business_structure")
        business_type = None
        if business_structure:
            # Map "Company (with shareholders)" → "company"
            # Map "Sole Trader" → "sole-trader"
            business_structure_lower = business_structure.lower()
            if "sole" in business_structure_lower or "trader" in business_structure_lower:
                business_type = "sole-trader"
            elif "company" in business_structure_lower or "shareholder" in business_structure_lower:
                business_type = "company"

        # Also check if business_type is directly provided (fallback)
        if not business_type:
            business_type = form_data.get("business_type")

        # Extract shares_for_sale (percentage of shares being sold)
        shares_for_sale = ManualFormAdapter._safe_float(form_data.get("shares_for_sale", 100))
        if shares_for_sale is None:
            shares_for_sale = Decimal("100.0")  # Default to 100% if not provided

        # Extract methodology preferences
        use_dcf = form_data.get("use_dcf", True)
        use_multiples = form_data.get("use_multiples", True)
        methodology = form_data.get("methodology", "HYBRID")
        projection_years = int(form_data.get("projection_years", 5))

        # Build ValuationRequest using builder
        builder = ValuationRequestBuilder()

        request_builder = (
            builder.with_company_info(company_name, country_code, industry, business_model)
            .with_registry_identity(
                registration_number=form_data.get("registration_number"),
                kbo_number=form_data.get("kbo_number"),
                kvk_number=form_data.get("kvk_number"),
                vat_number=form_data.get("vat_number"),
                legal_form=form_data.get("legal_form"),
                postal_code=form_data.get("postal_code"),
                city=form_data.get("city"),
            )
            .with_current_year_data(
                current_year,
                revenue,
                ebitda,
                net_income=current_year_data.net_income,
                total_assets=current_year_data.total_assets,
                total_liabilities=current_year_data.total_liabilities,
                cash=current_year_data.cash,
            )
            .with_historical_data(historical_years_data)
            .with_founding_year(founding_year)
            .with_employees(number_of_employees, number_of_owners)
            .with_recurring_revenue(recurring_revenue_percentage)
            .with_business_type_id(business_type_id)
            .with_business_type(business_type)
            .with_shares_for_sale(shares_for_sale)
            .with_methodology(use_dcf, use_multiples, methodology, projection_years)
        )
        if isinstance(form_data.get("business_context"), dict):
            request_builder = request_builder.with_business_context(form_data["business_context"])

        request = request_builder.build()

        logger.info(
            "Manual form data converted to ValuationRequest",
            extra={
                "company_name": company_name,
                "industry": industry,
                "revenue": revenue,
                "source": "manual_form",
            },
        )

        return request

    @staticmethod
    def _map_business_model(business_model_str: str) -> BusinessModel:
        """Map business model string to the shared normalized enum."""
        return normalize_business_model(business_model_str)

    @staticmethod
    def _extract_historical_data(form_data: Dict[str, Any]) -> List[YearDataInput]:
        """
        Extract historical financial data from form.

        Args:
            form_data: Form data containing historical years

        Returns:
            List of YearDataInput objects
        """
        historical_years_data = []

        # Check if historical_years_data is already a list of YearDataInput
        if "historical_years_data" in form_data:
            hist_data = form_data["historical_years_data"]
            if isinstance(hist_data, list):
                for year_data in hist_data:
                    if isinstance(year_data, dict):
                        historical_years_data.append(YearDataInput(**year_data))
                    elif isinstance(year_data, YearDataInput):
                        historical_years_data.append(year_data)

        # Check for year-specific fields (e.g., "2024_revenue", "2024_ebitda")
        current_year = get_current_filing_year()
        for year_offset in range(1, 4):  # Last 3 years
            year = current_year - year_offset
            year_str = str(year)

            revenue_key = f"{year_str}_revenue"
            ebitda_key = f"{year_str}_ebitda"

            if revenue_key in form_data or ebitda_key in form_data:
                revenue = ManualFormAdapter._safe_float(form_data.get(revenue_key, 0))
                ebitda = ManualFormAdapter._safe_float(form_data.get(ebitda_key, 0))

                if revenue > 0:  # Only add if revenue is provided
                    historical_years_data.append(
                        YearDataInput(year=year, revenue=revenue, ebitda=ebitda)
                    )

        historical_years_data.sort(key=lambda x: x.year)
        return historical_years_data

    @staticmethod
    def _safe_float(value: Any) -> Optional[Decimal]:
        """Safely convert value to float, returning None if invalid."""
        if value is None:
            return None
        try:
            return to_decimal(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        """Safely convert value to int, returning None if invalid."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
