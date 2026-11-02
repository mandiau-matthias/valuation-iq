"""Stateless valuation calculation orchestration.

The FastAPI router owns HTTP transport. This module owns the calculate
workflow so valuation math, benchmark policy, DCF, asset fallback, and
response assembly can evolve without turning the route into a god function.
"""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status

from src.api.routes.valuation.benchmark_contract_utils import (
    as_mapping,
    extract_resolved_benchmark_contract,
)
from src.api.schemas.stateless_api import CalculateRequest, CalculateResponse, TriageFlag
from src.api.schemas.stateless_response_schemas import MethodResult
from src.config.valuation_constants import get_asking_price_markup
from src.domain.financial_arithmetic import decimal_number
from src.domain.omni_calc_coordinator import calculate_all_methods
from src.services.reports.fiscal_ebitda_reference import fiscal_reported_ebitda
from src.services.reports.market_context import build_market_context
from src.services.reports.negative_ebitda_recovery import (
    build_negative_ebitda_response,
    build_normalized_positive_resolution,
    build_public_negative_ebitda_response,
    normalized_positive,
    requires_private_recovery_path,
    requires_public_recovery_path,
)
from src.services.reports.public_adaptive_profile import (
    apply_public_adaptive_profile,
    bind_public_adaptive_runtime_weights,
    public_adaptive_weights_are_authorized,
    public_modeled_dcf_is_authorized,
)
from src.services.reports.public_valuation_audit import build_public_valuation_audit
from src.services.reports.stateless_adaptive_synthesis import promote_adaptive_methodology_synthesis
from src.services.reports.stateless_asset_primary import resolve_asset_primary_methodology
from src.services.reports.stateless_benchmark_gate import enforce_stateless_benchmark_gate
from src.services.reports.stateless_benchmark_policy import (
    annotate_method_results_with_benchmark_provenance,
    derive_data_tier,
)
from src.services.reports.stateless_calculation_helpers import generate_valuation_summary
from src.services.reports.stateless_completion_accounts import completion_account_bridge
from src.services.reports.stateless_dcf import calculate_stateless_dcf
from src.services.reports.stateless_equity_adjustments import (
    apply_shareholding_to_equity as _apply_shareholding_to_equity,
)
from src.services.reports.stateless_forward_cone import build_explicit_forecast_forward_cone
from src.services.reports.stateless_governed_market_decimal import (
    replace_governed_external_market_method,
)
from src.services.reports.stateless_headline_orchestration import (
    build_stateless_headline_computation,
)
from src.services.reports.stateless_input_context import prepare_stateless_input_context
from src.services.reports.stateless_methodology_selection import (
    has_explicit_fcff_forecast,
    select_stateless_methodology,
)
from src.services.reports.stateless_override_governance import (
    enforce_override_governance,
    resolve_multiple_calibration,
    utc_now_iso,
)
from src.services.reports.stateless_owner_dependency import apply_stateless_owner_dependency
from src.services.reports.stateless_response_assembly import (
    PURE_EQUITY_METHOD_KEYS,
    StatelessHeadlineState,
    apply_selected_method_headline_override,
    apply_startup_headline_override,
    build_financial_metrics,
    build_fiscal_4x_anchor,
    build_weighted_valuation_result,
    calculate_stateless_status,
    promote_saas_validation_flags,
)
from src.services.reports.stateless_startup_forward_cone import build_startup_forward_value_cone
from src.services.reports.stateless_valuation_run import (
    build_stateless_valuation_run,
    build_value_driver_ledger,
)
from src.services.reports.stateless_weighted_synthesis import promote_weighted_synthesis
from src.services.reports.valuation_presentation import (
    ValuationPresentation,
    derive_valuation_presentation,
)
from src.utils.decimal_helpers import optional_decimal, safe_decimal_or_zero, safe_float
from src.utils.logging import get_logger

logger = get_logger(__name__)

_enforce_override_governance = enforce_override_governance

__all__ = ["_apply_shareholding_to_equity", "calculate_stateless_response"]


def _public_audit_enterprise_band(
    audit: object,
) -> tuple[Decimal, Decimal, Decimal] | None:
    """Return the exact publication EV band already reconciled by ValuationIQ.

    The core engine is historically equity-headline-first. Public Adaptive is
    enterprise-value-first when the filed debt/cash/lease bridge is incomplete,
    so the response must promote the audit's already-reconciled EV band instead
    of leaving the canonical enterprise headline empty.
    """

    bridge = as_mapping(as_mapping(audit).get("value_bridge"))
    band = as_mapping(bridge.get("enterprise_value"))
    try:
        low = Decimal(str(band.get("low")))
        mid = Decimal(str(band.get("mid")))
        high = Decimal(str(band.get("high")))
    except (ArithmeticError, TypeError, ValueError):
        return None
    if not all(value.is_finite() for value in (low, mid, high)):
        return None
    if low <= 0 or not low <= mid <= high:
        return None
    return low, mid, high


def _stateless_real_estate_surplus(request: CalculateRequest) -> Decimal:
    if request.real_estate_treatment not in {"included", "owned_included"}:
        return Decimal("0")
    # The operating valuation is rent-adjusted upstream. The non-operating
    # property therefore enters the equity bridge at independently appraised
    # market value once; subtracting book value here would double count it.
    return safe_decimal_or_zero(request.real_estate_market_value)


def _maybe_calculate_stateless_dcf(
    request: CalculateRequest,
    *,
    dcf_weight: float,
    ebitda: float,
) -> tuple[dict[str, object] | None, str | None]:
    if dcf_weight <= 0:
        return None, None
    from .forecast_admission import ForecastEvidenceError, require_verified_forecast

    try:
        from .public_adaptive_profile import public_modeled_dcf_is_authorized

        if not public_modeled_dcf_is_authorized(request):
            require_verified_forecast(request)
    except ForecastEvidenceError as exc:
        return None, str(exc)
    if ebitda <= 0 and not has_explicit_fcff_forecast(request):
        return None, None
    # Ineligibility is decided above or returned by the DCF model. A runtime
    # failure must reach the API error boundary, never silently reweight the
    # remaining methods into a seemingly successful valuation.
    from .forecast_admission import ForecastEvidenceError

    try:
        return calculate_stateless_dcf(request), None
    except ForecastEvidenceError as exc:
        # Only a known evidence exclusion may remove a method. Unexpected
        # arithmetic/runtime failures must still fail the entire calculation.
        return None, str(exc)


def _primary_omni_basis(asset_primary_payload: dict[str, object] | None) -> str:
    if asset_primary_payload and asset_primary_payload.get("available"):
        return "asset_based"
    return "hybrid"


def _nwc_adjustment_for_omni(nwc_normalization_data: object) -> Decimal:
    if not isinstance(nwc_normalization_data, dict):
        return Decimal(0)
    if not nwc_normalization_data.get("available", True):
        return Decimal(0)
    surplus_deficit = nwc_normalization_data.get("surplus_deficit")
    return (
        decimal_number(surplus_deficit, "NWC adjustment")
        if surplus_deficit is not None
        else Decimal(0)
    )


def _reconcile_dcf_payload_to_canonical_method(
    *,
    dcf_results: dict[str, object] | None,
    valuation_results: dict[str, MethodResult],
    nwc_adjustment: Decimal,
) -> None:
    """Pin report-facing DCF equity to the same one-time bridge used by Omni.

    The DCF engine emits enterprise value and an equity bridge before the
    measurement-date NWC peg is known.  Omni applies that peg when it builds
    the canonical DCF method result.  Persisting the earlier equity value in
    ``dcf_results`` made the DCF report page disagree with the API/run by the
    exact NWC amount, so retain the pre-peg value as lineage and publish the
    canonical method equity as the report-facing value.
    """
    if not isinstance(dcf_results, dict):
        return
    method = valuation_results.get("dcf")
    if method is None or not method.available or method.value is None:
        return
    prior_equity = safe_decimal_or_zero(dcf_results.get("equity_value"))
    canonical_equity = safe_decimal_or_zero(method.value)
    dcf_results["equity_value_before_nwc_adjustment"] = prior_equity
    dcf_results["nwc_adjustment"] = safe_decimal_or_zero(nwc_adjustment)
    dcf_results["equity_value"] = canonical_equity
    dcf_results["equity_bridge_reconciled"] = True


def _apply_requested_method_result_eligibility(
    request: CalculateRequest,
    valuation_results: dict[str, MethodResult],
) -> None:
    disabled: dict[str, str] = {}
    if not request.include_dcf:
        disabled["dcf"] = "DCF disabled by request include_dcf=false."
    if not request.include_multiples:
        for key in ("ebitda_multiple", "sde_multiple", "omzet_multiple", "arr_multiple"):
            disabled[key] = "Market multiple methods disabled by request include_multiples=false."
    for key, reason in disabled.items():
        result = valuation_results.get(key)
        if result is None:
            continue
        valuation_results[key] = result.model_copy(
            update={
                "value": None,
                "value_low": None,
                "value_high": None,
                "available": False,
                "unavailable_reason": reason,
            }
        )


def _has_stateless_balance_sheet(request: CalculateRequest) -> bool:
    current = getattr(request, "current_year", None)
    if current is None:
        return False
    return any(
        getattr(current, field, None) not in (None, "", 0)
        for field in ("total_assets", "total_debt", "cash", "total_equity")
    )


def _years_of_stateless_data(request: CalculateRequest) -> int:
    return 1 + len(getattr(request, "historical_years", None) or [])


def _has_legal_entity_identifier(request: CalculateRequest) -> bool:
    return any(
        str(getattr(request, field, "") or "").strip()
        for field in ("registration_number", "kbo_number", "kvk_number", "vat_number")
    )


def _is_limited_scope_activity_valuation(request: CalculateRequest) -> bool:
    return (
        _years_of_stateless_data(request) <= 2
        and not _has_stateless_balance_sheet(request)
        and not _has_legal_entity_identifier(request)
    )


def _apply_limited_scope_presentation(
    request: CalculateRequest,
    presentation: ValuationPresentation,
) -> ValuationPresentation:
    if presentation.data_tier != "defensible" or not _is_limited_scope_activity_valuation(request):
        return presentation
    return replace(
        presentation,
        confidence_label="Limited-scope estimate - benchmark-grounded, not transaction certainty",
        disclaimer=(
            "Benchmark-grounded on supplied P&L only; confirm legal entity, balance sheet, "
            "equipment value, debt/cash and owner compensation before using in a transaction."
        ),
    )


def _apply_adaptive_result_multiples_only_presentation(
    valuation_results: dict[str, object],
    *,
    dcf_exclusion_reason: str | None,
) -> None:
    dcf_result = valuation_results.get("dcf")
    if bool(getattr(dcf_result, "available", False)):
        return

    adaptive = valuation_results.get("upswitch_adaptive")
    details = getattr(adaptive, "details", None)
    if not isinstance(details, dict):
        return
    if str(details.get("primary_method_key") or "") in PURE_EQUITY_METHOD_KEYS:
        # A missing DCF does not turn a direct-equity NAV/startup/fiscal result
        # into a market-multiples conclusion. Preserve the engine's actual
        # premise and disclosure.
        return

    reason = dcf_exclusion_reason or getattr(dcf_result, "unavailable_reason", None)
    details["description"] = (
        "Market approach with calibrated transaction multiples; DCF is not included "
        "as a weighted valuation leg for this profile."
    )
    details["primary_basis"] = "market"
    details["methodology_justification"] = (
        f"DCF is not included for this profile: {reason}"
        if reason
        else (
            "DCF is not included for this profile; calibrated market multiples drive "
            "the conclusion."
        )
    )


def _dcf_method_available(valuation_results: dict[str, object]) -> bool | None:
    dcf_result = valuation_results.get("dcf")
    if dcf_result is None:
        return None
    return bool(getattr(dcf_result, "available", False))


def _normalize_unavailable_dcf_weights(
    valuation_results: dict[str, object],
    *,
    dcf_weight: object,
    multiples_weight: object,
    include_multiples: bool = True,
) -> tuple[Decimal, Decimal]:
    if _dcf_method_available(valuation_results) is not False:
        return safe_decimal_or_zero(dcf_weight), safe_decimal_or_zero(multiples_weight)
    adaptive = valuation_results.get("upswitch_adaptive")
    adaptive_details = getattr(adaptive, "details", None)
    if (
        isinstance(adaptive_details, dict)
        and str(adaptive_details.get("primary_method_key") or "") in PURE_EQUITY_METHOD_KEYS
    ):
        return safe_decimal_or_zero(dcf_weight), safe_decimal_or_zero(multiples_weight)
    return Decimal("0"), Decimal("1") if include_multiples else Decimal("0")


def _request_requires_dcf_only_outcome(request: CalculateRequest) -> bool:
    """Whether no standalone selected/weighted method can replace failed DCF."""
    if not request.include_dcf or request.include_multiples:
        return False
    user_weights = request.user_weights or {}
    if user_weights:
        return all(
            key == "dcf" or safe_decimal_or_zero(weight) <= 0
            for key, weight in user_weights.items()
        )
    return request.selected_method in {None, "dcf", "upswitch_adaptive"}


def _normalize_unavailable_dcf_selection_reason(
    valuation_results: dict[str, object],
    *,
    current_reason: str | None,
    dcf_exclusion_reason: str | None,
) -> str | None:
    if _dcf_method_available(valuation_results) is not False:
        return current_reason

    adaptive = valuation_results.get("upswitch_adaptive")
    details = getattr(adaptive, "details", None)
    if not isinstance(details, dict):
        return current_reason
    if str(details.get("primary_basis") or "").strip().lower() != "market":
        return current_reason

    reason = dcf_exclusion_reason or getattr(
        valuation_results.get("dcf"),
        "unavailable_reason",
        None,
    )
    if reason:
        return f"Market approach selected; DCF is not included for this profile: {reason}"
    return "Market approach selected; DCF is not included for this profile."


def _build_safe_stateless_market_context(
    request: CalculateRequest,
    *,
    owner_adjustment: float,
    data_tier: str,
) -> dict[str, object] | None:
    try:
        titan_metadata = as_mapping(getattr(request, "multiples_metadata", None))
        resolved_contract = extract_resolved_benchmark_contract(titan_metadata) or (
            titan_metadata.get("benchmark_contract") or titan_metadata.get("benchmarkContract")
        )
        return build_market_context(
            as_mapping(resolved_contract) or None,
            owner_dependency_adjustment=owner_adjustment,
            data_tier=data_tier,
            now=datetime.now(timezone.utc),
        )
    except Exception:
        logger.warning("market_context build failed", exc_info=True)
        return None


def _loggable_amount(value: object) -> float | None:
    """Return a finite float for a log field; the response owns the exact value."""
    amount = optional_decimal(value)
    return float(amount) if amount is not None else None


def _log_stateless_refusal(request: CalculateRequest, refusal: HTTPException) -> None:
    """Log a deliberate non-2xx outcome together with its machine-readable reason.

    The API's HTTPException handler returns the detail to the caller but logs
    nothing, so a refused calculation used to leave only a bare status code in
    the access log. Recursive timeline checkpoints already log each year they
    skip, so their refusals are recorded at info level to avoid doubling that.
    """
    if isinstance(refusal.detail, dict):
        detail = refusal.detail
        message = detail.get("message")
    else:
        detail = {}
        message = str(refusal.detail)[:300] if refusal.detail else None
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    timeline_subrequest = metadata.get("valuation_timeline_subrequest") is True
    log = logger.info if timeline_subrequest else logger.warning
    log(
        "Stateless calculate refused",
        extra={
            "valuation_id": request.valuation_id,
            "status_code": refusal.status_code,
            "code": detail.get("code"),
            "message": message,
            "failed_controls": detail.get("failed_controls"),
            "control_diagnostics": detail.get("control_diagnostics"),
            "valuation_timeline_subrequest": timeline_subrequest,
        },
    )


def calculate_stateless_response(
    request: CalculateRequest,
    *,
    verified_titan_request_wire_commitment: dict[str, str] | None = None,
    parent_public_owner_operated_classification: str | None = None,
) -> CalculateResponse:
    """
    Calculate business valuation from complete input data.

    BRAIN & MUSCLE ARCHITECTURE:
    - Titan (The Brain) sends ALL required data
    - ValuationIQ (The Muscle) runs the 12-step calculation
    - No database access, no AI calls, no session state
    - `shares_for_sale` preserves partial-stake valuations instead of clamping to 100%

    Returns complete valuation results.
    """
    start_time = time.time()

    logger.info(
        "Stateless calculate request received",
        extra={
            "valuation_id": request.valuation_id,
            "company_name": request.company_name,
            "industry": request.industry,
            "methodology": request.methodology,
        },
    )

    try:
        request_metadata = request.metadata if isinstance(request.metadata, dict) else {}
        if request_metadata.get("public_method_resolver_v2") is True:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "PUBLIC_METHOD_RESOLVER_RETIRED",
                    "message": (
                        "public_method_resolver_v2/v3 is a retired duplicate valuation path; "
                        "use ValuationIQ Public Adaptive V2"
                    ),
                },
            )
        request = apply_public_adaptive_profile(request)
        input_context = prepare_stateless_input_context(
            request=request,
            logger=logger,
            parent_public_owner_operated_classification=(
                parent_public_owner_operated_classification
            ),
        )
        request = input_context.request
        # Public negative-EBITDA cases are a separate, fail-closed domain path.
        # Route them before the private recovery resolver so public evidence can
        # never activate Recovery DCF, owner scenarios, or a forward cone.
        if requires_public_recovery_path(request, input_context.earnings_basis):
            return build_public_negative_ebitda_response(
                request,
                input_context,
                verified_titan_request_wire_commitment=(verified_titan_request_wire_commitment),
            )
        if requires_private_recovery_path(request, input_context.earnings_basis):
            return build_negative_ebitda_response(
                request,
                input_context,
                verified_titan_request_wire_commitment=(verified_titan_request_wire_commitment),
            )
        triage_flags = input_context.triage_flags
        historical_data = input_context.historical_data
        normalized_business_model = input_context.normalized_business_model
        trial_balance_anomalies = input_context.trial_balance_anomalies
        calibration = input_context.calibration
        primary_business_type_id = input_context.primary_business_type_id
        benchmark_contract = input_context.benchmark_contract
        allow_untrusted_multiples_fallback = input_context.allow_untrusted_multiples_fallback
        revenue = input_context.revenue
        ebitda = input_context.ebitda
        ebitda_margin = input_context.ebitda_margin
        revenue_growth = input_context.revenue_growth
        balance_sheet = input_context.balance_sheet
        activity_code = input_context.activity_code
        ownership_percentage = input_context.ownership_percentage
        ownership_multiplier = input_context.ownership_multiplier
        holdings_consolidation = input_context.holdings_consolidation

        methodology_selection = select_stateless_methodology(
            request=request,
            calibration=calibration,
            ebitda=ebitda,
            revenue=revenue,
            ebitda_margin=ebitda_margin,
            historical_year_count=len(historical_data),
            balance_sheet=balance_sheet,
            activity_code=activity_code,
        )
        dcf_weight = methodology_selection.dcf_weight
        multiples_weight = methodology_selection.multiples_weight
        methodology_used = methodology_selection.methodology_used
        methodology_selection_reason = methodology_selection.methodology_selection_reason
        dcf_exclusion_reason = methodology_selection.dcf_exclusion_reason
        triage_flags.extend(methodology_selection.triage_flags)

        multiple_calibration_state = resolve_multiple_calibration(
            request=request,
            calibration=calibration,
            primary_business_type_id=primary_business_type_id,
        )
        ev_ebitda_multiple = multiple_calibration_state.ev_ebitda_multiple
        p25_multiple = multiple_calibration_state.p25_multiple
        p75_multiple = multiple_calibration_state.p75_multiple
        business_type_multiple_override_audit = (
            multiple_calibration_state.business_type_multiple_override_audit
        )
        multiple_calibration_audit = multiple_calibration_state.multiple_calibration_audit
        effective_multiple_override_audit = None

        real_estate_surplus = _stateless_real_estate_surplus(request)

        completion_accounts = completion_account_bridge(request)
        total_debt = safe_float(completion_accounts.bridge_total_debt)
        cash = safe_float(completion_accounts.bridge_cash)

        dcf_results, dcf_runtime_failure = _maybe_calculate_stateless_dcf(
            request,
            dcf_weight=dcf_weight,
            ebitda=ebitda,
        )
        if dcf_runtime_failure is not None:
            dcf_exclusion_reason = dcf_runtime_failure
        nwc_normalization_data = None

        asset_primary_state = resolve_asset_primary_methodology(
            request=request,
            normalized_business_model=normalized_business_model,
            balance_sheet=balance_sheet,
            ownership_multiplier=ownership_multiplier,
            revenue=revenue,
            methodology_used=methodology_used,
            methodology_selection_reason=methodology_selection_reason,
            dcf_weight=dcf_weight,
            multiples_weight=multiples_weight,
            dcf_exclusion_reason=dcf_exclusion_reason,
            dcf_results=dcf_results,
        )
        asset_primary_payload = asset_primary_state.asset_primary_payload
        methodology_used = asset_primary_state.methodology_used
        methodology_selection_reason = asset_primary_state.methodology_selection_reason
        dcf_weight = asset_primary_state.dcf_weight
        multiples_weight = asset_primary_state.multiples_weight
        dcf_exclusion_reason = asset_primary_state.dcf_exclusion_reason
        dcf_results = asset_primary_state.dcf_results

        adaptive_uncertainty_inflation = Decimal("1")
        if dcf_runtime_failure is not None:
            if asset_primary_payload and asset_primary_payload.get("available"):
                pass
            elif safe_decimal_or_zero(multiples_weight) > 0 or (
                request.selected_method == "dcf"
                and not request.user_weights
                and request.include_multiples
            ):
                surviving_weight = max(Decimal("0.01"), safe_decimal_or_zero(multiples_weight))
                adaptive_uncertainty_inflation = min(Decimal("2"), Decimal("1") / surviving_weight)
                dcf_weight = Decimal("0")
                multiples_weight = Decimal("1")
                methodology_used = "MULTIPLES"
                methodology_selection_reason = (
                    "DCF was excluded because its source evidence or calculation was unavailable; the eligible "
                    "market method was renormalized to 100%."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "NO_ELIGIBLE_VALUATION_METHOD",
                        "message": dcf_runtime_failure,
                    },
                )
            triage_flags.append(
                TriageFlag(
                    field="dcf",
                    issue=(
                        "dcf_source_evidence_method_excluded"
                        if dcf_runtime_failure.startswith("FORECAST_")
                        else "dcf_runtime_failure_method_excluded"
                    ),
                    severity="warning",
                    value={
                        "reason": dcf_runtime_failure,
                        "resolved_weights": {
                            "dcf": str(dcf_weight),
                            "multiples": str(multiples_weight),
                        },
                        "uncertainty_inflation_factor": str(adaptive_uncertainty_inflation),
                    },
                )
            )
        if (
            not (asset_primary_payload and asset_primary_payload.get("available"))
            and safe_decimal_or_zero(dcf_weight) <= 0
            and safe_decimal_or_zero(multiples_weight) <= 0
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "NO_ELIGIBLE_VALUATION_METHOD",
                    "message": (
                        "No requested valuation method remains eligible after evidence "
                        "and request controls were applied."
                    ),
                    "dcf_exclusion_reason": dcf_exclusion_reason,
                },
            )
        try:
            benchmark_gate = enforce_stateless_benchmark_gate(
                request=request,
                calibration=calibration,
                asset_primary_payload=asset_primary_payload,
                benchmark_contract=benchmark_contract,
                allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
            )
            benchmark_contract_resolved = benchmark_gate.benchmark_contract_resolved
            benchmark_provenance = benchmark_gate.benchmark_provenance
        except HTTPException:
            dcf_equity = (
                safe_decimal_or_zero(dcf_results.get("equity_value"))
                if isinstance(dcf_results, dict)
                else Decimal("0")
            )
            if str(request.methodology).upper() != "HYBRID" or dcf_equity <= 0:
                raise
            original_dcf_weight = max(Decimal("0.01"), safe_decimal_or_zero(dcf_weight))
            adaptive_uncertainty_inflation = min(Decimal("2"), Decimal("1") / original_dcf_weight)
            dcf_weight = Decimal("1")
            multiples_weight = Decimal("0")
            methodology_used = "DCF"
            benchmark_contract_resolved = False
            benchmark_provenance = None
            triage_flags.append(
                TriageFlag(
                    field="business_type_calibration.benchmark_contract",
                    issue="multiples_ineligible_missing_benchmark_dcf_renormalized",
                    severity="warning",
                    value={
                        "resolved_weights": {"dcf": "1", "multiples": "0"},
                        "uncertainty_inflation_factor": str(adaptive_uncertainty_inflation),
                        "policy_version": "missing_method_uncertainty.v1",
                    },
                )
            )

        headline = build_stateless_headline_computation(
            request=request,
            input_context=input_context,
            asset_primary_payload=asset_primary_payload,
            real_estate_surplus=real_estate_surplus,
            benchmark_contract_resolved=benchmark_contract_resolved,
            benchmark_provenance=benchmark_provenance,
            ev_ebitda_multiple=ev_ebitda_multiple,
            p25_multiple=p25_multiple,
            p75_multiple=p75_multiple,
            multiple_calibration_audit=multiple_calibration_audit,
            business_type_multiple_override_audit=business_type_multiple_override_audit,
            benchmark_contract=benchmark_contract,
            total_debt=total_debt,
            cash=cash,
            logger=logger,
        )
        equity_value_low = headline.equity_value_low
        equity_value_mid = headline.equity_value_mid
        equity_value_high = headline.equity_value_high
        enterprise_value_mid = headline.enterprise_value_mid
        enterprise_value_low = headline.enterprise_value_low
        enterprise_value_high = headline.enterprise_value_high
        confidence_score = headline.confidence_score
        confidence_level = headline.confidence_level
        recommended_asking = headline.recommended_asking
        value_drivers = headline.value_drivers
        risk_factors = headline.risk_factors
        data_quality = headline.data_quality
        size_discount = headline.size_discount
        liquidity_discount = headline.liquidity_discount
        owner_adjustment = headline.owner_adjustment
        country_adjustment = headline.country_adjustment
        total_adjustment = headline.total_adjustment
        recommended_multiple = headline.recommended_multiple
        multiples_results = headline.multiples_results
        multiple_build_up_obj = headline.multiple_build_up_obj
        earnings_basis_value = headline.earnings_basis_value
        earnings_basis_rationale_value = headline.earnings_basis_rationale_value
        ownership_percentage = headline.ownership_percentage
        ownership_multiplier = headline.ownership_multiplier
        nwc_normalization_data = headline.nwc_normalization_data
        bridge_adjustment_data = headline.bridge_adjustment_data

        financial_metrics = build_financial_metrics(
            revenue_growth_evidence=input_context.revenue_growth_evidence,
            revenue_cagr_3y_evidence=input_context.revenue_cagr_3y_evidence,
            current_year=request.current_year,
            ebitda_margin=ebitda_margin,
            revenue_growth=float(revenue_growth),
            ownership_percentage=ownership_percentage,
            ownership_multiplier=ownership_multiplier,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            reported_ebitda=safe_decimal_or_zero(
                input_context.earnings_basis.get("current_reported_ebitda")
            ),
            normalized_ebitda=safe_decimal_or_zero(
                input_context.earnings_basis.get("current_normalized_ebitda")
            ),
            valuation_basis_ebitda=safe_decimal_or_zero(
                input_context.earnings_basis.get("normalized_ebitda")
            ),
            valuation_basis_mode=str(input_context.earnings_basis.get("mode") or "unknown"),
        )
        financial_metrics.update(completion_accounts.to_payload())
        # These two canonical bridge fields contain only known inputs. Missing
        # completion-account components remain explicit nulls above and force
        # the bridge into illustrative status in report policy.
        financial_metrics["cash"] = float(completion_accounts.bridge_cash)
        financial_metrics["total_debt"] = float(completion_accounts.bridge_total_debt)

        valuation_summary = generate_valuation_summary(
            company_name=request.company_name,
            equity_value_mid=equity_value_mid,
            methodology=methodology_used,
            confidence_level=confidence_level,
        )

        sde_basis = input_context.earnings_basis.get("sde_basis")
        if not isinstance(sde_basis, dict):
            sde_basis = {}
        owner_salary_addback = (
            safe_float(sde_basis.get("owner_compensation_addback"))
            if sde_basis.get("available") is True
            else None
        )
        sde_ebitda = (
            safe_float(sde_basis.get("sde_base_ebitda"))
            if sde_basis.get("available") is True
            else None
        )
        # Gross margin and revenue are distinct accounting measures. SDE's
        # turnover gate uses the observed revenue, including zero/missing.
        sde_revenue = None

        # === Omni-Calc: calculate all methods simultaneously ===
        primary_omni_basis = _primary_omni_basis(asset_primary_payload)
        nwc_adj_for_omni = _nwc_adjustment_for_omni(nwc_normalization_data)

        from .value_basis_admission import uses_accounting_basis_policy
        from .revenue_basis_admission import revenue_multiple_basis

        revenue_basis, cohort_revenue_basis, revenue_multiple_input = revenue_multiple_basis(
            request, benchmark_contract
        )
        valuation_results = calculate_all_methods(
            enterprise_value_mid=(
                enterprise_value_mid if uses_accounting_basis_policy(request) else None
            ),
            enterprise_value_low=(
                enterprise_value_low if uses_accounting_basis_policy(request) else None
            ),
            enterprise_value_high=(
                enterprise_value_high if uses_accounting_basis_policy(request) else None
            ),
            revenue_multiple_input=revenue_multiple_input,
            require_revenue_basis=uses_accounting_basis_policy(request),
            revenue_basis=revenue_basis,
            cohort_revenue_basis=cohort_revenue_basis,
            ebitda=input_context.earnings_basis.get("normalized_ebitda"),
            revenue=request.current_year.revenue,
            ev_ebitda_multiple=ev_ebitda_multiple,
            p25_multiple=p25_multiple,
            p75_multiple=p75_multiple,
            total_adjustment=total_adjustment,
            total_debt=completion_accounts.bridge_total_debt,
            cash=completion_accounts.bridge_cash,
            equity_value_mid=equity_value_mid,
            dcf_results=dcf_results,
            dcf_exclusion_reason=dcf_exclusion_reason,
            calibration=calibration,
            revenue_growth=float(revenue_growth),
            owner_dependency=request.owner_dependency,
            industry=request.industry,
            recurring_revenue_percentage=getattr(request, "recurring_revenue_percentage", None),
            equity_value_low=equity_value_low,
            equity_value_high=equity_value_high,
            ownership_multiplier=ownership_multiplier,
            country_code=request.country_code,
            company_name=request.company_name,
            business_model=normalized_business_model,
            founding_year=request.founding_year,
            reporting_year=request.current_year.year,
            balance_sheet=balance_sheet,
            business_context=getattr(request, "business_context", None),
            business_type_id=getattr(calibration, "business_type_id", None),
            primary_basis=primary_omni_basis,
            owner_salary_addback=owner_salary_addback,
            sde_ebitda=sde_ebitda,
            sde_revenue=sde_revenue,
            nwc_adjustment=nwc_adj_for_omni,
            fiscal_ebitda=ebitda,
            methodology_justification=methodology_selection_reason,
            startup_inputs=getattr(request, "startup_inputs", None),
            # Liquidation Phase 2-4 advisor inputs — single dict-shaped
            # passthrough; keys map 1:1 to calculate_liquidation_result
            # kwargs (cascade buckets, tax bridge, wind-down, premise
            # override, sensitivity, NACE code, replacement-cost uplift,
            # effective_date, etc.). None means engine defaults — the
            # report flags estimated buckets in that case.
            liquidation_inputs=getattr(request, "liquidation_inputs", None),
            real_estate_yield_evidence=getattr(
                request, "real_estate_yield_evidence_contract", None
            ),
        )
        _apply_requested_method_result_eligibility(request, valuation_results)
        if request.selected_method == "real_estate_yield":
            property_result = valuation_results.get("real_estate_yield")
            if (
                property_result is None
                or property_result.available is not True
                or property_result.value is None
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "REAL_ESTATE_YIELD_UNAVAILABLE",
                        "message": (
                            getattr(property_result, "unavailable_reason", None)
                            or "Governed property evidence could not support income capitalisation."
                        ),
                        "fallback_applied": False,
                        "required_premise": "distressed_or_liquidation_if_negative",
                    },
                )
        _reconcile_dcf_payload_to_canonical_method(
            dcf_results=dcf_results,
            valuation_results=valuation_results,
            nwc_adjustment=nwc_adj_for_omni,
        )
        _apply_adaptive_result_multiples_only_presentation(
            valuation_results,
            dcf_exclusion_reason=dcf_exclusion_reason,
        )

        promote_saas_validation_flags(
            valuation_results=valuation_results,
            triage_flags=triage_flags,
            logger=logger,
        )

        headline_state = apply_startup_headline_override(
            selected_method=getattr(request, "selected_method", None),
            valuation_results=valuation_results,
            headline_state=StatelessHeadlineState(
                equity_value_low=equity_value_low,
                equity_value_mid=equity_value_mid,
                equity_value_high=equity_value_high,
                enterprise_value_low=enterprise_value_low,
                enterprise_value_mid=enterprise_value_mid,
                enterprise_value_high=enterprise_value_high,
                recommended_asking=recommended_asking,
                recommended_multiple=recommended_multiple,
                multiples_results=multiples_results,
                methodology_used=methodology_used,
                methodology_selection_reason=methodology_selection_reason,
            ),
        )
        equity_value_low = headline_state.equity_value_low
        equity_value_mid = headline_state.equity_value_mid
        equity_value_high = headline_state.equity_value_high
        enterprise_value_low = headline_state.enterprise_value_low
        enterprise_value_mid = headline_state.enterprise_value_mid
        enterprise_value_high = headline_state.enterprise_value_high
        recommended_asking = headline_state.recommended_asking
        recommended_multiple = headline_state.recommended_multiple
        multiples_results = headline_state.multiples_results
        methodology_used = headline_state.methodology_used
        methodology_selection_reason = headline_state.methodology_selection_reason

        annotate_method_results_with_benchmark_provenance(
            valuation_results,
            request=request,
            benchmark_contract=benchmark_contract if benchmark_contract_resolved else None,
            benchmark_provenance=benchmark_provenance,
            allow_untrusted_fallback=allow_untrusted_multiples_fallback,
        )
        dcf_weight, multiples_weight = _normalize_unavailable_dcf_weights(
            valuation_results,
            dcf_weight=dcf_weight,
            multiples_weight=multiples_weight,
            include_multiples=request.include_multiples,
        )
        if (
            _dcf_method_available(valuation_results) is False
            and _request_requires_dcf_only_outcome(request)
            and not (asset_primary_payload and asset_primary_payload.get("available"))
        ):
            dcf_method = valuation_results.get("dcf")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "NO_ELIGIBLE_VALUATION_METHOD",
                    "message": (
                        "DCF became unavailable after the enterprise-to-equity bridge, "
                        "and market methods were explicitly disabled."
                    ),
                    "dcf_exclusion_reason": getattr(
                        dcf_method,
                        "unavailable_reason",
                        None,
                    ),
                    "resolved_weights": {"dcf": "0", "multiples": "0"},
                },
            )
        methodology_selection_reason = _normalize_unavailable_dcf_selection_reason(
            valuation_results,
            current_reason=methodology_selection_reason,
            dcf_exclusion_reason=dcf_exclusion_reason,
        )

        replace_governed_external_market_method(
            request=request,
            valuation_results=valuation_results,
            ebitda_basis=safe_decimal_or_zero(
                input_context.earnings_basis.get("normalized_ebitda")
            ),
            total_debt=safe_decimal_or_zero(total_debt),
            cash=safe_decimal_or_zero(cash),
            nwc_adjustment=safe_decimal_or_zero(nwc_adj_for_omni),
            ownership_multiplier=ownership_multiplier,
        )

        if methodology_used != "STARTUP_VALUATION" and not (
            asset_primary_payload and asset_primary_payload.get("available")
        ):
            common_bridge_adjustment = real_estate_surplus + safe_decimal_or_zero(
                bridge_adjustment_data.get("total_net_impact")
                if isinstance(bridge_adjustment_data, dict)
                else None
            )
            adaptive_headline = promote_adaptive_methodology_synthesis(
                valuation_results=valuation_results,
                dcf_results=dcf_results,
                dcf_weight=dcf_weight,
                multiples_weight=multiples_weight,
                multiples_equity_low=equity_value_low,
                multiples_equity_mid=equity_value_mid,
                multiples_equity_high=equity_value_high,
                multiples_enterprise_low=enterprise_value_low,
                multiples_enterprise_mid=enterprise_value_mid,
                multiples_enterprise_high=enterprise_value_high,
                total_debt=total_debt,
                cash=cash,
                nwc_adjustment=nwc_adj_for_omni,
                ownership_multiplier=ownership_multiplier,
                common_equity_bridge_adjustment=common_bridge_adjustment,
                current_reason=methodology_selection_reason,
                uncertainty_inflation_factor=adaptive_uncertainty_inflation,
            )
            if adaptive_headline is not None:
                equity_value_low = adaptive_headline.equity_value_low
                equity_value_mid = adaptive_headline.equity_value_mid
                equity_value_high = adaptive_headline.equity_value_high
                enterprise_value_low = adaptive_headline.enterprise_value_low
                enterprise_value_mid = adaptive_headline.enterprise_value_mid
                enterprise_value_high = adaptive_headline.enterprise_value_high
                methodology_used = adaptive_headline.methodology_used
                methodology_selection_reason = adaptive_headline.methodology_selection_reason
                valuation_results["upswitch_adaptive"] = adaptive_headline.adaptive_method
                asking_markup = get_asking_price_markup(
                    confidence_level.lower(),
                    advisor_override_pct=getattr(request, "asking_price_buffer_pct", None),
                )
                recommended_asking = (equity_value_mid * asking_markup).quantize(Decimal("0.01"))
                if methodology_used == "DCF":
                    recommended_multiple = None

        selected_headline = apply_selected_method_headline_override(
            selected_method=getattr(request, "selected_method", None),
            user_weights=getattr(request, "user_weights", None),
            valuation_results=valuation_results,
            headline_state=StatelessHeadlineState(
                equity_value_low=equity_value_low,
                equity_value_mid=equity_value_mid,
                equity_value_high=equity_value_high,
                enterprise_value_low=enterprise_value_low,
                enterprise_value_mid=enterprise_value_mid,
                enterprise_value_high=enterprise_value_high,
                recommended_asking=recommended_asking,
                recommended_multiple=recommended_multiple,
                multiples_results=multiples_results,
                methodology_used=methodology_used,
                methodology_selection_reason=methodology_selection_reason,
            ),
            triage_flags=triage_flags,
        )
        equity_value_low = selected_headline.equity_value_low
        equity_value_mid = selected_headline.equity_value_mid
        equity_value_high = selected_headline.equity_value_high
        enterprise_value_low = selected_headline.enterprise_value_low
        enterprise_value_mid = selected_headline.enterprise_value_mid
        enterprise_value_high = selected_headline.enterprise_value_high
        recommended_asking = selected_headline.recommended_asking
        recommended_multiple = selected_headline.recommended_multiple
        multiples_results = selected_headline.multiples_results
        methodology_used = selected_headline.methodology_used
        methodology_selection_reason = selected_headline.methodology_selection_reason
        if selected_headline.resolved_method_key == "dcf":
            dcf_weight, multiples_weight = Decimal("1"), Decimal("0")
        elif selected_headline.resolved_method_key in {
            "ebitda_multiple",
            "omzet_multiple",
            "sde_multiple",
            "arr_multiple",
        }:
            dcf_weight, multiples_weight = Decimal("0"), Decimal("1")
        elif selected_headline.resolved_method_key not in {
            None,
            "upswitch_adaptive",
        }:
            dcf_weight, multiples_weight = Decimal("0"), Decimal("0")

        holding_sotp = (
            holdings_consolidation.get("sotp") if isinstance(holdings_consolidation, dict) else None
        )
        if isinstance(holding_sotp, dict) and holding_sotp.get("available") is True:
            equity_value_low = (
                safe_decimal_or_zero(holding_sotp.get("equity_value_low")) * ownership_multiplier
            ).quantize(Decimal("0.01"))
            equity_value_mid = (
                safe_decimal_or_zero(holding_sotp.get("equity_value_mid")) * ownership_multiplier
            ).quantize(Decimal("0.01"))
            equity_value_high = (
                safe_decimal_or_zero(holding_sotp.get("equity_value_high")) * ownership_multiplier
            ).quantize(Decimal("0.01"))
            if holding_sotp.get("enterprise_value_available") is False:
                # A SOTP made from direct-equity child premises has no coherent
                # aggregate EV bridge. Preserve not-applicable instead of turning
                # absent child EV into a fabricated zero enterprise value.
                enterprise_value_low = None
                enterprise_value_mid = None
                enterprise_value_high = None
            else:
                enterprise_value_low = safe_decimal_or_zero(
                    holding_sotp.get("enterprise_value_low")
                ).quantize(Decimal("0.01"))
                enterprise_value_mid = safe_decimal_or_zero(
                    holding_sotp.get("enterprise_value_mid")
                ).quantize(Decimal("0.01"))
                enterprise_value_high = safe_decimal_or_zero(
                    holding_sotp.get("enterprise_value_high")
                ).quantize(Decimal("0.01"))
            asking_markup = get_asking_price_markup(
                confidence_level.lower(),
                advisor_override_pct=getattr(request, "asking_price_buffer_pct", None),
            )
            recommended_asking = (equity_value_mid * asking_markup).quantize(Decimal("0.01"))
            recommended_multiple = None
            methodology_used = "HOLDING_SOTP"
            methodology_selection_reason = (
                "True holding SOTP selected: each entity has an explicit valuation basis, "
                "ownership share, entity-level tax/bridge treatment and participation elimination."
            )
            dcf_weight = Decimal("0")
            multiples_weight = Decimal("0")
            dcf_exclusion_reason = "Holding SOTP is the primary methodology."
            valuation_results["holding_sotp"] = MethodResult(
                value=equity_value_mid,
                value_low=equity_value_low,
                value_high=equity_value_high,
                label="Holding company SOTP",
                available=True,
                confidence=(
                    "low"
                    if any(
                        bool(row.get("range_is_point_only"))
                        for row in holding_sotp.get("entity_rows", [])
                        if isinstance(row, dict)
                    )
                    else "medium"
                ),
                engine_version=str(holding_sotp.get("version") or "holding_sotp.v1"),
                method_key="holding_sotp",
                details=holding_sotp,
            )
            multiples_results = {
                "holding_sotp": holding_sotp,
                "supporting_operating_valuation": multiples_results,
                "supporting_only": True,
            }
            multiple_build_up_obj = None
            earnings_basis_value = None
            earnings_basis_rationale_value = (
                "Entity-level SOTP; no single consolidated earnings basis drives the headline."
            )

        statutory_fiscal_ebitda = fiscal_reported_ebitda(request)
        fiscal_4x_anchor = build_fiscal_4x_anchor(
            ebitda=(
                float(statutory_fiscal_ebitda) if statutory_fiscal_ebitda is not None else ebitda
            ),
            country_code=request.country_code,
        )
        request_metadata = request.metadata if isinstance(request.metadata, dict) else {}
        public_adaptive_v2 = request_metadata.get("public_adaptive_profile_v2") is True
        if public_adaptive_v2:
            public_adaptive_weighting = bind_public_adaptive_runtime_weights(
                request,
                dcf_weight=dcf_weight,
                multiples_weight=multiples_weight,
            )
            if not public_adaptive_weighting:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "PUBLIC_ADAPTIVE_WEIGHT_BINDING_FAILED",
                        "message": (
                            "Public Adaptive runtime weights could not be bound to "
                            "the verified ValuationIQ capability set."
                        ),
                    },
                )
        else:
            public_adaptive_weighting = public_adaptive_weights_are_authorized(request)
        weighted_valuation_result = build_weighted_valuation_result(
            valuation_results=valuation_results,
            user_weights=getattr(request, "user_weights", None),
            user_weight_justification=getattr(request, "user_weight_justification", None),
            triage_flags=triage_flags,
            logger=logger,
            value_basis=request.headline_value_basis,
            strict_user_weights=request.strict_user_weights,
            # Public Adaptive's strict map authorizes the only methods that may
            # run; it does not promise that every authorized method produces a
            # positive value at every historical checkpoint. Reweight only
            # inside that already verified capability set.
            renormalize_unavailable_weights=public_adaptive_weighting,
            require_positive_values=public_adaptive_weighting,
        )
        if weighted_valuation_result is not None and methodology_used == "HOLDING_SOTP":
            triage_flags.append(
                TriageFlag(
                    field="user_weights",
                    issue="weighted_synthesis_excluded_holding_sotp_primary",
                    severity="warning",
                    value="Holding SOTP is a standalone measurement-date methodology.",
                )
            )
            weighted_valuation_result = None
        elif weighted_valuation_result is not None:
            common_bridge_adjustment = real_estate_surplus + safe_decimal_or_zero(
                bridge_adjustment_data.get("total_net_impact")
                if isinstance(bridge_adjustment_data, dict)
                else None
            )
            synthesis_headline = promote_weighted_synthesis(
                weighted_valuation=weighted_valuation_result,
                valuation_results=valuation_results,
                ownership_multiplier=ownership_multiplier,
                total_debt=safe_decimal_or_zero(total_debt),
                cash=safe_decimal_or_zero(cash),
                nwc_adjustment=safe_decimal_or_zero(nwc_adj_for_omni),
                common_equity_bridge_adjustment=common_bridge_adjustment,
            )
            weighted_valuation_result = synthesis_headline.weighted_valuation
            if public_adaptive_weighting:
                contribution_weights = {
                    str(row.method_key): Decimal(str(row.weight))
                    for row in weighted_valuation_result.contributions
                }
                resolved_dcf_weight = contribution_weights.get("dcf", Decimal("0"))
                resolved_multiples_weight = sum(
                    (
                        weight
                        for method_key, weight in contribution_weights.items()
                        if method_key in {"ebitda_multiple", "omzet_multiple"}
                    ),
                    Decimal("0"),
                )
                resolved_total = resolved_dcf_weight + resolved_multiples_weight
                if abs(resolved_total - Decimal("1")) > Decimal("0.000001"):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "code": "PUBLIC_ADAPTIVE_WEIGHT_RECONCILIATION_FAILED",
                            "message": (
                                "The priced Public Adaptive contributions do not "
                                "reconcile to one complete valuation weight."
                            ),
                        },
                    )
                dcf_weight = resolved_dcf_weight
                multiples_weight = resolved_multiples_weight
            equity_value_low = synthesis_headline.equity_value_low
            equity_value_mid = synthesis_headline.equity_value_mid
            equity_value_high = synthesis_headline.equity_value_high
            enterprise_value_low = synthesis_headline.enterprise_value_low
            enterprise_value_mid = synthesis_headline.enterprise_value_mid
            enterprise_value_high = synthesis_headline.enterprise_value_high
            asking_markup = get_asking_price_markup(
                confidence_level.lower(),
                advisor_override_pct=getattr(request, "asking_price_buffer_pct", None),
            )
            recommended_asking = (equity_value_mid * asking_markup).quantize(Decimal("0.01"))
            recommended_multiple = None
            methodology_used = "WEIGHTED_SYNTHESIS"
            methodology_selection_reason = (
                (
                    "ValuationIQ Adaptive synthesis of the verified public method "
                    "capabilities; runtime readiness and evidence-quality weights "
                    "are applied before the common EV-to-equity bridge."
                )
                if public_adaptive_weighting
                else (
                    "Advisor-weighted synthesis of eligible method equity values; "
                    "the common EV-to-equity bridge is applied once after weighting."
                )
            )

        equity_before_owner_dependency = equity_value_mid
        owner_dependency_request = request
        if (
            isinstance(holding_sotp, dict)
            and holding_sotp.get("available") is True
            and holding_sotp.get("contains_embedded_owner_dependency") is True
            and request.owner_dependency_factors is not None
        ):
            triage_flags.append(
                TriageFlag(
                    field="owner_dependency_factors",
                    issue="holding_level_owner_dependency_suppressed_embedded_child_adjustment",
                    severity="warning",
                    value=(
                        "Canonical child equity ranges already contain owner-dependency "
                        "adjustments; an unscoped holding-level haircut was not applied again."
                    ),
                )
            )
            owner_dependency_request = request.model_copy(update={"owner_dependency_factors": None})
        owner_dependency_state = apply_stateless_owner_dependency(
            request=owner_dependency_request,
            equity_value_low=equity_value_low,
            equity_value_mid=equity_value_mid,
            equity_value_high=equity_value_high,
            recommended_asking_price=recommended_asking,
            risk_factors=risk_factors,
            valuation_results=valuation_results,
        )
        owner_dependency_result = owner_dependency_state.result
        owner_adjustment = owner_dependency_state.adjustment
        equity_value_low = owner_dependency_state.equity_value_low
        equity_value_mid = owner_dependency_state.equity_value_mid
        equity_value_high = owner_dependency_state.equity_value_high
        recommended_asking = owner_dependency_state.recommended_asking_price
        risk_factors = owner_dependency_state.risk_factors
        if weighted_valuation_result is not None:
            pre_shareholder_value = weighted_valuation_result.blended_equity_value
            weighted_valuation_result = weighted_valuation_result.model_copy(
                update={
                    "pre_shareholder_transaction_blended_equity_value": (pre_shareholder_value),
                    "shareholder_transaction_adjustment": (
                        equity_value_mid - pre_shareholder_value
                    ),
                    "blended_equity_value": equity_value_mid,
                    "valuation_range_low": equity_value_low,
                    "valuation_range_high": equity_value_high,
                }
            )
        valuation_summary = generate_valuation_summary(
            company_name=request.company_name,
            equity_value_mid=equity_value_mid,
            methodology=methodology_used,
            confidence_level=confidence_level,
        )

        # Completion is logged only once a response exists (see the end of this
        # function). The publication gates below can still refuse the result;
        # logging "completed" here made every such 422 look like a success.
        calc_status = calculate_stateless_status(triage_flags)

        # BET-434/435 — evidence maturity/defensibility (indicative|defensible)
        # from the trust of the inputs used; this is not a claim of measured accuracy.
        data_tier, data_tier_rationale = derive_data_tier(request)
        # BET-435 — the honest presentation contract for that tier (method + confidence
        # labels + the no-false-precision-headline rule). Additive; never mutates value.
        presentation = _apply_limited_scope_presentation(
            request,
            derive_valuation_presentation(data_tier),
        )
        is_disclosed_fallback = bool(
            isinstance(multiples_results, dict)
            and multiples_results.get("multiples_source") == "DISCLOSED_EXTERNAL_MARKET_FALLBACK"
        )
        if is_disclosed_fallback:
            # A disclosed fallback is permitted only for an explicitly consented
            # advisor workflow.  Financial-history completeness must never turn
            # that absence of a resolved benchmark, empirical percentiles, and
            # comparable transactions into a high-confidence valuation signal.
            # Keep the valuation-confidence contract deterministic and separate
            # from the quality of the supplied operating data.
            confidence_score = 35
            confidence_level = "LOW"
            valuation_summary = generate_valuation_summary(
                company_name=request.company_name,
                equity_value_mid=equity_value_mid,
                methodology=methodology_used,
                confidence_level=confidence_level,
            )
            presentation = replace(
                presentation,
                method_label="Disclosed external market fallback (EV/EBITDA)",
                confidence_label=("Indicative range — disclosed fallback, not benchmark-grounded"),
                disclaimer=(
                    "Uses an explicitly accepted disclosed external fallback; no resolved "
                    "Index contract, empirical percentiles, or transaction evidence."
                ),
            )
            risk_factors = [
                risk
                for risk in risk_factors
                if str(risk).strip().lower() != "no major risk factors identified"
            ]
            risk_factors.append(
                "No resolved benchmark contract; the disclosed external fallback remains indicative."
            )

        # Transaction qualifications are narrative scope controls, not valuation
        # adjustments.  Seal them before the valuation run is created so the
        # canonical report route never accepts a mutable report-time overlay.
        if request.advisor_qualifications:
            risk_factors = list(
                dict.fromkeys(
                    [
                        risk
                        for risk in [*risk_factors, *request.advisor_qualifications]
                        if str(risk).strip().lower() != "no major risk factors identified"
                    ]
                )
            )[:10]

        # BET-627 — the value-up market-context block (M&A-landscape signals) from the
        # resolved benchmark contract + owner-dependency. Never load-bearing: a surprising
        # shape degrades to None, never a 500 on the valuation.
        market_context = _build_safe_stateless_market_context(
            request,
            owner_adjustment=owner_adjustment,
            data_tier=data_tier,
        )

        # Per-year valuation timeline (the value-over-years curve). It is built
        # after the headline public audit below so every historical point can
        # carry an immutable audit for its own fiscal year.
        valuation_timeline = None

        forward_value_cone = build_startup_forward_value_cone(
            request=request,
            valuation_results=valuation_results,
            headline_equity_low=equity_value_low,
            headline_equity_mid=equity_value_mid,
            headline_equity_high=equity_value_high,
        )

        calculation_timestamp = utc_now_iso()
        negative_ebitda_resolution = None
        if normalized_positive(request, input_context.earnings_basis):
            sde_result = valuation_results.get("sde_multiple")
            normalized_primary = (
                "sde"
                if sde_result is not None
                and sde_result.available is True
                and sde_result.value is not None
                else "normalized_ebitda"
            )
            negative_ebitda_resolution = build_normalized_positive_resolution(
                request,
                earnings_basis=input_context.earnings_basis,
                primary_method=normalized_primary,
                cross_check_methods=[
                    key
                    for key in ("dcf", "arr_multiple", "omzet_multiple", "adjusted_nav")
                    if valuation_results.get(key) is not None
                    and valuation_results[key].available is True
                ],
                valuation_results=valuation_results,
                headline_equity=(equity_value_low, equity_value_mid, equity_value_high),
                headline_enterprise=(
                    (
                        enterprise_value_low,
                        enterprise_value_mid,
                        enterprise_value_high,
                    )
                    if enterprise_value_low is not None
                    and enterprise_value_mid is not None
                    and enterprise_value_high is not None
                    else None
                ),
                evaluated_at=datetime.fromisoformat(calculation_timestamp.replace("Z", "+00:00")),
            )
            # The immutable resolution is the report and response authority for
            # negative-reported / normalized-positive cases as well as recovery cases.
            equity_value_low = negative_ebitda_resolution.headline_equity_value_low
            equity_value_mid = negative_ebitda_resolution.headline_equity_value_mid
            equity_value_high = negative_ebitda_resolution.headline_equity_value_high
            enterprise_value_low = negative_ebitda_resolution.headline_enterprise_value_low
            enterprise_value_mid = negative_ebitda_resolution.headline_enterprise_value_mid
            enterprise_value_high = negative_ebitda_resolution.headline_enterprise_value_high
        # Method selection can promote a revenue multiple after the generic
        # headline build-up has populated an EBITDA basis.  The selected
        # method is the numeric authority, so keep the response and immutable
        # public audit semantics aligned with the calculation that actually
        # won.
        selected_methodology = str(methodology_used or "").strip().upper()
        if selected_methodology in {"OMZET_MULTIPLE", "REVENUE_MULTIPLE"}:
            earnings_basis_value = "REVENUE"
            earnings_basis_rationale_value = "selected_revenue_multiple"
        elif selected_methodology == "EBITDA_MULTIPLE":
            earnings_basis_value = "EBITDA"
            earnings_basis_rationale_value = "selected_ebitda_multiple"
        public_audit_failure_reasons: list[str] = []
        public_audit_failure_diagnostics: list[dict[str, object]] = []
        public_valuation_audit = build_public_valuation_audit(
            request=request,
            calculation_timestamp=calculation_timestamp,
            equity_value_low=equity_value_low,
            equity_value_mid=equity_value_mid,
            equity_value_high=equity_value_high,
            enterprise_value_low=enterprise_value_low,
            enterprise_value_mid=enterprise_value_mid,
            enterprise_value_high=enterprise_value_high,
            methodology_used=methodology_used,
            dcf_weight=dcf_weight,
            multiples_weight=multiples_weight,
            dcf_results=dcf_results,
            weighted_valuation_result=weighted_valuation_result,
            dcf_exclusion_reason=dcf_exclusion_reason,
            earnings_basis=earnings_basis_value,
            recommended_multiple=recommended_multiple,
            multiple_build_up=multiple_build_up_obj,
            confidence_level=confidence_level,
            size_discount=size_discount,
            liquidity_discount=liquidity_discount,
            country_adjustment=country_adjustment,
            failure_reasons=public_audit_failure_reasons,
            failure_diagnostics=public_audit_failure_diagnostics,
        )
        if (
            public_valuation_audit is None
            and isinstance(request.metadata, dict)
            and request.metadata.get("public_adaptive_profile_v2") is True
            and request.metadata.get("public_adaptive_modeled_forecast_point") is not True
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "PUBLIC_ADAPTIVE_AUDIT_UNRECONCILED",
                    "message": (
                        "Public Adaptive could not reconcile its numeric result "
                        "to the contributed official evidence."
                    ),
                    "failed_controls": sorted(set(public_audit_failure_reasons)),
                    # Which filing line failed and why, e.g. a used revenue
                    # line whose source is not a governed official registry.
                    "control_diagnostics": public_audit_failure_diagnostics,
                },
            )
        if request.headline_value_basis == "enterprise_value":
            public_enterprise_band = _public_audit_enterprise_band(public_valuation_audit)
            if public_enterprise_band is not None:
                (
                    enterprise_value_low,
                    enterprise_value_mid,
                    enterprise_value_high,
                ) = public_enterprise_band
        if getattr(request, "include_valuation_timeline", False):
            try:
                from src.services.reports.stateless_valuation_timeline import (
                    build_valuation_timeline,
                )

                valuation_timeline = build_valuation_timeline(
                    request=request,
                    headline_equity_low=equity_value_low,
                    headline_equity_mid=equity_value_mid,
                    headline_equity_high=equity_value_high,
                    headline_enterprise_value_low=enterprise_value_low,
                    headline_enterprise_value_mid=enterprise_value_mid,
                    headline_enterprise_value_high=enterprise_value_high,
                    headline_methodology_used=methodology_used,
                    headline_confidence_level=confidence_level,
                    headline_confidence_score=confidence_score,
                    logger=logger,
                    headline_audit_snapshot=public_valuation_audit,
                )
            except Exception:
                logger.warning(
                    "valuation_timeline build failed (non-fatal)",
                    extra={"valuation_id": request.valuation_id},
                    exc_info=True,
                )

        is_timeline_subrequest = bool(
            isinstance(request.metadata, dict)
            and request.metadata.get("valuation_timeline_subrequest") is True
        )
        is_public_adaptive_v2 = bool(
            isinstance(request.metadata, dict)
            and request.metadata.get("public_adaptive_profile_v2") is True
        )
        reconciled_public_modeled_dcf = bool(
            isinstance(public_valuation_audit, dict)
            and isinstance(public_valuation_audit.get("modeled_dcf"), dict)
        )
        if (
            forward_value_cone is None
            and not is_timeline_subrequest
            and (
                (
                    public_modeled_dcf_is_authorized(request)
                    and (not is_public_adaptive_v2 or reconciled_public_modeled_dcf)
                )
                or any(
                    row.is_forecast and row.year > request.current_year.year
                    for row in request.historical_years
                )
            )
        ):
            cone_timeline = valuation_timeline
            if cone_timeline is None:
                try:
                    from src.services.reports.stateless_valuation_timeline import (
                        build_valuation_timeline,
                    )

                    cone_timeline = build_valuation_timeline(
                        request=request,
                        headline_equity_low=equity_value_low,
                        headline_equity_mid=equity_value_mid,
                        headline_equity_high=equity_value_high,
                        headline_enterprise_value_low=enterprise_value_low,
                        headline_enterprise_value_mid=enterprise_value_mid,
                        headline_enterprise_value_high=enterprise_value_high,
                        headline_methodology_used=methodology_used,
                        headline_confidence_level=confidence_level,
                        headline_confidence_score=confidence_score,
                        logger=logger,
                        headline_audit_snapshot=public_valuation_audit,
                    )
                except (ArithmeticError, ImportError, KeyError, TypeError, ValueError):
                    logger.warning(
                        "forward_value_cone timeline build failed (non-fatal)",
                        extra={"valuation_id": request.valuation_id},
                        exc_info=True,
                    )
                    cone_timeline = None
            forward_value_cone = build_explicit_forecast_forward_cone(
                request=request,
                timeline=cone_timeline,
            )

        value_driver_ledger = build_value_driver_ledger(
            earnings_basis_ledger=input_context.earnings_basis,
            multiple_build_up=multiple_build_up_obj,
            equity_bridge_adjustments=bridge_adjustment_data,
            holdings_consolidation=holdings_consolidation,
            owner_dependency_result=owner_dependency_result,
            owner_dependency_adjustment=safe_decimal_or_zero(owner_adjustment),
            ownership_percentage=ownership_percentage,
            equity_before_owner_dependency=equity_before_owner_dependency,
            equity_after_owner_dependency=equity_value_mid,
            canonical_enterprise_value=enterprise_value_mid,
            methodology_used=methodology_used,
        )
        from .enterprise_only_publication import enterprise_only_publication

        enterprise_publication = enterprise_only_publication(
            request=request,
            completion_accounts=completion_accounts,
            enterprise_value_mid=enterprise_value_mid,
            financial_metrics=financial_metrics,
            method_results=valuation_results,
            multiple_build_up=multiple_build_up_obj,
            weighted_valuation=weighted_valuation_result,
            driver_ledger=value_driver_ledger,
            dcf_results=dcf_results,
            multiples_results=multiples_results,
            public_audit=public_valuation_audit,
            negative_resolution=negative_ebitda_resolution,
        )
        if enterprise_publication is not None:
            financial_metrics = enterprise_publication.financial_metrics
            valuation_results = enterprise_publication.method_results
            multiple_build_up_obj = enterprise_publication.multiple_build_up
            value_driver_ledger = enterprise_publication.driver_ledger
            dcf_results = enterprise_publication.dcf_results
            multiples_results = enterprise_publication.multiples_results
            public_valuation_audit = enterprise_publication.public_audit
            negative_ebitda_resolution = enterprise_publication.negative_resolution
            bridge_adjustment_data = enterprise_publication.bridge_adjustments
            equity_value_low = equity_value_mid = equity_value_high = None
            recommended_asking = None
            weighted_valuation_result = valuation_timeline = forward_value_cone = None
            calc_status = "WARNINGS"
            valuation_summary = "Indicative enterprise value; shareholder value awaits verified completion accounts."
            triage_flags.append(enterprise_publication.triage_flag)
        valuation_run = build_stateless_valuation_run(
            request=request,
            verified_titan_request_wire_commitment=verified_titan_request_wire_commitment,
            calculation_timestamp=calculation_timestamp,
            equity_values={
                "low": equity_value_low,
                "mid": equity_value_mid,
                "high": equity_value_high,
            },
            enterprise_values={
                "low": enterprise_value_low,
                "mid": enterprise_value_mid,
                "high": enterprise_value_high,
            },
            methodology_used=methodology_used,
            dcf_weight=safe_decimal_or_zero(dcf_weight),
            multiples_weight=safe_decimal_or_zero(multiples_weight),
            valuation_results=valuation_results,
            benchmark_contract=(benchmark_contract if benchmark_contract_resolved else None),
            triage_flags=triage_flags,
            driver_ledger=value_driver_ledger,
            public_valuation_audit=public_valuation_audit,
            valuation_timeline=valuation_timeline,
            forward_value_cone=forward_value_cone,
            weighted_valuation=weighted_valuation_result,
            financial_metrics=financial_metrics,
            dcf_results=dcf_results,
            multiples_results=multiples_results,
            response_snapshot={
                "recommended_asking_price": recommended_asking,
                "recommended_multiple": recommended_multiple,
                "methodology_selection_reason": methodology_selection_reason,
                "dcf_exclusion_reason": dcf_exclusion_reason,
                "confidence_level": confidence_level,
                "confidence_score": confidence_score,
                "earnings_basis": earnings_basis_value,
                "earnings_basis_rationale": earnings_basis_rationale_value,
                "multiple_build_up": multiple_build_up_obj,
                "earnings_basis_ledger": input_context.earnings_basis,
                "equity_bridge_adjustments": bridge_adjustment_data,
                "holdings_consolidation": holdings_consolidation,
                "size_discount": safe_decimal_or_zero(size_discount),
                "liquidity_discount": safe_decimal_or_zero(liquidity_discount),
                "owner_dependency_adjustment": safe_decimal_or_zero(owner_adjustment),
                "owner_dependency_result": owner_dependency_result,
                "country_adjustment": safe_decimal_or_zero(country_adjustment),
                "total_adjustment": total_adjustment,
                "nwc_normalization": nwc_normalization_data,
                "trial_balance_anomalies": trial_balance_anomalies,
                "valuation_summary": valuation_summary,
                "key_value_drivers": value_drivers,
                "risk_factors": risk_factors,
                "fiscal_4x_anchor": fiscal_4x_anchor,
                "data_quality": data_quality,
                "data_tier": data_tier,
                "data_tier_rationale": data_tier_rationale,
                "publication_allowed": False,
                "publication_blocked": True,
                "report_readiness_state": "calculation_uncertified",
                "defensibility_review_state": (
                    "approved" if data_tier in {"defensible", "attested"} else "review_required"
                ),
                "valuation_method_label": presentation.method_label,
                "confidence_label": presentation.confidence_label,
                "present_point_estimate": presentation.present_point_estimate,
                "valuation_disclaimer": presentation.disclaimer,
                "market_context": market_context,
                "public_valuation_audit": public_valuation_audit,
                "public_method_resolution": None,
                "negative_ebitda_resolution": (
                    negative_ebitda_resolution.model_dump(mode="json")
                    if negative_ebitda_resolution is not None
                    else None
                ),
            },
        )

        from .value_basis_admission import uses_accounting_basis_policy

        sealed_source_projection = uses_accounting_basis_policy(request)
        response = CalculateResponse(
            status=calc_status,
            valuation_id=request.valuation_id,
            calculation_timestamp=calculation_timestamp,
            valuation_run=valuation_run,
            equity_value_low=equity_value_low,
            equity_value_mid=equity_value_mid,
            equity_value_high=equity_value_high,
            enterprise_value_low=enterprise_value_low,
            enterprise_value_mid=enterprise_value_mid,
            enterprise_value_high=enterprise_value_high,
            recommended_asking_price=recommended_asking,
            recommended_multiple=recommended_multiple,
            triage_flags=triage_flags,
            artifacts=None,  # Artifacts generated separately via /generate-report
            methodology_used=methodology_used,
            dcf_weight=dcf_weight,
            multiples_weight=multiples_weight,
            methodology_selection_reason=methodology_selection_reason,
            dcf_exclusion_reason=dcf_exclusion_reason,
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            financial_metrics=financial_metrics,
            # Expose the exact transport-stable payload committed in the run so
            # API, timeline and report consumers cannot observe divergent DCF
            # representations of the same calculation.
            dcf_results=valuation_run.dcf_results,
            multiples_results=(
                valuation_run.multiples_results if sealed_source_projection else multiples_results
            ),
            earnings_basis=earnings_basis_value,
            earnings_basis_rationale=earnings_basis_rationale_value,
            multiple_build_up=multiple_build_up_obj,
            earnings_basis_ledger=(
                valuation_run.response_snapshot.get("earnings_basis_ledger")
                if sealed_source_projection
                else input_context.earnings_basis
            ),
            equity_bridge_adjustments=(
                valuation_run.response_snapshot.get("equity_bridge_adjustments")
                if sealed_source_projection
                else bridge_adjustment_data
            ),
            holdings_consolidation=(
                valuation_run.response_snapshot.get("holdings_consolidation")
                if sealed_source_projection
                else holdings_consolidation
            ),
            value_driver_ledger=(
                valuation_run.driver_ledger if sealed_source_projection else value_driver_ledger
            ),
            size_discount=safe_decimal_or_zero(size_discount),
            liquidity_discount=safe_decimal_or_zero(liquidity_discount),
            owner_dependency_adjustment=safe_decimal_or_zero(owner_adjustment),
            owner_dependency_result=owner_dependency_result,
            country_adjustment=safe_decimal_or_zero(country_adjustment),
            total_adjustment=total_adjustment,
            nwc_normalization=nwc_normalization_data,
            trial_balance_anomalies=trial_balance_anomalies,
            valuation_summary=valuation_summary,
            key_value_drivers=value_drivers,
            risk_factors=risk_factors,
            # The request schema rejects use_monte_carlo=True until a seeded,
            # governed simulation policy is certified. Never imply a run occurred.
            monte_carlo_results=None,
            valuation_results=valuation_results,
            weighted_valuation=weighted_valuation_result,
            fiscal_4x_anchor=fiscal_4x_anchor,
            data_quality=data_quality,
            data_tier=data_tier,
            data_tier_rationale=data_tier_rationale,
            publication_allowed=False,
            publication_blocked=True,
            report_readiness_state="calculation_uncertified",
            defensibility_review_state=(
                "approved" if data_tier in {"defensible", "attested"} else "review_required"
            ),
            valuation_method_label=presentation.method_label,
            confidence_label=presentation.confidence_label,
            present_point_estimate=presentation.present_point_estimate,
            valuation_disclaimer=presentation.disclaimer,
            market_context=market_context,
            public_valuation_audit=public_valuation_audit,
            public_method_resolution=None,
            negative_ebitda_resolution=negative_ebitda_resolution,
            valuation_timeline=valuation_timeline,
            forward_value_cone=forward_value_cone,
        )
        logger.info(
            "Stateless calculate completed",
            extra={
                "valuation_id": request.valuation_id,
                "equity_value_mid": _loggable_amount(response.equity_value_mid),
                "enterprise_value_mid": _loggable_amount(response.enterprise_value_mid),
                "elapsed_ms": int((time.time() - start_time) * 1000),
                "omni_calc_methods": len(valuation_results),
            },
        )
        return response

    except HTTPException as refusal:
        _log_stateless_refusal(request, refusal)
        raise
    except Exception as e:
        logger.error(
            "Stateless calculate failed",
            extra={
                "valuation_id": request.valuation_id,
                "error": str(e),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Calculation failed. Please check your input and try again.",
        )
