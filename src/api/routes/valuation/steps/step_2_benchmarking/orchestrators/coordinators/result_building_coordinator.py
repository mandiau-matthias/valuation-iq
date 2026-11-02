"""
Result Building Coordinator

Orchestrates result and metadata dictionary building for Step 2 (Industry Benchmarking).

SOURCE TRACING:
- Data Source: Upswitch Index benchmark contract via Titan
- Methodology Foundation: IVS evidence transparency + SME multiple selection
- Methodology: Industry multiple selection using priority cascade

ALIGNMENT WITH UPSWITCH PRIMITIVES:
- Primitive 2: Algorithmic Defensibility - multiples source fully traceable
- Primitive 3: Trust Node - accountant-grade citations for methodology
"""

from decimal import Decimal
from typing import Any, Dict, Mapping, Optional

from src.api.routes.valuation.benchmark_contract_utils import extract_resolved_benchmark_contract
from src.api.routes.valuation.benchmark_contract_utils import (
    request_allows_untrusted_multiples_fallback as _request_allows_untrusted_multiples_fallback,
)
from src.api.routes.valuation.triage.business_type_triage import BusinessTypeCategory
from src.utils.logging import get_logger
from src.utils.valuation_logger import ValuationLogger

# Import data source formatter
from ...utils.data_source_formatter import DataSourceFormatter
from .result_building_recovery import (
    create_fallback_result_from_multiples,
    create_result_building_fallback_recovery_service,
)
from .step_2_metadata_builder import build_step2_metadata_dict

# Import recovery service with fallback
try:
    from ...services import Step2RecoveryService
except ImportError:
    Step2RecoveryService = None

logger = get_logger(__name__)


def _coerce_decimal_multiple(
    raw_value: Any,
    metric_name: str,
    *,
    allow_untrusted_multiples_fallback: bool,
    fallback_value: Decimal,
) -> Optional[Decimal]:
    if raw_value is None:
        if allow_untrusted_multiples_fallback:
            return fallback_value
        return None
    if isinstance(raw_value, Decimal):
        return raw_value
    if isinstance(raw_value, (int, float, str)):
        try:
            return Decimal(str(raw_value))
        except Exception as exc:
            if allow_untrusted_multiples_fallback:
                return fallback_value
            raise ValueError(f"Invalid {metric_name} multiple; refusing silent fallback") from exc
    if allow_untrusted_multiples_fallback:
        return fallback_value
    raise ValueError(
        f"Invalid {metric_name} multiple type {type(raw_value).__name__}; refusing silent fallback"
    )


def _require_primary_multiple(
    primary_method: str,
    ev_ebitda_multiple: Optional[Decimal],
    ev_revenue_multiple: Optional[Decimal],
) -> None:
    if primary_method == "EV/Revenue" and ev_revenue_multiple is None:
        raise ValueError(
            "EV/Revenue selected but no resolved EV/Revenue benchmark multiple was supplied"
        )
    if primary_method != "EV/Revenue" and ev_ebitda_multiple is None:
        raise ValueError(
            "EV/EBITDA selected but no resolved EV/EBITDA benchmark multiple was supplied"
        )


def _extract_benchmark_provenance(multiples_data: Mapping[str, object]) -> object:
    if not isinstance(multiples_data, dict):
        return None

    data_source_details = multiples_data.get("data_source_details", {})
    if not isinstance(data_source_details, dict):
        data_source_details = {}

    raw_benchmark_provenance = (
        multiples_data.get("benchmark_provenance")
        or multiples_data.get("benchmark_contract")
        or data_source_details.get("benchmark_provenance")
        or data_source_details.get("benchmark_contract")
    )
    return extract_resolved_benchmark_contract(multiples_data) or raw_benchmark_provenance


def _resolve_benchmark_multiples(
    primary_method: str,
    multiples_data: Mapping[str, object],
    *,
    allow_untrusted_multiples_fallback: bool,
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    try:
        ev_ebitda_raw = (
            multiples_data.get("ev_ebitda") if isinstance(multiples_data, dict) else None
        )
        ev_revenue_raw = (
            multiples_data.get("ev_revenue") if isinstance(multiples_data, dict) else None
        )

        ev_ebitda_multiple = _coerce_decimal_multiple(
            ev_ebitda_raw,
            "EV/EBITDA",
            allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
            fallback_value=Decimal("5.0"),
        )
        ev_revenue_multiple = _coerce_decimal_multiple(
            ev_revenue_raw,
            "EV/Revenue",
            allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
            fallback_value=Decimal("1.0"),
        )
        _require_primary_multiple(primary_method, ev_ebitda_multiple, ev_revenue_multiple)
        return ev_ebitda_multiple, ev_revenue_multiple
    except Exception as conversion_error:
        logger.error(
            "Failed to convert defensible multiples to Decimal",
            extra={
                "error_type": type(conversion_error).__name__,
                "error_message": str(conversion_error),
                "ev_ebitda_raw": str(multiples_data.get("ev_ebitda")) if multiples_data else None,
                "ev_revenue_raw": str(multiples_data.get("ev_revenue")) if multiples_data else None,
                "allow_untrusted_multiples_fallback": allow_untrusted_multiples_fallback,
            },
            exc_info=True,
        )
        if not allow_untrusted_multiples_fallback:
            raise
        return Decimal("5.0"), Decimal("1.0")


def _decimal_percentile_from_data(
    multiples_data: Mapping[str, object], key: str
) -> Optional[Decimal]:
    raw = multiples_data.get(key) if multiples_data else None
    if raw is None:
        return None
    if isinstance(raw, Decimal):
        return raw
    try:
        return Decimal(str(raw))
    except Exception:
        return None


def _percentile_or_default(
    raw_value: object,
    multiple: Optional[Decimal],
    default_factor: Decimal,
) -> Optional[Decimal]:
    if raw_value is not None:
        return raw_value
    if multiple is None:
        return None
    return multiple * default_factor


def _build_percentile_payload(
    multiples_data: Mapping[str, object],
    ev_ebitda_multiple: Optional[Decimal],
    ev_revenue_multiple: Optional[Decimal],
) -> Dict[str, object]:
    ev_ebitda_p25_raw = multiples_data.get("ev_ebitda_p25")
    ev_ebitda_p50_raw = multiples_data.get("ev_ebitda_p50")
    ev_ebitda_p75_raw = multiples_data.get("ev_ebitda_p75")
    ev_revenue_p25_raw = multiples_data.get("ev_revenue_p25")
    ev_revenue_p50_raw = multiples_data.get("ev_revenue_p50")
    ev_revenue_p75_raw = multiples_data.get("ev_revenue_p75")

    return {
        "ev_ebitda_p10": _decimal_percentile_from_data(multiples_data, "ev_ebitda_p10"),
        "ev_ebitda_p25": _percentile_or_default(
            ev_ebitda_p25_raw, ev_ebitda_multiple, Decimal("0.8")
        ),
        "ev_ebitda_p50": (
            ev_ebitda_p50_raw if ev_ebitda_p50_raw is not None else ev_ebitda_multiple
        ),
        "ev_ebitda_p75": _percentile_or_default(
            ev_ebitda_p75_raw, ev_ebitda_multiple, Decimal("1.2")
        ),
        "ev_ebitda_p90": _decimal_percentile_from_data(multiples_data, "ev_ebitda_p90"),
        "ev_revenue_p25": _percentile_or_default(
            ev_revenue_p25_raw, ev_revenue_multiple, Decimal("0.8")
        ),
        "ev_revenue_p50": (
            ev_revenue_p50_raw if ev_revenue_p50_raw is not None else ev_revenue_multiple
        ),
        "ev_revenue_p75": _percentile_or_default(
            ev_revenue_p75_raw, ev_revenue_multiple, Decimal("1.2")
        ),
    }


def _benchmark_value(
    benchmark_provenance: object,
    multiples_data: Mapping[str, object],
    provenance_key: str,
    fallback_key: Optional[str] = None,
) -> object:
    if isinstance(benchmark_provenance, dict):
        return benchmark_provenance.get(provenance_key)
    return multiples_data.get(fallback_key or f"benchmark_{provenance_key}")


def _build_benchmark_payload(
    benchmark_provenance: object,
    multiples_data: Mapping[str, object],
) -> Dict[str, object]:
    return {
        "benchmark_contract": benchmark_provenance,
        "benchmark_provenance": benchmark_provenance,
        "benchmark_id": _benchmark_value(
            benchmark_provenance, multiples_data, "benchmark_id", "benchmark_id"
        ),
        "dataset_version_id": _benchmark_value(
            benchmark_provenance, multiples_data, "dataset_version_id", "dataset_version_id"
        ),
        "benchmark_country_code": _benchmark_value(
            benchmark_provenance, multiples_data, "country_code"
        ),
        "benchmark_region_key": _benchmark_value(
            benchmark_provenance, multiples_data, "region_key"
        ),
        "benchmark_tier": _benchmark_value(benchmark_provenance, multiples_data, "tier"),
        "benchmark_walk_step": _benchmark_value(benchmark_provenance, multiples_data, "walk_step"),
        "benchmark_scope_stage": _benchmark_value(
            benchmark_provenance, multiples_data, "scope_stage"
        ),
        "benchmark_sample_size": _benchmark_value(
            benchmark_provenance, multiples_data, "sample_size"
        ),
        "benchmark_confidence_band": _benchmark_value(
            benchmark_provenance, multiples_data, "confidence_band"
        ),
        "benchmark_source_mix": _benchmark_value(
            benchmark_provenance, multiples_data, "source_mix"
        ),
        "benchmark_evidence_summary": _benchmark_value(
            benchmark_provenance, multiples_data, "evidence_summary"
        ),
        "benchmark_published_at": _benchmark_value(
            benchmark_provenance, multiples_data, "published_at"
        ),
        "benchmark_methodology_version": _benchmark_value(
            benchmark_provenance, multiples_data, "methodology_version"
        ),
    }


def _build_recovery_backup(multiples_data: Mapping[str, object]) -> Dict[str, object]:
    if not multiples_data or not isinstance(multiples_data, dict):
        return {}

    return {
        "ev_ebitda": multiples_data.get("ev_ebitda"),
        "ev_revenue": multiples_data.get("ev_revenue"),
        "pe_ratio": multiples_data.get("pe_ratio"),
        "data_source": multiples_data.get("data_source", "unknown"),
        "data_source_details": multiples_data.get("data_source_details", {}),
        "ev_ebitda_p25": multiples_data.get("ev_ebitda_p25"),
        "ev_ebitda_p50": multiples_data.get("ev_ebitda_p50"),
        "ev_ebitda_p75": multiples_data.get("ev_ebitda_p75"),
        "ev_revenue_p25": multiples_data.get("ev_revenue_p25"),
        "ev_revenue_p50": multiples_data.get("ev_revenue_p50"),
        "ev_revenue_p75": multiples_data.get("ev_revenue_p75"),
        "benchmark_contract": multiples_data.get("benchmark_contract"),
        "benchmark_provenance": multiples_data.get("benchmark_provenance"),
    }


class ResultBuildingCoordinator:
    """
    Coordinates result and metadata dictionary building operations.
    """

    def __init__(self, insights_generator=None, validator=None, logger_instance=None) -> None:
        self.insights_generator = insights_generator
        self.validator = validator
        self.logger = logger_instance or logger

        # Initialize recovery service (with fallback if import failed)
        if Step2RecoveryService:
            if isinstance(logger_instance, ValuationLogger):
                self.recovery_service = Step2RecoveryService(logger_instance)
            else:
                # Fallback if logger_instance is not ValuationLogger
                valuation_logger = ValuationLogger(__name__)
                self.recovery_service = Step2RecoveryService(valuation_logger)
        else:
            # Fallback: create minimal recovery service inline
            self.recovery_service = self._create_fallback_recovery_service(
                logger_instance or logger
            )

    def _safe_get_methodology(self, eligibility_result: Any) -> str:
        """Safely extract methodology from eligibility_result."""
        if not eligibility_result:
            return "multiples_only"
        if not hasattr(eligibility_result, "decision"):
            return "multiples_only"
        if not eligibility_result.decision:
            return "multiples_only"
        try:
            # Try to get value attribute (for enums)
            if hasattr(eligibility_result.decision, "value"):
                return eligibility_result.decision.value
            # Try to get name attribute
            if hasattr(eligibility_result.decision, "name"):
                return eligibility_result.decision.name
            # Fallback to string representation
            return str(eligibility_result.decision)
        except (AttributeError, TypeError, ValueError) as e:
            logger.warning(
                "Step 2: _safe_get_methodology failed, defaulting to 'multiples_only'",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            return "multiples_only"

    def _convert_decimal_to_string(self, value: Any) -> Any:
        """Convert Decimal values to strings for JSON serialization."""
        if isinstance(value, Decimal):
            return str(value)
        return value

    def _convert_dict_decimals_to_strings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively convert Decimal values to strings for JSON serialization.

        NOTE: This should only be called at the API response level, not on
        intermediate step results that are passed to other steps.
        """
        result = {}
        for key, value in data.items():
            # Skip conversion for keys that should remain numeric (used in comparisons)
            if key in ["comparables_found", "sufficient_comparables", "dcf_suitability_score"]:
                result[key] = value
            elif isinstance(value, Decimal):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = self._convert_dict_decimals_to_strings(value)
            elif isinstance(value, list):
                result[key] = [
                    (
                        self._convert_dict_decimals_to_strings(item)
                        if isinstance(item, dict)
                        else str(item) if isinstance(item, Decimal) else item
                    )
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def _build_eligibility_payload(self, eligibility_result: object) -> Dict[str, object]:
        suitability_score = (
            eligibility_result.suitability_score
            if eligibility_result and hasattr(eligibility_result, "suitability_score")
            else None
        )
        return {
            "dcf_eligible": (
                getattr(eligibility_result, "should_calculate_dcf", False)
                if eligibility_result
                else False
            ),
            "recommended_methodology": self._safe_get_methodology(eligibility_result),
            "dcf_suitability_score": (
                getattr(suitability_score, "total_score", 0) if suitability_score else 0
            ),
            "dcf_exclusion_reason": (
                getattr(suitability_score, "exclusion_reason", None) if suitability_score else None
            ),
            "recommended_dcf_weight": (
                getattr(eligibility_result, "recommended_dcf_weight", 0.0)
                if eligibility_result
                else Decimal("0.0")
            ),
            "recommended_multiples_weight": (
                getattr(eligibility_result, "recommended_multiples_weight", 1.0)
                if eligibility_result
                else Decimal("1.0")
            ),
        }

    def build_result_dict(
        self,
        request: Any,
        primary_method: str,
        multiples_data: Dict[str, Any],
        comparables_data: Dict[str, Any],
        eligibility_result: Any,
        business_category: Optional[BusinessTypeCategory],
        business_type_id: Optional[int],
        data_quality_warnings: list,
        sme_calibration_data: Dict[str, Any],
        correlation_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        Build comprehensive result dictionary.

        Args:
            request: Valuation request
            primary_method: Primary valuation method
            multiples_data: Multiples data dictionary
            comparables_data: Comparables data dictionary
            eligibility_result: Methodology eligibility result
            business_category: Business type category
            business_type_id: Business type ID
            data_quality_warnings: List of data quality warnings
            sme_calibration_data: SME calibration data
            correlation_id: Correlation ID for logging

        Returns:
            Result dictionary
        """
        # DEBUG: in-method lifecycle breadcrumb; canonical Step 2 entry/exit
        # is already INFO at the step orchestrator boundary.
        logger.debug(
            "[RESULT-BUILDER] ========== build_result_dict CALLED ==========",
            extra={
                "correlation_id": correlation_id,
                "multiples_data_keys": list(multiples_data.keys()) if multiples_data else [],
                "multiples_data_size": len(multiples_data) if multiples_data else 0,
                "has_ev_ebitda": "ev_ebitda" in multiples_data if multiples_data else False,
                "has_ev_revenue": "ev_revenue" in multiples_data if multiples_data else False,
                "ev_ebitda_value": str(multiples_data.get("ev_ebitda")) if multiples_data else None,
                "ev_revenue_value": (
                    str(multiples_data.get("ev_revenue")) if multiples_data else None
                ),
            },
        )

        benchmark_provenance = _extract_benchmark_provenance(multiples_data)
        allow_untrusted_multiples_fallback = _request_allows_untrusted_multiples_fallback(request)
        ev_ebitda_multiple, ev_revenue_multiple = _resolve_benchmark_multiples(
            primary_method,
            multiples_data,
            allow_untrusted_multiples_fallback=allow_untrusted_multiples_fallback,
        )

        logger.debug(
            "[RESULT-BUILDER] After conversion",
            extra={
                "ev_ebitda_multiple": str(ev_ebitda_multiple),
                "ev_revenue_multiple": str(ev_revenue_multiple),
                "ev_ebitda_type": type(ev_ebitda_multiple).__name__,
                "ev_revenue_type": type(ev_revenue_multiple).__name__,
            },
        )

        # Ensure percentiles are set
        # BANK-GRADE: Use explicit None checking for percentiles to handle Decimal("0") correctly
        # Decimal("0") is falsy but valid - must check for None explicitly, not truthiness
        percentile_payload = _build_percentile_payload(
            multiples_data,
            ev_ebitda_multiple,
            ev_revenue_multiple,
        )

        # DEBUG: per-stage lifecycle within Step 2.
        try:
            logger.debug(
                "Step 2: Building result dict",
                extra={
                    "step_number": 2,
                    "correlation_id": correlation_id,
                    "multiples_data_keys": list(multiples_data.keys()) if multiples_data else [],
                    "multiples_data_size": len(multiples_data) if multiples_data else 0,
                    "ev_ebitda": str(ev_ebitda_multiple),
                    "ev_revenue": str(ev_revenue_multiple),
                    "data_source": multiples_data.get("data_source", "unknown"),
                },
            )
        except Exception as log_error:
            # Don't fail if logging fails
            pass

        try:
            logger.debug(
                "[RESULT-BUILDER] About to build result dict",
                extra={
                    "correlation_id": correlation_id,
                    "eligibility_result_type": (
                        type(eligibility_result).__name__ if eligibility_result else None
                    ),
                    "has_decision": (
                        hasattr(eligibility_result, "decision") if eligibility_result else False
                    ),
                    "decision_value": (
                        str(eligibility_result.decision)
                        if eligibility_result
                        and hasattr(eligibility_result, "decision")
                        and eligibility_result.decision
                        else None
                    ),
                },
            )
            result = {
                "primary_method": primary_method,
                "ev_ebitda_multiple": ev_ebitda_multiple,
                "ev_revenue_multiple": ev_revenue_multiple,
                **percentile_payload,
                "pe_ratio": (
                    multiples_data.get("pe_ratio")
                    if multiples_data.get("pe_ratio") is not None
                    else (Decimal("15.0") if allow_untrusted_multiples_fallback else None)
                ),
                "data_source": multiples_data.get(
                    "data_source",
                    "fallback" if allow_untrusted_multiples_fallback else "unknown",
                ),
                "data_source_details": multiples_data.get("data_source_details", {}),
                "comparables_found": comparables_data.get("count", 0),
                "comparables_list": comparables_data.get("comparables", []),
                "sufficient_comparables": comparables_data.get("sufficient", False),
                **self._build_eligibility_payload(eligibility_result),
                "business_type_category": (
                    getattr(business_category, "value", "unknown")
                    if business_category
                    else "unknown"
                ),
                "business_type_id": business_type_id,
                "correlation_id": correlation_id,
                "multiples_source": (
                    DataSourceFormatter.format_data_source_display(
                        multiples_data.get("data_source", "unknown"),
                        multiples_data.get("data_source_details", {}),
                    )
                ),
                "data_source_display": (
                    DataSourceFormatter.format_data_source_display(
                        multiples_data.get("data_source", "unknown"),
                        multiples_data.get("data_source_details", {}),
                    )
                ),
                "data_source_academic_citations": (
                    DataSourceFormatter.format_academic_citations(
                        multiples_data.get("data_source", "unknown")
                    )
                ),
                **_build_benchmark_payload(benchmark_provenance, multiples_data),
                "market_insights": (
                    self.insights_generator.generate_market_insights_safe(
                        request, business_category, comparables_data
                    )
                    if self.insights_generator
                    else {}
                ),
                "data_quality_warnings": data_quality_warnings,
                "sme_calibration": sme_calibration_data,
                "multiples_p25": (
                    multiples_data.get("ev_revenue_p25")
                    if primary_method == "EV/Revenue"
                    else multiples_data.get("ev_ebitda_p25")
                ),
                "multiples_p50": (
                    multiples_data.get("ev_revenue_p50")
                    if primary_method == "EV/Revenue"
                    else multiples_data.get("ev_ebitda_p50")
                ),
                "multiples_p75": (
                    multiples_data.get("ev_revenue_p75")
                    if primary_method == "EV/Revenue"
                    else multiples_data.get("ev_ebitda_p75")
                ),
            }

            # DEBUG: per-stage lifecycle within Step 2.
            try:
                logger.debug(
                    "Step 2: Result dict built",
                    extra={
                        "step_number": 2,
                        "correlation_id": correlation_id,
                        "result_keys": list(result.keys()),
                        "result_size": len(result),
                        "ev_ebitda_multiple": str(result.get("ev_ebitda_multiple")),
                        "ev_revenue_multiple": str(result.get("ev_revenue_multiple")),
                        "data_source": result.get("data_source"),
                    },
                )
            except Exception as log_error:
                # Don't fail if logging fails
                pass

            logger.debug(
                "[RESULT-BUILDER] Returning result dict",
                extra={
                    "result_keys": list(result.keys()),
                    "result_size": len(result),
                    "ev_ebitda_multiple": str(result.get("ev_ebitda_multiple")),
                    "ev_revenue_multiple": str(result.get("ev_revenue_multiple")),
                },
            )

            # NOTE: Do NOT convert Decimals to strings here - the result dict is used
            # by other steps that expect numeric values. JSON serialization should
            # be handled at the API response level with a custom encoder.
            # Converting here breaks comparisons in later steps.

            return result
        except Exception as build_error:
            logger.error(
                "Step 2: Failed to build result dictionary, using recovery service",
                extra={
                    "step_number": 2,
                    "error_type": type(build_error).__name__,
                    "error_message": str(build_error),
                    "correlation_id": correlation_id,
                    "multiples_data_keys": list(multiples_data.keys()) if multiples_data else [],
                    "data_source": (
                        multiples_data.get("data_source") if multiples_data else "unknown"
                    ),
                },
                exc_info=True,
            )

            backup = _build_recovery_backup(multiples_data)

            # Use recovery service (with fallback if method doesn't exist)
            if hasattr(self.recovery_service, "recover_result_dict"):
                # BANK-GRADE: Check for None explicitly, not truthiness (Decimal("0") is valid)
                ev_ebitda_present = backup.get("ev_ebitda") is not None if backup else False
                ev_revenue_present = backup.get("ev_revenue") is not None if backup else False

                recovered_result = self.recovery_service.recover_result_dict(
                    backup=backup if (ev_ebitda_present or ev_revenue_present) else None,
                    error=build_error,
                    context={
                        "correlation_id": correlation_id,
                        "business_type_id": business_type_id,
                        "allow_untrusted_multiples_fallback": (allow_untrusted_multiples_fallback),
                        "requires_trusted_benchmark": not allow_untrusted_multiples_fallback,
                    },
                )
            else:
                # Fallback: create minimal result from backup
                recovered_result = self._create_fallback_result_from_multiples(
                    backup,
                    build_error,
                    context={
                        "allow_untrusted_multiples_fallback": allow_untrusted_multiples_fallback,
                        "requires_trusted_benchmark": not allow_untrusted_multiples_fallback,
                    },
                )

            # Add additional context that recovery service doesn't include
            recovered_result.update(
                {
                    "comparables_found": (
                        comparables_data.get("count", 0) if comparables_data else 0
                    ),
                    "comparables_list": (
                        comparables_data.get("comparables", []) if comparables_data else []
                    ),
                    "sufficient_comparables": (
                        comparables_data.get("sufficient", False) if comparables_data else False
                    ),
                    "dcf_eligible": False,
                    "recommended_methodology": "multiples_only",
                    "dcf_suitability_score": 0,
                    "dcf_exclusion_reason": f"Result building failed but recovered: {str(build_error)}",
                    "recommended_dcf_weight": Decimal("0.0"),
                    "recommended_multiples_weight": Decimal("1.0"),
                    "business_type_category": (
                        getattr(business_category, "value", "unknown")
                        if business_category
                        else "unknown"
                    ),
                    "business_type_id": business_type_id,
                    "correlation_id": correlation_id,
                    "market_insights": {},
                    "data_quality_warnings": data_quality_warnings if data_quality_warnings else [],
                    "sme_calibration": sme_calibration_data if sme_calibration_data else {},
                }
            )

            # NOTE: Do NOT convert Decimals to strings here - the result dict is used
            # by other steps that expect numeric values. JSON serialization should
            # be handled at the API response level.

            return recovered_result

    def build_metadata_dict(
        self,
        request: Any,
        result_dict: Dict[str, Any],
        eligibility_result: Any,
        comparables_data: Dict[str, Any],
        business_category: Optional[BusinessTypeCategory],
        multiples_checksum: str,
        previous_results: Dict[int, Any],
    ) -> Dict[str, Any]:
        """Build comprehensive metadata dictionary with source tracing."""
        return build_step2_metadata_dict(
            request=request,
            result_dict=result_dict,
            eligibility_result=eligibility_result,
            comparables_data=comparables_data,
            business_category=business_category,
            multiples_checksum=multiples_checksum,
            previous_results=previous_results,
            validator=self.validator,
        )

    def _create_fallback_recovery_service(self, logger_instance):
        """Create a minimal fallback recovery service if import failed."""
        return create_result_building_fallback_recovery_service(logger_instance)

    def _create_fallback_result_from_multiples(self, multiples_data, error, context=None):
        """Create a minimal result from multiples_data when recovery service unavailable."""
        return create_fallback_result_from_multiples(multiples_data, error, context)
