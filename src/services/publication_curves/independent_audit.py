"""Independent completeness and arithmetic audit for Workstream D v9 curves.

This boundary deliberately does not trust a campaign's own hashes as proof of
calculation correctness.  It revalidates the adapter's curve, canonical-period
and rejection artifacts, reconstructs every calculation input, resolves the
frozen contract population, and re-invokes the pure ValuationIQ page executor.
The stored plan, complete page chain and final receipt must match that second
execution byte-for-byte at their canonical JSON boundary.

There is no database, network, provider or publication client in this module.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from pydantic import ValidationError

from .batch import execute_campaign_page
from .campaign_io import (
    CurveInputRecord,
    PublicCurveCampaignIOError,
    _calculation_input_fingerprint,
    _contract_ids_for_company,
    canonical_json_bytes,
    iter_curve_input_manifests,
    load_frozen_multiple_artifact,
    sha256_prefixed,
)
from .contracts import MAX_PUBLIC_CURVE_PERIODS, PublicCurveCampaignPlanV1

AUDIT_KIND = "offline_v9_valiq_independent_audit_receipt_v1"
ADAPTER_KIND = "offline_financial_period_v2_adapter_receipt_v1"
CURVE_MANIFEST_KIND = "offline_v9_curve_input_manifest_v1"
BUNDLE_MANIFEST_KIND = "offline_v9_official_period_bundle_manifest_v1"
REJECTION_MANIFEST_KIND = "offline_financial_period_v2_rejection_manifest_v1"
PERIOD_BUNDLE_KIND = "offline_official_financial_period_bundle_v9"
MAX_ARTIFACT_BYTES = 512 * 1024 * 1024

_SHA = re.compile(r"^sha256:[0-9a-f]{64}$")
_RAW_SHA = re.compile(r"^[0-9a-f]{64}$")
_PAGE = re.compile(r"^page-[0-9]{5}\.json$")


class IndependentPublicCurveAuditError(ValueError):
    """A sealed campaign cannot pass the independent v9 audit."""


@dataclass(frozen=True, slots=True)
class IndependentPublicCurveAuditInputs:
    adapter_output_dirs: tuple[Path, ...]
    frozen_multiple_artifact_path: Path
    campaign_plan_path: Path | None = None
    campaign_receipt_path: Path | None = None


@dataclass(frozen=True, slots=True)
class _AdapterSet:
    receipt_sha256: str
    curve_manifest_sha256: str
    curve_content_root_sha256: str
    accepted_company_content_root_sha256: str
    bundle_manifest_sha256: str
    rejection_manifest_sha256: str
    curve_manifest_path: Path
    bundles_by_company_key: Mapping[str, Mapping[str, Any]]
    rejection_count: int
    rejection_counts: Mapping[str, int]


def _object(path: Path, *, field: str) -> dict[str, Any]:
    target = path.resolve(strict=True)
    if target.is_symlink() or not target.is_file():
        raise IndependentPublicCurveAuditError(f"{field} is missing or symlinked")
    size = target.stat().st_size
    if not 0 < size <= MAX_ARTIFACT_BYTES:
        raise IndependentPublicCurveAuditError(f"{field} size is outside its bound")
    try:
        value = json.loads(target.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndependentPublicCurveAuditError(f"{field} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise IndependentPublicCurveAuditError(f"{field} must be an object")
    return value


def _sealed(value: Mapping[str, Any], *, hash_field: str, field: str) -> dict[str, Any]:
    material = dict(value)
    claimed = material.pop(hash_field, None)
    if not isinstance(claimed, str) or _SHA.fullmatch(claimed) is None:
        raise IndependentPublicCurveAuditError(f"{field} lacks {hash_field}")
    if sha256_prefixed(canonical_json_bytes(material)) != claimed:
        raise IndependentPublicCurveAuditError(f"{field} content hash drifted")
    return dict(value)


def _raw_sha(value: Any, *, field: str) -> str:
    text = str(value or "")
    if _RAW_SHA.fullmatch(text) is None:
        raise IndependentPublicCurveAuditError(f"{field} is not a raw SHA-256 digest")
    return text


def _sha(value: Any, *, field: str) -> str:
    text = str(value or "")
    if _SHA.fullmatch(text) is None:
        raise IndependentPublicCurveAuditError(f"{field} is not a SHA-256 fingerprint")
    return text


def _physical(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return f"sha256:{digest.hexdigest()}", size


def _manifest_records(  # noqa: C901 -- one pass validates every shard boundary
    manifest_path: Path,
    *,
    kind: str,
    hash_field: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = _sealed(
        _object(manifest_path, field=kind),
        hash_field="manifest_sha256",
        field=kind,
    )
    if (
        manifest.get("contract_kind") != kind
        or manifest.get("schema_version") != 1
        or manifest.get("status") != "complete"
        or manifest.get("publication_enabled") is not False
        or manifest.get("database_writes") != 0
        or manifest.get("network_requests") != 0
    ):
        raise IndependentPublicCurveAuditError(f"{kind} crossed its dark boundary")
    count = manifest.get("record_count")
    files = manifest.get("files")
    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or count < 0
        or not isinstance(files, list)
        or (count == 0 and files)
        or (count > 0 and not files)
    ):
        raise IndependentPublicCurveAuditError(f"{kind} file/count census drifted")
    records: list[dict[str, Any]] = []
    root = manifest_path.resolve().parent
    previous_key: str | None = None
    for descriptor in files:
        expected_descriptor = {
            "path",
            "record_count",
            "logical_sha256",
            "logical_byte_size",
            "physical_sha256",
            "physical_byte_size",
            "first_company_key",
            "last_company_key",
        }
        if not isinstance(descriptor, Mapping) or set(descriptor) != expected_descriptor:
            raise IndependentPublicCurveAuditError(f"{kind} descriptor shape drifted")
        name = str(descriptor.get("path") or "")
        path = (root / name).resolve()
        if path.parent != root or path.is_symlink() or not path.is_file():
            raise IndependentPublicCurveAuditError(f"{kind} shard path is unsafe")
        physical_sha, physical_size = _physical(path)
        if physical_sha != descriptor.get("physical_sha256") or physical_size != descriptor.get(
            "physical_byte_size"
        ):
            raise IndependentPublicCurveAuditError(f"{kind} physical shard drifted")
        logical_digest = hashlib.sha256()
        logical_size = 0
        shard: list[dict[str, Any]] = []
        try:
            with gzip.open(path, "rb") as handle:
                for line in handle:
                    logical_digest.update(line)
                    logical_size += len(line)
                    if not line.endswith(b"\n"):
                        raise IndependentPublicCurveAuditError(f"{kind} has an unterminated row")
                    value = json.loads(line)
                    if not isinstance(value, dict) or canonical_json_bytes(value) + b"\n" != line:
                        raise IndependentPublicCurveAuditError(f"{kind} row is not canonical JSON")
                    shard.append(value)
        except (OSError, EOFError, json.JSONDecodeError) as exc:
            raise IndependentPublicCurveAuditError(f"{kind} gzip shard is corrupt") from exc
        if (
            len(shard) != descriptor.get("record_count")
            or logical_size != descriptor.get("logical_byte_size")
            or f"sha256:{logical_digest.hexdigest()}" != descriptor.get("logical_sha256")
        ):
            raise IndependentPublicCurveAuditError(f"{kind} logical shard drifted")
        keys = [
            str(
                item.get("company_key")
                or (
                    item.get("company_input", {}).get("company_key")
                    if isinstance(item.get("company_input"), Mapping)
                    else ""
                )
            )
            for item in shard
        ]
        if not keys and kind == BUNDLE_MANIFEST_KIND:
            keys = [
                str(item.get("country_code")) + ":" + str(item.get("registry_number"))
                for item in shard
            ]
        if shard:
            # Bundle records do not carry the opaque key.  Its descriptor does.
            first = str(descriptor.get("first_company_key"))
            last = str(descriptor.get("last_company_key"))
            if kind != BUNDLE_MANIFEST_KIND and (keys[0] != first or keys[-1] != last):
                raise IndependentPublicCurveAuditError(f"{kind} key range drifted")
            if (
                previous_key is not None
                and first <= previous_key
                and kind != REJECTION_MANIFEST_KIND
            ):
                raise IndependentPublicCurveAuditError(f"{kind} shard order drifted")
            previous_key = last
        records.extend(shard)
    if len(records) != count:
        raise IndependentPublicCurveAuditError(f"{kind} record count drifted")
    if kind != REJECTION_MANIFEST_KIND:
        content = [str(record.get(hash_field)) for record in records]
        if sha256_prefixed(canonical_json_bytes(content)) != manifest.get("content_root_sha256"):
            raise IndependentPublicCurveAuditError(f"{kind} content root drifted")
    return manifest, records


def _canonical_decimal(value: Any, *, field: str) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise IndependentPublicCurveAuditError(f"{field} is not numeric") from exc
    if not number.is_finite():
        raise IndependentPublicCurveAuditError(f"{field} is non-finite")
    text = format(number.normalize(), "f")
    return "0" if number == 0 else text


def _verify_fact(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise IndependentPublicCurveAuditError("official fact is invalid")
    fact = _sealed(value, hash_field="fact_sha256", field="official fact")
    if set(fact) != {
        "name",
        "value",
        "provenance",
        "source_rubric",
        "derivation_formula_sha256",
        "derivation_input_sha256s",
        "fact_sha256",
    }:
        raise IndependentPublicCurveAuditError("official fact shape drifted")
    if fact.get("value") != _canonical_decimal(fact.get("value"), field="official fact"):
        raise IndependentPublicCurveAuditError("official fact decimal is not canonical")
    return fact


def _verify_period(value: Any, *, country: str, registry: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise IndependentPublicCurveAuditError("official period is invalid")
    period = _sealed(value, hash_field="period_sha256", field="official period")
    expected = {
        "contract_kind",
        "schema_version",
        "country",
        "registry_number",
        "period_start",
        "period_end",
        "statement_scope",
        "source_document_version",
        "currency",
        "visibility",
        "source_authority",
        "source_record_id",
        "source_reference_url",
        "source_document_sha256",
        "raw_record_sha256",
        "filed_at",
        "deposited_at",
        "source_document_updated_at",
        "source_observed_at",
        "correction_precedence",
        "supersedes_document_versions",
        "revenue_source",
        "facts",
        "period_sha256",
    }
    if (
        set(period) != expected
        or period.get("contract_kind") != "official_financial_period_v2"
        or period.get("schema_version") != 2
        or period.get("country") != country
        or period.get("registry_number") != registry
        or period.get("visibility") not in {"public", "public_simplified"}
    ):
        raise IndependentPublicCurveAuditError("official period shape or identity drifted")
    _sha(period.get("source_document_sha256"), field="period source document")
    facts = period.get("facts")
    if not isinstance(facts, list) or not facts:
        raise IndependentPublicCurveAuditError("official period has no facts")
    verified = [_verify_fact(item) for item in facts]
    if [str(item["name"]) for item in verified] != sorted(str(item["name"]) for item in verified):
        raise IndependentPublicCurveAuditError("official period facts are not ordered")
    return period


def _period_projection(period: Mapping[str, Any]) -> dict[str, Any]:
    facts = {str(item["name"]): item for item in period["facts"]}

    def value(name: str) -> str | None:
        item = facts.get(name)
        return str(item["value"]) if item is not None else None

    def bridge(name: str) -> str | None:
        result = value(name)
        return result if result is not None and Decimal(result) >= 0 else None

    revenue_source = period.get("revenue_source")
    revenue_kind = (
        "TURNOVER"
        if revenue_source in {"turnover", "operating_revenue", "official_revenue"}
        else "GROSS_MARGIN" if revenue_source == "gross_margin" else "UNKNOWN"
    )
    ebitda = facts.get("ebitda")
    return {
        "period_start": period["period_start"],
        "period_end": period["period_end"],
        "filed_at": str(period["filed_at"])[:10],
        "statement_scope": {
            "entity": "COMPANY",
            "consolidated": "CONSOLIDATED",
        }.get(str(period["statement_scope"])),
        "source_document_version": period["source_document_version"],
        "source_record_id": period["source_record_id"],
        "source_sha256": str(period["source_document_sha256"]).removeprefix("sha256:"),
        "currency": period["currency"],
        "revenue": value("revenue"),
        "revenue_source": revenue_kind,
        "gross_margin": value("gross_margin"),
        "reported_ebitda": (
            str(ebitda["value"])
            if ebitda is not None and ebitda.get("provenance") == "reported"
            else None
        ),
        "ebit": value("ebit"),
        "depreciation_amortization": value("depreciation_amortization"),
        "net_income": value("net_income"),
        "book_equity": value("book_equity"),
        "interest_bearing_debt": bridge("interest_bearing_debt"),
        "lease_liabilities": bridge("leases"),
        "cash": bridge("cash"),
        "is_official": True,
        "is_forecast": False,
    }


def _adapter_set(directory: Path) -> _AdapterSet:
    root = directory.resolve(strict=True)
    if root.is_symlink() or not root.is_dir():
        raise IndependentPublicCurveAuditError("adapter output directory is unsafe")
    receipt = _sealed(
        _object(root / "adapter-receipt.json", field="adapter receipt"),
        hash_field="receipt_sha256",
        field="adapter receipt",
    )
    if (
        receipt.get("contract_kind") != ADAPTER_KIND
        or receipt.get("schema_version") != 1
        or receipt.get("status") != "complete"
        or receipt.get("database_reads") != 0
        or receipt.get("database_writes") != 0
        or receipt.get("network_requests") != 0
        or receipt.get("valuationiq_execution") != 0
        or receipt.get("publication_enabled") is not False
    ):
        raise IndependentPublicCurveAuditError("adapter receipt crossed its dark boundary")
    curve, _ = _manifest_records(
        root / "curve-input-manifest.json",
        kind=CURVE_MANIFEST_KIND,
        hash_field="record_sha256",
    )
    bundle, bundle_records = _manifest_records(
        root / "official-period-bundle-manifest.json",
        kind=BUNDLE_MANIFEST_KIND,
        hash_field="bundle_sha256",
    )
    rejection, rejection_records = _manifest_records(
        root / "rejection-manifest.json",
        kind=REJECTION_MANIFEST_KIND,
        hash_field="record_sha256",
    )
    if (
        receipt.get("curve_input_manifest_sha256") != curve.get("manifest_sha256")
        or receipt.get("official_period_bundle_manifest_sha256") != bundle.get("manifest_sha256")
        or receipt.get("rejection_manifest_sha256") != rejection.get("manifest_sha256")
        or bundle.get("curve_input_manifest_sha256") != curve.get("manifest_sha256")
        or curve.get("accepted_company_content_root_sha256")
        != bundle.get("accepted_company_content_root_sha256")
        or curve.get("record_count") != bundle.get("record_count")
    ):
        raise IndependentPublicCurveAuditError("adapter output bindings diverged")
    bundles: dict[str, Mapping[str, Any]] = {}
    official_period_count = 0
    for raw in bundle_records:
        sealed_bundle = _sealed(raw, hash_field="bundle_sha256", field="period bundle")
        if (
            sealed_bundle.get("contract_kind") != PERIOD_BUNDLE_KIND
            or sealed_bundle.get("schema_version") != 9
        ):
            raise IndependentPublicCurveAuditError("period bundle version drifted")
        country = str(sealed_bundle.get("country_code") or "")
        registry = str(sealed_bundle.get("registry_number") or "")
        periods = sealed_bundle.get("official_periods")
        if not isinstance(periods, list) or not 2 <= len(periods) <= MAX_PUBLIC_CURVE_PERIODS:
            raise IndependentPublicCurveAuditError("period bundle count is outside 2..20")
        verified = [_verify_period(item, country=country, registry=registry) for item in periods]
        keys = [
            (
                str(item["period_end"]),
                str(item["statement_scope"]),
                str(item["source_document_version"]),
            )
            for item in verified
        ]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise IndependentPublicCurveAuditError("period bundle is not unique/natural ordered")
        # The exact opaque key is recovered below from the curve record; keep
        # the natural identity here to make accidental cross-company joins fail.
        natural = f"{country}:{registry}"
        if natural in bundles:
            raise IndependentPublicCurveAuditError("period bundle identity is duplicated")
        bundles[natural] = sealed_bundle
        official_period_count += len(verified)
    if official_period_count != bundle.get("official_period_count"):
        raise IndependentPublicCurveAuditError("official-period census drifted")
    observed_rejections: Counter[str] = Counter()
    for raw in rejection_records:
        record = _sealed(raw, hash_field="record_sha256", field="adapter rejection")
        reasons = record.get("reason_codes")
        if not isinstance(reasons, list) or not reasons:
            raise IndependentPublicCurveAuditError("adapter rejection lacks reasons")
        observed_rejections.update(str(reason) for reason in reasons)
    expected_rejections = dict(sorted(observed_rejections.items()))
    counts = receipt.get("counts")
    if (
        rejection.get("rejection_counts") != expected_rejections
        or curve.get("rejection_counts") != expected_rejections
        or receipt.get("rejection_counts") != expected_rejections
        or counts
        != {
            "accepted_companies": curve.get("record_count"),
            "accepted_periods": official_period_count,
            "rejected_periods": len(rejection_records),
        }
    ):
        raise IndependentPublicCurveAuditError("adapter receipt census drifted")
    return _AdapterSet(
        receipt_sha256=str(receipt["receipt_sha256"]),
        curve_manifest_sha256=str(curve["manifest_sha256"]),
        curve_content_root_sha256=str(curve["content_root_sha256"]),
        accepted_company_content_root_sha256=str(curve["accepted_company_content_root_sha256"]),
        bundle_manifest_sha256=str(bundle["manifest_sha256"]),
        rejection_manifest_sha256=str(rejection["manifest_sha256"]),
        curve_manifest_path=root / "curve-input-manifest.json",
        bundles_by_company_key=bundles,
        rejection_count=len(rejection_records),
        rejection_counts=expected_rejections,
    )


def _records_and_bundles(
    adapter_sets: Sequence[_AdapterSet],
) -> tuple[list[CurveInputRecord], dict[str, Mapping[str, Any]]]:
    paths = tuple(item.curve_manifest_path for item in adapter_sets)
    if all(_object(path, field="curve manifest").get("record_count") == 0 for path in paths):
        return [], {}
    try:
        records = list(iter_curve_input_manifests(paths))
    except PublicCurveCampaignIOError as exc:
        raise IndependentPublicCurveAuditError(str(exc)) from exc
    bundles_by_natural = {
        natural: bundle
        for adapter in adapter_sets
        for natural, bundle in adapter.bundles_by_company_key.items()
    }
    if len(bundles_by_natural) != sum(
        len(adapter.bundles_by_company_key) for adapter in adapter_sets
    ):
        raise IndependentPublicCurveAuditError("adapter bundle identities overlap")
    bundles_by_key: dict[str, Mapping[str, Any]] = {}
    shared_by_adapter: dict[str, list[dict[str, str]]] = {
        adapter.curve_manifest_sha256: [] for adapter in adapter_sets
    }
    adapter_by_manifest = {adapter.curve_manifest_sha256: adapter for adapter in adapter_sets}
    for record in records:
        natural = f"{record.company.country_code}:{record.company.normalized_registry_number}"
        bundle = bundles_by_natural.get(natural)
        if bundle is None:
            raise IndependentPublicCurveAuditError("curve input lacks its canonical period bundle")
        raw_periods = bundle["official_periods"]
        projections = [_period_projection(period) for period in raw_periods]
        if record.company.model_dump(mode="json")["periods"] != projections:
            raise IndependentPublicCurveAuditError(
                "curve calculation facts differ from OfficialFinancialPeriodV2"
            )
        expected_bindings = [
            {
                "official_period_key": [
                    period["country"],
                    period["registry_number"],
                    period["period_end"],
                    period["statement_scope"],
                    period["source_document_version"],
                ],
                "official_period_sha256": period["period_sha256"],
                "source_document_sha256": period["source_document_sha256"],
            }
            for period in raw_periods
        ]
        if list(record.official_period_bindings) != expected_bindings:
            raise IndependentPublicCurveAuditError("curve input period bindings drifted")
        if record.company.company_key in bundles_by_key:
            raise IndependentPublicCurveAuditError("curve company key is duplicated")
        bundles_by_key[record.company.company_key] = bundle
        adapter = adapter_by_manifest.get(record.source_manifest_sha256)
        if adapter is None:
            raise IndependentPublicCurveAuditError("curve record leaves adapter manifest set")
        shared_by_adapter[adapter.curve_manifest_sha256].append(
            {
                "company_key": record.company.company_key,
                "curve_record_sha256": record.record_sha256,
                "official_period_bundle_sha256": str(bundle["bundle_sha256"]),
            }
        )
    if set(bundles_by_natural) != {
        f"{record.company.country_code}:{record.company.normalized_registry_number}"
        for record in records
    }:
        raise IndependentPublicCurveAuditError("curve/bundle accepted inventories diverged")
    for adapter in adapter_sets:
        observed = sha256_prefixed(
            canonical_json_bytes(shared_by_adapter[adapter.curve_manifest_sha256])
        )
        if observed != adapter.accepted_company_content_root_sha256:
            raise IndependentPublicCurveAuditError("adapter accepted-company root drifted")
    return records, bundles_by_key


def _audit_campaign(  # noqa: C901 -- completeness and arithmetic are one atomic gate
    *,
    inputs: IndependentPublicCurveAuditInputs,
    adapter_sets: Sequence[_AdapterSet],
    records: Sequence[CurveInputRecord],
) -> dict[str, Any]:
    if inputs.campaign_plan_path is None or inputs.campaign_receipt_path is None:
        raise IndependentPublicCurveAuditError("accepted curve inputs require plan and receipt")
    frozen = load_frozen_multiple_artifact(inputs.frozen_multiple_artifact_path)
    plan_envelope = _sealed(
        _object(inputs.campaign_plan_path, field="campaign plan"),
        hash_field="plan_sha256",
        field="campaign plan",
    )
    try:
        plan = PublicCurveCampaignPlanV1(**plan_envelope["plan"])
    except (KeyError, TypeError, ValidationError) as exc:
        raise IndependentPublicCurveAuditError("campaign plan is invalid") from exc
    if (
        plan_envelope.get("frozen_multiple_artifact_sha256") != frozen.artifact_sha256
        or plan.snapshot != frozen.snapshot
        or plan_envelope.get("publication_enabled") is not False
        or plan_envelope.get("rollout_state") != "sealed_dark"
    ):
        raise IndependentPublicCurveAuditError("campaign plan leaves its frozen dark run")
    companies = {record.company.company_key: record.company for record in records}
    bindings = {record.company.company_key: record.official_period_bindings for record in records}
    record_hashes = {record.company.company_key: record.record_sha256 for record in records}
    expected_jobs: list[dict[str, Any]] = []
    expected_fingerprints: dict[str, str] = {}
    for record in records:
        contract_ids = _contract_ids_for_company(
            record.company,
            frozen.contracts_by_id,
            campaign_request_id=plan.campaign_request_id,
            valuation_as_of=plan.created_at.date(),
        )
        if not contract_ids:
            continue
        expected_jobs.append(
            {"company_key": record.company.company_key, "contract_ids": list(contract_ids)}
        )
        expected_fingerprints[record.company.company_key] = _calculation_input_fingerprint(
            company=record.company,
            contracts=tuple(frozen.contracts_by_id[item] for item in contract_ids),
            model_version=plan.model_version,
            valuation_as_of=plan.created_at.date(),
        )
    if plan.model_dump(mode="json")["jobs"] != expected_jobs:
        raise IndependentPublicCurveAuditError(
            "campaign jobs are not the exact ordered eligible input inventory"
        )
    job_keys = [job.company_key for job in plan.jobs]
    expected_manifest_sha = [item.curve_manifest_sha256 for item in adapter_sets]
    expected_content_roots = [item.curve_content_root_sha256 for item in adapter_sets]
    expected_shared_roots = [item.accepted_company_content_root_sha256 for item in adapter_sets]
    if (
        plan_envelope.get("curve_input_manifest_sha256s") != expected_manifest_sha
        or plan_envelope.get("curve_input_content_root_sha256s") != expected_content_roots
        or plan_envelope.get("curve_input_accepted_company_content_root_sha256s")
        != expected_shared_roots
        or plan_envelope.get("input_record_sha256_by_company_key")
        != {key: record_hashes[key] for key in sorted(job_keys)}
        or plan_envelope.get("official_period_binding_sha256_by_company_key")
        != {key: sha256_prefixed(canonical_json_bytes(bindings[key])) for key in sorted(job_keys)}
        or plan_envelope.get("expected_input_fingerprint_by_company_key")
        != {key: expected_fingerprints[key] for key in job_keys}
    ):
        raise IndependentPublicCurveAuditError("campaign plan input roots or bindings drifted")
    receipt = _sealed(
        _object(inputs.campaign_receipt_path, field="campaign receipt"),
        hash_field="receipt_sha256",
        field="campaign receipt",
    )
    expected_receipt_keys = {
        "contract_kind",
        "schema_version",
        "campaign_request_id",
        "plan_sha256",
        "curve_input_manifest_sha256s",
        "curve_input_content_root_sha256s",
        "curve_input_accepted_company_content_root_sha256s",
        "frozen_multiple_artifact_sha256",
        "job_count",
        "success_count",
        "blocked_count",
        "page_count",
        "page_chain_head_sha256",
        "pages",
        "engine_sha256",
        "runtime_sha256",
        "package_lock_sha256",
        "database_reads",
        "database_writes",
        "network_requests",
        "publication_enabled",
        "rollout_state",
        "receipt_sha256",
    }
    if (
        set(receipt) != expected_receipt_keys
        or receipt.get("contract_kind") != "offline_v9_public_curve_campaign_receipt_v1"
        or receipt.get("schema_version") != 1
        or receipt.get("campaign_request_id") != plan.campaign_request_id
        or receipt.get("plan_sha256") != plan_envelope.get("plan_sha256")
        or receipt.get("frozen_multiple_artifact_sha256") != frozen.artifact_sha256
        or receipt.get("job_count") != len(plan.jobs)
        or receipt.get("engine_sha256") != plan.engine_sha256
        or receipt.get("runtime_sha256") != plan.runtime_sha256
        or receipt.get("package_lock_sha256") != plan.package_lock_sha256
        or any(
            receipt.get(field) != 0
            for field in ("database_reads", "database_writes", "network_requests")
        )
        or receipt.get("publication_enabled") is not False
        or receipt.get("rollout_state") != "sealed_dark"
    ):
        raise IndependentPublicCurveAuditError("campaign receipt bindings drifted")
    for field in ("engine_sha256", "runtime_sha256", "package_lock_sha256"):
        _raw_sha(receipt.get(field), field=field)
    for field in (
        "curve_input_manifest_sha256s",
        "curve_input_content_root_sha256s",
        "curve_input_accepted_company_content_root_sha256s",
    ):
        if receipt.get(field) != plan_envelope.get(field):
            raise IndependentPublicCurveAuditError("campaign receipt input roots drifted")
    pages = receipt.get("pages")
    if not isinstance(pages, list) or len(pages) != receipt.get("page_count"):
        raise IndependentPublicCurveAuditError("campaign page receipt census drifted")
    page_root = inputs.campaign_receipt_path.resolve().parent
    declared_names = [str(item.get("path") or "") for item in pages if isinstance(item, Mapping)]
    if (
        len(declared_names) != len(pages)
        or any(_PAGE.fullmatch(name) is None for name in declared_names)
        or set(declared_names) != {path.name for path in page_root.glob("page-*.json")}
    ):
        raise IndependentPublicCurveAuditError("campaign page file inventory is incomplete")
    success = 0
    blocked = 0
    previous: str | None = None
    ordered_result_material: list[dict[str, Any]] = []
    for page_number, descriptor in enumerate(pages, start=1):
        if not isinstance(descriptor, Mapping) or set(descriptor) != {
            "path",
            "page_number",
            "page_sha256",
            "result_count",
        }:
            raise IndependentPublicCurveAuditError("campaign page descriptor drifted")
        expected_page = execute_campaign_page(
            plan=plan,
            page_number=page_number,
            companies_by_key=companies,
            contracts_by_id=frozen.contracts_by_id,
            previous_page_sha256=previous,
        )
        stored = _object(page_root / str(descriptor["path"]), field="campaign page")
        expected_value = expected_page.model_dump(mode="json")
        if stored != expected_value:
            raise IndependentPublicCurveAuditError(
                "stored page differs from independent ValuationIQ recomputation"
            )
        if (
            descriptor.get("page_number") != page_number
            or descriptor.get("page_sha256") != expected_page.page_sha256
            or descriptor.get("result_count") != len(expected_page.results)
        ):
            raise IndependentPublicCurveAuditError("campaign page descriptor differs from page")
        previous = expected_page.page_sha256
        success += len(expected_page.result_sha256s)
        blocked += len(expected_page.blocked_fingerprints)
        for offset, result in enumerate(expected_page.results):
            payload = result.model_dump(mode="json")
            ordered_result_material.append(
                {
                    "job_index": expected_page.first_job_index + offset,
                    "company_key": payload["company_key"],
                    "result_kind": payload["schema_version"],
                    "input_fingerprint": payload["input_fingerprint"],
                    "result_sha256": payload.get("result_sha256"),
                }
            )
    if (
        success != receipt.get("success_count")
        or blocked != receipt.get("blocked_count")
        or success + blocked != len(plan.jobs)
        or previous != receipt.get("page_chain_head_sha256")
        or len(ordered_result_material) != len(plan.jobs)
        or [item["company_key"] for item in ordered_result_material] != job_keys
    ):
        raise IndependentPublicCurveAuditError(
            "campaign results are a prefix, reorder, omission or duplicate of the plan"
        )
    return {
        "campaign_request_id": plan.campaign_request_id,
        "plan_sha256": plan_envelope["plan_sha256"],
        "campaign_receipt_sha256": receipt["receipt_sha256"],
        "job_count": len(plan.jobs),
        "success_count": success,
        "blocked_count": blocked,
        "page_count": len(pages),
        "page_chain_head_sha256": previous,
        "engine_sha256": plan.engine_sha256,
        "runtime_sha256": plan.runtime_sha256,
        "package_lock_sha256": plan.package_lock_sha256,
        "ordered_job_result_root_sha256": sha256_prefixed(
            canonical_json_bytes(ordered_result_material)
        ),
    }


def build_independent_public_curve_audit_receipt(
    inputs: IndependentPublicCurveAuditInputs,
) -> dict[str, Any]:
    """Return a sealed audit receipt after a complete local second execution."""

    if not inputs.adapter_output_dirs:
        raise IndependentPublicCurveAuditError("at least one adapter output is required")
    try:
        frozen = load_frozen_multiple_artifact(inputs.frozen_multiple_artifact_path)
    except PublicCurveCampaignIOError as exc:
        raise IndependentPublicCurveAuditError(str(exc)) from exc
    adapter_sets = [_adapter_set(path) for path in inputs.adapter_output_dirs]
    records, _ = _records_and_bundles(adapter_sets)
    rejected = sum(item.rejection_count for item in adapter_sets)
    if not records:
        if rejected <= 0:
            raise IndependentPublicCurveAuditError(
                "zero-job semantics require a non-empty rejection-only adapter result"
            )
        if inputs.campaign_plan_path is not None or inputs.campaign_receipt_path is not None:
            raise IndependentPublicCurveAuditError(
                "rejection-only adapter output must not claim a ValuationIQ campaign"
            )
        campaign: dict[str, Any] | None = None
        mode = "rejection_only"
    else:
        campaign = _audit_campaign(
            inputs=inputs,
            adapter_sets=adapter_sets,
            records=records,
        )
        mode = "independently_recalculated"
    rejection_counts: Counter[str] = Counter()
    for adapter in adapter_sets:
        rejection_counts.update(adapter.rejection_counts)
    material = {
        "contract_kind": AUDIT_KIND,
        "schema_version": 1,
        "status": "complete",
        "audit_mode": mode,
        "adapter_receipt_sha256s": [item.receipt_sha256 for item in adapter_sets],
        "curve_input_manifest_sha256s": [item.curve_manifest_sha256 for item in adapter_sets],
        "curve_input_content_root_sha256s": [
            item.curve_content_root_sha256 for item in adapter_sets
        ],
        "curve_input_accepted_company_content_root_sha256s": [
            item.accepted_company_content_root_sha256 for item in adapter_sets
        ],
        "official_period_bundle_manifest_sha256s": [
            item.bundle_manifest_sha256 for item in adapter_sets
        ],
        "rejection_manifest_sha256s": [item.rejection_manifest_sha256 for item in adapter_sets],
        "frozen_multiple_artifact_sha256": frozen.artifact_sha256,
        "accepted_company_count": len(records),
        "rejected_period_count": rejected,
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "campaign": campaign,
        "public_checkpoint_limit": MAX_PUBLIC_CURVE_PERIODS,
        "database_reads": 0,
        "database_writes": 0,
        "network_requests": 0,
        "publication_enabled": False,
        "rollout_state": "sealed_dark",
    }
    return {
        **material,
        "audit_receipt_sha256": sha256_prefixed(canonical_json_bytes(material)),
    }


def write_independent_public_curve_audit_receipt(
    *, inputs: IndependentPublicCurveAuditInputs, output_path: Path
) -> dict[str, Any]:
    receipt = build_independent_public_curve_audit_receipt(inputs)
    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(receipt) + b"\n"
    if target.exists():
        if target.is_symlink() or target.read_bytes() != payload:
            raise IndependentPublicCurveAuditError("stored independent audit receipt drifted")
        return receipt
    temporary = target.with_name(f".{target.name}.tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    return receipt


__all__ = [
    "AUDIT_KIND",
    "IndependentPublicCurveAuditError",
    "IndependentPublicCurveAuditInputs",
    "build_independent_public_curve_audit_receipt",
    "write_independent_public_curve_audit_receipt",
]
