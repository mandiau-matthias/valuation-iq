from decimal import Decimal
from typing import TypeAlias, cast

from src.services.reports.protocol_adapter import DictWrapper, _unwrap

BenchmarkContract: TypeAlias = dict[str, object]
BenchmarkContracts: TypeAlias = dict[str, BenchmarkContract]

REQUIRED_BENCHMARK_PROVENANCE_FIELDS = (
    "benchmark_id",
    "dataset_version_id",
    "country_code",
    "region_key",
    "tier",
    "sample_size",
    "confidence_band",
    "source_mix",
    "evidence_summary",
    "published_at",
    "methodology_version",
    "scope_stage",
)

PRESENCE_ONLY_BENCHMARK_PROVENANCE_FIELDS = ("source_mix",)

BENCHMARK_PROVENANCE_OUTPUT_FIELDS = (
    "benchmark_id",
    "dataset_version_id",
    "country_code",
    "region_key",
    "tier",
    "walk_step",
    "walk_proximity",
    "sample_size",
    "confidence_band",
    "confidence_score",
    "source_mix",
    "evidence_summary",
    "published_at",
    "methodology_version",
    "benchmark_scope",
    "benchmark_kind",
    "is_borrowed",
    "source_business_type_id",
    "source_business_type_title",
    "source_primary_nace_code",
    "borrowed_from_country",
    "scope_stage",
)

_BENCHMARK_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "schema_version": ("schema_version", "schemaVersion"),
    "status": ("status",),
    "source": ("source",),
    "data_source": ("data_source", "dataSource"),
    "primary_metric": ("primary_metric", "primaryMetric"),
    "metric_name": ("metric_name", "metricName"),
    "benchmark_id": ("benchmark_id", "benchmarkId"),
    "dataset_version_id": ("dataset_version_id", "datasetVersionId"),
    "country_code": ("country_code", "countryCode"),
    "region_key": ("region_key", "regionKey"),
    "tier": ("tier",),
    "walk_step": ("walk_step", "walkStep"),
    "walk_proximity": ("walk_proximity", "walkProximity"),
    "sample_size": ("sample_size", "sampleSize"),
    "confidence_band": ("confidence_band", "confidenceBand"),
    "confidence_score": ("confidence_score", "confidenceScore"),
    "source_mix": ("source_mix", "sourceMix"),
    "evidence_summary": ("evidence_summary", "evidenceSummary"),
    "published_at": ("published_at", "publishedAt"),
    "methodology_version": ("methodology_version", "methodologyVersion"),
    "benchmark_scope": ("benchmark_scope", "benchmarkScope"),
    "benchmark_kind": ("benchmark_kind", "benchmarkKind"),
    "is_borrowed": ("is_borrowed", "isBorrowed"),
    "source_business_type_id": ("source_business_type_id", "sourceBusinessTypeId"),
    "source_business_type_title": (
        "source_business_type_title",
        "sourceBusinessTypeTitle",
    ),
    "source_primary_nace_code": ("source_primary_nace_code", "sourcePrimaryNaceCode"),
    "borrowed_from_country": ("borrowed_from_country", "borrowedFromCountry"),
    "scope_stage": ("scope_stage", "scopeStage"),
    "metrics": ("metrics",),
    "business_type_id": ("business_type_id", "businessTypeId"),
    "primary_nace_code": ("primary_nace_code", "primaryNaceCode"),
    "geography": ("geography",),
    "company_size_band": ("company_size_band", "companySizeBand"),
    "release_policy": ("release_policy", "releasePolicy"),
    "standalone_conclusion_eligible": (
        "standalone_conclusion_eligible",
        "standaloneConclusionEligible",
    ),
    "release_blockers": ("release_blockers", "releaseBlockers"),
}

_BENCHMARK_METRIC_FIELDS = (
    "metric_name",
    "benchmark_id",
    "business_type_id",
    "country_code",
    "median",
    "p10",
    "p25",
    "p75",
    "p90",
    *BENCHMARK_PROVENANCE_OUTPUT_FIELDS,
    "release_policy",
    "standalone_conclusion_eligible",
    "release_blockers",
    "data_source",
)


def as_plain_mapping(value: object) -> BenchmarkContract | None:
    value = _unwrap(value) if isinstance(value, DictWrapper) else value
    if isinstance(value, dict):
        return cast(BenchmarkContract, value)

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return cast(BenchmarkContract, dumped) if isinstance(dumped, dict) else None
    return None


def _benchmark_field(mapping: BenchmarkContract, field: str) -> object:
    for key in _BENCHMARK_FIELD_ALIASES.get(field, (field,)):
        if key in mapping:
            return mapping.get(key)
    return None


def _normalize_metric_contract(
    metric_name: str,
    raw_metric: object,
) -> BenchmarkContract:
    metric = as_plain_mapping(raw_metric) or {}
    normalized = {field: _benchmark_field(metric, field) for field in _BENCHMARK_METRIC_FIELDS}
    normalized["metric_name"] = normalized.get("metric_name") or metric_name
    return normalized


def _default_scope_stage(contract: BenchmarkContract) -> str:
    country_code = str(contract.get("country_code") or "").upper()
    region_key = str(contract.get("region_key") or "").upper()
    is_borrowed = contract.get("is_borrowed") is True
    if country_code in {"BE", "NL", "LU"} and not is_borrowed:
        return "native_benelux"
    if country_code in {"BE", "NL", "LU"}:
        return "borrowed_benelux"
    if region_key == "GLOBAL":
        return "global_compatibility_beta"
    return "beta_borrowed"


def normalize_benchmark_contract(raw_contract: object) -> BenchmarkContract:
    """Normalize snake/camel and nested-metric contracts without API imports.

    Report generation is imported by the valuation route package itself, so a
    report helper must not import the route-level normalizer. Keeping the small
    normalization boundary here prevents a cold-start circular import while
    preserving the same canonical provenance shape for API, screen and PDF
    report outputs.
    """

    contract = as_plain_mapping(raw_contract) or {}
    metrics_raw = as_plain_mapping(_benchmark_field(contract, "metrics")) or {}
    metrics = {
        str(name): _normalize_metric_contract(str(name), metric)
        for name, metric in metrics_raw.items()
        if as_plain_mapping(metric) is not None
    }
    primary_metric = _benchmark_field(contract, "primary_metric")
    primary_payload = metrics.get(str(primary_metric or ""))
    if primary_payload is None and metrics:
        primary_payload = next(iter(metrics.values()))

    def contract_or_metric(field: str) -> object:
        value = _benchmark_field(contract, field)
        if value is not None:
            return value
        return _benchmark_field(primary_payload or {}, field)

    normalized: BenchmarkContract = {
        "schema_version": _benchmark_field(contract, "schema_version"),
        "status": _benchmark_field(contract, "status"),
        "source": _benchmark_field(contract, "source"),
        "business_type_id": _benchmark_field(contract, "business_type_id"),
        "primary_nace_code": _benchmark_field(contract, "primary_nace_code"),
        "geography": _benchmark_field(contract, "geography"),
        "company_size_band": _benchmark_field(contract, "company_size_band"),
        "release_policy": contract_or_metric("release_policy"),
        "standalone_conclusion_eligible": contract_or_metric("standalone_conclusion_eligible"),
        "release_blockers": contract_or_metric("release_blockers") or [],
        "primary_metric": primary_metric,
        **{field: contract_or_metric(field) for field in BENCHMARK_PROVENANCE_OUTPUT_FIELDS},
        "data_source": contract_or_metric("data_source"),
        "multiple_trend": contract.get("multiple_trend", contract.get("multipleTrend")),
        "metrics": metrics,
    }
    if not normalized.get("scope_stage"):
        normalized["scope_stage"] = _default_scope_stage(normalized)
    return normalized


def has_benchmark_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list, tuple, set)):
        return len(value) > 0
    return True


def missing_benchmark_provenance(contract: BenchmarkContract | None) -> list[str]:
    if not contract:
        return ["benchmark_contract"]

    missing = [
        field
        for field in REQUIRED_BENCHMARK_PROVENANCE_FIELDS
        if field not in PRESENCE_ONLY_BENCHMARK_PROVENANCE_FIELDS
        and not has_benchmark_value(contract.get(field))
    ]

    # Keep report rendering in lock-step with the valuation preflight gate:
    # source_mix is JSON provenance with a valid empty-object catalog-backfill
    # shape. Presence matters; per-source decomposition may legitimately be
    # unavailable.
    if not isinstance(contract.get("source_mix"), dict):
        missing.append("source_mix")

    sample_size = contract.get("sample_size")
    try:
        if sample_size is None or Decimal(str(sample_size)) <= 0:
            missing.append("sample_size")
    except Exception:
        missing.append("sample_size")

    if "walk_step" not in contract:
        missing.append("walk_step")

    return sorted(set(missing))


def benchmark_contract_is_resolved(contract: BenchmarkContract | None) -> bool:
    if not contract:
        return False
    status = contract.get("status")
    return status is None or str(status).strip().lower() == "resolved"


def benchmark_contract_metric_names(contract: BenchmarkContract | None) -> set[str]:
    if not contract:
        return set()

    names: set[str] = set()
    metrics = as_plain_mapping(contract.get("metrics"))
    if metrics:
        for metric_name, payload in metrics.items():
            metric_payload = as_plain_mapping(payload)
            if payload is not None and (
                metric_payload is None or metric_payload.get("benchmark_id")
            ):
                names.add(str(metric_name).strip().lower())

    for key in ("primary_metric", "primaryMetric", "metric_name", "metric"):
        value = contract.get(key)
        if isinstance(value, str) and value.strip():
            names.add(value.strip().lower())

    return names


def benchmark_contract_supports_metric(
    contract: BenchmarkContract | None,
    aliases: tuple[str, ...],
    *,
    allow_unscoped_contract: bool = False,
) -> bool:
    names = benchmark_contract_metric_names(contract)
    if not names:
        return allow_unscoped_contract and bool(contract)
    return bool(names & {alias.strip().lower() for alias in aliases})


def extract_benchmark_contracts_from_calibration(
    calibration_data: BenchmarkContract,
) -> BenchmarkContracts:
    contracts: BenchmarkContracts = {}
    for container in _benchmark_contract_containers(calibration_data):
        mapping = as_plain_mapping(container)
        if not mapping:
            continue
        _add_nested_benchmark_contracts(contracts, mapping)
        _add_single_benchmark_contract(contracts, mapping)
    return contracts


def _benchmark_contract_containers(calibration_data: BenchmarkContract) -> list[object]:
    return [
        calibration_data,
        calibration_data.get("multiples_metadata"),
        calibration_data.get("industry_benchmarks"),
        calibration_data.get("ev_ebitda_multiple"),
        calibration_data.get("ev_revenue_multiple"),
    ]


def _add_nested_benchmark_contracts(
    contracts: BenchmarkContracts,
    mapping: BenchmarkContract,
) -> None:
    nested_contracts = mapping.get("benchmark_contracts") or mapping.get("benchmarkContracts") or {}
    nested_contracts = as_plain_mapping(nested_contracts) or {}
    for metric_name, contract in nested_contracts.items():
        contract_mapping = as_plain_mapping(contract)
        if contract_mapping:
            contracts[_normalized_metric_name(metric_name)] = contract_mapping


def _add_single_benchmark_contract(
    contracts: BenchmarkContracts,
    mapping: BenchmarkContract,
) -> None:
    contract = mapping.get("benchmark_contract") or mapping.get("benchmarkContract")
    contract_mapping = as_plain_mapping(contract)
    if contract_mapping:
        contracts.setdefault(_contract_metric_name(contract_mapping), contract_mapping)


def _contract_metric_name(contract_mapping: BenchmarkContract) -> str:
    return _normalized_metric_name(
        contract_mapping.get("primary_metric")
        or contract_mapping.get("primaryMetric")
        or contract_mapping.get("metric_name")
        or contract_mapping.get("metric")
        or "ev_ebitda"
    )


def _normalized_metric_name(metric_name: object) -> str:
    return str(metric_name).strip().lower()


def resolved_contract_for_metric(
    contracts: BenchmarkContracts,
    aliases: tuple[str, ...],
) -> BenchmarkContract | None:
    alias_set = {alias.strip().lower() for alias in aliases}
    for metric_name, contract in contracts.items():
        if metric_name in alias_set or benchmark_contract_supports_metric(
            contract,
            aliases,
            allow_unscoped_contract=False,
        ):
            if benchmark_contract_is_resolved(contract) and not missing_benchmark_provenance(
                contract
            ):
                return contract
    return None
