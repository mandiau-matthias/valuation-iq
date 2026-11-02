"""
Reusable response component schemas for the legacy valuation API contract.

`legacy_schemas.py` still re-exports these names so existing imports keep
working, but the standalone module makes the response surface easier to own.
"""

from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

from src.domain.models import ConfidenceLevel


class FinancialMetricsResponse(BaseModel):
    """
    Financial metrics and ratios.

    DATA FORMAT CONVENTIONS:
    - Growth metrics (revenue_growth, revenue_cagr_3y, ebitda_growth): DECIMAL format
      * Example: Decimal('0.20') = 20%, Decimal('0.0037') = 0.37%, -Decimal('0.15') = -15%
      * Frontend should multiply by 100 to display as percentage
    - Margin metrics (ebitda_margin, etc.): PERCENTAGE format (already multiplied by 100)
      * Example: Decimal('17.1') = 17.1%, Decimal('25.5') = 25.5%
    - Multiples: RATIO format (not percentage)
      * Example: 4.2x, 1.0x
    """

    # Profitability
    gross_margin: Optional[Decimal] = None
    ebitda_margin: Decimal = Field(
        ...,
        description="EBITDA margin as percentage (Decimal('17.1') = 17.1%, not Decimal('0.171'))",
    )
    ebit_margin: Optional[Decimal] = None
    net_margin: Optional[Decimal] = None
    return_on_assets: Optional[Decimal] = None
    return_on_equity: Optional[Decimal] = None

    # Liquidity
    current_ratio: Optional[Decimal] = None
    quick_ratio: Optional[Decimal] = None
    cash_ratio: Optional[Decimal] = None

    # Leverage
    debt_to_equity: Optional[Decimal] = None
    debt_to_assets: Optional[Decimal] = None
    interest_coverage: Optional[Decimal] = None

    # Growth
    # All growth metrics use DECIMAL format (0.20 = 20%, 0.0037 = 0.37%)
    # Frontend should multiply by 100 to display as percentage
    revenue_growth: Optional[Decimal] = Field(
        None,
        description="Year-over-year revenue growth in decimal format (Decimal('0.20') = 20%, -Decimal('0.15') = -15%). "
        "Null when comparable revenue observations are unavailable. "
        "Frontend should multiply by 100 for display.",
    )
    revenue_cagr_3y: Optional[Decimal] = Field(
        None,
        description="Compound Annual Growth Rate in decimal format (Decimal('0.0037') = 0.37%, Decimal('0.111') = 11.1%). "
        "Calculated over exactly three elapsed fiscal years; null when the required revenue history is unavailable. "
        "Frontend should multiply by 100 for display.",
    )
    ebitda_growth: Optional[Decimal] = Field(
        None,
        description="Year-over-year EBITDA growth in decimal format (Decimal('0.15') = 15%, -Decimal('0.10') = -10%). "
        "Frontend should multiply by 100 for display.",
    )

    # Risk
    altman_z_score: Optional[Decimal] = None
    financial_health_score: int = Field(..., ge=0, le=100)
    financial_health_description: str

    # Error tracking (optional - only present if calculation errors occurred)
    calculation_errors: Optional[list[str]] = Field(
        None,
        description="List of error messages if any calculations failed. "
        "Presence of this field indicates partial results.",
    )


class DCFValuationResponse(BaseModel):
    """DCF valuation results."""

    enterprise_value: Decimal
    enterprise_value_low: Optional[Decimal] = Field(
        None, description="Low end of the DCF enterprise value range"
    )
    enterprise_value_mid: Optional[Decimal] = Field(
        None, description="Mid-point DCF enterprise value; mirrors enterprise_value"
    )
    enterprise_value_high: Optional[Decimal] = Field(
        None, description="High end of the DCF enterprise value range"
    )
    equity_value: Decimal
    equity_value_low: Optional[Decimal] = Field(
        None, description="Low end of the DCF equity value range"
    )
    equity_value_mid: Optional[Decimal] = Field(
        None, description="Mid-point DCF equity value; mirrors equity_value"
    )
    equity_value_high: Optional[Decimal] = Field(
        None, description="High end of the DCF equity value range"
    )
    wacc: Decimal
    cost_of_equity: Decimal
    cost_of_debt: Decimal
    terminal_growth_rate: Decimal
    terminal_value: Decimal
    terminal_value_methodology: Optional[str] = None
    terminal_exit_multiple: Optional[Decimal] = None
    pv_terminal_value: Decimal
    mid_year_discounting: Optional[bool] = Field(
        True,
        description="True when explicit FCFs are discounted at mid-year points (0.5, 1.5, …).",
    )
    discount_periods_note: Optional[str] = Field(
        None,
        description="Human-readable note on discount timing (e.g. mid-year convention).",
    )
    academic_cost_of_equity_formula: Optional[str] = Field(
        None,
        description="CAPM-style cost of equity string: Rf + Beta x ERP + Size Premium (excludes CSR).",
    )
    wacc_buildup: Optional[dict[str, object]] = Field(
        None,
        description="Explicit WACC buildup inputs and formula components.",
    )
    terminal_value_pct_of_total: Optional[Decimal] = Field(
        None,
        description="Percentage of total DCF enterprise value attributable to terminal value.",
    )
    explicit_forecast_pct_of_total: Optional[Decimal] = Field(
        None,
        description="Percentage of total DCF enterprise value attributable to the explicit forecast period.",
    )
    implied_ev_ebitda: Optional[Decimal] = Field(
        None,
        description=(
            "Implied EV/EBITDA multiple of the intrinsic DCF enterprise value — a "
            "sanity cross-check of the income approach against market comparables."
        ),
    )
    terminal_value_steady_state: Optional[dict[str, object]] = Field(
        None,
        description=(
            "Terminal-value steady-state check: whether the final explicit year holds "
            "CapEx approximately equal to D&A, the maintainable-reinvestment assumption "
            "the Gordon perpetuity rests on."
        ),
    )
    dcf_enterprise_value_before_apv: Optional[Decimal] = Field(
        None,
        description="Operating DCF enterprise value before separately valued APV tax shields.",
    )
    dcf_equity_value_before_apv: Optional[Decimal] = Field(
        None,
        description="Operating DCF equity value before separately valued APV tax shields.",
    )
    apv_contract_version: Optional[Literal["apv_tax_shield.v2"]] = None
    apv_tax_shield_projections: Optional[list[Decimal]] = None
    apv_tax_shield_pv: Optional[list[Decimal]] = None
    apv_methodology: Optional[str] = Field(
        None,
        description="APV bridge methodology when explicit tax-shield cash flows are supplied.",
    )
    apv_discount_rate: Optional[Decimal] = Field(
        None,
        description="Discount rate used for explicit APV debt tax-shield cash flows.",
    )
    apv_discounting_convention: Optional[str] = Field(
        None,
        description="Timing convention used for APV tax-shield discounting.",
    )
    apv_tax_shield_value: Optional[Decimal] = Field(
        None,
        description="Present value of explicit APV debt tax shields.",
    )
    apv_tax_shield_pct_of_total: Optional[Decimal] = Field(
        None,
        description="APV tax shield as a percentage of APV enterprise value.",
    )
    apv_enterprise_value: Optional[Decimal] = Field(
        None,
        description="Enterprise value after adding APV tax shields.",
    )
    apv_equity_value: Optional[Decimal] = Field(
        None,
        description="Equity value after adding APV tax shields.",
    )
    apv_tax_shield_projections_5y: Optional[list[Decimal]] = Field(
        None,
        max_length=5,
        description="Nominal annual APV tax-shield cash flows for the first five forecast years.",
    )
    apv_tax_shield_pv_5y: Optional[list[Decimal]] = Field(
        None,
        max_length=5,
        description="Present value of annual APV tax-shield cash flows for the first five forecast years.",
    )
    apv_bridge_provenance: Optional[dict[str, object]] = Field(
        None,
        description=(
            "Structured provenance for the APV tax-shield bridge, including whether the "
            "run uses the year-end customer-template reconciliation convention."
        ),
    )
    apv_benchmark_reconciliation: Optional[dict[str, object]] = Field(
        None,
        description=(
            "Optional customer-template benchmark reconciliation with expected, actual, "
            "delta, tolerance and pass/fail rows."
        ),
    )
    dcf_benchmark_reconciliation: Optional[dict[str, object]] = Field(
        None,
        description=(
            "Optional standard-DCF (Gordon-growth) customer-template benchmark "
            "reconciliation — expected vs actual per workbook line with delta, "
            "tolerance and pass/fail rows. Parallel to apv_benchmark_reconciliation "
            "for the standard half of the customer DCF workbook."
        ),
    )

    # Projections (first 5 years for API response)
    calculation_contract_version: Optional[Literal["dcf_calculation.v2"]] = None
    fcf_projections: Optional[list[Decimal]] = None
    pv_fcf_projections: Optional[list[Decimal]] = None
    fcf_projections_5y: list[Decimal] = Field(..., max_length=5)
    pv_fcf_projections_5y: list[Decimal] = Field(..., max_length=5)
    fcf_projection_detail: Optional[list[dict[str, object]]] = Field(
        None,
        description="Granular per-year FCFF buildup (revenue, EBITDA, EBIT, taxes, CapEx, NWC, FCFF).",
    )
    projection_years: Optional[int] = Field(
        None,
        description="Number of explicit forecast years used in the DCF calculation.",
    )

    # Sensitivity analysis
    sensitivity_wacc: dict[str, Decimal]
    sensitivity_growth: dict[str, Decimal]
    sensitivity_matrix_2d: Optional[dict[str, object]] = None
    ebitda_margin_sensitivity: Optional[dict[str, Decimal]] = Field(
        None,
        description="DCF enterprise value by EBITDA-margin scenario.",
    )
    sensitivity_range_policy: Optional[dict[str, object]] = Field(
        None,
        description="Governed low/high construction across WACC, g and EBITDA margin.",
    )

    # Confidence
    confidence: ConfidenceLevel
    confidence_score: int = Field(..., ge=0, le=100)
    confidence_factors: dict[str, str]
    historical_fcf_readiness: Optional[dict[str, object]] = None
    dcf_audit_trail: Optional[dict[str, object]] = Field(
        None,
        description="Step/source summary from DCF transparency collector (API runs).",
    )
    market_assumptions: Optional[dict[str, object]] = Field(
        None,
        description=(
            "DCF market-input provenance, including risk-free rate, ERP, GDP growth, "
            "inflation, sources, and valuation date."
        ),
    )
    data_quality_warnings: Optional[list[dict[str, object]]] = Field(
        None,
        description="DCF-specific quality warnings, such as aggressive forecast assumptions.",
    )


class MultiplesValuationResponse(BaseModel):
    """Market multiples valuation results."""

    # Core valuation values (CRITICAL: These were missing!)
    enterprise_value: Optional[Decimal] = None
    equity_value: Optional[Decimal] = None
    equity_value_low: Optional[Decimal] = None
    equity_value_mid: Optional[Decimal] = None
    equity_value_high: Optional[Decimal] = None

    ev_ebitda_valuation: Optional[Decimal] = None
    ev_revenue_valuation: Optional[Decimal] = None
    pe_valuation: Optional[Decimal] = None

    ebitda_multiple: Optional[Decimal] = None
    revenue_multiple: Optional[Decimal] = None
    pe_multiple: Optional[Decimal] = None

    # Percentile multiples (P25/P50/P75) from comparable companies
    p25_ebitda_multiple: Optional[Decimal] = Field(
        None, description="25th percentile EBITDA multiple from comparables"
    )
    p50_ebitda_multiple: Optional[Decimal] = Field(
        None, description="50th percentile (median) EBITDA multiple from comparables"
    )
    p75_ebitda_multiple: Optional[Decimal] = Field(
        None, description="75th percentile EBITDA multiple from comparables"
    )
    p10_ebitda_multiple: Optional[Decimal] = Field(
        None, description="10th percentile EBITDA multiple (Upswitch SME index band)"
    )
    p90_ebitda_multiple: Optional[Decimal] = Field(
        None, description="90th percentile EBITDA multiple (Upswitch SME index band)"
    )
    p25_revenue_multiple: Optional[Decimal] = Field(
        None, description="25th percentile revenue multiple from comparables"
    )
    p50_revenue_multiple: Optional[Decimal] = Field(
        None, description="50th percentile (median) revenue multiple from comparables"
    )
    p75_revenue_multiple: Optional[Decimal] = Field(
        None, description="75th percentile revenue multiple from comparables"
    )

    # Primary method tracking
    primary_method: Optional[str] = None  # "revenue_multiple" or "ebitda_multiple"
    earnings_basis: Optional[str] = Field(
        None, description="Explicit earnings basis used with the applied multiple."
    )
    data_source: Optional[str] = None  # Where multiples came from

    comparables_count: int
    comparables_quality: ConfidenceLevel

    # Adjustments (Small Firm Effect Transparency)
    base_value: Optional[Decimal] = Field(None, description="Base valuation before adjustments")
    size_discount: Decimal
    liquidity_discount: Decimal
    country_adjustment: Decimal
    growth_premium: Optional[Decimal] = Field(
        default=Decimal("0.0"), description="Growth premium for high-growth companies"
    )
    total_adjustment: Decimal

    adjusted_equity_value: Decimal
    confidence: ConfidenceLevel
    confidence_score: int = Field(..., ge=0, le=100)

    # Owner concentration adjustment (for key person risk)
    owner_concentration: Optional[dict[str, object]] = Field(
        None,
        description="Owner concentration risk adjustment details (ratio, adjustment_factor, risk_level, etc.)",
    )
    multiple_type_blend: Optional[dict[str, object]] = Field(
        None,
        description="EV/EBITDA vs EV/Revenue vs P/E blend weights and contribution rows.",
    )
    discount_build_up: Optional[dict[str, object]] = Field(
        None,
        description="Multiplicative discount stack with advisor weighting and floor policy.",
    )
    multiple_build_up: Optional[dict[str, object]] = Field(
        None,
        description="Canonical show-your-work build-up object for UI/PDF consumers.",
    )
    advisor_override_governance: Optional[dict[str, object]] = Field(
        None,
        description="Override bounds, rationale, and advisor-adjusted labeling metadata.",
    )
    segment_valuation: Optional[dict[str, object]] = Field(
        None,
        description="True SOTP or explicitly flagged blended fallback segment summary.",
    )


class SmallFirmAdjustments(BaseModel):
    """Detailed breakdown of small firm adjustments for transparency."""

    size_discount: Decimal = Field(
        ..., description="Size discount (e.g., -Decimal('0.20') for -20%)"
    )
    size_discount_reason: str = Field(..., description="Explanation of size discount")

    liquidity_discount: Decimal = Field(..., description="Liquidity discount for private companies")
    liquidity_discount_reason: str = Field(..., description="Explanation of liquidity discount")

    country_adjustment: Decimal = Field(..., description="Country risk adjustment")
    country_adjustment_reason: str = Field(..., description="Explanation of country adjustment")

    growth_premium: Decimal = Field(..., description="Growth premium for high-growth companies")
    growth_premium_reason: str = Field(..., description="Explanation of growth premium")

    combined_effect: Decimal = Field(..., description="Net combined adjustment")
    base_value_before_adjustments: Decimal = Field(
        ..., gt=0, description="Base valuation before adjustments"
    )
    adjusted_value_after_adjustments: Decimal = Field(
        ..., gt=0, description="Final adjusted valuation"
    )


class MethodologySelection(BaseModel):
    """Explanation of methodology selection for transparency."""

    selected_methodology: str = Field(
        ..., description="Selected methodology: DCF, MULTIPLES, or HYBRID"
    )
    dcf_included: bool = Field(..., description="Whether DCF was included in valuation")
    dcf_weight: Decimal = Field(
        ..., ge=Decimal("0.0"), le=Decimal("1.0"), description="Weight given to DCF"
    )
    dcf_exclusion_reason: Optional[str] = Field(
        None, description="Reason DCF was excluded (if applicable)"
    )

    multiples_included: bool = Field(..., description="Whether Multiples was included in valuation")
    multiples_weight: Decimal = Field(
        ..., ge=Decimal("0.0"), le=Decimal("1.0"), description="Weight given to Multiples"
    )

    selection_rationale: str = Field(
        ..., description="User-friendly explanation of methodology selection"
    )


class MCPInsightsResponse(BaseModel):
    """MCP (Model Context Protocol) Intelligence Insights."""

    # Pattern analysis summary
    historical_comparables_count: int = Field(
        ..., description="Number of historical valuations analyzed"
    )
    industry_median_multiple: Optional[Decimal] = Field(
        None, description="Industry median revenue multiple"
    )
    industry_quartile_position: Optional[str] = Field(
        None, description="Position in industry (top/upper/median/lower)"
    )

    # Market intelligence
    seasonal_trend: Optional[str] = Field(None, description="Current seasonal market trend")
    market_timing_premium: Optional[Decimal] = Field(
        None, description="Market timing adjustment (%)"
    )

    # Quality metrics
    valuation_quality_score: Optional[int] = Field(
        None, ge=0, le=100, description="Quality of MCP analysis"
    )
    pattern_confidence: Optional[str] = Field(None, description="Confidence in pattern matching")

    # Market context
    market_strategic_insights: Optional[str] = Field(
        None, description="Deterministic strategic market context"
    )
    ai_strategic_insights: Optional[str] = Field(
        None, description="Deprecated alias; use market_strategic_insights"
    )
    key_benchmarks: Optional[list[str]] = Field(None, description="Key benchmark comparisons")

    # Execution metadata
    execution_time_seconds: Optional[Decimal] = Field(
        None, description="MCP pipeline execution time"
    )
    data_freshness: Optional[str] = Field(None, description="Data freshness indicator")


class MonteCarloResults(BaseModel):
    """Monte Carlo simulation results for uncertainty quantification."""

    p10_value: Decimal = Field(..., description="10th percentile (pessimistic)")
    p50_value: Decimal = Field(..., description="50th percentile (median)")
    p90_value: Decimal = Field(..., description="90th percentile (optimistic)")
    mean_value: Decimal = Field(..., description="Mean value from simulation")
    std_deviation: Decimal = Field(..., description="Standard deviation")
    confidence_interval_80: list[Decimal] = Field(
        ..., description="80% confidence interval [low, high]"
    )
    iterations: int = Field(default=10000, description="Number of simulation iterations")
    distribution_data: Optional[list[Decimal]] = Field(
        None, description="Histogram data for visualization"
    )


class ValuationDataQuality(BaseModel):
    """
    Data quality indicators for valuation transparency.

    Tracks the source and quality of valuation multiples to ensure calculation transparency.
    This helps identify when a resolved benchmark contract was used vs. disclosed fallbacks.

    FOUNDATION:
    - Upswitch Index benchmark contracts
    - Local SME market calibration
    - Published transaction, listing, and partner-contribution evidence
    """

    multiples_source: str = Field(
        ...,
        description="Source of valuation multiples. "
        "Best: 'titan_enrichment' (resolved benchmark contract via Titan). "
        "Warning: external/cache/default sources indicate disclosed fallback usage.",
    )

    is_delphi_benchmark_sourced: bool = Field(
        ...,
        description="True if multiples come from a resolved Upswitch Index benchmark contract rather than a disclosed baseline fallback.",
    )

    enrichment_complete: bool = Field(
        ...,
        description="True if Titan provided complete enrichment data (category_id + ev_ebitda_multiple)",
    )

    fallback_used: bool = Field(
        ..., description="True if any hardcoded fallback was used instead of database values"
    )

    fallback_reason: Optional[str] = Field(
        None,
        description="Reason fallback was used (e.g., 'Titan enrichment unavailable', 'business_type_id not in database')",
    )

    business_type_id: Optional[str] = Field(
        None, description="Business type ID used for valuation (e.g., 'advertising-agency')"
    )

    category_id: Optional[str] = Field(
        None,
        description="Category ID from database (e.g., 'creative-media', 'professional-services')",
    )

    business_type_category: Optional[str] = Field(
        None, description="Mapped BusinessTypeCategory enum value (e.g., 'professional_services')"
    )

    data_quality_score: Optional[Decimal] = Field(
        None,
        ge=Decimal("0.0"),
        le=Decimal("1.0"),
        description="Overall data quality score (0-1). Higher is better. Based on multiples source and completeness.",
    )

    academic_sources: Optional[list[str]] = Field(
        None,
        description="List of academic sources used (e.g., 'Damodaran (2024)', 'Koller et al. (2020)')",
    )


class MultiplePipelineStage(BaseModel):
    """Single stage in the multiple discount pipeline (Multiple-First Discounting)."""

    step_number: int = Field(..., description="Step number in calculation journey")
    step_name: str = Field(
        ..., description="Name of the discount step (e.g., 'Owner Concentration')"
    )
    discount_type: str = Field(
        ..., description="Type of discount: 'owner_concentration', 'size', 'liquidity', 'ownership'"
    )
    discount_percentage: Decimal = Field(
        ..., description="Discount percentage applied (e.g., -Decimal('20.0') for 20% discount)"
    )
    multiple_before: Decimal = Field(..., description="Multiple value before this discount")
    multiple_after: Decimal = Field(..., description="Multiple value after this discount")
    metric_value: Decimal = Field(..., description="EBITDA or Revenue value used")
    ev_before: Decimal = Field(..., description="Enterprise Value before this discount")
    ev_after: Decimal = Field(..., description="Enterprise Value after this discount")
    explanation: str = Field(..., description="Human-readable explanation of the discount")


class MultiplePipeline(BaseModel):
    """Complete multiple discount pipeline showing cascading adjustments (Multiple-First Discounting)."""

    initial_multiple: Decimal = Field(..., description="Starting multiple (e.g., 10x)")
    final_multiple: Decimal = Field(..., description="Final adjusted multiple (e.g., 6.48x)")
    total_reduction_percentage: Decimal = Field(
        ..., description="Total reduction percentage (e.g., -35.2%)"
    )
    metric_type: str = Field(..., description="Metric type: 'EBITDA' or 'Revenue'")
    metric_value: Decimal = Field(..., description="Metric value used for calculations")
    stages: list[MultiplePipelineStage] = Field(..., description="All discount stages in order")


class OwnerCompensationSwap(BaseModel):
    """Post-Deal owner-compensation swap (Business Card Pre-Deal/Post-Deal lens).

    Captures the SDE-driven equity transition between the seller's current
    state (owner running the business and taking actual compensation) and
    the post-deal state (a market-rate manager replaces the owner). The
    `post_deal_equity_value` is what a buyer would underwrite on
    normalized economics; `pre_deal_equity_value` is the engine's reported
    headline.

    `applied=False` means the engine couldn't compute the swap (DCF-only
    path, missing inputs). In that case `post_deal_equity_value` mirrors
    `pre_deal_equity_value` and the FE disables the toggle.
    """

    applied: bool = Field(
        ..., description="True when the swap was computed; False when the lens is unavailable."
    )
    state: str = Field(
        default="unknown",
        description=(
            "FE rendering discriminator. One of: 'applied' (swap computed), "
            "'not_applicable' (methodology has no SDE owner-comp dimension — "
            "NAV / startup), 'unavailable' (should have worked but inputs "
            "were missing). FE picks lens-copy variant from this."
        ),
    )
    pre_deal_equity_value: Decimal = Field(
        ..., gt=0, description="Engine equity headline (mid-point) before the SDE swap."
    )
    post_deal_equity_value: Decimal = Field(
        ...,
        gt=0,
        description=(
            "Equity after replacing actual owner compensation with a market-rate "
            "manager and capitalising the delta at the calibrated multiple."
        ),
    )
    pre_deal_equity_low: Optional[Decimal] = Field(
        None, gt=0, description="Pre-Deal low-end equity (mirrors response equity_value_low)."
    )
    post_deal_equity_low: Optional[Decimal] = Field(
        None, gt=0, description="Post-Deal low-end equity, scaled proportionally to the mid swap."
    )
    pre_deal_equity_high: Optional[Decimal] = Field(
        None, gt=0, description="Pre-Deal high-end equity (mirrors response equity_value_high)."
    )
    post_deal_equity_high: Optional[Decimal] = Field(
        None, gt=0, description="Post-Deal high-end equity, scaled proportionally to the mid swap."
    )
    owner_compensation_actual: Optional[Decimal] = Field(
        None, ge=0, description="Reported (or estimated) actual owner compensation in EUR."
    )
    market_replacement_cost: Optional[Decimal] = Field(
        None, ge=0, description="Market rate to hire a replacement manager in EUR."
    )
    owner_compensation_adjustment: Optional[Decimal] = Field(
        None,
        description=(
            "actual_owner_compensation - market_replacement_cost. Positive when "
            "owner is paid above market (typical SME pattern)."
        ),
    )
    effective_multiple: Optional[Decimal] = Field(
        None,
        gt=0,
        description="Calibrated multiple used to capitalise the swap (Step 2.5 multiple_after).",
    )
    equity_delta: Decimal = Field(
        default=Decimal("0"),
        description="post_deal_equity_value - pre_deal_equity_value (signed).",
    )
    data_quality: str = Field(
        default="unknown",
        description="'provided' | 'estimated' | 'unknown' | 'unavailable'.",
    )
    rationale: str = Field(
        default="",
        description="Human-readable explanation of the swap, suitable for FE tooltip / report copy.",
    )
