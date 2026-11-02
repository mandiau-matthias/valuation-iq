"""Input extraction for OmniCalc comprehensive-response enrichment."""

import types
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Optional

from src.api.routes.valuation.orchestration.executors.comprehensive.omni_methodology_context import (
    _resolve_omni_execution_context,
)
from src.api.schemas import ValuationRequest, ValuationResponse
from src.services.reports.fiscal_ebitda_reference import fiscal_reported_ebitda
from src.utils.adaptive_input_helpers import get_percent_override
from src.utils.decimal_helpers import to_decimal


def _read(value: object, key: str) -> object:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _multiples_step_results(response: ValuationResponse) -> dict[object, object]:
    detailed_results = getattr(response, "detailed_results", None) or {}
    multiples_payload = (
        detailed_results.get("multiples_valuation", {})
        if isinstance(detailed_results, dict)
        else {}
    )
    step_results = (
        multiples_payload.get("_step_results", {}) if isinstance(multiples_payload, dict) else {}
    )
    return step_results if isinstance(step_results, dict) else {}


def _step_output(step_results: dict[object, object], step: int) -> object:
    return step_results.get(step) or step_results.get(float(step)) or step_results.get(str(step))


def _step_result(step_results: dict[object, object], step: int) -> object:
    step_output = _step_output(step_results, step)
    return _read(step_output, "result") if step_output is not None else None


def _pipeline_ebitda(raw_current_ebitda: float, step_results: dict[object, object]) -> float:
    step_1_result = _step_result(step_results, 1)
    pipeline_ebitda_raw = _read(step_1_result, "ebitda") if step_1_result is not None else None
    return float(pipeline_ebitda_raw) if pipeline_ebitda_raw is not None else raw_current_ebitda


def _request_ev_ebitda_multiple(request: ValuationRequest) -> float:
    raw = getattr(request, "ev_ebitda_multiple", None) or {}
    return float(raw.get("median", 0)) if isinstance(raw, dict) else 0.0


def _pipeline_final_multiple(
    response: ValuationResponse, step_results: dict[object, object]
) -> object:
    pipeline = getattr(response, "multiple_pipeline", None)
    if pipeline is None:
        step_11_result = _step_result(step_results, 11)
        pipeline = (
            _read(step_11_result, "multiple_pipeline") if step_11_result is not None else None
        )
    final_multiple = _read(pipeline, "final_multiple")
    return final_multiple if final_multiple is not None else _read(pipeline, "final_multiple_mid")


@dataclass(frozen=True)
class _MultiplesInputs:
    ebitda: float
    ev_ebitda_multiple: float
    adaptive_multiple_used: float
    p25_multiple: float
    p75_multiple: float
    total_adjustment: float


def _multiples_inputs(
    request: ValuationRequest,
    response: ValuationResponse,
    raw_current_ebitda: float,
    step_results: dict[object, object],
) -> _MultiplesInputs:
    mv = response.multiples_valuation
    ev_ebitda_multiple = (
        float(mv.ebitda_multiple) if mv and mv.ebitda_multiple is not None else None
    )
    adaptive_multiple_used = ev_ebitda_multiple
    pipeline_multiple = _pipeline_final_multiple(response, step_results)
    if pipeline_multiple is not None:
        adaptive_multiple_used = float(pipeline_multiple)

    if ev_ebitda_multiple is None:
        ev_ebitda_multiple = _request_ev_ebitda_multiple(request)
    if adaptive_multiple_used is None:
        adaptive_multiple_used = ev_ebitda_multiple

    p25_multiple = (
        float(mv.p25_ebitda_multiple)
        if mv and mv.p25_ebitda_multiple is not None
        else (ev_ebitda_multiple * 0.8 if ev_ebitda_multiple else 0.0)
    )
    p75_multiple = (
        float(mv.p75_ebitda_multiple)
        if mv and mv.p75_ebitda_multiple is not None
        else (ev_ebitda_multiple * 1.2 if ev_ebitda_multiple else 0.0)
    )

    return _MultiplesInputs(
        ebitda=_pipeline_ebitda(raw_current_ebitda, step_results),
        ev_ebitda_multiple=ev_ebitda_multiple,
        adaptive_multiple_used=adaptive_multiple_used,
        p25_multiple=p25_multiple,
        p75_multiple=p75_multiple,
        total_adjustment=_total_adjustment(mv),
    )


def _total_adjustment(mv: object) -> float:
    if not mv:
        return 0.0
    size_disc = abs(float(mv.size_discount or 0))
    liq_disc = abs(float(mv.liquidity_discount or 0))
    owner_dep_adj = abs(float(getattr(mv, "owner_dependency_adjustment", 0) or 0))
    country_adj = abs(float(mv.country_adjustment or 0))
    computed = size_disc + liq_disc + owner_dep_adj + country_adj
    total_adj = computed if computed > 0 else abs(float(mv.total_adjustment or 0))
    return min(total_adj, 0.95)


def _balance_sheet(cyd: object) -> dict[str, object]:
    return {
        "total_assets": getattr(cyd, "total_assets", None),
        "current_assets": getattr(cyd, "current_assets", None),
        "cash": getattr(cyd, "cash", None),
        "accounts_receivable": getattr(cyd, "accounts_receivable", None),
        "inventory": getattr(cyd, "inventory", None),
        "total_liabilities": getattr(cyd, "total_liabilities", None),
        "current_liabilities": getattr(cyd, "current_liabilities", None),
        "total_debt": getattr(cyd, "total_debt", None),
        "total_equity": getattr(cyd, "total_equity", None),
    }


def _dcf_results(response: ValuationResponse) -> Optional[dict[str, object]]:
    dcf_resp = response.dcf_valuation
    if not dcf_resp:
        return None
    return {
        "enterprise_value": float(dcf_resp.enterprise_value),
        "wacc": float(dcf_resp.wacc),
        "terminal_value": float(dcf_resp.terminal_value),
        "terminal_growth_rate": float(dcf_resp.terminal_growth_rate),
        "terminal_value_methodology": dcf_resp.terminal_value_methodology,
        "terminal_exit_multiple": (
            float(dcf_resp.terminal_exit_multiple)
            if dcf_resp.terminal_exit_multiple is not None
            else None
        ),
        "cost_of_equity": float(dcf_resp.cost_of_equity),
        "sensitivity_matrix_2d": dcf_resp.sensitivity_matrix_2d,
    }


def _revenue_calibration(request: ValuationRequest) -> types.SimpleNamespace:
    raw_ev_rev = getattr(request, "ev_revenue_multiple", None) or {}
    return types.SimpleNamespace(
        ev_revenue_median=(
            Decimal(str(raw_ev_rev.get("median", 0)))
            if isinstance(raw_ev_rev, dict) and raw_ev_rev.get("median")
            else None
        ),
        ev_revenue_p25=(
            Decimal(str(raw_ev_rev.get("p25", 0)))
            if isinstance(raw_ev_rev, dict) and raw_ev_rev.get("p25")
            else None
        ),
        ev_revenue_p75=(
            Decimal(str(raw_ev_rev.get("p75", 0)))
            if isinstance(raw_ev_rev, dict) and raw_ev_rev.get("p75")
            else None
        ),
        business_type_id=getattr(request, "business_type_id", None),
        category_id=getattr(request, "category_id", None),
    )


def _revenue_growth(request: ValuationRequest, revenue: float) -> float:
    growth = 0.0
    hist = getattr(request, "historical_years_data", None) or []
    if hist:
        sorted_hist = sorted(hist, key=lambda y: getattr(y, "year", 0))
        prior_rev = float(sorted_hist[-1].revenue) if hasattr(sorted_hist[-1], "revenue") else 0
        if prior_rev > 0:
            growth = (revenue - prior_rev) / prior_rev
    manual_revenue_growth = get_percent_override(request, "dcf_revenue_growth_pct")
    return float(manual_revenue_growth) if manual_revenue_growth is not None else growth


def _ownership_multiplier(
    request: ValuationRequest,
    step_results: dict[object, object],
) -> Decimal:
    multiplier = Decimal("1")
    shares = getattr(request, "shares_for_sale", None)
    if shares is not None:
        shares_decimal = to_decimal(shares)
        if shares_decimal < Decimal("100"):
            multiplier = shares_decimal / Decimal("100")

    step_8_result = _step_result(step_results, 8)
    if step_8_result is None:
        return multiplier

    step_8_multiplier = _read(step_8_result, "ownership_multiplier")
    step_8_adjustment_factor = _read(step_8_result, "adjustment_factor")
    if step_8_multiplier is None or step_8_adjustment_factor is None:
        return multiplier
    return to_decimal(step_8_multiplier) * to_decimal(step_8_adjustment_factor)


def _saas_analysis(step_results: dict[object, object]) -> Optional[dict[str, object]]:
    step_0_result = _step_result(step_results, 0)
    sub_calculations = (
        step_0_result.get("sub_calculations")
        if isinstance(step_0_result, dict)
        and isinstance(step_0_result.get("sub_calculations"), dict)
        else {}
    )
    saas = sub_calculations.get("saas_analysis")
    return saas if isinstance(saas, dict) else None


def _nwc_adjustment(response: ValuationResponse) -> float:
    nwc_norm = getattr(response, "nwc_normalization", None)
    if isinstance(nwc_norm, dict):
        return float(nwc_norm.get("surplus_deficit", 0) or 0)
    return 0.0


@dataclass(frozen=True)
class OmniCalculationInputs:
    ebitda: float
    revenue: float
    ev_ebitda_multiple: float
    adaptive_multiple_used: float
    p25_multiple: float
    p75_multiple: float
    total_adjustment: float
    total_debt: float
    cash: float
    equity_value_mid: Decimal
    dcf_results: Optional[dict[str, object]]
    dcf_exclusion_reason: Optional[str]
    calibration: types.SimpleNamespace
    revenue_growth: float
    owner_dependency: object
    industry: object
    recurring_revenue_percentage: object
    equity_value_low: Decimal
    equity_value_high: Decimal
    ownership_multiplier: Decimal
    country_code: object
    company_name: object
    business_model: str
    founding_year: object
    reporting_year: object
    balance_sheet: dict[str, object]
    business_context: object
    business_type_id: object
    primary_basis: Literal["hybrid", "asset_based"]
    saas_analysis: Optional[dict[str, object]]
    owner_salary_addback: object
    methodology_justification: object
    fiscal_ebitda: float
    nwc_adjustment: float
    startup_inputs: object
    lifecycle_stage_triage: object
    liquidation_inputs: object
    executed_methodology_token: str

    def as_calculate_all_methods_kwargs(self) -> dict[str, object]:
        return {
            "ebitda": self.ebitda,
            "revenue": self.revenue,
            "ev_ebitda_multiple": self.ev_ebitda_multiple,
            "adaptive_multiple_used": self.adaptive_multiple_used,
            "p25_multiple": self.p25_multiple,
            "p75_multiple": self.p75_multiple,
            "total_adjustment": self.total_adjustment,
            "total_debt": self.total_debt,
            "cash": self.cash,
            "equity_value_mid": self.equity_value_mid,
            "dcf_results": self.dcf_results,
            "dcf_exclusion_reason": self.dcf_exclusion_reason,
            "calibration": self.calibration,
            "revenue_growth": self.revenue_growth,
            "owner_dependency": self.owner_dependency,
            "industry": self.industry,
            "recurring_revenue_percentage": self.recurring_revenue_percentage,
            "equity_value_low": self.equity_value_low,
            "equity_value_high": self.equity_value_high,
            "ownership_multiplier": self.ownership_multiplier,
            "country_code": self.country_code,
            "company_name": self.company_name,
            "business_model": self.business_model,
            "founding_year": self.founding_year,
            "reporting_year": self.reporting_year,
            "balance_sheet": self.balance_sheet,
            "business_context": self.business_context,
            "business_type_id": self.business_type_id,
            "primary_basis": self.primary_basis,
            "saas_analysis": self.saas_analysis,
            "owner_salary_addback": self.owner_salary_addback,
            "methodology_justification": self.methodology_justification,
            "fiscal_ebitda": self.fiscal_ebitda,
            "nwc_adjustment": self.nwc_adjustment,
            "startup_inputs": self.startup_inputs,
            "lifecycle_stage_triage": self.lifecycle_stage_triage,
            "liquidation_inputs": self.liquidation_inputs,
        }


def build_omni_calculation_inputs(
    request: ValuationRequest,
    response: ValuationResponse,
    *,
    equity_value_low: Decimal,
    equity_value_mid: Decimal,
    equity_value_high: Decimal,
    dcf_exclusion_reason: Optional[str],
    methodology: Optional[object],
    logger: object,
) -> OmniCalculationInputs:
    """Build the canonical input object handed to ``calculate_all_methods``."""
    cyd = request.current_year_data
    raw_current_ebitda = float(cyd.ebitda)
    statutory_ebitda = fiscal_reported_ebitda(request)
    revenue = float(cyd.revenue)
    step_results = _multiples_step_results(response)
    multiples = _multiples_inputs(request, response, raw_current_ebitda, step_results)
    omni_execution = _resolve_omni_execution_context(methodology)
    ownership_multiplier = _ownership_multiplier(request, step_results)

    dbg = getattr(logger, "debug", None)
    if callable(dbg):
        dbg(
            "[OmniCalc] primary_basis=%s from executed methodology=%r normalized=%s ownership_multiplier=%s",
            omni_execution.primary_basis,
            methodology,
            omni_execution.executed_methodology_token or "<empty>",
            ownership_multiplier,
        )

    return OmniCalculationInputs(
        ebitda=multiples.ebitda,
        revenue=revenue,
        ev_ebitda_multiple=multiples.ev_ebitda_multiple,
        adaptive_multiple_used=multiples.adaptive_multiple_used,
        p25_multiple=multiples.p25_multiple,
        p75_multiple=multiples.p75_multiple,
        total_adjustment=multiples.total_adjustment,
        total_debt=float(cyd.total_debt or 0),
        cash=float(cyd.cash or 0),
        equity_value_mid=equity_value_mid,
        dcf_results=_dcf_results(response),
        dcf_exclusion_reason=dcf_exclusion_reason,
        calibration=_revenue_calibration(request),
        revenue_growth=_revenue_growth(request, revenue),
        owner_dependency=getattr(request, "owner_dependency", None),
        industry=getattr(request, "industry", ""),
        recurring_revenue_percentage=getattr(request, "recurring_revenue_percentage", None),
        equity_value_low=equity_value_low,
        equity_value_high=equity_value_high,
        ownership_multiplier=ownership_multiplier,
        country_code=getattr(request, "country_code", "BE"),
        company_name=getattr(request, "company_name", "Unknown Company"),
        business_model=str(getattr(request, "business_model", "other") or "other"),
        founding_year=getattr(request, "founding_year", None),
        reporting_year=getattr(cyd, "year", None),
        balance_sheet=_balance_sheet(cyd),
        business_context=getattr(request, "business_context", None),
        business_type_id=getattr(request, "business_type_id", None),
        primary_basis=omni_execution.primary_basis,
        saas_analysis=_saas_analysis(step_results),
        owner_salary_addback=getattr(request, "owner_salary_addback", None),
        methodology_justification=getattr(response, "methodology_downgrade_reason", None),
        fiscal_ebitda=float(statutory_ebitda) if statutory_ebitda is not None else raw_current_ebitda,
        nwc_adjustment=_nwc_adjustment(response),
        startup_inputs=getattr(request, "startup_inputs", None),
        lifecycle_stage_triage=getattr(request, "lifecycle_stage_triage", None),
        liquidation_inputs=getattr(request, "liquidation_inputs", None),
        executed_methodology_token=omni_execution.executed_methodology_token,
    )
