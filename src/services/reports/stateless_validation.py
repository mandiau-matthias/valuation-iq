"""Validation rules for stateless calculation requests."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.api.schemas.stateless_api import ValidateRequest, ValidateResponse, ValidationWarning
from src.domain.asset_based_support import has_sufficient_asset_inputs
from src.services.reports.stateless_balance_sheet import build_balance_sheet_payload
from src.services.reports.stateless_benchmark_policy import (
    as_mapping,
    benchmark_contract_is_resolved,
    benchmark_metric_available,
    has_positive_calibration_multiple,
    missing_required_benchmark_provenance,
)
from src.services.reports.stateless_calculation_helpers import (
    maybe_reanchor_placeholder_current_year,
)
from src.utils.decimal_helpers import safe_decimal_or_zero, safe_float


@dataclass(frozen=True)
class BenchmarkValidationContext:
    calibration: object | None
    contract_complete: bool
    contract_authorizes_ebitda: bool
    requires_multiple_benchmark: bool
    fallback_allowed: bool
    governed_external_reference: bool


def _reanchored_request(
    request: ValidateRequest,
) -> tuple[ValidateRequest, ValidationWarning | None]:
    reanchored_current, reanchored_history, reanchor = maybe_reanchor_placeholder_current_year(
        request.current_year, request.historical_years
    )
    if reanchor is None:
        return request, None

    return request.model_copy(
        update={
            "current_year": reanchored_current,
            "historical_years": reanchored_history,
        }
    ), ValidationWarning(
        field="current_year",
        code="PLACEHOLDER_CURRENT_YEAR_REANCHORED",
        message=(
            f"Fiscal year {reanchor['from_year']} has no booked figures yet; "
            f"the valuation will be based on the latest closed year {reanchor['to_year']}."
        ),
        severity="info",
        suggestion="Sync or enter figures for the current fiscal year to value off fresher data.",
    )


def _revenue_ok_without_turnover(request: ValidateRequest) -> bool:
    balance_sheet = build_balance_sheet_payload(request.current_year)
    return has_sufficient_asset_inputs(balance_sheet) or (
        request.methodology is not None and str(request.methodology).upper() == "ASSET_BASED"
    )


def _validate_revenue(
    *,
    request: ValidateRequest,
    warnings: list[ValidationWarning],
    missing_required: list[str],
) -> None:
    if request.current_year.revenue > 0:
        return

    if _revenue_ok_without_turnover(request):
        warnings.append(
            ValidationWarning(
                field="revenue",
                code="ZERO_TURNOVER_ASSET_PATH",
                message=(
                    "Turnover is €0. Revenue-based multiples (e.g. EV/Revenue) are not applicable; "
                    "use asset-based (Gecorrigeerde Netto Activa) or EBITDA-based methods as appropriate."
                ),
                severity="info",
                suggestion="Ensure balance-sheet fields are complete for adjusted NAV.",
            )
        )
        return

    missing_required.append("revenue")
    warnings.append(
        ValidationWarning(
            field="revenue",
            code="MISSING_REVENUE",
            message=(
                "Turnover is zero or missing. Provide positive revenue for revenue-based multiples, "
                "or supply sufficient balance sheet data (total assets and liabilities) for asset-based valuation, "
                "or set methodology to ASSET_BASED."
            ),
            severity="error",
        )
    )


def _warn_negative_ebitda(request: ValidateRequest, warnings: list[ValidationWarning]) -> None:
    if request.current_year.ebitda <= 0:
        warnings.append(
            ValidationWarning(
                field="ebitda",
                code="NEGATIVE_EBITDA",
                message="EBITDA is negative or zero. DCF valuation may be limited.",
                severity="warning",
                suggestion="Consider using multiples-only methodology",
            )
        )


def _warn_limited_history(
    *,
    request: ValidateRequest,
    warnings: list[ValidationWarning],
    missing_optional: list[str],
) -> None:
    if len(request.historical_years) < 2:
        warnings.append(
            ValidationWarning(
                field="historical_years",
                code="LIMITED_HISTORY",
                message="Less than 2 years of historical data. Growth projections may be less reliable.",
                severity="info",
                suggestion="Provide at least 2-3 years of historical data for better accuracy",
            )
        )
        missing_optional.append("historical_years")


def _benchmark_validation_context(
    *,
    request: ValidateRequest,
    revenue: float,
) -> BenchmarkValidationContext:
    calibration = request.business_type_calibration
    benchmark_contract = (
        as_mapping(getattr(calibration, "benchmark_contract", None)) if calibration else None
    )
    benchmark_contract_complete = benchmark_contract_is_resolved(
        benchmark_contract
    ) and not missing_required_benchmark_provenance(benchmark_contract)
    benchmark_contract_authorizes_ebitda = (
        benchmark_contract_complete
        and benchmark_metric_available(
            benchmark_contract,
            ("ev_ebitda", "ev_ebitda_multiple", "ebitda_multiple"),
        )
    )

    requires = (
        calibration is not None
        and has_positive_calibration_multiple(calibration)
        and str(request.methodology or "HYBRID").upper() not in {"DCF", "ASSET_BASED"}
        and revenue > 0
    )
    return BenchmarkValidationContext(
        calibration=calibration,
        contract_complete=benchmark_contract_complete,
        contract_authorizes_ebitda=benchmark_contract_authorizes_ebitda,
        requires_multiple_benchmark=requires,
        fallback_allowed=bool(request.allow_untrusted_multiples_fallback),
        governed_external_reference=(
            request.external_market_reference_contract is not None
        ),
    )


def _validate_benchmark_contract(
    *,
    context: BenchmarkValidationContext,
    warnings: list[ValidationWarning],
    missing_required: list[str],
) -> None:
    if not context.requires_multiple_benchmark:
        return

    if not context.contract_complete:
        if context.governed_external_reference:
            warnings.append(
                ValidationWarning(
                    field="external_market_reference_contract",
                    code="GOVERNED_EXTERNAL_MARKET_REFERENCE",
                    message=(
                        "A reviewed, hash-sealed external EV/EBITDA reference authorizes "
                        "the market method for this dossier. It is non-statistical and "
                        "is not an Upswitch Index benchmark."
                    ),
                    severity="warning",
                    suggestion=(
                        "Retain the source contract, reviewer identity and limitations "
                        "with the immutable valuation evidence."
                    ),
                )
            )
            return
        if context.fallback_allowed:
            warnings.append(
                ValidationWarning(
                    field="benchmark_contract",
                    code="BENCHMARK_FALLBACK_DISCLOSED",
                    message=(
                        "No resolved Upswitch Index benchmark contract is available. "
                        "The advisor explicitly accepted a disclosed external market "
                        "fallback; the result remains indicative and is not a defensible "
                        "benchmark-grounded valuation."
                    ),
                    severity="warning",
                    suggestion=(
                        "Replace the fallback with a resolved benchmark contract before "
                        "using the valuation as transaction-grade evidence."
                    ),
                )
            )
            return
        missing_required.append("benchmark_contract")
        warnings.append(
            ValidationWarning(
                field="benchmark_contract",
                code="BENCHMARK_CONTRACT_REQUIRED",
                message=(
                    "A resolved benchmark contract with full provenance is required "
                    "before ValuationIQ can publish a multiples-based validation estimate."
                ),
                severity="error",
                suggestion="Resolve the business_type x country benchmark or request an explicitly disclosed fallback.",
            )
        )
        return

    if not context.contract_authorizes_ebitda:
        missing_required.append("benchmark_contract.ev_ebitda")
        warnings.append(
            ValidationWarning(
                field="benchmark_contract",
                code="BENCHMARK_METRIC_REQUIRED",
                message=(
                    "The resolved benchmark contract does not authorize the EV/EBITDA "
                    "multiple used for the validation estimate."
                ),
                severity="error",
                suggestion="Resolve an EV/EBITDA benchmark contract or omit the quick estimate.",
            )
        )


def _warn_margin_deviation(
    *,
    request: ValidateRequest,
    revenue: float,
    ebitda: float,
    warnings: list[ValidationWarning],
) -> None:
    if revenue <= 0 or not request.business_type_calibration:
        return

    ebitda_margin = ebitda / revenue
    typical_margin_f = safe_float(request.business_type_calibration.typical_ebitda_margin)
    if typical_margin_f <= 0:
        return

    deviation = abs(ebitda_margin - typical_margin_f) / typical_margin_f
    if deviation > 0.5:
        warnings.append(
            ValidationWarning(
                field="ebitda",
                code="MARGIN_DEVIATION",
                message=f"EBITDA margin ({ebitda_margin:.1%}) deviates significantly from industry typical ({typical_margin_f:.1%})",
                severity="warning",
                suggestion="Verify EBITDA is correctly calculated or consider normalizations",
            )
        )


def _warn_missing_normalization(
    *,
    request: ValidateRequest,
    warnings: list[ValidationWarning],
    missing_optional: list[str],
) -> None:
    if request.current_year.ebitda_normalized is not False:
        return

    missing_optional.append("ebitda_normalization")
    warnings.append(
        ValidationWarning(
            field="ebitda",
            code="NOT_NORMALIZED",
            message="EBITDA has not been normalized. Consider owner salary, one-time costs, etc.",
            severity="info",
            suggestion="Review EBITDA for normalization opportunities",
        )
    )


def _overall_status(
    *,
    warnings: list[ValidationWarning],
    missing_required: list[str],
) -> tuple[str, bool]:
    if missing_required:
        return "INVALID", False
    if len([w for w in warnings if w.severity == "error"]) > 0:
        return "INVALID", False
    if warnings:
        return "WARNINGS", True
    return "VALID", True


def _quick_estimate(
    *,
    ready: bool,
    context: BenchmarkValidationContext,
    revenue: float,
    ebitda: float,
) -> tuple[dict[str, Decimal] | None, Decimal | None]:
    if not (
        ready
        and context.calibration
        and revenue > 0
        and (
            context.contract_authorizes_ebitda
            or context.fallback_allowed
            or context.governed_external_reference
        )
    ):
        return None, None

    multiple = safe_float(getattr(context.calibration, "ev_ebitda_median", None))
    estimated_multiple = safe_decimal_or_zero(multiple) if multiple > 0 else None
    if multiple <= 0:
        return None, estimated_multiple

    base_ev = ebitda * multiple
    return (
        {
            "low": safe_decimal_or_zero(base_ev * 0.8),
            "mid": safe_decimal_or_zero(base_ev),
            "high": safe_decimal_or_zero(base_ev * 1.2),
        },
        estimated_multiple,
    )


def _data_quality_score(
    *,
    warnings: list[ValidationWarning],
    missing_required: list[str],
    missing_optional: list[str],
) -> int:
    data_quality_score = 100
    data_quality_score -= len(missing_required) * 25
    data_quality_score -= len(missing_optional) * 10
    data_quality_score -= len([w for w in warnings if w.severity == "warning"]) * 5
    return max(0, min(100, data_quality_score))


def validate_stateless_request(request: ValidateRequest) -> ValidateResponse:
    """Validate stateless calculation inputs and return warnings/suggestions."""
    warnings: list[ValidationWarning] = []
    missing_required: list[str] = []
    missing_optional: list[str] = []

    # Parity with /calculate: a no-books current year (open filing year from an
    # accounting import) re-anchors onto the latest usable closed year instead
    # of being rejected as "missing revenue". The caller learns about the
    # re-anchor via an info warning; everything below validates the promoted
    # basis exactly as the calculation will use it.
    request, reanchor_warning = _reanchored_request(request)
    if reanchor_warning is not None:
        warnings.append(reanchor_warning)

    _validate_revenue(
        request=request,
        warnings=warnings,
        missing_required=missing_required,
    )
    _warn_negative_ebitda(request, warnings)
    _warn_limited_history(
        request=request,
        warnings=warnings,
        missing_optional=missing_optional,
    )

    revenue = safe_float(request.current_year.revenue)
    ebitda = safe_float(request.current_year.ebitda)
    benchmark_context = _benchmark_validation_context(request=request, revenue=revenue)
    _validate_benchmark_contract(
        context=benchmark_context,
        warnings=warnings,
        missing_required=missing_required,
    )

    if revenue > 0:
        _warn_margin_deviation(
            request=request,
            revenue=revenue,
            ebitda=ebitda,
            warnings=warnings,
        )

    _warn_missing_normalization(
        request=request,
        warnings=warnings,
        missing_optional=missing_optional,
    )

    overall_status, ready = _overall_status(
        warnings=warnings,
        missing_required=missing_required,
    )
    estimated_range, estimated_multiple = _quick_estimate(
        ready=ready,
        context=benchmark_context,
        revenue=revenue,
        ebitda=ebitda,
    )

    data_quality_score = _data_quality_score(
        warnings=warnings,
        missing_required=missing_required,
        missing_optional=missing_optional,
    )

    return ValidateResponse(
        status=overall_status,
        ready_for_calculation=ready,
        warnings=warnings,
        estimated_valuation_range=estimated_range,
        estimated_multiple=estimated_multiple,
        benchmark_comparisons=None,  # Could add benchmark comparison logic
        missing_required_fields=missing_required,
        missing_optional_fields=missing_optional,
        data_quality_score=data_quality_score,
    )
