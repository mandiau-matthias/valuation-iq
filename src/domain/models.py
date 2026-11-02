"""
Pydantic models for valuation domain entities.

These models represent the core data structures used across
all valuation methodologies with comprehensive validation.
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator

# =============================================================================
# OWNER-PROFILING-1 MVP cap (SPIKE-1 §3.2)
# =============================================================================
# These constants are the single source of truth for the owner-dependency
# adjustment band. The Pydantic field on `SynthesizedValuation` binds to them
# directly, the synthesizer's `_apply_mvp_cap` clamps to them, and the report
# aggregator renders the floor in the cap-bind banner from the same value.
#
# CEILING is 0.00 by design, not by oversight: the Damodaran 12-factor engine
# (`owner_dependency_engine._determine_valuation_adjustment`) is a discount
# model — score 100 maps to -5%, score 0 maps to -40%, the curve never crosses
# zero. An owner-led SME cannot earn a positive premium from this dimension;
# strong owner profiling reduces the discount toward zero, it doesn't add
# uplift. Earlier specs floated a +5% upside band; that was never wired and
# would require a different engine (e.g. transferability premium model). Do
# not raise the ceiling without first changing the engine contract.
#
# Relax the FLOOR with care:
#   1. Update `MVP_OWNER_ADJUSTMENT_FLOOR` here.
#   2. Re-run the SPIKE-1 §11.2 attribution gate (≥10 attributed deals).
#   3. Update the Titan Prisma CHECK constraint on
#      `owner_profile_assessment.applied_adjustment` to match.
#   4. The Pydantic field, the processor clamp, and the aggregator copy will
#      pick up the new value automatically — no other edits required.
#
# The processor module re-exports these names for back-compat with existing
# imports (`from src.domain.synthesis.owner_dependency_processor import
# MVP_OWNER_ADJUSTMENT_FLOOR`); new code should import from this module.
# The constant values themselves live in `owner_dependency_constants` so
# both this module and `owner_models/owner_dependency.py` can read them
# at class-definition time without triggering a circular import via
# `models/__init__.py` (which re-exports both modules). Re-export here
# so existing callers (`from src.domain.models import
# MVP_OWNER_ADJUSTMENT_FLOOR`) continue to work.
from src.domain.owner_dependency_constants import (  # noqa: E402
    MVP_OWNER_ADJUSTMENT_CEILING,
    MVP_OWNER_ADJUSTMENT_FLOOR,
    OWNER_DEPENDENCY_ENGINE_CEILING,
    OWNER_DEPENDENCY_ENGINE_FLOOR,
)
from src.domain.session_state_models import (
    ActionItem,
    DataSource,
    FieldMetadata,
    FieldStatus,
    GapAnalysisResult,
    InterfaceRoute,
    SessionFieldState,
)

# =============================================================================
# OWNER-PROFILING engine band (Damodaran 12-factor)
# =============================================================================
# These constants describe the *engine's raw output band* — distinct from the
# MVP cap above. The engine emits in [ENGINE_FLOOR, ENGINE_CEILING];
# `OwnerDependencyProcessor` then clamps to [MVP_FLOOR, MVP_CEILING] before
# anything downstream sees the figure.
#
# Two fields persist BOTH bands:
#   - `OwnerDependencyResult.raw_adjustment` is in the engine band.
#   - `OwnerDependencyResult.valuation_adjustment` is lifecycle-dependent
#     (engine band before processor, MVP band after); we bind it to the
#     wider engine band so engine-level construction in tests / fixtures
#     works without a separate "pre-cap" model.
#   - `owner_profile_assessment.raw_adjustment` (Titan Prisma CHECK)
#     mirrors the engine band; the cross-app drift guard at
#     `tests/unit/synthesis/test_titan_prisma_check_drift.py` pins this.
#
# CEILING matches MVP_CEILING by engine design (see comment block above);
# a future engine that emits positive uplift would need to bump BOTH
# constants and reason through the implications for the cap.


# Import validation function from schemas (may fail during circular import when schemas loads legacy_schemas)
try:
    from src.api.schemas import validate_industry_field
except (ImportError, AttributeError):
    # Fallback for when schemas module is not available
    def validate_industry_field(industry: str) -> str:
        """Fallback validation function."""
        return industry.strip().lower() if industry else ""


class IndustryCode(str, Enum):
    """
    Standard industry classification codes.

    NOTE: This enum is kept for backward compatibility and documentation purposes.
    The actual industry field now accepts any string to support the full taxonomy
    of current business type catalog stored in the PostgreSQL database.

    Common industries include:
    - food-production, food-services
    - professional-services, creative-services, home-services
    - retail-fashion, retail-books
    - healthcare-services, veterinary-services
    - beauty-wellness, fitness-wellness
    - education, ecommerce, marketing-advertising
    """

    TECHNOLOGY = "technology"
    MANUFACTURING = "manufacturing"
    RETAIL = "retail"
    SERVICES = "services"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    REAL_ESTATE = "real_estate"
    HOSPITALITY = "hospitality"
    CONSTRUCTION = "construction"
    FOOD_PRODUCTION = "food-production"
    OTHER = "other"


class BusinessModel(str, Enum):
    """Business model types."""

    B2B_SAAS = "b2b_saas"
    B2C = "b2c"
    MARKETPLACE = "marketplace"
    ECOMMERCE = "ecommerce"
    MANUFACTURING = "manufacturing"
    SERVICES = "services"
    OTHER = "other"


class ConfidenceLevel(str, Enum):
    """Valuation confidence levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValidationWarningSeverity(str, Enum):
    """Severity levels for validation warnings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValidationWarningType(str, Enum):
    """Types of validation warnings."""

    WACC = "wacc"
    CAGR = "cagr"
    GROWTH_CONSISTENCY = "growth_consistency"
    METHODOLOGY_VARIANCE = "methodology_variance"
    DATA_QUALITY = "data_quality"


class ValidationWarning(BaseModel):
    """
    Structured validation warning from sanity checks.

    Provides transparency about calculations that fall outside typical ranges
    or indicate potential data quality issues.

    Used by frontend to display warnings prominently to users.
    """

    type: ValidationWarningType
    severity: ValidationWarningSeverity
    message: str
    details: Optional[str] = None
    recommended_action: Optional[str] = None


class YearData(BaseModel):
    """Financial data for a single year."""

    year: int = Field(..., ge=2000, le=2100)
    revenue: Decimal = Field(
        ...,
        ge=0,
        description="Annual revenue in EUR (0 allowed for holdings and asset-based cases)",
    )
    cogs: Optional[Decimal] = Field(None, ge=0, description="Cost of Goods Sold")
    gross_profit: Optional[Decimal] = Field(None, description="Gross Profit")
    operating_expenses: Optional[Decimal] = Field(None, ge=0)
    ebitda: Decimal = Field(..., description="EBITDA")
    ebit: Optional[Decimal] = Field(None, description="EBIT")
    depreciation: Optional[Decimal] = Field(None, ge=0)
    amortization: Optional[Decimal] = Field(None, ge=0)
    interest_expense: Optional[Decimal] = Field(None, ge=0)
    tax_expense: Optional[Decimal] = Field(None, ge=0)
    net_income: Optional[Decimal] = Field(None)
    ebitda_normalized: bool = Field(
        False,
        description="True when EBITDA reflects advisor-confirmed normalization adjustments.",
    )
    ebitda_normalization_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Reported-to-adjusted EBITDA bridge metadata and add-back ledger.",
    )

    # Balance sheet items
    total_assets: Optional[Decimal] = Field(None, ge=0)
    current_assets: Optional[Decimal] = Field(None, ge=0)
    cash: Optional[Decimal] = Field(None, ge=0)
    accounts_receivable: Optional[Decimal] = Field(None, ge=0)
    accounts_payable: Optional[Decimal] = Field(None, ge=0)
    inventory: Optional[Decimal] = Field(None, ge=0)
    total_liabilities: Optional[Decimal] = Field(None, ge=0)
    current_liabilities: Optional[Decimal] = Field(None, ge=0)
    short_term_debt: Optional[Decimal] = Field(None, ge=0)
    total_debt: Optional[Decimal] = Field(None, ge=0)
    total_equity: Optional[Decimal] = Field(None)

    # Cash flow items
    capex: Optional[Decimal] = Field(None, ge=0, description="Capital Expenditures")
    nwc_change: Optional[Decimal] = Field(None, description="Change in Net Working Capital")
    free_cash_flow: Optional[Decimal] = Field(
        None,
        description="Explicit FCFF for forecast years (skips EBITDA bridge when set)",
    )

    # Forecast flag
    is_forecast: bool = Field(
        False, description="True if this year is a user-provided forecast/prognosis"
    )

    @field_validator("ebitda", "ebit", "net_income")
    @classmethod
    def check_profitability_metrics(cls, v, info):
        """Allow negative values for profitability metrics (losses)."""
        return v

    @model_validator(mode="after")
    def calculate_derived_fields(self):
        """Calculate derived fields if not provided."""
        # Calculate gross profit if not provided
        if self.gross_profit is None and self.cogs is not None:
            self.gross_profit = self.revenue - self.cogs

        # Calculate EBIT if not provided
        if self.ebit is None and self.depreciation is not None and self.amortization is not None:
            self.ebit = self.ebitda - self.depreciation - self.amortization

        # Calculate total equity if not provided
        if (
            self.total_equity is None
            and self.total_assets is not None
            and self.total_liabilities is not None
        ):
            self.total_equity = self.total_assets - self.total_liabilities

        return self


class FinancialData(BaseModel):
    """Complete financial data for a business."""

    company_id: str
    company_name: str
    country_code: str = Field(..., pattern="^[A-Z]{2}$")
    industry: str = Field(..., min_length=1, max_length=100, description="Industry classification")
    business_model: BusinessModel
    founding_year: int = Field(..., ge=1900, le=2100)

    # Prior fiscal years. Three actual years including current_year are
    # recommended for accounting-driven DCF, but explicit FCFF projections can
    # legitimately enter the domain with no prior-year rows.
    historical_years: List[YearData] = Field(..., max_length=10)

    # Current year data (most recent)
    current_year: YearData

    # Explicit forward projections for DCF, separate from realized history
    forecast_years: List[YearData] = Field(default_factory=list, max_length=15)
    balance_sheet_adjustments: List[Any] = Field(
        default_factory=list,
        max_length=50,
        description="Itemized EV-to-equity bridge adjustments carried from request normalization.",
    )

    # Additional context
    number_of_employees: Optional[int] = Field(None, ge=0)
    number_of_owners: Optional[int] = Field(1, ge=1, le=100)
    recurring_revenue_percentage: Decimal = Field(0.0, ge=0.0, le=1.0)
    has_complete_financials: bool = Field(True)

    @property
    def latest_revenue(self) -> Decimal:
        """Get most recent revenue."""
        return self.current_year.revenue

    @property
    def latest_ebitda(self) -> Decimal:
        """Get most recent EBITDA."""
        return self.current_year.ebitda

    @property
    def operating_history_years(self) -> int:
        """Calculate years of operating history."""
        return date.today().year - self.founding_year

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v):
        """Validate and sanitize industry field."""
        return validate_industry_field(v)


class MarketContext(BaseModel):
    """Market and economic context for valuation."""

    country_code: str = Field(..., pattern="^[A-Z]{2}$")
    government_bond_yield: Decimal = Field(
        ..., ge=0.0, le=1.0, description="10-year government bond yield"
    )
    long_term_gdp_growth: Decimal = Field(
        ..., ge=-0.1, le=0.5, description="Long-term GDP growth rate"
    )
    inflation_rate: Decimal = Field(..., ge=-0.05, le=0.5, description="Current inflation rate")
    equity_risk_premium: Decimal = Field(0.06, ge=0.0, le=0.2, description="Market risk premium")
    valuation_date: date = Field(default_factory=date.today)


class IndustryBenchmarks(BaseModel):
    """Industry-specific benchmarks and data."""

    industry: str = Field(..., min_length=1, max_length=100, description="Industry classification")
    region: str = Field(..., description="Geographic region (e.g., EU, DE, FR)")

    # Growth expectations
    expected_growth_rate: Decimal = Field(..., ge=-0.5, le=2.0)
    historical_growth_rate: Optional[Decimal] = Field(None, ge=-0.5, le=2.0)

    # Risk metrics
    average_beta: Decimal = Field(1.0, ge=0.0, le=3.0, description="Industry average beta")
    default_spread: Optional[Decimal] = Field(None, ge=0.0, le=0.5)

    # Operating metrics
    avg_tax_rate: Decimal = Field(0.25, ge=0.0, le=1.0)
    avg_ebitda_margin: Optional[Decimal] = Field(None, ge=-1.0, le=1.0)
    avg_capex_to_revenue: Decimal = Field(0.03, ge=0.0, le=0.5)
    avg_da_to_revenue: Optional[Decimal] = Field(None, ge=0.0, le=0.5)
    avg_nwc_to_revenue: Decimal = Field(0.0, ge=-0.5, le=0.5)

    # Valuation multiples
    median_ev_ebitda: Optional[Decimal] = Field(None, ge=0.0, le=100.0)
    median_ev_revenue: Optional[Decimal] = Field(None, ge=0.0, le=50.0)
    median_pe: Optional[Decimal] = Field(None, ge=0.0, le=200.0)

    data_quality: ConfidenceLevel = Field(ConfidenceLevel.MEDIUM)

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v):
        """Validate and sanitize industry field."""
        return validate_industry_field(v)


class FinancialMetrics(BaseModel):
    """Calculated financial metrics and ratios."""

    # Profitability ratios
    gross_margin: Optional[Decimal] = Field(None, ge=-1.0, le=1.0)
    ebitda_margin: Decimal = Field(..., ge=-5.0, le=1.0)
    ebit_margin: Optional[Decimal] = Field(None, ge=-5.0, le=1.0)
    net_margin: Optional[Decimal] = Field(None, ge=-5.0, le=1.0)
    return_on_assets: Optional[Decimal] = Field(None, ge=-5.0, le=5.0)
    return_on_equity: Optional[Decimal] = Field(None, ge=-10.0, le=10.0)

    # Liquidity ratios
    current_ratio: Optional[Decimal] = Field(None, ge=0.0, le=50.0)
    quick_ratio: Optional[Decimal] = Field(None, ge=0.0, le=50.0)
    cash_ratio: Optional[Decimal] = Field(None, ge=0.0, le=50.0)

    # Leverage ratios
    debt_to_equity: Optional[Decimal] = Field(None, ge=0.0, le=100.0)
    debt_to_assets: Optional[Decimal] = Field(None, ge=0.0, le=10.0)
    interest_coverage: Optional[Decimal] = Field(None, ge=-100.0, le=1000.0)

    # Efficiency ratios
    asset_turnover: Optional[Decimal] = Field(None, ge=0.0, le=50.0)
    receivables_turnover: Optional[Decimal] = Field(None, ge=0.0, le=365.0)
    inventory_turnover: Optional[Decimal] = Field(None, ge=0.0, le=365.0)

    # Growth metrics
    revenue_growth: Decimal = Field(..., ge=-1.0, le=20.0)
    revenue_cagr_3y: Optional[Decimal] = Field(None, ge=-1.0, le=20.0)
    ebitda_growth: Optional[Decimal] = Field(None, ge=-10.0, le=50.0)

    # Risk metrics
    altman_z_score: Optional[Decimal] = Field(None, ge=-10.0, le=50.0)
    financial_health_score: int = Field(..., ge=0, le=100)

    # Owner concentration metrics
    owner_fte_ratio: Optional[Decimal] = Field(
        None, ge=0.0, le=1.0, description="Ratio of operational owners to total employees"
    )


class DCFResult(BaseModel):
    """Results from DCF valuation."""

    enterprise_value: Decimal = Field(..., gt=0)
    equity_value: Decimal = Field(...)
    equity_value_per_share: Optional[Decimal] = Field(None, gt=0)

    # Key assumptions
    wacc: Decimal = Field(..., gt=0, lt=1)
    cost_of_equity: Decimal = Field(..., gt=0, lt=1)
    cost_of_debt: Decimal = Field(..., gt=0, lt=1)
    terminal_growth_rate: Decimal = Field(..., ge=0, lt=0.1)

    # Detailed calculations
    fcf_projections: List[Decimal] = Field(..., min_length=5, max_length=15)
    pv_fcf_projections: List[Decimal] = Field(..., min_length=5, max_length=15)
    terminal_value: Decimal = Field(..., gt=0)
    pv_terminal_value: Decimal = Field(..., gt=0)

    # Sensitivity analysis
    sensitivity_wacc: Dict[str, Decimal] = Field(default_factory=dict)
    sensitivity_growth: Dict[str, Decimal] = Field(default_factory=dict)

    # Confidence assessment
    confidence: ConfidenceLevel
    confidence_score: int = Field(..., ge=0, le=100)
    confidence_factors: Dict[str, str] = Field(default_factory=dict)

    methodology: str = Field("Discounted Cash Flow (DCF)")


class MultiplesResult(BaseModel):
    """Results from market multiples valuation."""

    # Primary valuations
    ev_ebitda_valuation: Optional[Decimal] = Field(None, gt=0)
    ev_revenue_valuation: Optional[Decimal] = Field(None, gt=0)
    pe_valuation: Optional[Decimal] = Field(None, gt=0)

    # Multiples applied
    ebitda_multiple: Optional[Decimal] = Field(None, gt=0)
    revenue_multiple: Optional[Decimal] = Field(None, gt=0)
    pe_multiple: Optional[Decimal] = Field(None, gt=0)

    # Comparable companies info
    comparables_count: int = Field(..., ge=0)
    comparables_quality: ConfidenceLevel

    # Adjustments applied (Small Firm Effect Transparency)
    base_value: Optional[Decimal] = Field(None, gt=0, description="Base value before adjustments")
    size_discount: Decimal = Field(0.0, ge=-0.5, le=0.5)
    liquidity_discount: Decimal = Field(0.0, ge=-0.5, le=0.5)
    country_adjustment: Decimal = Field(0.0, ge=-0.5, le=0.5)
    growth_premium: Decimal = Field(
        0.0, ge=-0.5, le=0.5, description="Growth premium for high-growth companies"
    )
    total_adjustment: Decimal = Field(..., ge=-0.9, le=2.0)

    # Advisor-grade transparency / governance (Defensible Multiples)
    earnings_basis: Optional[str] = Field(
        None,
        description="Earnings basis attached to the applied multiple (EBITDA, SDE, EBIT, Revenue).",
    )
    multiple_type_blend: Dict[str, Any] = Field(
        default_factory=dict,
        description="EV/EBITDA vs EV/Revenue vs P/E blend weights and contributions.",
    )
    discount_build_up: Dict[str, Any] = Field(
        default_factory=dict,
        description="Multiplicative discount stack with advisor weights and floor policy.",
    )
    multiple_build_up: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical show-your-work object consumed by UI/PDF surfaces.",
    )
    advisor_override_governance: Dict[str, Any] = Field(
        default_factory=dict,
        description="Bounds, rationale, and labeling metadata for advisor-entered overrides.",
    )
    segment_valuation: Dict[str, Any] = Field(
        default_factory=dict,
        description="True SOTP segment valuation or flagged blended fallback summary.",
    )
    adjusted_ebitda_build_up: Dict[str, Any] = Field(
        default_factory=dict,
        description="Reported EBITDA to adjusted/maintainable EBITDA build-up.",
    )
    reported_ebitda: Optional[Decimal] = Field(
        None,
        description="Reported EBITDA before advisor-confirmed normalization adjustments.",
    )
    adjusted_ebitda: Optional[Decimal] = Field(
        None,
        description="Adjusted/maintainable EBITDA used by EBITDA multiples.",
    )
    ev_equity_bridge: Dict[str, Any] = Field(
        default_factory=dict,
        description="Itemized EV-to-equity bridge with net debt, NWC, and surplus asset adjustments.",
    )
    nwc_normalization: Dict[str, Any] = Field(
        default_factory=dict,
        description="Working-capital normalization disclosed in the EV-to-equity bridge.",
    )
    nwc_surplus_deficit: Decimal = Field(
        Decimal("0"),
        description="NWC surplus/deficit applied to equity value; positive adds to equity.",
    )
    balance_sheet_adjustments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Signed surplus asset / non-operating balance-sheet adjustments applied to equity.",
    )

    # Final valuation
    adjusted_equity_value: Decimal = Field(..., gt=0)
    confidence: ConfidenceLevel
    confidence_score: int = Field(..., ge=0, le=100)

    methodology: str = Field("Market Multiples")


class SynthesizedValuation(BaseModel):
    """Final synthesized valuation combining multiple methodologies."""

    company_id: str
    company_name: str
    valuation_date: date

    # Individual methodology results
    dcf_valuation: Optional[DCFResult] = None
    multiples_valuation: Optional[MultiplesResult] = None

    # Weights applied to each methodology
    dcf_weight: Decimal = Field(0.0, ge=0.0, le=1.0)
    multiples_weight: Decimal = Field(0.0, ge=0.0, le=1.0)

    # Final valuation range
    equity_value_low: Decimal = Field(..., gt=0)
    equity_value_mid: Decimal = Field(..., gt=0)
    equity_value_high: Decimal = Field(..., gt=0)

    # Key metrics
    financial_metrics: FinancialMetrics

    # Overall confidence
    overall_confidence: ConfidenceLevel
    confidence_score: int = Field(..., ge=0, le=100)

    # Validation warnings from sanity checks
    validation_warnings: List[ValidationWarning] = Field(default_factory=list)

    # Recommendations
    recommended_asking_price: Decimal = Field(..., gt=0)
    recommended_asking_multiple: Optional[Decimal] = Field(None, gt=0)
    valuation_summary: str
    key_value_drivers: List[str]
    risk_factors: List[str]
    methodology_notes: str

    # Owner Dependency Assessment (Phase 4: 12-factor analysis)
    owner_dependency_result: Optional[Any] = None  # OwnerDependencyResult
    # Bound to the MVP-cap constants (single source of truth). Any future
    # relaxation MUST happen at the constant; the field tracks it. A direct
    # write of e.g. -0.40 here was previously accepted at the schema layer
    # even though the live processor clamped at -0.15 — this binding closes
    # that drift gap.
    owner_dependency_adjustment: Decimal = Field(
        default=Decimal("0.0"),
        ge=MVP_OWNER_ADJUSTMENT_FLOOR,
        le=MVP_OWNER_ADJUSTMENT_CEILING,
    )

    # M&A-grade reconciliation of structural (multiple-side) + behavioral
    # (equity-side) owner-risk discounts on a single auditable record.
    # Pure presentation metadata — does not affect any computed value;
    # built post-synthesis from existing pipeline outputs. See
    # `src/domain/owner_risk_ledger.py` for the no-double-count invariant
    # and academic foundation. Optional so back-compat callers / fixtures
    # that don't run the synthesizer's tail remain valid.
    owner_risk_ledger: Optional[Any] = None  # OwnerRiskLedger

    @model_validator(mode="after")
    def validate_valuation_range(self):
        """Ensure valuation range is logical."""
        if not (self.equity_value_low <= self.equity_value_mid <= self.equity_value_high):
            raise ValueError("Valuation range must be: low <= mid <= high")
        return self


class ComparableCompany(BaseModel):
    """Data for a comparable company."""

    symbol: str
    company_name: str
    country: str
    industry: str
    industry_code: Optional[str] = None

    # Financial data
    revenue: Decimal = Field(..., gt=0)
    ebitda: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    total_assets: Optional[Decimal] = Field(None, gt=0)
    total_debt: Optional[Decimal] = Field(None, ge=0)
    cash: Optional[Decimal] = Field(None, ge=0)

    # Market data
    market_cap: Decimal = Field(..., gt=0)
    enterprise_value: Decimal = Field(..., gt=0)

    # Calculated multiples
    ev_ebitda: Optional[Decimal] = Field(None, gt=0)
    ev_revenue: Optional[Decimal] = Field(None, gt=0)
    pe_ratio: Optional[Decimal] = Field(None, gt=0)

    # Similarity metrics
    similarity_score: Optional[Decimal] = Field(None, ge=0.0, le=1.0)
