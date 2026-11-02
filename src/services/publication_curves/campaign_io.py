"""Sealed, bounded local I/O for Workstream D v9 public-curve campaigns.

The calculation engine is pure.  This module is the deliberately small file
boundary around it: it validates one frozen Delphi/Athena artifact and one or
more hash-bound company-input manifests, writes immutable plans of at most
10,000 jobs, and commits result pages of at most 250 jobs atomically.

There is no database, HTTP, Railway, Athena, Delphi, or publication client in
this module.  All hashes use the exact canonical JSON representation consumed
by the v9 regrade assembler.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from pydantic import TypeAdapter, ValidationError

from .batch import execute_campaign_page
from .contracts import (
    CampaignJobV1,
    CurveCompanyInputV1,
    FrozenMultipleSnapshotV1,
    MultipleContractV9,
    PublicCurveCampaignPlanV1,
)
from .runner import PublicCurveBlockedV1, ValuationGrade, run_public_curve

MAX_INPUT_SHARD_ROWS = 50_000
MAX_CAMPAIGN_JOBS = 10_000
MAX_DURABLE_RESULTS_PER_PAGE = 250
DEFAULT_MINIMUM_FREE_BYTES = 80 * 1024**3

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_RAW_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CAMPAIGN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,199}$")
_INPUT_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,511}\.ndjson\.gz$")
_CONTRACT_ADAPTER = TypeAdapter(MultipleContractV9)


class PublicCurveCampaignIOError(ValueError):
    """A local campaign input, plan, page, or resume binding is invalid."""


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PublicCurveCampaignIOError("campaign material is not canonical JSON") from exc


def sha256_prefixed(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _object(path: Path, *, field: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicCurveCampaignIOError(f"{field} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise PublicCurveCampaignIOError(f"{field} must be a JSON object")
    return value


def _sealed_object(value: Mapping[str, Any], *, hash_field: str, field: str) -> dict[str, Any]:
    material = dict(value)
    claimed = material.pop(hash_field, None)
    if not isinstance(claimed, str) or _SHA256.fullmatch(claimed) is None:
        raise PublicCurveCampaignIOError(f"{field} lacks {hash_field}")
    if sha256_prefixed(canonical_json_bytes(material)) != claimed:
        raise PublicCurveCampaignIOError(f"{field} hash drifted")
    return dict(value)


def _safe_child(root: Path, raw: Any) -> Path:
    if not isinstance(raw, str) or _INPUT_FILE.fullmatch(raw) is None:
        raise PublicCurveCampaignIOError("curve-input shard path is invalid")
    candidate = (root / raw).resolve()
    resolved_root = root.resolve()
    if candidate == resolved_root or resolved_root not in candidate.parents:
        raise PublicCurveCampaignIOError("curve-input shard escapes its manifest directory")
    if candidate.is_symlink() or not candidate.is_file():
        raise PublicCurveCampaignIOError("curve-input shard is missing or symlinked")
    return candidate


def _physical(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return f"sha256:{digest.hexdigest()}", size


def _iter_gzip_ndjson(
    path: Path,
    *,
    expected_count: int,
    expected_logical_sha256: str,
    expected_logical_size: int,
) -> Iterator[dict[str, Any]]:
    digest = hashlib.sha256()
    size = 0
    count = 0
    try:
        with gzip.open(path, "rb") as handle:
            for raw_line in handle:
                digest.update(raw_line)
                size += len(raw_line)
                if not raw_line.endswith(b"\n"):
                    raise PublicCurveCampaignIOError("curve-input NDJSON row is unterminated")
                try:
                    value = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    raise PublicCurveCampaignIOError(
                        "curve-input NDJSON row is invalid JSON"
                    ) from exc
                if not isinstance(value, dict) or canonical_json_bytes(value) + b"\n" != raw_line:
                    raise PublicCurveCampaignIOError("curve-input row is not canonical JSON")
                count += 1
                if count > expected_count:
                    raise PublicCurveCampaignIOError("curve-input shard count exceeded descriptor")
                yield value
    except (OSError, EOFError) as exc:
        raise PublicCurveCampaignIOError("curve-input gzip shard is corrupt") from exc
    if (
        count != expected_count
        or size != expected_logical_size
        or f"sha256:{digest.hexdigest()}" != expected_logical_sha256
    ):
        raise PublicCurveCampaignIOError("curve-input logical descriptor drifted")


@dataclass(frozen=True, slots=True)
class FrozenMultipleArtifact:
    artifact_sha256: str
    snapshot: FrozenMultipleSnapshotV1
    contracts_by_id: Mapping[str, MultipleContractV9]


def load_frozen_multiple_artifact(path: Path) -> FrozenMultipleArtifact:
    artifact = _sealed_object(
        _object(path, field="frozen multiple artifact"),
        hash_field="artifact_sha256",
        field="frozen multiple artifact",
    )
    if (
        artifact.get("contract_kind") != "offline_v9_frozen_multiple_contracts"
        or artifact.get("schema_version") != 1
        or artifact.get("publication_enabled") is not False
        or artifact.get("database_reads") != 0
        or artifact.get("database_writes") != 0
        or artifact.get("network_requests") != 0
    ):
        raise PublicCurveCampaignIOError("frozen multiple artifact crossed its dark boundary")
    try:
        snapshot = FrozenMultipleSnapshotV1(**artifact["frozen_multiple_snapshot"])
    except (KeyError, TypeError, ValidationError) as exc:
        raise PublicCurveCampaignIOError("frozen multiple snapshot is invalid") from exc
    contracts: dict[str, MultipleContractV9] = {}
    for collection_name in (
        "model_prior_contracts",
        "broad_median_prior_contracts",
        "benchmark_contracts",
    ):
        collection = artifact.get(collection_name)
        if not isinstance(collection, list):
            raise PublicCurveCampaignIOError(f"{collection_name} is not an array")
        for raw in collection:
            try:
                contract = _CONTRACT_ADAPTER.validate_python(raw)
            except ValidationError as exc:
                raise PublicCurveCampaignIOError("frozen multiple contract is invalid") from exc
            if contract.contract_id in contracts:
                raise PublicCurveCampaignIOError("frozen multiple contract ID is duplicated")
            observed_hash = hashlib.sha256(canonical_json_bytes(raw)).hexdigest()
            if snapshot.contract_sha256_by_id.get(contract.contract_id) != observed_hash:
                raise PublicCurveCampaignIOError("frozen multiple contract hash drifted")
            contracts[contract.contract_id] = contract
    if set(contracts) != set(snapshot.contract_sha256_by_id):
        raise PublicCurveCampaignIOError("frozen multiple contract inventory is incomplete")
    return FrozenMultipleArtifact(
        artifact_sha256=str(artifact["artifact_sha256"]),
        snapshot=snapshot,
        contracts_by_id=contracts,
    )


@dataclass(frozen=True, slots=True)
class CurveInputRecord:
    company: CurveCompanyInputV1
    official_period_bindings: tuple[dict[str, Any], ...]
    record_sha256: str
    source_manifest_sha256: str = ""
    source_content_root_sha256: str = ""
    source_accepted_company_content_root_sha256: str = ""


def _calculation_input_fingerprint(
    *,
    company: CurveCompanyInputV1,
    contracts: Sequence[MultipleContractV9],
    model_version: str,
    valuation_as_of: date,
) -> str:
    """Reproduce the pure runner's exact immutable input fingerprint."""

    material = {
        "model_version": model_version,
        "valuation_as_of": valuation_as_of.isoformat(),
        "company": company.model_dump(mode="json"),
        "contracts": [
            contract.model_dump(mode="json")
            for contract in sorted(contracts, key=lambda item: item.contract_id)
        ],
    }
    return hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def _curve_input_record(value: Mapping[str, Any]) -> CurveInputRecord:
    expected = {
        "contract_kind",
        "schema_version",
        "company_input",
        "official_period_bindings",
        "record_sha256",
    }
    if (
        set(value) != expected
        or value.get("contract_kind") != "offline_v9_curve_company_input_v1"
        or value.get("schema_version") != 1
    ):
        raise PublicCurveCampaignIOError("curve company-input record shape drifted")
    material = dict(value)
    claimed = material.pop("record_sha256")
    if not isinstance(claimed, str) or sha256_prefixed(canonical_json_bytes(material)) != claimed:
        raise PublicCurveCampaignIOError("curve company-input record hash drifted")
    try:
        company = CurveCompanyInputV1(**value["company_input"])
    except (KeyError, TypeError, ValidationError) as exc:
        raise PublicCurveCampaignIOError("CurveCompanyInputV1 is invalid") from exc
    raw_bindings = value.get("official_period_bindings")
    if not isinstance(raw_bindings, list) or len(raw_bindings) != len(company.periods):
        raise PublicCurveCampaignIOError("official period binding count drifted")
    bindings: list[dict[str, Any]] = []
    for period, raw in zip(company.periods, raw_bindings, strict=True):
        if not isinstance(raw, dict) or set(raw) != {
            "official_period_key",
            "official_period_sha256",
            "source_document_sha256",
        }:
            raise PublicCurveCampaignIOError("official period binding shape drifted")
        key = raw.get("official_period_key")
        source_hash = raw.get("source_document_sha256")
        if (
            not isinstance(key, list)
            or len(key) != 5
            or key[2:]
            != [
                period.period_end.isoformat(),
                "entity" if period.statement_scope.value == "COMPANY" else "consolidated",
                period.source_document_version,
            ]
            or source_hash != f"sha256:{period.source_sha256}"
            or _SHA256.fullmatch(str(raw.get("official_period_sha256") or "")) is None
        ):
            raise PublicCurveCampaignIOError("official period binding differs from calculation")
        bindings.append(dict(raw))
    return CurveInputRecord(
        company=company,
        official_period_bindings=tuple(bindings),
        record_sha256=str(claimed),
    )


def iter_curve_input_manifests(paths: Sequence[Path]) -> Iterator[CurveInputRecord]:
    seen_company_keys: set[str] = set()
    expected_previous: str | None = None
    observed_root_material: list[str] = []
    for manifest_path in paths:
        manifest = _sealed_object(
            _object(manifest_path, field="curve-input manifest"),
            hash_field="manifest_sha256",
            field="curve-input manifest",
        )
        if (
            manifest.get("contract_kind") != "offline_v9_curve_input_manifest_v1"
            or manifest.get("schema_version") != 1
            or manifest.get("status") != "complete"
            or manifest.get("publication_enabled") is not False
            or manifest.get("database_writes") != 0
            or manifest.get("network_requests") != 0
            or manifest.get("previous_manifest_sha256") != expected_previous
        ):
            raise PublicCurveCampaignIOError("curve-input manifest chain drifted")
        expected_manifest_keys = {
            "contract_kind",
            "schema_version",
            "status",
            "previous_manifest_sha256",
            "record_count",
            "files",
            "content_root_sha256",
            "accepted_company_content_root_sha256",
            "source_manifest_sha256s",
            "rejection_counts",
            "publication_enabled",
            "database_writes",
            "network_requests",
            "manifest_sha256",
        }
        if set(manifest) != expected_manifest_keys:
            raise PublicCurveCampaignIOError("curve-input manifest shape drifted")
        if (
            _SHA256.fullmatch(str(manifest.get("accepted_company_content_root_sha256") or ""))
            is None
        ):
            raise PublicCurveCampaignIOError("curve-input accepted-company content root is invalid")
        source_manifests = manifest.get("source_manifest_sha256s")
        if (
            not isinstance(source_manifests, list)
            or not source_manifests
            or len(source_manifests) != len(set(source_manifests))
            or any(_SHA256.fullmatch(str(value)) is None for value in source_manifests)
        ):
            raise PublicCurveCampaignIOError("curve-input source manifest inventory is invalid")
        if not isinstance(manifest.get("rejection_counts"), dict):
            raise PublicCurveCampaignIOError("curve-input rejection census is invalid")
        files = manifest.get("files")
        record_count = manifest.get("record_count")
        if (
            isinstance(record_count, bool)
            or not isinstance(record_count, int)
            or record_count < 0
            or not isinstance(files, list)
            or (record_count == 0 and files)
            or (record_count > 0 and not files)
        ):
            raise PublicCurveCampaignIOError("curve-input manifest file/count census is invalid")
        if record_count == 0:
            empty_root = sha256_prefixed(canonical_json_bytes([]))
            if (
                manifest.get("content_root_sha256") != empty_root
                or manifest.get("accepted_company_content_root_sha256") != empty_root
            ):
                raise PublicCurveCampaignIOError("empty curve-input content roots drifted")
        total = 0
        manifest_record_hashes: list[str] = []
        previous_company_key: str | None = None
        root = manifest_path.resolve().parent
        for descriptor in files:
            expected_descriptor_keys = {
                "path",
                "record_count",
                "logical_sha256",
                "logical_byte_size",
                "physical_sha256",
                "physical_byte_size",
                "first_company_key",
                "last_company_key",
            }
            if not isinstance(descriptor, dict) or set(descriptor) != expected_descriptor_keys:
                raise PublicCurveCampaignIOError("curve-input descriptor is invalid")
            count = descriptor.get("record_count")
            if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 50_000:
                raise PublicCurveCampaignIOError("curve-input descriptor count is invalid")
            path = _safe_child(root, descriptor.get("path"))
            first_key = descriptor.get("first_company_key")
            last_key = descriptor.get("last_company_key")
            if (
                not isinstance(first_key, str)
                or not isinstance(last_key, str)
                or not first_key
                or first_key > last_key
            ):
                raise PublicCurveCampaignIOError("curve-input descriptor key range is invalid")
            physical_sha, physical_size = _physical(path)
            if physical_sha != descriptor.get("physical_sha256") or physical_size != descriptor.get(
                "physical_byte_size"
            ):
                raise PublicCurveCampaignIOError("curve-input physical descriptor drifted")
            observed_first: str | None = None
            observed_last: str | None = None
            for raw in _iter_gzip_ndjson(
                path,
                expected_count=count,
                expected_logical_sha256=str(descriptor.get("logical_sha256") or ""),
                expected_logical_size=int(descriptor.get("logical_byte_size") or -1),
            ):
                record = _curve_input_record(raw)
                if record.company.company_key in seen_company_keys:
                    raise PublicCurveCampaignIOError("curve-input company key is duplicated")
                if (
                    previous_company_key is not None
                    and record.company.company_key <= previous_company_key
                ):
                    raise PublicCurveCampaignIOError("curve-input company keys are not ordered")
                seen_company_keys.add(record.company.company_key)
                previous_company_key = record.company.company_key
                observed_first = observed_first or record.company.company_key
                observed_last = record.company.company_key
                observed_root_material.append(record.record_sha256)
                manifest_record_hashes.append(record.record_sha256)
                total += 1
                yield CurveInputRecord(
                    company=record.company,
                    official_period_bindings=record.official_period_bindings,
                    record_sha256=record.record_sha256,
                    source_manifest_sha256=str(manifest["manifest_sha256"]),
                    source_content_root_sha256=str(manifest["content_root_sha256"]),
                    source_accepted_company_content_root_sha256=str(
                        manifest["accepted_company_content_root_sha256"]
                    ),
                )
            if observed_first != first_key or observed_last != last_key:
                raise PublicCurveCampaignIOError("curve-input descriptor key range drifted")
        if total != manifest.get("record_count"):
            raise PublicCurveCampaignIOError("curve-input manifest count drifted")
        if sha256_prefixed(canonical_json_bytes(manifest_record_hashes)) != manifest.get(
            "content_root_sha256"
        ):
            raise PublicCurveCampaignIOError("curve-input content root drifted")
        expected_previous = str(manifest["manifest_sha256"])
    if not observed_root_material:
        raise PublicCurveCampaignIOError("curve-input manifest set is empty")


def _contract_ids_for_company(
    company: CurveCompanyInputV1,
    contracts: Mapping[str, MultipleContractV9],
    *,
    campaign_request_id: str,
    valuation_as_of: date,
) -> tuple[str, ...]:
    compatible: list[MultipleContractV9] = []
    for contract in contracts.values():
        version = contract.contract_version
        if version == "BroadMedianPriorContractV1":
            if company.mapping_status.value == "UNAVAILABLE":
                compatible.append(contract)
        else:
            if (
                company.mapping_status.value == "REVIEWED"
                and company.business_type_id == contract.business_type_id
                and company.mapping_version == contract.mapping_version
                and (
                    version != "BenchmarkContractV2"
                    or company.country_code == contract.country_code
                )
            ):
                compatible.append(contract)
    if not compatible:
        return ()
    # Population priority applies only after the pure resolver proves that the
    # population can form its claimed curve.  In particular, an exact observed
    # contract whose metric is ineligible must not suppress an eligible modeled
    # T2-M curve.  Observed inputs are selected only when they really resolve to
    # T3-O; populations are never mixed.
    populations = [
        [item for item in compatible if item.contract_version == version]
        for version in (
            "BenchmarkContractV2",
            "ModelPriorContractV1",
            "BroadMedianPriorContractV1",
        )
    ]
    populations = [
        sorted(population, key=lambda item: item.contract_id)
        for population in populations
        if population
    ]
    for population in populations:
        resolved = run_public_curve(
            campaign_request_id=campaign_request_id,
            company=company,
            contracts=tuple(population),
            valuation_as_of=valuation_as_of,
        )
        if isinstance(resolved, PublicCurveBlockedV1):
            continue
        if population[0].contract_version != "BenchmarkContractV2" or (
            resolved.valuation_grade == ValuationGrade.T3_O
        ):
            return tuple(item.contract_id for item in population)
    # Preserve a durable blocked result when no compatible population can
    # resolve.  This is reporting evidence, not a preference over a successful
    # lower population (the loop above already tried all of them).
    return tuple(item.contract_id for item in populations[0])


def _write_atomic_json(path: Path, value: Any) -> None:
    payload = canonical_json_bytes(value) + b"\n"
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _runtime_hash() -> str:
    material = {
        "implementation": "cpython",
        "python": sys.version,
        "platform": sys.platform,
    }
    return hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def _package_lock_hash(root: Path) -> str:
    candidates = (root / "poetry.lock", root / "requirements.txt", root / "pyproject.toml")
    material: list[dict[str, str]] = []
    for path in candidates:
        if path.is_file():
            material.append(
                {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            )
    if not material:
        raise PublicCurveCampaignIOError("ValuationIQ package-lock inputs are missing")
    return hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def _engine_hash(package_root: Path) -> str:
    package = package_root / "src" / "services" / "publication_curves"
    material: list[dict[str, str]] = []
    for path in sorted(package.glob("*.py")):
        material.append(
            {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
    if not material:
        raise PublicCurveCampaignIOError("publication-curves engine tree is empty")
    return hashlib.sha256(canonical_json_bytes(material)).hexdigest()


@dataclass(frozen=True, slots=True)
class BuiltCampaign:
    plan: PublicCurveCampaignPlanV1
    companies_by_key: Mapping[str, CurveCompanyInputV1]
    bindings_by_key: Mapping[str, tuple[dict[str, Any], ...]]
    input_record_sha256_by_key: Mapping[str, str]
    curve_input_manifest_sha256s: tuple[str, ...]
    curve_input_content_root_sha256s: tuple[str, ...]
    curve_input_accepted_company_content_root_sha256s: tuple[str, ...]
    frozen_multiple_artifact_sha256: str
    contracts_by_id: Mapping[str, MultipleContractV9]


def build_campaign(
    *,
    campaign_request_id: str,
    curve_input_manifests: Sequence[Path],
    frozen_multiple_artifact: Path,
    package_root: Path,
    created_at: datetime | None = None,
) -> BuiltCampaign:
    if _CAMPAIGN.fullmatch(campaign_request_id) is None:
        raise PublicCurveCampaignIOError("campaign_request_id is invalid")
    frozen = load_frozen_multiple_artifact(frozen_multiple_artifact)
    resolved_created_at = created_at or datetime.now(timezone.utc).replace(microsecond=0)
    companies: dict[str, CurveCompanyInputV1] = {}
    bindings: dict[str, tuple[dict[str, Any], ...]] = {}
    record_hashes: dict[str, str] = {}
    input_manifests: list[str] = []
    input_roots: list[str] = []
    accepted_roots: list[str] = []
    jobs: list[CampaignJobV1] = []
    for record in iter_curve_input_manifests(curve_input_manifests):
        contract_ids = _contract_ids_for_company(
            record.company,
            frozen.contracts_by_id,
            campaign_request_id=campaign_request_id,
            valuation_as_of=resolved_created_at.date(),
        )
        if not contract_ids:
            continue
        if len(contract_ids) > 4:
            raise PublicCurveCampaignIOError("company resolves to more than four metric contracts")
        key = record.company.company_key
        companies[key] = record.company
        bindings[key] = record.official_period_bindings
        record_hashes[key] = record.record_sha256
        if record.source_manifest_sha256 not in input_manifests:
            input_manifests.append(record.source_manifest_sha256)
            input_roots.append(record.source_content_root_sha256)
            accepted_roots.append(record.source_accepted_company_content_root_sha256)
        jobs.append(CampaignJobV1(company_key=key, contract_ids=contract_ids))
        if len(jobs) > MAX_CAMPAIGN_JOBS:
            raise PublicCurveCampaignIOError("one immutable campaign cannot exceed 10K jobs")
    if not jobs:
        raise PublicCurveCampaignIOError("no curve input matches the frozen contract inventory")
    plan = PublicCurveCampaignPlanV1(
        campaign_request_id=campaign_request_id,
        created_at=resolved_created_at,
        snapshot=frozen.snapshot,
        engine_sha256=_engine_hash(package_root),
        runtime_sha256=_runtime_hash(),
        package_lock_sha256=_package_lock_hash(package_root),
        jobs=tuple(jobs),
        durable_results_per_page=MAX_DURABLE_RESULTS_PER_PAGE,
    )
    return BuiltCampaign(
        plan=plan,
        companies_by_key=companies,
        bindings_by_key=bindings,
        input_record_sha256_by_key=record_hashes,
        curve_input_manifest_sha256s=tuple(input_manifests),
        curve_input_content_root_sha256s=tuple(input_roots),
        curve_input_accepted_company_content_root_sha256s=tuple(accepted_roots),
        frozen_multiple_artifact_sha256=frozen.artifact_sha256,
        contracts_by_id=frozen.contracts_by_id,
    )


def execute_campaign_to_directory(
    *,
    campaign: BuiltCampaign,
    output_dir: Path,
    resume: bool = False,
    minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
) -> dict[str, Any]:
    target = output_dir.resolve()
    if target.exists() and not resume:
        raise PublicCurveCampaignIOError("output exists; explicit resume is required")
    if not target.exists() and resume:
        raise PublicCurveCampaignIOError("resume output does not exist")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.mkdir()
    if target.is_symlink() or not target.is_dir():
        raise PublicCurveCampaignIOError("campaign output is not a regular directory")
    plan_value = campaign.plan.model_dump(mode="json")
    plan_material = {
        "contract_kind": "offline_v9_public_curve_campaign_plan_envelope_v1",
        "schema_version": 1,
        "plan": plan_value,
        "curve_input_manifest_sha256s": list(campaign.curve_input_manifest_sha256s),
        "curve_input_content_root_sha256s": list(campaign.curve_input_content_root_sha256s),
        "curve_input_accepted_company_content_root_sha256s": list(
            campaign.curve_input_accepted_company_content_root_sha256s
        ),
        "input_record_sha256_by_company_key": dict(
            sorted(campaign.input_record_sha256_by_key.items())
        ),
        "official_period_binding_sha256_by_company_key": {
            key: sha256_prefixed(canonical_json_bytes(campaign.bindings_by_key[key]))
            for key in sorted(campaign.bindings_by_key)
        },
        "expected_input_fingerprint_by_company_key": {
            job.company_key: _calculation_input_fingerprint(
                company=campaign.companies_by_key[job.company_key],
                contracts=tuple(campaign.contracts_by_id[value] for value in job.contract_ids),
                model_version=campaign.plan.model_version,
                valuation_as_of=campaign.plan.created_at.date(),
            )
            for job in campaign.plan.jobs
        },
        "frozen_multiple_artifact_sha256": campaign.frozen_multiple_artifact_sha256,
        "publication_enabled": False,
        "rollout_state": "sealed_dark",
    }
    plan_sha = sha256_prefixed(canonical_json_bytes(plan_material))
    plan_envelope = {**plan_material, "plan_sha256": plan_sha}
    plan_path = target / "plan.json"
    if plan_path.exists():
        if _object(plan_path, field="stored plan") != plan_envelope:
            raise PublicCurveCampaignIOError("stored campaign plan drifted")
    else:
        _write_atomic_json(plan_path, plan_envelope)
    total_pages = (
        len(campaign.plan.jobs) + campaign.plan.durable_results_per_page - 1
    ) // campaign.plan.durable_results_per_page
    previous: str | None = None
    pages: list[dict[str, Any]] = []
    success = 0
    blocked = 0
    for page_number in range(1, total_pages + 1):
        if (
            minimum_free_bytes
            and os.statvfs(target).f_bavail * os.statvfs(target).f_frsize < minimum_free_bytes
        ):
            raise PublicCurveCampaignIOError("local free space is below the configured reserve")
        page_path = target / f"page-{page_number:05d}.json"
        calculated = execute_campaign_page(
            plan=campaign.plan,
            page_number=page_number,
            companies_by_key=campaign.companies_by_key,
            contracts_by_id=campaign.contracts_by_id,
            previous_page_sha256=previous,
        )
        # Persist the complete internal result envelope.  The offline Delphi
        # regrader validates every resolved method, contract ID, weight, source
        # record and document hash before it constructs the smaller public
        # seal.  Projecting through ``to_public_seal_v9`` here would discard
        # precisely that audit lineage and make the page unverifiable.
        page_value = calculated.model_dump(mode="json")
        if page_path.exists():
            if _object(page_path, field="stored page") != page_value:
                raise PublicCurveCampaignIOError("stored campaign page drifted")
        else:
            _write_atomic_json(page_path, page_value)
        previous = calculated.page_sha256
        pages.append(
            {
                "path": page_path.name,
                "page_number": page_number,
                "page_sha256": calculated.page_sha256,
                "result_count": len(calculated.results),
            }
        )
        success += len(calculated.result_sha256s)
        blocked += len(calculated.blocked_fingerprints)
    material = {
        "contract_kind": "offline_v9_public_curve_campaign_receipt_v1",
        "schema_version": 1,
        "campaign_request_id": campaign.plan.campaign_request_id,
        "plan_sha256": plan_sha,
        "curve_input_manifest_sha256s": list(campaign.curve_input_manifest_sha256s),
        "curve_input_content_root_sha256s": list(campaign.curve_input_content_root_sha256s),
        "curve_input_accepted_company_content_root_sha256s": list(
            campaign.curve_input_accepted_company_content_root_sha256s
        ),
        "frozen_multiple_artifact_sha256": campaign.frozen_multiple_artifact_sha256,
        "job_count": len(campaign.plan.jobs),
        "success_count": success,
        "blocked_count": blocked,
        "page_count": len(pages),
        "page_chain_head_sha256": previous,
        "pages": pages,
        "engine_sha256": campaign.plan.engine_sha256,
        "runtime_sha256": campaign.plan.runtime_sha256,
        "package_lock_sha256": campaign.plan.package_lock_sha256,
        "database_reads": 0,
        "database_writes": 0,
        "network_requests": 0,
        "publication_enabled": False,
        "rollout_state": "sealed_dark",
    }
    receipt = {**material, "receipt_sha256": sha256_prefixed(canonical_json_bytes(material))}
    receipt_path = target / "receipt.json"
    if receipt_path.exists():
        if _object(receipt_path, field="stored receipt") != receipt:
            raise PublicCurveCampaignIOError("stored campaign receipt drifted")
    else:
        _write_atomic_json(receipt_path, receipt)
    return receipt


__all__ = [
    "BuiltCampaign",
    "CurveInputRecord",
    "FrozenMultipleArtifact",
    "PublicCurveCampaignIOError",
    "build_campaign",
    "canonical_json_bytes",
    "execute_campaign_to_directory",
    "iter_curve_input_manifests",
    "load_frozen_multiple_artifact",
    "sha256_prefixed",
]
