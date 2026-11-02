"""Quality-warning aggregation helpers for comprehensive valuation responses."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Dict, List, Optional

from src.domain.report_integrity import build_method_substitution_warning


def ensure_method_substitution_warning(
    warnings: List[Dict[str, object]],
    substitution_payload: Optional[Dict[str, object]],
) -> List[Dict[str, object]]:
    if not isinstance(warnings, list):
        warnings = []
    if not isinstance(substitution_payload, dict):
        return warnings

    for warning in warnings:
        if isinstance(warning, dict) and warning.get("type") == "method_substitution":
            return warnings

    reason = substitution_payload.get("reason")
    warnings.insert(
        0,
        build_method_substitution_warning(
            requested_method=str(
                substitution_payload.get("requested_methodology") or "ASSET_BASED"
            ),
            executed_method=str(substitution_payload.get("executed_methodology") or "MULTIPLES"),
            reason=reason,
            extra_details={
                "reason_code": substitution_payload.get("reason_code"),
                "missing_fields": list(substitution_payload.get("missing_fields") or []),
                "remediation": substitution_payload.get("remediation"),
                "substitution": dict(substitution_payload),
            },
        ),
    )
    return warnings


def aggregate_quality_warnings(detailed_results: Dict[str, object]) -> List[Dict[str, object]]:
    """
    Collect every data-quality warning emitted by the calculation pipeline.

    Sources, in order:
      1. detailed_results['multiples_valuation']['data_quality_warnings']
         (Step 2 emits these; this is the legacy nesting location.)
      2. step.result.get('data_quality_warnings') across all step results
         (forward-compatible — future steps can publish here.)
      3. step.metadata.get('quality_warning') across all step results
         (Step 4 missing-inputs, weighted-EBITDA divergence, etc.)
      4. detailed_results['data_quality_warnings'] (Pass-8: top-level slot
         for cross-cutting warnings that don't belong to any single step,
         e.g. method-substitution emitted by the orchestrator).

    De-duplicates by (type, message) so duplicate disclosures found through
    multiple paths do not render twice with different provenance metadata.
    """
    if not isinstance(detailed_results, dict):
        return []

    collector = _WarningCollector()
    collector.add_many(detailed_results.get("data_quality_warnings") or [])

    multiples_res = detailed_results.get("multiples_valuation")
    if isinstance(multiples_res, dict):
        collector.add_many(multiples_res.get("data_quality_warnings") or [], source_step=2)

    dcf_res = detailed_results.get("dcf_valuation")
    if isinstance(dcf_res, dict):
        collector.add_many(dcf_res.get("data_quality_warnings") or [], source_step="dcf")

    for step_num, step_output in _iter_step_outputs(detailed_results, multiples_res):
        collector.add_many(_result_warnings(step_output), source_step=step_num)
        collector.add(_metadata_warning(step_output), source_step=step_num)
        collector.add_many(_metadata_warnings(step_output), source_step=step_num)

    return collector.warnings


class _WarningCollector:
    def __init__(self) -> None:
        self.warnings: List[Dict[str, object]] = []
        self._seen: set[tuple[object, object]] = set()

    def add_many(self, warnings: Iterable[object], source_step: object = None) -> None:
        for warning in warnings:
            self.add(warning, source_step=source_step)

    def add(self, warning: object, source_step: object = None) -> None:
        if not isinstance(warning, dict):
            return
        entry = dict(warning)
        if source_step is not None and "step_number" not in entry:
            entry["step_number"] = source_step
        key = (entry.get("type"), entry.get("message"))
        if key in self._seen:
            return
        self._seen.add(key)
        self.warnings.append(entry)


def _iter_step_outputs(
    detailed_results: Dict[str, object],
    multiples_res: object,
) -> Iterable[tuple[object, object]]:
    for bucket in _step_buckets(detailed_results, multiples_res):
        if not isinstance(bucket, dict):
            continue
        for step_num, step_output in bucket.items():
            if step_output is not None:
                yield step_num, step_output


def _step_buckets(
    detailed_results: Dict[str, object],
    multiples_res: object,
) -> list[object]:
    buckets: list[object] = []
    if isinstance(multiples_res, dict):
        buckets.append(multiples_res.get("_step_results"))
    buckets.append(detailed_results.get("step_results"))
    nested = detailed_results.get("detailed_results")
    if isinstance(nested, dict):
        buckets.append(nested.get("step_results"))
    return buckets


def _result_warnings(step_output: object) -> Iterable[object]:
    result_obj = _step_output_mapping(step_output, "result")
    if not isinstance(result_obj, dict):
        return []
    return result_obj.get("data_quality_warnings") or []


def _metadata_warning(step_output: object) -> object:
    metadata_obj = _step_output_mapping(step_output, "metadata")
    if not isinstance(metadata_obj, dict):
        return None
    return metadata_obj.get("quality_warning")


def _metadata_warnings(step_output: object) -> Iterable[object]:
    metadata_obj = _step_output_mapping(step_output, "metadata")
    if not isinstance(metadata_obj, dict):
        return []
    return metadata_obj.get("quality_warnings") or []


def _step_output_mapping(step_output: object, key: str) -> object:
    value = getattr(step_output, key, None)
    if value is None and isinstance(step_output, dict):
        return step_output.get(key)
    return value
