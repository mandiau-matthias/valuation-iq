"""
Database Adapter

Converts user business profile from database to ValuationRequest.
Handles database query integration, data enrichment, and historical data handling.
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


class DatabaseAdapter:
    """
    Adapter for converting user business profile from database to ValuationRequest.

    This adapter handles:
    - Database query integration
    - Data enrichment from business profile
    - Historical data handling
    - Default value handling for missing data
    """

    @staticmethod
    async def convert(
        user_id: str,
        business_profile: Optional[Dict[str, Any]] = None,
        db_session: Optional[Any] = None,
    ) -> ValuationRequest:
        """
        Convert user business profile from database to ValuationRequest.

        Args:
            user_id: User ID to fetch business profile
            business_profile: Optional pre-fetched business profile
            db_session: Optional database session for queries

        Returns:
            ValuationRequest object ready for calculation

        Raises:
            ValueError: If required data is missing or invalid
        """
        # Fetch business profile if not provided
        if not business_profile and db_session:
            business_profile = await DatabaseAdapter._fetch_business_profile(user_id, db_session)

        if not business_profile:
            raise ValueError(f"Business profile not found for user {user_id}")

        # Extract company information
        company_name = business_profile.get("company_name", "").strip()
        country_code = business_profile.get("country_code", "BE").upper()
        industry = business_profile.get("industry", "professional-services")

        # Extract business model
        business_model_str = business_profile.get("business_model", "service_based")
        business_model = DatabaseAdapter._map_business_model(business_model_str)

        # Extract founding year
        founding_year = int(
            business_profile.get("founding_year")
            or business_profile.get("founded_year")
            or datetime.now().year - 5
        )

        # Extract latest financial data
        latest_financials = business_profile.get("latest_financials") or {}
        current_year = get_current_filing_year()
        revenue = to_decimal(latest_financials.get("revenue", 0))
        ebitda = to_decimal(latest_financials.get("ebitda", 0))

        # Build current year data
        current_year_data = YearDataInput(
            year=current_year,
            revenue=revenue,
            ebitda=ebitda,
            net_income=DatabaseAdapter._safe_float(latest_financials.get("net_income")),
            total_assets=DatabaseAdapter._safe_float(latest_financials.get("total_assets")),
            total_liabilities=DatabaseAdapter._safe_float(latest_financials.get("total_debt")),
            cash=DatabaseAdapter._safe_float(latest_financials.get("cash")),
        )

        # Extract historical data
        historical_years_data = DatabaseAdapter._extract_historical_data(business_profile)

        # Extract employee and owner data
        number_of_employees = DatabaseAdapter._safe_int(business_profile.get("number_of_employees"))
        number_of_owners = DatabaseAdapter._safe_int(business_profile.get("number_of_owners"))

        # Extract recurring revenue percentage
        recurring_revenue_percentage = to_decimal(
            business_profile.get("recurring_revenue_percentage", Decimal("0.0"))
        )

        # Extract business type ID
        business_type_id = business_profile.get("business_type_id")

        # Build ValuationRequest using builder
        builder = ValuationRequestBuilder()

        request_builder = (
            builder.with_company_info(company_name, country_code, industry, business_model)
            .with_registry_identity(
                registration_number=business_profile.get("registration_number"),
                kbo_number=business_profile.get("kbo_number"),
                kvk_number=business_profile.get("kvk_number"),
                vat_number=business_profile.get("vat_number"),
                legal_form=business_profile.get("legal_form"),
                postal_code=business_profile.get("postal_code"),
                city=business_profile.get("city"),
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
            .with_methodology(use_dcf=True, use_multiples=True)
        )
        if isinstance(business_profile.get("business_context"), dict):
            request_builder = request_builder.with_business_context(
                business_profile["business_context"]
            )

        request = request_builder.build()

        logger.info(
            "Database business profile converted to ValuationRequest",
            extra={
                "user_id": user_id,
                "company_name": company_name,
                "industry": industry,
                "revenue": revenue,
                "source": "database_profile",
            },
        )

        return request

    @staticmethod
    async def _fetch_business_profile(user_id: str, db_session: Any) -> Optional[Dict[str, Any]]:
        """
        Fetch business profile from database.

        Args:
            user_id: User ID
            db_session: Database session

        Returns:
            Business profile dictionary or None
        """
        # TODO: Implement database query
        # This would query the business_profiles table
        # For now, return None (caller should provide business_profile)
        logger.warning(
            "Database query not implemented, business_profile should be provided",
            extra={"user_id": user_id},
        )
        return None

    @staticmethod
    def _map_business_model(business_model_str: str) -> BusinessModel:
        """Map business model string to the shared normalized enum."""
        return normalize_business_model(business_model_str)

    @staticmethod
    def _extract_historical_data(business_profile: Dict[str, Any]) -> List[YearDataInput]:
        """
        Extract historical financial data from business profile.

        Args:
            business_profile: Business profile dictionary

        Returns:
            List of YearDataInput objects
        """
        historical_years_data = []

        # Check for historical_financials array
        historical_financials = business_profile.get("historical_financials", [])
        if isinstance(historical_financials, list):
            for year_data in historical_financials:
                if isinstance(year_data, dict):
                    historical_years_data.append(YearDataInput(**year_data))
                elif isinstance(year_data, YearDataInput):
                    historical_years_data.append(year_data)

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
