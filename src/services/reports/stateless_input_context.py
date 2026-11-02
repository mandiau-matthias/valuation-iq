"""Input-context preparation for stateless valuation calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from src.api.schemas.stateless_api import BusinessTypeCalibration, CalculateRequest, TriageFlag
from src.domain.asset_based_support import normalize_business_model
from src.domain.revenue_growth import revenue_growth
from src.services.reports.stateless_balance_sheet import build_balance_sheet_payload
from src.services.reports.stateless_advisor_override_governance import (
    apply_advisor_override_governance,
)
from src.services.reports.stateless_benchmark_policy import (
    JsonMap,
    extract_stateless_benchmark_contract,
    request_allows_untrusted_multiples_fallback,
)
from src.services.reports.stateless_calculation_helpers import (
    convert_year_data,
    filter_usable_actual_years,
    maybe_reanchor_placeholder_current_year,
)
from src.services.reports.stateless_earnings_basis import resolve_stateless_earnings_basis
from src.services.reports.stateless_holdings import apply_stateless_holdings_consolidation
from src.services.reports.stateless_method_weight_governance import (
    apply_method_weight_governance,
)
from src.services.reports.stateless_owner_salary import (
    apply_modelled_owner_normalization,
    build_modelled_sde_basis,
    build_weighted_sde_basis,
)
from src.services.reports.stateless_real_estate import apply_stateless_real_estate_perimeter
from src.utils.decimal_helpers import float_or_none, safe_decimal_or_zero, safe_float


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...

    def warning(self, msg: str, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class StatelessInputContext:
    request: CalculateRequest
    triage_flags: list[TriageFlag]
    current_year_data: dict[str, object]
    historical_data: list[dict[str, object]]
    normalized_business_model: str
    trial_balance_anomalies: dict[str, object] | None
    calibration: BusinessTypeCalibration
    business_type_mix: list[dict[str, object]]
    business_type_weights: dict[str, object]
    primary_business_type_id: str
    business_type_mix_policy: str
    benchmark_contract: JsonMap | None
    allow_untrusted_multiples_fallback: bool
    multiples_context: dict[str, object]
    economic_context: dict[str, object]
    revenue: float
    ebitda: float
    earnings_basis: dict[str, object]
    ebitda_margin: float
    revenue_growth: Decimal
    revenue_growth_evidence: dict[str, object]
    revenue_cagr_3y_evidence: dict[str, object]
    balance_sheet: dict[str, object]
    activity_code: str
    ownership_percentage: Decimal
    ownership_multiplier: Decimal
    holdings_consolidation: dict[str, object] | None


def prepare_stateless_input_context(
    *,
    request: CalculateRequest,
    logger: LoggerLike,
    parent_public_owner_operated_classification: str | None = None,
) -> StatelessInputContext:
    """Normalize request inputs used by the stateless calculation orchestration."""
    triage_flags: list[TriageFlag] = []
    request, override_flags = apply_advisor_override_governance(request)
    triage_flags.extend(override_flags)
    request, weight_flags = apply_method_weight_governance(request)
    triage_flags.extend(weight_flags)
    valuation_case = request.valuation_case
    if (
        valuation_case is not None
        and valuation_case.accounting_evidence is not None
        and valuation_case.accounting_evidence_attachment == "unattached_non_priced"
    ):
        triage_flags.append(
            TriageFlag(
                field="valuation_case.accounting_evidence",
                issue="accounting_evidence_package_unattached_non_priced",
                severity="warning",
            )
        )
    request = _maybe_reanchor_request(request=request, triage_flags=triage_flags, logger=logger)
    request, holdings_consolidation, holding_flags = apply_stateless_holdings_consolidation(request)
    triage_flags.extend(holding_flags)
    request, real_estate_flags = apply_stateless_real_estate_perimeter(request)
    triage_flags.extend(real_estate_flags)
    if request.owner_dependency is not None:
        # Legacy chat scores have no evidence/decision contract and must never
        # alter WACC or an SDE multiple. The governed twelve-factor result is the
        # sole priced path and is applied once at the disclosed equity layer.
        triage_flags.append(
            TriageFlag(
                field="owner_dependency",
                issue="legacy_owner_dependency_scenario_only_unverified",
                severity="warning",
            )
        )
        request = request.model_copy(update={"owner_dependency": None})

    current_year_data = convert_year_data(request.current_year)
    usable_historical_years = filter_usable_actual_years(request.historical_years)
    actual_year_count = sum(not year.is_forecast for year in request.historical_years)
    dropped_historical_years = actual_year_count - len(usable_historical_years)
    if dropped_historical_years > 0:
        logger.info(
            "Dropped unusable stateless historical rows before calculation",
            extra={
                "valuation_id": request.valuation_id,
                "company_name": request.company_name,
                "dropped_count": dropped_historical_years,
                "remaining_count": len(usable_historical_years),
            },
        )
    historical_data = [convert_year_data(year) for year in usable_historical_years]
    earnings_basis_resolution = resolve_stateless_earnings_basis(request)
    earnings_basis = earnings_basis_resolution.to_payload()
    earnings_basis = _maybe_charge_modelled_owner_pay(
        request,
        earnings_basis,
        parent_classification=parent_public_owner_operated_classification,
    )
    earnings_basis["sde_basis"] = _resolve_sde_basis(request, earnings_basis)
    triage_flags.extend(earnings_basis_resolution.triage_flags)
    normalized_business_model = normalize_business_model(request.business_model).value
    trial_balance_anomalies = _scan_trial_balance_anomalies(
        request=request,
        current_year_data=current_year_data,
        historical_data=historical_data,
        logger=logger,
    )

    calibration = request.business_type_calibration
    business_type_mix = list(request.business_type_mix or [])
    business_type_weights = dict(request.business_type_weights or {})
    primary_business_type_id = (
        str(business_type_mix[0].get("business_type_id"))
        if business_type_mix and isinstance(business_type_mix[0], dict)
        else calibration.business_type_id
    )
    business_type_mix_policy = (
        "weighted_business_type_mix" if len(business_type_mix) > 1 else "single_business_type"
    )
    benchmark_contract = extract_stateless_benchmark_contract(request)
    allow_untrusted_multiples_fallback = request_allows_untrusted_multiples_fallback(request)
    multiples_context = {
        "ev_ebitda_median": safe_float(calibration.ev_ebitda_median),
        "ev_ebitda_p25": float_or_none(calibration.ev_ebitda_p25),
        "ev_ebitda_p75": float_or_none(calibration.ev_ebitda_p75),
        "ev_revenue_median": float_or_none(calibration.ev_revenue_median),
        "typical_ebitda_margin": float_or_none(calibration.typical_ebitda_margin),
        "dcf_preference": safe_float(calibration.dcf_preference) or 0.5,
        "multiples_preference": safe_float(calibration.multiples_preference) or 0.5,
    }

    economic = request.economic_context
    economic_context = economic.model_dump() if hasattr(economic, "model_dump") else dict(economic)
    revenue = safe_float(request.current_year.revenue)
    # Read from the payload, not the resolution: a modelled owner-pay charge is
    # applied to the payload above and must reach the multiple that prices it.
    ebitda = safe_float(earnings_basis.get("normalized_ebitda"))
    current_normalized_ebitda = safe_float(earnings_basis.get("current_normalized_ebitda"))
    ebitda_margin = current_normalized_ebitda / revenue if revenue > 0 else 0
    latest_growth = revenue_growth(request.current_year, usable_historical_years)
    three_year_growth = revenue_growth(
        request.current_year, usable_historical_years, horizon="three_year"
    )
    if latest_growth.reason is not None:
        triage_flags.append(
            TriageFlag(
                field="revenue_growth",
                issue="revenue_growth_unavailable",
                severity="info",
                value=latest_growth.to_payload(),
            )
        )
    balance_sheet = build_balance_sheet_payload(request.current_year)
    activity_code = extract_activity_code_from_request(request)
    ownership_percentage = (
        request.shares_for_sale if request.shares_for_sale is not None else Decimal("100")
    )
    ownership_multiplier = ownership_percentage / Decimal("100")

    return StatelessInputContext(
        request=request,
        triage_flags=triage_flags,
        current_year_data=current_year_data,
        historical_data=historical_data,
        normalized_business_model=normalized_business_model,
        trial_balance_anomalies=trial_balance_anomalies,
        calibration=calibration,
        business_type_mix=business_type_mix,
        business_type_weights=business_type_weights,
        primary_business_type_id=primary_business_type_id,
        business_type_mix_policy=business_type_mix_policy,
        benchmark_contract=benchmark_contract,
        allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
        multiples_context=multiples_context,
        economic_context=economic_context,
        revenue=revenue,
        ebitda=ebitda,
        earnings_basis=earnings_basis,
        ebitda_margin=ebitda_margin,
        revenue_growth=latest_growth.rate if latest_growth.rate is not None else Decimal("0"),
        revenue_growth_evidence=latest_growth.to_payload(),
        revenue_cagr_3y_evidence=three_year_growth.to_payload(),
        balance_sheet=balance_sheet,
        activity_code=activity_code,
        ownership_percentage=ownership_percentage,
        ownership_multiplier=ownership_multiplier,
        holdings_consolidation=holdings_consolidation,
    )


def extract_activity_code_from_request(request: CalculateRequest) -> str:
    for attr in ("canonical_nace_code", "nace_code", "activity_code"):
        normalized = _normalize_activity_code(getattr(request, attr, None))
        if normalized:
            return normalized

    business_context = getattr(request, "business_context", None)
    if isinstance(business_context, dict):
        for key in ("canonical_nace_code", "nace_code", "activity_code"):
            normalized = _normalize_activity_code(business_context.get(key))
            if normalized:
                return normalized

    return ""


def _maybe_reanchor_request(
    *,
    request: CalculateRequest,
    triage_flags: list[TriageFlag],
    logger: LoggerLike,
) -> CalculateRequest:
    reanchored_current, reanchored_history, reanchor = maybe_reanchor_placeholder_current_year(
        request.current_year, request.historical_years
    )
    if reanchor is None:
        return request

    request = request.model_copy(
        update={
            "current_year": reanchored_current,
            "historical_years": reanchored_history,
        }
    )
    triage_flags.append(
        TriageFlag(
            field="current_year",
            issue="placeholder_current_year_reanchored",
            severity="warning",
            value=reanchor["from_year"],
            benchmark=reanchor["to_year"],
        )
    )
    logger.info(
        "Re-anchored placeholder current year onto latest usable closed year",
        extra={
            "valuation_id": request.valuation_id,
            "company_name": request.company_name,
            "from_year": reanchor["from_year"],
            "to_year": reanchor["to_year"],
        },
    )
    return request


def _scan_trial_balance_anomalies(
    *,
    request: CalculateRequest,
    current_year_data: dict[str, object],
    historical_data: list[dict[str, object]],
    logger: LoggerLike,
) -> dict[str, object] | None:
    try:
        from src.domain.trial_balance_anomaly_scanner import TrialBalanceAnomalyScanner

        if len(historical_data) >= 2:
            anomaly_result = TrialBalanceAnomalyScanner(z_threshold=2.0, min_years=3).scan(
                historical_data,
                current_year_data,
            )
            return anomaly_result.to_dict()
    except Exception as exc:
        logger.warning(
            "Stateless trial balance anomaly scan failed",
            extra={
                "valuation_id": request.valuation_id,
                "company_name": request.company_name,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
        return {
            "anomaly_detected": False,
            "scan_error": True,
        }
    return None


def _normalize_activity_code(code: object | None) -> str:
    if code is None:
        return ""
    raw = str(code).strip()
    if not raw:
        return ""
    return raw.replace(" ", "")


def _resolve_sde_basis(request: object, earnings_basis: dict[str, object]) -> dict[str, object]:
    """Governed owner compensation first; modelled for the public owner-operated class.

    The filed basis is always attempted and always wins. Where it cannot apply,
    a PUBLIC run falls back to the modelled owner-operated basis: those filings
    will never disclose owner pay, so a filed figure is not a thing that can
    arrive later. Advisor and owner flows are deliberately excluded — they have
    a trial balance, and an assumption must never displace evidence that exists.

    The modelled result carries `disclosure_required`, and the surface that
    publishes it has to say the owner's pay is assumed rather than reported.
    """
    governed = build_weighted_sde_basis(earnings_basis)
    if governed.get("available") is True:
        return governed

    # `public_adaptive_profile_v2` is Titan's marker that this is a public run,
    # and it is on the request before the profile executes. (The richer
    # `public_modeled_dcf_is_authorized` reads resolution state the profile
    # writes later, so it is not yet true at input-context time.)
    metadata = request.metadata if isinstance(getattr(request, "metadata", None), dict) else {}
    if metadata.get("public_adaptive_profile_v2") is not True:
        return governed

    actual_years = [
        year
        for year in [request.current_year, *(getattr(request, "historical_years", None) or [])]
        if not getattr(year, "is_forecast", False)
    ]
    if not actual_years:
        return governed
    # Recency weighting by FISCAL YEAR, not by position in the request — the
    # current year is transported first and the historical rows behind it in
    # whatever order the caller sent, so ranking by position silently weights an
    # older filing above a newer one. Normalized to sum to 1, the same
    # convention the governed basis uses, so both yield a weighted average.
    ordered = sorted(actual_years, key=lambda year: getattr(year, "year", 0))
    raw_weights = [Decimal(index + 1) for index in range(len(ordered))]
    total_weight = sum(raw_weights)
    rows = [
        {
            "fiscal_year": getattr(year, "year", None),
            "gross_margin": getattr(year, "gross_margin", None),
            "ebitda": getattr(year, "ebitda", None),
            "weight": raw_weight / total_weight,
        }
        for year, raw_weight in zip(ordered, raw_weights)
    ]
    modelled = build_modelled_sde_basis(rows)
    return modelled if modelled.get("available") is True else governed


def _maybe_charge_modelled_owner_pay(
    request: object,
    earnings_basis: dict[str, object],
    *,
    parent_classification: str | None = None,
) -> dict[str, object]:
    """Deduct market-rate owner pay on a public owner-operated run.

    Public filings for this class expense nothing for the person doing the
    work, so an unadjusted multiple prices earnings no buyer can keep. Advisor
    and owner flows are untouched: they can state the real figure.
    """
    metadata = request.metadata if isinstance(getattr(request, "metadata", None), dict) else {}
    if metadata.get("public_adaptive_profile_v2") is not True:
        return earnings_basis
    if parent_classification == "not_owner_operated":
        return earnings_basis
    return apply_modelled_owner_normalization(request, earnings_basis)
