"""
Valuation Request Builder

Main builder class implementing the Builder pattern for creating ValuationRequest
objects with comprehensive validation and data normalization.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.api.schemas import ValuationRequest, YearDataInput
from src.domain.models import BusinessModel
from src.utils.decimal_helpers import from_decimal, to_decimal
from src.utils.logging import get_logger
from src.utils.registry_identity_context import resolve_business_type_id, resolve_registry_identity
from src.utils.sole_trader_detector import SoleTraderDetector

logger = get_logger(__name__)


class ValuationRequestBuilder:
    """
    Builder class for creating ValuationRequest objects.

    This class provides a fluent interface for building ValuationRequest objects
    with validation, normalization, and data quality checks.

    Example:
        builder = ValuationRequestBuilder()
        request = (builder
            .with_company_info("Acme Corp", "BE", "professional-services")
            .with_current_year_data(2024, 1000000, 100000)
            .with_founding_year(2020)
            .build())
    """

    def __init__(self):
        """Initialize the builder with default values."""
        self._company_name: Optional[str] = None
        self._country_code: Optional[str] = None
        self._industry: Optional[str] = None
        self._business_model: Optional[BusinessModel] = None
        self._founding_year: Optional[int] = None
        self._registration_number: Optional[str] = None
        self._kbo_number: Optional[str] = None
        self._kvk_number: Optional[str] = None
        self._vat_number: Optional[str] = None
        self._legal_form: Optional[str] = None
        self._postal_code: Optional[str] = None
        self._city: Optional[str] = None
        self._current_year_data: Optional[YearDataInput] = None
        self._historical_years_data: List[YearDataInput] = []
        self._number_of_employees: Optional[int] = None
        self._number_of_owners: Optional[int] = None
        self._recurring_revenue_percentage: Decimal = Decimal("0.0")
        self._business_type_id: Optional[str] = None
        self._business_type: Optional[str] = None
        self._business_context: Optional[Dict[str, Any]] = None
        self._is_sole_trader: Optional[bool] = None
        self._shares_for_sale: Optional[Decimal] = None
        self._use_dcf: bool = True
        self._use_multiples: bool = True
        self._projection_years: int = 5
        self._methodology: str = "HYBRID"

    def with_company_info(
        self,
        company_name: str,
        country_code: str,
        industry: str,
        business_model: Optional[BusinessModel] = None,
    ) -> "ValuationRequestBuilder":
        """
        Set company information.

        Args:
            company_name: Company name
            country_code: 2-letter ISO country code
            industry: Industry classification
            business_model: Business model type (optional)

        Returns:
            Self for method chaining
        """
        self._company_name = company_name.strip() if company_name else None
        self._country_code = country_code.upper() if country_code else None
        self._industry = industry.strip() if industry else None
        self._business_model = business_model

        return self

    @staticmethod
    def _optional_clean_str(value: object) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    def with_registry_identity(
        self,
        *,
        registration_number: object = None,
        kbo_number: object = None,
        kvk_number: object = None,
        vat_number: object = None,
        legal_form: object = None,
        postal_code: object = None,
        city: object = None,
    ) -> "ValuationRequestBuilder":
        """Set optional company registry identity fields."""
        self._registration_number = self._optional_clean_str(registration_number)
        self._kbo_number = self._optional_clean_str(kbo_number)
        self._kvk_number = self._optional_clean_str(kvk_number)
        self._vat_number = self._optional_clean_str(vat_number)
        self._legal_form = self._optional_clean_str(legal_form)
        self._postal_code = self._optional_clean_str(postal_code)
        self._city = self._optional_clean_str(city)
        return self

    def with_current_year_data(
        self, year: int, revenue: Decimal, ebitda: Decimal, **kwargs
    ) -> "ValuationRequestBuilder":
        """
        Set current year financial data.

        Args:
            year: Fiscal year
            revenue: Annual revenue
            ebitda: EBITDA
            **kwargs: Additional financial fields (net_income, total_assets, etc.)

        Returns:
            Self for method chaining
        """
        self._current_year_data = YearDataInput(year=year, revenue=revenue, ebitda=ebitda, **kwargs)
        return self

    def with_historical_data(
        self, historical_years: List[YearDataInput]
    ) -> "ValuationRequestBuilder":
        """
        Set historical financial data.

        Args:
            historical_years: List of YearDataInput objects

        Returns:
            Self for method chaining
        """
        self._historical_years_data = historical_years
        return self

    def with_founding_year(self, founding_year: int) -> "ValuationRequestBuilder":
        """Set founding year."""
        self._founding_year = founding_year
        return self

    def with_employees(
        self, number_of_employees: Optional[int], number_of_owners: Optional[int] = None
    ) -> "ValuationRequestBuilder":
        """Set employee and owner counts."""
        self._number_of_employees = number_of_employees
        self._number_of_owners = number_of_owners
        return self

    def with_recurring_revenue(self, percentage: Decimal) -> "ValuationRequestBuilder":
        """Set recurring revenue percentage."""
        self._recurring_revenue_percentage = max(Decimal("0.0"), min(Decimal("1.0"), percentage))
        return self

    def with_business_type_id(self, business_type_id: Optional[str]) -> "ValuationRequestBuilder":
        """Set business type ID for database-driven multiples."""
        self._business_type_id = business_type_id
        return self

    def with_business_type(self, business_type: Optional[str]) -> "ValuationRequestBuilder":
        """Set business type (e.g., 'sole-trader', 'company')."""
        self._business_type = business_type
        return self

    def with_is_sole_trader(self, is_sole_trader: Optional[bool]) -> "ValuationRequestBuilder":
        """Set explicit sole trader flag."""
        self._is_sole_trader = is_sole_trader
        return self

    def with_shares_for_sale(self, shares_for_sale: Optional[Decimal]) -> "ValuationRequestBuilder":
        """
        Set percentage of shares for sale (0-100).

        Args:
            shares_for_sale: Percentage of shares being sold (0-100)

        Returns:
            Self for method chaining
        """
        if shares_for_sale is not None:
            # Validate range
            if shares_for_sale < 0 or shares_for_sale > 100:
                logger.warning(
                    f"shares_for_sale out of range (0-100), got: {shares_for_sale}, clamping to valid range"
                )
                shares_for_sale = max(Decimal("0.0"), min(Decimal("100.0"), shares_for_sale))
        self._shares_for_sale = shares_for_sale
        return self

    def with_business_context(self, context: Dict[str, Any]) -> "ValuationRequestBuilder":
        """Set additional business context."""
        self._business_context = context
        return self

    def with_methodology(
        self,
        use_dcf: bool = True,
        use_multiples: bool = True,
        methodology: str = "HYBRID",
        projection_years: int = 5,
    ) -> "ValuationRequestBuilder":
        """Set valuation methodology preferences."""
        self._use_dcf = use_dcf
        self._use_multiples = use_multiples
        self._methodology = methodology
        self._projection_years = projection_years
        return self

    def _normalize_data(self) -> None:
        """
        Normalize and validate data before building.

        This method ensures:
        - Required fields are present
        - Data types are correct
        - Default values are set appropriately
        """
        # Set default business model if not provided
        if not self._business_model:
            # Try to infer from industry
            if self._industry:
                industry_lower = self._industry.lower()
                if any(x in industry_lower for x in ["saas", "software", "tech"]):
                    self._business_model = BusinessModel.B2B_SAAS
                elif any(x in industry_lower for x in ["ecommerce", "online"]):
                    self._business_model = BusinessModel.ECOMMERCE
                elif any(x in industry_lower for x in ["consulting", "professional", "services"]):
                    self._business_model = BusinessModel.SERVICES
                else:
                    self._business_model = BusinessModel.SERVICES  # Default
            else:
                self._business_model = BusinessModel.SERVICES  # Default

        # Set default founding year if not provided
        if not self._founding_year:
            current_year = datetime.now().year
            self._founding_year = current_year - 5  # Default: 5 years ago

        # Normalize country code
        if self._country_code:
            self._country_code = self._country_code.upper()

        resolved_identity = resolve_registry_identity(
            country_code=self._country_code,
            business_context=self._business_context,
            registration_number=self._registration_number,
            kbo_number=self._kbo_number,
            kvk_number=self._kvk_number,
            vat_number=self._vat_number,
            legal_form=self._legal_form,
            postal_code=self._postal_code,
            city=self._city,
        )
        self._registration_number = resolved_identity["registration_number"]
        self._kbo_number = resolved_identity["kbo_number"]
        self._kvk_number = resolved_identity["kvk_number"]
        self._vat_number = resolved_identity["vat_number"]
        self._legal_form = resolved_identity["legal_form"]
        self._postal_code = resolved_identity["postal_code"]
        self._city = resolved_identity["city"]
        self._business_type_id = resolve_business_type_id(
            business_context=self._business_context,
            business_type_id=self._business_type_id,
        )

        # Normalize industry
        if self._industry:
            self._industry = self._industry.strip().lower()

        # Auto-detect sole trader status if not explicitly set
        if self._is_sole_trader is None:
            # Extract business_structure from business_context if available
            business_structure = None
            if self._business_context:
                business_structure = self._business_context.get("business_structure")

            # Detect sole trader status
            self._is_sole_trader = SoleTraderDetector.detect(
                business_structure=business_structure,
                business_type=self._business_type,
                number_of_owners=self._number_of_owners,
                number_of_employees=self._number_of_employees,
                is_sole_trader=None,  # Not explicitly set
                business_context=self._business_context,
            )

            if self._is_sole_trader:
                logger.info(
                    "Sole trader auto-detected",
                    extra={
                        "business_structure": business_structure,
                        "business_type": self._business_type,
                        "number_of_owners": self._number_of_owners,
                        "number_of_employees": self._number_of_employees,
                    },
                )

    def _validate(self) -> None:
        """
        Validate that all required fields are present.

        Raises:
            ValueError: If required fields are missing or invalid
        """
        errors = []

        if not self._company_name:
            errors.append("company_name is required")

        if not self._country_code:
            errors.append("country_code is required")
        elif len(self._country_code) != 2:
            errors.append(f"country_code must be 2 letters, got: {self._country_code}")

        if not self._industry:
            errors.append("industry is required")

        if not self._business_model:
            errors.append("business_model is required")

        if not self._founding_year:
            errors.append("founding_year is required")
        elif not (1900 <= self._founding_year <= 2100):
            errors.append(
                f"founding_year must be between 1900 and 2100, got: {self._founding_year}"
            )

        if not self._current_year_data:
            errors.append("current_year_data is required")
        elif self._current_year_data.revenue <= 0:
            errors.append("current_year_data.revenue must be positive")

        if errors:
            raise ValueError(f"Validation failed: {', '.join(errors)}")

    def build(self) -> ValuationRequest:
        """
        Build and return the ValuationRequest object.

        Returns:
            Validated ValuationRequest object

        Raises:
            ValueError: If validation fails
        """
        # Normalize data
        self._normalize_data()

        # Validate
        self._validate()

        # Build request
        request = ValuationRequest(
            company_name=self._company_name,
            registration_number=self._registration_number,
            kbo_number=self._kbo_number,
            kvk_number=self._kvk_number,
            vat_number=self._vat_number,
            legal_form=self._legal_form,
            country_code=self._country_code,
            industry=self._industry,
            business_model=self._business_model,
            founding_year=self._founding_year,
            current_year_data=self._current_year_data,
            historical_years_data=self._historical_years_data,
            number_of_employees=self._number_of_employees,
            number_of_owners=self._number_of_owners,
            recurring_revenue_percentage=self._recurring_revenue_percentage,
            business_type_id=self._business_type_id,
            business_type=self._business_type,
            is_sole_trader=self._is_sole_trader,
            shares_for_sale=self._shares_for_sale,
            use_dcf=self._use_dcf,
            use_multiples=self._use_multiples,
            projection_years=self._projection_years,
            methodology=self._methodology,
            business_context=self._business_context,
            postal_code=self._postal_code,
            city=self._city,
        )

        logger.info(
            "ValuationRequest built successfully",
            extra={
                "company_name": self._company_name,
                "industry": self._industry,
                "revenue": self._current_year_data.revenue if self._current_year_data else None,
            },
        )

        return request
