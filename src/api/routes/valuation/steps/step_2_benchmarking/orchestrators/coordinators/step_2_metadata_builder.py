"""Step 2 metadata assembly for benchmark result building."""

from __future__ import annotations

from typing import Optional, Protocol

from src.api.routes.valuation.benchmark_contract_utils import (
    benchmark_contract_source_key,
    is_resolved_benchmark_contract,
)
from src.api.routes.valuation.triage.business_type_triage import BusinessTypeCategory

from ....source_tracing import build_source_metadata


class QualityCheckpointValidator(Protocol):
    def validate_quality_checkpoint(
        self,
        request: object,
        previous_results: dict[int, object],
    ) -> object: ...


def _resolve_benchmark_provenance(result_dict: dict[str, object]) -> object:
    data_source_details = result_dict.get("data_source_details", {})
    if not isinstance(data_source_details, dict):
        data_source_details = {}
    return (
        result_dict.get("benchmark_provenance")
        or result_dict.get("benchmark_contract")
        or data_source_details.get("benchmark_provenance")
        or data_source_details.get("benchmark_contract")
    )


def _source_key_for_result(result_dict: dict[str, object], benchmark_provenance: object) -> str:
    data_source_key = result_dict.get("data_source", "TITAN_BUSINESS_TYPES_DB")
    if is_resolved_benchmark_contract(benchmark_provenance):
        return benchmark_contract_source_key(benchmark_provenance)
    if any(
        marker in str(data_source_key).lower()
        for marker in ("fmp", "cache", "fallback", "default", "damodaran", "pepperdine")
    ):
        return "DISCLOSED_EXTERNAL_MARKET_FALLBACK"
    return "TITAN_BUSINESS_TYPES_DB"


def _benchmark_field(
    *,
    benchmark_provenance: object,
    result_dict: dict[str, object],
    provenance_key: str,
    result_key: str,
) -> object:
    if isinstance(benchmark_provenance, dict):
        return benchmark_provenance.get(provenance_key)
    return result_dict.get(result_key)


def build_step2_metadata_dict(
    *,
    request: object,
    result_dict: dict[str, object],
    eligibility_result: object,
    comparables_data: dict[str, object],
    business_category: Optional[BusinessTypeCategory],
    multiples_checksum: str,
    previous_results: dict[int, object],
    validator: QualityCheckpointValidator | None = None,
) -> dict[str, object]:
    """Build comprehensive Step 2 metadata with source tracing."""
    benchmark_provenance = _resolve_benchmark_provenance(result_dict)
    source_metadata = build_source_metadata(
        step_key="step_2_benchmarking",
        data_source=_source_key_for_result(result_dict, benchmark_provenance),
    )

    metadata = {
        "selection_logic": "resolved_benchmark_contract_first",
        "cascade_levels": [
            "resolved_benchmark_contract",
            "explicitly_disclosed_untrusted_fallback_only",
        ],
        "business_type_category": (
            getattr(business_category, "value", "unknown") if business_category else "unknown"
        ),
        "multiples_checksum": multiples_checksum,
        "methodology_decision": {
            "decision": (
                getattr(eligibility_result.decision, "value", "multiples_only")
                if eligibility_result and hasattr(eligibility_result, "decision")
                else "multiples_only"
            ),
            "dcf_eligible": (
                getattr(eligibility_result, "should_calculate_dcf", False)
                if eligibility_result
                else False
            ),
            "suitability_score": (
                getattr(eligibility_result.suitability_score, "total_score", 0)
                if eligibility_result
                and hasattr(eligibility_result, "suitability_score")
                and eligibility_result.suitability_score
                else 0
            ),
            "breakdown": (
                getattr(eligibility_result.suitability_score, "breakdown", {})
                if eligibility_result
                and hasattr(eligibility_result, "suitability_score")
                and eligibility_result.suitability_score
                else {}
            ),
            "explanation": (
                getattr(eligibility_result, "explanation", None) if eligibility_result else None
            ),
        },
        "comparables_analysis": {
            "count": comparables_data.get("count", 0),
            "sufficient": comparables_data.get("sufficient", False),
        },
        "multiples_backup": {
            "ev_revenue_multiple": result_dict.get("ev_revenue_multiple"),
            "ev_ebitda_multiple": result_dict.get("ev_ebitda_multiple"),
            "ev_revenue_p25": result_dict.get("ev_revenue_p25"),
            "ev_revenue_p50": result_dict.get("ev_revenue_p50"),
            "ev_revenue_p75": result_dict.get("ev_revenue_p75"),
            "ev_ebitda_p25": result_dict.get("ev_ebitda_p25"),
            "ev_ebitda_p50": result_dict.get("ev_ebitda_p50"),
            "ev_ebitda_p75": result_dict.get("ev_ebitda_p75"),
            "pe_ratio": result_dict.get("pe_ratio"),
            "primary_method": result_dict.get("primary_method"),
            "data_source": result_dict.get("data_source"),
            "benchmark_contract": benchmark_provenance,
        },
        "result_backup": result_dict.copy(),
        "benchmark_contract": benchmark_provenance,
        "benchmark_provenance": benchmark_provenance,
        "benchmark_id": _benchmark_field(
            benchmark_provenance=benchmark_provenance,
            result_dict=result_dict,
            provenance_key="benchmark_id",
            result_key="benchmark_id",
        ),
        "dataset_version_id": _benchmark_field(
            benchmark_provenance=benchmark_provenance,
            result_dict=result_dict,
            provenance_key="dataset_version_id",
            result_key="dataset_version_id",
        ),
        "benchmark_country_code": _benchmark_field(
            benchmark_provenance=benchmark_provenance,
            result_dict=result_dict,
            provenance_key="country_code",
            result_key="benchmark_country_code",
        ),
        "benchmark_region_key": _benchmark_field(
            benchmark_provenance=benchmark_provenance,
            result_dict=result_dict,
            provenance_key="region_key",
            result_key="benchmark_region_key",
        ),
        "benchmark_tier": _benchmark_field(
            benchmark_provenance=benchmark_provenance,
            result_dict=result_dict,
            provenance_key="tier",
            result_key="benchmark_tier",
        ),
        "benchmark_walk_step": _benchmark_field(
            benchmark_provenance=benchmark_provenance,
            result_dict=result_dict,
            provenance_key="walk_step",
            result_key="benchmark_walk_step",
        ),
        "benchmark_scope_stage": _benchmark_field(
            benchmark_provenance=benchmark_provenance,
            result_dict=result_dict,
            provenance_key="scope_stage",
            result_key="benchmark_scope_stage",
        ),
        "benchmark_sample_size": _benchmark_field(
            benchmark_provenance=benchmark_provenance,
            result_dict=result_dict,
            provenance_key="sample_size",
            result_key="benchmark_sample_size",
        ),
        "benchmark_confidence_band": _benchmark_field(
            benchmark_provenance=benchmark_provenance,
            result_dict=result_dict,
            provenance_key="confidence_band",
            result_key="benchmark_confidence_band",
        ),
        "benchmark_source_mix": _benchmark_field(
            benchmark_provenance=benchmark_provenance,
            result_dict=result_dict,
            provenance_key="source_mix",
            result_key="benchmark_source_mix",
        ),
        "benchmark_evidence_summary": _benchmark_field(
            benchmark_provenance=benchmark_provenance,
            result_dict=result_dict,
            provenance_key="evidence_summary",
            result_key="benchmark_evidence_summary",
        ),
        "benchmark_published_at": _benchmark_field(
            benchmark_provenance=benchmark_provenance,
            result_dict=result_dict,
            provenance_key="published_at",
            result_key="benchmark_published_at",
        ),
        "benchmark_methodology_version": _benchmark_field(
            benchmark_provenance=benchmark_provenance,
            result_dict=result_dict,
            provenance_key="methodology_version",
            result_key="benchmark_methodology_version",
        ),
        "data_source": source_metadata["data_source"],
        "data_source_name": source_metadata["data_source_name"],
        "source_confidence": source_metadata["source_confidence"],
        "academic_sources": source_metadata["academic_sources"],
        "primary_citation": source_metadata["primary_citation"],
    }

    if validator:
        quality_checkpoint = validator.validate_quality_checkpoint(request, previous_results)
        if quality_checkpoint:
            metadata["quality_checkpoint"] = quality_checkpoint

    return metadata
