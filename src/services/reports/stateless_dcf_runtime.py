"""Runtime helpers for the stateless DCF adapter."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Optional, Protocol

from src.api.schemas.stateless_api import CalculateRequest
from src.utils.adaptive_input_helpers import get_customer_concentration_override
from src.utils.decimal_helpers import safe_float, to_decimal


class LoggerLike(Protocol):
    def warning(self, msg: str, *args: object, **kwargs: object) -> object: ...


def resolve_stateless_size_premium(
    request: CalculateRequest,
    dcf_request: SimpleNamespace,
    *,
    logger: LoggerLike,
) -> tuple[Decimal, str]:
    if request.wacc_evidence_contract is not None:
        # ``direct_sector_wacc`` is a complete observed discount rate and its
        # contract explicitly confirms the source already contains a size
        # premium. Returning zero here prevents the core engine from pricing a
        # second SME premium before the direct WACC override is applied.
        return Decimal("0"), "direct_sector_wacc:included_in_observed_rate"

    from src.api.routes.valuation.calculators.dcf_size_premium_resolver import (
        resolve_size_premium_for_dcf_engine,
    )

    revenue_for_size = to_decimal(request.current_year.revenue or 0)
    sme_for_size = getattr(dcf_request, "sme_calibration", None)
    if not isinstance(sme_for_size, dict) or not sme_for_size:
        sme_for_size = getattr(request, "sme_calibration", None)

    return resolve_size_premium_for_dcf_engine(
        revenue=revenue_for_size,
        sme_calibration=sme_for_size if isinstance(sme_for_size, dict) else None,
        logger=logger,
    )


def _public_run_uses_modeled_capital_structure(request: CalculateRequest) -> bool:
    """True when Public Adaptive's signed resolution declared the 70/30 default.

    Imported lazily: public_adaptive_profile imports from this module, so a
    top-level import would close a cycle.
    """
    from src.services.reports.public_adaptive_profile import (
        _has_complete_public_wacc_capital_structure,
        public_modeled_dcf_is_authorized,
    )

    if not public_modeled_dcf_is_authorized(request):
        return False
    metadata = getattr(request, "metadata", None) or {}
    return not _has_complete_public_wacc_capital_structure(metadata, request.current_year.year)


def run_stateless_dcf_engine(
    request: CalculateRequest,
    *,
    dcf_request: SimpleNamespace,
    mid_year_discounting: bool,
    size_premium: Decimal,
    has_audit: bool | None,
    owner_dependency_score: Decimal | None,
) -> tuple[object, dict[str, object]]:
    from src.api.routes.valuation.calculators.dcf_data_adapter import DCFDataAdapter
    from src.domain.dcf_engine import DCFValuationEngineRefactored
    from src.domain.dcf_types import DCFConfiguration

    adapter = DCFDataAdapter()
    financial_data = adapter.create_financial_data(dcf_request)
    market_context, market_context_metadata = adapter.create_market_context(dcf_request)
    industry_benchmarks = adapter.create_industry_benchmarks(dcf_request)
    explicit_projection_years = len(getattr(dcf_request, "forecast_years_data", []) or [])

    dcf_result = DCFValuationEngineRefactored(
        financial_data=financial_data,
        market_context=market_context,
        industry_benchmarks=industry_benchmarks,
        config=DCFConfiguration(mid_year_discounting=mid_year_discounting),
        transparency_collector=None,
        size_premium=size_premium,
        customer_concentration=get_customer_concentration_override(dcf_request),
        industry=request.industry,
        has_audit=has_audit,
        owner_dependency_score=owner_dependency_score,
        # Public Adaptive declares its capital structure in the signed modeled-DCF
        # resolution BEFORE this runs, using
        # `_has_complete_public_wacc_capital_structure`. If the calculator then
        # infers a different structure the audit's policy and evidence describe
        # different things and `_modeled_dcf_wacc_reconciles` fails closed.
        # Decide once, from the same predicate on the same inputs: pin the
        # calculator to the disclosed 70/30 default exactly when the policy
        # declared it, and leave the observed path alone otherwise.
        force_modeled_capital_structure=_public_run_uses_modeled_capital_structure(request),
    ).calculate_dcf_valuation(
        projection_years=explicit_projection_years or request.projection_years,
        sensitivity_analysis=True,
    )
    return dcf_result, market_context_metadata


def apply_stateless_result_overrides(
    request: CalculateRequest,
    *,
    dcf_result: object,
    mid_year_discounting: bool,
    override_fn,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, list[Decimal], str, Decimal | None]:
    return override_fn(
        request,
        enterprise_value=to_decimal(dcf_result.enterprise_value),
        wacc=to_decimal(dcf_result.wacc),
        terminal_growth_rate=to_decimal(dcf_result.terminal_growth_rate),
        terminal_value=to_decimal(dcf_result.terminal_value),
        pv_terminal_value=to_decimal(dcf_result.pv_terminal_value),
        cash_flow_projections=[to_decimal(value) for value in dcf_result.fcf_projections],
        mid_year_discounting=mid_year_discounting,
    )


def stateless_apv_bridge(
    dcf_request: SimpleNamespace,
    *,
    enterprise_value: Decimal,
    wacc: Decimal,
    mid_year_discounting: bool,
) -> dict[str, object] | None:
    from src.api.routes.valuation.calculators.dcf_apv_bridge import calculate_apv_tax_shield_bridge

    return calculate_apv_tax_shield_bridge(
        dcf_request,
        enterprise_value=enterprise_value,
        equity_value=None,
        discount_rate=to_decimal(wacc),
        mid_year_discounting=mid_year_discounting,
    )


def apv_adjusted_enterprise_value(
    enterprise_value: Decimal,
    apv_bridge: dict[str, object] | None,
) -> Decimal:
    if apv_bridge is None:
        return enterprise_value
    return to_decimal(apv_bridge["apv_enterprise_value"])


def terminal_ebitda_from_dcf_request(dcf_request: SimpleNamespace) -> Decimal | None:
    explicit_forecast_years = getattr(dcf_request, "forecast_years_data", None) or []
    if explicit_forecast_years:
        terminal_forecast = max(
            explicit_forecast_years,
            key=lambda year_data: getattr(year_data, "year", 0),
        )
        last_forecast_ebitda = getattr(terminal_forecast, "ebitda", None)
        return to_decimal(last_forecast_ebitda) if last_forecast_ebitda is not None else None

    current_ebitda = getattr(getattr(dcf_request, "current_year_data", None), "ebitda", None)
    return to_decimal(current_ebitda) if current_ebitda is not None else None


def wacc_buildup_from_components(wc: object | None) -> dict[str, object] | None:
    if wc is None:
        return None
    erp_f = safe_float(wc.market_risk_premium)
    result = {
        "risk_free_rate": safe_float(wc.risk_free_rate),
        "market_risk_premium": erp_f,
        "equity_risk_premium": erp_f,
        "beta": safe_float(wc.beta),
        "size_premium": safe_float(wc.size_premium),
        "company_specific_risk": safe_float(wc.company_specific_risk),
        "cost_of_equity": safe_float(wc.cost_of_equity),
        "cost_of_debt": safe_float(wc.cost_of_debt),
        "tax_rate": safe_float(wc.tax_rate),
        "tax_shield": safe_float(wc.tax_shield),
        "equity_weight": safe_float(wc.equity_weight),
        "debt_weight": safe_float(wc.debt_weight),
    }
    evidence = getattr(wc, "evidence", None)
    if evidence is not None:
        result["wacc_evidence"] = {
            "capital_structure_source": evidence.capital_structure_source,
            "capital_structure_fallback": evidence.capital_structure_fallback,
            "fallback_reason": evidence.fallback_reason,
            "confidence": evidence.confidence,
            "warnings": list(evidence.warnings),
            "risk_free_rate_source": evidence.risk_free_rate_source,
            "market_risk_premium_source": evidence.market_risk_premium_source,
            "beta_source": evidence.beta_source,
            "cost_of_debt_source": evidence.cost_of_debt_source,
            "tax_rate_source": evidence.tax_rate_source,
        }
    return result


def aligned_wacc_buildup(
    wacc_buildup: dict[str, object] | None,
    *,
    has_manual_wacc_override: bool,
    wacc: Decimal,
) -> dict[str, object] | None:
    from src.api.routes.valuation.calculators.dcf_policy_context import (
        apply_manual_wacc_override_to_buildup,
    )

    if has_manual_wacc_override and wacc_buildup is not None:
        return apply_manual_wacc_override_to_buildup(wacc_buildup, to_decimal(wacc))
    return wacc_buildup


def direct_sector_wacc_buildup(
    contract: object,
    *,
    wacc: Decimal,
) -> dict[str, object]:
    """Present a direct WACC without fabricating a CAPM decomposition."""

    return {
        "mode": "direct_sector_wacc",
        "wacc": safe_float(wacc),
        "wacc_override_applied": True,
        "component_buildup_applicable": False,
        "risk_free_rate": None,
        "market_risk_premium": None,
        "equity_risk_premium": None,
        "beta": None,
        "size_premium": None,
        "company_specific_risk": None,
        "cost_of_equity": None,
        "cost_of_debt": None,
        "tax_rate": None,
        "tax_shield": None,
        "equity_weight": None,
        "debt_weight": None,
        "wacc_evidence_contract": contract.model_dump(mode="json"),
    }


def cost_of_equity_headline(
    dcf_result: object,
    *,
    has_manual_wacc_override: bool,
    wacc_buildup: dict[str, object] | None,
) -> Decimal:
    if has_manual_wacc_override and wacc_buildup is not None:
        coe_aligned = wacc_buildup.get("cost_of_equity")
        if coe_aligned is not None:
            return to_decimal(coe_aligned)
    return to_decimal(dcf_result.cost_of_equity)


def operating_enterprise_value(
    enterprise_value: Decimal,
    apv_bridge: dict[str, object] | None,
) -> Decimal:
    if apv_bridge is None:
        return enterprise_value
    return to_decimal(apv_bridge["dcf_enterprise_value_before_apv"])


def terminal_value_mix(
    *,
    operating_enterprise_value: Decimal,
    pv_terminal_value: Decimal,
) -> tuple[float, float]:
    total_ev_for_split = safe_float(operating_enterprise_value)
    total_pv_tv = safe_float(pv_terminal_value)
    tv_pct = (total_pv_tv / total_ev_for_split * 100) if total_ev_for_split > 0 else 0.0
    forecast_pct = 100.0 - tv_pct if total_ev_for_split > 0 else 0.0
    return tv_pct, forecast_pct


def projection_year_count(dcf_result: object) -> int:
    projections = getattr(dcf_result, "fcf_projections", None)
    return len(projections) if projections else 5


def ownership_multiplier(request: CalculateRequest) -> float:
    ownership_pct = (
        request.shares_for_sale if request.shares_for_sale is not None else Decimal("100")
    )
    return float(ownership_pct / Decimal("100"))


def stateless_equity_value_from_ev(
    request: CalculateRequest,
    *,
    enterprise_value: Decimal,
    ownership_multiplier: float,
) -> float:
    from src.domain.methods._shared import dcf_equity_from_ev
    from src.services.reports.stateless_completion_accounts import completion_account_bridge

    completion = completion_account_bridge(request)

    return dcf_equity_from_ev(
        enterprise_value,
        total_debt=completion.bridge_total_debt,
        cash=completion.bridge_cash,
        ownership_multiplier=ownership_multiplier,
        nwc_adjustment=0.0,
    )


def apply_apv_equity_bridge(
    apv_bridge: dict[str, object] | None,
    request: CalculateRequest,
    *,
    equity_after_ev_override: float,
    ownership_multiplier: float,
) -> None:
    if apv_bridge is None:
        return
    equity_before_apv = stateless_equity_value_from_ev(
        request,
        enterprise_value=to_decimal(apv_bridge["dcf_enterprise_value_before_apv"]),
        ownership_multiplier=ownership_multiplier,
    )
    apv_bridge["dcf_equity_value_before_apv"] = to_decimal(str(equity_before_apv))
    apv_bridge["apv_equity_value"] = to_decimal(str(equity_after_ev_override))


def market_assumptions_with_size_premium_source(
    market_context_metadata: dict[str, object],
    size_premium_source: str,
    *,
    tax_provenance: dict[str, object] | None = None,
) -> dict[str, object]:
    market_assumptions: dict[str, object] = dict(market_context_metadata)
    market_assumptions["dcf_size_premium_source"] = size_premium_source
    if tax_provenance is not None:
        market_assumptions["tax_rate_provenance"] = tax_provenance
    return market_assumptions


def stateless_dcf_result_payload(
    *,
    enterprise_value: Decimal,
    equity_after_ev_override: float,
    market_assumptions: dict[str, object],
    dcf_result: object,
    wc: object | None,
    wacc: Decimal,
    cost_of_equity_headline: Decimal,
    terminal_growth_rate: Decimal,
    terminal_value: Decimal,
    terminal_value_methodology: str,
    terminal_exit_multiple: Decimal | None,
    pv_terminal_value: Decimal,
    tv_pct: float,
    forecast_pct: float,
    proj_years: int,
    mid_year_discounting: bool,
    pv_fcf_projections: list[Decimal],
    sensitivity_wacc: dict[str, object],
    sensitivity_growth: dict[str, object],
    sensitivity_matrix_2d: Optional[dict[str, object]],
    wacc_buildup: dict[str, object] | None,
    apv_bridge: dict[str, object] | None,
) -> dict[str, object]:
    # Once advisor CAPM/capital-structure inputs have been overlaid, every
    # public DCF component must come from that aligned buildup. Publishing the
    # engine's pre-override debt cost or weights beside an overridden WACC makes
    # the disclosed formula impossible to reconcile even when the valuation
    # arithmetic itself is correct.
    aligned_cost_of_debt = (
        wacc_buildup.get("cost_of_debt")
        if wacc_buildup is not None and wacc_buildup.get("cost_of_debt") is not None
        else dcf_result.cost_of_debt
    )
    aligned_equity_weight = (
        wacc_buildup.get("equity_weight")
        if wacc_buildup is not None and wacc_buildup.get("equity_weight") is not None
        else (float(wc.equity_weight) if wc else None)
    )
    aligned_debt_weight = (
        wacc_buildup.get("debt_weight")
        if wacc_buildup is not None and wacc_buildup.get("debt_weight") is not None
        else (float(wc.debt_weight) if wc else None)
    )
    result = {
        "calculation_contract_version": "dcf_calculation.v2",
        "enterprise_value": enterprise_value,
        "equity_value": equity_after_ev_override,
        "market_assumptions": market_assumptions,
        "engine_wacc": to_decimal(dcf_result.wacc),
        "engine_cost_of_equity": to_decimal(dcf_result.cost_of_equity),
        "wacc": wacc,
        "cost_of_equity": cost_of_equity_headline,
        "cost_of_debt": aligned_cost_of_debt,
        "equity_weight": aligned_equity_weight,
        "debt_weight": aligned_debt_weight,
        "terminal_growth_rate": terminal_growth_rate,
        "terminal_value": terminal_value,
        "terminal_value_methodology": terminal_value_methodology,
        "terminal_exit_multiple": terminal_exit_multiple,
        "pv_terminal_value": pv_terminal_value,
        "terminal_value_pct_of_total": round(tv_pct, 1),
        "explicit_forecast_pct_of_total": round(forecast_pct, 1),
        "projection_years": proj_years,
        "mid_year_discounting": mid_year_discounting,
        "fcf_projections_5y": dcf_result.fcf_projections[:5],
        "pv_fcf_projections_5y": pv_fcf_projections[:5],
        "fcf_projections": list(dcf_result.fcf_projections),
        "pv_fcf_projections": list(pv_fcf_projections),
        "fcf_projection_detail": getattr(dcf_result, "projection_detail", None),
        "sensitivity_wacc": sensitivity_wacc,
        "sensitivity_growth": sensitivity_growth,
        "sensitivity_matrix_2d": sensitivity_matrix_2d,
        "wacc_buildup": wacc_buildup,
        "confidence": dcf_result.confidence,
        "confidence_score": dcf_result.confidence_score,
        "confidence_factors": dcf_result.confidence_factors,
        "historical_fcf_readiness": getattr(dcf_result, "historical_fcf_readiness", None),
    }
    if isinstance(wacc_buildup, dict) and wacc_buildup.get("mode") == "direct_sector_wacc":
        # Pre-override engine rates are diagnostic implementation details. A
        # direct-sector contract is the sole client-visible WACC authority.
        result.pop("engine_wacc", None)
        result.pop("engine_cost_of_equity", None)
    if apv_bridge is not None:
        result.update(apv_bridge)
    return result
