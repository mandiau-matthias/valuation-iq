"""Immutable hash and driver-ledger assembly for stateless valuations."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel
import rfc8785

from src import __version__
from src.api.schemas.stateless_api import CalculateRequest
from src.api.schemas.valuation_contracts import (
    BenchmarkSnapshotReference,
    ClassificationResolutionSnapshot,
    EconomicSnapshotReference,
    GovernedReportReviewDecision,
    NormalizationAdjustmentSnapshot,
    ReportAssuranceContract,
    ReportContentProvenanceSnapshot,
    ReportSourceCitation,
    SnapshotReference,
    ValuationRunV2,
    iter_accounting_reported_facts,
    priced_accounting_evidence,
    validate_priced_accounting_evidence_request,
)
from src.config.country_packs import COUNTRY_PACK_SCHEMA_VERSION, country_pack
from src.domain.valuation_wire import canonical_wire_value as _canonical
from src.services.reports.public_adaptive_profile import (
    public_modeled_dcf_is_authorized,
)
from src.services.reports.stateless_evidence_dates import evidence_source_as_of
from src.services.reports.report_assurance import assurance_from_legacy_response_snapshot
from src.utils.decimal_helpers import safe_decimal_or_zero

RUN_SCHEMA_VERSION = "valuation_run.v1"
RUN_SCHEMA_VERSION_V2 = "valuation_run.v2"
DEFAULT_POLICY_VERSION = "evidence_first_2026_08"
CONFIDENCE_MODEL_VERSION = "evidence_confidence.v1"
RUN_INTEGRITY_VERSION = "valuation_run_integrity.v1"
RUN_INTEGRITY_VERSION_V2 = "valuation_run_integrity.v2"
VALUATION_RESPONSE_SNAPSHOT_FIELDS = (
    "recommended_asking_price",
    "recommended_multiple",
    "methodology_selection_reason",
    "dcf_exclusion_reason",
    "confidence_level",
    "confidence_score",
    "earnings_basis",
    "earnings_basis_rationale",
    "multiple_build_up",
    "earnings_basis_ledger",
    "equity_bridge_adjustments",
    "holdings_consolidation",
    "size_discount",
    "liquidity_discount",
    "owner_dependency_adjustment",
    "owner_dependency_result",
    "country_adjustment",
    "total_adjustment",
    "nwc_normalization",
    "trial_balance_anomalies",
    "valuation_summary",
    "key_value_drivers",
    "risk_factors",
    "fiscal_4x_anchor",
    "data_quality",
    "data_tier",
    "data_tier_rationale",
    "publication_allowed",
    "publication_blocked",
    "report_readiness_state",
    "defensibility_review_state",
    "valuation_method_label",
    "confidence_label",
    "present_point_estimate",
    "valuation_disclaimer",
    "market_context",
    "public_valuation_audit",
    "negative_ebitda_resolution",
)


def canonical_json_bytes(value: object) -> bytes:
    """Serialize a contract value identically in Python and JavaScript.

    RFC 8785 deliberately uses ECMAScript number rendering.  Python's native
    JSON encoder renders some equivalent numbers differently (for example
    ``0.0`` instead of ``0`` and ``1e-07`` instead of ``1e-7``), which made a
    ValuationIQ-sealed run fail Titan's independent hash check for a small but
    real subset of public companies.
    """
    return rfc8785.dumps(_canonical(value))


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def transport_stable_valuation_run_value(value: object) -> object:
    """Materialize a run exactly as a JSON consumer can re-hash it.

    JSON parsers do not preserve the lexical distinction between an integer
    token and an integral floating-point token (``0`` versus ``0.0``). Python's
    A native Python JSON encoder preserves that distinction while JavaScript's
    ``JSON.parse``/``JSON.stringify`` does not. Any float inside a permissive
    run ``JsonObject`` would therefore self-verify in ValuationIQ but fail the
    same commitment in Titan. Decimal-valued calculation facts are already
    transported as strings; extend that rule to floats before sealing the run.
    """

    if isinstance(value, BaseModel):
        return transport_stable_valuation_run_value(value.model_dump(mode="python"))
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("valuation run contains a non-finite Decimal")
        return format(value, "f")
    if isinstance(value, float):
        decimal_value = Decimal(str(value))
        if not decimal_value.is_finite():
            raise ValueError("valuation run contains a non-finite float")
        return format(decimal_value, "f")
    if isinstance(value, Enum):
        return transport_stable_valuation_run_value(value.value)
    if isinstance(value, datetime):
        rendered = value.isoformat()
        return f"{rendered[:-6]}Z" if rendered.endswith("+00:00") else rendered
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): transport_stable_valuation_run_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [transport_stable_valuation_run_value(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _without_volatile_audit_fields(value: object) -> object:
    """Remove recording-time fields from deterministic calculation identity."""
    if isinstance(value, BaseModel):
        return _without_volatile_audit_fields(value.model_dump(mode="python"))
    if isinstance(value, Mapping):
        return {
            str(key): _without_volatile_audit_fields(item)
            for key, item in value.items()
            if str(key) not in {"calculation_timestamp", "recording_date", "valuation_date"}
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_without_volatile_audit_fields(item) for item in value]
    return value


_REVIEW_SCOPE_VOLATILE_FIELDS = frozenset(
    {
        "calculated_at",
        "calculation_timestamp",
        "computed_at",
        "created_at",
        "execution_id",
        "generated_at",
        "recording_date",
        "recording_timestamp",
        "run_id",
        "updated_at",
        "valuation_date",
    }
)


def _without_review_scope_volatile_fields(value: object) -> object:
    """Remove runtime receipts while retaining every priced input and result.

    Calculation/run identity continues to bind the full audit payload.  The
    advisor review scope must instead be reproducible when the same economic
    calculation is executed twice, so clocks and process identifiers are not
    part of that separate commitment.
    """

    if isinstance(value, BaseModel):
        return _without_review_scope_volatile_fields(value.model_dump(mode="python"))
    if isinstance(value, Mapping):
        return {
            str(key): _without_review_scope_volatile_fields(item)
            for key, item in value.items()
            if str(key) not in _REVIEW_SCOPE_VOLATILE_FIELDS
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_without_review_scope_volatile_fields(item) for item in value]
    return value


def _run_field(run: object, name: str, default: object = None) -> object:
    if isinstance(run, Mapping):
        return run.get(name, default)
    return getattr(run, name, default)


def _is_timeline_projection_request(request: CalculateRequest) -> bool:
    """Recognize only the internally constructed, non-releasable subrequest."""

    metadata = request.metadata if isinstance(request.metadata, Mapping) else {}
    parent_id = str(metadata.get("valuation_timeline_parent_valuation_id") or "")
    target_year = metadata.get("valuation_timeline_target_fiscal_year")
    return bool(
        metadata.get("valuation_timeline_subrequest") is True
        and parent_id
        and target_year == request.current_year.year
        and request.valuation_id == f"{parent_id}_ty{target_year}"
        and request.include_valuation_timeline is False
    )


def valuation_run_calculation_commitment(run: object) -> dict[str, object]:
    return {
        "valuation_range": _run_field(run, "valuation_range", {}),
        "enterprise_value_range": _run_field(run, "enterprise_value_range", {}),
        "methodology_used": _run_field(run, "methodology_used"),
        "method_mix": _run_field(run, "method_mix", []),
        "method_results": _run_field(run, "method_results", {}),
        "weighted_valuation": _run_field(run, "weighted_valuation"),
        "methodology_weights": _run_field(run, "methodology_weights", {}),
        "financial_metrics": _run_field(run, "financial_metrics", {}),
        "dcf_results": _run_field(run, "dcf_results"),
        "multiples_results": _run_field(run, "multiples_results"),
        "response_snapshot": _run_field(run, "response_snapshot", {}),
        "driver_ledger": _run_field(run, "driver_ledger", {}),
        "calculation_lineage": _run_field(run, "calculation_lineage", {}),
        "projection_layers": _without_volatile_audit_fields(
            _run_field(run, "projection_layers", {})
        ),
    }


_STABLE_REVIEW_ATTESTATION_FIELDS = (
    "schema_version",
    "content_hash_version",
    "canonicalization",
    "company_id",
    "case_id",
    "evidence_revision_id",
    "evidence_hash",
    "decision_set_hash",
    "benchmark_hash",
    "economic_snapshot_hash",
    "country_pack_hash",
    "policy_hash",
)


def _stable_review_calculation_lineage(value: object) -> dict[str, object]:
    """Remove only receipt/signature material that changes when review is added.

    The stable commitment keeps every independent evidence, decision-set,
    benchmark, economic, country-pack and policy hash. The issuer/key lifecycle,
    enclosing case hash, detached signature, and exact request-wire hash remain
    protected by the ordinary calculation/run hashes but cannot be part of the
    object that an advisor must sign before that receipt exists.
    """

    lineage = dict(value) if isinstance(value, Mapping) else {}
    attestation = lineage.get("valuation_case_attestation")
    if isinstance(attestation, Mapping):
        lineage["valuation_case_attestation"] = {
            field: attestation.get(field) for field in _STABLE_REVIEW_ATTESTATION_FIELDS
        }
    for volatile in (
        "valuation_case_attestation_content_hash",
        "valuation_case_hash",
        "titan_request_wire_commitment",
    ):
        lineage.pop(volatile, None)
    return lineage


def valuation_run_review_scope_commitment(run: object) -> dict[str, object]:
    """Economic calculation material that is stable across two-pass review."""

    method_mix = _without_review_scope_volatile_fields(_run_field(run, "method_mix", []))
    selected_keys = {
        str(row.get("method_key"))
        for row in method_mix
        if isinstance(row, Mapping) and safe_decimal_or_zero(row.get("weight")) > 0
    }
    raw_methods = _run_field(run, "method_results", {})
    selected_methods = (
        {
            str(key): _without_review_scope_volatile_fields(value)
            for key, value in raw_methods.items()
            if str(key) in selected_keys
            or (
                str(key) == "ebitda_multiple"
                and "upswitch_adaptive" in selected_keys
                and isinstance(value, Mapping)
                and (
                    value.get("source_contract") == "governed_external_market_reference"
                    or (
                        isinstance(value.get("details"), Mapping)
                        and value["details"].get("source_contract")
                        == "governed_external_market_reference"
                    )
                )
            )
        }
        if isinstance(raw_methods, Mapping)
        else {}
    )
    # This is intentionally a priced projection, not a copy of every run
    # diagnostic. Zero-weight liquidation/SDE/startup audit records and their
    # runtime IDs cannot change the economic object reviewed by an advisor.
    # ``input_hash`` is deliberately excluded: it commits the complete request
    # envelope, including the case receipt that is created only after this
    # scope is reviewed. It remains protected by calculation/run identity,
    # while stable evidence/decision/economic hashes and all priced outputs are
    # bound below without the circular two-pass lifecycle material.
    commitment = {
        "valuation_range": _run_field(run, "valuation_range", {}),
        "enterprise_value_range": _run_field(run, "enterprise_value_range", {}),
        "value_basis": _run_field(run, "value_basis", "mixed"),
        "methodology_used": _run_field(run, "methodology_used"),
        "method_mix": method_mix,
        "method_results": selected_methods,
        "weighted_valuation": _without_review_scope_volatile_fields(
            _run_field(run, "weighted_valuation")
        ),
        "methodology_weights": _run_field(run, "methodology_weights", {}),
        "financial_metrics": _run_field(run, "financial_metrics", {}),
        "dcf_results": _without_review_scope_volatile_fields(_run_field(run, "dcf_results")),
        "multiples_results": _without_review_scope_volatile_fields(
            _run_field(run, "multiples_results")
        ),
        "benchmark_hash": _run_field(run, "benchmark_hash"),
        "evidence_hash": _run_field(run, "evidence_hash"),
        "accounting_evidence_bundle_hash": _run_field(run, "accounting_evidence_bundle_hash"),
    }
    commitment["calculation_lineage"] = _stable_review_calculation_lineage(
        _run_field(run, "calculation_lineage", {})
    )
    scrubbed = _without_review_scope_volatile_fields(commitment)
    return dict(scrubbed) if isinstance(scrubbed, Mapping) else commitment


def valuation_response_snapshot(value: object) -> dict[str, object]:
    """Select and sanitize every report-consumed response field committed by a run."""
    snapshot = {field: _run_field(value, field) for field in VALUATION_RESPONSE_SNAPSHOT_FIELDS}
    sanitized = _without_volatile_audit_fields(snapshot)
    return dict(sanitized) if isinstance(sanitized, Mapping) else snapshot


def valuation_run_audit_commitment(run: object) -> dict[str, object]:
    return {
        "public_valuation_audit": _run_field(run, "public_valuation_audit_snapshot"),
        "triage_flags": _run_field(run, "qualifications", []),
        "driver_ledger": _run_field(run, "driver_ledger", {}),
    }


def valuation_run_identity_commitment(run: object) -> dict[str, object]:
    commitment = {
        "schema_version": _run_field(run, "schema_version", RUN_SCHEMA_VERSION),
        "integrity_version": _run_field(run, "integrity_version"),
        "execution_id": _run_field(run, "execution_id"),
        "valuation_id": _run_field(run, "valuation_id"),
        "case_id": _run_field(run, "case_id"),
        "company_id": _run_field(run, "company_id"),
        "company_name": _run_field(run, "company_name"),
        "country_code": _run_field(run, "country_code"),
        "company_profile_snapshot": _run_field(run, "company_profile_snapshot", {}),
        "scenario_id": _run_field(run, "scenario_id"),
        "evidence_revision_id": _run_field(run, "evidence_revision_id"),
        "calculation_timestamp": _run_field(run, "calculation_timestamp"),
        "recording_timestamp": _run_field(run, "recording_timestamp"),
        "fiscal_effective_date": _run_field(run, "fiscal_effective_date"),
        "valuation_lens_date": _run_field(run, "valuation_lens_date"),
        "source_as_of": _run_field(run, "source_as_of"),
        "currency": _run_field(run, "currency"),
        "value_basis": _run_field(run, "value_basis", "mixed"),
        "engine_version": _run_field(run, "engine_version"),
        "policy_version": _run_field(run, "policy_version"),
        "confidence_model_version": _run_field(run, "confidence_model_version"),
        "input_hash": _run_field(run, "input_hash"),
        "evidence_hash": _run_field(run, "evidence_hash"),
        "evidence_hash_source": _run_field(run, "evidence_hash_source"),
        "benchmark_hash": _run_field(run, "benchmark_hash"),
        "benchmark_hash_source": _run_field(run, "benchmark_hash_source"),
        "calculation_hash": _run_field(run, "calculation_hash"),
        "audit_hash": _run_field(run, "audit_hash"),
    }
    if _run_field(run, "schema_version") == RUN_SCHEMA_VERSION_V2:
        commitment.update(
            {
                "company_snapshot": _run_field(run, "company_snapshot", {}),
                "uploaded_data_snapshot": _run_field(run, "uploaded_data_snapshot"),
                "uploaded_data_snapshot_status": _run_field(
                    run, "uploaded_data_snapshot_status", "not_supplied"
                ),
                "classification_resolution": _run_field(run, "classification_resolution", {}),
                "benchmark_snapshot_references": _run_field(
                    run, "benchmark_snapshot_references", []
                ),
                "source_citations": _run_field(run, "source_citations", []),
                "normalization_adjustments": _run_field(run, "normalization_adjustments", []),
                "normalization_adjustments_hash": _run_field(run, "normalization_adjustments_hash"),
                "accounting_evidence_bundle_hash": _run_field(
                    run, "accounting_evidence_bundle_hash"
                ),
                "country_pack_schema_version": _run_field(run, "country_pack_schema_version"),
                "country_pack_version": _run_field(run, "country_pack_version"),
                "economic_snapshot": _run_field(run, "economic_snapshot"),
                "economic_snapshot_status": _run_field(
                    run, "economic_snapshot_status", "not_supplied"
                ),
                "review_scope_hash": _run_field(run, "review_scope_hash"),
                "report_review_decisions": _run_field(run, "report_review_decisions", []),
                "content_provenance": _run_field(run, "content_provenance", {}),
                "assurance": _run_field(run, "assurance", {}),
            }
        )
    return commitment


def verify_valuation_run_integrity(run: object) -> None:
    benchmark_snapshot = _run_field(run, "benchmark_snapshot")
    if not isinstance(benchmark_snapshot, Mapping):
        raise ValueError("valuation_run benchmark_snapshot is required for integrity")
    if canonical_hash(benchmark_snapshot) != _run_field(run, "benchmark_hash"):
        raise ValueError("valuation_run benchmark_hash integrity check failed")
    if _run_field(run, "schema_version") == RUN_SCHEMA_VERSION_V2:
        if canonical_hash(_run_field(run, "normalization_adjustments", [])) != _run_field(
            run, "normalization_adjustments_hash"
        ):
            raise ValueError("valuation_run normalization_adjustments_hash integrity check failed")
    expected_calculation = canonical_hash(valuation_run_calculation_commitment(run))
    if expected_calculation != _run_field(run, "calculation_hash"):
        raise ValueError("valuation_run calculation_hash integrity check failed")
    if _run_field(run, "schema_version") == RUN_SCHEMA_VERSION_V2:
        expected_review_scope = canonical_hash(valuation_run_review_scope_commitment(run))
        if expected_review_scope != _run_field(run, "review_scope_hash"):
            raise ValueError("valuation_run review_scope_hash integrity check failed")
    expected_audit = canonical_hash(valuation_run_audit_commitment(run))
    if expected_audit != _run_field(run, "audit_hash"):
        raise ValueError("valuation_run audit_hash integrity check failed")
    expected_run = canonical_hash(valuation_run_identity_commitment(run))
    if expected_run != _run_field(run, "run_hash"):
        raise ValueError("valuation_run run_hash integrity check failed")
    if f"vrun_{expected_run[:24]}" != _run_field(run, "run_id"):
        raise ValueError("valuation_run run_id does not match run_hash")


def seal_valuation_run_payload(fields: Mapping[str, object]) -> dict[str, object]:
    """Seal a complete run payload using the same commitments as validation."""
    transport_fields = transport_stable_valuation_run_value(fields)
    if not isinstance(transport_fields, Mapping):
        raise ValueError("valuation run payload must be an object")
    sealed = dict(transport_fields)
    sealed.setdefault("schema_version", RUN_SCHEMA_VERSION)
    sealed.setdefault(
        "integrity_version",
        (
            RUN_INTEGRITY_VERSION_V2
            if sealed.get("schema_version") == RUN_SCHEMA_VERSION_V2
            else RUN_INTEGRITY_VERSION
        ),
    )
    sealed.setdefault("value_basis", "mixed")
    if sealed.get("schema_version") == RUN_SCHEMA_VERSION_V2:
        _materialize_v2_evidence_defaults(sealed)
        _normalize_v2_evidence_fields(sealed)
    benchmark_snapshot = sealed.get("benchmark_snapshot")
    if not isinstance(benchmark_snapshot, Mapping):
        raise ValueError("benchmark_snapshot is required before sealing a valuation run")
    sealed["benchmark_hash"] = canonical_hash(benchmark_snapshot)
    if sealed.get("schema_version") == RUN_SCHEMA_VERSION_V2:
        sealed["normalization_adjustments_hash"] = canonical_hash(
            sealed.get("normalization_adjustments", [])
        )
    sealed["calculation_hash"] = canonical_hash(valuation_run_calculation_commitment(sealed))
    if sealed.get("schema_version") == RUN_SCHEMA_VERSION_V2:
        sealed["review_scope_hash"] = canonical_hash(valuation_run_review_scope_commitment(sealed))
        # Method certification is the only assurance projection that depends
        # on the stable two-pass review scope. The first pass computes that
        # scope; a later pass may carry an advisor decision over it. Refresh
        # the projection only after the scope exists, then validate the whole
        # assurance contract before it enters the immutable run identity.
        assurance_payload = dict(sealed.get("assurance") or {})
        assurance_payload.update(_method_certification_assurance_fields(sealed))
        sealed["assurance"] = ReportAssuranceContract.model_validate(assurance_payload).model_dump(
            mode="json"
        )
    sealed["audit_hash"] = canonical_hash(valuation_run_audit_commitment(sealed))
    sealed["run_hash"] = canonical_hash(valuation_run_identity_commitment(sealed))
    sealed["run_id"] = f"vrun_{str(sealed['run_hash'])[:24]}"
    return sealed


def _materialize_v2_evidence_defaults(sealed: dict[str, object]) -> None:
    """Keep the sealing helper useful for hand-built deterministic test runs."""
    profile = sealed.get("company_profile_snapshot")
    profile_mapping = dict(profile) if isinstance(profile, Mapping) else {}
    profile_hash = canonical_hash(profile_mapping)
    sealed.setdefault(
        "company_snapshot",
        {
            "snapshot_id": f"company_{profile_hash[:24]}",
            "snapshot_hash": profile_hash,
            "source_kind": "derived_request_company_profile",
        },
    )
    sealed.setdefault("uploaded_data_snapshot", None)
    sealed.setdefault("uploaded_data_snapshot_status", "not_supplied")
    sealed.setdefault(
        "classification_resolution",
        _derived_classification_resolution(profile_mapping),
    )
    sealed.setdefault("benchmark_snapshot_references", [])
    sealed.setdefault("source_citations", [])
    sealed.setdefault("normalization_adjustments", [])
    sealed.setdefault("report_review_decisions", [])
    sealed.setdefault(
        "content_provenance",
        ReportContentProvenanceSnapshot().model_dump(mode="json"),
    )
    assurance = sealed.get("assurance")
    assurance_payload = (
        dict(assurance)
        if isinstance(assurance, Mapping)
        else assurance_from_legacy_response_snapshot(
            sealed.get("response_snapshot"),
            confidence_model_version=str(
                sealed.get("confidence_model_version") or CONFIDENCE_MODEL_VERSION
            ),
        ).model_dump(mode="json")
    )
    resolved_pack = country_pack(str(sealed.get("country_code") or ""))
    if resolved_pack is None:
        raise ValueError("a configured CountryPack is required to seal valuation_run.v2")
    assurance_payload.update(_country_pack_assurance_fields(resolved_pack))
    assurance_payload.update(_method_certification_assurance_fields(sealed))
    sealed["assurance"] = assurance_payload
    sealed.setdefault("country_pack_schema_version", COUNTRY_PACK_SCHEMA_VERSION)
    sealed.setdefault("country_pack_version", resolved_pack.pack_version)
    sealed.setdefault("economic_snapshot", None)
    sealed.setdefault("economic_snapshot_status", "not_supplied")


def _normalize_v2_evidence_fields(sealed: dict[str, object]) -> None:
    sealed["company_snapshot"] = SnapshotReference.model_validate(
        sealed["company_snapshot"]
    ).model_dump(mode="json")
    uploaded = sealed.get("uploaded_data_snapshot")
    sealed["uploaded_data_snapshot"] = (
        SnapshotReference.model_validate(uploaded).model_dump(mode="json")
        if uploaded is not None
        else None
    )
    sealed["classification_resolution"] = ClassificationResolutionSnapshot.model_validate(
        sealed["classification_resolution"]
    ).model_dump(mode="json")
    economic_snapshot = sealed.get("economic_snapshot")
    sealed["economic_snapshot"] = (
        EconomicSnapshotReference.model_validate(economic_snapshot).model_dump(mode="json")
        if economic_snapshot is not None
        else None
    )
    sealed["benchmark_snapshot_references"] = [
        BenchmarkSnapshotReference.model_validate(row).model_dump(mode="json")
        for row in sealed.get("benchmark_snapshot_references", [])
    ]
    sealed["source_citations"] = [
        ReportSourceCitation.model_validate(row).model_dump(mode="json")
        for row in sealed.get("source_citations", [])
    ]
    sealed["normalization_adjustments"] = [
        NormalizationAdjustmentSnapshot.model_validate(row).model_dump(mode="json")
        for row in sealed.get("normalization_adjustments", [])
    ]
    sealed["report_review_decisions"] = [
        GovernedReportReviewDecision.model_validate(row).model_dump(mode="json")
        for row in sealed.get("report_review_decisions", [])
    ]
    sealed["content_provenance"] = ReportContentProvenanceSnapshot.model_validate(
        sealed.get("content_provenance") or {}
    ).model_dump(mode="json")
    sealed["assurance"] = ReportAssuranceContract.model_validate(
        sealed.get("assurance") or {}
    ).model_dump(mode="json")


def _country_pack_assurance_fields(pack: object) -> dict[str, object]:
    """Project the exact policy-pack certification record into run assurance."""

    return {
        "country_pack_certification_state": getattr(pack, "certification_state", "draft"),
        "country_pack_certification_manifest_hash": getattr(
            pack, "certification_manifest_hash", None
        ),
        "country_pack_certification_reviewer_receipt_ids": list(
            getattr(pack, "certification_reviewer_receipt_ids", ()) or ()
        ),
    }


def _method_certification_assurance_fields(run: Mapping[str, object]) -> dict[str, object]:
    """Evaluate the actual priced run; registry membership never certifies it."""

    from src.domain.method_certification_evaluator import (
        evaluate_run_method_certification,
    )
    from src.domain.method_certification_profiles import (
        METHOD_CERTIFICATION_PROFILE_VERSION,
    )

    evaluations = evaluate_run_method_certification(run)
    profile_keys = sorted(
        {
            str(row["method_key"])
            for row in evaluations
            if row.get("profile_version") == METHOD_CERTIFICATION_PROFILE_VERSION
        }
    )
    eligible = bool(evaluations) and all(row.get("eligible") is True for row in evaluations)
    return {
        "method_certification_profile_version": METHOD_CERTIFICATION_PROFILE_VERSION,
        "priced_method_certification_profile_keys": profile_keys,
        "method_certification_evaluations": evaluations,
        "method_country_certification_eligible": eligible,
    }


def _derived_classification_resolution(
    profile: Mapping[str, object],
) -> dict[str, object]:
    nace = profile.get("nace_code")
    business_type_id = profile.get("business_type_id")
    material = {
        "requested_nace_code": nace,
        "canonical_nace_code": nace,
        "business_type_id": business_type_id,
        "business_type_label": profile.get("business_type_label"),
        "resolution_level": "request_calibration",
        "resolution_status": (
            "resolved" if nace and business_type_id else "manual_review_required"
        ),
        "confidence": None,
        "mapping_version": None,
        "taxonomy_version": None,
        "reviewer_state": None,
    }
    material["mapping_hash"] = canonical_hash(material)
    return material


def _economic_snapshot_reference(request: CalculateRequest) -> dict[str, object] | None:
    context = request.economic_context
    if getattr(context, "schema_version", None) != "economic_snapshot.v1":
        return None
    return {
        "schema_version": context.schema_version,
        "snapshot_id": context.snapshot_id,
        "snapshot_hash": context.snapshot_hash,
        "snapshot_issuer": context.snapshot_issuer,
        "country_code": context.country_code,
        "risk_free_rate_observed_at": context.risk_free_rate_observed_at.isoformat(),
        "equity_risk_premium_observed_at": (context.equity_risk_premium_observed_at.isoformat()),
        "growth_rates_observed_at": context.growth_rates_observed_at.isoformat(),
        "source": context.source,
        "source_references": list(context.source_references),
    }


def build_value_driver_ledger(
    *,
    earnings_basis_ledger: Mapping[str, object],
    multiple_build_up: object,
    equity_bridge_adjustments: Mapping[str, object],
    holdings_consolidation: Mapping[str, object] | None,
    owner_dependency_result: Mapping[str, object] | None,
    owner_dependency_adjustment: Decimal,
    ownership_percentage: Decimal,
    equity_before_owner_dependency: Decimal,
    equity_after_owner_dependency: Decimal,
    canonical_enterprise_value: Decimal | None = None,
    methodology_used: str | None = None,
) -> dict[str, object]:
    build_up = (
        multiple_build_up.model_dump(mode="json")
        if isinstance(multiple_build_up, BaseModel)
        else dict(multiple_build_up) if isinstance(multiple_build_up, Mapping) else {}
    )
    market_bridge = build_up.get("equity_bridge")
    canonical_bridge = _canonical_equity_bridge(
        market_bridge=market_bridge,
        canonical_enterprise_value=canonical_enterprise_value,
        canonical_equity_value=equity_before_owner_dependency,
        methodology_used=methodology_used,
    )
    bridge_not_applicable = (
        isinstance(canonical_bridge, Mapping)
        and canonical_bridge.get("applicability") == "not_applicable"
    )
    return {
        "version": "value_driver_ledger.v1",
        "layers": {
            "operating_normalizations": {
                "label": "Reported to normalized operating basis",
                "earnings_basis": dict(earnings_basis_ledger),
                "holdings_consolidation": (
                    dict(holdings_consolidation) if holdings_consolidation else None
                ),
            },
            "method_calibration": {
                "label": "Method-level market calibration before enterprise value",
                "value_basis": "enterprise_value",
                "market_discount_stack": build_up.get("discounts"),
                "calculation_order": "reference_multiple_to_applied_multiple_to_enterprise_value",
            },
            "enterprise_to_equity": {
                "label": (
                    "Enterprise value not applicable — direct equity premise"
                    if bridge_not_applicable
                    else "Enterprise value to total shareholder equity"
                ),
                "bridge": canonical_bridge,
                "supporting_market_bridge": (
                    market_bridge
                    if canonical_bridge is not market_bridge and not bridge_not_applicable
                    else None
                ),
                "explicit_adjustments": dict(equity_bridge_adjustments),
            },
            "shareholder_transaction": {
                "label": "Structural, shareholder and transaction adjustments",
                "ownership_percentage": ownership_percentage,
                "owner_dependency": (
                    dict(owner_dependency_result) if owner_dependency_result else None
                ),
                "owner_dependency_adjustment": owner_dependency_adjustment,
                "equity_before_owner_dependency": equity_before_owner_dependency,
                "equity_after_owner_dependency": equity_after_owner_dependency,
            },
        },
    }


def _canonical_equity_bridge(
    *,
    market_bridge: object,
    canonical_enterprise_value: Decimal | None,
    canonical_equity_value: Decimal,
    methodology_used: str | None,
) -> object:
    if canonical_enterprise_value is None:
        # Never substitute a supporting market bridge when the selected
        # canonical conclusion has no enterprise-value premise. This covers
        # direct-equity methods and equity-only SOTP composites alike.
        return {
            "version": "canonical_enterprise_to_equity_reconciliation.v1",
            "methodology_used": methodology_used,
            "applicability": "not_applicable",
            "value_basis": "equity_value",
            "enterprise_value": None,
            "equity_value": safe_decimal_or_zero(canonical_equity_value),
            "lines": [],
        }
    enterprise = safe_decimal_or_zero(canonical_enterprise_value)
    equity = safe_decimal_or_zero(canonical_equity_value)
    if isinstance(market_bridge, Mapping):
        market_enterprise = safe_decimal_or_zero(market_bridge.get("enterprise_value"))
        market_equity = safe_decimal_or_zero(market_bridge.get("equity_value"))
        if market_enterprise == enterprise and market_equity == equity:
            return market_bridge
    adjustment = equity - enterprise
    return {
        "version": "canonical_enterprise_to_equity_reconciliation.v1",
        "methodology_used": methodology_used,
        "enterprise_value": enterprise,
        "equity_value": equity,
        "lines": [
            {
                "kind": "canonical_equity_bridge_reconciliation",
                "label": "Net EV-to-equity and synthesis reconciliation",
                "operator": "+" if adjustment >= 0 else "-",
                "amount": abs(adjustment),
                "priced": True,
            }
        ],
    }


def build_stateless_valuation_run(
    *,
    request: CalculateRequest,
    verified_titan_request_wire_commitment: Mapping[str, str] | None = None,
    calculation_timestamp: str,
    equity_values: Mapping[str, object],
    enterprise_values: Mapping[str, object] | None,
    methodology_used: str,
    dcf_weight: Decimal,
    multiples_weight: Decimal,
    valuation_results: Mapping[str, object],
    benchmark_contract: Mapping[str, object] | None,
    triage_flags: Sequence[object],
    driver_ledger: Mapping[str, object],
    public_valuation_audit: Mapping[str, object] | None,
    valuation_timeline: object = None,
    forward_value_cone: object = None,
    weighted_valuation: object = None,
    financial_metrics: Mapping[str, object] | None = None,
    dcf_results: Mapping[str, object] | None = None,
    multiples_results: Mapping[str, object] | None = None,
    response_snapshot: Mapping[str, object] | None = None,
) -> ValuationRunV2:
    # This builder is also used directly by deterministic/report tests. Repeat
    # the boundary check here so no caller can seal an unrelated evidence hash
    # without passing through the public CalculateRequest validator.
    validate_priced_accounting_evidence_request(request)
    case = request.valuation_case
    request_payload = request.model_dump(mode="json")
    input_hash = canonical_hash(request_payload)
    accounting_evidence = priced_accounting_evidence(case)
    accounting_evidence_bundle_hash = None
    if accounting_evidence is not None:
        evidence_hash = accounting_evidence.snapshot_hash
        evidence_hash_source = "accounting_evidence_package"
        if case is not None and isinstance(case.accounting_evidence_bundle, Mapping):
            accounting_evidence_bundle_hash = case.accounting_evidence_bundle.get("bundle_hash")
    else:
        evidence_hash = canonical_hash(
            {
                "current_year": request_payload.get("current_year"),
                "historical_years": request_payload.get("historical_years"),
                "normalizations": request_payload.get("normalizations"),
            }
        )
        evidence_hash_source = "derived_from_request_reported_facts"

    property_yield_contract = getattr(request, "real_estate_yield_evidence_contract", None)
    if property_yield_contract is not None:
        property_yield_material = _property_yield_benchmark_material(property_yield_contract)
        benchmark_snapshot_payload = {
            "schema_version": "valuation_benchmark_bundle.v1",
            "target_country_code": request.country_code,
            "metrics": {"property_yield": property_yield_material},
        }
        benchmark_hash_source = "signed_real_estate_yield_evidence_contract"
    else:
        benchmark_snapshot_payload = (
            dict(benchmark_contract)
            if benchmark_contract
            else request.business_type_calibration.model_dump(mode="json")
        )
        benchmark_hash_source = (
            "governed_benchmark_contract"
            if benchmark_contract
            else "request_business_type_calibration"
        )
    business_type_id = request.business_type_calibration.business_type_id
    business_type_label = business_type_id.replace("_", " ").replace("-", " ").title()
    benchmark_title = (
        benchmark_contract.get("source_business_type_title")
        if isinstance(benchmark_contract, Mapping)
        else None
    )
    if benchmark_title:
        business_type_label = str(benchmark_title)
    company_profile_snapshot = {
        "company_name": request.company_name,
        "country_code": request.country_code,
        "industry": request.industry,
        "business_model": request.business_model,
        "founding_year": request.founding_year,
        "number_of_employees": request.number_of_employees,
        "registration_number": (
            request.registration_number or request.kbo_number or request.kvk_number
        ),
        "nace_code": request.canonical_nace_code or request.nace_code,
        "legal_form": request.legal_form,
        "city": request.city,
        "incorporated_on": request.incorporated_on,
        "business_type_id": business_type_id,
        "business_type_label": business_type_label,
    }
    company_profile_hash = canonical_hash(company_profile_snapshot)
    company_snapshot = {
        "snapshot_id": (
            case.company_snapshot_id
            if case is not None and case.company_snapshot_id
            else f"company_{company_profile_hash[:24]}"
        ),
        "snapshot_hash": (
            case.company_snapshot_hash
            if case is not None and case.company_snapshot_hash
            else company_profile_hash
        ),
        "source_kind": (
            "upstream_company_snapshot"
            if case is not None and case.company_snapshot_id
            else "derived_request_company_profile"
        ),
        # A detached client-indicative dossier has no canonical entity UUID yet,
        # but the immutable run must still expose the exact legal-entity key it
        # hashed.  Keep the field nullable for legacy/unregistered requests and
        # never infer an owner or workspace identity from it.
        "company_registry_number": (
            request.registration_number or request.kbo_number or request.kvk_number
        ),
    }
    attested_snapshot = (
        case.attested_uploaded_data_snapshot
        if case is not None and case.accounting_evidence_attachment == "unattached_non_priced"
        else None
    )
    if attested_snapshot is not None:
        request_registry = _normalized_registry_number(
            request.registration_number or request.kbo_number or request.kvk_number
        )
        snapshot_registry = _normalized_registry_number(attested_snapshot.company_registry_number)
        if request_registry and snapshot_registry and request_registry != snapshot_registry:
            raise ValueError(
                "attested uploaded-data snapshot registry number must match request company"
            )
    if accounting_evidence is not None:
        uploaded_data_snapshot = {
            "snapshot_id": accounting_evidence.snapshot_id,
            "snapshot_hash": accounting_evidence.snapshot_hash,
            "source_kind": "uploaded_accounting_evidence",
            "revision_id": accounting_evidence.evidence_revision_id,
        }
        uploaded_data_snapshot_status = "priced"
    elif attested_snapshot is not None:
        uploaded_data_snapshot = attested_snapshot.model_dump(mode="json")
        uploaded_data_snapshot_status = "attested_non_priced"
    else:
        uploaded_data_snapshot = None
        uploaded_data_snapshot_status = "not_supplied"
    classification_resolution = _classification_resolution_for_run(
        request=request,
        case=case,
        company_profile_snapshot=company_profile_snapshot,
    )
    benchmark_snapshot_references = _benchmark_snapshot_references_for_run(
        request=request,
        benchmark_contract=benchmark_contract,
    )
    if property_yield_contract is not None:
        benchmark_snapshot_references.append(
            _property_yield_benchmark_reference(property_yield_contract)
        )
    source_citations = _source_citations_for_run(
        case=case,
        accounting_evidence=accounting_evidence,
        request=request,
        benchmark_contract=benchmark_contract,
        real_estate_yield_evidence_contract=property_yield_contract,
    )
    normalization_adjustments = _normalization_adjustments_for_run(request)
    method_mix = _method_mix(
        weighted_valuation=weighted_valuation,
        methodology_used=methodology_used,
        dcf_weight=dcf_weight,
        multiples_weight=multiples_weight,
    )
    resolved_weights = (financial_metrics or {}).get("resolved_method_weights")
    if resolved_weights:
        # EV-only publication removes the equity synthesis object. Preserve its
        # actual admitted method contributions rather than infer fallback weights.
        method_mix = [dict(row) for row in resolved_weights]
    policy_version = case.policy_version if case is not None else DEFAULT_POLICY_VERSION
    engine_version = os.getenv("VALUATIONIQ_VERSION", f"valuation-iq/{__version__}")
    resolved_country_pack = country_pack(request.country_code)
    if resolved_country_pack is None:
        raise ValueError(f"no CountryPack configured for {request.country_code!r}")
    execution_id = f"exec_{uuid4().hex}"
    valuation_range = {
        "low": equity_values.get("low"),
        "mid": equity_values.get("mid"),
        "high": equity_values.get("high"),
        "currency": request.currency,
        "value_basis": "equity_value",
        "uncertainty_type": "valuation_range",
    }
    enterprise_components = tuple(
        enterprise_values.get(key) if enterprise_values is not None else None
        for key in ("low", "mid", "high")
    )
    if any(value is not None for value in enterprise_components) and not all(
        value is not None for value in enterprise_components
    ):
        raise ValueError(
            "enterprise value range must provide low/mid/high together or be explicitly not applicable"
        )
    enterprise_value_range = (
        {
            "low": enterprise_components[0],
            "mid": enterprise_components[1],
            "high": enterprise_components[2],
            "currency": request.currency,
            "value_basis": "enterprise_value",
            "uncertainty_type": "valuation_range",
        }
        if all(value is not None for value in enterprise_components)
        else None
    )
    equity_unavailable = all(equity_values.get(key) is None for key in ("low", "mid", "high"))
    if equity_unavailable:
        if enterprise_value_range is None:
            raise ValueError("numeric run requires an independently eligible value basis")
        valuation_range = dict(enterprise_value_range)
        for row in method_mix:
            row["value_basis"] = "enterprise_value"
    reported_facts_node: dict[str, object] = {
        "id": "reported_facts",
        "kind": "reported_evidence",
        "hash": evidence_hash,
    }
    if accounting_evidence is not None:
        reported_facts_node.update(
            {
                "snapshot_id": accounting_evidence.snapshot_id,
                "evidence_revision_id": accounting_evidence.evidence_revision_id,
                "content_hash_version": accounting_evidence.content_hash_version,
                "attachment": "priced",
            }
        )
    timeline_projection_only = _is_timeline_projection_request(request)
    calculation_lineage = {
        "version": "valuation_calculation_lineage.v1",
        "nodes": [
            reported_facts_node,
            {"id": "input_decisions", "kind": "accepted_or_verified_decisions"},
            {"id": "normalized_history", "kind": "annual_normalization_then_weighting"},
            {"id": "method_calibration", "kind": "method_level_ev_calibration"},
            {"id": "method_results", "kind": "method_specific_calculations"},
            {"id": "enterprise_to_equity", "kind": "equity_bridge"},
            {"id": "shareholder_transaction", "kind": "structural_adjustments"},
            {"id": "valuation_range", "kind": "canonical_result"},
        ],
        "edges": [
            {"from": "reported_facts", "to": "input_decisions"},
            {"from": "input_decisions", "to": "normalized_history"},
            {"from": "normalized_history", "to": "method_calibration"},
            {"from": "method_calibration", "to": "method_results"},
            {"from": "method_results", "to": "enterprise_to_equity"},
            {"from": "enterprise_to_equity", "to": "shareholder_transaction"},
            {"from": "shareholder_transaction", "to": "valuation_range"},
        ],
    }
    claimed_request_wire_commitment = (
        request.metadata.get("titan_request_wire_commitment")
        if isinstance(request.metadata, Mapping)
        else None
    )
    if claimed_request_wire_commitment is not None:
        if verified_titan_request_wire_commitment is None:
            raise ValueError("Titan request wire commitment was not verified at the HTTP boundary")
        if _canonical(claimed_request_wire_commitment) != _canonical(
            verified_titan_request_wire_commitment
        ):
            raise ValueError("verified Titan request wire commitment changed after admission")
        calculation_lineage["titan_request_wire_commitment"] = dict(
            verified_titan_request_wire_commitment
        )
    case_attestation = case.case_attestation if case is not None else None
    if case_attestation is not None:
        # Preserve the full signed wire (including the detached signature) so
        # Titan can re-authenticate the exact case before issuing an advisor
        # verification receipt. Flat aliases make receipt/database predicates
        # explicit and are required to agree with the nested signed contract.
        calculation_lineage.update(
            {
                "valuation_case_attestation": case_attestation.model_dump(mode="json"),
                "valuation_case_attestation_content_hash": case_attestation.content_hash,
                "valuation_case_hash": case_attestation.case_hash,
                "decision_set_hash": case_attestation.decision_set_hash,
                "evidence_hash": case_attestation.evidence_hash,
                "valuation_case_evidence_hash": case_attestation.evidence_hash,
                "evidence_revision_id": case_attestation.evidence_revision_id,
            }
        )
    if timeline_projection_only:
        metadata = request.metadata if isinstance(request.metadata, Mapping) else {}
        calculation_lineage["timeline_projection"] = {
            "parent_valuation_id": metadata.get("valuation_timeline_parent_valuation_id"),
            "target_fiscal_year": request.current_year.year,
            "calculation_purpose": "current_lens_timeline_projection",
            "independent_release_authorized": False,
            "headline_review_receipt_applied": False,
            "release_policy": "projection_only_not_independently_releasable",
        }
    # Certification predicates belong to input lineage, not the priced DCF
    # result. Keeping them here seals the selected DCF mode and any conditional
    # jurisdiction regime without mutating the response payload after the
    # engine calculated it. The top-level response and immutable run therefore
    # remain byte-for-byte equivalent.
    calculation_lineage["dcf_input_mode"] = getattr(request, "dcf_input_mode", None)
    from src.api.schemas.method_eligibility import MethodEligibility
    from .range_provenance import sealed_range_provenance
    from .value_basis_admission import uses_accounting_basis_policy

    if uses_accounting_basis_policy(request):
        from src.api.schemas.financial_history import seal_financial_history

        calculation_lineage["financial_history"] = seal_financial_history(request)
    calculation_lineage["method_eligibility"] = MethodEligibility.model_validate(
        {
            "schema_version": "method-eligibility.v1",
            "policy_version": (
                "source-evidence-required.v1"
                if uses_accounting_basis_policy(request)
                else "legacy-evidence-admission.v1"
            ),
            "methods": {
                key: {
                    "eligible": getattr(result, "available", False),
                    "value_basis": getattr(result, "value_basis", None),
                    "reason": getattr(result, "unavailable_reason", None),
                }
                for key, result in valuation_results.items()
            },
            "equity_status": (financial_metrics or {}).get("equity_status", "available"),
            "resolved_weights": method_mix,
        }
    ).model_dump(mode="json")
    calculation_lineage["range_provenance"] = sealed_range_provenance(
        method_results=valuation_results,
        source_vintages=benchmark_snapshot_references,
        method_mix=method_mix,
    )
    if case is not None and case.forecast_evidence is not None:
        calculation_lineage["forecast_evidence"] = case.forecast_evidence.model_dump(mode="json")

    from src.utils.percentage_input_contract import percentage_input_provenance

    percentage_provenance = percentage_input_provenance(request.business_context or {})
    if percentage_provenance is not None:
        calculation_lineage["percentage_input_contract"] = percentage_provenance
    if property_yield_contract is not None:
        calculation_lineage["real_estate_yield_evidence"] = {
            "schema_version": property_yield_contract.schema_version,
            "contract_id": property_yield_contract.contract_id,
            "content_sha256": property_yield_contract.content_sha256,
            "company_id": property_yield_contract.company_id,
            "evidence_revision_id": property_yield_contract.evidence_revision_id,
            "country_code": property_yield_contract.country_code,
            "currency": property_yield_contract.currency,
            "valuation_date": property_yield_contract.valuation_date.isoformat(),
            "authority": "titan_signed_valuation_case_v2",
        }
    if request.country_code == "IE":
        business_context = (
            request.business_context if isinstance(request.business_context, Mapping) else {}
        )
        calculation_lineage["irish_tax_regime"] = business_context.get("irish_tax_regime")
    fiscal_effective_date = _fiscal_effective_date(request)
    valuation_lens_date = (
        property_yield_contract.valuation_date.isoformat()
        if property_yield_contract is not None
        else calculation_timestamp[:10]
    )
    method_results_payload = {
        str(key): _method_result_payload(value) for key, value in valuation_results.items()
    }
    projection_layers = {
        "contemporaneous_observation": valuation_range,
        "current_lens_restatements": _canonical(valuation_timeline),
        "base_forecasts_and_scenarios": _canonical(forward_value_cone),
    }
    qualifications = [
        flag.model_dump(mode="json") if isinstance(flag, BaseModel) else _canonical(flag)
        for flag in triage_flags
    ]
    weighted_payload_raw = _canonical(weighted_valuation)
    weighted_payload = (
        dict(weighted_payload_raw) if isinstance(weighted_payload_raw, Mapping) else None
    )
    public_audit_raw = _without_volatile_audit_fields(public_valuation_audit)
    public_audit_snapshot = (
        dict(public_audit_raw) if isinstance(public_audit_raw, Mapping) else None
    )
    economic_snapshot = _economic_snapshot_reference(request)
    economic_snapshot_status = (
        "used_for_dcf"
        if economic_snapshot is not None and safe_decimal_or_zero(dcf_weight) > 0
        else (
            "valuation_iq_modeled_public_dcf"
            if safe_decimal_or_zero(dcf_weight) > 0 and public_modeled_dcf_is_authorized(request)
            else "available_not_used" if economic_snapshot is not None else "not_supplied"
        )
    )
    run_payload: dict[str, object] = {
        "schema_version": RUN_SCHEMA_VERSION_V2,
        "integrity_version": RUN_INTEGRITY_VERSION_V2,
        "execution_id": execution_id,
        "valuation_id": request.valuation_id,
        "case_id": case.case_id if case is not None else request.valuation_id,
        "company_id": case.company_id if case is not None else None,
        "company_name": request.company_name,
        "country_code": request.country_code,
        "company_profile_snapshot": company_profile_snapshot,
        "company_snapshot": company_snapshot,
        "uploaded_data_snapshot": uploaded_data_snapshot,
        "uploaded_data_snapshot_status": uploaded_data_snapshot_status,
        "classification_resolution": classification_resolution,
        "benchmark_snapshot_references": benchmark_snapshot_references,
        "source_citations": source_citations,
        "normalization_adjustments": normalization_adjustments,
        "report_review_decisions": (
            []
            if timeline_projection_only
            else (
                [decision.model_dump(mode="json") for decision in case.report_review_decisions]
                if case is not None
                else []
            )
        ),
        "content_provenance": (
            case.content_provenance.model_dump(mode="json")
            if case is not None
            else ReportContentProvenanceSnapshot().model_dump(mode="json")
        ),
        "assurance": {
            **assurance_from_legacy_response_snapshot(
                response_snapshot,
                confidence_model_version=CONFIDENCE_MODEL_VERSION,
            ).model_dump(mode="json"),
            **_country_pack_assurance_fields(resolved_country_pack),
            **_method_certification_assurance_fields(
                {
                    "method_mix": method_mix,
                    "country_code": request.country_code,
                    "valuation_lens_date": valuation_lens_date,
                }
            ),
        },
        "country_pack_schema_version": resolved_country_pack.schema_version,
        "country_pack_version": resolved_country_pack.pack_version,
        "economic_snapshot": economic_snapshot,
        "economic_snapshot_status": economic_snapshot_status,
        "scenario_id": case.scenario_id if case is not None else "observed",
        "evidence_revision_id": (case.evidence_revision_id if case is not None else None),
        "calculation_timestamp": calculation_timestamp,
        "recording_timestamp": calculation_timestamp,
        "fiscal_effective_date": fiscal_effective_date,
        "valuation_lens_date": valuation_lens_date,
        "source_as_of": (
            property_yield_contract.valuation_date.isoformat()
            if property_yield_contract is not None
            else evidence_source_as_of(request, request.current_year.year)
        ),
        "currency": request.currency,
        "value_basis": (
            "enterprise_value"
            if equity_unavailable
            else "mixed" if enterprise_value_range is not None else "equity_value"
        ),
        "engine_version": engine_version,
        "policy_version": policy_version,
        "confidence_model_version": CONFIDENCE_MODEL_VERSION,
        "methodology_used": methodology_used,
        "input_hash": input_hash,
        "evidence_hash": evidence_hash,
        "accounting_evidence_bundle_hash": accounting_evidence_bundle_hash,
        "evidence_hash_source": evidence_hash_source,
        "benchmark_hash_source": benchmark_hash_source,
        "valuation_range": valuation_range,
        "enterprise_value_range": enterprise_value_range,
        "method_mix": method_mix,
        "method_results": method_results_payload,
        "weighted_valuation": weighted_payload,
        "methodology_weights": {
            "dcf": dcf_weight,
            "multiples": multiples_weight,
        },
        "financial_metrics": dict(financial_metrics or {}),
        "dcf_results": _canonical(dcf_results),
        "multiples_results": _canonical(multiples_results),
        "response_snapshot": valuation_response_snapshot(response_snapshot or {}),
        "benchmark_snapshot": benchmark_snapshot_payload,
        "calculation_lineage": calculation_lineage,
        "driver_ledger": dict(driver_ledger),
        "projection_layers": projection_layers,
        "qualifications": qualifications,
        "public_valuation_audit_snapshot": public_audit_snapshot,
    }
    return ValuationRunV2.model_validate(seal_valuation_run_payload(run_payload))


def _classification_resolution_for_run(
    *,
    request: CalculateRequest,
    case: object,
    company_profile_snapshot: Mapping[str, object],
) -> dict[str, object]:
    raw = getattr(case, "classification_resolution", None) if case is not None else None
    supplied = dict(raw) if isinstance(raw, Mapping) else {}
    nace = request.canonical_nace_code or request.nace_code
    resolution = {
        "requested_nace_code": request.nace_code,
        "canonical_nace_code": nace,
        "business_type_id": request.business_type_calibration.business_type_id,
        "business_type_label": company_profile_snapshot.get("business_type_label"),
        "resolution_level": supplied.get("resolution_level", "request_calibration"),
        "resolution_status": supplied.get(
            "resolution_status",
            "resolved" if nace else "manual_review_required",
        ),
        "confidence": supplied.get("confidence"),
        "mapping_version": supplied.get("mapping_version"),
        "taxonomy_version": supplied.get("taxonomy_version"),
        "reviewer_state": supplied.get("reviewer_state"),
    }
    declared_hash = supplied.get("mapping_hash")
    expected_hash = canonical_hash(resolution)
    if declared_hash is not None and str(declared_hash).lower() != expected_hash:
        raise ValueError(
            "classification_resolution mapping_hash does not match its canonical mapping"
        )
    resolution["mapping_hash"] = expected_hash
    return resolution


def _benchmark_snapshot_references_for_run(
    *,
    request: CalculateRequest,
    benchmark_contract: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    if not benchmark_contract:
        return []

    if benchmark_contract.get("contract_version") == "benchmark_resolution.v1":
        return _canonical_resolution_references_for_run(
            request=request,
            resolution_contract=benchmark_contract,
        )

    from src.services.reports.report_benchmark_contracts import (
        as_plain_mapping,
        normalize_benchmark_contract,
    )
    from src.services.reports.stateless_benchmark_policy import (
        _METHOD_BENCHMARK_METRICS,
        _required_benchmark_method_keys,
    )

    normalized = normalize_benchmark_contract(benchmark_contract)
    metrics = as_plain_mapping(benchmark_contract.get("metrics")) or {}
    required_alias_sets = [
        _METHOD_BENCHMARK_METRICS[key]
        for key in sorted(_required_benchmark_method_keys(request))
        if key in _METHOD_BENCHMARK_METRICS
    ]
    references: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for aliases in required_alias_sets:
        metric_name, metric_payload = _metric_contract_for_aliases(
            aliases=aliases,
            metrics=metrics,
            normalized=normalized,
        )
        benchmark_id = str(metric_payload.get("benchmark_id") or "").strip()
        if not benchmark_id:
            continue
        key = (metric_name, benchmark_id)
        if key in seen:
            continue
        seen.add(key)
        resolution_contract = metric_payload.get("resolution_contract")
        resolution_material = (
            dict(resolution_contract)
            if isinstance(resolution_contract, Mapping)
            else metric_payload
        )
        resolution_id = _first_text(
            resolution_material,
            "resolution_contract_id",
            "resolution_id",
            "contract_id",
            "snapshot_id",
        ) or _first_text(metric_payload, "resolution_contract_id", "resolution_id")
        declared_resolution_hash = _first_text(
            resolution_material,
            "resolution_contract_hash",
            "resolution_hash",
            "contract_hash",
            "snapshot_hash",
        ) or _first_text(metric_payload, "resolution_contract_hash", "resolution_hash")
        adjustments = metric_payload.get("adjustments")
        references.append(
            {
                "metric": metric_name,
                "benchmark_id": benchmark_id,
                "snapshot_hash": canonical_hash(resolution_material),
                "resolution_contract_id": resolution_id or benchmark_id,
                "resolution_contract_hash": declared_resolution_hash
                or canonical_hash(resolution_material),
                "dataset_version_id": metric_payload.get("dataset_version_id"),
                "source_dataset_version_id": metric_payload.get("source_dataset_version_id"),
                "resolution_level": metric_payload.get("resolution_level")
                or metric_payload.get("scope_stage"),
                "source_benchmark_id": metric_payload.get("source_benchmark_id") or benchmark_id,
                "borrowed_from_country": metric_payload.get("borrowed_from_country"),
                "borrowed_from_business_type": metric_payload.get("borrowed_from_business_type")
                or metric_payload.get("source_business_type_id"),
                "adjustments": list(adjustments) if isinstance(adjustments, list) else [],
                "evidence_window": metric_payload.get("evidence_window"),
                "confidence": metric_payload.get("confidence")
                or metric_payload.get("confidence_band"),
                "review_state": metric_payload.get("review_state"),
                "published_at": metric_payload.get("published_at"),
            }
        )
    return references


def _property_yield_benchmark_material(contract: object) -> dict[str, object]:
    """Project the governed cap-rate sample into the sealed benchmark graph."""

    sources = list(getattr(contract, "sources", ()) or ())
    yield_source = next(
        (
            source
            for source in sources
            if getattr(source, "source_kind", None) == "property_yield_snapshot"
        ),
        None,
    )
    return {
        "metric_name": "property_yield",
        "benchmark_id": getattr(contract, "contract_id"),
        "target_country_code": getattr(contract, "country_code"),
        "country_code": getattr(contract, "country_code"),
        "currency": getattr(contract, "currency"),
        "sample_size": getattr(contract, "sample_size"),
        "methodology": getattr(contract, "methodology"),
        "methodology_version": getattr(contract, "methodology_version"),
        "cap_rate_low": getattr(contract, "cap_rate_low"),
        "cap_rate_mid": getattr(contract, "cap_rate_mid"),
        "cap_rate_high": getattr(contract, "cap_rate_high"),
        "observed_at": getattr(contract, "yield_observed_on").isoformat(),
        "published_at": getattr(contract, "yield_published_on").isoformat(),
        "provider": getattr(yield_source, "provider", None),
        "source_id": getattr(yield_source, "source_id", None),
        "review_state": "approved",
        "evidence_window": {
            "freshness": "current",
            "evidence_as_of": getattr(contract, "yield_observed_on").isoformat(),
        },
        "resolution_contract_id": getattr(contract, "contract_id"),
        "resolution_contract_hash": getattr(contract, "content_sha256"),
    }


def _property_yield_benchmark_reference(contract: object) -> dict[str, object]:
    return {
        "metric": "property_yield",
        "benchmark_id": getattr(contract, "contract_id"),
        "snapshot_hash": getattr(contract, "content_sha256"),
        "resolution_contract_id": getattr(contract, "contract_id"),
        "resolution_contract_hash": getattr(contract, "content_sha256"),
        "dataset_version_id": getattr(contract, "methodology_version"),
        "source_dataset_version_id": getattr(contract, "methodology_version"),
        "resolution_level": "country_property_income_cohort",
        "source_benchmark_id": getattr(contract, "contract_id"),
        "borrowed_from_country": None,
        "borrowed_from_business_type": None,
        "adjustments": [],
        "evidence_window": {
            "freshness": "current",
            "evidence_as_of": getattr(contract, "yield_observed_on").isoformat(),
        },
        "confidence": "high",
        "review_state": "approved",
        "published_at": getattr(contract, "yield_published_on").isoformat(),
    }


def _canonical_resolution_references_for_run(
    *,
    request: CalculateRequest,
    resolution_contract: Mapping[str, object],
) -> list[dict[str, object]]:
    from src.services.reports.stateless_benchmark_policy import (
        _METHOD_BENCHMARK_METRICS,
        _required_benchmark_method_keys,
        _resolution_authorizes_metric,
    )

    dataset = resolution_contract.get("dataset_snapshot")
    dataset_mapping = dict(dataset) if isinstance(dataset, Mapping) else {}
    raw_resolutions = resolution_contract.get("resolutions")
    resolutions = (
        list(raw_resolutions)
        if isinstance(raw_resolutions, Sequence)
        and not isinstance(raw_resolutions, (str, bytes, bytearray))
        else []
    )
    required_aliases = {
        alias.lower()
        for method in _required_benchmark_method_keys(request)
        for alias in _METHOD_BENCHMARK_METRICS.get(method, ())
    }
    rows: list[dict[str, object]] = []
    for raw in resolutions:
        if not isinstance(raw, Mapping):
            continue
        metric_name = str(raw.get("metric_name") or "").strip().lower()
        if metric_name not in required_aliases:
            continue
        if not _resolution_authorizes_metric(dict(raw)):
            continue
        source_benchmark_id = _first_text(raw, "source_benchmark_id")
        if not source_benchmark_id:
            continue
        resolution_id = _first_text(raw, "resolution_id")
        resolution_hash = _first_text(raw, "resolution_hash")
        if not resolution_id or not resolution_hash:
            continue
        adjustments = raw.get("adjustments")
        rows.append(
            {
                "metric": metric_name,
                "benchmark_id": source_benchmark_id,
                "snapshot_hash": resolution_hash,
                "resolution_contract_id": resolution_id,
                "resolution_contract_hash": resolution_hash,
                "dataset_version_id": dataset_mapping.get("id")
                or dataset_mapping.get("version_number"),
                "source_dataset_version_id": raw.get("source_dataset_version_id"),
                "resolution_level": raw.get("resolution_level"),
                "source_benchmark_id": source_benchmark_id,
                "borrowed_from_country": raw.get("borrowed_from_country"),
                "borrowed_from_business_type": raw.get("borrowed_from_business_type"),
                "adjustments": list(adjustments) if isinstance(adjustments, list) else [],
                "evidence_window": raw.get("evidence_window"),
                "confidence": raw.get("confidence"),
                "review_state": raw.get("review_state"),
                "published_at": raw.get("published_at") or dataset_mapping.get("published_at"),
            }
        )
    return rows


def _metric_contract_for_aliases(
    *,
    aliases: Sequence[str],
    metrics: Mapping[str, object],
    normalized: Mapping[str, object],
) -> tuple[str, dict[str, object]]:
    alias_set = {alias.strip().lower() for alias in aliases}
    for raw_name, raw_payload in metrics.items():
        if str(raw_name).strip().lower() not in alias_set:
            continue
        if isinstance(raw_payload, Mapping):
            return aliases[0], dict(raw_payload)
    primary = str(normalized.get("primary_metric") or "").strip().lower()
    return aliases[0], dict(normalized) if primary in alias_set else {}


def _first_text(mapping: Mapping[str, object], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalized_registry_number(value: object) -> str:
    normalized = "".join(character for character in str(value or "").upper() if character.isalnum())
    if len(normalized) > 2 and normalized[:2].isalpha():
        normalized = normalized[2:]
    return normalized.lstrip("0") or normalized


def _source_citations_for_run(
    *,
    case: object,
    accounting_evidence: object,
    request: CalculateRequest,
    benchmark_contract: Mapping[str, object] | None,
    real_estate_yield_evidence_contract: object = None,
) -> list[dict[str, object]]:
    raw_citations = list(getattr(case, "source_citations", []) or []) if case is not None else []
    citations: list[dict[str, object]] = []
    for raw in raw_citations:
        if not isinstance(raw, Mapping):
            continue
        citation = dict(raw)
        citation.setdefault("source_kind", "report_source")
        citation.setdefault("citation_id", f"cite_{canonical_hash(citation)[:24]}")
        citations.append(citation)

    reported_facts = (
        iter_accounting_reported_facts(accounting_evidence)
        if accounting_evidence is not None
        else []
    )
    for fact in reported_facts:
        for source in getattr(fact, "source_refs", []) or []:
            citation = {
                "source_kind": source.source_kind,
                "source_id": source.source_id,
                "provider": source.provider,
                "document_hash": source.document_hash,
                "locator": source.locator,
                "observed_at": (
                    source.observed_at.isoformat() if source.observed_at is not None else None
                ),
                "use": f"accounting_fact:{getattr(fact, 'fact_id', '')}",
            }
            citation["citation_id"] = f"cite_{canonical_hash(citation)[:24]}"
            citations.append(citation)
    citations.extend(
        _benchmark_citations_for_run(
            request=request,
            benchmark_contract=benchmark_contract,
        )
    )
    citations.extend(_property_yield_citations_for_run(real_estate_yield_evidence_contract))
    deduplicated: dict[str, dict[str, object]] = {}
    for citation in citations:
        deduplicated[str(citation["citation_id"])] = citation
    return list(deduplicated.values())


_PROPERTY_YIELD_CITATION_USE = {
    "property_title": "priced_property_title",
    "property_noi": "priced_property_noi",
    "property_occupancy": "priced_property_occupancy",
    "property_yield_snapshot": "priced_benchmark_metric:property_yield",
    "property_debt": "priced_property_debt",
    "property_cash": "priced_property_cash",
    "property_nwc": "priced_property_nwc",
    "property_nav_appraisal": "priced_property_nav_appraisal",
}


def _property_yield_citations_for_run(contract: object) -> list[dict[str, object]]:
    if contract is None:
        return []
    sources = sorted(
        list(getattr(contract, "sources", ()) or ()),
        key=lambda source: (
            str(getattr(source, "source_kind", "")),
            str(getattr(source, "source_id", "")),
        ),
    )
    citations: list[dict[str, object]] = []
    for source in sources:
        source_kind = str(getattr(source, "source_kind", ""))
        citation = {
            "source_kind": source_kind,
            "title": getattr(source, "evidence_summary", None),
            "source_id": getattr(source, "source_id", None),
            "provider": getattr(source, "provider", None),
            "url": getattr(source, "url", None),
            "document_hash": getattr(source, "document_hash", None),
            "locator": getattr(source, "locator", None),
            "observed_at": getattr(source, "observed_on").isoformat(),
            "published_at": (
                getattr(source, "published_on").isoformat()
                if getattr(source, "published_on", None) is not None
                else None
            ),
            "use": _PROPERTY_YIELD_CITATION_USE.get(source_kind, "priced_property_evidence"),
        }
        citation["citation_id"] = f"cite_{canonical_hash(citation)[:24]}"
        citations.append(citation)
    return citations


def _benchmark_citations_for_run(
    *,
    request: CalculateRequest,
    benchmark_contract: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    if not benchmark_contract:
        return []
    from src.services.reports.report_benchmark_contracts import as_plain_mapping
    from src.services.reports.stateless_benchmark_policy import (
        _METHOD_BENCHMARK_METRICS,
        _required_benchmark_method_keys,
    )

    if benchmark_contract.get("contract_version") == "benchmark_resolution.v1":
        return _canonical_resolution_citations_for_run(
            request=request,
            resolution_contract=benchmark_contract,
        )

    metrics = as_plain_mapping(benchmark_contract.get("metrics")) or {}
    primary = str(benchmark_contract.get("primary_metric") or "").strip().lower()
    materials: list[Mapping[str, object]] = []
    for method in sorted(_required_benchmark_method_keys(request)):
        aliases = _METHOD_BENCHMARK_METRICS.get(method)
        if not aliases:
            continue
        alias_set = {alias.lower() for alias in aliases}
        matched = False
        for name, raw in metrics.items():
            if str(name).strip().lower() in alias_set and isinstance(raw, Mapping):
                materials.append(raw)
                matched = True
        if not matched and primary in alias_set:
            materials.append(benchmark_contract)

    citations: list[dict[str, object]] = []
    for material in materials:
        raw_citations = material.get("source_citations") or material.get("citations") or []
        if not isinstance(raw_citations, Sequence) or isinstance(
            raw_citations, (str, bytes, bytearray)
        ):
            continue
        for raw in raw_citations:
            if not isinstance(raw, Mapping):
                continue
            citation = dict(raw)
            citation.setdefault("source_kind", "benchmark_evidence")
            citation.setdefault("use", "priced_benchmark_metric")
            citation.setdefault("citation_id", f"cite_{canonical_hash(citation)[:24]}")
            citations.append(citation)
    return citations


def _canonical_resolution_citations_for_run(
    *,
    request: CalculateRequest,
    resolution_contract: Mapping[str, object],
) -> list[dict[str, object]]:
    from src.services.reports.stateless_benchmark_policy import (
        _METHOD_BENCHMARK_METRICS,
        _required_benchmark_method_keys,
        _resolution_authorizes_metric,
    )

    aliases = {
        alias.lower()
        for method in _required_benchmark_method_keys(request)
        for alias in _METHOD_BENCHMARK_METRICS.get(method, ())
    }
    raw_resolutions = resolution_contract.get("resolutions")
    if not isinstance(raw_resolutions, Sequence) or isinstance(
        raw_resolutions, (str, bytes, bytearray)
    ):
        return []
    rows: list[dict[str, object]] = []
    for resolution in raw_resolutions:
        if not isinstance(resolution, Mapping):
            continue
        metric = str(resolution.get("metric_name") or "").strip().lower()
        if metric not in aliases:
            continue
        if not _resolution_authorizes_metric(dict(resolution)):
            continue
        raw_citations = resolution.get("citations")
        if not isinstance(raw_citations, Sequence) or isinstance(
            raw_citations, (str, bytes, bytearray)
        ):
            continue
        for raw in raw_citations:
            if not isinstance(raw, Mapping):
                continue
            citation = {
                "citation_id": raw.get("citation_id"),
                "source_kind": str(
                    raw.get("source_kind") or raw.get("evidence_class") or "benchmark_evidence"
                ),
                "title": raw.get("label"),
                "url": raw.get("url"),
                "observed_at": raw.get("observed_at"),
                "published_at": raw.get("published_at"),
                "use": raw.get("role") or f"priced_benchmark_metric:{metric}",
            }
            citation["citation_id"] = citation.get("citation_id") or (
                f"cite_{canonical_hash(citation)[:24]}"
            )
            rows.append(citation)
    return rows


def _normalization_adjustments_for_run(
    request: CalculateRequest,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for adjustment in request.normalizations:
        raw = adjustment.model_dump(mode="json")
        rows.append(
            {
                "adjustment_id": raw.get("id") or f"normalization_{canonical_hash(raw)[:24]}",
                "field": raw.get("field"),
                "label": raw.get("label"),
                "original_value": raw.get("original_value"),
                "adjusted_value": raw.get("adjusted_value"),
                "adjustment_amount": raw.get("adjustment_amount"),
                "reason": raw.get("reason"),
                "source": raw.get("source"),
                "status": raw.get("status"),
                "fiscal_year": raw.get("fiscal_year"),
                "evidence_id": raw.get("evidence_id"),
                "approved_by": raw.get("approved_by"),
                "reviewed_at": raw.get("reviewed_at"),
                "rule_version": raw.get("rule_version"),
            }
        )
    return rows


def _fiscal_effective_date(request: CalculateRequest) -> str | None:
    case = request.valuation_case
    accounting_evidence = priced_accounting_evidence(case)
    if accounting_evidence is not None:
        if accounting_evidence.period_end:
            return accounting_evidence.period_end
    fiscal_inputs = request.fiscal_inputs
    if isinstance(fiscal_inputs, Mapping):
        reference_date = fiscal_inputs.get("reference_date")
        if reference_date:
            return str(reference_date)
    # The current annual fact is the measurement basis when no more precise
    # evidence period end is available. This is explicit rather than silently
    # substituting the calculation date.
    return f"{request.current_year.year}-12-31"


def _method_result_payload(value: object) -> object:
    """Serialize one method with an explicit EV/equity basis."""
    canonical = _canonical(value)
    if isinstance(canonical, Mapping):
        return {"value_basis": "equity_value", **canonical}
    return canonical


def _method_mix(
    *,
    weighted_valuation: object,
    methodology_used: str,
    dcf_weight: Decimal,
    multiples_weight: Decimal,
) -> list[dict[str, object]]:
    if isinstance(weighted_valuation, BaseModel):
        raw_contributions = getattr(weighted_valuation, "contributions", None)
        weighted_value_basis = str(
            getattr(weighted_valuation, "value_basis", None) or "equity_value"
        )
        if isinstance(raw_contributions, Sequence):
            rows = [
                {
                    "method_key": str(getattr(row, "method_key", "unknown")),
                    "weight": Decimal(str(getattr(row, "weight", 0))),
                    "eligible": True,
                    "value_basis": str(getattr(row, "value_basis", None) or weighted_value_basis),
                }
                for row in raw_contributions
                if Decimal(str(getattr(row, "weight", 0))) > 0
            ]
            if rows:
                return rows

    rows = [
        {
            "method_key": "dcf",
            "weight": dcf_weight,
            "eligible": dcf_weight > 0,
            "value_basis": "equity_value",
        },
        {
            "method_key": "market_approach",
            "weight": multiples_weight,
            "eligible": multiples_weight > 0,
            "value_basis": "equity_value",
        },
    ]
    if dcf_weight == 0 and multiples_weight == 0:
        rows.append(
            {
                "method_key": methodology_used.strip().lower(),
                "weight": Decimal("1"),
                "eligible": True,
                "value_basis": "equity_value",
            }
        )
    return rows
