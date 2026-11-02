"""
Base Registry Client

Defines the interface for all registry clients in the registry-first architecture.
Each country's registry client must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from src.utils.core import format_currency
from decimal import Decimal


class RegistrySearchResult(BaseModel):
    """Standardized search result from any registry."""

    # Explicit result type for type-safe detection
    result_type: Literal["COMPANY", "SUGGESTION", "ERROR"] = Field(
        default="COMPANY",
        description="Type of result: COMPANY (real company), SUGGESTION (search help), ERROR (error info)"
    )

    company_id: str = Field(..., description="Unique company identifier in registry")
    company_name: str = Field(..., description="Official company name")
    registration_number: str = Field(..., description="Registration/company number")
    country_code: str = Field(default="BE", description="2-letter country code (e.g., BE, NL, DE)")
    legal_form: Optional[str] = Field(None, description="Legal form (Ltd, BV, GmbH, etc.)")
    address: Optional[str] = Field(None, description="Registered address")
    status: str = Field(..., description="Company status (active, dissolved, etc.)")
    confidence_score: Decimal = Field(..., ge=0.0, le=1.0, description="Search confidence (0-1)")
    registry_name: str = Field(..., description="Source registry name")
    registry_url: Optional[str] = Field(None, description="Direct link to registry entry")
    website: Optional[str] = Field(None, description="Company website URL")
    nace_code: Optional[str] = Field(None, description="Canonical 4-digit NACE code")
    nace_description: Optional[str] = Field(None, description="NACE/SBI activity description")
    activity_code: Optional[str] = Field(None, description="Market-facing activity code (e.g. SBI)")
    activity_label: Optional[str] = Field(None, description="Market-facing activity label")
    taxonomy: Optional[str] = Field(None, description="Activity taxonomy (e.g. NACE_REV2, SBI_2008)")
    canonical_nace_code: Optional[str] = Field(None, description="Canonical NACE code for downstream mapping")
    postal_code: Optional[str] = Field(None, description="Postal code")
    city: Optional[str] = Field(None, description="City")


class FinancialFilingYear(BaseModel):
    """Financial data for a specific year."""

    year: int = Field(..., description="Financial year")
    revenue: Optional[Decimal] = Field(None, description="Annual revenue")
    ebitda: Optional[Decimal] = Field(None, description="EBITDA")
    net_income: Optional[Decimal] = Field(None, description="Net income")
    total_assets: Optional[Decimal] = Field(None, description="Total assets")
    total_debt: Optional[Decimal] = Field(None, description="Total debt")
    cash: Optional[Decimal] = Field(None, description="Cash and equivalents")
    cost_of_goods_sold: Optional[Decimal] = Field(None, description="Cost of goods sold")
    operating_expenses: Optional[Decimal] = Field(None, description="Operating expenses")
    filing_date: Optional[datetime] = Field(None, description="Date filed with registry")
    source_url: Optional[str] = Field(None, description="Link to filing document")


class RegistryFinancialData(BaseModel):
    """Complete financial data from registry."""

    company_id: str = Field(..., description="Company identifier")
    company_name: str = Field(..., description="Company name")
    registration_number: str = Field(..., description="Registration number")
    country_code: str = Field(..., description="2-letter country code")
    legal_form: str = Field(..., description="Legal form")

    # Financial history
    filing_history: List[FinancialFilingYear] = Field(..., description="Historical financial data")

    # Company metadata
    founding_year: Optional[int] = Field(None, description="Year founded")
    industry_code: Optional[str] = Field(None, description="Industry classification code")
    industry_description: Optional[str] = Field(None, description="Industry description")
    employees: Optional[int] = Field(None, description="Number of employees")
    website: Optional[str] = Field(None, description="Company website")

    # Data quality
    data_source: str = Field(..., description="Source registry name")
    source_url: Optional[str] = Field(None, description="Link to registry entry")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last data update")
    completeness_score: Decimal = Field(..., ge=0.0, le=1.0, description="Data completeness (0-1)")


class RegistryClient(ABC):
    """
    Abstract base class for registry clients.

    Each country's registry client must implement this interface to ensure
    consistent behavior across different registries.
    """

    def __init__(self, api_key: Optional[str] = None, timeout: Decimal = 30.0):
        """Initialize registry client."""
        self.api_key = api_key
        self.timeout = timeout
        self.registry_name = self.get_registry_name()
        self.country_code = self.get_country_code()

    @abstractmethod
    def get_registry_name(self) -> str:
        """Return the human-readable name of this registry."""
        pass

    @abstractmethod
    def get_country_code(self) -> str:
        """Return the 2-letter country code."""
        pass

    @abstractmethod
    async def search_companies(
        self, 
        company_name: str, 
        limit: int = 10
    ) -> List[RegistrySearchResult]:
        """
        Search for companies by name.

        Args:
            company_name: Company name to search for
            limit: Maximum number of results

        Returns:
            List of matching companies
        """
        pass

    @abstractmethod
    async def get_company_financials(
        self, 
        company_id: str, 
        years: Optional[int] = None
    ) -> Optional[RegistryFinancialData]:
        """
        Fetch financial data for a specific company.

        Args:
            company_id: Company identifier from search results
            years: Number of years of history to fetch (None = all available)

        Returns:
            Complete financial data or None if not found
        """
        pass

    @abstractmethod
    async def get_company_details(self, company_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch additional company details (metadata, not financials).

        Args:
            company_id: Company identifier

        Returns:
            Company details or None if not found
        """
        pass

    def calculate_completeness_score(self, data: RegistryFinancialData) -> Decimal:
        """
        Calculate data completeness score (0-1).

        Higher score = more complete data for valuation.
        """
        # Bank-grade: Use Decimal for scoring precision
        score = Decimal('0.0')
        total_checks = 0

        if data.filing_history:
            latest = data.filing_history[0]
            total_checks += 6

            # Required fields - Bank-grade: Decimal increments
            if latest.revenue is not None:
                score += Decimal('1.0')
            if latest.ebitda is not None:
                score += Decimal('1.0')
            if latest.net_income is not None:
                score += Decimal('1.0')
            if latest.total_assets is not None:
                score += Decimal('1.0')
            if latest.total_debt is not None:
                score += Decimal('1.0')
            if latest.cash is not None:
                score += Decimal('1.0')

        # Historical data bonus
        if len(data.filing_history) >= 3:
            score += Decimal('0.2')
        elif len(data.filing_history) >= 2:
            score += Decimal('0.1')

        # Metadata bonus
        if data.industry_description:
            score += Decimal('0.1')
        if data.employees is not None:
            score += Decimal('0.1')

        # Bank-grade: Decimal division
        return min(score / Decimal(str(total_checks + 0.4)), Decimal('1.0'))

    def format_currency(self, amount: Decimal, country_code: str) -> str:
        """
        Format currency amount for display using unified utility.
        
        Delegates to src.utils.core.format_currency for consistency.
        Maps country codes to currency codes.
        """
        # Map country codes to currency codes
        currency_map = {
            "GB": "GBP",  # Great Britain -> British Pound
            "UK": "GBP",  # United Kingdom -> British Pound
            "US": "USD",  # United States -> US Dollar
            "CA": "USD",  # Canada -> US Dollar (or CAD if needed)
        }
        
        currency = currency_map.get(country_code.upper(), "EUR")  # Default to EUR
        return format_currency(amount, currency=currency, precision=0)

    def get_registry_url(self, company_id: str) -> Optional[str]:
        """Get direct URL to company's registry entry."""
        # Override in subclasses to provide registry-specific URLs
        return None
