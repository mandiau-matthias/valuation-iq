"""DCF calculation adapter for the stateless valuation route."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Optional

from src.api.routes.valuation.calculators.dcf_apv_sensitivity import (
    apply_apv_advisor_range,
    apply_apv_sensitivity_basis,
)
from src.api.routes.valuation.calculators.dcf_policy_context import (
    overlay_user_capm_on_wacc_buildup,
)
from src.api.routes.valuation.calculators.dcf_tax_rate_provenance import build_tax_rate_provenance
from src.api.schemas.stateless_api import CalculateRequest
from src.domain.asset_based_support import normalize_business_model
from src.domain.dcf.manual_assumption_validation import (
    require_override_cash_flows,
    require_positive_discount_rate,
    require_valid_gordon_growth,
)
from src.services.reports.public_adaptive_profile import public_modeled_dcf_is_authorized
from src.services.reports.stateless_earnings_basis import with_normalized_actual_earnings
from src.utils.adaptive_input_helpers import (
    get_business_context,
    get_dcf_exit_multiple_override,
    get_dcf_mid_year_discounting,
    get_effective_dcf_wacc_override,
    get_percent_override,
)
from src.utils.decimal_helpers import to_decimal
from src.utils.logging import get_logger

from .stateless_dcf_forecast import _current_capex_ratio as _current_capex_ratio
from .stateless_dcf_forecast import (
    _generate_stateless_dcf_forecast_years as _generate_stateless_dcf_forecast_years,
)
from .stateless_dcf_forecast import (
    _project_stateless_forecast_year as _project_stateless_forecast_year,
)
from .stateless_dcf_forecast import _ratio_to_revenue as _ratio_to_revenue
from .stateless_dcf_forecast import (
    _repair_stateless_legacy_forecast_nwc_changes as _repair_stateless_legacy_forecast_nwc_changes,
)
from .stateless_dcf_forecast import (
    _split_stateless_forecast_years as _split_stateless_forecast_years,
)
from .stateless_dcf_forecast import (
    _stateless_forecast_assumptions as _stateless_forecast_assumptions,
)
from .stateless_dcf_forecast import _stateless_forecast_overrides as _stateless_forecast_overrides
from .stateless_dcf_forecast import _StatelessForecastAssumptions as _StatelessForecastAssumptions
from .stateless_dcf_forecast import _StatelessForecastOverrides as _StatelessForecastOverrides
from .stateless_dcf_forecast import (
    stateless_dcf_forecast_years_for_timeline as stateless_dcf_forecast_years_for_timeline,
)
from .stateless_dcf_runtime import (
    aligned_wacc_buildup,
    apply_apv_equity_bridge,
    apply_stateless_result_overrides,
    apv_adjusted_enterprise_value,
)
from .stateless_dcf_runtime import cost_of_equity_headline as build_cost_of_equity_headline
from .stateless_dcf_runtime import (
    direct_sector_wacc_buildup,
    market_assumptions_with_size_premium_source,
    operating_enterprise_value,
    ownership_multiplier,
    projection_year_count,
    resolve_stateless_size_premium,
    run_stateless_dcf_engine,
    stateless_apv_bridge,
    stateless_dcf_result_payload,
    stateless_equity_value_from_ev,
    terminal_ebitda_from_dcf_request,
    terminal_value_mix,
    wacc_buildup_from_components,
)
from .stateless_dcf_sensitivity import (
    _build_advisor_dcf_sensitivity as _build_advisor_dcf_sensitivity,
)
from .stateless_dcf_sensitivity import (
    _discounted_fcff_enterprise_value as _discounted_fcff_enterprise_value,
)
from .stateless_dcf_sensitivity import _margin_fcff_from_forecasts as _margin_fcff_from_forecasts
from .stateless_dcf_sensitivity import resolve_advisor_dcf_sensitivity

logger = get_logger(__name__)


def _economic_snapshot_commits_risk_free_rate(economic_context: dict[str, object]) -> bool:
    """Whether the typed context carries a complete canonical snapshot claim.

    Hash verification and jurisdiction binding happen again in the market
    adapter.  This narrow check only decides whether the stateless shim should
    forward the committed rate as its explicit bond-yield input.
    """

    return bool(
        economic_context.get("schema_version") == "economic_snapshot.v1"
        and economic_context.get("snapshot_id")
        and economic_context.get("snapshot_hash")
        and economic_context.get("snapshot_issuer")
        and economic_context.get("risk_free_rate_observed_at")
        and economic_context.get("equity_risk_premium_observed_at")
        and economic_context.get("growth_rates_observed_at")
        and economic_context.get("source_references")
    )


def calculate_stateless_dcf(request: CalculateRequest) -> dict[str, object]:
    if isinstance(request, CalculateRequest) and public_modeled_dcf_is_authorized(request):
        from .public_adaptive_profile import apply_public_adaptive_profile
        from .forecast_output_policy import label_forecast_output

        # Revalidate the attested producer before admitting its disclosed scenario.
        profiled = apply_public_adaptive_profile(request)
        if public_modeled_dcf_is_authorized(profiled):
            return label_forecast_output(_calculate_stateless_dcf_diagnostic(profiled), None)
    from .forecast_admission import require_verified_forecast

    forecast = require_verified_forecast(request)
    payload = _calculate_stateless_dcf_diagnostic(request)
    from .verified_forecast_projection import apply_verified_forecast_projection

    return apply_verified_forecast_projection(payload, forecast)


def _calculate_stateless_dcf_diagnostic(request: CalculateRequest) -> dict[str, object]:
    """DCF arithmetic shared by indicative and source-verified estimates."""
    dcf_request = _build_stateless_dcf_request(request)
    mid_year_discounting = get_dcf_mid_year_discounting(dcf_request)
    size_premium, size_premium_source = resolve_stateless_size_premium(
        request,
        dcf_request,
        logger=logger,
    )
    dcf_result, market_context_metadata = run_stateless_dcf_engine(
        request,
        dcf_request=dcf_request,
        mid_year_discounting=mid_year_discounting,
        size_premium=size_premium,
        has_audit=_extract_stateless_has_audit(request),
        # Transferability risk is priced exactly once in the governed equity
        # waterfall; legacy chat scores cannot silently lift WACC.
        owner_dependency_score=None,
    )

    (
        enterprise_value,
        wacc,
        terminal_growth_rate,
        terminal_value,
        pv_terminal_value,
        pv_fcf_projections,
        terminal_value_methodology,
        terminal_exit_multiple,
    ) = apply_stateless_result_overrides(
        request,
        dcf_result=dcf_result,
        mid_year_discounting=mid_year_discounting,
        override_fn=_apply_stateless_dcf_overrides,
    )
    apv_bridge = stateless_apv_bridge(
        dcf_request,
        enterprise_value=enterprise_value,
        wacc=wacc,
        mid_year_discounting=mid_year_discounting,
    )
    enterprise_value = apv_adjusted_enterprise_value(enterprise_value, apv_bridge)

    terminal_ebitda = terminal_ebitda_from_dcf_request(dcf_request)
    sensitivity_wacc, sensitivity_growth, sensitivity_matrix_2d = (
        _finalize_stateless_dcf_sensitivities(
            dcf_result=dcf_result,
            fcf_values=[to_decimal(value) for value in dcf_result.fcf_projections],
            wacc=to_decimal(wacc),
            terminal_growth_rate=to_decimal(terminal_growth_rate),
            terminal_value=to_decimal(terminal_value),
            terminal_value_methodology=terminal_value_methodology,
            terminal_exit_multiple=terminal_exit_multiple,
            terminal_ebitda=terminal_ebitda,
            mid_year_discounting=mid_year_discounting,
        )
    )

    wc = getattr(dcf_result, "wacc_components", None)
    wacc_buildup = wacc_buildup_from_components(wc)
    wacc_buildup = overlay_user_capm_on_wacc_buildup(wacc_buildup, request)
    has_manual_wacc_override = get_effective_dcf_wacc_override(request) is not None
    wacc_buildup = aligned_wacc_buildup(
        wacc_buildup,
        has_manual_wacc_override=has_manual_wacc_override,
        wacc=wacc,
    )
    if request.wacc_evidence_contract is not None:
        wacc_buildup = direct_sector_wacc_buildup(
            request.wacc_evidence_contract,
            wacc=to_decimal(wacc),
        )
    cost_of_equity_headline = build_cost_of_equity_headline(
        dcf_result,
        has_manual_wacc_override=has_manual_wacc_override,
        wacc_buildup=wacc_buildup,
    )

    tv_pct, forecast_pct = terminal_value_mix(
        operating_enterprise_value=operating_enterprise_value(enterprise_value, apv_bridge),
        pv_terminal_value=pv_terminal_value,
    )
    ownership_multiplier_value = ownership_multiplier(request)
    equity_after_ev_override = stateless_equity_value_from_ev(
        request,
        enterprise_value=enterprise_value,
        ownership_multiplier=ownership_multiplier_value,
    )
    apply_apv_equity_bridge(
        apv_bridge,
        request,
        equity_after_ev_override=equity_after_ev_override,
        ownership_multiplier=ownership_multiplier_value,
    )

    advisor_sensitivity, advisor_range_exclusion = resolve_advisor_dcf_sensitivity(
        request,
        wacc=to_decimal(wacc),
        terminal_growth_rate=to_decimal(terminal_growth_rate),
        mid_year_discounting=mid_year_discounting,
        terminal_value_methodology=terminal_value_methodology,
        operating_enterprise_value=operating_enterprise_value(enterprise_value, apv_bridge),
    )
    if advisor_sensitivity is not None:
        sensitivity_wacc = advisor_sensitivity["sensitivity_wacc"]
        sensitivity_growth = advisor_sensitivity["sensitivity_growth"]
        sensitivity_matrix_2d = advisor_sensitivity["sensitivity_matrix_2d"]

    sensitivity_wacc, sensitivity_growth, sensitivity_matrix_2d = apply_apv_sensitivity_basis(
        apv_bridge,
        sensitivity_wacc,
        sensitivity_growth,
        sensitivity_matrix_2d,
        base_rate=to_decimal(wacc),
    )
    apply_apv_advisor_range(apv_bridge, advisor_sensitivity, to_decimal(wacc))

    payload = stateless_dcf_result_payload(
        enterprise_value=enterprise_value,
        equity_after_ev_override=equity_after_ev_override,
        market_assumptions=market_assumptions_with_size_premium_source(
            market_context_metadata,
            size_premium_source,
            tax_provenance=build_tax_rate_provenance(dcf_request),
        ),
        dcf_result=dcf_result,
        wc=wc,
        wacc=wacc,
        cost_of_equity_headline=cost_of_equity_headline,
        terminal_growth_rate=terminal_growth_rate,
        terminal_value=terminal_value,
        terminal_value_methodology=terminal_value_methodology,
        terminal_exit_multiple=terminal_exit_multiple,
        pv_terminal_value=pv_terminal_value,
        tv_pct=tv_pct,
        forecast_pct=forecast_pct,
        proj_years=projection_year_count(dcf_result),
        mid_year_discounting=mid_year_discounting,
        pv_fcf_projections=pv_fcf_projections,
        sensitivity_wacc=sensitivity_wacc,
        sensitivity_growth=sensitivity_growth,
        sensitivity_matrix_2d=sensitivity_matrix_2d,
        wacc_buildup=wacc_buildup,
        apv_bridge=apv_bridge,
    )
    if request.wacc_evidence_contract is not None:
        payload.update(
            {
                "wacc_evidence_contract": request.wacc_evidence_contract.model_dump(mode="json"),
                "wacc_source_range_low": request.wacc_evidence_contract.range_low_fraction,
                "wacc_source_range_high": request.wacc_evidence_contract.range_high_fraction,
                # A direct observed WACC has no defensible synthetic cost-of-
                # equity decomposition. Keep the internal engine value out of
                # outward-facing payloads rather than presenting fake precision.
                "cost_of_equity": None,
                "cost_of_debt": None,
                "equity_weight": None,
                "debt_weight": None,
            }
        )
    # The core DCF engine consumes explicit FCFF correctly, but its generic
    # projection-detail rows use zero placeholders for EBITDA/EBIT/capex/NWC on
    # that path. Preserve the caller's sealed forecast detail for report and
    # audit presentation without changing the calculated cash flows.
    _actual_rows, explicit_forecast_rows = _split_stateless_forecast_years(request)
    if request.dcf_input_mode == "fcff_only":
        # Historical CapEx/tax/NWC coverage is relevant when the engine must
        # derive FCFF from accounting drivers.  It is not the cash-flow
        # authority on the explicit-FCFF path.  Keeping the core engine's
        # generic ``manual_fallback`` status here made a fully supplied,
        # sealed FCFF forecast read as assumption-driven in the report.
        payload["historical_fcf_readiness"] = {
            "schema_version": "dcf_input_readiness.v1",
            "status": "explicit_fcff_forecast",
            "historical_years_count": len(_actual_rows),
            "forecast_fcff_years": len(explicit_forecast_rows),
            "historical_driver_context": payload.get("historical_fcf_readiness"),
        }
    if explicit_forecast_rows:
        previous_revenue = to_decimal(request.current_year.revenue or 0)
        explicit_detail: list[dict[str, object]] = []
        for index, row in enumerate(
            sorted(explicit_forecast_rows, key=lambda item: item.year), start=1
        ):
            revenue = to_decimal(row.revenue or 0)
            growth_rate = (
                (revenue / previous_revenue - Decimal("1"))
                if previous_revenue > 0
                else Decimal("0")
            )
            explicit_detail.append(
                {
                    "year": row.year,
                    "revenue": revenue,
                    "ebitda": to_decimal(row.ebitda or 0),
                    "ebit": to_decimal(row.ebit or 0),
                    "taxes": to_decimal(row.tax_expense or 0),
                    "capex": to_decimal(row.capex or 0),
                    "nwc_change": to_decimal(row.nwc_change or 0),
                    "free_cash_flow": to_decimal(
                        row.free_cash_flow
                        if row.free_cash_flow is not None
                        else dcf_result.fcf_projections[index - 1]
                    ),
                    "growth_rate": growth_rate,
                    "confidence_score": max(
                        Decimal("0.6"), Decimal("1") - Decimal(index - 1) * Decimal("0.1")
                    ),
                }
            )
            previous_revenue = revenue
        payload["fcf_projection_detail"] = explicit_detail
    if advisor_sensitivity is not None:
        payload.update(
            {
                "enterprise_value_low": advisor_sensitivity["enterprise_value_low"],
                "enterprise_value_mid": enterprise_value,
                "enterprise_value_high": advisor_sensitivity["enterprise_value_high"],
                "ebitda_margin_sensitivity": advisor_sensitivity["ebitda_margin_sensitivity"],
                "sensitivity_range_policy": advisor_sensitivity["sensitivity_range_policy"],
            }
        )
    if advisor_range_exclusion is not None:
        payload["sensitivity_range_policy"] = advisor_range_exclusion
    return payload


def _extract_stateless_has_audit(request: CalculateRequest) -> Optional[bool]:
    for attr in ("has_audit", "audited_financials", "is_audited"):
        value = getattr(request, attr, None)
        if isinstance(value, bool):
            return value
    business_context = get_business_context(request)
    for key in ("has_audit", "audited_financials", "is_audited"):
        value = business_context.get(key)
        if isinstance(value, bool):
            return value
    return None


def _coalesce_stateless_sme_calibration(
    request: CalculateRequest,
) -> Optional[dict[str, object]]:
    raw = getattr(request, "sme_calibration", None)
    if isinstance(raw, dict) and raw:
        return dict(raw)
    return None


def _build_stateless_dcf_request(request: CalculateRequest) -> SimpleNamespace:
    request = with_normalized_actual_earnings(request)
    economic_context = (
        request.economic_context.model_dump()
        if hasattr(request.economic_context, "model_dump")
        else dict(request.economic_context)
    )
    has_audit = _extract_stateless_has_audit(request)
    business_context = get_business_context(request)
    historical_years, forecast_years = _split_stateless_forecast_years(request)
    if getattr(request, "dcf_input_mode", None) == "fcff_only":
        missing_years = [row.year for row in forecast_years if row.free_cash_flow is None]
        if not forecast_years or missing_years:
            raise ValueError(
                "FCFF-only DCF requires explicit free_cash_flow on every "
                f"forecast row; missing years: {missing_years}"
            )
    if forecast_years:
        forecast_years = _repair_stateless_legacy_forecast_nwc_changes(
            request,
            base_year=request.current_year,
            forecast_years=forecast_years,
        )
    if not forecast_years:
        forecast_years = _generate_stateless_dcf_forecast_years(
            request,
            base_year=request.current_year,
            projection_years=request.projection_years,
        )
    equity_risk_premium = (
        economic_context.get("equity_risk_premium")
        if economic_context.get("equity_risk_premium") is not None
        else (
            economic_context.get("market_risk_premium")
            if economic_context.get("market_risk_premium") is not None
            else economic_context.get("erp")
        )
    )
    modeled_public_dcf_authorized = public_modeled_dcf_is_authorized(request)

    return SimpleNamespace(
        company_name=request.company_name,
        country_code=request.country_code,
        registration_number=getattr(request, "registration_number", None),
        kbo_number=getattr(request, "kbo_number", None),
        kvk_number=getattr(request, "kvk_number", None),
        vat_number=getattr(request, "vat_number", None),
        legal_form=getattr(request, "legal_form", None),
        postal_code=getattr(request, "postal_code", None),
        city=getattr(request, "city", None),
        industry=request.industry,
        business_model=normalize_business_model(request.business_model),
        founding_year=request.founding_year,
        business_type_id=getattr(request.business_type_calibration, "business_type_id", None),
        sme_calibration=_coalesce_stateless_sme_calibration(request),
        current_year_data=request.current_year,
        historical_years_data=historical_years,
        forecast_years_data=forecast_years,
        dcf_input_mode=getattr(request, "dcf_input_mode", None),
        number_of_employees=request.number_of_employees,
        recurring_revenue_percentage=request.recurring_revenue_percentage,
        rev_recurring_pct=getattr(request, "rev_recurring_pct", None),
        rev_recurring_amount=getattr(request, "rev_recurring_amount", None),
        rev_top_client_concentration_pct=getattr(request, "rev_top_client_concentration_pct", None),
        rev_top_client_amount=getattr(request, "rev_top_client_amount", None),
        rev_contract_backlog=getattr(request, "rev_contract_backlog", None),
        government_bond_yield=(
            economic_context.get("risk_free_rate")
            if bool(economic_context.get("risk_free_rate_is_override"))
            or _economic_snapshot_commits_risk_free_rate(economic_context)
            or modeled_public_dcf_authorized
            else None
        ),
        long_term_gdp_growth=(
            economic_context.get("gdp_growth_rate")
            if economic_context.get("gdp_growth_rate") is not None
            else economic_context.get("terminal_growth_rate")
        ),
        equity_risk_premium=equity_risk_premium,
        economic_context=economic_context,
        # This is derived inside ValuationIQ after the signed Public Adaptive
        # resolution verifies.  It is deliberately not part of the public API
        # schema, so callers cannot spoof ValuationIQ-owned market provenance.
        public_modeled_dcf_authorized=modeled_public_dcf_authorized,
        # The market-context adapter needs the governed mode to distinguish an
        # all-in observed WACC (whose CAPM components are intentionally null)
        # from a component-built discount rate.  The public CalculateRequest
        # has already verified this contract against signed valuation_case.v2.
        wacc_evidence_contract=getattr(request, "wacc_evidence_contract", None),
        business_context=business_context,
        has_audit=has_audit,
        audited_financials=has_audit,
        is_audited=has_audit,
        owner_dependency=request.owner_dependency,
    )


def _apply_stateless_dcf_overrides(
    request: CalculateRequest,
    *,
    enterprise_value: Decimal,
    wacc: Decimal,
    terminal_growth_rate: Decimal,
    terminal_value: Decimal,
    pv_terminal_value: Decimal,
    cash_flow_projections: list[Decimal],
    mid_year_discounting: bool = True,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, list[Decimal], str, Decimal | None]:
    override_wacc = get_effective_dcf_wacc_override(request)
    override_terminal_growth = get_percent_override(request, "dcf_terminal_growth_pct")
    override_exit_multiple = get_dcf_exit_multiple_override(request)

    if (
        override_wacc is None
        and override_terminal_growth is None
        and override_exit_multiple is None
    ):
        return (
            enterprise_value,
            wacc,
            terminal_growth_rate,
            terminal_value,
            pv_terminal_value,
            [
                fcf
                / (
                    (Decimal("1") + wacc)
                    ** (Decimal(index) - (Decimal("0.5") if mid_year_discounting else 0))
                )
                for index, fcf in enumerate(cash_flow_projections, start=1)
            ],
            "gordon_growth",
            None,
        )

    applied_wacc = override_wacc if override_wacc is not None else wacc
    applied_growth = (
        override_terminal_growth if override_terminal_growth is not None else terminal_growth_rate
    )
    require_positive_discount_rate(applied_wacc)

    projected_fcfs = require_override_cash_flows(cash_flow_projections)

    def _discount_period(index: int) -> Decimal:
        period = Decimal(index)
        return period - Decimal("0.5") if mid_year_discounting else period

    pv_fcf_projections = [
        fcf / ((Decimal("1") + applied_wacc) ** _discount_period(index))
        for index, fcf in enumerate(projected_fcfs, start=1)
    ]
    terminal_ebitda = None
    explicit_forecast_years = [
        year_data
        for year_data in (getattr(request, "historical_years", None) or [])
        if getattr(year_data, "is_forecast", False)
    ]
    if explicit_forecast_years:
        last_forecast = max(
            explicit_forecast_years,
            key=lambda year_data: getattr(year_data, "year", 0),
        )
        last_forecast_ebitda = getattr(last_forecast, "ebitda", None)
        terminal_ebitda = (
            to_decimal(last_forecast_ebitda) if last_forecast_ebitda is not None else None
        )
    if terminal_ebitda is None:
        current_ebitda = getattr(getattr(request, "current_year", None), "ebitda", None)
        terminal_ebitda = to_decimal(current_ebitda) if current_ebitda is not None else None

    terminal_value_methodology = "gordon_growth"
    applied_exit_multiple = None
    fcff_only = getattr(request, "dcf_input_mode", None) == "fcff_only"
    if fcff_only and override_exit_multiple is not None:
        from .verified_terminal_earnings import verified_fcff_terminal_ebitda

        terminal_ebitda = verified_fcff_terminal_ebitda(request)
    if terminal_ebitda is not None and terminal_ebitda <= 0:
        terminal_ebitda = None
    if override_exit_multiple is not None and terminal_ebitda is not None:
        recalculated_terminal_value = terminal_ebitda * override_exit_multiple
        terminal_value_methodology = "exit_multiple"
        applied_exit_multiple = override_exit_multiple
    else:
        require_valid_gordon_growth(applied_wacc, applied_growth)
        terminal_fcf = projected_fcfs[-1] * (Decimal("1") + applied_growth)
        terminal_spread = applied_wacc - applied_growth
        # Match the engine and sensitivity grid for non-positive terminal FCFF.
        # Explicit negative cash flows are retained in the present-value sum.
        recalculated_terminal_value = (
            terminal_fcf / terminal_spread if projected_fcfs[-1] > 0 else Decimal("0")
        )
    recalculated_pv_terminal = recalculated_terminal_value / (
        (Decimal("1") + applied_wacc) ** _discount_period(len(projected_fcfs))
    )
    recalculated_enterprise = sum(pv_fcf_projections, Decimal("0")) + recalculated_pv_terminal

    return (
        recalculated_enterprise,
        applied_wacc,
        applied_growth,
        recalculated_terminal_value,
        recalculated_pv_terminal,
        pv_fcf_projections,
        terminal_value_methodology,
        applied_exit_multiple,
    )


def _finalize_stateless_dcf_sensitivities(
    *,
    dcf_result: object,
    fcf_values: list[Decimal],
    wacc: Decimal,
    terminal_growth_rate: Decimal,
    terminal_value: Decimal,
    terminal_value_methodology: str = "gordon_growth",
    terminal_exit_multiple: Decimal | None = None,
    terminal_ebitda: Decimal | None = None,
    mid_year_discounting: bool = True,
) -> tuple[dict[str, object], dict[str, object], Optional[dict[str, object]]]:
    from src.api.routes.valuation.calculators.dcf_calculator import DCFCalculator
    from src.api.routes.valuation.calculators.dcf_sensitivity_merge import (
        merge_rebuilt_dcf_sensitivity_payload,
    )

    raw_prior_wacc = getattr(dcf_result, "sensitivity_wacc", None)
    raw_prior_growth = getattr(dcf_result, "sensitivity_growth", None)
    prior_wacc = (
        {str(k): v for k, v in raw_prior_wacc.items()} if isinstance(raw_prior_wacc, dict) else {}
    )
    prior_growth = (
        {str(k): v for k, v in raw_prior_growth.items()}
        if isinstance(raw_prior_growth, dict)
        else {}
    )
    engine_matrix_2d = getattr(dcf_result, "sensitivity_matrix_2d", None)

    calc = DCFCalculator()
    return merge_rebuilt_dcf_sensitivity_payload(
        build=lambda: calc._build_dcf_sensitivity_payload(
            fcf_values=fcf_values,
            wacc=wacc,
            terminal_growth_rate=terminal_growth_rate,
            terminal_value=terminal_value,
            terminal_value_methodology=terminal_value_methodology,
            terminal_exit_multiple=terminal_exit_multiple,
            terminal_ebitda=terminal_ebitda,
            mid_year_discounting=mid_year_discounting,
        ),
        sanitize_matrix_2d=DCFCalculator._sanitize_sensitivity_matrix_2d,
        sensitivity_values_are_finite=DCFCalculator._sensitivity_scenario_values_are_finite,
        prior_wacc=prior_wacc,
        prior_growth=prior_growth,
        engine_matrix_2d=engine_matrix_2d,
        logger=logger,
        rebuild_failure_message="Stateless DCF sensitivity payload failed; using engine sensitivities",
        invalid_1d_maps_type_message=(
            "Stateless DCF API-layer sensitivity rebuild returned non-dict 1D maps; "
            "using engine sensitivities"
        ),
        non_finite_rebuild_message=(
            "Stateless DCF API-layer sensitivity maps contain non-finite or invalid numerics; "
            "using engine sensitivities"
        ),
        final_clear_message=(
            "Stateless DCF sensitivity maps failed finite check after merge; clearing 1D/2D sensitivity extras"
        ),
        matrix_sanitize_failed_message=(
            "Stateless DCF 2D sensitivity matrix sanitization failed; dropping matrix for this response"
        ),
        extra_base={"phase": "stateless_dcf_sensitivity"},
    )
