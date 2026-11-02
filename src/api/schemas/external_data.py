"""
External Data Schemas for ValuationIQ.

These schemas define the structure of data that comes from Titan API,
replacing direct database and external API connections in ValuationIQ.

Architecture:
- Titan API fetches data from databases and external APIs (FMP, ECB, OECD)
- ValuationIQ receives this data as part of the valuation request
- ValuationIQ becomes a pure computation engine with no external dependencies
  (except Redis for optional caching). Titan owns AI orchestration.

@module ExternalDataSchemas
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from decimal import Decimal


class IndustryMultiplesInput(BaseModel):
    """
    Industry multiples from FMP or business types database.
    
    These multiples are used for market-based valuation when
    database-driven calibration data is not available.
    """
    
    # Industry identifier
    industry: str = Field(..., description="Industry identifier (normalized)")
    
    # EV/EBITDA multiple distribution
    ev_ebitda_median: Optional[float] = Field(None, description="EV/EBITDA median multiple")
    ev_ebitda_p25: Optional[float] = Field(None, description="EV/EBITDA 25th percentile")
    ev_ebitda_p75: Optional[float] = Field(None, description="EV/EBITDA 75th percentile")
    
    # EV/Revenue multiple distribution
    ev_revenue_median: Optional[float] = Field(None, description="EV/Revenue median multiple")
    ev_revenue_p25: Optional[float] = Field(None, description="EV/Revenue 25th percentile")
    ev_revenue_p75: Optional[float] = Field(None, description="EV/Revenue 75th percentile")
    
    # P/E ratio distribution
    pe_ratio_median: Optional[float] = Field(None, description="P/E ratio median")
    pe_ratio_p25: Optional[float] = Field(None, description="P/E ratio 25th percentile")
    pe_ratio_p75: Optional[float] = Field(None, description="P/E ratio 75th percentile")
    
    # Data quality metadata
    source: str = Field("unknown", description="Data source (FMP, Damodaran, etc.)")
    sample_size: Optional[int] = Field(None, description="Number of data points")
    last_updated: Optional[str] = Field(None, description="Last update timestamp (ISO format)")


class EconomicIndicatorsInput(BaseModel):
    """
    Economic indicators from ECB/OECD.
    
    These are used for DCF calculations (risk-free rate, terminal growth)
    and market context assessment.
    """
    
    # Country identifier
    country_code: str = Field(..., description="ISO 2-letter country code")
    
    # Risk-free rate (critical for WACC/DCF)
    risk_free_rate: float = Field(..., ge=0.0, le=0.5, description="10-year government bond yield")
    
    # Economic growth indicators
    gdp_growth_rate: Optional[float] = Field(None, description="GDP growth rate (annual %)")
    inflation_rate: Optional[float] = Field(None, description="Inflation rate (annual %)")
    unemployment_rate: Optional[float] = Field(None, description="Unemployment rate (%)")
    policy_rate: Optional[float] = Field(None, description="Central bank policy rate")
    
    # Data sources
    sources: Optional[Dict[str, Optional[str]]] = Field(
        None,
        description="Data sources: {risk_free_rate, gdp_growth_rate, inflation_rate}"
    )
    
    # Metadata
    last_updated: Optional[str] = Field(None, description="Last update timestamp (ISO format)")


class ComparableCompanyInput(BaseModel):
    """
    Comparable public company data from FMP.
    
    Used for market-based valuation and benchmarking.
    """
    
    # Company identification
    name: str = Field(..., description="Company name")
    symbol: str = Field(..., description="Stock symbol")
    
    # Financials
    market_cap: float = Field(..., ge=0, description="Market capitalization in EUR")
    enterprise_value: Optional[float] = Field(None, description="Enterprise value in EUR")
    revenue: Optional[float] = Field(None, description="Revenue in EUR")
    ebitda: Optional[float] = Field(None, description="EBITDA in EUR")
    
    # Valuation multiples
    ev_ebitda: Optional[float] = Field(None, description="EV/EBITDA multiple")
    ev_revenue: Optional[float] = Field(None, description="EV/Revenue multiple")
    pe_ratio: Optional[float] = Field(None, description="P/E ratio")
    
    # Classification
    industry: str = Field(..., description="Industry classification")
    sector: str = Field("", description="Sector classification")
    country: str = Field("", description="Country")


class MarketDataInput(BaseModel):
    """
    Complete market data payload from Titan API.
    
    This is the main schema for external market data that ValuationIQ
    receives from Titan. It replaces direct FMP/ECB/OECD API calls.
    
    Usage in valuation:
    - industry_multiples: Used for market-based valuation fallback
    - economic_indicators: Used for DCF (risk-free rate, growth rates)
    - comparable_companies: Used for peer comparison and benchmarking
    """
    
    # Industry-specific multiples from FMP
    industry_multiples: Optional[IndustryMultiplesInput] = Field(
        None,
        description="Industry-specific valuation multiples from FMP"
    )
    
    # Country economic indicators from ECB/OECD
    economic_indicators: Optional[EconomicIndicatorsInput] = Field(
        None,
        description="Country economic indicators from ECB/OECD"
    )
    
    # Comparable public companies from FMP
    comparable_companies: List[ComparableCompanyInput] = Field(
        default=[],
        description="List of comparable public companies"
    )
    
    # Metadata
    fetched_at: str = Field(..., description="When the data was fetched (ISO timestamp)")
    source: str = Field("titan-api", description="Data source (always 'titan-api')")


class BusinessTypeDataInput(BaseModel):
    """
    Business type enrichment data from Titan.
    
    This represents the data from the business_types database
    that Titan enriches the request with.
    
    Note: This is already partially implemented in the main schemas.py
    via fields like sme_calibration, sde_calibration, etc.
    This schema is for reference and potential future consolidation.
    """
    
    # Identification
    id: str = Field(..., description="Business type ID")
    title: str = Field(..., description="Business type title")
    
    # Classification
    category_id: str = Field(..., description="Category ID")
    industry: Optional[str] = Field(None, description="Industry classification")
    sector: Optional[str] = Field(None, description="Sector classification")
    
    # Multiples (with distributions)
    ev_ebitda_multiple: Optional[Dict[str, Any]] = Field(None, description="EV/EBITDA distribution")
    ev_revenue_multiple: Optional[Dict[str, Any]] = Field(None, description="EV/Revenue distribution")
    pe_ratio: Optional[Dict[str, Any]] = Field(None, description="P/E ratio distribution")
    
    # SME Calibration
    sme_calibration: Optional[Dict[str, Any]] = Field(None, description="SME tier-specific multiples")
    
    # SDE Calibration
    sde_calibration: Optional[Dict[str, Any]] = Field(None, description="SDE multiples for small businesses")
    
    # Asset-Based Calibration
    asset_based_calibration: Optional[Dict[str, Any]] = Field(None, description="Asset-based factors")
    
    # Preferences
    valuation_preferences: Optional[Dict[str, Any]] = Field(None, description="Methodology preferences")


class ExternalDataInput(BaseModel):
    """
    Complete external data package from Titan API.
    
    This is the top-level schema that combines all external data
    that ValuationIQ receives from Titan, making ValuationIQ
    a pure valuation engine without external dependencies.
    
    Fields:
    - market_data: Real-time market data from FMP/ECB/OECD
    - business_type_data: Static business type data from database
    
    Note: business_type_data fields are currently spread across
    the main ValuationRequest schema (sme_calibration, sde_calibration, etc.)
    """
    
    # Market data from external APIs
    market_data: Optional[MarketDataInput] = Field(
        None,
        description="Market data from FMP/ECB/OECD via Titan API"
    )
    
    # Business type data from database (for future consolidation)
    business_type_data: Optional[BusinessTypeDataInput] = Field(
        None,
        description="Business type enrichment data from Titan"
    )


# Default values for when external data is not provided
DEFAULT_RISK_FREE_RATE = 0.03  # 3% default
DEFAULT_GDP_GROWTH = 0.015  # 1.5% default
DEFAULT_INFLATION = 0.025  # 2.5% default


def get_risk_free_rate(market_data: Optional[MarketDataInput], country_code: str = "BE") -> float:
    """
    Get risk-free rate from market data or use default.
    
    Args:
        market_data: Market data input from Titan
        country_code: Country code for fallback lookup
        
    Returns:
        Risk-free rate as float (0.03 = 3%)
    """
    if market_data and market_data.economic_indicators:
        return market_data.economic_indicators.risk_free_rate
    
    # European country defaults (10Y government bonds)
    country_defaults = {
        "DE": 0.025,
        "FR": 0.030,
        "NL": 0.027,
        "BE": 0.032,
        "ES": 0.035,
        "IT": 0.040,
    }
    
    return country_defaults.get(country_code, DEFAULT_RISK_FREE_RATE)


def get_gdp_growth(market_data: Optional[MarketDataInput]) -> float:
    """
    Get GDP growth rate from market data or use default.
    
    Args:
        market_data: Market data input from Titan
        
    Returns:
        GDP growth rate as float (0.015 = 1.5%)
    """
    if market_data and market_data.economic_indicators and market_data.economic_indicators.gdp_growth_rate:
        return market_data.economic_indicators.gdp_growth_rate
    
    return DEFAULT_GDP_GROWTH
