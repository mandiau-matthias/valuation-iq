"""Utilities for Upswitch Index benchmark contracts.

The valuation pipeline must treat "resolved" as more than a status string:
every publishable multiple needs complete provenance and a staged local/borrowed
scope. These helpers accept both Python snake_case and Titan camelCase payloads
without relaxing the required contract fields.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import TypeAlias

JsonMap: TypeAlias = dict[str, object]

REQUIRED_BENCHMARK_PROVENANCE_FIELDS = (
    "benchmark_id",
    "dataset_version_id",
    "country_code",
    "region_key",
    "tier",
    "walk_step",
    "sample_size",
    "confidence_band",
    "source_mix",
    "evidence_summary",
    "published_at",
    "methodology_version",
    "scope_stage",
)

# `walk_step` and `source_mix` are presence-only; everything else must be
# non-empty.
#
# `source_mix` is JSONB with `default=dict` on the Delphi side
# (apps/delphi/src/database/models.py: benchmarks.source_mix). Catalog-backfill,
# BENELUX-aggregate, and single-source rows legitimately resolve with an empty
# `{}` source mix — there is simply no per-source decomposition to disclose.
# Provenance still flows through `evidence_summary`, which STAYS strict. Treating
# `source_mix` as presence-only (present, not None; may be `{}`) mirrors Titan's
# `missingRequiredResolvedBenchmarkFields` / `missingRequiredBenchmarkProvenanceForPython`
# and the documented cross-app contract, so the two engines never disagree on
# whether a benchmark is resolved (the BENCHMARK_CONTRACT_REQUIRED divergence:
# Titan would accept the contract and forward it, python would reject it → 500).
_PRESENCE_ONLY_FIELDS = ("walk_step", "source_mix")
_REQUIRED_NON_EMPTY_FIELDS = tuple(
    field for field in REQUIRED_BENCHMARK_PROVENANCE_FIELDS if field not in _PRESENCE_ONLY_FIELDS
)

_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
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
    "source_business_type_title": ("source_business_type_title", "sourceBusinessTypeTitle"),
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

_CONTRACT_KEYS = (
    "benchmark_contract",
    "benchmarkContract",
    "benchmark_provenance",
    "benchmarkProvenance",
)


def as_mapping(value: object) -> JsonMap:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
            return dumped if isinstance(dumped, dict) else {}
        except Exception:
            return {}
    if hasattr(value, "dict"):
        try:
            dumped = value.dict()
            return dumped if isinstance(dumped, dict) else {}
        except Exception:
            return {}
    return {}


def _get_any(mapping: JsonMap, *fields: str) -> object:
    for field in fields:
        for key in _FIELD_ALIASES.get(field, (field,)):
            if key in mapping:
                return mapping.get(key)
    return None


def _has_any_key(mapping: JsonMap, field: str) -> bool:
    return any(key in mapping for key in _FIELD_ALIASES.get(field, (field,)))


def _has_benchmark_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _scope_stage_for_contract(contract: JsonMap) -> str:
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


def _normalize_metric_provenance(metric_name: str, raw_metric: object) -> JsonMap:
    metric = as_mapping(raw_metric)
    return {
        "metric_name": _get_any(metric, "metric_name") or metric_name,
        "benchmark_id": _get_any(metric, "benchmark_id"),
        "business_type_id": _get_any(metric, "business_type_id", "businessTypeId"),
        "country_code": _get_any(metric, "country_code"),
        "median": _get_any(metric, "median"),
        "p10": _get_any(metric, "p10"),
        "p25": _get_any(metric, "p25"),
        "p75": _get_any(metric, "p75"),
        "p90": _get_any(metric, "p90"),
        "dataset_version_id": _get_any(metric, "dataset_version_id"),
        "region_key": _get_any(metric, "region_key"),
        "sample_size": _get_any(metric, "sample_size"),
        "confidence_band": _get_any(metric, "confidence_band"),
        "confidence_score": _get_any(metric, "confidence_score"),
        "data_source": _get_any(metric, "data_source"),
        "source_mix": _get_any(metric, "source_mix"),
        "evidence_summary": _get_any(metric, "evidence_summary"),
        "published_at": _get_any(metric, "published_at"),
        "methodology_version": _get_any(metric, "methodology_version"),
        "benchmark_scope": _get_any(metric, "benchmark_scope"),
        "benchmark_kind": _get_any(metric, "benchmark_kind"),
        "tier": _get_any(metric, "tier"),
        "is_borrowed": _get_any(metric, "is_borrowed"),
        "walk_step": _get_any(metric, "walk_step"),
        "walk_proximity": _get_any(metric, "walk_proximity"),
        "source_business_type_id": _get_any(metric, "source_business_type_id"),
        "source_business_type_title": _get_any(metric, "source_business_type_title"),
        "source_primary_nace_code": _get_any(metric, "source_primary_nace_code"),
        "borrowed_from_country": _get_any(metric, "borrowed_from_country"),
        "scope_stage": _get_any(metric, "scope_stage"),
        "release_policy": _get_any(metric, "release_policy"),
        "standalone_conclusion_eligible": _get_any(metric, "standalone_conclusion_eligible"),
        "release_blockers": _get_any(metric, "release_blockers"),
    }


def normalize_benchmark_contract(raw_contract: object) -> JsonMap:
    contract = as_mapping(raw_contract)
    metrics_raw = as_mapping(_get_any(contract, "metrics"))
    normalized_metrics = {
        name: _normalize_metric_provenance(name, metric)
        for name, metric in metrics_raw.items()
        if isinstance(metric, dict)
    }
    primary_metric = _get_any(contract, "primary_metric")
    primary_metric_data = normalized_metrics.get(str(primary_metric or ""))
    if primary_metric_data is None and normalized_metrics:
        primary_metric_data = next(iter(normalized_metrics.values()))

    def from_contract_or_metric(field: str) -> object:
        value = _get_any(contract, field)
        if value is not None:
            return value
        if primary_metric_data:
            return _get_any(primary_metric_data, field)
        return None

    normalized = {
        "schema_version": _get_any(contract, "schema_version"),
        "status": _get_any(contract, "status"),
        "source": _get_any(contract, "source"),
        "business_type_id": _get_any(contract, "business_type_id"),
        "primary_nace_code": _get_any(contract, "primary_nace_code"),
        "geography": _get_any(contract, "geography"),
        "company_size_band": _get_any(contract, "company_size_band"),
        "release_policy": from_contract_or_metric("release_policy"),
        "standalone_conclusion_eligible": from_contract_or_metric("standalone_conclusion_eligible"),
        "release_blockers": from_contract_or_metric("release_blockers") or [],
        "primary_metric": primary_metric,
        "benchmark_id": from_contract_or_metric("benchmark_id"),
        "dataset_version_id": from_contract_or_metric("dataset_version_id"),
        "country_code": from_contract_or_metric("country_code"),
        "region_key": from_contract_or_metric("region_key"),
        "tier": from_contract_or_metric("tier"),
        "walk_step": from_contract_or_metric("walk_step"),
        "walk_proximity": from_contract_or_metric("walk_proximity"),
        "sample_size": from_contract_or_metric("sample_size"),
        "confidence_band": from_contract_or_metric("confidence_band"),
        "confidence_score": from_contract_or_metric("confidence_score"),
        "data_source": from_contract_or_metric("data_source"),
        "source_mix": from_contract_or_metric("source_mix"),
        "evidence_summary": from_contract_or_metric("evidence_summary"),
        "published_at": from_contract_or_metric("published_at"),
        "methodology_version": from_contract_or_metric("methodology_version"),
        "benchmark_scope": from_contract_or_metric("benchmark_scope"),
        "benchmark_kind": from_contract_or_metric("benchmark_kind"),
        "is_borrowed": from_contract_or_metric("is_borrowed"),
        "source_business_type_id": from_contract_or_metric("source_business_type_id"),
        "source_business_type_title": from_contract_or_metric("source_business_type_title"),
        "source_primary_nace_code": from_contract_or_metric("source_primary_nace_code"),
        "borrowed_from_country": from_contract_or_metric("borrowed_from_country"),
        "scope_stage": from_contract_or_metric("scope_stage"),
        # BET-628 — the sector-multiple trend (contract-level; value-up market-context's
        # sector_cycle reads it). Preserved through normalization so it isn't whitelisted out.
        "multiple_trend": _get_any(contract, "multiple_trend"),
        "metrics": normalized_metrics,
    }
    if not normalized.get("scope_stage"):
        normalized["scope_stage"] = _scope_stage_for_contract(normalized)
    return normalized


def _primary_raw_metric(contract: JsonMap) -> JsonMap:
    metrics_raw = as_mapping(_get_any(contract, "metrics"))
    primary_metric = _get_any(contract, "primary_metric")
    if primary_metric and isinstance(metrics_raw.get(str(primary_metric)), dict):
        return metrics_raw[str(primary_metric)]
    for metric in metrics_raw.values():
        if isinstance(metric, dict):
            return metric
    return {}


def _field_present_on_contract_or_primary_metric(contract: JsonMap, field: str) -> bool:
    if _has_any_key(contract, field):
        return True
    primary_metric = _primary_raw_metric(contract)
    return _has_any_key(primary_metric, field)


def _is_positive_sample_size(value: object) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, str) and not re.fullmatch(
        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value.strip()
    ):
        return False
    try:
        sample = Decimal(str(value))
        return (
            sample.is_finite()
            and 0 < sample <= 9007199254740991
            and sample == sample.to_integral_value()
        )
    except (InvalidOperation, ValueError, TypeError):
        return False


def _truthy_flag(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


def _is_synthetic_seed_contract(normalized: JsonMap) -> bool:
    data_source = str(normalized.get("data_source") or "").upper()
    methodology_version = str(normalized.get("methodology_version") or "").lower()
    if data_source == "BENCH_SEED_V1" or methodology_version == "bench_seed_v1":
        return True

    evidence_summary = as_mapping(normalized.get("evidence_summary"))
    seed = as_mapping(evidence_summary.get("seed"))
    if _truthy_flag(seed.get("is_fallback")):
        return True

    source_mix = as_mapping(normalized.get("source_mix"))
    return "BENCH_SEED_V1" in {str(key).upper() for key in source_mix.keys()}


def missing_required_benchmark_provenance(raw_contract: object) -> list[str]:
    contract = as_mapping(raw_contract)
    if not contract:
        return ["benchmark_contract"]
    normalized = normalize_benchmark_contract(contract)
    missing = [
        field
        for field in _REQUIRED_NON_EMPTY_FIELDS
        if not _has_benchmark_value(normalized.get(field))
    ]
    # `source_mix` is presence-only (see _PRESENCE_ONLY_FIELDS): an empty `{}` is
    # the legitimate catalog-backfill / aggregate shape and must NOT fail the
    # gate. Only a missing or non-dict (e.g. None) source mix is a real contract
    # violation — mirrors Titan's `hasRequiredBenchmarkPresence`.
    if not isinstance(normalized.get("source_mix"), dict):
        missing.append("source_mix")
    if not _is_positive_sample_size(normalized.get("sample_size")) and "sample_size" not in missing:
        missing.append("sample_size")
    if not _field_present_on_contract_or_primary_metric(contract, "walk_step"):
        missing.append("walk_step")
    if _is_synthetic_seed_contract(normalized):
        missing.append("defensible_local_or_borrowed_evidence")
    return missing


def is_resolved_benchmark_contract(raw_contract: object) -> bool:
    contract = as_mapping(raw_contract)
    return _get_any(contract, "status") == "resolved" and not missing_required_benchmark_provenance(
        contract
    )


def is_country_baseline_benchmark_contract(raw_contract: object) -> bool:
    contract = as_mapping(raw_contract)
    if not contract:
        return False
    normalized = normalize_benchmark_contract(contract)
    marker_values = {
        str(normalized.get("source") or "").strip().lower(),
        str(normalized.get("data_source") or "").strip().lower(),
        str(normalized.get("benchmark_scope") or "").strip().lower(),
        str(normalized.get("benchmark_kind") or "").strip().lower(),
    }
    return any("country_baseline" in marker for marker in marker_values)


def benchmark_contract_data_source(raw_contract: object) -> str:
    if is_country_baseline_benchmark_contract(raw_contract):
        return "country_baseline_benchmark_contract"
    return "delphi_benchmark_contract"


def benchmark_contract_source_key(raw_contract: object) -> str:
    if is_country_baseline_benchmark_contract(raw_contract):
        return "COUNTRY_BASELINE_BENCHMARK_CONTRACT"
    return "DELPHI_BENCHMARK_CONTRACT"


def _iter_contract_candidates(container: object) -> Iterable[object]:
    mapping = as_mapping(container)
    if not mapping:
        return ()
    return tuple(mapping.get(key) for key in _CONTRACT_KEYS if key in mapping)


def extract_resolved_benchmark_contract(container: object) -> JsonMap | None:
    mapping = as_mapping(container)
    if not mapping:
        return None
    candidates = list(_iter_contract_candidates(mapping))
    details = as_mapping(mapping.get("data_source_details") or mapping.get("dataSourceDetails"))
    candidates.extend(_iter_contract_candidates(details))
    for candidate in candidates:
        if is_resolved_benchmark_contract(candidate):
            return normalize_benchmark_contract(candidate)
    return None


def _request_contract_candidates(request: object) -> list[object]:
    """Every place a caller may attach a benchmark contract to a request,
    in priority order. Shared by the extractor and the diagnoser so they can
    never disagree about where to look."""
    candidates: list[object] = [
        getattr(request, "benchmark_contract", None),
        getattr(request, "benchmarkContract", None),
    ]
    for attr_name in ("multiples_metadata", "metadata", "business_context"):
        container = as_mapping(getattr(request, attr_name, None))
        if container:
            candidates.extend(_iter_contract_candidates(container))
    return candidates


def extract_request_resolved_benchmark_contract(request: object) -> JsonMap | None:
    for candidate in _request_contract_candidates(request):
        if is_resolved_benchmark_contract(candidate):
            return normalize_benchmark_contract(candidate)
    return None


def derive_data_tier_v1(request: object) -> tuple[str, str]:
    """BET-434/435 (v1 lane) — the valuation-accuracy tier this result rests on,
    derived from the TRUST of the inputs the engine actually used. Mirrors the v2
    stateless ``derive_data_tier`` exactly, expressed through THIS module's helpers so
    the two lanes can never disagree (and so the tier can never contradict the
    ``data_sources.multiples.source`` key v1 already publishes from the same signal):

      - ``defensible`` — a RESOLVED Upswitch Index benchmark contract backs the
        multiples (company-specific, published evidence), so the number is grounded
        in real data rather than a market proxy.
      - ``indicative`` — a country-baseline / fallback benchmark, or no resolved
        contract at all: a discussion RANGE, never a false-precision point.

    VIQ never claims ``attested`` from data alone — that tier is owned by the legal /
    Attest layer (titan ``deal_ready``). Reads only benchmark-contract provenance;
    never the computed value or confidence, so the tier label is value-free.
    """
    contract = extract_request_resolved_benchmark_contract(request)
    if contract is not None and not is_country_baseline_benchmark_contract(contract):
        return ("defensible", "Grounded in a resolved Upswitch Index benchmark contract.")
    return (
        "indicative",
        "Registry-proxy or fallback benchmark — a discussion range, not a binding valuation.",
    )


def diagnose_request_benchmark_contract(request: object) -> dict[str, object]:
    """Explain *why* a request has no resolved benchmark contract.

    Returns the most-complete candidate's status plus the exact provenance
    fields it is missing, so the BENCHMARK_CONTRACT_REQUIRED envelope is
    self-diagnosing (e.g. ``missing_required_fields=['source_mix']``) instead
    of a bare "contract required". This is what lets the next incident be read
    straight off the error/log instead of reverse-engineered. Read-only and
    exception-safe — diagnostics must never themselves break the raise path.
    """
    best_status: object = None
    best_missing: list[str] | None = None
    for candidate in _request_contract_candidates(request):
        mapping = as_mapping(candidate)
        if not mapping:
            continue
        try:
            missing = missing_required_benchmark_provenance(mapping)
        except Exception:  # noqa: BLE001 — diagnostics must never raise
            continue
        # Prefer the candidate closest to resolved (fewest missing fields).
        if best_missing is None or len(missing) < len(best_missing):
            best_missing = missing
            best_status = _get_any(mapping, "status")
    if best_missing is None:
        return {
            "benchmark_contract_present": False,
            "missing_required_fields": ["benchmark_contract"],
        }
    return {
        "benchmark_contract_present": True,
        "benchmark_contract_status": best_status,
        "missing_required_fields": best_missing,
    }


def request_allows_untrusted_multiples_fallback(request: object) -> bool:
    if getattr(request, "allow_untrusted_multiples_fallback", False) is True:
        return True
    for attr_name in ("metadata", "business_context"):
        container = as_mapping(getattr(request, attr_name, None))
        if container.get("allow_untrusted_multiples_fallback") is True:
            return True
    return False
