"""Independent PDF/A-2b conformance validation for publishable artifacts.

The renderer and the conformance validator must not be the same trust boundary.
WeasyPrint produces the document; veraPDF evaluates it against the ISO 19005-2
machine-verifiable rules and emits a report whose digest is committed to the
cross-service render receipt.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


class PdfaConformanceValidationError(RuntimeError):
    """Raised when conformance cannot be established unambiguously."""


@dataclass(frozen=True)
class PdfaConformanceResult:
    engine: str
    validator_version: str
    profile: str
    is_compliant: bool
    failed_rules: int
    failed_checks: int
    report_sha256: str


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first(root: ET.Element, local_name: str) -> ET.Element | None:
    return next((node for node in root.iter() if _local_name(node.tag) == local_name), None)


def _nonnegative_int(value: str | None, label: str) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise PdfaConformanceValidationError(f"veraPDF omitted a valid {label} counter") from exc
    if parsed < 0:
        raise PdfaConformanceValidationError(f"veraPDF returned a negative {label} counter")
    return parsed


def parse_verapdf_xml(report: bytes) -> PdfaConformanceResult:
    """Parse one bounded veraPDF XML report and reject ambiguous output."""

    if not report or len(report) > 2 * 1024 * 1024:
        raise PdfaConformanceValidationError("veraPDF returned an empty or oversized report")
    try:
        root = ET.fromstring(report)
    except ET.ParseError as exc:
        raise PdfaConformanceValidationError("veraPDF returned malformed XML") from exc

    validation_reports = [
        node for node in root.iter() if _local_name(node.tag) == "validationReport"
    ]
    if len(validation_reports) != 1:
        raise PdfaConformanceValidationError(
            "veraPDF must return exactly one validation report per artifact"
        )
    validation = validation_reports[0]
    profile = str(validation.attrib.get("profileName") or "").strip()
    if "PDF/A-2B" not in profile.upper():
        raise PdfaConformanceValidationError(
            f"veraPDF evaluated an unexpected conformance profile: {profile or 'missing'}"
        )
    compliant_raw = str(validation.attrib.get("isCompliant") or "").strip().lower()
    if compliant_raw not in {"true", "false"}:
        raise PdfaConformanceValidationError("veraPDF omitted the conformance decision")

    details = _first(validation, "details")
    if details is None:
        raise PdfaConformanceValidationError("veraPDF omitted validation detail counters")
    failed_rules = _nonnegative_int(details.attrib.get("failedRules"), "failedRules")
    failed_checks = _nonnegative_int(details.attrib.get("failedChecks"), "failedChecks")

    batch = _first(root, "batchSummary")
    summary = _first(batch, "validationReports") if batch is not None else None
    if batch is None or summary is None:
        raise PdfaConformanceValidationError("veraPDF omitted its batch summary")
    if any(
        _nonnegative_int(batch.attrib.get(counter), counter) != 0
        for counter in ("failedToParse", "encrypted", "outOfMemory", "veraExceptions")
        if counter in batch.attrib
    ):
        raise PdfaConformanceValidationError("veraPDF reported a processing failure")
    compliant_count = _nonnegative_int(summary.attrib.get("compliant"), "compliant")
    noncompliant_count = _nonnegative_int(summary.attrib.get("nonCompliant"), "nonCompliant")
    failed_jobs = _nonnegative_int(summary.attrib.get("failedJobs"), "failedJobs")
    is_compliant = compliant_raw == "true"
    expected_counts = (1, 0, 0) if is_compliant else (0, 1, 0)
    if (compliant_count, noncompliant_count, failed_jobs) != expected_counts:
        raise PdfaConformanceValidationError(
            "veraPDF's artifact decision and batch summary do not reconcile"
        )
    if is_compliant and (failed_rules != 0 or failed_checks != 0):
        raise PdfaConformanceValidationError(
            "veraPDF marked the artifact compliant despite failed rules or checks"
        )

    release_details = [node for node in root.iter() if _local_name(node.tag) == "releaseDetails"]
    version_node = next(
        (node for node in release_details if node.attrib.get("id") == "validation-model"),
        release_details[0] if release_details else None,
    )
    version = str(
        (version_node.attrib.get("version") if version_node is not None else None) or "unknown"
    )
    if len(version) > 80:
        raise PdfaConformanceValidationError("veraPDF returned an invalid validator version")

    return PdfaConformanceResult(
        engine="verapdf",
        validator_version=version,
        profile="PDF/A-2b",
        is_compliant=is_compliant,
        failed_rules=failed_rules,
        failed_checks=failed_checks,
        report_sha256=hashlib.sha256(report).hexdigest(),
    )


def validate_pdfa_2b(pdf_bytes: bytes) -> PdfaConformanceResult | None:
    """Run veraPDF when installed; fail if production requires it and it is absent."""

    command = Path(os.getenv("VERAPDF_CLI_PATH", "/opt/verapdf/verapdf"))
    required = _truthy(os.getenv("SEALED_REQUIRE_VERAPDF"))
    if not command.is_file() or not os.access(command, os.X_OK):
        if required:
            raise PdfaConformanceValidationError(
                f"Required veraPDF executable is unavailable at {command}"
            )
        return None

    timeout_seconds = max(5, min(120, int(os.getenv("VERAPDF_TIMEOUT_SECONDS", "30"))))
    with tempfile.NamedTemporaryFile(suffix=".pdf") as artifact:
        artifact.write(pdf_bytes)
        artifact.flush()
        try:
            completed = subprocess.run(
                [
                    str(command),
                    "--format",
                    "xml",
                    "--flavour",
                    "2b",
                    "--maxfailuresdisplayed",
                    "20",
                    artifact.name,
                ],
                check=False,
                capture_output=True,
                timeout=timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PdfaConformanceValidationError("veraPDF execution failed") from exc
    # veraPDF uses status 1 for a successfully evaluated but non-conformant
    # artifact. Parse that report so the caller receives the authoritative
    # decision; other statuses represent execution failures.
    if completed.returncode not in {0, 1}:
        stderr = completed.stderr.decode("utf-8", errors="replace")[:500]
        raise PdfaConformanceValidationError(
            f"veraPDF exited with status {completed.returncode}: {stderr}"
        )
    result = parse_verapdf_xml(completed.stdout)
    if (result.is_compliant and completed.returncode != 0) or (
        not result.is_compliant and completed.returncode != 1
    ):
        raise PdfaConformanceValidationError(
            "veraPDF's process status and conformance decision do not reconcile"
        )
    return result
