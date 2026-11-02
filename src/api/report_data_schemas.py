"""Structured report-data schemas for the legacy valuation API contract."""

from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class EBITDAAdjustment(BaseModel):
    """EBITDA normalization adjustment for report display.

    Tracks each adjustment made during EBITDA normalization with full
    audit trail including source system and approval status.
    """

    id: str = Field(..., description="Unique identifier for this adjustment")
    label: str = Field(..., description="Human-readable label for the adjustment")
    value: Decimal = Field(..., description="Adjustment amount (positive or negative)")
    type: str = Field(..., description="Adjustment type: 'add', 'subtract', 'base', or 'result'")
    category: str = Field(
        ...,
        description="Category: 'owner', 'nonRecurring', 'accounting', 'normalization', 'base', 'result'",
    )
    description: Optional[str] = Field(None, description="Detailed explanation of adjustment")
    source: Optional[str] = Field(
        None, description="Data source: 'yuki', 'exact', 'odoo', 'manual', 'suggestion'"
    )
    source_ref: Optional[str] = Field(
        None, description="Source reference (e.g., 'Yuki 613xxx', 'Exact 4000-4999')"
    )
    status: str = Field(
        default="approved", description="Approval status: 'approved', 'pending', 'rejected'"
    )
    approved_by: Optional[str] = Field(None, description="Accountant name who approved")


class YearlyEBITDA(BaseModel):
    """Multi-year EBITDA data for weighted average calculation."""

    year: int = Field(..., description="Fiscal year")
    year_display: Optional[str] = Field(
        None,
        description="Calendar year with filing role label, e.g. '2024 (Base)', '2023 (Base - 1)'",
    )
    reported_ebitda: Decimal = Field(..., description="Reported EBITDA before normalization")
    normalized_ebitda: Decimal = Field(..., description="EBITDA after normalization adjustments")
    weight: Decimal = Field(
        ...,
        ge=Decimal("0.0"),
        le=Decimal("1.0"),
        description="Weight for weighted average (e.g., 0.5 for most recent, 0.3, 0.2 for older)",
    )
    adjustments: Optional[List[EBITDAAdjustment]] = Field(
        None, description="Adjustments applied to this year's EBITDA"
    )


class ValuationMetric(BaseModel):
    """Key metric for report display grid."""

    label: str = Field(..., description="Metric label (e.g., 'Revenue', 'EBITDA Margin')")
    value: str = Field(..., description="Formatted value for display")
    change: Optional[Decimal] = Field(None, description="YoY change percentage")
    category: Optional[str] = Field(
        None, description="Category: 'financial', 'operational', 'growth'"
    )


class AccountantBranding(BaseModel):
    """Accountant/Advisor branding for co-branded reports."""

    firm_name: str = Field(..., description="Accounting firm name")
    logo_url: Optional[str] = Field(None, description="URL to firm logo")
    website: Optional[str] = Field(None, description="Firm website URL")
    email: Optional[str] = Field(None, description="Firm contact email")


class ComparableTransaction(BaseModel):
    """Comparable transaction for report display."""

    company: str = Field(..., description="Company name")
    multiple: Decimal = Field(..., description="Transaction multiple")
    revenue: Optional[Decimal] = Field(None, description="Company revenue")
    date: Optional[str] = Field(None, description="Transaction date")


class ValuationReportData(BaseModel):
    """Structured data for React report template.

    This schema provides all data needed by the frontend React template
    to render the valuation report. Replaces server-side HTML generation
    with structured JSON that the frontend renders using React components.
    """

    id: str = Field(..., description="Valuation ID")
    company_name: str = Field(..., description="Company name")
    generated_at: str = Field(..., description="ISO 8601 timestamp of report generation")

    valuation: Decimal = Field(..., description="Mid-point valuation (equity value)")
    valuation_low: Optional[Decimal] = Field(None, description="Low end of valuation range")
    valuation_high: Optional[Decimal] = Field(None, description="High end of valuation range")

    ebitda: Decimal = Field(..., description="Sustainable EBITDA (weighted average if multi-year)")
    reported_ebitda: Optional[Decimal] = Field(
        None, description="Latest year reported EBITDA (before normalization)"
    )
    latest_normalized_ebitda: Optional[Decimal] = Field(
        None, description="Latest year EBITDA after normalization"
    )
    primary_filing_year: Optional[int] = Field(
        None,
        description="Fiscal year for EBITDA headings in React report (Mercury parity)",
    )
    ebitda_adjustments: List[EBITDAAdjustment] = Field(
        default_factory=list, description="EBITDA normalization adjustments"
    )
    multi_year_ebitda: Optional[List[YearlyEBITDA]] = Field(
        None, description="Multi-year EBITDA data for weighted average calculation"
    )

    multiple: Decimal = Field(..., description="Applied EV/EBITDA multiple")
    multiple_low: Optional[Decimal] = Field(None, description="Low end of multiple range")
    multiple_high: Optional[Decimal] = Field(None, description="High end of multiple range")

    industry: Optional[str] = Field(None, description="Industry classification")
    industry_emoji: Optional[str] = Field(None, description="Industry emoji for display")
    revenue: Optional[Decimal] = Field(None, description="Annual revenue")
    employee_count: Optional[int] = Field(None, description="Number of employees")
    founded_year: Optional[int] = Field(None, description="Year company was founded")
    country_code: Optional[str] = Field(None, description="ISO country code")

    metrics: List[ValuationMetric] = Field(
        default_factory=list, description="Key metrics for display grid"
    )

    methodology: Optional[str] = Field(
        None, description="Valuation methodology used (e.g., 'EBITDA Multiple', 'DCF')"
    )
    methodology_notes: Optional[str] = Field(None, description="Detailed methodology explanation")

    comparables: Optional[List[ComparableTransaction]] = Field(
        None, description="Comparable transactions used in valuation"
    )

    accountant: Optional[AccountantBranding] = Field(
        None, description="Accountant branding for co-branded reports"
    )

    confidence_level: Optional[str] = Field(
        None, description="Confidence level: 'low', 'medium', 'high'"
    )
    confidence_score: Optional[int] = Field(
        None, ge=0, le=100, description="Confidence score (0-100)"
    )
    risk_factors: Optional[List[str]] = Field(None, description="Key risk factors identified")
    value_drivers: Optional[List[str]] = Field(None, description="Key value drivers identified")
    dcf_historical_fcf_readiness: Optional[Dict[str, object]] = Field(
        None,
        description="Actual-vs-fallback readiness metadata for historical DCF free cash flow inputs.",
    )

    show_fiscal_reference: Optional[bool] = Field(
        None, description="Whether to include fiscal reference page in report"
    )
    fiscal_ebitda_multiple: Optional[Decimal] = Field(
        None, description="Fiscal EBITDA multiple (always 4.0 per Belgian law)"
    )
    fiscal_ebitda_component: Optional[Decimal] = Field(None, description="4 x normalized EBITDA")
    fiscal_book_equity: Optional[Decimal] = Field(
        None, description="Book equity (eigen vermogen) from annual accounts"
    )
    fiscal_book_equity_negative: Optional[bool] = Field(
        None, description="Whether book equity is negative (triggers informational warning)"
    )
    fiscal_reference_value: Optional[Decimal] = Field(
        None, description="Forfaitaire waarde: eigen vermogen + 4 x EBITDA"
    )
