"""
API Protocols for Services Layer

Protocol definitions for API types used by services.
These allow services to work with API types without runtime dependencies.
"""

from typing import Protocol, Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime


class FinancialDataProtocol(Protocol):
    """Protocol for FinancialData from valuation_types."""
    
    revenue: Decimal
    ebitda: Decimal
    net_income: Decimal
    total_assets: Decimal
    total_debt: Decimal
    cash: Decimal
    working_capital: Decimal
    capex: Decimal
    depreciation: Decimal
    tax_rate: Decimal
    growth_rate: Decimal
    discount_rate: Decimal
    terminal_growth_rate: Decimal
    year: int


class MarketDataProtocol(Protocol):
    """Protocol for MarketData from valuation_types."""
    
    industry_multiple: Decimal
    market_cap: Decimal
    enterprise_value: Decimal
    pe_ratio: Decimal
    ev_ebitda_ratio: Decimal
    price_to_sales: Decimal
    price_to_book: Decimal
    dividend_yield: Decimal
    beta: Decimal
    risk_free_rate: Decimal
    market_risk_premium: Decimal


class YearDataInputProtocol(Protocol):
    """Protocol for YearDataInput from schemas."""
    
    year: int
    revenue: Optional[Decimal]
    ebitda: Optional[Decimal]
    net_income: Optional[Decimal]
    total_assets: Optional[Decimal]
    total_liabilities: Optional[Decimal]
    equity: Optional[Decimal]


class BusinessTypeProtocol(Protocol):
    """Protocol for BusinessType enum."""
    
    value: str


class IndustryCategoryProtocol(Protocol):
    """Protocol for IndustryCategory enum."""
    
    value: str

