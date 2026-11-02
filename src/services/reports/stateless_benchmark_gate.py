"""Fail-closed benchmark contract gate for stateless calculations."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from src.api.schemas.stateless_api import BusinessTypeCalibration, CalculateRequest
from src.services.reports.benchmark_pricing_binding import benchmark_pricing_binding_issues
from src.services.reports.public_modeled_prior_binding import public_source_calibration
from src.services.reports.stateless_benchmark_policy import (
    JsonMap,
    _required_calibration_multiple_attributes,
    benchmark_contract_is_resolved,
    flatten_benchmark_provenance,
    missing_benchmark_metrics_for_calibration,
    missing_required_benchmark_provenance,
    stateless_requires_benchmark_contract,
)


@dataclass(frozen=True)
class StatelessBenchmarkGateResult:
    benchmark_contract_resolved: bool
    benchmark_provenance: JsonMap | None


def enforce_stateless_benchmark_gate(
    *,
    request: CalculateRequest,
    calibration: BusinessTypeCalibration,
    asset_primary_payload: JsonMap | None,
    benchmark_contract: JsonMap | None,
    allow_untrusted_multiples_fallback: bool,
) -> StatelessBenchmarkGateResult:
    """Validate benchmark contract trust before multiples-based stateless valuation."""
    benchmark_contract_resolved = benchmark_contract_is_resolved(
        benchmark_contract
    ) and not missing_required_benchmark_provenance(benchmark_contract)
    source_calibration, modeled_band_issues = public_source_calibration(
        request, calibration.model_dump()
    )
    binding_issues = modeled_band_issues + (
        benchmark_pricing_binding_issues(
            benchmark_contract,
            calibration=source_calibration,
            required_attributes=_required_calibration_multiple_attributes(request),
            business_type_id=calibration.business_type_id,
            country_code=request.country_code,
            business_type_mix=request.business_type_mix,
        )
        if benchmark_contract_resolved and benchmark_contract
        else []
    )
    benchmark_contract_resolved = benchmark_contract_resolved and not binding_issues
    governed_external_reference = getattr(request, "external_market_reference_contract", None)
    benchmark_provenance = (
        flatten_benchmark_provenance(benchmark_contract) if benchmark_contract_resolved else None
    )

    if not (
        stateless_requires_benchmark_contract(
            request,
            calibration=calibration,
            asset_primary_payload=asset_primary_payload,
        )
        and governed_external_reference is None
        and not allow_untrusted_multiples_fallback
    ):
        return StatelessBenchmarkGateResult(
            benchmark_contract_resolved=benchmark_contract_resolved,
            benchmark_provenance=benchmark_provenance,
        )

    if not benchmark_contract:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "BENCHMARK_UNAVAILABLE",
                "message": (
                    "No trusted benchmark contract is available for this stateless "
                    "business-type multiple valuation. Upswitch will not silently "
                    "use unlabeled generic market multiples."
                ),
                "business_type_id": calibration.business_type_id,
                "country_code": request.country_code,
                "reason": "missing_benchmark_contract",
            },
        )

    missing_required_fields = missing_required_benchmark_provenance(benchmark_contract)
    if missing_required_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "BENCHMARK_UNAVAILABLE",
                "message": (
                    "The resolved benchmark contract is missing required provenance. "
                    "Upswitch will not calculate from an incomplete benchmark contract."
                ),
                "business_type_id": calibration.business_type_id,
                "country_code": request.country_code,
                "reason": "incomplete_benchmark_provenance",
                "missing_required_fields": missing_required_fields,
                "benchmark_contract": benchmark_contract,
            },
        )

    if not benchmark_contract_is_resolved(benchmark_contract):
        missing_metric_keys = missing_benchmark_metrics_for_calibration(
            calibration,
            benchmark_contract,
            request=request,
        )
        if missing_metric_keys:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "BENCHMARK_UNAVAILABLE",
                    "message": (
                        "The benchmark contract does not authorize every multiple "
                        "requested for this valuation."
                    ),
                    "business_type_id": calibration.business_type_id,
                    "country_code": request.country_code,
                    "reason": "missing_benchmark_metric",
                    "missing_metrics": missing_metric_keys,
                    "benchmark_contract": benchmark_contract,
                },
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "BENCHMARK_UNAVAILABLE",
                "message": "The benchmark contract is not resolved for pricing.",
                "business_type_id": calibration.business_type_id,
                "country_code": request.country_code,
                "reason": str(benchmark_contract.get("status") or "unresolved"),
            },
        )

    missing_metric_keys = missing_benchmark_metrics_for_calibration(
        calibration,
        benchmark_contract,
        request=request,
    )
    if missing_metric_keys:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "BENCHMARK_UNAVAILABLE",
                "message": (
                    "The resolved benchmark contract does not authorize every "
                    "multiple requested for this valuation."
                ),
                "business_type_id": calibration.business_type_id,
                "country_code": request.country_code,
                "reason": "missing_benchmark_metric",
                "missing_metrics": missing_metric_keys,
                "benchmark_contract": benchmark_contract,
            },
        )

    if binding_issues:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "BENCHMARK_UNAVAILABLE",
                "message": "Pricing inputs do not match the benchmark evidence for this company.",
                "reason": "benchmark_pricing_binding_mismatch",
                "business_type_id": calibration.business_type_id,
                "country_code": request.country_code,
                "binding_issues": binding_issues,
            },
        )

    return StatelessBenchmarkGateResult(
        benchmark_contract_resolved=True,
        benchmark_provenance=flatten_benchmark_provenance(benchmark_contract),
    )
