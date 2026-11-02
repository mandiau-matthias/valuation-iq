"""
Transparency Data Models

Defines data structures for complete calculation transparency, data provenance,
and audit trails in valuation calculations.

ARCHITECTURE:
- DataSource: Track all external data fetches with timestamps
- CalculationStep: Document each calculation step with formulas
- TransparencyData: Aggregate all transparency information
- ConfidenceBreakdown: 8-factor confidence score breakdown
- RangeMethodology: Document range calculation methodology

USAGE:
These models are used throughout the valuation engine to collect and export
detailed transparency information about calculations, ensuring full auditability.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DataSource(BaseModel):
    """
    Track a single external data source used in valuation

    Attributes:
        name: Human-readable name of the data point
        value: The actual value fetched
        source: Source system/API name
        timestamp: ISO timestamp of when data was fetched
        confidence: Confidence score 0-100
        api_url: Optional API endpoint URL
        cache_status: Cache status (Fresh, Stale, Live, etc.)
    """

    name: str = Field(description="Name of the data source")
    value: Any = Field(description="Value from the data source")
    source: str = Field(description="Source system or API")
    timestamp: str = Field(description="ISO timestamp when fetched")
    confidence: Decimal = Field(ge=0, le=100, description="Confidence score 0-100")
    api_url: Optional[str] = Field(default=None, description="API endpoint URL")
    cache_status: Optional[str] = Field(default=None, description="Cache status")


class CalculationStep(BaseModel):
    """
    Document a single calculation step with formula and values

    Attributes:
        step_number: Sequence number in calculation flow
        description: Human-readable description
        formula: Mathematical formula or algorithm description
        inputs: Dict of input values used
        outputs: Dict of output values produced
        explanation: Academic/business explanation of this step
    """

    step_number: int = Field(description="Step sequence number")
    description: str = Field(description="Step description")
    formula: str = Field(description="Mathematical formula")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Input values")
    outputs: Dict[str, Any] = Field(default_factory=dict, description="Output values")
    explanation: str = Field(description="Explanation of the calculation")


class ComparableCompany(BaseModel):
    """
    Details of a comparable company used in multiples valuation

    Attributes:
        name: Company name
        country: Country code
        revenue: Annual revenue
        ebitda_multiple: EV/EBITDA multiple (if available)
        revenue_multiple: EV/Revenue multiple (if available)
        similarity_score: 0-100 score of how similar to target
        source: Data source (KBO, public markets, etc.)
    """

    name: str = Field(description="Company name")
    country: str = Field(description="Country code")
    revenue: Decimal = Field(description="Annual revenue")
    ebitda_multiple: Optional[Decimal] = Field(default=None, description="EV/EBITDA multiple")
    revenue_multiple: Optional[Decimal] = Field(default=None, description="EV/Revenue multiple")
    similarity_score: Decimal = Field(ge=0, le=100, description="Similarity score 0-100")
    source: str = Field(description="Data source")


class ConfidenceBreakdown(BaseModel):
    """
    8-factor breakdown of overall confidence score

    Each factor is scored 0-100. Factors are weighted to produce overall_score.

    Attributes:
        data_quality: Quality and completeness of input data
        historical_data: Years of historical financial data available
        methodology_agreement: How closely DCF and Multiples agree
        industry_benchmarks: Quality of comparable companies/data
        company_profile: Business stability, profitability, growth
        market_conditions: Current market volatility and environment
        geographic_data: Quality of country-specific data
        business_model_clarity: How well business fits valuation models
        overall_score: Weighted average of all factors
    """

    data_quality: Decimal = Field(ge=0, le=100, description="Input data quality score")
    historical_data: Decimal = Field(ge=0, le=100, description="Historical data availability score")
    methodology_agreement: Decimal = Field(
        ge=0, le=100, description="DCF/Multiples agreement score"
    )
    industry_benchmarks: Decimal = Field(
        ge=0, le=100, description="Industry benchmark quality score"
    )
    company_profile: Decimal = Field(ge=0, le=100, description="Company profile strength score")
    market_conditions: Decimal = Field(
        ge=0, le=100, description="Market conditions stability score"
    )
    geographic_data: Decimal = Field(ge=0, le=100, description="Geographic data quality score")
    business_model_clarity: Decimal = Field(
        ge=0, le=100, description="Business model clarity score"
    )
    overall_score: Decimal = Field(ge=0, le=100, description="Weighted average confidence score")


class RangeMethodology(BaseModel):
    """
    Documentation of how valuation range (low/mid/high) was calculated

    Attributes:
        mid_point: Mid-point valuation (€)
        confidence_level: HIGH, MEDIUM, or LOW
        base_spread: Base spread percentage (e.g., 0.18 for 18%)
        asymmetric_adjustment: Whether asymmetric ranges were applied
        downside_factor: Multiplier for downside (e.g., 1.2 = -22%)
        upside_factor: Multiplier for upside (e.g., 0.8 = +18%)
        low_value: Low-end valuation (€)
        high_value: High-end valuation (€)
        academic_source: Academic paper/source for methodology
        calculation_steps: Detailed calculation steps
    """

    mid_point: Decimal = Field(description="Mid-point valuation")
    confidence_level: str = Field(description="Confidence level (HIGH/MEDIUM/LOW)")
    base_spread: Decimal = Field(description="Base spread percentage")
    asymmetric_adjustment: bool = Field(description="Whether asymmetric ranges were applied")
    downside_factor: Decimal = Field(description="Downside multiplier")
    upside_factor: Decimal = Field(description="Upside multiplier")
    low_value: Decimal = Field(description="Low-end valuation")
    high_value: Decimal = Field(description="High-end valuation")
    academic_source: str = Field(description="Academic source for methodology")
    calculation_steps: List[CalculationStep] = Field(
        default_factory=list, description="Calculation steps"
    )


class TransparencyData(BaseModel):
    """
    Complete transparency package for a valuation

    This aggregates all transparency information including data sources,
    calculation steps, comparable companies, confidence breakdown, and
    range methodology.

    Attributes:
        data_sources: All external data sources used
        calculation_steps: All calculation steps performed
        comparable_companies: Comparable companies (if multiples used)
        confidence_breakdown: 8-factor confidence breakdown
        range_methodology: Range calculation methodology
    """

    data_sources: List[DataSource] = Field(
        default_factory=list, description="External data sources"
    )
    calculation_steps: List[CalculationStep] = Field(
        default_factory=list, description="Calculation steps"
    )
    comparable_companies: Optional[List[ComparableCompany]] = Field(
        default=None, description="Comparable companies"
    )
    confidence_breakdown: ConfidenceBreakdown = Field(description="Confidence score breakdown")
    range_methodology: RangeMethodology = Field(description="Range calculation methodology")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data_sources": [
                    {
                        "name": "Risk-Free Rate",
                        "value": "2.5%",
                        "source": "European Central Bank",
                        "timestamp": "2025-10-27T09:00:00Z",
                        "confidence": 95,
                        "api_url": "https://api.ecb.europa.eu/stats/...",
                        "cache_status": "Fresh (< 24 hours)",
                    }
                ],
                "calculation_steps": [
                    {
                        "step_number": 1,
                        "description": "Cost of Equity (CAPM)",
                        "formula": "Re = Rf + β × (Rm - Rf)",
                        "inputs": {
                            "risk_free_rate": 0.025,
                            "beta": 1.2,
                            "market_risk_premium": 0.08,
                        },
                        "outputs": {"cost_of_equity": 0.121},
                        "explanation": "Using Capital Asset Pricing Model to determine required return on equity",
                    }
                ],
                "confidence_breakdown": {
                    "data_quality": 85,
                    "historical_data": 67,
                    "methodology_agreement": 68,
                    "industry_benchmarks": 90,
                    "company_profile": 78,
                    "market_conditions": 75,
                    "geographic_data": 92,
                    "business_model_clarity": 88,
                    "overall_score": 80,
                },
            }
        }
    )