"""
Registry Types and Data Structures

This module defines all data structures, enums, and configuration classes
for the Registry API refactoring.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal


class RegistryStatus(str, Enum):
    """Registry service status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    ERROR = "error"


class CountryCode(str, Enum):
    """Supported country codes"""
    BELGIUM = "BE"
    UK = "GB"
    NETHERLANDS = "NL"
    GERMANY = "DE"
    FRANCE = "FR"
    LUXEMBOURG = "LU"


class DataCompletenessLevel(str, Enum):
    """Data completeness levels"""
    MINIMAL = "minimal"
    BASIC = "basic"
    MODERATE = "moderate"
    COMPREHENSIVE = "comprehensive"
    COMPLETE = "complete"


class RegistryType(str, Enum):
    """Registry types"""
    BUSINESS = "business"
    FINANCIAL = "financial"
    LEGAL = "legal"
    TAX = "tax"


@dataclass
class RegistryEndpoint:
    """Registry endpoint configuration"""
    endpoint_id: str
    name: str
    url: str
    country_code: CountryCode
    registry_type: RegistryType
    status: RegistryStatus
    rate_limit: int  # requests per minute
    timeout_seconds: int
    retry_attempts: int
    priority: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompanySearchResult:
    """Company search result"""
    company_id: str
    company_name: str
    registration_number: str
    country_code: str
    legal_form: str
    status: str
    founding_year: Optional[int]
    industry_code: Optional[str]
    industry_description: Optional[str]
    employees: Optional[int]
    website: Optional[str]
    address: Optional[str]
    confidence_score: Decimal
    registry_name: str
    registry_url: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FinancialData:
    """Financial data structure"""
    year: int
    revenue: Optional[Decimal]
    ebitda: Optional[Decimal]
    net_income: Optional[Decimal]
    total_assets: Optional[Decimal]
    total_liabilities: Optional[Decimal]
    equity: Optional[Decimal]
    cash: Optional[Decimal]
    debt: Optional[Decimal]
    employees: Optional[int]
    currency: str
    data_quality_score: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompanyDetails:
    """Complete company details"""
    company_id: str
    company_name: str
    registration_number: str
    country_code: str
    legal_form: str
    status: str
    founding_year: Optional[int]
    industry_code: Optional[str]
    industry_description: Optional[str]
    employees: Optional[int]
    website: Optional[str]
    address: Optional[str]
    filing_history: List[FinancialData]
    data_source: str
    source_url: Optional[str]
    last_updated: datetime
    completeness_score: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)


# Pydantic Models for API
class RegistrySearchRequest(BaseModel):
    """Request model for company search"""
    company_name: str = Field(..., description="Company name to search for", min_length=2)
    country_code: Optional[str] = Field(None, description="2-letter country code (BE, UK, etc.)", max_length=2)
    limit: int = Field(10, description="Maximum number of results", ge=1, le=200)


class RegistrySearchResponse(BaseModel):
    """Response model for company search"""
    results: List[Dict[str, Any]] = Field(..., description="List of matching companies")
    total_results: int = Field(..., description="Total number of matches")
    search_time_ms: int = Field(..., description="Search duration in milliseconds")
    registry_name: str = Field(..., description="Source registry name")
    registry_url: Optional[str] = Field(None, description="Link to registry website")


class RegistryFetchRequest(BaseModel):
    """Request model for fetching company financials"""
    company_id: str = Field(..., description="Company identifier from search results")
    country_code: str = Field(..., description="2-letter country code", min_length=2, max_length=2)
    years: Optional[int] = Field(None, description="Number of years of history to fetch", ge=1, le=10)


class RegistryFetchResponse(BaseModel):
    """Response model for company financials"""
    company_id: str = Field(..., description="Company identifier")
    company_name: str = Field(..., description="Company name")
    registration_number: str = Field(..., description="Registration number")
    country_code: str = Field(..., description="Country code")
    legal_form: str = Field(..., description="Legal form")
    filing_history: List[Dict[str, Any]] = Field(..., description="Historical financial data")
    founding_year: Optional[int] = Field(None, description="Year founded")
    industry_code: Optional[str] = Field(None, description="Industry classification")
    industry_description: Optional[str] = Field(None, description="Industry description")
    employees: Optional[int] = Field(None, description="Number of employees")
    website: Optional[str] = Field(None, description="Company website")
    data_source: str = Field(..., description="Source registry name")
    source_url: Optional[str] = Field(None, description="Link to registry entry")
    last_updated: str = Field(..., description="Last data update timestamp")
    completeness_score: Decimal = Field(..., description="Data completeness score (0-1)")


class RegistryHealthResponse(BaseModel):
    """Registry health check response"""
    status: str = Field(..., description="Overall registry status")
    endpoints: List[Dict[str, Any]] = Field(..., description="Individual endpoint statuses")
    total_endpoints: int = Field(..., description="Total number of endpoints")
    active_endpoints: int = Field(..., description="Number of active endpoints")
    last_check: str = Field(..., description="Last health check timestamp")


class RegistryMetrics(BaseModel):
    """Registry performance metrics"""
    total_requests: int = Field(..., description="Total requests processed")
    successful_requests: int = Field(..., description="Successful requests")
    failed_requests: int = Field(..., description="Failed requests")
    average_response_time: Decimal = Field(..., description="Average response time in ms")
    success_rate: Decimal = Field(..., description="Success rate (0-1)")
    last_updated: str = Field(..., description="Last metrics update timestamp")


# Default registry configurations
DEFAULT_REGISTRY_ENDPOINTS = {
    CountryCode.BELGIUM: RegistryEndpoint(
        endpoint_id="kbo_belgium",
        name="Titan KBO Belgium",
        url="/api/v2/registry",
        country_code=CountryCode.BELGIUM,
        registry_type=RegistryType.BUSINESS,
        status=RegistryStatus.ACTIVE,
        rate_limit=100,
        timeout_seconds=30,
        retry_attempts=3,
        priority=1
    ),
    CountryCode.UK: RegistryEndpoint(
        endpoint_id="companies_house_uk",
        name="Companies House UK",
        url="https://api.companieshouse.gov.uk",
        country_code=CountryCode.UK,
        registry_type=RegistryType.BUSINESS,
        status=RegistryStatus.INACTIVE,
        rate_limit=600,
        timeout_seconds=30,
        retry_attempts=3,
        priority=2
    ),
    CountryCode.NETHERLANDS: RegistryEndpoint(
        endpoint_id="kvk_netherlands",
        name="KVK Netherlands",
        url="https://api.kvk.nl",
        country_code=CountryCode.NETHERLANDS,
        registry_type=RegistryType.BUSINESS,
        status=RegistryStatus.INACTIVE,
        rate_limit=1000,
        timeout_seconds=30,
        retry_attempts=3,
        priority=3
    )
}

# Search validation patterns
INVALID_SEARCH_PATTERNS = [
    "search for",
    "try with",
    "try searching",
    "try different",
    "use registration number",
    "look up",
    "find companies",
    "search companies"
]

# Country-specific configurations
COUNTRY_CONFIGURATIONS = {
    CountryCode.BELGIUM: {
        "registry_name": "Titan KBO",
        "website_url": None,
        "search_fields": ["company_name", "registration_number"],
        "financial_data_available": False,
        "max_years_history": 0
    },
    CountryCode.UK: {
        "registry_name": "Companies House",
        "website_url": "https://find-and-update.company-information.service.gov.uk",
        "search_fields": ["company_name", "company_number"],
        "financial_data_available": True,
        "max_years_history": 10
    },
    CountryCode.NETHERLANDS: {
        "registry_name": "KVK",
        "website_url": "https://www.kvk.nl",
        "search_fields": ["company_name", "kvk_number"],
        "financial_data_available": False,
        "max_years_history": 5
    }
}

# Rate limiting configurations
RATE_LIMIT_CONFIG = {
    "default": {
        "requests_per_minute": 60,
        "burst_limit": 10,
        "window_size_seconds": 60
    },
    "premium": {
        "requests_per_minute": 300,
        "burst_limit": 50,
        "window_size_seconds": 60
    }
}

# Cache configurations
CACHE_CONFIG = {
    "search_results": {
        "ttl_seconds": 3600,  # 1 hour
        "max_entries": 1000
    },
    "company_details": {
        "ttl_seconds": 86400,  # 24 hours
        "max_entries": 500
    },
    "financial_data": {
        "ttl_seconds": 604800,  # 7 days
        "max_entries": 200
    }
}
