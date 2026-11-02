"""BET-293 live valuation hook for parent/subsidiary consolidation."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

from src.api.schemas import ValuationRequest, YearDataInput
from src.services.holding_consolidation import (
    HoldingConsolidationInputError,
    consolidate_holding_entities,
)
from src.services.holdings_fallback import standalone_holdings_fallback
from src.services.reports.consolidation_report_context import build_consolidation_report_context
from src.services.structure_evidence import StructureEvidenceGate, evaluate_structure_evidence
from src.utils.decimal_helpers import to_decimal

_CONSOLIDATED_LINE_TO_YEAR_FIELD = {
    "revenue": "revenue",
    "ebitda": "ebitda",
    "net_income": "net_income",
    "total_assets": "total_assets",
    "equity": "total_equity",
}


def _payload_mapping(payload: object, field: str) -> Mapping[str, object] | None:
    value = getattr(payload, field, None)
    return value if isinstance(value, Mapping) else None


def _payload_sequence(payload: object, field: str) -> list[Mapping[str, object]]:
    value = getattr(payload, field, None)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _decimal_or_none(value: object) -> Decimal | None:
    try:
        return cast(Decimal, to_decimal(value))
    except (TypeError, ValueError, ArithmeticError):
        return None


def _uuid_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def _entity_source_ids(
    parent: Mapping[str, object],
    subsidiaries: list[Mapping[str, object]],
) -> list[str]:
    entity_ids: list[str] = []
    for entity in (parent, *subsidiaries):
        for key in ("id", "entity_id", "company_id"):
            value = entity.get(key)
            if value is not None and str(value).strip():
                entity_ids.append(str(value).strip())
                break
    return entity_ids


def _entity_source_id(entity: Mapping[str, object]) -> str | None:
    ids = _entity_source_ids(entity, [])
    return ids[0] if ids else None


def _entity_report_bindings(
    parent: Mapping[str, object],
    subsidiaries: list[Mapping[str, object]],
) -> list[dict[str, object]]:
    return [
        {
            "entity_id": _entity_source_id(entity),
            "valuation_report_id": entity.get("valuation_report_id"),
            "valuation_evidence_revision_id": entity.get("evidence_revision_id"),
        }
        for entity in (parent, *subsidiaries)
    ]


def _accepted_holdings_decision_ids(valuation_case: object) -> list[str]:
    case = valuation_case if isinstance(valuation_case, Mapping) else {}
    raw_decisions = case.get("input_decisions")
    if not isinstance(raw_decisions, list):
        return []
    decision_ids: list[str] = []
    for raw in raw_decisions:
        if not isinstance(raw, Mapping):
            continue
        field_key = str(raw.get("field_key") or "")
        decision_id = str(raw.get("decision_id") or "").strip()
        if (
            field_key.startswith("holdings_consolidation.")
            and raw.get("state") in {"accepted", "edited"}
            and decision_id
        ):
            decision_ids.append(decision_id)
    return sorted(set(decision_ids))


def _holdings_ownership(
    parent: Mapping[str, object],
    subsidiaries: list[Mapping[str, object]],
) -> dict[str, object]:
    ownership: dict[str, object] = {}
    parent_id = _entity_source_id(parent)
    if parent_id is not None and parent.get("parent_ownership_pct") is not None:
        ownership[parent_id] = parent.get("parent_ownership_pct")
    for subsidiary in subsidiaries:
        entity_id = _entity_source_id(subsidiary)
        if entity_id is None:
            continue
        for key in ("ownership_pct", "ownership_pct_in_parent", "parent_ownership_pct"):
            if subsidiary.get(key) is not None:
                ownership[entity_id] = subsidiary.get(key)
                break
    return ownership


def _real_estate_treatment(request: ValuationRequest) -> str:
    treatment = str(getattr(request, "real_estate_treatment", None) or "").strip().lower()
    if treatment in {"none", "included", "carve_out"}:
        return treatment
    return "carve_out" if bool(getattr(request, "exclude_real_estate", False)) else "none"


def _scenario_provenance(
    gate: StructureEvidenceGate,
    *,
    consolidation_mode: str,
    subsidiary_run_ids: list[str],
    elimination_provenance: object,
) -> dict[str, object]:
    evidence = gate.normalized or {}
    provenance = evidence.get("provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    return {
        "eligible": gate.scenario_eligible,
        "source": "valuation_iq_holdings_consolidation" if gate.scenario_eligible else None,
        "consolidation_mode": consolidation_mode,
        "evidence_revision": provenance.get("revision"),
        "playbook_version": provenance.get("playbook_version"),
        "subsidiary_run_ids": subsidiary_run_ids,
        "elimination_provenance": elimination_provenance,
        "reasons": list(gate.reasons),
    }


def _standalone_evidence_result(
    gate: StructureEvidenceGate,
    *,
    locale: str,
) -> dict[str, object]:
    result: dict[str, object] = {
        "applied": False,
        "mode": "standalone",
        "consolidation_mode": "standalone",
        "entity_count": 1,
        "subsidiary_count": 0,
        "subsidiary_run_ids": [],
        "eliminations": {},
        "elimination_provenance": {},
        "structure_evidence_gate": gate.to_payload(),
        "expert_review_required": gate.expert_review_required,
    }
    result["scenario_provenance"] = _scenario_provenance(
        gate,
        consolidation_mode="standalone",
        subsidiary_run_ids=[],
        elimination_provenance={},
    )
    result["report_context"] = build_consolidation_report_context(result, locale=locale)
    return result


def _consolidation_mode(result: Mapping[str, object]) -> str:
    mode = "full" if str(result.get("mode")).strip().lower() == "full" else "pro_rata"
    return f"consolidated_{mode}"


def _real_estate_rent_delta(current_year_data: YearDataInput) -> Decimal:
    metadata = getattr(current_year_data, "ebitda_normalization_metadata", None)
    if not isinstance(metadata, Mapping):
        return Decimal("0")

    delta = Decimal("0")
    adjustments = metadata.get("adjustments")
    if not isinstance(adjustments, list):
        return delta
    for adjustment in adjustments:
        if not isinstance(adjustment, Mapping):
            continue
        if adjustment.get("category") != "real_estate_carve_out":
            continue
        amount = _decimal_or_none(adjustment.get("amount"))
        if amount is None:
            continue
        delta -= abs(amount)
    return delta


def _build_consolidated_current_year(
    current_year_data: YearDataInput,
    lines: Mapping[str, object],
) -> YearDataInput:
    year_data = current_year_data.model_dump()
    real_estate_rent_delta = _real_estate_rent_delta(current_year_data)

    for line, field in _CONSOLIDATED_LINE_TO_YEAR_FIELD.items():
        value = _decimal_or_none(lines.get(line))
        if value is not None:
            year_data[field] = (
                value + real_estate_rent_delta
                if line == "ebitda" and real_estate_rent_delta != 0
                else value
            )

    if real_estate_rent_delta != 0:
        metadata = year_data.get("ebitda_normalization_metadata")
        if isinstance(metadata, dict):
            raw_consolidated_ebitda = _decimal_or_none(lines.get("ebitda"))
            if raw_consolidated_ebitda is not None:
                metadata = dict(metadata)
                metadata["reported_ebitda"] = raw_consolidated_ebitda
                metadata["normalized_ebitda"] = raw_consolidated_ebitda + real_estate_rent_delta
                year_data["ebitda_normalization_metadata"] = metadata

    net_debt = _decimal_or_none(lines.get("net_debt"))
    if net_debt is not None:
        if net_debt >= 0:
            year_data["total_debt"] = net_debt
            year_data["cash"] = Decimal("0")
        else:
            year_data["total_debt"] = Decimal("0")
            year_data["cash"] = abs(net_debt)

    return YearDataInput(**year_data)


def apply_holdings_consolidation_to_request(
    request: ValuationRequest,
    *,
    logger: Any | None = None,
) -> tuple[ValuationRequest, dict[str, object] | None]:
    """Return a request whose current-year data reflects the consolidated group.

    The hook is intentionally inert for standalone valuations and for malformed
    empty envelopes. When subsidiaries are present, invalid ownership structures
    fail before valuation so the user never receives a silently-clamped group
    valuation.
    """
    payload = getattr(request, "holdings_consolidation", None)
    if payload is None:
        return request, standalone_holdings_fallback(getattr(request, "business_context", None))

    parent = _payload_mapping(payload, "parent")
    subsidiaries = _payload_sequence(payload, "subsidiaries")
    if parent is None or not subsidiaries:
        return request, None

    subsidiary_run_ids = _uuid_strings(getattr(payload, "subsidiary_run_ids", None))
    valuation_case = _payload_mapping(request, "valuation_case") or {}
    evidence_gate = evaluate_structure_evidence(
        getattr(request, "business_context", None),
        holdings_entity_ids=_entity_source_ids(parent, subsidiaries),
        subsidiary_count=len(subsidiaries),
        subsidiary_run_ids=subsidiary_run_ids,
        real_estate_treatment=_real_estate_treatment(request),
        intercompany_entries_present=bool(
            _payload_mapping(payload, "eliminations")
            or _payload_sequence(payload, "intercompany_transactions")
        ),
        holdings_ownership=_holdings_ownership(parent, subsidiaries),
        parent_entity_id=_entity_source_id(parent),
        aggregation_basis=str(getattr(payload, "aggregation_basis", None) or "legal_group"),
        consolidation_mode=str(getattr(payload, "mode", None) or "pro_rata"),
        allow_common_owner_sotp=False,
        assembly_provenance=_payload_mapping(payload, "assembly_provenance"),
        valuation_currency=str(getattr(request, "currency", None) or "") or None,
        entity_report_bindings=_entity_report_bindings(parent, subsidiaries),
        holdings_revision_id=(
            str(valuation_case["holdings_revision_id"])
            if isinstance(valuation_case.get("holdings_revision_id"), str)
            else None
        ),
        accepted_holdings_decision_ids=_accepted_holdings_decision_ids(valuation_case),
    )
    if not evidence_gate.consolidation_allowed:
        if logger is not None:
            logger.warning(
                "Holding consolidation kept standalone by structure-evidence gate",
                extra={
                    "company": getattr(request, "company_name", None),
                    "reasons": list(evidence_gate.reasons),
                },
            )
        return (
            request,
            _standalone_evidence_result(
                evidence_gate,
                locale=str(getattr(request, "locale", None) or "nl"),
            ),
        )

    try:
        result = consolidate_holding_entities(
            parent=parent,
            subsidiaries=subsidiaries,
            eliminations=_payload_mapping(payload, "eliminations"),
            intercompany_transactions=_payload_sequence(payload, "intercompany_transactions"),
            mode=str(getattr(payload, "mode", None) or "pro_rata"),
            # The tolerant library mode exists for internal UI preflight only.
            # A valuation request must never opt out of ownership validation.
            require_valid=True,
        )
    except HoldingConsolidationInputError as exc:
        if logger is not None:
            logger.error(
                "[BET-293] Holding consolidation validation failed",
                extra={
                    "validation": exc.validation,
                    "company": getattr(request, "company_name", None),
                },
            )
        raise

    lines = result.get("lines")
    consolidated_current_year = _build_consolidated_current_year(
        request.current_year_data,
        lines if isinstance(lines, Mapping) else {},
    )
    report_context = build_consolidation_report_context(
        result,
        locale=str(getattr(request, "locale", None) or "nl"),
    )
    consolidation_result = {
        **result,
        "applied": True,
        "report_context": report_context,
        "consolidation_mode": _consolidation_mode(result),
        "subsidiary_run_ids": subsidiary_run_ids,
        "structure_evidence_gate": evidence_gate.to_payload(),
        "expert_review_required": evidence_gate.expert_review_required,
    }
    consolidation_result["scenario_provenance"] = _scenario_provenance(
        evidence_gate,
        consolidation_mode=str(consolidation_result["consolidation_mode"]),
        subsidiary_run_ids=subsidiary_run_ids,
        elimination_provenance=consolidation_result.get("elimination_provenance", {}),
    )

    if logger is not None:
        logger.info(
            "[BET-293] Applied holdings consolidation to valuation request",
            extra={
                "company": getattr(request, "company_name", None),
                "mode": consolidation_result["consolidation_mode"],
                "entity_count": consolidation_result.get("entity_count"),
                "subsidiary_count": consolidation_result.get("subsidiary_count"),
            },
        )

    return (
        request.model_copy(
            update={
                "current_year_data": consolidated_current_year,
                "revenue": consolidated_current_year.revenue,
            }
        ),
        consolidation_result,
    )
