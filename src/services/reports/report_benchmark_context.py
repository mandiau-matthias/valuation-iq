"""Benchmark calibration extraction for report aggregation."""

from collections.abc import Callable
from typing import Optional, Protocol, TypeAlias, cast

from src.domain.report_contact.sanitize import is_legal_form_label
from src.services.reports.protocol_adapter import DictWrapper, _attr, _unwrap
from src.services.reports.report_benchmark_anchor_fallbacks import (
    _ENGINE_SECTOR_ANCHOR_SOURCE,
    apply_benchmark_anchor_fallbacks,
)
from src.services.reports.report_benchmark_band import metric_band as _metric_band
from src.services.reports.report_benchmark_contracts import (
    BENCHMARK_PROVENANCE_OUTPUT_FIELDS,
    as_plain_mapping,
    benchmark_contract_is_resolved,
    extract_benchmark_contracts_from_calibration,
    missing_benchmark_provenance,
    normalize_benchmark_contract,
    resolved_contract_for_metric,
)
from src.utils.decimal_helpers import safe_float

ReportMap: TypeAlias = dict[str, object]
BenchmarkContracts: TypeAlias = dict[str, ReportMap]
SectorLabelPredicate: TypeAlias = Callable[[object], bool]


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> object: ...

    def warning(self, msg: str, *args: object, **kwargs: object) -> object: ...


class Gettable(Protocol):
    def get(self, key: str, default: object = None) -> object: ...


_FLAT_INDUSTRY_BENCHMARK_KEYS = (
    "typical_revenue_min",
    "typical_revenue_max",
    "typical_revenue_median",
    "typical_ebitda_margin_min",
    "typical_ebitda_margin_median",
    "revenue_growth_benchmark",
)

_DIRECT_MULTIPLE_ALIASES = {
    "ev_ebitda_multiple": ("ev_ebitda_multiple", "ebitda_multiple"),
    "ev_revenue_multiple": ("ev_revenue_multiple", "revenue_multiple"),
}

_BENCHMARK_CONTRACT_KEYS = (
    "benchmark_contract",
    "benchmarkContract",
    "benchmark_provenance",
    "benchmarkProvenance",
)
_BENCHMARK_CONTRACTS_KEYS = ("benchmark_contracts", "benchmarkContracts")

_METRIC_ALIASES = {
    "ev_ebitda_multiple": ("ev_ebitda", "ev_ebitda_multiple", "ebitda_multiple"),
    "ev_revenue_multiple": ("ev_revenue", "ev_revenue_multiple", "revenue_multiple"),
}


def _unwrap_dictwrapper(value: object) -> object:
    return _unwrap(value) if isinstance(value, DictWrapper) else value


def _as_report_map(value: object) -> Optional[ReportMap]:
    mapping = as_plain_mapping(value)
    return cast(ReportMap, mapping) if mapping is not None else None


def _as_gettable(value: object) -> Optional[Gettable]:
    unwrapped = _unwrap_dictwrapper(value)
    get_method = getattr(unwrapped, "get", None)
    if unwrapped and callable(get_method):
        return cast(Gettable, unwrapped)
    return None


def _has_calibration_source(request: object) -> bool:
    return bool(
        getattr(request, "ev_ebitda_multiple", None)
        or getattr(request, "ebitda_multiple", None)
        or getattr(request, "ev_revenue_multiple", None)
        or getattr(request, "revenue_multiple", None)
        or getattr(request, "industry_benchmarks", None)
        or getattr(request, "data_sources", None)
        or getattr(request, "multiples_valuation", None)
    )


def _add_direct_multiples(request: object, calibration: ReportMap) -> None:
    for target_key, aliases in _DIRECT_MULTIPLE_ALIASES.items():
        direct_value = _first_request_attr(request, aliases)
        if direct_value:
            calibration[target_key] = _unwrap_dictwrapper(direct_value)

    multiples_valuation = _as_report_map(getattr(request, "multiples_valuation", None)) or {}
    for target_key, aliases in _DIRECT_MULTIPLE_ALIASES.items():
        if calibration.get(target_key):
            continue
        valuation_value = _first_map_value(multiples_valuation, aliases)
        if valuation_value:
            calibration[target_key] = _unwrap_dictwrapper(valuation_value)


def _normalized_contract(value: object) -> Optional[ReportMap]:
    raw_contract = _as_report_map(value)
    if not raw_contract:
        return None
    normalized = normalize_benchmark_contract(raw_contract)
    return cast(ReportMap, normalized) if normalized else raw_contract


def _contract_metric_payload(
    contract: ReportMap,
    aliases: tuple[str, ...],
) -> Optional[ReportMap]:
    metrics = _as_report_map(contract.get("metrics")) or {}
    primary_metric = str(contract.get("primary_metric") or "").strip().lower()
    alias_set = {alias.lower() for alias in aliases}

    if primary_metric in alias_set:
        primary_payload = _as_report_map(metrics.get(primary_metric))
        if primary_payload:
            return primary_payload

    for metric_name, raw_payload in metrics.items():
        if str(metric_name).strip().lower() not in alias_set:
            continue
        payload = _as_report_map(raw_payload)
        if payload:
            return payload
    return None


def _apply_contract_multiple_bands(calibration: ReportMap) -> None:
    contracts = cast(
        BenchmarkContracts,
        extract_benchmark_contracts_from_calibration(calibration),
    )
    for target_key, aliases in _METRIC_ALIASES.items():
        contract = resolved_contract_for_metric(
            contracts,
            aliases,
        )
        if not contract:
            continue
        metric_payload = _contract_metric_payload(contract, aliases)
        band = _metric_band(metric_payload or contract)
        if band:
            # A benchmark contract describes the market reference distribution.
            # It is therefore authoritative over the applied company multiple
            # carried by the legacy ``multiples_valuation`` alias.
            calibration[target_key] = band


def _add_multiples_valuation_provenance(
    request: object,
    calibration: ReportMap,
) -> None:
    """Recover provenance nested in the legacy report alias.

    Stateless report assembly aliases ``multiples_results`` to
    ``multiples_valuation`` for the legacy aggregator.  The alias contains the
    complete benchmark contract, not just the applied multiple; dropping that
    nested contract caused valid percentile bands and sample metadata to render
    as zeroes.  Keep the complete normalized contract attached to calibration.
    """

    multiples_valuation = _as_report_map(getattr(request, "multiples_valuation", None))
    if not multiples_valuation:
        return

    raw_contract = _first_map_value(multiples_valuation, _BENCHMARK_CONTRACT_KEYS)
    contract = _normalized_contract(raw_contract)
    if contract and _should_replace_benchmark_contract(calibration):
        calibration["benchmark_contract"] = contract

    raw_contracts = _first_map_value(multiples_valuation, _BENCHMARK_CONTRACTS_KEYS)
    contract_map = _as_report_map(raw_contracts)
    if contract_map and not calibration.get("benchmark_contracts"):
        calibration["benchmark_contracts"] = {
            str(metric): _normalized_contract(value) or value
            for metric, value in contract_map.items()
        }


def build_benchmark_provenance_snapshot(
    multiples_valuation: object,
) -> Optional[ReportMap]:
    """Return the report/API benchmark snapshot from one canonical contract.

    Both rendered report trees and the stateless ``report_data`` response use
    this shape.  Keeping the percentile band beside the provenance prevents a
    future alias or serialization layer from pairing one contract's metadata
    with another multiple band.
    """

    valuation = _as_report_map(multiples_valuation)
    if not valuation:
        return None
    raw_contract = _first_map_value(valuation, _BENCHMARK_CONTRACT_KEYS)
    contract = _normalized_contract(raw_contract)
    if (
        not contract
        or not benchmark_contract_is_resolved(contract)
        or missing_benchmark_provenance(contract)
    ):
        return None

    primary_metric = str(contract.get("primary_metric") or "").strip().lower()
    ordered_targets = list(_METRIC_ALIASES.items())
    ordered_targets.sort(
        key=lambda item: 0 if primary_metric in {alias.lower() for alias in item[1]} else 1
    )
    metric_name: Optional[str] = None
    metric_payload: Optional[ReportMap] = None
    band: Optional[ReportMap] = None
    for target_key, aliases in ordered_targets:
        candidate_payload = _contract_metric_payload(contract, aliases)
        candidate_band = _metric_band(candidate_payload or contract)
        if candidate_band:
            metric_name = target_key
            metric_payload = candidate_payload or contract
            band = candidate_band
            break
    if not band:
        return None

    metric_payload = metric_payload or {}

    def metric_or_contract(key: str) -> object:
        value = metric_payload.get(key)
        return value if value is not None else contract.get(key)

    return {
        "metric": metric_name,
        "low": band.get("p25"),
        "mid": band.get("median"),
        "high": band.get("p75"),
        "sample_size": metric_or_contract("sample_size"),
        "source": metric_or_contract("data_source") or contract.get("source"),
        "published_at": metric_or_contract("published_at"),
        "benchmark_id": metric_or_contract("benchmark_id"),
        "dataset_version_id": metric_or_contract("dataset_version_id"),
        "country_code": metric_or_contract("country_code"),
        "region_key": metric_or_contract("region_key"),
        "tier": metric_or_contract("tier"),
        "walk_step": metric_or_contract("walk_step"),
        "scope_stage": metric_or_contract("scope_stage"),
        "confidence_band": metric_or_contract("confidence_band"),
        "source_mix": metric_or_contract("source_mix"),
        "evidence_summary": metric_or_contract("evidence_summary"),
        "methodology_version": metric_or_contract("methodology_version"),
        "contract": contract,
    }


def _first_request_attr(source: object, keys: tuple[str, ...]) -> object:
    for key in keys:
        value = getattr(source, key, None)
        if value:
            return value
    return None


def _first_map_value(source: ReportMap, keys: tuple[str, ...]) -> object:
    for key in keys:
        value = source.get(key)
        if value:
            return value
    return None


def _add_data_source_contract(request: object, calibration: ReportMap) -> None:
    data_sources = _as_report_map(getattr(request, "data_sources", None)) or {}
    multiples_source = _as_report_map(data_sources.get("multiples")) or {}
    benchmark_contract = _first_map_value(multiples_source, _BENCHMARK_CONTRACT_KEYS)
    benchmark_contracts = _first_map_value(multiples_source, _BENCHMARK_CONTRACTS_KEYS)
    if benchmark_contract and _should_replace_benchmark_contract(calibration):
        calibration["benchmark_contract"] = benchmark_contract
    if benchmark_contracts and not calibration.get("benchmark_contracts"):
        calibration["benchmark_contracts"] = benchmark_contracts


def _should_replace_benchmark_contract(calibration: ReportMap) -> bool:
    existing_contract = _as_report_map(calibration.get("benchmark_contract"))
    return not existing_contract or bool(missing_benchmark_provenance(existing_contract))


def _add_metadata(request: object, calibration: ReportMap) -> None:
    metadata = getattr(request, "multiples_metadata", None)
    if not metadata:
        return

    calibration["multiples_metadata"] = (
        _unwrap(metadata)
        if isinstance(metadata, DictWrapper)
        else metadata if isinstance(metadata, dict) else {}
    )
    metadata_map = _as_report_map(calibration["multiples_metadata"]) or {}
    benchmark_contract = metadata_map.get("benchmark_contract") or metadata_map.get(
        "benchmarkContract"
    )
    benchmark_contracts = metadata_map.get("benchmark_contracts") or metadata_map.get(
        "benchmarkContracts"
    )
    if benchmark_contract:
        calibration["benchmark_contract"] = benchmark_contract
    if benchmark_contracts:
        calibration["benchmark_contracts"] = benchmark_contracts


def _add_top_level_labels(request: object, calibration: ReportMap) -> None:
    request_contract = getattr(request, "benchmark_contract", None)
    if request_contract:
        calibration["benchmark_contract"] = request_contract

    sector = getattr(request, "sector", None)
    if sector:
        calibration["sector"] = sector
    sub_industry = getattr(request, "sub_industry", None)
    if sub_industry:
        calibration.setdefault("title", sub_industry)


def _add_typical_revenue(industry_benchmarks: ReportMap, calibration: ReportMap) -> None:
    typical_revenue = _unwrap_dictwrapper(industry_benchmarks.get("typical_revenue"))
    if isinstance(typical_revenue, dict):
        calibration.setdefault("typical_revenue_min", typical_revenue.get("min"))
        calibration.setdefault("typical_revenue_max", typical_revenue.get("max"))
        calibration.setdefault("typical_revenue_median", typical_revenue.get("median"))


def _add_typical_margin(industry_benchmarks: ReportMap, calibration: ReportMap) -> None:
    typical_margin = _unwrap_dictwrapper(industry_benchmarks.get("typical_ebitda_margin"))
    if isinstance(typical_margin, dict):
        calibration.setdefault("typical_ebitda_margin_min", typical_margin.get("min"))
        calibration.setdefault("typical_ebitda_margin_median", typical_margin.get("median"))


def _add_flat_industry_benchmark_values(
    industry_benchmarks: ReportMap,
    calibration: ReportMap,
) -> None:
    for key in _FLAT_INDUSTRY_BENCHMARK_KEYS:
        if industry_benchmarks.get(key) is not None:
            calibration.setdefault(key, industry_benchmarks[key])


def _add_industry_benchmarks(request: object, calibration: ReportMap) -> None:
    industry_benchmarks = _unwrap_dictwrapper(getattr(request, "industry_benchmarks", None))
    if not isinstance(industry_benchmarks, dict):
        return

    industry_benchmarks_map = cast(ReportMap, industry_benchmarks)
    calibration["industry_benchmarks"] = industry_benchmarks_map
    calibration.setdefault(
        "title",
        industry_benchmarks_map.get("business_type_title") or industry_benchmarks_map.get("title"),
    )
    calibration.setdefault("business_type_icon", industry_benchmarks_map.get("business_type_icon"))
    calibration.setdefault("sector", industry_benchmarks_map.get("sector"))
    if industry_benchmarks_map.get("benchmark_contract"):
        calibration.setdefault("benchmark_contract", industry_benchmarks_map["benchmark_contract"])
    if industry_benchmarks_map.get("benchmark_contracts"):
        calibration.setdefault(
            "benchmark_contracts", industry_benchmarks_map["benchmark_contracts"]
        )
    if industry_benchmarks_map.get("ev_ebitda_multiple") is not None:
        calibration.setdefault("ev_ebitda_multiple", industry_benchmarks_map["ev_ebitda_multiple"])
    if industry_benchmarks_map.get("ev_revenue_multiple") is not None:
        calibration.setdefault(
            "ev_revenue_multiple", industry_benchmarks_map["ev_revenue_multiple"]
        )

    _add_typical_revenue(industry_benchmarks_map, calibration)
    _add_typical_margin(industry_benchmarks_map, calibration)
    _add_flat_industry_benchmark_values(industry_benchmarks_map, calibration)


def extract_calibration_data_from_request(request: Optional[object]) -> Optional[ReportMap]:
    """Extract Titan enrichment data from the request for report benchmarks."""
    if request is None or not _has_calibration_source(request):
        return None

    calibration: ReportMap = {}
    _add_top_level_labels(request, calibration)
    _add_direct_multiples(request, calibration)
    _add_multiples_valuation_provenance(request, calibration)
    _add_metadata(request, calibration)
    _add_industry_benchmarks(request, calibration)
    _add_data_source_contract(request, calibration)
    _apply_contract_multiple_bands(calibration)
    return calibration if calibration else None


def initial_industry_benchmarks(business_type_id: Optional[str]) -> ReportMap:
    """Return the default industry benchmark report context."""
    return {
        "has_benchmarks": False,
        "business_type_id": business_type_id,
        "business_type_title": None,
        "business_type_icon": "\U0001f3e2",
        "sector": None,
        "ev_ebitda_p25": None,
        "ev_ebitda_p50": None,
        "ev_ebitda_p75": None,
        "ev_revenue_median": None,
        "median_ebitda_margin": None,
        "median_revenue_growth": None,
        "typical_revenue_min": None,
        "typical_revenue_max": None,
        "typical_revenue_median": None,
        "sample_size": None,
        "data_source": None,
        "country_code": None,
        "benchmark_contract": None,
        "benchmark_contracts": None,
        "benchmark_id": None,
        "dataset_version_id": None,
        "region_key": None,
        "tier": None,
        "walk_step": None,
        "confidence_band": None,
        "source_mix": None,
        "evidence_summary": None,
        "published_at": None,
        "methodology_version": None,
        "scope_stage": None,
    }


def _default_generic_sector_label(sector_label: object) -> bool:
    if not sector_label or not isinstance(sector_label, str):
        return False
    normalized = sector_label.replace("_", " ").replace("-", " ").strip().lower()
    return normalized in {
        "other",
        "service",
        "services",
        "retail",
        "retail service",
        "retail services",
        "general service",
        "general services",
    }


def _warn_unresolved_contracts(
    logger: Optional[LoggerLike],
    *,
    business_type_id: Optional[str],
    benchmark_contracts: BenchmarkContracts,
) -> None:
    if not logger:
        return
    logger.warning(
        "Ignoring report benchmark multiples because Upswitch Index provenance is incomplete or unresolved",
        extra={
            "business_type_id": business_type_id,
            "missing_provenance": {
                key: missing_benchmark_provenance(value)
                for key, value in benchmark_contracts.items()
            },
        },
    )


def _apply_representative_contract(
    benchmarks: ReportMap,
    *,
    representative_contract: Optional[ReportMap],
    benchmark_contracts: BenchmarkContracts,
) -> None:
    if not representative_contract:
        return
    benchmarks["benchmark_contract"] = representative_contract
    benchmarks["benchmark_contracts"] = benchmark_contracts or None
    for field in BENCHMARK_PROVENANCE_OUTPUT_FIELDS:
        if field in representative_contract:
            benchmarks[field] = representative_contract.get(field)
    benchmarks["data_source"] = "Upswitch index benchmark contract"
    benchmarks["country_code"] = representative_contract.get("country_code")
    benchmarks["sample_size"] = representative_contract.get("sample_size")


def _contract_business_type_title(benchmarks: ReportMap) -> object:
    contract = _unwrap_dictwrapper(benchmarks.get("benchmark_contract"))
    if isinstance(contract, dict) and contract.get("source_business_type_title"):
        return contract.get("source_business_type_title")
    return benchmarks.get("source_business_type_title")


def _apply_calibration_labels(
    benchmarks: ReportMap,
    calibration_data: ReportMap,
    *,
    is_generic_sector_label: SectorLabelPredicate,
) -> None:
    benchmarks["business_type_title"] = (
        calibration_data.get("title")
        or calibration_data.get("business_type_title")
        or _contract_business_type_title(benchmarks)
    )
    benchmarks["business_type_icon"] = calibration_data.get("business_type_icon") or "\U0001f3e2"
    raw_sector = calibration_data.get("sector")
    if (
        raw_sector
        and isinstance(raw_sector, str)
        and not is_generic_sector_label(raw_sector)
        and not is_legal_form_label(raw_sector)
    ):
        benchmarks["sector"] = raw_sector
    else:
        benchmarks["sector"] = None


def _apply_financial_ranges(benchmarks: ReportMap, calibration_data: ReportMap) -> None:
    if calibration_data.get("typical_revenue_min"):
        benchmarks["typical_revenue_min"] = safe_float(calibration_data["typical_revenue_min"])
    if calibration_data.get("typical_revenue_max"):
        benchmarks["typical_revenue_max"] = safe_float(calibration_data["typical_revenue_max"])
    if calibration_data.get("typical_revenue_median"):
        benchmarks["typical_revenue_median"] = safe_float(
            calibration_data["typical_revenue_median"]
        )
    if calibration_data.get("typical_ebitda_margin_min"):
        benchmarks["median_ebitda_margin"] = safe_float(
            calibration_data["typical_ebitda_margin_min"]
        )
    if calibration_data.get("typical_ebitda_margin_median"):
        benchmarks["median_ebitda_margin"] = safe_float(
            calibration_data["typical_ebitda_margin_median"]
        )


def _apply_ebitda_multiple(
    benchmarks: ReportMap,
    calibration_data: ReportMap,
    ev_ebitda_contract: Optional[ReportMap],
) -> None:
    ev_ebitda_dict = _unwrap_dictwrapper(calibration_data.get("ev_ebitda_multiple"))
    if ev_ebitda_contract and isinstance(ev_ebitda_dict, dict):
        if ev_ebitda_dict.get("median") is not None:
            benchmarks["ev_ebitda_p50"] = safe_float(ev_ebitda_dict["median"])
            benchmarks["has_benchmarks"] = True
        if ev_ebitda_dict.get("p25") is not None:
            benchmarks["ev_ebitda_p25"] = safe_float(ev_ebitda_dict["p25"])
        if ev_ebitda_dict.get("p75") is not None:
            benchmarks["ev_ebitda_p75"] = safe_float(ev_ebitda_dict["p75"])
    elif ev_ebitda_contract and ev_ebitda_dict is not None:
        benchmarks["ev_ebitda_p50"] = safe_float(ev_ebitda_dict)
        benchmarks["has_benchmarks"] = True


def _apply_revenue_multiple(
    benchmarks: ReportMap,
    calibration_data: ReportMap,
    ev_revenue_contract: Optional[ReportMap],
) -> None:
    ev_revenue_dict = _unwrap_dictwrapper(calibration_data.get("ev_revenue_multiple"))
    if ev_revenue_contract and isinstance(ev_revenue_dict, dict):
        if ev_revenue_dict.get("median") is not None:
            benchmarks["ev_revenue_median"] = safe_float(ev_revenue_dict["median"])
            benchmarks["has_benchmarks"] = True
    elif ev_revenue_contract and ev_revenue_dict is not None:
        benchmarks["ev_revenue_median"] = safe_float(ev_revenue_dict)
        benchmarks["has_benchmarks"] = True


def _apply_metadata_supplements(
    benchmarks: ReportMap,
    calibration_data: ReportMap,
) -> None:
    metadata = _as_report_map(calibration_data.get("multiples_metadata")) or {}
    if not benchmarks["sample_size"] and metadata.get("sample_size") is not None:
        benchmarks["sample_size"] = metadata["sample_size"]
    if calibration_data.get("revenue_growth_benchmark"):
        benchmarks["median_revenue_growth"] = safe_float(
            calibration_data["revenue_growth_benchmark"]
        )


def _log_benchmark_choice(
    logger: Optional[LoggerLike],
    *,
    business_type_id: Optional[str],
    benchmarks: ReportMap,
) -> None:
    if not logger:
        return
    logger.info(
        (
            "Using report benchmarks from Upswitch index benchmark contract"
            if benchmarks["has_benchmarks"]
            else "Report benchmark multiples unavailable without Upswitch index benchmark contract"
        ),
        extra={
            "business_type_id": business_type_id,
            "title": benchmarks["business_type_title"],
            "ev_ebitda_p25": benchmarks.get("ev_ebitda_p25"),
            "ev_ebitda_p50": benchmarks.get("ev_ebitda_p50"),
            "ev_ebitda_p75": benchmarks.get("ev_ebitda_p75"),
            "sample_size": benchmarks.get("sample_size"),
            "data_source": benchmarks.get("data_source"),
        },
    )


def _apply_calibration_benchmarks(
    benchmarks: ReportMap,
    calibration_data: ReportMap,
    *,
    business_type_id: Optional[str],
    is_generic_sector_label: SectorLabelPredicate,
    logger: Optional[LoggerLike],
) -> None:
    benchmark_contracts = cast(
        BenchmarkContracts, extract_benchmark_contracts_from_calibration(calibration_data)
    )
    ev_ebitda_contract = cast(
        Optional[ReportMap],
        resolved_contract_for_metric(
            benchmark_contracts,
            ("ev_ebitda", "ev_ebitda_multiple", "ebitda_multiple"),
        ),
    )
    ev_revenue_contract = cast(
        Optional[ReportMap],
        resolved_contract_for_metric(
            benchmark_contracts,
            ("ev_revenue", "ev_revenue_multiple", "revenue_multiple"),
        ),
    )
    representative_contract = ev_ebitda_contract or ev_revenue_contract
    _apply_representative_contract(
        benchmarks,
        representative_contract=representative_contract,
        benchmark_contracts=benchmark_contracts,
    )
    if not representative_contract and benchmark_contracts:
        _warn_unresolved_contracts(
            logger,
            business_type_id=business_type_id,
            benchmark_contracts=benchmark_contracts,
        )

    _apply_calibration_labels(
        benchmarks,
        calibration_data,
        is_generic_sector_label=is_generic_sector_label,
    )
    _apply_financial_ranges(benchmarks, calibration_data)
    _apply_ebitda_multiple(benchmarks, calibration_data, ev_ebitda_contract)
    _apply_revenue_multiple(benchmarks, calibration_data, ev_revenue_contract)
    _apply_metadata_supplements(benchmarks, calibration_data)
    _log_benchmark_choice(logger, business_type_id=business_type_id, benchmarks=benchmarks)


def _sector_from_response(response: object) -> Optional[object]:
    detailed_results = _as_gettable(getattr(response, "detailed_results", None))
    if detailed_results:
        return detailed_results.get("business_type_category") or detailed_results.get("industry")
    return None


def _normalized_sector(value: object) -> Optional[str]:
    if not value or str(value).lower() == "other":
        return None
    candidate = str(value).replace("_", " ").replace("-", " ").title()
    if is_legal_form_label(candidate):
        return None
    return candidate


def _apply_sector_fallbacks(
    benchmarks: ReportMap,
    *,
    business_type_id: Optional[str],
    response: object,
    is_generic_sector_label: SectorLabelPredicate,
) -> None:
    response_sector = _normalized_sector(_sector_from_response(response))
    if response_sector and (
        not benchmarks["sector"] or is_generic_sector_label(benchmarks["sector"])
    ):
        benchmarks["sector"] = response_sector

    if benchmarks["sector"]:
        return
    if response_sector:
        benchmarks["sector"] = response_sector
        return
    business_type_sector = _normalized_sector(business_type_id)
    if business_type_sector:
        benchmarks["sector"] = business_type_sector


def build_industry_benchmarks(
    *,
    business_type_id: Optional[str],
    business_type_mix: Optional[list[dict[str, object]]] = None,
    nace_code: Optional[str],
    response: object,
    calibration_data: Optional[ReportMap] = None,
    is_generic_sector_label: Optional[SectorLabelPredicate] = None,
    logger: Optional[LoggerLike] = None,
    country_code: Optional[str] = None,
    allow_mutable_anchor_fallbacks: bool = True,
) -> ReportMap:
    """Build report-ready industry benchmark context."""
    _ = nace_code
    generic_sector = is_generic_sector_label or _default_generic_sector_label
    benchmarks = initial_industry_benchmarks(business_type_id)

    if calibration_data:
        _apply_calibration_benchmarks(
            benchmarks,
            calibration_data,
            business_type_id=business_type_id,
            is_generic_sector_label=generic_sector,
            logger=logger,
        )
    _apply_sector_fallbacks(
        benchmarks,
        business_type_id=business_type_id,
        response=response,
        is_generic_sector_label=generic_sector,
    )
    # Legacy reports may still use a mutable DB/engine anchor. Canonical runs
    # must render exclusively from their sealed benchmark snapshot; otherwise
    # the same run hash can produce a different PDF after a DB refresh.
    if allow_mutable_anchor_fallbacks:
        apply_benchmark_anchor_fallbacks(
            benchmarks,
            business_type_id=business_type_id,
            business_type_mix=business_type_mix,
            country_code=country_code,
            response=response,
        )
    return benchmarks


def build_benchmark_report_context(
    *,
    industry_benchmarks: ReportMap,
    business_type_id: Optional[str],
    business_type_title: object,
    business_type_icon: object,
    sector: object,
    nace_code: Optional[str],
    benchmark_data_source_label: object,
    neutral_benchmark_source_label: object,
) -> ReportMap:
    """Flatten resolved benchmark data into the main report template contract."""
    has_benchmarks = bool(industry_benchmarks.get("has_benchmarks", False))
    return {
        "industry_benchmarks": industry_benchmarks,
        "has_industry_benchmarks": has_benchmarks,
        "business_type_id": business_type_id,
        "business_type_title": business_type_title,
        "business_type_icon": business_type_icon,
        "sector": sector,
        "nace_code": nace_code,
        "benchmark_ev_ebitda_p25": industry_benchmarks.get("ev_ebitda_p25"),
        "benchmark_ev_ebitda_p50": industry_benchmarks.get("ev_ebitda_p50"),
        "benchmark_ev_ebitda_p75": industry_benchmarks.get("ev_ebitda_p75"),
        "benchmark_ev_revenue_median": industry_benchmarks.get("ev_revenue_median"),
        "benchmark_ebitda_margin": industry_benchmarks.get("median_ebitda_margin"),
        "benchmark_revenue_growth": industry_benchmarks.get("median_revenue_growth"),
        "benchmark_revenue_min": industry_benchmarks.get("typical_revenue_min"),
        "benchmark_revenue_max": industry_benchmarks.get("typical_revenue_max"),
        "benchmark_revenue_median": industry_benchmarks.get("typical_revenue_median"),
        "benchmark_sample_size": (
            industry_benchmarks.get("sample_size") if has_benchmarks else None
        ),
        "benchmark_data_source": (
            benchmark_data_source_label if has_benchmarks else neutral_benchmark_source_label
        ),
        "benchmark_contract": industry_benchmarks.get("benchmark_contract"),
        "benchmark_contracts": industry_benchmarks.get("benchmark_contracts"),
        "benchmark_id": industry_benchmarks.get("benchmark_id"),
        "benchmark_dataset_version_id": industry_benchmarks.get("dataset_version_id"),
        "benchmark_country_code": industry_benchmarks.get("country_code"),
        "benchmark_region_key": industry_benchmarks.get("region_key"),
        "benchmark_tier": industry_benchmarks.get("tier"),
        "benchmark_walk_step": industry_benchmarks.get("walk_step"),
        "benchmark_confidence_band": industry_benchmarks.get("confidence_band"),
        "benchmark_source_mix": industry_benchmarks.get("source_mix"),
        "benchmark_evidence_summary": industry_benchmarks.get("evidence_summary"),
        "benchmark_published_at": industry_benchmarks.get("published_at"),
        "benchmark_methodology_version": industry_benchmarks.get("methodology_version"),
        "benchmark_scope_stage": industry_benchmarks.get("scope_stage"),
    }
