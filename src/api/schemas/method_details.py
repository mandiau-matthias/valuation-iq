"""
Typed detail schemas for each Omni-Calc valuation method.

Each ``MethodResult.details`` dict follows one of the TypedDicts below,
depending on the method key.  The schemas serve as living documentation
and are enforced at build-time by ``build_*_details`` helpers so that
downstream consumers (report templates, Venus frontend, PDF pipeline)
can rely on a stable key contract.

Usage in ``omni_calc_coordinator.py``::

    from src.api.schemas.method_details import build_dcf_details
    details = build_dcf_details(enterprise_value=..., terminal_value=..., ...)
"""

from typing import Dict, List, Optional, TypedDict, Union

from src.api.schemas.dcf_method_details import DcfDetails, build_dcf_details
from src.api.schemas.liquidation_method_details import (
    LiquidationAnalysisDetails,
    build_liquidation_analysis_details,
)

# ---------------------------------------------------------------------------
# 1. UpSwitch Adaptive
# ---------------------------------------------------------------------------


class AdaptiveDetails(TypedDict, total=False):
    description: str
    primary_basis: str  # "hybrid" | "asset_based"
    methodology_justification: str
    primary_method_key: str  # only when asset-based
    equity_range_low: float
    equity_range_high: float
    saas_metrics: Dict[str, object]
    saas_adjustment_breakdown: List[Dict[str, object]]
    secondary_method_key: str
    secondary_method_label: str


def build_adaptive_details(
    *,
    description: str,
    primary_basis: str,
    methodology_justification: str,
    primary_method_key: Optional[str] = None,
    equity_range_low: Optional[float] = None,
    equity_range_high: Optional[float] = None,
    saas_metrics: Optional[Dict[str, object]] = None,
    saas_adjustment_breakdown: Optional[List[Dict[str, object]]] = None,
    secondary_method_key: Optional[str] = None,
    secondary_method_label: Optional[str] = None,
) -> AdaptiveDetails:
    d: AdaptiveDetails = {
        "description": description,
        "primary_basis": primary_basis,
        "methodology_justification": methodology_justification,
    }
    if primary_method_key is not None:
        d["primary_method_key"] = primary_method_key
    if equity_range_low is not None:
        d["equity_range_low"] = equity_range_low
    if equity_range_high is not None:
        d["equity_range_high"] = equity_range_high
    if saas_metrics is not None:
        d["saas_metrics"] = saas_metrics
    if saas_adjustment_breakdown is not None:
        d["saas_adjustment_breakdown"] = saas_adjustment_breakdown
    if secondary_method_key is not None:
        d["secondary_method_key"] = secondary_method_key
    if secondary_method_label is not None:
        d["secondary_method_label"] = secondary_method_label
    return d


# ---------------------------------------------------------------------------
# 2. EBITDA Multiple
# ---------------------------------------------------------------------------


class EbitdaMultipleDetails(TypedDict, total=False):
    enterprise_value: float
    enterprise_value_low: float
    enterprise_value_high: float
    reference_enterprise_value: float
    reference_multiple: float
    method_adjustment_factor: float
    p25_multiple: float
    p75_multiple: float
    equity_range_low: float
    equity_range_high: float
    saas_metrics: Dict[str, object]
    saas_adjustment_factor: float


def build_ebitda_details(
    *,
    enterprise_value: float,
    p25_multiple: float,
    p75_multiple: float,
    enterprise_value_low: Optional[float] = None,
    enterprise_value_high: Optional[float] = None,
    equity_range_low: Optional[float] = None,
    equity_range_high: Optional[float] = None,
    saas_metrics: Optional[Dict[str, object]] = None,
    saas_adjustment_factor: Optional[float] = None,
    reference_enterprise_value: Optional[float] = None,
    reference_multiple: Optional[float] = None,
    method_adjustment_factor: Optional[float] = None,
) -> EbitdaMultipleDetails:
    d: EbitdaMultipleDetails = {
        "enterprise_value": enterprise_value,
        "p25_multiple": p25_multiple,
        "p75_multiple": p75_multiple,
    }
    if enterprise_value_low is not None:
        d["enterprise_value_low"] = enterprise_value_low
    if enterprise_value_high is not None:
        d["enterprise_value_high"] = enterprise_value_high
    if equity_range_low is not None:
        d["equity_range_low"] = equity_range_low
    if equity_range_high is not None:
        d["equity_range_high"] = equity_range_high
    if saas_metrics is not None:
        d["saas_metrics"] = saas_metrics
    if saas_adjustment_factor is not None:
        d["saas_adjustment_factor"] = saas_adjustment_factor
    if reference_enterprise_value is not None:
        d["reference_enterprise_value"] = reference_enterprise_value
    if reference_multiple is not None:
        d["reference_multiple"] = reference_multiple
    if method_adjustment_factor is not None:
        d["method_adjustment_factor"] = method_adjustment_factor
    return d


# ---------------------------------------------------------------------------
# 4. SDE Multiple
# ---------------------------------------------------------------------------


class SdeMultipleDetails(TypedDict, total=False):
    # Core required keys — present on every SDE MethodResult.
    sde: float
    owner_salary_addback: float
    owner_salary_source: str  # "trial_balance" | "estimate"
    owner_salary_estimate: float
    enterprise_value: float
    enterprise_value_low: float
    enterprise_value_high: float
    # SDE channel context (optional — populated when the SDE calibration
    # cascade has been run). Carrying these on details keeps the SDE
    # rendering path independent of the EBITDA cascade.
    sde_base_multiple: float
    sde_applied_multiple: float
    sde_multiple_p25: float
    sde_multiple_p75: float
    equity_range_low: float
    equity_range_high: float
    owner_role: str  # "working" | "passive"
    owner_concentration_tier: str  # "low" | "medium" | "high"
    owner_concentration_adjustment: float  # multiplicative delta on the multiple
    size_discount_adjustment: float
    liquidity_discount_adjustment: float
    belgian_market_premium: float
    sde_calibration_steps: List[Dict[str, object]]
    sde_bridge: List[Dict[str, object]]


def build_sde_details(
    *,
    sde: float,
    owner_salary_addback: float,
    owner_salary_source: str,
    owner_salary_estimate: float,
    enterprise_value: float,
    enterprise_value_low: Optional[float] = None,
    enterprise_value_high: Optional[float] = None,
    sde_base_multiple: Optional[float] = None,
    sde_applied_multiple: Optional[float] = None,
    sde_multiple_p25: Optional[float] = None,
    sde_multiple_p75: Optional[float] = None,
    equity_range_low: Optional[float] = None,
    equity_range_high: Optional[float] = None,
    owner_role: Optional[str] = None,
    owner_concentration_tier: Optional[str] = None,
    owner_concentration_adjustment: Optional[float] = None,
    size_discount_adjustment: Optional[float] = None,
    liquidity_discount_adjustment: Optional[float] = None,
    belgian_market_premium: Optional[float] = None,
    sde_calibration_steps: Optional[List[Dict[str, object]]] = None,
    sde_bridge: Optional[List[Dict[str, object]]] = None,
) -> SdeMultipleDetails:
    d: SdeMultipleDetails = {
        "sde": sde,
        "owner_salary_addback": owner_salary_addback,
        "owner_salary_source": owner_salary_source,
        "owner_salary_estimate": owner_salary_estimate,
        "enterprise_value": enterprise_value,
    }
    if enterprise_value_low is not None:
        d["enterprise_value_low"] = enterprise_value_low
    if enterprise_value_high is not None:
        d["enterprise_value_high"] = enterprise_value_high
    if sde_base_multiple is not None:
        d["sde_base_multiple"] = sde_base_multiple
    if sde_applied_multiple is not None:
        d["sde_applied_multiple"] = sde_applied_multiple
    if sde_multiple_p25 is not None:
        d["sde_multiple_p25"] = sde_multiple_p25
    if sde_multiple_p75 is not None:
        d["sde_multiple_p75"] = sde_multiple_p75
    if equity_range_low is not None:
        d["equity_range_low"] = equity_range_low
    if equity_range_high is not None:
        d["equity_range_high"] = equity_range_high
    if owner_role:
        d["owner_role"] = owner_role
    if owner_concentration_tier:
        d["owner_concentration_tier"] = owner_concentration_tier
    if owner_concentration_adjustment is not None:
        d["owner_concentration_adjustment"] = owner_concentration_adjustment
    if size_discount_adjustment is not None:
        d["size_discount_adjustment"] = size_discount_adjustment
    if liquidity_discount_adjustment is not None:
        d["liquidity_discount_adjustment"] = liquidity_discount_adjustment
    if belgian_market_premium is not None:
        d["belgian_market_premium"] = belgian_market_premium
    if sde_calibration_steps is not None:
        d["sde_calibration_steps"] = sde_calibration_steps
    if sde_bridge is not None:
        d["sde_bridge"] = sde_bridge
    return d


# ---------------------------------------------------------------------------
# 5. Omzet (Revenue) Multiple
# ---------------------------------------------------------------------------


class OmzetMultipleDetails(TypedDict, total=False):
    enterprise_value: float
    enterprise_value_low: float
    enterprise_value_high: float
    reference_enterprise_value: float
    reference_multiple: float
    method_adjustment_factor: float
    revenue: float
    equity_range_low: float
    equity_range_high: float


def build_omzet_details(
    *,
    enterprise_value: float,
    revenue: float,
    enterprise_value_low: Optional[float] = None,
    enterprise_value_high: Optional[float] = None,
    equity_range_low: Optional[float] = None,
    equity_range_high: Optional[float] = None,
    reference_enterprise_value: Optional[float] = None,
    reference_multiple: Optional[float] = None,
    method_adjustment_factor: Optional[float] = None,
) -> OmzetMultipleDetails:
    d: OmzetMultipleDetails = {
        "enterprise_value": enterprise_value,
        "revenue": revenue,
    }
    if enterprise_value_low is not None:
        d["enterprise_value_low"] = enterprise_value_low
    if enterprise_value_high is not None:
        d["enterprise_value_high"] = enterprise_value_high
    if equity_range_low is not None:
        d["equity_range_low"] = equity_range_low
    if equity_range_high is not None:
        d["equity_range_high"] = equity_range_high
    if reference_enterprise_value is not None:
        d["reference_enterprise_value"] = reference_enterprise_value
    if reference_multiple is not None:
        d["reference_multiple"] = reference_multiple
    if method_adjustment_factor is not None:
        d["method_adjustment_factor"] = method_adjustment_factor
    return d


# ---------------------------------------------------------------------------
# 6. ARR Multiple (SaaS)
# ---------------------------------------------------------------------------


class ArrMultipleDetails(TypedDict, total=False):
    arr: float
    enterprise_value: float
    reference_enterprise_value: float
    reference_multiple: float
    method_adjustment_factor: float
    saas_metrics: Dict[str, object]
    saas_adjustment_breakdown: List[Dict[str, object]]
    eligibility: Dict[str, object]
    validation_flags: List[Dict[str, object]]
    recurring_share: float
    # Optional cap-table simulator payload — present when the caller
    # supplied a non-empty cap-table (prior round, SAFEs, option pool)
    # alongside an investment ask.  Same shape the startup_valuation
    # engine emits, so the React simulator + Jinja templates that
    # already render it for startup reports work unchanged for the
    # SaaS report.
    cap_table_simulator: Dict[str, object]


def build_arr_details(
    *,
    arr: float,
    enterprise_value: float,
    saas_metrics: Optional[Dict[str, object]] = None,
    saas_adjustment_breakdown: Optional[List[Dict[str, object]]] = None,
    eligibility: Optional[Dict[str, object]] = None,
    validation_flags: Optional[List[Dict[str, object]]] = None,
    recurring_share: Optional[float] = None,
    cap_table_simulator: Optional[Dict[str, object]] = None,
    reference_enterprise_value: Optional[float] = None,
    reference_multiple: Optional[float] = None,
    method_adjustment_factor: Optional[float] = None,
) -> ArrMultipleDetails:
    d: ArrMultipleDetails = {
        "arr": arr,
        "enterprise_value": enterprise_value,
    }
    if saas_metrics is not None:
        d["saas_metrics"] = saas_metrics
    if saas_adjustment_breakdown is not None:
        d["saas_adjustment_breakdown"] = saas_adjustment_breakdown
    if eligibility is not None:
        d["eligibility"] = eligibility
    if validation_flags:
        d["validation_flags"] = validation_flags
    if recurring_share is not None:
        d["recurring_share"] = recurring_share
    if cap_table_simulator is not None:
        d["cap_table_simulator"] = cap_table_simulator
    if reference_enterprise_value is not None:
        d["reference_enterprise_value"] = reference_enterprise_value
    if reference_multiple is not None:
        d["reference_multiple"] = reference_multiple
    if method_adjustment_factor is not None:
        d["method_adjustment_factor"] = method_adjustment_factor
    return d


# ---------------------------------------------------------------------------
# 7. Adjusted NAV
# ---------------------------------------------------------------------------


class AdjustedNavDetails(TypedDict, total=False):
    asset_based_evidence: bool
    net_asset_value: float
    net_asset_value_before_deductions: float
    tax_latency_deduction: float
    off_balance_deduction: float
    enterprise_value: float
    total_assets_book: float
    total_liabilities_book: float
    total_assets_adjusted: float
    total_liabilities_adjusted: float
    tangible_asset_value: float
    intangible_asset_value: float
    equity_range_low: float
    equity_range_high: float
    methodology: str
    confidence: str
    asset_adjustments: List[Dict[str, object]]
    warnings: List[str]
    manual_nav_adjustments: Dict[str, object]


# NAV details are built by asset_based_support.calculate_adjusted_nav_payload,
# not by omni_calc_coordinator directly. No builder here — the schema
# documents the contract for downstream consumers.


# ---------------------------------------------------------------------------
# 8. Fiscal 4x (BE only)
# ---------------------------------------------------------------------------


class Fiscal4xDetails(TypedDict):
    book_equity: float
    fiscal_anchor: float
    description: str


def build_fiscal_4x_details(
    *,
    book_equity: float,
    fiscal_anchor: float,
    description: str,
) -> Fiscal4xDetails:
    return {
        "book_equity": book_equity,
        "fiscal_anchor": fiscal_anchor,
        "description": description,
    }


# ---------------------------------------------------------------------------
# Union type for type-checking downstream consumers
# ---------------------------------------------------------------------------

MethodDetails = Union[
    AdaptiveDetails,
    EbitdaMultipleDetails,
    DcfDetails,
    SdeMultipleDetails,
    OmzetMultipleDetails,
    ArrMultipleDetails,
    AdjustedNavDetails,
    Fiscal4xDetails,
    LiquidationAnalysisDetails,
]
