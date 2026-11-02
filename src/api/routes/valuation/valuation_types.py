"""
Valuation API Types

This module defines shared data structures and enums for the valuation API.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from src.utils.decimal_helpers import from_decimal, to_decimal


class ValuationMethod(str, Enum):
    """Valuation methodology types"""

    DCF = "dcf"
    MULTIPLES = "multiples"
    ASSET_BASED = "asset_based"
    MARKET = "market"
    INCOME = "income"
    COST = "cost"
    HYBRID = "hybrid"


class BusinessType(str, Enum):
    """Business type categories"""

    STARTUP = "startup"
    SME = "sme"
    ENTERPRISE = "enterprise"
    FRANCHISE = "franchise"
    E_COMMERCE = "e_commerce"
    SERVICES = "services"
    MANUFACTURING = "manufacturing"
    RETAIL = "retail"
    REAL_ESTATE = "real_estate"
    CONSULTING = "consulting"


class IndustryCategory(str, Enum):
    """Industry categories"""

    TECHNOLOGY = "technology"
    MANUFACTURING = "manufacturing"
    RETAIL = "retail"
    SERVICES = "services"
    HEALTHCARE = "healthcare"
    CONSTRUCTION = "construction"
    HOSPITALITY = "hospitality"
    FINANCE = "finance"
    REAL_ESTATE = "real_estate"
    TRANSPORTATION = "transportation"
    EDUCATION = "education"
    ENTERTAINMENT = "entertainment"
    AGRICULTURE = "agriculture"
    MINING = "mining"
    UTILITIES = "utilities"
    OTHER = "other"


class ValuationStatus(str, Enum):
    """Valuation status types"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ValuationQuality(str, Enum):
    """Valuation quality levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PROFESSIONAL = "professional"


@dataclass
class FinancialData:
    """Financial data structure"""

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


@dataclass
class MarketData:
    """Market data structure"""

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


@dataclass
class ValuationInputs:
    """Valuation input parameters"""

    business_name: str
    business_type: BusinessType
    industry: IndustryCategory
    financial_data: FinancialData
    market_data: MarketData
    assumptions: Dict[str, Any]
    methodology: ValuationMethod
    owner_profile: Optional[Dict[str, Any]] = None
    business_context: Optional[Dict[str, Any]] = None


@dataclass
class ValuationResult:
    """Valuation calculation result"""

    valuation_id: str
    business_name: str
    methodology: ValuationMethod
    enterprise_value: Decimal
    equity_value: Decimal
    per_share_value: Optional[Decimal]
    confidence_score: Decimal
    quality_rating: ValuationQuality
    assumptions: Dict[str, Any]
    sensitivity_analysis: Dict[str, Any]
    created_at: datetime
    status: ValuationStatus


@dataclass
class DCFResult:
    """DCF valuation result"""

    present_value: Decimal
    terminal_value: Decimal
    enterprise_value: Decimal
    equity_value: Decimal
    wacc: Decimal
    terminal_growth_rate: Decimal
    cash_flow_projections: List[Dict[str, Decimal]]
    sensitivity_analysis: Dict[str, Any]


@dataclass
class MultiplesResult:
    """Multiples valuation result"""

    pe_multiple: Decimal
    ev_ebitda_multiple: Decimal
    price_to_sales_multiple: Decimal
    price_to_book_multiple: Decimal
    industry_averages: Dict[str, Decimal]
    comparable_companies: List[Dict[str, Any]]
    valuation_range: Dict[str, Decimal]


@dataclass
class AssetBasedResult:
    """Asset-based valuation result"""

    book_value: Decimal
    adjusted_book_value: Decimal
    liquidation_value: Decimal
    replacement_cost: Decimal
    intangible_assets: Decimal
    goodwill: Decimal
    asset_breakdown: Dict[str, Decimal]


@dataclass
class ValuationReport:
    """Comprehensive valuation report"""

    executive_summary: str
    methodology_explanation: str
    key_assumptions: List[str]
    risk_factors: List[str]
    recommendations: List[str]
    appendices: Dict[str, Any]
    charts_and_graphs: List[Dict[str, Any]]
    disclaimer: str


# Pydantic models for API requests and responses
class QuickValuationRequest(BaseModel):
    """Quick valuation request model"""

    revenue: Decimal
    ebitda: Decimal
    industry: str  # Changed from IndustryCategory to str to match frontend
    country_code: str  # Added to match frontend
    registration_number: Optional[str] = None
    kbo_number: Optional[str] = None
    kvk_number: Optional[str] = None
    vat_number: Optional[str] = None
    legal_form: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    business_name: Optional[str] = "Quick Valuation"  # Made optional with default
    business_type: Optional[BusinessType] = BusinessType.SME  # Made optional with default
    business_type_id: Optional[str] = None  # Titan catalog id; drives DB multiples in quick path
    benchmark_contract: Optional[Dict[str, Any]] = None
    multiples_metadata: Optional[Dict[str, Any]] = None
    allow_untrusted_multiples_fallback: bool = False
    employee_count: Optional[int] = None
    owner_role: Optional[str] = None
    owner_hours: Optional[int] = None


class ValuationRequest(BaseModel):
    """Comprehensive valuation request model"""

    business_name: str
    business_type: BusinessType
    industry: IndustryCategory
    financial_data: FinancialData
    market_data: MarketData
    methodology: ValuationMethod
    assumptions: Dict[str, Any] = Field(default_factory=dict)
    owner_profile: Optional[Dict[str, Any]] = None
    business_context: Optional[Dict[str, Any]] = None


class QuickValuationResponse(BaseModel):
    """Quick valuation response model"""

    valuation_id: str
    business_name: str
    estimated_value: Decimal
    value_range: Dict[str, Decimal]
    methodology: str
    confidence_score: Decimal
    key_factors: List[str]
    recommendations: List[str]
    created_at: datetime


class ValuationResponse(BaseModel):
    """Comprehensive valuation response model"""

    valuation_id: str
    business_name: str
    methodology: ValuationMethod
    enterprise_value: Decimal
    equity_value: Decimal
    per_share_value: Optional[Decimal]
    confidence_score: Decimal
    quality_rating: ValuationQuality
    detailed_results: Dict[str, Any]
    sensitivity_analysis: Dict[str, Any]
    report_url: Optional[str] = None
    created_at: datetime
    status: ValuationStatus


class DCFValuationResponse(BaseModel):
    """DCF valuation response model"""

    valuation_id: str
    present_value: Decimal
    terminal_value: Decimal
    enterprise_value: Decimal
    equity_value: Decimal
    wacc: Decimal
    terminal_growth_rate: Decimal
    cash_flow_projections: List[Dict[str, Decimal]]
    sensitivity_analysis: Dict[str, Any]
    created_at: datetime


class MultiplesValuationResponse(BaseModel):
    """Multiples valuation response model"""

    valuation_id: str
    pe_multiple: Decimal
    ev_ebitda_multiple: Decimal
    price_to_sales_multiple: Decimal
    price_to_book_multiple: Decimal
    industry_averages: Dict[str, Decimal]
    comparable_companies: List[Dict[str, Any]]
    valuation_range: Dict[str, Decimal]
    created_at: datetime


class AssetBasedValuationResponse(BaseModel):
    """Asset-based valuation response model"""

    valuation_id: str
    book_value: Decimal
    adjusted_book_value: Decimal
    liquidation_value: Decimal
    replacement_cost: Decimal
    intangible_assets: Decimal
    goodwill: Decimal
    asset_breakdown: Dict[str, Decimal]
    created_at: datetime


class FinancialMetricsResponse(BaseModel):
    """Financial metrics response model"""

    valuation_id: str
    profitability_metrics: Dict[str, Decimal]
    liquidity_metrics: Dict[str, Decimal]
    efficiency_metrics: Dict[str, Decimal]
    leverage_metrics: Dict[str, Decimal]
    growth_metrics: Dict[str, Decimal]
    industry_benchmarks: Dict[str, Decimal]
    created_at: datetime


class MCPInsightsResponse(BaseModel):
    """MCP insights response model"""

    valuation_id: str
    market_insights: List[str]
    industry_trends: List[str]
    competitive_analysis: List[str]
    risk_factors: List[str]
    opportunities: List[str]
    recommendations: List[str]
    created_at: datetime


class ErrorResponse(BaseModel):
    """Error response model"""

    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ValidationError(BaseModel):
    """Validation error model"""

    field: str
    message: str
    value: Any


class ValidationResponse(BaseModel):
    """Validation response model"""

    is_valid: bool
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# Export all types for backward compatibility
__all__ = [
    "ValuationMethod",
    "BusinessType",
    "IndustryCategory",
    "ValuationStatus",
    "ValuationQuality",
    "FinancialData",
    "MarketData",
    "ValuationInputs",
    "ValuationResult",
    "DCFResult",
    "MultiplesResult",
    "AssetBasedResult",
    "ValuationReport",
    "QuickValuationRequest",
    "ValuationRequest",
    "QuickValuationResponse",
    "ValuationResponse",
    "DCFValuationResponse",
    "MultiplesValuationResponse",
    "AssetBasedValuationResponse",
    "FinancialMetricsResponse",
    "MCPInsightsResponse",
    "ErrorResponse",
    "ValidationError",
    "ValidationResponse",
]
