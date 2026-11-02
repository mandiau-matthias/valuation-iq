"""Benchmark publication policy for stateless valuation responses."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Dict, Optional, TypeAlias

from src.api.routes.valuation.benchmark_contract_utils import (
    missing_required_benchmark_provenance as missing_canonical_benchmark_provenance,
)
from src.api.schemas.stateless_api import CalculateRequest

_BENCHMARK_PROVENANCE_OUTPUT_FIELDS = (
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

_CALIBRATION_MULTIPLE_METRICS = {
    "ev_ebitda_median": ("ev_ebitda", "ev_ebitda_multiple", "ebitda_multiple"),
    "ev_revenue_median": ("ev_revenue", "ev_revenue_multiple", "revenue_multiple"),
}

_METHOD_BENCHMARK_METRICS = {
    "upswitch_adaptive": ("ev_ebitda", "ev_ebitda_multiple", "ebitda_multiple"),
    "ebitda_multiple": ("ev_ebitda", "ev_ebitda_multiple", "ebitda_multiple"),
    "omzet_multiple": ("ev_revenue", "ev_revenue_multiple", "revenue_multiple"),
    "sde_multiple": ("sde_multiple", "sde"),
    "arr_multiple": ("arr_multiple", "arr"),
}

_CALIBRATION_ATTRIBUTE_BY_METHOD = {
    "upswitch_adaptive": "ev_ebitda_median",
    "ebitda_multiple": "ev_ebitda_median",
    "omzet_multiple": "ev_revenue_median",
}

_RESOLUTION_CONTRACT_VERSION = "benchmark_resolution.v1"
_RESOLUTION_INTEGRITY_VERSION = "benchmark_resolution_integrity.v1"
_RESOLUTION_ID = re.compile(r"^brv1_[0-9a-f]{32}$")
_RESOLUTION_CONTEXT_ID = re.compile(r"^bctx_[0-9a-f]{24}$")
_METRIC_RESOLUTION_ID = re.compile(r"^bres_[0-9a-f]{24}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_AUTHORIZED_REVIEW_STATES = {
    "published_approved",
    "approved_manual_expert_selection",
}

JsonMap: TypeAlias = Dict[str, object]


def as_mapping(value: object) -> Optional[JsonMap]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else None
    return None


def has_benchmark_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def truthy_flag(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def request_allows_untrusted_multiples_fallback(request: CalculateRequest) -> bool:
    from .value_basis_admission import uses_accounting_basis_policy
    if uses_accounting_basis_policy(request):
        return False
    if truthy_flag(getattr(request, "allow_untrusted_multiples_fallback", False)):
        return True
    for container_name in ("metadata", "business_context"):
        container = as_mapping(getattr(request, container_name, None))
        if container and truthy_flag(container.get("allow_untrusted_multiples_fallback")):
            return True
    return False


def extract_stateless_benchmark_contract(
    request: CalculateRequest,
) -> Optional[JsonMap]:
    calibration = getattr(request, "business_type_calibration", None)
    candidates = [
        getattr(request, "benchmark_contract", None),
        getattr(calibration, "benchmark_contract", None),
    ]
    for container_name in ("multiples_metadata", "metadata", "business_context"):
        container = as_mapping(getattr(request, container_name, None))
        if container:
            candidates.append(container.get("benchmark_contract"))

    for candidate in candidates:
        mapping = as_mapping(candidate)
        if mapping:
            return mapping
    return None


def missing_required_benchmark_provenance(contract: Optional[JsonMap]) -> list[str]:
    """Delegate provenance validity to the cross-endpoint canonical contract.

    `source_mix={}` is a legitimate single-source/catalog-backfill shape.  This
    wrapper intentionally remains for report-layer callers, but it may not
    define a second interpretation of benchmark provenance.
    """

    if _is_resolution_contract(contract):
        return _missing_resolution_contract_provenance(contract or {})
    return missing_canonical_benchmark_provenance(contract)


def benchmark_contract_is_resolved(contract: Optional[JsonMap]) -> bool:
    if not contract:
        return False
    if _is_resolution_contract(contract):
        return not _missing_resolution_contract_provenance(contract) and any(
            _resolution_authorizes_metric(row) for row in _resolution_rows(contract)
        )
    status_value = contract.get("status")
    return status_value is None or str(status_value).strip().lower() == "resolved"


def benchmark_contract_is_country_baseline(contract: Optional[JsonMap]) -> bool:
    if not contract:
        return False
    source = str(contract.get("source") or "").strip().lower()
    benchmark_kind = str(contract.get("benchmark_kind") or "").strip().lower()
    benchmark_scope = str(contract.get("benchmark_scope") or "").strip().lower()
    return "country_baseline" in {source, benchmark_kind, benchmark_scope}


def benchmark_contract_multiples_source(contract: Optional[JsonMap]) -> str:
    if benchmark_contract_is_country_baseline(contract):
        return "COUNTRY_BASELINE_BENCHMARK_CONTRACT"
    return "DELPHI_BENCHMARK_CONTRACT"


def benchmark_contract_is_delphi_sourced(contract: Optional[JsonMap]) -> bool:
    return not benchmark_contract_is_country_baseline(contract)


def benchmark_contract_fallback_reason(contract: Optional[JsonMap]) -> Optional[str]:
    if not benchmark_contract_is_country_baseline(contract):
        return None
    evidence_summary = as_mapping((contract or {}).get("evidence_summary"))
    reason = evidence_summary.get("fallback_reason") if evidence_summary else None
    return str(reason or "country_baseline").strip() or "country_baseline"


def benchmark_metric_names(contract: Optional[JsonMap]) -> set[str]:
    if not contract:
        return set()
    names: set[str] = set()
    if _is_resolution_contract(contract):
        for row in _resolution_rows(contract):
            if not _resolution_authorizes_metric(row):
                continue
            metric_name = _resolution_metric_name(row)
            if metric_name:
                names.add(metric_name)
        return names
    metrics = as_mapping(contract.get("metrics"))
    if metrics:
        for metric_name, metric_payload in metrics.items():
            metric = as_mapping(metric_payload)
            if metric_payload is not None and (metric is None or metric.get("benchmark_id")):
                names.add(str(metric_name).strip().lower())
    primary_metric = contract.get("primary_metric") or contract.get("primaryMetric")
    if isinstance(primary_metric, str) and primary_metric.strip():
        names.add(primary_metric.strip().lower())
    return names


def benchmark_metric_available(
    contract: Optional[JsonMap],
    metric_aliases: tuple[str, ...],
) -> bool:
    names = benchmark_metric_names(contract)
    aliases = {alias.strip().lower() for alias in metric_aliases}
    return bool(names & aliases)


def positive_decimal_attr(obj: object, attr: str) -> bool:
    try:
        value = getattr(obj, attr, None)
        return value is not None and Decimal(str(value)) > 0
    except Exception:
        return False


def has_positive_calibration_multiple(calibration: object) -> bool:
    return any(positive_decimal_attr(calibration, attr) for attr in _CALIBRATION_MULTIPLE_METRICS)


def missing_benchmark_metrics_for_calibration(
    calibration: object,
    contract: Optional[JsonMap],
    *,
    request: CalculateRequest | None = None,
) -> list[str]:
    required_methods = _required_benchmark_method_keys(request)
    missing: list[str] = []
    for method_key in required_methods:
        metric_aliases = _METHOD_BENCHMARK_METRICS[method_key]
        calibration_attr = _CALIBRATION_ATTRIBUTE_BY_METHOD.get(method_key)
        if calibration_attr is not None and not positive_decimal_attr(
            calibration, calibration_attr
        ):
            continue
        if not benchmark_metric_available(contract, metric_aliases):
            missing.append(metric_aliases[0])
    return missing


def _required_benchmark_method_keys(
    request: CalculateRequest | None,
) -> set[str]:
    if request is None:
        return {"ebitda_multiple", "omzet_multiple"}
    if not getattr(request, "include_multiples", True):
        return set()

    user_weights = getattr(request, "user_weights", None) or {}
    if user_weights:
        required = {
            str(key)
            for key, weight in user_weights.items()
            if _safe_positive_weight(weight) and str(key) in _METHOD_BENCHMARK_METRICS
        }
        if _safe_positive_weight(user_weights.get("upswitch_adaptive")):
            required.discard("upswitch_adaptive")
            required.update(_adaptive_component_method_keys(request))
        return required

    selected = str(getattr(request, "selected_method", None) or "").strip().lower()
    if selected:
        if selected == "upswitch_adaptive":
            return _adaptive_component_method_keys(request)
        if selected in _METHOD_BENCHMARK_METRICS:
            return {selected}
        return set()

    required: set[str] = set()
    weights = getattr(request, "multiple_type_weights", None) or {}
    for raw_key, raw_weight in weights.items():
        if not _safe_positive_weight(raw_weight):
            continue
        key = str(raw_key).strip().lower()
        if key in {"ev_revenue", "revenue", "revenue_multiple", "omzet"}:
            required.add("omzet_multiple")
        elif key in {"ev_ebitda", "ebitda", "ebitda_multiple"}:
            required.add("ebitda_multiple")

    return required or {"ebitda_multiple"}


def _adaptive_component_method_keys(request: CalculateRequest) -> set[str]:
    """Return the metric methods that can enter the adaptive market leg.

    Adaptive defaults to an EBITDA multiple, but explicit multiple-type
    weights can make revenue enter the price. Treating adaptive as a fixed
    EBITDA alias would allow a revenue-weighted price without an authorized
    revenue resolution.
    """

    weights = getattr(request, "multiple_type_weights", None) or {}
    if not weights:
        return {"ebitda_multiple"}

    required: set[str] = set()
    for raw_key, raw_weight in weights.items():
        if not _safe_positive_weight(raw_weight):
            continue
        key = str(raw_key).strip().lower()
        if key in {"ev_revenue", "revenue", "revenue_multiple", "omzet"}:
            required.add("omzet_multiple")
        elif key in {"ev_ebitda", "ebitda", "ebitda_multiple"}:
            required.add("ebitda_multiple")
    return required or {"ebitda_multiple"}


def _required_calibration_multiple_attributes(
    request: CalculateRequest | None,
) -> set[str]:
    """Return only calibration metrics that can enter this request's price.

    Calibration envelopes may contain informative revenue and EBITDA scalars.
    Their mere presence must not activate a method or make an otherwise valid
    EBITDA valuation fail because an unused revenue benchmark is absent.
    """
    if request is None:
        return set(_CALIBRATION_MULTIPLE_METRICS)

    return {
        calibration_attr
        for method_key in _required_benchmark_method_keys(request)
        if (calibration_attr := _CALIBRATION_ATTRIBUTE_BY_METHOD.get(method_key)) is not None
    }


def _safe_positive_weight(value: object) -> bool:
    try:
        return value is not None and Decimal(str(value)) > 0
    except Exception:
        return False


def stateless_requires_benchmark_contract(
    request: CalculateRequest,
    *,
    calibration: object,
    asset_primary_payload: Optional[JsonMap],
) -> bool:
    if not getattr(calibration, "business_type_id", None):
        return False
    if not getattr(request, "include_multiples", True):
        return False
    if asset_primary_payload and asset_primary_payload.get("available"):
        return False
    required_methods = _required_benchmark_method_keys(request)
    if not required_methods:
        return False
    if required_methods & {"sde_multiple", "arr_multiple"}:
        return True
    return any(
        positive_decimal_attr(calibration, calibration_attr)
        for method_key in required_methods
        if (calibration_attr := _CALIBRATION_ATTRIBUTE_BY_METHOD.get(method_key)) is not None
    )


def flatten_benchmark_provenance(
    contract: Optional[JsonMap],
) -> Optional[JsonMap]:
    if not contract:
        return None
    if _is_resolution_contract(contract):
        rows = _resolution_rows(contract)
        resolved = next((row for row in rows if _resolution_authorizes_metric(row)), {})
        dataset = as_mapping(contract.get("dataset_snapshot")) or {}
        confidence = resolved.get("confidence")
        confidence_mapping = as_mapping(confidence)
        return {
            "contract_version": contract.get("contract_version"),
            "resolution_id": contract.get("resolution_id"),
            "resolution_fingerprint_sha256": contract.get("resolution_fingerprint_sha256"),
            "dataset_snapshot": dataset,
            "resolutions": rows,
            "benchmark_id": resolved.get("source_benchmark_id"),
            "dataset_version_id": dataset.get("id") or dataset.get("version_number"),
            "sample_size": resolved.get("sample_size"),
            "confidence_band": (
                confidence_mapping.get("band") if confidence_mapping else confidence
            ),
            "evidence_summary": {"citations": resolved.get("citations") or []},
            "published_at": resolved.get("published_at") or dataset.get("published_at"),
            "methodology_version": resolved.get("methodology_version"),
            "scope_stage": resolved.get("resolution_level"),
            "benchmark_scope_stage": resolved.get("resolution_level"),
        }
    provenance = {
        key: contract.get(key) for key in _BENCHMARK_PROVENANCE_OUTPUT_FIELDS if key in contract
    }
    provenance["benchmark_scope_stage"] = contract.get("scope_stage")
    return provenance


def _is_resolution_contract(contract: Optional[JsonMap]) -> bool:
    return bool(
        contract
        and (
            contract.get("contract_version") == _RESOLUTION_CONTRACT_VERSION
            or contract.get("schema_version") == _RESOLUTION_CONTRACT_VERSION
        )
    )


def _resolution_rows(contract: JsonMap) -> list[JsonMap]:
    raw_rows = contract.get("resolutions") or contract.get("metric_outcomes")
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes, bytearray)):
        return []
    return [dict(row) for row in raw_rows if isinstance(row, Mapping)]


def _resolution_metric_name(row: JsonMap) -> str:
    raw = str(row.get("metric_name") or row.get("metric") or "").strip().lower()
    return {
        "ev/ebitda": "ev_ebitda",
        "ev_ebitda_multiple": "ev_ebitda",
        "ev/revenue": "ev_revenue",
        "ev_revenue_multiple": "ev_revenue",
    }.get(raw, raw)


def _resolution_authorizes_metric(row: JsonMap) -> bool:
    outcome = str(row.get("outcome") or "").strip().lower()
    review_state = str(row.get("review_state") or "").strip().lower()
    confidence = as_mapping(row.get("confidence"))
    citations = row.get("citations")
    try:
        median_is_positive = Decimal(str(row.get("median"))) > 0
        sample_is_positive = int(row.get("sample_size") or 0) > 0
        confidence_score = Decimal(str((confidence or {}).get("score")))
        confidence_is_publishable = confidence_score >= Decimal("0.55")
    except (ArithmeticError, TypeError, ValueError):
        return False
    citations_are_complete = bool(
        isinstance(citations, Sequence)
        and not isinstance(citations, (str, bytes, bytearray))
        and citations
        and all(
            isinstance(citation, Mapping)
            and has_benchmark_value(citation.get("citation_id"))
            and has_benchmark_value(citation.get("source_kind"))
            and has_benchmark_value(citation.get("url"))
            for citation in citations
        )
    )
    return bool(
        _resolution_metric_name(row)
        and outcome == "resolved"
        and row.get("publication_eligible") is True
        and review_state in _AUTHORIZED_REVIEW_STATES
        and row.get("source_benchmark_id")
        and row.get("resolution_level")
        and row.get("dataset_version_id")
        and row.get("source_dataset_version_id")
        and row.get("target_business_type_id")
        and row.get("target_country_code")
        and row.get("published_at")
        and row.get("methodology_version")
        and isinstance(row.get("evidence_window"), Mapping)
        and isinstance(row.get("adjustments"), list)
        and _METRIC_RESOLUTION_ID.fullmatch(str(row.get("resolution_id") or ""))
        and _SHA256.fullmatch(str(row.get("resolution_hash") or ""))
        and median_is_positive
        and sample_is_positive
        and confidence_is_publishable
        and has_benchmark_value((confidence or {}).get("band"))
        and citations_are_complete
    )


def _missing_resolution_contract_provenance(contract: JsonMap) -> list[str]:
    missing: list[str] = []
    if contract.get("schema_version") != _RESOLUTION_CONTRACT_VERSION:
        missing.append("schema_version")
    if contract.get("contract_version") != _RESOLUTION_CONTRACT_VERSION:
        missing.append("contract_version")
    if contract.get("integrity_version") != _RESOLUTION_INTEGRITY_VERSION:
        missing.append("integrity_version")
    resolution_id = str(contract.get("resolution_id") or "")
    fingerprint = str(contract.get("resolution_fingerprint_sha256") or "")
    if not _RESOLUTION_ID.fullmatch(resolution_id):
        missing.append("resolution_id")
    if not _SHA256.fullmatch(fingerprint):
        missing.append("resolution_fingerprint_sha256")
    elif resolution_id and resolution_id != f"brv1_{fingerprint[:32]}":
        missing.append("resolution_id_hash_binding")
    context_hash = str(contract.get("resolution_context_hash") or "")
    context_id = str(contract.get("resolution_context_id") or "")
    if context_hash != fingerprint:
        missing.append("resolution_context_hash_alias")
    if not _RESOLUTION_CONTEXT_ID.fullmatch(context_id) or (
        fingerprint and context_id != f"bctx_{fingerprint[:24]}"
    ):
        missing.append("resolution_context_id_hash_binding")

    commitment = as_mapping(contract.get("resolution_commitment"))
    if not commitment:
        missing.append("resolution_commitment")
    else:
        if _resolution_contract_hash(commitment) != fingerprint:
            missing.append("resolution_commitment_hash_binding")
        expected_commitment = _resolution_commitment_projection(contract)
        if commitment != expected_commitment:
            missing.append("resolution_commitment_alias_binding")

    dataset = as_mapping(contract.get("dataset_snapshot"))
    if not dataset:
        missing.append("dataset_snapshot")
    else:
        for field in ("id", "version_number", "published_at", "requested_as_of"):
            if not has_benchmark_value(dataset.get(field)):
                missing.append(f"dataset_snapshot.{field}")
        if dataset.get("id") != contract.get("dataset_version_id"):
            missing.append("dataset_snapshot.id_alias_binding")
        if dataset.get("published_at") != contract.get("dataset_published_at"):
            missing.append("dataset_snapshot.published_at_alias_binding")
        if dataset.get("requested_as_of") != contract.get("as_of"):
            missing.append("dataset_snapshot.requested_as_of_alias_binding")

    rows = _resolution_rows(contract)
    raw_resolutions = contract.get("resolutions")
    raw_outcomes = contract.get("metric_outcomes")
    if raw_resolutions != raw_outcomes:
        missing.append("resolutions_metric_outcomes_alias_binding")
    if not rows:
        missing.append("resolutions")
    for index, row in enumerate(rows):
        prefix = f"resolutions[{index}]"
        expected_metric_hash = _metric_resolution_hash(contract, row)
        declared_metric_hash = str(row.get("resolution_hash") or "")
        declared_metric_id = str(row.get("resolution_id") or "")
        if not _SHA256.fullmatch(declared_metric_hash) or (
            declared_metric_hash != expected_metric_hash
        ):
            missing.append(f"{prefix}.resolution_hash_binding")
        if not _METRIC_RESOLUTION_ID.fullmatch(declared_metric_id) or (
            declared_metric_id != f"bres_{expected_metric_hash[:24]}"
        ):
            missing.append(f"{prefix}.resolution_id_hash_binding")
        if row.get("target_business_type_id") != contract.get("business_type_id"):
            missing.append(f"{prefix}.target_business_type_id_alias_binding")
        if row.get("target_country_code") != contract.get("country_code"):
            missing.append(f"{prefix}.target_country_code_alias_binding")
        if row.get("dataset_version_id") != contract.get("dataset_version_id"):
            missing.append(f"{prefix}.dataset_version_id_alias_binding")
        if row.get("metric") != row.get("metric_name"):
            missing.append(f"{prefix}.metric_name_alias_binding")
        if str(row.get("outcome") or "").lower() == "resolved":
            for field in (
                "resolution_level",
                "source_benchmark_id",
                "median",
                "sample_size",
                "evidence_window",
                "confidence",
                "review_state",
                "publication_eligible",
                "published_at",
                "methodology_version",
                "citations",
                "source_dataset_version_id",
            ):
                value = row.get(field)
                if field == "publication_eligible":
                    present = isinstance(value, bool)
                elif field == "adjustments":
                    present = isinstance(value, list)
                else:
                    present = has_benchmark_value(value)
                if not present:
                    missing.append(f"{prefix}.{field}")
            if not isinstance(row.get("adjustments"), list):
                missing.append(f"{prefix}.adjustments")
    return list(dict.fromkeys(missing))


def _resolution_commitment_projection(contract: JsonMap) -> JsonMap:
    return {
        "schema_version": contract.get("schema_version"),
        "business_type_id": contract.get("business_type_id"),
        "country_code": contract.get("country_code"),
        "size_band": contract.get("size_band"),
        "dataset_version_id": contract.get("dataset_version_id"),
        "dataset_published_at": contract.get("dataset_published_at"),
        "as_of": contract.get("as_of"),
        "overall_outcome": contract.get("overall_outcome"),
        "publication_eligible": contract.get("publication_eligible"),
        "metric_outcomes": contract.get("metric_outcomes"),
    }


def _metric_resolution_hash(contract: JsonMap, row: JsonMap) -> str:
    metric_outcome = dict(row)
    metric_outcome.pop("resolution_id", None)
    metric_outcome.pop("resolution_hash", None)
    return _resolution_contract_hash(
        {
            "schema_version": contract.get("schema_version"),
            "target_business_type_id": contract.get("business_type_id"),
            "target_country_code": contract.get("country_code"),
            "dataset_version_id": contract.get("dataset_version_id"),
            "as_of": contract.get("as_of"),
            "metric_outcome": metric_outcome,
        }
    )


def _resolution_contract_hash(value: object) -> str:
    from src.services.reports.stateless_valuation_run import canonical_hash

    return canonical_hash(value)


def fallback_benchmark_provenance() -> JsonMap:
    return {
        "multiples_source": "DISCLOSED_EXTERNAL_MARKET_FALLBACK",
        "is_delphi_benchmark_sourced": False,
        "fallback_used": True,
        "fallback_reason": "explicit_untrusted_multiples_fallback",
        "benchmark_contract": None,
    }


def governed_external_market_provenance(request: CalculateRequest) -> JsonMap | None:
    contract = getattr(request, "external_market_reference_contract", None)
    if contract is None:
        return None
    payload = contract.model_dump(mode="json") if hasattr(contract, "model_dump") else contract
    return {
        "multiples_source": "GOVERNED_EXTERNAL_MARKET_REFERENCE",
        "is_delphi_benchmark_sourced": False,
        "fallback_used": False,
        "fallback_reason": None,
        "benchmark_contract": None,
        "external_market_reference_contract": payload,
        "empirical_percentiles_available": False,
        "sample_size": None,
    }


def _preserve_external_reference_range_semantics(
    details: JsonMap,
    request: CalculateRequest | None,
) -> None:
    """Keep an advisor-defined range out of empirical-percentile fields.

    The generic EBITDA method predates disclosed external references and stores
    its valuation band under ``p25_multiple`` / ``p75_multiple``.  Those field
    names are materially misleading when the range is an explicitly disclosed
    advisor reference rather than an observed percentile distribution.  Retain
    the numerical range under names that state its provenance, so API consumers
    cannot accidentally label it an Index percentile band.
    """

    if request is None:
        return
    reference = getattr(request, "external_market_reference_contract", None) or getattr(
        request, "disclosed_external_market_reference", None
    )
    if reference is None:
        return

    details.pop("p25_multiple", None)
    details.pop("p75_multiple", None)
    details.update(
        {
            "external_reference_range_low_multiple": float(reference.range_low_multiple),
            "external_reference_range_high_multiple": float(reference.range_high_multiple),
            "range_basis": "advisor_defined_external_reference_not_empirical",
        }
    )


def resolve_multiples_source_policy(
    *,
    benchmark_contract_resolved: bool,
    benchmark_contract: Optional[JsonMap],
    allow_untrusted_multiples_fallback: bool,
    governed_external_market_reference: bool = False,
) -> tuple[str, bool, bool, Optional[str]]:
    """Resolve the response-level multiples source and fallback disclosure flags."""
    if benchmark_contract_resolved:
        return (
            benchmark_contract_multiples_source(benchmark_contract),
            benchmark_contract_is_delphi_sourced(benchmark_contract),
            benchmark_contract_is_country_baseline(benchmark_contract),
            benchmark_contract_fallback_reason(benchmark_contract),
        )
    if governed_external_market_reference:
        return ("GOVERNED_EXTERNAL_MARKET_REFERENCE", False, False, None)
    if allow_untrusted_multiples_fallback:
        return (
            "DISCLOSED_EXTERNAL_MARKET_FALLBACK",
            False,
            True,
            "explicit_untrusted_multiples_fallback",
        )
    return ("not_applicable", False, False, None)


def mark_method_unavailable_for_benchmark(result: object, *, reason: str) -> None:
    setattr(result, "available", False)
    setattr(result, "value", None)
    setattr(result, "multiple_used", None)
    setattr(result, "unavailable_reason", reason)


def annotate_method_results_with_benchmark_provenance(
    valuation_results: Optional[Dict[str, object]],
    *,
    request: CalculateRequest | None = None,
    benchmark_contract: Optional[JsonMap],
    benchmark_provenance: Optional[JsonMap],
    allow_untrusted_fallback: bool,
) -> None:
    if not valuation_results:
        return

    for method_key, metric_aliases in _METHOD_BENCHMARK_METRICS.items():
        result = valuation_results.get(method_key)
        if result is None:
            continue

        uses_multiple = getattr(result, "multiple_used", None) is not None
        if not uses_multiple:
            continue

        details = as_mapping(getattr(result, "details", None)) or {}
        required_alias_sets = [metric_aliases]
        if method_key == "upswitch_adaptive" and request is not None:
            required_alias_sets = [
                _METHOD_BENCHMARK_METRICS[component]
                for component in sorted(_adaptive_component_method_keys(request))
            ]
        metrics_authorized = all(
            benchmark_metric_available(benchmark_contract, aliases)
            for aliases in required_alias_sets
        )
        if benchmark_provenance and metrics_authorized:
            fallback_reason = benchmark_contract_fallback_reason(benchmark_contract)
            details.update(
                {
                    "multiples_source": benchmark_contract_multiples_source(benchmark_contract),
                    "is_delphi_benchmark_sourced": benchmark_contract_is_delphi_sourced(
                        benchmark_contract
                    ),
                    "benchmark_contract": benchmark_contract,
                    "benchmark_provenance": benchmark_provenance,
                    "fallback_used": benchmark_contract_is_country_baseline(benchmark_contract),
                    "fallback_reason": fallback_reason,
                }
            )
            result.details = details
            continue

        governed_external = (
            governed_external_market_provenance(request) if request is not None else None
        )
        if governed_external is not None:
            details.update(governed_external)
            _preserve_external_reference_range_semantics(details, request)
            result.details = details
            continue

        if allow_untrusted_fallback:
            details.update(fallback_benchmark_provenance())
            _preserve_external_reference_range_semantics(details, request)
            result.details = details
            continue

        mark_method_unavailable_for_benchmark(
            result,
            reason=(
                "Geen gepubliceerde Upswitch-indexbenchmark beschikbaar voor deze multiple. "
                "De methode wordt niet gepubliceerd zonder expliciete fallback-goedkeuring."
            ),
        )
        details.update(
            {
                "publication_blocked": True,
                "required_benchmark_metric": ",".join(
                    aliases[0] for aliases in required_alias_sets
                ),
                "fallback_used": False,
            }
        )
        result.details = details


def _request_is_audited(request: CalculateRequest) -> bool:
    return bool(
        getattr(request, "has_audit", None)
        or getattr(request, "audited_financials", None)
        or getattr(request, "is_audited", None)
    )


def derive_data_tier(request: CalculateRequest) -> tuple[str, str]:
    """BET-434/435 — the evidence-defensibility tier this result rests on, derived from
    the TRUST of the inputs the engine actually used (reuses the benchmark-provenance
    policy above; never reinvents it):

      - ``defensible`` — a RESOLVED Upswitch index benchmark contract backs the
        multiples (company-specific, published evidence), so the number is grounded
        in real data rather than a market proxy.
      - ``indicative`` — a country-baseline / disclosed-fallback benchmark, or no
        resolved contract: a discussion RANGE, never a false-precision point.

    The shared lifecycle ladder has a third tier, ``attested`` (hash-locked legal
    attestation); VIQ never claims it from data alone — that upgrade is owned by the
    lifecycle / Attest layer (titan ``deal_ready``). Audited financials sharpen the
    ``defensible`` rationale but do not by themselves promote the tier here.
    """
    contract = extract_stateless_benchmark_contract(request)
    delphi_resolved = (
        contract is not None
        and benchmark_contract_is_resolved(contract)
        and benchmark_contract_is_delphi_sourced(contract)
    )
    if delphi_resolved:
        if _request_is_audited(request):
            return (
                "defensible",
                "Grounded in a resolved Upswitch index benchmark contract with audited financials.",
            )
        return ("defensible", "Grounded in a resolved Upswitch index benchmark contract.")
    if getattr(request, "external_market_reference_contract", None) is not None:
        return (
            "indicative",
            "Advisor-reviewed external market evidence; non-statistical and not an Upswitch Index benchmark.",
        )
    return (
        "indicative",
        "Registry-proxy or fallback benchmark — a discussion range, not a binding valuation.",
    )
