"""
Type definitions for Step 11 Synthesis Coordinators

Provides proper type hints to replace Any types with specific types.
"""

from decimal import Decimal
from typing import Dict, List, Optional, Protocol, TypedDict, Union

from src.api.routes.valuation.steps.base_step import StepOutput

# ==================== Step Result Types ====================


class StepResultProtocol(Protocol):
    """Protocol for step result objects."""

    step_number: int
    step_name: str
    status: "StepStatus"  # Forward reference
    result: Dict[str, Union[Decimal, int, float, str, bool, None, Dict, List]]
    metadata: Dict[str, Union[Decimal, int, float, str, bool, None, Dict, List]]
    error: Optional[str]
    execution_time_ms: Decimal


# Use StepOutput directly instead of Any
StepResult = StepOutput


# ==================== Previous Results Type ====================

StepNumber = Union[int, float]
PreviousResults = Dict[StepNumber, StepOutput]


# ==================== Key Output Types ====================


class KeyOutputs(TypedDict, total=False):
    """Type for key outputs extracted from step results."""

    pass  # Base type - specific step outputs extend this


class Step0KeyOutputs(KeyOutputs, total=False):
    """Key outputs for Step 0 (Data Quality Assessment)."""

    quality_score: Optional[Union[int, float, Decimal]]
    dimension_scores: Dict[str, Union[int, float, Decimal]]
    dcf_eligible: bool
    dcf_exclusion_reason: Optional[str]
    multiples_method: str
    warnings: List[str]
    recommendations: List[str]
    quality_level: str


class Step1KeyOutputs(KeyOutputs, total=False):
    """Key outputs for Step 1 (Input Validation)."""

    revenue: Optional[Decimal]
    ebitda: Optional[Decimal]
    ebitda_margin: Optional[Decimal]
    weighted_revenue: Optional[Decimal]
    weighted_ebitda: Optional[Decimal]
    using_weighted_metrics: Optional[bool]
    company_name: Optional[str]
    industry: Optional[str]
    country: Optional[str]


class Step2KeyOutputs(KeyOutputs, total=False):
    """Key outputs for Step 2 (Industry Benchmarking)."""

    primary_method: Optional[str]
    primary_method_reason: Optional[str]
    ev_ebitda_multiple: Optional[Decimal]
    ev_revenue_multiple: Optional[Decimal]
    multiples_p25: Optional[Decimal]
    multiples_p50: Optional[Decimal]
    multiples_p75: Optional[Decimal]
    p25_ebitda_multiple: Optional[Decimal]
    p50_ebitda_multiple: Optional[Decimal]
    p75_ebitda_multiple: Optional[Decimal]
    p25_revenue_multiple: Optional[Decimal]
    p50_revenue_multiple: Optional[Decimal]
    p75_revenue_multiple: Optional[Decimal]
    comparables_count: Optional[int]
    comparables_quality: Optional[str]
    data_source: Optional[str]
    dcf_eligible: Optional[bool]
    recommended_methodology: Optional[str]
    dcf_suitability_score: Optional[Decimal]
    business_category: Optional[str]


class Step3KeyOutputs(KeyOutputs, total=False):
    """Key outputs for Step 3 (Base Enterprise Value)."""

    enterprise_value_low: Optional[Decimal]
    enterprise_value_mid: Optional[Decimal]
    enterprise_value_high: Optional[Decimal]
    metric_used: Optional[str]
    metric_value: Optional[Decimal]
    multiple_low: Optional[Decimal]
    multiple_mid: Optional[Decimal]
    multiple_high: Optional[Decimal]
    multiple_p25: Optional[Decimal]
    multiple_p50: Optional[Decimal]
    multiple_p75: Optional[Decimal]
    percentile_source: Optional[str]
    primary_method: Optional[str]
    auto_corrected: Optional[bool]


class Step4KeyOutputs(KeyOutputs, total=False):
    """Key outputs for Step 4 (Owner Concentration)."""

    enterprise_value_low: Optional[Decimal]
    enterprise_value_mid: Optional[Decimal]
    enterprise_value_high: Optional[Decimal]
    owner_employee_ratio: Optional[Decimal]
    risk_level: Optional[str]
    adjustment_percentage: Optional[Decimal]
    number_of_owners: Optional[int]
    number_of_employees: Optional[int]
    calibration_type: Optional[str]
    business_type_id: Optional[str]
    ev_low_before: Optional[Decimal]
    ev_mid_before: Optional[Decimal]
    ev_high_before: Optional[Decimal]


class Step5KeyOutputs(KeyOutputs, total=False):
    """Key outputs for Step 5 (Size Discount)."""

    enterprise_value_low: Optional[Decimal]
    enterprise_value_mid: Optional[Decimal]
    enterprise_value_high: Optional[Decimal]
    revenue_tier: Optional[str]
    base_discount: Optional[Decimal]
    adjustment_multiplier: Optional[Decimal]
    size_discount_percentage: Optional[Decimal]
    business_category: Optional[str]
    ev_low_before: Optional[Decimal]
    ev_mid_before: Optional[Decimal]
    ev_high_before: Optional[Decimal]


class Step6KeyOutputs(KeyOutputs, total=False):
    """Key outputs for Step 6 (Liquidity Discount)."""

    enterprise_value_low: Optional[Decimal]
    enterprise_value_mid: Optional[Decimal]
    enterprise_value_high: Optional[Decimal]
    base_discount: Optional[Decimal]
    margin_bonus: Optional[Decimal]
    growth_bonus: Optional[Decimal]
    recurring_revenue_bonus: Optional[Decimal]
    size_bonus: Optional[Decimal]
    total_discount_percentage: Optional[Decimal]
    business_category: Optional[str]
    base_step: Optional[int]
    ev_low_before: Optional[Decimal]
    ev_mid_before: Optional[Decimal]
    ev_high_before: Optional[Decimal]


class Step7KeyOutputs(KeyOutputs, total=False):
    """Key outputs for Step 7 (EV to Equity Conversion)."""

    equity_value_low: Optional[Decimal]
    equity_value_mid: Optional[Decimal]
    equity_value_high: Optional[Decimal]
    total_debt: Optional[Decimal]
    cash: Optional[Decimal]
    operating_cash: Optional[Decimal]
    excess_cash: Optional[Decimal]
    net_debt: Optional[Decimal]
    balance_sheet_available: Optional[bool]
    ev_source_step: Optional[int]
    exemption_applied: Optional[bool]
    range_validated: Optional[bool]
    ev_low: Optional[Decimal]
    ev_mid: Optional[Decimal]
    ev_high: Optional[Decimal]


class Step8KeyOutputs(KeyOutputs, total=False):
    """Key outputs for Step 8 (Ownership Adjustment)."""

    equity_value_low: Optional[Decimal]
    equity_value_mid: Optional[Decimal]
    equity_value_high: Optional[Decimal]
    ownership_percentage: Optional[Decimal]
    adjustment_type: Optional[str]
    adjustment_percentage: Optional[Decimal]
    equity_low_before: Optional[Decimal]
    equity_mid_before: Optional[Decimal]
    equity_high_before: Optional[Decimal]


class Step9KeyOutputs(KeyOutputs, total=False):
    """Key outputs for Step 9 (Confidence Score)."""

    overall_confidence_score: Optional[Union[int, float, Decimal]]
    confidence_level: Optional[str]
    factor_scores: Dict[str, Union[int, float, Decimal]]


class Step10KeyOutputs(KeyOutputs, total=False):
    """Key outputs for Step 10 (Range Methodology)."""

    valuation_low: Optional[Decimal]
    valuation_mid: Optional[Decimal]
    valuation_high: Optional[Decimal]
    methodology: Optional[str]
    confidence_level: Optional[str]
    base_spread: Optional[Decimal]
    business_type_multiplier: Optional[Decimal]
    size_adjustment: Optional[Decimal]
    growth_adjustment: Optional[Decimal]
    profitability_adjustment: Optional[Decimal]
    data_quality_adjustment: Optional[Decimal]
    total_spread: Optional[Decimal]
    asymmetric_adjustment: Optional[Decimal]
    downside_factor: Optional[Decimal]
    upside_factor: Optional[Decimal]
    step7_equity_value_mid: Optional[Decimal]
    value_preservation_validated: Optional[bool]


class Step11KeyOutputs(KeyOutputs, total=False):
    """Key outputs for Step 11 (Final Valuation)."""

    valuation_low: Optional[Decimal]
    valuation_mid: Optional[Decimal]
    valuation_high: Optional[Decimal]
    confidence_score: Optional[Union[int, float, Decimal]]
    methodology_statement: Optional[str]
    professional_review_ready: Optional[Dict[str, Union[bool, int, str]]]
    value_chain_validated: Optional[bool]
    # Engine SDE cross-check / blend (when a Seller's-Discretionary-Earnings leg
    # was weighted into the headline). Surfaced so the report can disclose the
    # EBITDA-leg + SDE-leg -> headline bridge instead of an unexplained drop.
    sde_cross_check: Optional[Dict[str, object]]


# Union type for all key outputs
KeyOutputsUnion = Union[
    Step0KeyOutputs,
    Step1KeyOutputs,
    Step2KeyOutputs,
    Step3KeyOutputs,
    Step4KeyOutputs,
    Step5KeyOutputs,
    Step6KeyOutputs,
    Step7KeyOutputs,
    Step8KeyOutputs,
    Step9KeyOutputs,
    Step10KeyOutputs,
    Step11KeyOutputs,
    Dict[str, Union[Decimal, int, float, str, bool, None, Dict, List]],  # Fallback
]


# ==================== Adjustment Types ====================


class Adjustment(TypedDict, total=False):
    """Type for adjustment extraction."""

    step: str
    step_number: int
    adjustment: Decimal
    adjustment_pct: Decimal
    type: str
    rationale: Optional[str]
    ownership_percentage: Optional[Decimal]
    tier: Optional[str]


# ==================== Data Source Types ====================


class DataSource(TypedDict, total=False):
    """Type for data source extraction."""

    type: str
    source: str


# ==================== Pipeline Types ====================


class PipelineStage(TypedDict, total=False):
    """Type for pipeline stage."""

    step: int
    step_name: str
    multiple_before_low: Optional[Decimal]
    multiple_before_mid: Optional[Decimal]
    multiple_before_high: Optional[Decimal]
    multiple_after_low: Optional[Decimal]
    multiple_after_mid: Optional[Decimal]
    multiple_after_high: Optional[Decimal]
    discount_percentage: Decimal
    description: str


class DiscountWaterfallStep(TypedDict, total=False):
    """Type for discount waterfall step."""

    step: Union[int, str]
    step_name: str
    multiple_before_low: Optional[Decimal]
    multiple_before_mid: Optional[Decimal]
    multiple_before_high: Optional[Decimal]
    multiple_after_low: Optional[Decimal]
    multiple_after_mid: Optional[Decimal]
    multiple_after_high: Optional[Decimal]
    discount_percentage: Decimal
    description: str


class MultiplePipeline(TypedDict, total=False):
    """Type for multiple pipeline."""

    initial_multiple_low: Optional[Decimal]
    initial_multiple_mid: Optional[Decimal]
    initial_multiple_high: Optional[Decimal]
    final_multiple_low: Optional[Decimal]
    final_multiple_mid: Optional[Decimal]
    final_multiple_high: Optional[Decimal]
    total_reduction_percentage: Decimal
    metric_type: str
    metric_value: Optional[Decimal]
    stages: List[PipelineStage]
    discount_waterfall: List[DiscountWaterfallStep]


# ==================== Transparency Report Types ====================


class CalculationStepData(TypedDict, total=False):
    """Type for calculation step in transparency report."""

    step: int
    name: str
    description: str
    status: str
    execution_time_ms: Decimal
    key_outputs: Dict[str, Union[Decimal, int, float, str, bool, None, Dict, List]]
    reason: Optional[str]
    error: Optional[str]
    methodology_note: Optional[str]


class ConfidenceBreakdown(TypedDict, total=False):
    """Type for confidence breakdown."""

    overall: Optional[Union[int, float, Decimal]]
    data_quality: Optional[Union[int, float, Decimal]]
    methodology: Optional[Union[int, float, Decimal]]


class TransparencyReport(TypedDict, total=False):
    """Type for transparency report."""

    calculation_steps: List[CalculationStepData]
    data_sources: List[DataSource]
    adjustments_applied: List[Adjustment]
    confidence_breakdown: ConfidenceBreakdown
    standards_compliance: List[str]
    methodology_statement: Optional[str]
    academic_sources: Optional[List[Dict[str, str]]]
    professional_review_ready: Optional[Dict[str, Union[bool, int, str]]]


# ==================== Methodology Types ====================


class Methodologies(TypedDict, total=False):
    """Type for methodologies."""

    primary_method: Optional[str]
    range_methodology: Optional[str]
    dcf_used: Optional[bool]
    multiples_used: Optional[bool]
    hybrid_used: Optional[bool]
    confidence_methodology: Optional[str]
    used_methodologies: Optional[List[str]]


class AcademicSource(TypedDict, total=False):
    """Type for academic source."""

    title: str
    author: Optional[str]
    url: Optional[str]
    year: Optional[int]


class ProfessionalReviewReady(TypedDict, total=False):
    """Type for professional review readiness."""

    ready: bool
    score: Optional[int]
    status: Optional[str]


# ==================== Function Protocol Types ====================


class GetPreviousStepResultFunc(Protocol):
    """Protocol for get_previous_step_result function."""

    def __call__(
        self, step_num: StepNumber, previous_results: PreviousResults
    ) -> Optional[Dict[str, Union[Decimal, int, float, str, bool, None, Dict, List]]]:
        """Get previous step result."""
        ...
