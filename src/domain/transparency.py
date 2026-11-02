"""
Transparency Models for Valuation Engine.

These models track data provenance, market data sources, calculation steps,
and validation checks to provide radical transparency to users.

Every number in a valuation should be traceable to its source.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DataSource(str, Enum):
    """Source of data for transparency tracking."""

    # Official registries
    KBO_REGISTRY = "kbo_registry"  # Belgian company registry
    COMPANIES_HOUSE = "companies_house"  # UK company registry
    HANDELSREGISTER = "handelsregister"  # German company registry

    # Market data providers
    OECD_DATABASE = "oecd_database"  # OECD industry data
    ECB_DATA = "ecb_data"  # European Central Bank
    FMP_API = "fmp_api"  # Financial Modeling Prep API
    WORLD_BANK = "world_bank"  # World Bank data

    # User input
    USER_INPUT = "user_input"  # Manually entered by user
    USER_UPLOAD = "user_upload"  # Uploaded document

    # System calculated
    CALCULATED = "calculated"  # Derived from other data
    ESTIMATED = "estimated"  # Estimated by system

    # Historical
    HISTORICAL = "historical"  # From previous valuation
    BENCHMARK = "benchmark"  # Industry benchmark


class DataQuality(str, Enum):
    """Quality/confidence in data source."""

    VERIFIED = "verified"  # Official source, high confidence
    VALIDATED = "validated"  # Cross-checked, good confidence
    ESTIMATED = "estimated"  # System estimate, medium confidence
    ASSUMED = "assumed"  # Assumption, lower confidence

    @classmethod
    def _missing_(cls, value):
        """Handle case-insensitive enum lookup."""
        if isinstance(value, str):
            value_lower = value.lower()
            for member in cls:
                if member.value == value_lower:
                    return member
        return None


class DataProvenance(BaseModel):
    """
    Track where a data point came from.

    This is the foundation of transparency - every number should have a source.
    """

    field_name: str = Field(..., description="Field name (e.g., 'revenue_2023')")
    value: Decimal = Field(..., description="The actual value")

    # Source information
    source: DataSource = Field(..., description="Where data came from")
    source_date: date = Field(..., description="When data was sourced")
    source_url: Optional[str] = Field(None, description="URL to original source")
    source_reference: Optional[str] = Field(
        None, description="Reference ID (e.g., 'KBO line 70', 'OECD table 3.2')"
    )

    # Quality assessment
    quality: DataQuality = Field(..., description="Quality/confidence in data")
    confidence: int = Field(..., ge=0, le=100, description="Confidence score 0-100")

    # Metadata
    notes: Optional[str] = Field(None, description="Additional context")
    last_updated: datetime = Field(default_factory=datetime.now)


class MarketDataDetails(BaseModel):
    """
    Transparent market data used in valuation.

    Shows users exactly what market multiples, rates, and benchmarks were used.
    """

    # Industry multiples
    industry_multiples: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Industry multiples used",
        examples=[
            {
                "ev_ebitda_median": 9.0,
                "ev_ebitda_p25": 7.5,
                "ev_ebitda_p75": 11.2,
                "ev_revenue_median": 1.5,
                "ev_revenue_p25": 1.2,
                "ev_revenue_p75": 2.0,
            }
        ],
    )

    # Data sources
    multiples_source: str = Field(..., description="Source of multiples (e.g., 'OECD')")
    multiples_date: date = Field(..., description="Date of multiples data")
    multiples_sample_size: int = Field(..., description="Number of comparable companies")

    # Market conditions
    risk_free_rate: Decimal = Field(..., description="Risk-free rate used")
    risk_free_rate_source: str = Field(..., description="Source (e.g., 'ECB 10Y Bond')")
    risk_free_rate_date: date = Field(..., description="Date of rate")

    market_risk_premium: Decimal = Field(..., description="Market risk premium used")
    market_risk_premium_source: str = Field(..., description="Source (e.g., 'Historical EU')")

    gdp_growth_rate: Optional[Decimal] = Field(None, description="GDP growth rate")
    gdp_growth_source: Optional[str] = Field(None, description="Source (e.g., 'IMF forecast')")

    # Comparable companies (top 5 for display)
    comparable_companies: List[Dict[str, Any]] = Field(
        default_factory=list,
        max_length=10,
        description="Comparable companies used",
        examples=[
            [
                {
                    "name": "Belgian Software Co",  # Can be anonymized
                    "country": "Belgium",
                    "industry": "Software/SaaS",
                    "revenue": 3200000,
                    "ebitda": 580000,
                    "ev_ebitda_multiple": 9.2,
                    "ev_revenue_multiple": 1.6,
                    "similarity_score": 87,  # 0-100
                }
            ]
        ],
    )


class IndustryBenchmark(BaseModel):
    """
    Industry benchmark for a specific metric.

    Shows how company compares to industry peers.
    """

    metric_name: str = Field(..., description="Metric name (e.g., 'EBITDA Margin')")
    metric_value: Decimal = Field(..., description="Company's value")

    # Industry distribution
    industry_p25: Decimal = Field(..., description="Industry 25th percentile")
    industry_median: Decimal = Field(..., description="Industry median (50th percentile)")
    industry_p75: Decimal = Field(..., description="Industry 75th percentile")
    industry_p90: Decimal = Field(..., description="Industry 90th percentile")

    # Company's position
    company_percentile: int = Field(..., ge=0, le=100, description="Company's percentile rank")
    assessment: str = Field(
        ..., description="Assessment (excellent, good, average, below_average, poor)"
    )
    explanation: str = Field(..., description="Human-readable explanation")

    # Source
    data_source: str = Field(..., description="Source of benchmark data")
    data_date: date = Field(..., description="Date of benchmark data")
    sample_size: int = Field(..., description="Number of companies in benchmark")


class CalculationStep(BaseModel):
    """
    Individual calculation step for audit trail.

    Shows step-by-step how valuations were calculated.
    Enhanced to preserve full StepOutput data from triage system.
    """

    step_number: int = Field(..., ge=0, le=11, description="Step number in sequence (0-11, all 12 steps)")
    calculation_name: str = Field(..., description="Name of calculation (e.g., 'WACC')")
    formula: str = Field(..., description="Formula used (human-readable)")

    # Inputs
    inputs: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Input values with names",
        examples=[
            {
                "risk_free_rate": 0.032,
                "beta": 1.2,
                "market_risk_premium": 0.070,
            }
        ],
    )

    # Output
    output: Decimal = Field(..., description="Result of calculation (primary output value)")
    output_formatted: str = Field(..., description="Result formatted (e.g., '12.5%')")

    # Explanation
    explanation: str = Field(..., description="Plain English explanation")
    formula_latex: Optional[str] = Field(None, description="LaTeX formula for display")

    # Metadata
    calculation_type: str = Field(..., description="Type (e.g., 'wacc', 'dcf', 'terminal_value')")

    # NEW: Step status and execution tracking (from StepOutput)
    status: str = Field(
        default="completed",
        description="Step execution status: 'completed', 'skipped', 'failed', 'pending', 'executing'",
    )
    skip_reason: Optional[str] = Field(
        None, description="Reason why step was skipped (if status='skipped')"
    )
    error: Optional[str] = Field(
        None, description="Error message if step failed (if status='failed')"
    )
    execution_time_ms: Optional[Decimal] = Field(
        None, description="Time taken to execute step in milliseconds"
    )

    # NEW: Full metadata and outputs preservation
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Complete metadata from StepOutput (formulas, rationales, decision logic)",
    )
    rationale: Optional[str] = Field(
        None, description="Step-specific rationale/explanation (extracted from metadata)"
    )
    outputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Complete outputs dict from StepOutput.result (preserves all calculation results)",
    )
    
    # WORLD-CLASS: Academic sources for this calculation step
    academic_source_ids: List[str] = Field(
        default_factory=list,
        description="Academic source IDs used in this calculation (from provenance tracker)"
    )
    academic_sources: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Full academic source details for display in templates (author, year, title, pages, relevance)"
    )


class ValidationCheck(BaseModel):
    """
    Result of a validation check.

    Shows what data quality checks were performed.
    """

    check_name: str = Field(..., description="Name of check")
    check_type: str = Field(
        ..., description="Type (data_quality, consistency, realism, completeness)"
    )

    # Result
    status: str = Field(..., description="Status (passed, warning, failed)")
    severity: str = Field(..., description="Severity (info, warning, error)")

    message: str = Field(..., description="Human-readable message")
    recommendation: Optional[str] = Field(None, description="Recommended action")

    # Details
    expected_value: Optional[Decimal] = Field(None, description="Expected/typical value")
    actual_value: Optional[Decimal] = Field(None, description="Actual value found")
    threshold: Optional[Decimal] = Field(None, description="Threshold for check")

    # Impact
    impact_on_confidence: int = Field(
        0, ge=-20, le=20, description="Impact on confidence score (-20 to +20)"
    )


class ValidationReport(BaseModel):
    """
    Complete validation report.

    Summary of all data quality checks performed.
    """

    total_checks: int = Field(..., description="Total number of checks")
    passed: int = Field(..., description="Number passed")
    warnings: int = Field(..., description="Number with warnings")
    failed: int = Field(..., description="Number failed")

    checks: List[ValidationCheck] = Field(..., description="Individual check results")

    overall_status: str = Field(
        ..., description="Overall status (passed, passed_with_warnings, failed)"
    )

    validation_score: int = Field(..., ge=0, le=100, description="Overall validation score 0-100")

    summary: str = Field(..., description="Human-readable summary")


class TransparencyData(BaseModel):
    """
    Complete transparency data for a valuation.

    This is the master object that contains all transparency information.
    """

    # Data provenance (where every number came from)
    data_provenance: Dict[str, DataProvenance] = Field(
        default_factory=dict, description="Provenance for each data field"
    )

    # Market data transparency
    market_data: MarketDataDetails = Field(..., description="Market data and sources used")

    # Industry benchmarks
    industry_benchmarks: Dict[str, IndustryBenchmark] = Field(
        default_factory=dict, description="Industry benchmarks for key metrics"
    )

    # Calculation trail
    calculation_steps: Dict[str, List[CalculationStep]] = Field(
        default_factory=dict, description="Calculation steps by type (wacc, dcf, multiples, etc.)"
    )

    # Validation report
    validation_report: ValidationReport = Field(..., description="Data quality validation results")

    # Metadata
    transparency_version: str = Field("1.0", description="Version of transparency schema")
    generated_at: datetime = Field(
        default_factory=datetime.now, description="When transparency data was generated"
    )


# === HELPER FUNCTIONS ===


def create_data_provenance(
    field_name: str,
    value: Decimal,
    source: DataSource,
    source_date: date,
    quality: DataQuality,
    confidence: int,
    source_url: Optional[str] = None,
    source_reference: Optional[str] = None,
    notes: Optional[str] = None,
) -> DataProvenance:
    """Helper function to create DataProvenance object."""
    return DataProvenance(
        field_name=field_name,
        value=value,
        source=source,
        source_date=source_date,
        source_url=source_url,
        source_reference=source_reference,
        quality=quality,
        confidence=confidence,
        notes=notes,
    )


def create_validation_check(
    check_name: str,
    check_type: str,
    status: str,
    severity: str,
    message: str,
    impact_on_confidence: int = 0,
    **kwargs,
) -> ValidationCheck:
    """Helper function to create ValidationCheck object."""
    return ValidationCheck(
        check_name=check_name,
        check_type=check_type,
        status=status,
        severity=severity,
        message=message,
        impact_on_confidence=impact_on_confidence,
        **kwargs,
    )


def create_calculation_step(
    step_number: int,
    calculation_name: str,
    formula: str,
    inputs: Dict[str, Decimal],
    output: Decimal,
    explanation: str,
    calculation_type: str,
    output_formatted: Optional[str] = None,
) -> CalculationStep:
    """Helper function to create CalculationStep object."""
    if output_formatted is None:
        # Auto-format based on value
        if abs(output) < 1:
            output_formatted = f"{output * 100:.2f}%"
        else:
            output_formatted = f"\u20AC{output:,.0f}"

    return CalculationStep(
        step_number=step_number,
        calculation_name=calculation_name,
        formula=formula,
        inputs=inputs,
        output=output,
        output_formatted=output_formatted,
        explanation=explanation,
        calculation_type=calculation_type,
    )


def create_industry_benchmark(
    metric_name: str,
    metric_value: Decimal,
    industry_data: Dict[str, Decimal],
    data_source: str,
    data_date: date,
    sample_size: int,
    is_higher_better: bool = True,
) -> IndustryBenchmark:
    """
    Helper function to create IndustryBenchmark object.

    Automatically calculates percentile and assessment.
    """
    # Extract industry distribution values (needed for assessment calculation and percentile calculation)
    p25 = industry_data["p25"]
    median = industry_data["median"]
    p75 = industry_data["p75"]
    p90 = industry_data["p90"]
    
    # Check if percentile is provided in industry_data (from record_industry_benchmark)
    # Use provided percentile if available, otherwise calculate it
    if "percentile" in industry_data and industry_data["percentile"] is not None:
        try:
            percentile = int(industry_data["percentile"])
        except (ValueError, TypeError):
            percentile = None
    
    if percentile is None:
        # Calculate percentile
        # Estimate percentile (linear interpolation)
        # Handle negative values specially - they should be in bottom percentile
        if metric_value < Decimal("0"):
            # Negative values are always in bottom percentile (0-10%)
            # Use a simple formula that always produces positive values
            if p25 > Decimal("0"):
                # Scale negative value relative to p25, but ensure positive result
                # Use Decimal arithmetic, convert to float only for min() comparison
                ratio_decimal = abs(metric_value / p25)
                ratio_capped = min(ratio_decimal, Decimal("1"))
                percentile_decimal = Decimal("10") * (Decimal("1") - ratio_capped)
                percentile = max(0, min(10, int(percentile_decimal)))
            else:
                percentile = 5
        elif metric_value <= p25:
            percentile_decimal = Decimal("25") * (metric_value / p25) if p25 > Decimal("0") else Decimal("25")
            percentile = int(percentile_decimal)
        elif metric_value <= median:
            percentile_decimal = Decimal("25") + Decimal("25") * ((metric_value - p25) / (median - p25)) if (median - p25) > Decimal("0") else Decimal("50")
            percentile = int(percentile_decimal)
        elif metric_value <= p75:
            percentile_decimal = Decimal("50") + Decimal("25") * ((metric_value - median) / (p75 - median)) if (p75 - median) > Decimal("0") else Decimal("75")
            percentile = int(percentile_decimal)
        elif metric_value <= p90:
            percentile_decimal = Decimal("75") + Decimal("15") * ((metric_value - p75) / (p90 - p75)) if (p90 - p75) > Decimal("0") else Decimal("90")
            percentile = int(percentile_decimal)
        else:
            percentile_decimal = Decimal("90") + Decimal("10") * ((metric_value - p90) / (p90 * Decimal('0.2'))) if p90 > Decimal("0") else Decimal("99")
            percentile = min(99, int(percentile_decimal))
    
    # Ensure percentile is within valid range [0, 100]
    percentile = max(0, min(100, percentile))

    # Assessment
    if is_higher_better:
        if percentile >= 75:
            assessment = "excellent"
            explanation = f"Your {metric_name} is in the top 25% of companies"
        elif percentile >= 60:
            assessment = "good"
            explanation = f"Your {metric_name} is above industry average"
        elif percentile >= 40:
            assessment = "average"
            explanation = f"Your {metric_name} is around industry average"
        elif percentile >= 25:
            assessment = "below_average"
            explanation = f"Your {metric_name} is below industry average"
        else:
            assessment = "poor"
            explanation = f"Your {metric_name} is in the bottom 25% of companies"
    else:
        # For metrics where lower is better (e.g., debt ratio)
        if percentile <= 25:
            assessment = "excellent"
            explanation = f"Your {metric_name} is in the bottom 25% (very good)"
        elif percentile <= 40:
            assessment = "good"
            explanation = f"Your {metric_name} is below industry average (good)"
        elif percentile <= 60:
            assessment = "average"
            explanation = f"Your {metric_name} is around industry average"
        elif percentile <= 75:
            assessment = "below_average"
            explanation = f"Your {metric_name} is above industry average (caution)"
        else:
            assessment = "poor"
            explanation = f"Your {metric_name} is in the top 25% (concerning)"

    return IndustryBenchmark(
        metric_name=metric_name,
        metric_value=metric_value,
        industry_p25=p25,
        industry_median=median,
        industry_p75=p75,
        industry_p90=p90,
        company_percentile=percentile,
        assessment=assessment,
        explanation=explanation,
        data_source=data_source,
        data_date=data_date,
        sample_size=sample_size,
    )
