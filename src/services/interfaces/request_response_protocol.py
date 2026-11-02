"""
Request/Response Protocols for Services

Protocol definitions for valuation request and response objects.
Services can use these protocols instead of importing from API layer.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Protocol

from src.domain.interfaces.request_protocol import (
    CurrentYearDataProtocol,
    HistoricalYearDataProtocol,
)


class ValuationRequestProtocol(Protocol):
    """Protocol for valuation request objects."""

    company_name: str
    registration_number: Optional[str]
    kbo_number: Optional[str]
    kvk_number: Optional[str]
    vat_number: Optional[str]
    legal_form: Optional[str]
    postal_code: Optional[str]
    city: Optional[str]
    business_type_id: Optional[str]
    business_model: Optional[str]
    industry: Optional[str]
    number_of_employees: Optional[int]
    number_of_owners: Optional[int]
    is_sole_trader: Optional[bool]
    business_context: Optional[dict]
    recurring_revenue_percentage: Decimal
    locale: Optional[str]  # Report language: 'nl' (Dutch) or 'en' (English), defaults to 'en'
    presentation_surface: Optional[str]

    @property
    def current_year_data(self) -> "CurrentYearDataProtocol":
        """Current year financial data."""
        ...

    @property
    def historical_years_data(self) -> List["HistoricalYearDataProtocol"]:
        """Historical financial data."""
        ...


class ValuationResponseProtocol(Protocol):
    """Protocol for valuation response objects."""

    valuation_id: Optional[str]
    company_name: Optional[str]
    enterprise_value: Optional[Decimal]
    equity_value: Optional[Decimal]
    methodology: Optional[str]
    confidence_score: Optional[Decimal]

    @property
    def transparency(self) -> Optional[Dict[str, Any]]:
        """Transparency data."""
        ...

    @property
    def steps(self) -> Optional[List[Dict[str, Any]]]:
        """Step outputs."""
        ...


class QuickValuationRequestProtocol(Protocol):
    """Protocol for quick valuation request objects."""

    company_name: str
    revenue: Optional[Decimal]
    ebitda: Optional[Decimal]
    business_type_id: Optional[str]
    industry: Optional[str]
    country_code: Optional[str]
