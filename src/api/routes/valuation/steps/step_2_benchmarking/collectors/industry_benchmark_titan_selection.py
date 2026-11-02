"""Titan resolved-contract multiple selection for Step 2 benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Protocol

from src.utils.decimal_helpers import to_decimal


class LoggerLike(Protocol):
    def debug(self, msg: str, *args: object, **kwargs: object) -> object: ...

    def warning(self, msg: str, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class TitanBenchmarkSelection:
    ev_ebitda_ratio: Optional[Decimal]
    revenue_multiple: Optional[Decimal]
    pe_ratio: Decimal
    data_source: str
    data_source_details: Dict[str, object]
    comparables_data: Optional[Dict[str, object]]


def apply_titan_benchmark_selection(
    *,
    has_titan_enrichment: bool,
    titan_ev_ebitda: object,
    titan_ev_revenue: object,
    titan_pe_ratio: object,
    titan_multiples_metadata: object,
    used_synced_business_types_db: bool,
    used_synced_business_type_mix_db: bool,
    business_type_id: Optional[str],
    business_type_mix: List[Dict[str, object]],
    correlation_id: Optional[str],
    normalized_benchmark_contract: Dict[str, object],
    ev_ebitda_ratio: Optional[Decimal],
    revenue_multiple: Optional[Decimal],
    pe_ratio: Decimal,
    data_source: str,
    data_source_details: Dict[str, object],
    comparables_data: Optional[Dict[str, object]],
    logger: LoggerLike,
) -> TitanBenchmarkSelection:
    """Apply Titan-pushed multiples and percentile bands when available."""
    if not has_titan_enrichment:
        return TitanBenchmarkSelection(
            ev_ebitda_ratio=ev_ebitda_ratio,
            revenue_multiple=revenue_multiple,
            pe_ratio=pe_ratio,
            data_source=data_source,
            data_source_details=data_source_details,
            comparables_data=comparables_data,
        )

    logger.debug(
        "PRIORITY -1: Using TITAN-PROVIDED resolved benchmark contract",
        extra={
            "business_type_id": business_type_id,
            "correlation_id": correlation_id,
            "priority": "HIGHEST - resolved benchmark contract via Titan",
            "titan_ev_ebitda": titan_ev_ebitda,
            "titan_ev_revenue": titan_ev_revenue,
            "titan_pe_ratio": titan_pe_ratio,
        },
    )

    if isinstance(titan_ev_ebitda, dict):
        titan_ebitda_median = titan_ev_ebitda.get("median")
        if titan_ebitda_median is not None and float(titan_ebitda_median) > 0:
            ev_ebitda_ratio = to_decimal(titan_ebitda_median)
            logger.debug(
                "Using Titan EV/EBITDA median",
                extra={"source": "titan_enrichment", "value": ev_ebitda_ratio},
            )

    if isinstance(titan_ev_revenue, dict):
        titan_revenue_median = titan_ev_revenue.get("median")
        if titan_revenue_median is not None and float(titan_revenue_median) > 0:
            revenue_multiple = to_decimal(titan_revenue_median)
            logger.debug(
                "Using Titan EV/Revenue median",
                extra={"source": "titan_enrichment", "value": revenue_multiple},
            )

    if isinstance(titan_pe_ratio, dict):
        titan_pe_median = titan_pe_ratio.get("median")
        if titan_pe_median is not None and float(titan_pe_median) > 0:
            pe_ratio = to_decimal(titan_pe_median)
            logger.debug(
                "Using Titan P/E median",
                extra={"source": "titan_enrichment", "value": pe_ratio},
            )

    titan_has_valid_ebitda = ev_ebitda_ratio is not None and ev_ebitda_ratio > 0
    titan_has_valid_revenue = revenue_multiple is not None and revenue_multiple > 0
    if not (titan_has_valid_ebitda or titan_has_valid_revenue):
        return TitanBenchmarkSelection(
            ev_ebitda_ratio=ev_ebitda_ratio,
            revenue_multiple=revenue_multiple,
            pe_ratio=pe_ratio,
            data_source=data_source,
            data_source_details=data_source_details,
            comparables_data=comparables_data,
        )

    data_source = "titan_enrichment"
    titan_percentiles = _extract_titan_percentiles(
        titan_ev_ebitda=titan_ev_ebitda,
        titan_ev_revenue=titan_ev_revenue,
        ev_ebitda_ratio=ev_ebitda_ratio,
        revenue_multiple=revenue_multiple,
        logger=logger,
    )
    if titan_percentiles:
        if comparables_data is None:
            comparables_data = dict(titan_percentiles)
        else:
            comparables_data = {**comparables_data, **titan_percentiles}
        logger.debug(
            "Populated percentile distributions from resolved benchmark contract",
            extra={
                "percentiles_extracted": list(titan_percentiles.keys()),
                "ev_ebitda_p25": titan_percentiles.get("ev_ebitda_p25"),
                "ev_ebitda_p75": titan_percentiles.get("ev_ebitda_p75"),
                "ev_revenue_p25": titan_percentiles.get("ev_revenue_p25"),
                "ev_revenue_p75": titan_percentiles.get("ev_revenue_p75"),
                "source": "Upswitch index benchmark contract via Titan API",
            },
        )

    multiples_source = "Upswitch index benchmark contract"
    multiples_sample_size = None
    multiples_quality_score = None
    if isinstance(titan_multiples_metadata, dict):
        multiples_source = titan_multiples_metadata.get("source", multiples_source)
        multiples_sample_size = titan_multiples_metadata.get("sample_size")
        multiples_quality_score = titan_multiples_metadata.get("quality_score")
    if used_synced_business_types_db:
        multiples_source = (
            "Upswitch synced business-types DB weighted mix"
            if used_synced_business_type_mix_db
            else "Upswitch synced business-types DB"
        )

    data_source_details = {
        "business_type_id": business_type_id,
        "source": (
            "business_type_db_weighted_mix"
            if used_synced_business_type_mix_db
            else ("business_type_db" if used_synced_business_types_db else "titan_enrichment")
        ),
        "business_type_mix": business_type_mix if used_synced_business_type_mix_db else None,
        "ev_ebitda": ev_ebitda_ratio,
        "ev_revenue": revenue_multiple,
        "pe": pe_ratio,
        "correlation_id": correlation_id,
        "priority": "HIGHEST (-1)",
        "multiples_source": multiples_source,
        "multiples_sample_size": multiples_sample_size,
        "multiples_quality_score": multiples_quality_score,
        "ev_ebitda_distribution": titan_ev_ebitda if isinstance(titan_ev_ebitda, dict) else None,
        "ev_revenue_distribution": titan_ev_revenue if isinstance(titan_ev_revenue, dict) else None,
        "pe_distribution": titan_pe_ratio if isinstance(titan_pe_ratio, dict) else None,
        "benchmark_contract": normalized_benchmark_contract,
        "benchmark_provenance": normalized_benchmark_contract,
        "academic_sources": [
            "Upswitch index benchmark contract",
        ],
        "academic_citations": "Upswitch/benchmark contract",
        "source_explanation": (
            "The valuation multiple and report explanation use the same resolved "
            f"benchmark contract for business type '{business_type_id}'."
        ),
        "calibration_methodology": normalized_benchmark_contract.get("methodology_version"),
    }

    logger.debug(
        "SUCCESS: Using TITAN-PROVIDED multiples (PRIORITY -1)",
        extra={
            "business_type_id": business_type_id,
            "ev_ebitda": ev_ebitda_ratio,
            "ev_revenue": revenue_multiple,
            "pe": pe_ratio,
            "data_source": "titan_enrichment",
            "correlation_id": correlation_id,
            "multiples_source": multiples_source,
        },
    )

    return TitanBenchmarkSelection(
        ev_ebitda_ratio=ev_ebitda_ratio,
        revenue_multiple=revenue_multiple,
        pe_ratio=pe_ratio,
        data_source=data_source,
        data_source_details=data_source_details,
        comparables_data=comparables_data,
    )


def _extract_titan_percentiles(
    *,
    titan_ev_ebitda: object,
    titan_ev_revenue: object,
    ev_ebitda_ratio: Optional[Decimal],
    revenue_multiple: Optional[Decimal],
    logger: LoggerLike,
) -> Dict[str, object]:
    titan_percentiles: Dict[str, object] = {}
    if isinstance(titan_ev_ebitda, dict):
        for pct_key in ("p10", "p25", "p75", "p90"):
            raw_val = titan_ev_ebitda.get(pct_key)
            if raw_val is not None:
                titan_percentiles[f"ev_ebitda_{pct_key}"] = to_decimal(raw_val)
        if ev_ebitda_ratio is not None:
            titan_percentiles["ev_ebitda_p50"] = ev_ebitda_ratio

    if isinstance(titan_ev_revenue, dict):
        for pct_key in ("p10", "p25", "p75", "p90"):
            raw_val = titan_ev_revenue.get(pct_key)
            if raw_val is not None:
                titan_percentiles[f"ev_revenue_{pct_key}"] = to_decimal(raw_val)
        if revenue_multiple is not None:
            titan_percentiles["ev_revenue_p50"] = revenue_multiple

    _drop_non_monotone_titan_bands(titan_percentiles, logger)
    return titan_percentiles


def _drop_non_monotone_titan_bands(
    titan_percentiles: Dict[str, object], logger: LoggerLike
) -> None:
    for metric in ("ev_ebitda", "ev_revenue"):
        chain = [
            titan_percentiles.get(f"{metric}_{key}") for key in ("p10", "p25", "p50", "p75", "p90")
        ]
        present = [value for value in chain if value is not None]
        if len(present) >= 2 and any(
            present[index] > present[index + 1] for index in range(len(present) - 1)
        ):
            for key in ("p10", "p25", "p75", "p90"):
                titan_percentiles.pop(f"{metric}_{key}", None)
            logger.warning(
                "Dropped non-monotone Titan-pushed percentile band",
                extra={"metric": metric, "chain": [str(value) for value in chain]},
            )
