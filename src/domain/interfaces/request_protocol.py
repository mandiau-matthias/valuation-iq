"""
Valuation Request Protocol

Protocol definition for valuation request objects.
This allows domain layer to work with request objects without
depending on API layer schemas.
"""

from typing import Protocol, Optional, List
from decimal import Decimal
from datetime import date


class ValuationRequestProtocol(Protocol):
    """Protocol for valuation request objects."""
    
    company_name: str
    business_type_id: Optional[str]
    business_model: Optional[str]
    industry: Optional[str]
    number_of_employees: Optional[int]
    number_of_owners: Optional[int]
    is_sole_trader: Optional[bool]
    business_context: Optional[dict]
    locale: Optional[str]  # Report language: 'nl' (Dutch) or 'en' (English), defaults to 'en'
    
    @property
    def current_year_data(self) -> "CurrentYearDataProtocol":
        """Current year financial data."""
        ...
    
    @property
    def historical_years_data(self) -> List["HistoricalYearDataProtocol"]:
        """Historical financial data."""
        ...

    @property
    def forecast_years_data(self) -> List["HistoricalYearDataProtocol"]:
        """Explicit forward-looking financial data for DCF."""
        ...
    
    recurring_revenue_percentage: Decimal


class CurrentYearDataProtocol(Protocol):
    """Protocol for current year financial data."""
    
    revenue: Optional[Decimal]
    ebitda: Optional[Decimal]
    net_income: Optional[Decimal]
    total_assets: Optional[Decimal]
    total_liabilities: Optional[Decimal]
    total_debt: Optional[Decimal]  # Alias for debt
    equity: Optional[Decimal]
    cash: Optional[Decimal]
    debt: Optional[Decimal]
    depreciation: Optional[Decimal]
    capital_expenditures: Optional[Decimal]
    capex: Optional[Decimal]  # Alias for capital_expenditures
    working_capital: Optional[Decimal]


class HistoricalYearDataProtocol(Protocol):
    """Protocol for historical year financial data."""
    
    year: int
    revenue: Optional[Decimal]
    ebitda: Optional[Decimal]
    net_income: Optional[Decimal]
    total_assets: Optional[Decimal]
    total_liabilities: Optional[Decimal]
    equity: Optional[Decimal]

