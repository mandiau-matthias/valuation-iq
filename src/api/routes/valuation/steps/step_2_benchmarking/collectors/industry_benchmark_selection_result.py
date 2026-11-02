"""Result shaping and observability for selected Step 2 multiples."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Optional, Protocol

from ..utils.data_source_formatter import DataSourceFormatter
from .industry_benchmark_percentiles import MultiplesPercentiles, decimal_or_none

try:
    from src.api.routes.valuation.metrics import (
        multiples_critical_fallback_counter,
        multiples_fallback_counter,
        multiples_source_by_country_counter,
        multiples_source_counter,
        titan_enrichment_status,
    )

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...

    def debug(self, msg: str, *args: object, **kwargs: object) -> object: ...


SOURCE_PRIORITY_LABELS = {
    "DELPHI_BENCHMARK_CONTRACT": DataSourceFormatter.UPSWITCH_INDEX_CONTRACT_DISPLAY,
    "delphi_benchmark_contract": DataSourceFormatter.UPSWITCH_INDEX_CONTRACT_DISPLAY,
    "delphi-resolved-benchmark": DataSourceFormatter.UPSWITCH_INDEX_CONTRACT_DISPLAY,
    "titan_enrichment": DataSourceFormatter.UPSWITCH_INDEX_CONTRACT_DISPLAY,
    "upswitch_index_benchmark_contract": DataSourceFormatter.UPSWITCH_INDEX_CONTRACT_DISPLAY,
    "business_type_db": "Disclosed legacy business-type cache fallback",
    "fmp_api": "Disclosed public-company market-data fallback",
    "cache": "Disclosed cached market-data fallback",
    "database_driven_default": "Disclosed synced calibration fallback",
    "database_category_default": "Disclosed synced category fallback",
    "database_industry_default": "Disclosed synced industry fallback",
    "business_type_default": "Disclosed business-type default fallback",
    "business_category_default": "Disclosed category default fallback",
    "industry_rules": "Disclosed industry-rules fallback",
    "hardcoded_industry": "Disclosed hardcoded industry fallback",
    "hardcoded_default": "Disclosed emergency generic fallback",
}

SOURCE_QUALITY = {
    "titan_enrichment": "resolved_contract",
    "business_type_db": "legacy_cache",
    "database_driven_default": "disclosed_fallback",
    "database_category_default": "disclosed_fallback",
    "database_industry_default": "disclosed_fallback",
    "fmp_api": "disclosed_external_fallback",
    "cache": "disclosed_cached_fallback",
    "hardcoded_business_type": "degraded",
    "hardcoded_category_default": "degraded",
    "hardcoded_industry": "degraded",
    "hardcoded_default": "emergency",
}

DEGRADED_SOURCE_QUALITIES = {
    "degraded",
    "emergency",
    "legacy_cache",
    "disclosed_fallback",
    "disclosed_external_fallback",
    "disclosed_cached_fallback",
}


def build_selected_multiples_result(
    *,
    ev_ebitda_ratio: Optional[Decimal],
    revenue_multiple: Optional[Decimal],
    pe_ratio: Decimal,
    percentiles: MultiplesPercentiles,
    data_source: str,
    data_source_details: Dict[str, object],
    business_type_id: Optional[str],
    correlation_id: Optional[str],
    request_country_code: Optional[str],
    industry: Optional[str],
    has_titan_enrichment: bool,
    cache_business_type_found: bool,
    normalized_benchmark_contract: Dict[str, object],
    logger: LoggerLike,
) -> Dict[str, object]:
    """Build the public multiples payload and record source observability."""
    source_priority_label = SOURCE_PRIORITY_LABELS.get(data_source, f"Unknown ({data_source})")

    logger.info(
        f"✅ MULTIPLES SELECTION COMPLETE - Source: {source_priority_label}",
        extra={
            "ev_ebitda_ratio": ev_ebitda_ratio,
            "revenue_multiple": revenue_multiple,
            "pe_ratio": pe_ratio,
            "data_source": data_source,
            "source_priority": source_priority_label,
            "business_type_id": business_type_id,
            "correlation_id": correlation_id,
            "is_titan_source": data_source == "titan_enrichment",
            "multiples_quality_score": data_source_details.get("multiples_quality_score"),
            "multiples_sample_size": data_source_details.get("multiples_sample_size"),
        },
    )

    data_source_display = DataSourceFormatter.format_data_source_display(
        data_source, data_source_details
    )

    if "academic_sources" not in data_source_details:
        data_source_details["academic_sources"] = (
            DataSourceFormatter.get_academic_sources_for_data_source(data_source)
        )
        data_source_details["academic_citations"] = DataSourceFormatter.format_academic_citations(
            data_source
        )
        data_source_details["source_explanation"] = DataSourceFormatter.generate_source_explanation(
            data_source,
            data_source_details.get("business_type_id"),
            data_source_details,
        )

    source_quality = SOURCE_QUALITY.get(data_source, "unknown")
    data_source_details["source_quality"] = source_quality
    data_source_details["cache_business_type_found"] = cache_business_type_found
    data_source_details["authoritative_source_expected"] = bool(business_type_id)
    data_source_details["degraded_source"] = source_quality in DEGRADED_SOURCE_QUALITIES

    _record_multiples_metrics(
        data_source=data_source,
        business_type_id=business_type_id,
        request_country_code=request_country_code,
        industry=industry,
        has_titan_enrichment=has_titan_enrichment,
        logger=logger,
    )

    return {
        "ev_ebitda": decimal_or_none(ev_ebitda_ratio),
        "ev_ebitda_p10": percentiles.ev_ebitda_p10,
        "ev_ebitda_p25": percentiles.ev_ebitda_p25,
        "ev_ebitda_p50": percentiles.ev_ebitda_p50,
        "ev_ebitda_p75": percentiles.ev_ebitda_p75,
        "ev_ebitda_p90": percentiles.ev_ebitda_p90,
        "ev_ebitda_percentile_source": percentiles.ev_ebitda_percentile_source,
        "ev_revenue": decimal_or_none(revenue_multiple),
        "ev_revenue_p25": percentiles.ev_revenue_p25,
        "ev_revenue_p50": percentiles.ev_revenue_p50,
        "ev_revenue_p75": percentiles.ev_revenue_p75,
        "ev_revenue_percentile_source": percentiles.ev_revenue_percentile_source,
        "pe_ratio": decimal_or_none(pe_ratio),
        "data_source": data_source,
        "data_source_display": data_source_display,
        "data_source_details": data_source_details,
        "source_quality": source_quality,
        "benchmark_contract": normalized_benchmark_contract or None,
        "benchmark_provenance": normalized_benchmark_contract or None,
        "benchmark_id": normalized_benchmark_contract.get("benchmark_id"),
        "dataset_version_id": normalized_benchmark_contract.get("dataset_version_id"),
        "benchmark_country_code": normalized_benchmark_contract.get("country_code"),
        "benchmark_region_key": normalized_benchmark_contract.get("region_key"),
        "benchmark_tier": normalized_benchmark_contract.get("tier"),
        "benchmark_walk_step": normalized_benchmark_contract.get("walk_step"),
        "benchmark_scope_stage": normalized_benchmark_contract.get("scope_stage"),
        "benchmark_sample_size": normalized_benchmark_contract.get("sample_size"),
        "benchmark_confidence_band": normalized_benchmark_contract.get("confidence_band"),
        "benchmark_source_mix": normalized_benchmark_contract.get("source_mix"),
        "benchmark_evidence_summary": normalized_benchmark_contract.get("evidence_summary"),
        "benchmark_published_at": normalized_benchmark_contract.get("published_at"),
        "benchmark_methodology_version": normalized_benchmark_contract.get("methodology_version"),
        "p25": (percentiles.ev_revenue_p25 if revenue_multiple else percentiles.ev_ebitda_p25),
        "p50": (percentiles.ev_revenue_p50 if revenue_multiple else percentiles.ev_ebitda_p50),
        "p75": (percentiles.ev_revenue_p75 if revenue_multiple else percentiles.ev_ebitda_p75),
    }


def _record_multiples_metrics(
    *,
    data_source: str,
    business_type_id: Optional[str],
    request_country_code: Optional[str],
    industry: Optional[str],
    has_titan_enrichment: bool,
    logger: LoggerLike,
) -> None:
    if not METRICS_AVAILABLE:
        return

    try:
        multiples_source_counter.labels(
            source=data_source, business_type_id=business_type_id or "unknown"
        ).inc()
        multiples_source_by_country_counter.labels(
            source=data_source,
            business_type_id=business_type_id or "unknown",
            country_code=(request_country_code or "unknown").upper(),
        ).inc()

        fallback_sources = {
            "hardcoded_business_type": "MEDIUM",
            "hardcoded_category_default": "MEDIUM",
            "hardcoded_industry": "LOW",
            "hardcoded_default": "CRITICAL",
        }
        if data_source in fallback_sources:
            multiples_fallback_counter.labels(
                fallback_type=data_source, severity=fallback_sources[data_source]
            ).inc()

        if data_source == "hardcoded_default":
            multiples_critical_fallback_counter.labels(
                business_type_id=business_type_id or "unknown",
                country_code=(request_country_code or "unknown").upper(),
                industry=str(industry or "unknown"),
            ).inc()

        if business_type_id:
            if data_source == "titan_enrichment":
                titan_enrichment_status.labels(
                    status="success", business_type_id=business_type_id
                ).inc()
            elif not has_titan_enrichment:
                titan_enrichment_status.labels(
                    status="missing", business_type_id=business_type_id
                ).inc()
    except Exception as metric_error:
        logger.debug(f"Failed to record metrics: {metric_error}")
