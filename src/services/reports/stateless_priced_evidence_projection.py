"""Deterministic report views of one sealed ValuationRunV2.

The projection is intentionally read-only: it consumes only benchmark
snapshots, source citations and the value-driver ledger already committed to
the run.  It never reads a report request, mutable case data or template
context, and it never changes valuation economics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from src.api.schemas.priced_evidence_register import (
    ActionableAdjustmentLine,
    ActionableAdjustmentProjection,
    PricedEvidenceEntry,
    PricedEvidenceRegister,
    actionable_adjustment_projection_hash,
    priced_evidence_register_hash,
)
from src.api.schemas.valuation_contracts import ValuationRunV2
from src.services.reports.stateless_valuation_run import (
    canonical_hash,
    verify_valuation_run_integrity,
)


@dataclass(frozen=True)
class StatelessPricedEvidenceProjection:
    priced_evidence_register: PricedEvidenceRegister
    actionable_adjustments: ActionableAdjustmentProjection

    def as_report_context(self) -> dict[str, object]:
        register = self.priced_evidence_register.model_dump(mode="json")
        adjustments = self.actionable_adjustments.model_dump(mode="json")
        return {
            "priced_evidence_register": register,
            "actionable_adjustment_projection": adjustments,
            "actionable_adjustment_lines": adjustments["lines"],
            "show_canonical_evidence_adjustments_appendix": True,
        }


def build_stateless_priced_evidence_projection(
    run: ValuationRunV2,
) -> StatelessPricedEvidenceProjection:
    """Build both report projections after re-verifying the sealed run."""

    verify_valuation_run_integrity(run)
    evidence_entries = _priced_evidence_entries(run)
    evidence_material = {
        "schema_version": "priced_evidence_register.v1",
        "valuation_run_id": run.run_id,
        "valuation_run_hash": run.run_hash,
        "entries": [entry.model_dump(mode="json") for entry in evidence_entries],
    }
    register = PricedEvidenceRegister.model_validate(
        {
            **evidence_material,
            "register_hash": priced_evidence_register_hash(evidence_material),
        }
    )

    adjustment_lines = _actionable_adjustment_lines(run)
    adjustment_material = {
        "schema_version": "actionable_adjustment_projection.v1",
        "valuation_run_id": run.run_id,
        "valuation_run_hash": run.run_hash,
        "lines": [line.model_dump(mode="json") for line in adjustment_lines],
    }
    adjustments = ActionableAdjustmentProjection.model_validate(
        {
            **adjustment_material,
            "projection_hash": actionable_adjustment_projection_hash(adjustment_material),
        }
    )
    return StatelessPricedEvidenceProjection(
        priced_evidence_register=register,
        actionable_adjustments=adjustments,
    )


def _priced_evidence_entries(run: ValuationRunV2) -> list[PricedEvidenceEntry]:
    snapshot_materials = _benchmark_materials(run.benchmark_snapshot)
    citations = [citation.model_dump(mode="json") for citation in run.source_citations]
    priced_uses = _driver_evidence_uses(run.driver_ledger)
    entries: list[PricedEvidenceEntry] = []
    consumed_citation_ids: set[str] = set()

    for reference in run.benchmark_snapshot_references:
        ref = reference.model_dump(mode="json")
        metric = str(ref.get("metric") or "benchmark").strip()
        material = _matching_benchmark_material(ref, snapshot_materials)
        matching_citations = [
            citation
            for citation in citations
            if _citation_benchmark_metric(citation) == _normalized_metric(metric)
        ]
        if not matching_citations and len(run.benchmark_snapshot_references) == 1:
            # Older sealed runs used the non-metric-specific marker.  It is
            # unambiguous only when the run contains exactly one benchmark
            # reference; otherwise it remains a separate disclosed source.
            matching_citations = [
                citation
                for citation in citations
                if str(citation.get("use") or "").strip() == "priced_benchmark_metric"
            ]
        if not matching_citations:
            matching_citations = [None]
        for citation in matching_citations:
            if citation is not None:
                consumed_citation_ids.add(str(citation.get("citation_id") or ""))
            entries.append(
                _benchmark_evidence_entry(
                    reference=ref,
                    material=material,
                    citation=citation,
                )
            )

    for citation in citations:
        citation_id = str(citation.get("citation_id") or "")
        if citation_id in consumed_citation_ids:
            continue
        use = str(citation.get("use") or "").strip()
        source_id = str(citation.get("source_id") or "").strip()
        driver_use = priced_uses.get(source_id) or priced_uses.get(citation_id)
        accounting_fact_use = use.startswith("accounting_fact:") and (
            run.uploaded_data_snapshot_status == "priced"
        )
        explicitly_priced = use.startswith("priced_") or use.startswith("priced_benchmark_metric:")
        if not (driver_use or accounting_fact_use or explicitly_priced):
            continue
        method_key, resolved_use = driver_use or (
            _method_for_citation_use(use),
            use or "priced_report_source",
        )
        provider = _text(citation, "provider")
        content_hash = _text(citation, "document_hash")
        locator = _text(citation, "locator")
        observed_at = _text(citation, "observed_at")
        published_at = _text(citation, "published_at")
        missing_fields = _missing_evidence_fields(
            provider=provider,
            identity=source_id or None,
            snapshot_id=None,
            hash_or_locator=content_hash or locator,
            observed_at=observed_at,
            published_at=published_at,
            freshness_status="not_assessed",
            review_status="not_assessed",
            require_snapshot=False,
        )
        entries.append(
            PricedEvidenceEntry(
                entry_id=_entry_id(
                    "source",
                    citation_id or source_id or canonical_hash(citation),
                    method_key,
                    resolved_use,
                ),
                method_key=method_key,
                use=resolved_use,
                source_kind=str(citation.get("source_kind") or "report_source"),
                source_label=_text(citation, "title"),
                provider=provider,
                source_id=source_id or None,
                content_hash=content_hash,
                locator=locator,
                url=_text(citation, "url"),
                observed_at=observed_at,
                published_at=published_at,
                sample_size=None,
                sample_size_disclosure="not_applicable",
                freshness_status="not_assessed",
                review_status="not_assessed",
                source_completeness="incomplete" if missing_fields else "complete",
                missing_committed_fields=missing_fields,
            )
        )

    resolved_reference_ids = {
        value
        for citation in citations
        for value in (
            _first_text(citation.get("citation_id")),
            _first_text(citation.get("source_id")),
        )
        if value
    }
    for evidence_id, (method_key, use) in sorted(priced_uses.items()):
        if evidence_id in resolved_reference_ids:
            continue
        missing_fields = _missing_evidence_fields(
            provider=None,
            identity=evidence_id,
            snapshot_id=None,
            hash_or_locator=None,
            observed_at=None,
            published_at=None,
            freshness_status="not_assessed",
            review_status="not_assessed",
            require_snapshot=False,
        )
        entries.append(
            PricedEvidenceEntry(
                entry_id=_entry_id("unresolved_source", evidence_id, method_key, use),
                method_key=method_key,
                use=use,
                source_kind="unresolved_committed_reference",
                source_id=evidence_id,
                sample_size=None,
                sample_size_disclosure="not_applicable",
                freshness_status="not_assessed",
                review_status="not_assessed",
                source_completeness="incomplete",
                missing_committed_fields=missing_fields,
            )
        )

    deduplicated: dict[str, PricedEvidenceEntry] = {}
    for entry in entries:
        deduplicated[entry.entry_id] = entry
    return [deduplicated[key] for key in sorted(deduplicated)]


def _benchmark_evidence_entry(
    *,
    reference: Mapping[str, object],
    material: Mapping[str, object],
    citation: Mapping[str, object] | None,
) -> PricedEvidenceEntry:
    citation = citation or {}
    metric = str(reference.get("metric") or material.get("metric_name") or "benchmark")
    evidence_window = _mapping(reference.get("evidence_window")) or _mapping(
        material.get("evidence_window")
    )
    sample_size = _nonnegative_int(material.get("sample_size"))
    source_id = _first_text(citation.get("source_id"), reference.get("source_benchmark_id"))
    benchmark_id = _first_text(reference.get("benchmark_id"), material.get("benchmark_id"))
    snapshot_id = _first_text(
        reference.get("resolution_contract_id"),
        material.get("resolution_id"),
        material.get("snapshot_id"),
    )
    method_key = _method_for_metric(metric)
    use = f"priced_benchmark_metric:{_normalized_metric(metric)}"
    citation_id = _first_text(citation.get("citation_id"))
    provider = _first_text(
        citation.get("provider"),
        material.get("provider"),
        material.get("data_source"),
        material.get("source"),
    )
    content_hash = _first_text(
        citation.get("document_hash"), reference.get("resolution_contract_hash")
    )
    locator = _text(citation, "locator")
    observed_at = _first_text(
        citation.get("observed_at"),
        evidence_window.get("evidence_as_of"),
        evidence_window.get("observed_at"),
    )
    published_at = _first_text(
        citation.get("published_at"),
        reference.get("published_at"),
        material.get("published_at"),
    )
    freshness_status = (
        _first_text(evidence_window.get("freshness"), material.get("freshness_status"))
        or "not_assessed"
    )
    review_status = (
        _first_text(reference.get("review_state"), material.get("review_state")) or "not_assessed"
    )
    missing_fields = _missing_evidence_fields(
        provider=provider,
        identity=source_id or benchmark_id,
        snapshot_id=snapshot_id,
        hash_or_locator=content_hash or locator,
        observed_at=observed_at,
        published_at=published_at,
        freshness_status=freshness_status,
        review_status=review_status,
    )
    return PricedEvidenceEntry(
        entry_id=_entry_id(
            "benchmark",
            benchmark_id or source_id or snapshot_id or canonical_hash(reference),
            citation_id or "snapshot",
            _normalized_metric(metric),
        ),
        method_key=method_key,
        use=use,
        source_kind=str(citation.get("source_kind") or "benchmark_snapshot"),
        source_label=_first_text(
            citation.get("title"),
            material.get("evidence_summary"),
            material.get("data_source"),
        ),
        provider=provider,
        source_id=source_id,
        benchmark_id=benchmark_id,
        snapshot_id=snapshot_id,
        snapshot_hash=_first_text(
            reference.get("snapshot_hash"), reference.get("resolution_contract_hash")
        ),
        dataset_version_id=_first_text(
            reference.get("dataset_version_id"),
            reference.get("source_dataset_version_id"),
            material.get("dataset_version_id"),
        ),
        content_hash=content_hash,
        locator=locator,
        url=_text(citation, "url"),
        observed_at=observed_at,
        published_at=published_at,
        sample_size=sample_size,
        sample_size_disclosure=("reported" if sample_size is not None else "not_disclosed"),
        freshness_status=freshness_status,
        review_status=review_status,
        source_completeness="incomplete" if missing_fields else "complete",
        missing_committed_fields=missing_fields,
    )


def _actionable_adjustment_lines(run: ValuationRunV2) -> list[ActionableAdjustmentLine]:
    layers = _mapping(run.driver_ledger.get("layers"))
    lines: list[ActionableAdjustmentLine] = []
    lines.extend(_operating_adjustment_lines(run, layers))
    lines.extend(_enterprise_bridge_lines(run, layers))
    lines.extend(_method_calibration_lines(run, layers))
    lines.extend(_shareholder_adjustment_lines(run, layers))
    deduplicated: dict[str, ActionableAdjustmentLine] = {}
    for line in lines:
        deduplicated[line.line_id] = line
    return [deduplicated[key] for key in sorted(deduplicated)]


def _operating_adjustment_lines(
    run: ValuationRunV2,
    layers: Mapping[str, object],
) -> list[ActionableAdjustmentLine]:
    operating = _mapping(layers.get("operating_normalizations"))
    earnings_basis = _mapping(operating.get("earnings_basis"))
    year_rows = _sequence(earnings_basis.get("rows"))
    output: list[ActionableAdjustmentLine] = []
    for year_index, raw_year in enumerate(year_rows):
        year = _mapping(raw_year)
        fiscal_year = _nonnegative_int(year.get("fiscal_year"))
        for state_key, priced in (
            ("applied_adjustments", True),
            ("pending_adjustments", False),
        ):
            for row_index, raw in enumerate(_sequence(year.get(state_key))):
                row = _mapping(raw)
                signed_amount = _decimal(row.get("signed_amount"))
                has_sealed_impact = signed_amount is not None
                is_priced = priced and has_sealed_impact
                evidence_ids, evidence_status, evidence_date, missing_fields = (
                    _line_evidence_fields(row)
                )
                if not has_sealed_impact:
                    missing_fields.append("signed_impact")
                source_path = (
                    "driver_ledger.layers.operating_normalizations.earnings_basis."
                    f"rows[{year_index}].{state_key}[{row_index}]"
                )
                output.append(
                    ActionableAdjustmentLine(
                        line_id=_line_id(
                            "operating",
                            row.get("id"),
                            fiscal_year,
                            row_index,
                            state_key,
                        ),
                        category="operating_normalization",
                        label=str(row.get("label") or "Operating normalization"),
                        signed_amount=signed_amount,
                        amount_basis="normalized_ebitda",
                        currency=_currency(row.get("currency"), run.currency),
                        priced_state="priced" if is_priced else "scenario_only",
                        status=str(
                            row.get("status")
                            or (
                                "applied"
                                if is_priced
                                else ("unpriced_impact_missing" if priced else "proposed")
                            )
                        ),
                        evidence_reference_ids=evidence_ids,
                        evidence_status=evidence_status,
                        evidence_date=evidence_date,
                        source=_first_text(row.get("source")),
                        source_path=source_path,
                        fiscal_year=fiscal_year,
                        effective_date=_first_text(row.get("effective_date")),
                        recoverability=_recoverability(row.get("recoverability")),
                        action=_first_text(row.get("action"), row.get("recommended_action")),
                        proof_required=_first_text(
                            row.get("proof_required"), row.get("required_proof")
                        ),
                        missing_committed_fields=missing_fields,
                    )
                )
    return output


def _enterprise_bridge_lines(
    run: ValuationRunV2,
    layers: Mapping[str, object],
) -> list[ActionableAdjustmentLine]:
    layer = _mapping(layers.get("enterprise_to_equity"))
    bridge = _mapping(layer.get("bridge"))
    if bridge.get("applicability") == "not_applicable":
        return []
    explicit = _mapping(layer.get("explicit_adjustments"))
    explicit_rows = [_mapping(raw) for raw in _sequence(explicit.get("rows"))]
    explicit_by_key = {
        str(row.get("key")): row for row in explicit_rows if row.get("key") is not None
    }
    seen_keys: set[str] = set()
    output: list[ActionableAdjustmentLine] = []
    for index, raw in enumerate(_sequence(bridge.get("lines"))):
        row = _mapping(raw)
        key = str(row.get("key") or row.get("kind") or f"bridge_{index + 1}")
        seen_keys.add(key)
        evidence = explicit_by_key.get(key, {})
        signed_amount = _signed_bridge_amount(row)
        has_sealed_impact = signed_amount is not None
        evidence_ids, evidence_status, evidence_date, missing_fields = _line_evidence_fields(
            evidence
        )
        if not has_sealed_impact:
            missing_fields.append("signed_impact")
        output.append(
            ActionableAdjustmentLine(
                line_id=_line_id("enterprise_to_equity", key),
                category="enterprise_to_equity",
                label=str(row.get("label") or evidence.get("label") or key),
                signed_amount=signed_amount,
                amount_basis="equity_value",
                currency=_currency(evidence.get("currency"), run.currency),
                priced_state="priced" if has_sealed_impact else "scenario_only",
                status=str(
                    evidence.get("status")
                    or ("applied" if has_sealed_impact else "unpriced_impact_missing")
                ),
                evidence_reference_ids=evidence_ids,
                evidence_status=evidence_status,
                evidence_date=evidence_date,
                source=_first_text(evidence.get("source_contract"), evidence.get("source")),
                source_path=f"driver_ledger.layers.enterprise_to_equity.bridge.lines[{index}]",
                fiscal_year=_nonnegative_int(evidence.get("fiscal_year")),
                effective_date=_first_text(evidence.get("effective_date")),
                recoverability=_recoverability(evidence.get("recoverability")),
                action=_first_text(evidence.get("action"), evidence.get("recommended_action")),
                proof_required=_first_text(
                    evidence.get("proof_required"), evidence.get("required_proof")
                ),
                missing_committed_fields=missing_fields,
            )
        )

    for index, row in enumerate(explicit_rows):
        key = str(row.get("key") or f"explicit_{index + 1}")
        if key in seen_keys:
            continue
        applied = row.get("applied") is True
        signed_amount = _decimal(row.get("signed_amount"))
        has_sealed_impact = signed_amount is not None
        is_priced = applied and has_sealed_impact
        evidence_ids, evidence_status, evidence_date, missing_fields = _line_evidence_fields(row)
        if not has_sealed_impact:
            missing_fields.append("signed_impact")
        output.append(
            ActionableAdjustmentLine(
                line_id=_line_id("enterprise_to_equity_explicit", key),
                category="enterprise_to_equity",
                label=str(row.get("label") or key),
                signed_amount=signed_amount,
                amount_basis="equity_value",
                currency=_currency(row.get("currency"), run.currency),
                priced_state="priced" if is_priced else "scenario_only",
                status=str(
                    row.get("status")
                    or (
                        "applied"
                        if is_priced
                        else "unpriced_impact_missing" if applied else "proposed"
                    )
                ),
                evidence_reference_ids=evidence_ids,
                evidence_status=evidence_status,
                evidence_date=evidence_date,
                source=_first_text(row.get("source_contract"), row.get("source")),
                source_path=(
                    "driver_ledger.layers.enterprise_to_equity.explicit_adjustments."
                    f"rows[{index}]"
                ),
                fiscal_year=_nonnegative_int(row.get("fiscal_year")),
                effective_date=_first_text(row.get("effective_date")),
                recoverability=_recoverability(row.get("recoverability")),
                action=_first_text(row.get("action"), row.get("recommended_action")),
                proof_required=_first_text(row.get("proof_required"), row.get("required_proof")),
                missing_committed_fields=missing_fields,
            )
        )
    return output


def _method_calibration_lines(
    run: ValuationRunV2,
    layers: Mapping[str, object],
) -> list[ActionableAdjustmentLine]:
    calibration = _mapping(layers.get("method_calibration"))
    stack = _mapping(calibration.get("market_discount_stack"))
    output: list[ActionableAdjustmentLine] = []
    for index, raw in enumerate(_sequence(stack.get("rows"))):
        row = _mapping(raw)
        enabled = row.get("enabled") is not False
        magnitude = _decimal(row.get("magnitude"))
        percentage_points = magnitude * Decimal("100") if magnitude is not None else None
        euro_impact = _decimal(row.get("euro_impact"))
        has_sealed_impact = euro_impact is not None or percentage_points is not None
        is_priced = enabled and has_sealed_impact
        evidence_ids, evidence_status, evidence_date, missing_fields = _line_evidence_fields(row)
        if not has_sealed_impact:
            missing_fields.append("signed_impact")
        output.append(
            ActionableAdjustmentLine(
                line_id=_line_id("method_calibration", row.get("key"), index),
                category="structural_shareholder_transaction",
                label=str(row.get("label") or row.get("key") or "Method adjustment"),
                signed_amount=euro_impact,
                signed_percentage_points=percentage_points,
                amount_basis="enterprise_value_multiple",
                currency=run.currency,
                priced_state="priced" if is_priced else "scenario_only",
                status=(
                    "applied" if is_priced else "unpriced_impact_missing" if enabled else "disabled"
                ),
                evidence_reference_ids=evidence_ids,
                evidence_status=evidence_status,
                evidence_date=evidence_date,
                source=_first_text(row.get("source")),
                source_path=(
                    "driver_ledger.layers.method_calibration.market_discount_stack."
                    f"rows[{index}]"
                ),
                recoverability=_recoverability(row.get("recoverability")),
                action=_first_text(row.get("action"), row.get("recommended_action")),
                proof_required=_first_text(row.get("proof_required"), row.get("required_proof")),
                missing_committed_fields=missing_fields,
            )
        )
    return output


def _shareholder_adjustment_lines(
    run: ValuationRunV2,
    layers: Mapping[str, object],
) -> list[ActionableAdjustmentLine]:
    layer = _mapping(layers.get("shareholder_transaction"))
    result = _mapping(layer.get("owner_dependency"))
    adjustment = _decimal(layer.get("owner_dependency_adjustment"))
    before = _decimal(layer.get("equity_before_owner_dependency"))
    after = _decimal(layer.get("equity_after_owner_dependency"))
    if not result and (adjustment is None or adjustment == 0) and before == after:
        return []
    scenario = str(result.get("status") or "").startswith("scenario_only") or (
        result.get("priced") is False
    )
    signed_amount = after - before if before is not None and after is not None else None
    percentage_points = adjustment * Decimal("100") if adjustment is not None else None
    has_sealed_impact = signed_amount is not None or percentage_points is not None
    is_priced = not scenario and has_sealed_impact
    evidence_ids, evidence_status, evidence_date, missing_fields = _line_evidence_fields(result)
    if not has_sealed_impact:
        missing_fields.append("signed_impact")
    return [
        ActionableAdjustmentLine(
            line_id=_line_id("shareholder", "owner_dependency"),
            category="structural_shareholder_transaction",
            label="Owner dependency / transferability",
            signed_amount=signed_amount,
            signed_percentage_points=percentage_points,
            amount_basis="shareholder_equity_value",
            currency=run.currency,
            priced_state="priced" if is_priced else "scenario_only",
            status=str(
                result.get("status")
                or (
                    "applied"
                    if is_priced
                    else "scenario_only" if scenario else "unpriced_impact_missing"
                )
            ),
            evidence_reference_ids=evidence_ids,
            evidence_status=evidence_status,
            evidence_date=evidence_date,
            source=_first_text(result.get("source")),
            source_path="driver_ledger.layers.shareholder_transaction.owner_dependency",
            recoverability=_recoverability(result.get("recoverability")),
            action=_first_text(result.get("action"), result.get("recommended_action")),
            proof_required=_first_text(result.get("proof_required"), result.get("required_proof")),
            missing_committed_fields=missing_fields,
        )
    ]


def _missing_evidence_fields(
    *,
    provider: str | None,
    identity: str | None,
    snapshot_id: str | None,
    hash_or_locator: str | None,
    observed_at: str | None,
    published_at: str | None,
    freshness_status: str,
    review_status: str,
    require_snapshot: bool = True,
) -> list[str]:
    """Name absent run commitments without substituting report-time data."""

    missing: list[str] = []
    for field, value in (
        ("provider", provider),
        ("source_or_benchmark_id", identity),
        ("hash_or_locator", hash_or_locator),
        ("observed_at", observed_at),
        ("published_at", published_at),
    ):
        if value is None:
            missing.append(field)
    if require_snapshot and snapshot_id is None:
        missing.append("snapshot_id")
    if freshness_status == "not_assessed":
        missing.append("freshness_status")
    if review_status == "not_assessed":
        missing.append("review_status")
    return missing


def _line_evidence_fields(
    row: Mapping[str, object],
) -> tuple[list[str], str, str | None, list[str]]:
    """Project evidence metadata exactly as committed on a ledger row."""

    evidence_ids = _evidence_ids(row)
    evidence_status = _first_text(
        row.get("evidence_status"),
        row.get("verification_status"),
        row.get("review_status"),
    )
    evidence_date = _first_text(
        row.get("evidence_date"),
        row.get("observed_at"),
        row.get("reviewed_at"),
        row.get("source_date"),
    )
    source = _first_text(row.get("source_contract"), row.get("source"))
    missing: list[str] = []
    if not evidence_ids:
        missing.append("evidence_reference_ids")
    if evidence_status is None:
        missing.append("evidence_status")
    if evidence_date is None:
        missing.append("evidence_date")
    if source is None:
        missing.append("source")
    return evidence_ids, evidence_status or "not_supplied", evidence_date, missing


def _driver_evidence_uses(
    driver_ledger: Mapping[str, object],
) -> dict[str, tuple[str, str]]:
    layers = _mapping(driver_ledger.get("layers"))
    uses: dict[str, tuple[str, str]] = {}
    operating = _mapping(layers.get("operating_normalizations"))
    earnings = _mapping(operating.get("earnings_basis"))

    def record(row: Mapping[str, object], method_key: str, use: str) -> None:
        for evidence_id in _evidence_ids(row):
            uses[evidence_id] = (method_key, use)

    for raw_year in _sequence(earnings.get("rows")):
        year = _mapping(raw_year)
        for raw in _sequence(year.get("applied_adjustments")):
            row = _mapping(raw)
            if _decimal(row.get("signed_amount")) is not None:
                record(row, "all_priced_methods", "operating_normalization")
    bridge = _mapping(layers.get("enterprise_to_equity"))
    explicit = _mapping(bridge.get("explicit_adjustments"))
    for raw in _sequence(explicit.get("rows")):
        row = _mapping(raw)
        if row.get("applied") is True and _decimal(row.get("signed_amount")) is not None:
            record(row, "all_priced_methods", "enterprise_to_equity_adjustment")
    calibration = _mapping(layers.get("method_calibration"))
    stack = _mapping(calibration.get("market_discount_stack"))
    for raw in _sequence(stack.get("rows")):
        row = _mapping(raw)
        if row.get("enabled") is False:
            continue
        if _decimal(row.get("euro_impact")) is None and _decimal(row.get("magnitude")) is None:
            continue
        record(row, "adaptive_synthesis", "method_calibration_adjustment")
    shareholder = _mapping(layers.get("shareholder_transaction"))
    owner_dependency = _mapping(shareholder.get("owner_dependency"))
    is_scenario = (
        str(owner_dependency.get("status") or "").startswith("scenario_only")
        or owner_dependency.get("priced") is False
    )
    has_owner_impact = _decimal(shareholder.get("owner_dependency_adjustment")) is not None or (
        _decimal(shareholder.get("equity_before_owner_dependency")) is not None
        and _decimal(shareholder.get("equity_after_owner_dependency")) is not None
    )
    if not is_scenario and has_owner_impact:
        record(
            owner_dependency,
            "all_priced_methods",
            "shareholder_transferability_adjustment",
        )
    return uses


def _benchmark_materials(snapshot: object) -> list[Mapping[str, object]]:
    root = _mapping(snapshot)
    output: list[Mapping[str, object]] = []
    for key in ("resolutions", "metric_outcomes"):
        output.extend(_mapping(raw) for raw in _sequence(root.get(key)))
    metrics = _mapping(root.get("metrics"))
    output.extend(_mapping(raw) for raw in metrics.values())
    commitment = _mapping(root.get("resolution_commitment"))
    for key in ("resolutions", "metric_outcomes"):
        output.extend(_mapping(raw) for raw in _sequence(commitment.get(key)))
    if root:
        output.append(root)
    return [row for row in output if row]


def _matching_benchmark_material(
    reference: Mapping[str, object],
    materials: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    benchmark_ids = {
        text
        for text in (
            _first_text(reference.get("benchmark_id")),
            _first_text(reference.get("source_benchmark_id")),
        )
        if text
    }
    metric = _normalized_metric(reference.get("metric"))
    for material in materials:
        material_ids = {
            text
            for text in (
                _first_text(material.get("benchmark_id")),
                _first_text(material.get("source_benchmark_id")),
            )
            if text
        }
        if benchmark_ids and material_ids and benchmark_ids.intersection(material_ids):
            return material
    for material in materials:
        material_metric = _normalized_metric(material.get("metric_name") or material.get("metric"))
        if material_metric and material_metric == metric:
            return material
    return {}


def _citation_benchmark_metric(citation: Mapping[str, object]) -> str | None:
    use = str(citation.get("use") or "")
    prefix = "priced_benchmark_metric:"
    if use.startswith(prefix):
        return _normalized_metric(use[len(prefix) :])
    return None


def _method_for_citation_use(use: str) -> str:
    metric = _citation_benchmark_metric({"use": use})
    if metric:
        return _method_for_metric(metric)
    return "all_priced_methods"


def _method_for_metric(value: object) -> str:
    metric = _normalized_metric(value)
    if "ebitda" in metric:
        return "ebitda_multiple"
    if "arr" in metric:
        return "arr_multiple"
    if "revenue" in metric or "sales" in metric or "omzet" in metric:
        return "revenue_multiple"
    if "sde" in metric:
        return "sde_multiple"
    if "yield" in metric or "real_estate" in metric:
        return "real_estate_yield"
    if "startup" in metric:
        return "startup"
    return metric or "cross_method"


def _normalized_metric(value: object) -> str:
    return str(value or "").strip().lower().replace("/", "_").replace("-", "_").replace(" ", "_")


def _entry_id(*parts: object) -> str:
    return f"pe_{canonical_hash([str(part or '') for part in parts])[:24]}"


def _line_id(*parts: object) -> str:
    return f"aal_{canonical_hash([str(part or '') for part in parts])[:24]}"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> list[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _text(mapping: Mapping[str, object], key: str) -> str | None:
    return _first_text(mapping.get(key))


def _first_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    decimal_value = _decimal(value)
    if decimal_value is None or decimal_value != decimal_value.to_integral_value():
        return None
    parsed = int(decimal_value)
    return parsed if parsed >= 0 else None


def _signed_bridge_amount(row: Mapping[str, object]) -> Decimal | None:
    signed = _decimal(row.get("signed_amount"))
    if signed is not None:
        return signed
    amount = _decimal(row.get("amount"))
    if amount is None:
        return None
    return abs(amount) if str(row.get("operator") or "-") == "+" else -abs(amount)


def _currency(primary: object, fallback: object) -> str | None:
    value = _first_text(primary, fallback)
    return value.upper() if value and len(value) == 3 else None


def _recoverability(value: object) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"recoverable", "partly_recoverable", "structural"}:
        return normalized
    return "not_assessed"


def _evidence_ids(row: Mapping[str, object]) -> list[str]:
    values: list[object] = [
        row.get("evidence_id"),
        row.get("citation_id"),
        row.get("source_id"),
    ]
    for key in (
        "evidence_reference_ids",
        "strength_factor_captured_input_ids",
        "strength_factor_data_point_ids",
    ):
        values.extend(_sequence(row.get(key)))
    output: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        normalized = value.strip()
        if normalized not in output:
            output.append(normalized)
    return output
