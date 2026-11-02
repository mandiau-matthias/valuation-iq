"""
DCF Types and Data Structures

This module defines all data structures, enums, and configuration classes
for the DCF (Discounted Cash Flow) valuation engine refactoring.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional


class DCFMethodology(str, Enum):
    """DCF calculation methodology types"""

    GORDON_GROWTH = "gordon_growth"
    EXIT_MULTIPLE = "exit_multiple"
    HYBRID = "hybrid"


class GrowthModel(str, Enum):
    """Growth projection models"""

    LINEAR = "linear"
    DECAY = "decay"
    STEP = "step"
    CUSTOM = "custom"


class SensitivityType(str, Enum):
    """Sensitivity analysis types"""

    WACC = "wacc"
    GROWTH = "growth"
    TERMINAL_GROWTH = "terminal_growth"
    BETA = "beta"
    TAX_RATE = "tax_rate"


class CostOfEquityModel(str, Enum):
    """
    Cost of equity calculation model types.

    CAPM: Single-factor Capital Asset Pricing Model (Sharpe, 1964)
          Re = Rf + β * (Rm - Rf)

    FAMA_FRENCH_3: Three-factor model (Fama & French, 1992)
                   Re = Rf + β_mkt*(Rm-Rf) + β_smb*SMB + β_hml*HML
                   - SMB: Small Minus Big (size premium)
                   - HML: High Minus Low (value premium)
                   Recommended for SMEs due to size factor capture.

    FAMA_FRENCH_5: Five-factor model (Fama & French, 2015)
                   Adds RMW (profitability) and CMA (investment) factors.
                   More granular but requires additional data.
    """

    CAPM = "capm"
    FAMA_FRENCH_3 = "fama_french_3"
    FAMA_FRENCH_5 = "fama_french_5"


@dataclass
class DCFConfiguration:
    """Configuration for DCF valuation calculations"""

    projection_years: int = 5
    terminal_growth_method: DCFMethodology = DCFMethodology.GORDON_GROWTH
    growth_model: GrowthModel = GrowthModel.DECAY
    sensitivity_analysis: bool = True
    confidence_threshold: Decimal = 0.7
    wacc_range: tuple[float, float] = (0.05, 0.30)
    growth_range: tuple[float, float] = (-0.10, 0.50)
    terminal_growth_range: tuple[float, float] = (0.01, 0.05)
    beta_range: tuple[float, float] = (0.5, 2.5)
    tax_rate_range: tuple[float, float] = (0.15, 0.35)
    # Cash-flow timing convention. True = mid-year discounting (0.5, 1.5, ...);
    # False = year-end discounting (1, 2, ...), used by many accountant DCF templates.
    mid_year_discounting: bool = True
    # Cost of equity model selection (default CAPM, use FAMA_FRENCH_3 for SMEs)
    cost_of_equity_model: CostOfEquityModel = CostOfEquityModel.CAPM
    # Fama-French factor defaults (based on historical EU/US averages)
    # SMB premium: ~3% annually (Fama-French 1992, updated Duff & Phelps 2024)
    smb_premium: Decimal = Decimal("0.03")
    # HML premium: ~4% annually (value stocks outperform growth)
    hml_premium: Decimal = Decimal("0.04")


@dataclass
class CashFlowProjection:
    """Cash flow projection data structure"""

    year: int
    revenue: Decimal
    ebitda: Decimal
    ebit: Decimal
    taxes: Decimal
    capex: Decimal
    nwc_change: Decimal
    free_cash_flow: Decimal
    growth_rate: Decimal
    cumulative_growth: Decimal = 0.0
    confidence_score: Decimal = 1.0


@dataclass
class ForwardWaccEvidence:
    """Machine-readable provenance for WACC used by forward DCF/cone gates."""

    capital_structure_source: str
    capital_structure_fallback: bool
    confidence: str
    equity_weight: Decimal
    debt_weight: Decimal
    observed_total_debt: Decimal
    observed_total_equity: Decimal
    fallback_reason: Optional[str] = None
    risk_free_rate_source: str = "market_context"
    market_risk_premium_source: str = "market_context"
    beta_source: str = "industry_benchmark"
    cost_of_debt_source: str = "balance_sheet_leverage_and_market_context"
    tax_rate_source: str = "industry_benchmark"
    size_premium_source: Optional[str] = None
    company_specific_risk_source: Optional[str] = None
    warnings: tuple[str, ...] = ()


@dataclass
class WACCComponents:
    """WACC calculation components"""

    cost_of_equity: Decimal
    cost_of_debt: Decimal
    equity_weight: Decimal
    debt_weight: Decimal
    tax_rate: Decimal
    wacc: Decimal
    beta: Decimal
    risk_free_rate: Decimal
    market_risk_premium: Decimal
    debt_yield: Decimal
    tax_shield: Decimal
    size_premium: Decimal = Decimal("0")
    company_specific_risk: Decimal = Decimal("0")
    evidence: Optional[ForwardWaccEvidence] = None


@dataclass
class TerminalValueParams:
    """Terminal value calculation parameters"""

    final_fcf: Decimal
    terminal_growth_rate: Decimal
    wacc: Decimal
    terminal_value: Decimal
    pv_terminal_value: Decimal
    methodology: DCFMethodology
    exit_multiple: Optional[Decimal] = None
    exit_year_ebitda: Optional[Decimal] = None
    terminal_growth_evidence: Optional[dict[str, object]] = None


@dataclass
class SensitivityRange:
    """Sensitivity analysis range definition"""

    parameter: SensitivityType
    min_value: Decimal
    max_value: Decimal
    step_size: Decimal
    base_value: Decimal
    scenarios: list[Decimal] = field(default_factory=list)


@dataclass
class SensitivityResult:
    """Sensitivity analysis result"""

    parameter: SensitivityType
    base_value: Decimal
    base_result: Decimal
    scenarios: dict[Decimal, Decimal]
    impact_range: tuple[float, float]
    volatility: Decimal
    key_drivers: list[str] = field(default_factory=list)


@dataclass
class DCFResult:
    """Complete DCF valuation result"""

    enterprise_value: Decimal
    equity_value: Decimal
    wacc: Decimal
    cost_of_equity: Decimal
    cost_of_debt: Decimal
    terminal_growth_rate: Decimal
    fcf_projections: list[Decimal]
    pv_fcf_projections: list[Decimal]
    terminal_value: Decimal
    pv_terminal_value: Decimal
    sensitivity_wacc: dict[Decimal, Decimal]
    sensitivity_growth: dict[Decimal, Decimal]
    confidence: str
    confidence_score: Decimal
    confidence_factors: list[str]
    historical_fcf_readiness: Optional[dict[str, object]] = None
    sensitivity_matrix_2d: Optional[dict[str, object]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    methodology: str = "dcf"
    transparency_data: Optional[dict[str, object]] = None
    wacc_components: Optional[WACCComponents] = None
    projection_detail: Optional[list["CashFlowProjection"]] = None
    # Implied EV/EBITDA — a sanity cross-check of the intrinsic DCF value
    # against market multiples (None when no positive EBITDA base is available).
    implied_ev_ebitda: Optional[Decimal] = None
    # Terminal-value steady-state check. The Gordon perpetuity assumes the
    # business reinvests just enough to sustain capacity (CapEx ≈ D&A). This
    # dict reports whether the final explicit year satisfies that; None when it
    # cannot be checked (e.g. FCFF-only input with no CapEx/D&A detail).
    terminal_value_steady_state: Optional[dict[str, object]] = None
    terminal_growth_evidence: Optional[dict[str, object]] = None
    valuation_date_convention: str = "present_value_as_of_current_valuation_date"


@dataclass
class HistoricalFCF:
    """Historical free cash flow data"""

    years: list[int]
    fcf_values: list[Decimal]
    revenue: list[Decimal]
    ebitda: list[Decimal]
    taxes: list[Decimal]
    capex: list[Decimal]
    nwc_change: list[Decimal]
    actual_tax_years: int
    actual_capex_years: int
    actual_nwc_years: int
    cagr: Decimal
    volatility: Decimal
    trend: str  # "increasing", "decreasing", "stable", "volatile"


@dataclass
class GrowthProjection:
    """Growth projection parameters"""

    historical_growth: Decimal
    industry_growth: Decimal
    economic_growth: Decimal
    blended_growth: Decimal
    decay_factor: Decimal
    terminal_growth: Decimal
    projection_years: int
    model: GrowthModel


@dataclass
class CAPMComponents:
    """CAPM (Capital Asset Pricing Model) components"""

    risk_free_rate: Decimal
    beta: Decimal
    market_risk_premium: Decimal
    cost_of_equity: Decimal
    beta_source: str  # "industry", "peer", "estimated", "regression"
    confidence: Decimal


@dataclass
class FamaFrenchComponents:
    """
    Fama-French 3-Factor Model Components

    Academic Foundation:
    - Fama, E.F. & French, K.R. (1992): "The Cross-Section of Expected Stock Returns"
    - Fama, E.F. & French, K.R. (1993): "Common Risk Factors in Returns on Stocks and Bonds"

    Formula:
    Re = Rf + β_mkt*(Rm-Rf) + β_smb*SMB + β_hml*HML

    Where:
    - Rf: Risk-free rate
    - Rm: Expected market return
    - β_mkt: Market beta (systematic risk)
    - SMB: Small Minus Big - size premium (small cap outperformance)
    - β_smb: Sensitivity to size factor
    - HML: High Minus Low - value premium (value vs growth)
    - β_hml: Sensitivity to value factor

    For SMEs:
    - β_smb is typically higher (1.0-1.5) due to small firm effect
    - β_hml varies by industry (higher for capital-intensive sectors)
    """

    # Core components
    risk_free_rate: Decimal
    market_beta: Decimal  # β_mkt - systematic market risk
    market_risk_premium: Decimal  # (Rm - Rf)

    # Size factor (SMB - Small Minus Big)
    smb_premium: Decimal  # Average ~3% annually
    smb_beta: Decimal  # β_smb - sensitivity to size factor (typically 1.0-1.5 for SMEs)

    # Value factor (HML - High Minus Low)
    hml_premium: Decimal  # Average ~4% annually
    hml_beta: Decimal  # β_hml - sensitivity to value factor

    # Calculated cost of equity
    cost_of_equity: Decimal

    # Metadata
    model_type: str = "fama_french_3"
    beta_source: str = "sme_adjusted"
    confidence: Decimal = Decimal("0.85")

    # Academic citations for transparency
    academic_sources: list[str] = field(
        default_factory=lambda: [
            "Fama & French (1992): The Cross-Section of Expected Stock Returns",
            "Fama & French (1993): Common Risk Factors in Returns on Stocks and Bonds",
            "Duff & Phelps (2024): Valuation Handbook - size premium data",
        ]
    )


@dataclass
class DebtStructure:
    """Debt structure analysis"""

    total_debt: Decimal
    short_term_debt: Decimal
    long_term_debt: Decimal
    debt_yield: Decimal
    credit_rating: Optional[str]
    cost_of_debt: Decimal
    tax_shield: Decimal
    leverage_ratio: Decimal


@dataclass
class EconomicContext:
    """Economic context for DCF calculations"""

    gdp_growth: Decimal
    inflation_rate: Decimal
    interest_rate: Decimal
    market_conditions: str  # "bull", "bear", "neutral"
    cycle_position: str  # "expansion", "contraction", "peak", "trough"
    risk_appetite: Decimal  # 0.0 to 1.0
    volatility_index: Decimal


@dataclass
class IndustryContext:
    """Industry-specific context for DCF calculations"""

    industry_name: str
    growth_rate: Decimal
    volatility: Decimal
    cyclicality: str  # "high", "medium", "low"
    capital_intensity: str  # "high", "medium", "low"
    competitive_position: str  # "leader", "follower", "challenger"
    market_maturity: str  # "emerging", "growth", "mature", "decline"


@dataclass
class CompanyProfile:
    """Company-specific profile for DCF calculations"""

    company_name: str
    size: str  # "small", "medium", "large", "enterprise"
    stage: str  # "startup", "growth", "mature", "decline"
    profitability: str  # "high", "medium", "low", "negative"
    growth_stage: str  # "early", "growth", "mature", "decline"
    competitive_advantages: list[str]
    risk_factors: list[str]


# Default configurations
DEFAULT_DCF_CONFIG = DCFConfiguration(
    projection_years=5,
    terminal_growth_method=DCFMethodology.GORDON_GROWTH,
    growth_model=GrowthModel.DECAY,
    sensitivity_analysis=True,
    confidence_threshold=0.7,
    wacc_range=(0.05, 0.30),
    growth_range=(-0.10, 0.50),
    terminal_growth_range=(0.01, 0.05),
    beta_range=(0.5, 2.5),
    tax_rate_range=(0.15, 0.35),
)

# Sensitivity analysis ranges
SENSITIVITY_RANGES = {
    SensitivityType.WACC: SensitivityRange(
        parameter=SensitivityType.WACC,
        min_value=0.05,
        max_value=0.25,
        step_size=0.01,
        base_value=0.10,
    ),
    SensitivityType.GROWTH: SensitivityRange(
        parameter=SensitivityType.GROWTH,
        min_value=-0.05,
        max_value=0.20,
        step_size=0.02,
        base_value=0.05,
    ),
    SensitivityType.TERMINAL_GROWTH: SensitivityRange(
        parameter=SensitivityType.TERMINAL_GROWTH,
        min_value=0.01,
        max_value=0.05,
        step_size=0.005,
        base_value=0.025,
    ),
    SensitivityType.BETA: SensitivityRange(
        parameter=SensitivityType.BETA, min_value=0.5, max_value=2.0, step_size=0.1, base_value=1.0
    ),
    SensitivityType.TAX_RATE: SensitivityRange(
        parameter=SensitivityType.TAX_RATE,
        min_value=0.15,
        max_value=0.35,
        step_size=0.02,
        base_value=0.25,
    ),
}

# Confidence levels
CONFIDENCE_LEVELS = {
    "high": {"min_score": 0.8, "description": "High confidence in valuation"},
    "medium": {"min_score": 0.6, "description": "Medium confidence in valuation"},
    "low": {"min_score": 0.4, "description": "Low confidence in valuation"},
    "very_low": {"min_score": 0.0, "description": "Very low confidence in valuation"},
}
