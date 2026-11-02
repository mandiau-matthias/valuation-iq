"""Deterministic holding-company consolidation for the stateless contract."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from src.api.schemas.stateless_api import CalculateRequest, TriageFlag
from src.services.holding_consolidation import (
    HoldingConsolidationInputError,
    consolidate_holding_entities,
)
from src.services.holdings_fallback import standalone_holdings_fallback
from src.services.reports.stateless_bridge_adjustments import (
    resolve_stateless_bridge_adjustments,
)
from src.services.reports.stateless_holdings_entity_value import (
    CanonicalChildRunError as _CanonicalChildRunError,
)
from src.services.reports.stateless_holdings_entity_value import (
    entity_sotp_value as _entity_sotp_value,
)
from src.services.reports.stateless_holdings_governance import (
    assumption_governance as _assumption_governance,
)
from src.services.reports.stateless_holdings_governance import (
    consolidation_governance_issues as _consolidation_governance_issues,
)
from src.services.reports.stateless_holdings_governance import (
    unpriced_assumption as _unpriced_assumption,
)
from src.services.structure_evidence import StructureEvidenceGate, evaluate_structure_evidence
from src.utils.decimal_helpers import safe_decimal_or_zero

_LINE_TO_YEAR_FIELD = {
    "revenue": "revenue",
    "ebitda": "ebitda",
    "net_income": "net_income",
    "total_assets": "total_assets",
    "equity": "total_equity",
}


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _entity_lines(entity: Mapping[str, object]) -> Mapping[str, object]:
    for key in ("lines", "financial_lines", "financials"):
        nested = entity.get(key)
        if isinstance(nested, Mapping):
            return nested
    return entity


def _entity_source_id(entity: Mapping[str, object]) -> str | None:
    for key in ("id", "entity_id", "company_id"):
        value = entity.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _entity_report_bindings(
    parent: Mapping[str, object],
    subsidiaries: list[object],
) -> list[dict[str, object]]:
    bindings: list[dict[str, object]] = []
    for entity in (parent, *(_mapping(raw) for raw in subsidiaries)):
        bindings.append(
            {
                "entity_id": _entity_source_id(entity),
                "valuation_report_id": entity.get("valuation_report_id"),
                "valuation_evidence_revision_id": entity.get("evidence_revision_id"),
            }
        )
    return bindings


def _accepted_holdings_decision_ids(request: CalculateRequest) -> list[str]:
    valuation_case = request.valuation_case
    if valuation_case is None:
        return []
    return sorted(
        {
            decision.decision_id
            for decision in valuation_case.authoritative_input_decisions
            if decision.field_key.startswith("holdings_consolidation.")
            and decision.state in {"accepted", "edited"}
        }
    )


def _holdings_ownership(
    parent: Mapping[str, object],
    subsidiaries: list[object],
) -> dict[str, object]:
    ownership: dict[str, object] = {}
    parent_id = _entity_source_id(parent)
    if parent_id is not None and parent.get("parent_ownership_pct") is not None:
        ownership[parent_id] = parent.get("parent_ownership_pct")
    for raw in subsidiaries:
        subsidiary = _mapping(raw)
        entity_id = _entity_source_id(subsidiary)
        if entity_id is None:
            continue
        for key in ("ownership_pct", "ownership_pct_in_parent", "parent_ownership_pct"):
            if subsidiary.get(key) is not None:
                ownership[entity_id] = subsidiary.get(key)
                break
    return ownership


def _structure_evidence_standalone(
    request: CalculateRequest,
    payload: object,
    gate: StructureEvidenceGate,
) -> tuple[CalculateRequest, dict[str, object], list[TriageFlag]]:
    result = {
        "applied": False,
        "mode": "standalone",
        "consolidation_mode": "standalone",
        "reason": "structure_evidence_rejected",
        "subsidiary_run_ids": list(getattr(payload, "subsidiary_run_ids", None) or []),
        "calculation_authority": "valuation_iq",
        "structure_evidence_gate": gate.to_payload(),
        "aggregation_basis": str(getattr(payload, "aggregation_basis", None) or "legal_group"),
    }
    return (
        request,
        result,
        [
            TriageFlag(
                field="holdings_consolidation",
                issue="structure_evidence_rejected_standalone_fallback",
                severity="warning",
                value={"reasons": list(gate.reasons)},
            )
        ],
    )


def _first_decimal(*values: object) -> Decimal | None:
    for value in values:
        if value is not None and value != "":
            try:
                parsed = value if isinstance(value, Decimal) else Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if parsed.is_finite():
                return parsed
    return None


def _first_decimal_field(
    row: Mapping[str, object],
    *field_names: str,
) -> tuple[str | None, Decimal | None]:
    for field_name in field_names:
        if field_name not in row:
            continue
        parsed = _first_decimal(row.get(field_name))
        if parsed is not None:
            return field_name, parsed
    return None, None


def _build_holding_sotp(
    payload: object,
    *,
    parent_currency: str | None,
    request: CalculateRequest,
    consolidation_result: Mapping[str, object],
) -> dict[str, object]:
    parent = _mapping(getattr(payload, "parent", None))
    subsidiaries = list(getattr(payload, "subsidiaries", None) or [])
    try:
        parent_row, parent_unpriced = _entity_sotp_value(
            parent,
            default_name="Parent",
            parent_currency=parent_currency,
            request=request,
            entity_path="holdings_consolidation.parent",
        )
    except _CanonicalChildRunError as exc:
        return {
            "available": False,
            "mode": "consolidated_operating_fallback",
            "reason": "canonical_child_run_rejected",
            "missing": [f"parent.valuation_run.{exc.code}"],
            "canonical_run_errors": [{"entity": "parent", "code": exc.code, "message": str(exc)}],
        }
    if parent_row is None:
        return {
            "available": False,
            "mode": "consolidated_operating_fallback",
            "reason": (
                "priced_assumption_governance_missing"
                if parent_unpriced
                else "parent_value_basis_missing"
            ),
            "missing": [row["field"] for row in parent_unpriced],
            "unpriced_assumptions": parent_unpriced,
        }

    parent_basis = str(parent_row.get("value_basis") or "")
    parent_participations_excluded = parent.get("participations_excluded_from_value") is True
    aggregation_basis = str(getattr(payload, "aggregation_basis", None) or "legal_group")
    parent_ownership = (
        _first_decimal(parent.get("parent_ownership_pct"))
        if aggregation_basis == "common_owner_sotp"
        else Decimal("100")
    )
    if parent_ownership is None or parent_ownership < 0 or parent_ownership > 100:
        return {
            "available": False,
            "mode": "standalone",
            "reason": "parent_ownership_pct_missing",
            "missing": ["parent.parent_ownership_pct"],
        }
    rows = [{**parent_row, "ownership_pct": parent_ownership}]
    missing: list[str] = []
    canonical_run_errors: list[dict[str, str]] = []
    unpriced_assumptions: list[dict[str, object]] = []
    participation_elimination = Decimal("0")
    for index, raw in enumerate(subsidiaries, start=1):
        subsidiary = _mapping(raw)
        try:
            row, entity_unpriced = _entity_sotp_value(
                subsidiary,
                default_name=f"Subsidiary {index}",
                parent_currency=parent_currency,
                request=request,
                entity_path=f"holdings_consolidation.subsidiaries[{index - 1}]",
            )
        except _CanonicalChildRunError as exc:
            missing.append(f"subsidiary_{index}.valuation_run.{exc.code}")
            canonical_run_errors.append(
                {
                    "entity": f"subsidiary_{index}",
                    "code": exc.code,
                    "message": str(exc),
                }
            )
            continue
        ownership = _first_decimal(
            subsidiary.get("ownership_pct"),
            subsidiary.get("ownership_pct_in_parent"),
            subsidiary.get("parent_ownership_pct"),
        )
        if row is None:
            missing.append(f"subsidiary_{index}.value_basis")
            unpriced_assumptions.extend(entity_unpriced)
            continue
        if ownership is None or ownership < 0 or ownership > 100:
            missing.append(f"subsidiary_{index}.ownership_pct")
            continue
        if parent_basis in {"equity", "canonical_run"} and not parent_participations_excluded:
            book_value_field, book_value = _first_decimal_field(
                subsidiary,
                "participation_book_value",
            )
            if book_value is None or book_value_field is None:
                missing.append(f"subsidiary_{index}.participation_book_value")
                continue
            book_value_path = f"holdings_consolidation.subsidiaries[{index - 1}].{book_value_field}"
            book_value_verdict = _assumption_governance(
                request,
                field_name=book_value_field,
                field_path=book_value_path,
                value=book_value,
                monetary=True,
                parent_currency=parent_currency,
            )
            if not book_value_verdict.priced:
                missing.append(f"subsidiary_{index}.participation_book_value_governance")
                unpriced_assumptions.append(
                    _unpriced_assumption(
                        field_path=book_value_path,
                        value=book_value,
                        verdict=book_value_verdict,
                    )
                )
                continue
            participation_elimination += book_value
        rows.append({**row, "ownership_pct": ownership})

    if missing or len(rows) != len(subsidiaries) + 1:
        return {
            "available": False,
            "mode": "consolidated_operating_fallback",
            "reason": (
                "priced_assumption_governance_missing"
                if unpriced_assumptions
                else "entity_sotp_inputs_incomplete"
            ),
            "missing": sorted(set(missing)),
            "candidate_rows": rows,
            "canonical_run_errors": canonical_run_errors,
            "unpriced_assumptions": unpriced_assumptions,
        }

    explicit_eliminations = _mapping(getattr(payload, "eliminations", None))
    elimination_provenance = _mapping(consolidation_result.get("elimination_provenance"))
    operating_eliminations = {
        key: safe_decimal_or_zero(_mapping(elimination_provenance.get(key)).get("amount"))
        for key in ("revenue", "ebitda", "net_income")
        if safe_decimal_or_zero(_mapping(elimination_provenance.get(key)).get("amount")) != 0
    }
    has_sotp_value_impact = "sotp_value_impact" in explicit_eliminations
    if operating_eliminations and not has_sotp_value_impact:
        return {
            "available": False,
            "mode": "consolidated_operating_fallback",
            "reason": "operating_elimination_value_impact_unverified",
            "missing": ["eliminations.sotp_value_impact_governance"],
            "operating_eliminations": operating_eliminations,
        }
    sotp_value_impact = abs(safe_decimal_or_zero(explicit_eliminations.get("sotp_value_impact")))
    if has_sotp_value_impact:
        field_path = "holdings_consolidation.eliminations.sotp_value_impact"
        verdict = _assumption_governance(
            request,
            field_name="sotp_value_impact",
            field_path=field_path,
            value=sotp_value_impact,
            monetary=True,
            parent_currency=parent_currency,
        )
        if not verdict.priced:
            return {
                "available": False,
                "mode": "consolidated_operating_fallback",
                "reason": "operating_elimination_value_impact_unverified",
                "missing": [field_path],
                "operating_eliminations": operating_eliminations,
                "unpriced_assumptions": [
                    _unpriced_assumption(
                        field_path=field_path,
                        value=sotp_value_impact,
                        verdict=verdict,
                    )
                ],
            }
    explicit_participation_elimination = _first_decimal(
        explicit_eliminations.get("participations"),
        explicit_eliminations.get("investment_in_subsidiaries"),
    )
    if explicit_participation_elimination is not None:
        explicit_participation_field = (
            "participations"
            if explicit_eliminations.get("participations") is not None
            else "investment_in_subsidiaries"
        )
        explicit_participation_elimination = abs(explicit_participation_elimination)
        field_path = f"holdings_consolidation.eliminations.{explicit_participation_field}"
        verdict = _assumption_governance(
            request,
            field_name=explicit_participation_field,
            field_path=field_path,
            value=explicit_participation_elimination,
            monetary=True,
            parent_currency=parent_currency,
        )
        if not verdict.priced:
            return {
                "available": False,
                "mode": "consolidated_operating_fallback",
                "reason": "priced_assumption_governance_missing",
                "missing": [field_path],
                "unpriced_assumptions": [
                    _unpriced_assumption(
                        field_path=field_path,
                        value=explicit_participation_elimination,
                        verdict=verdict,
                    )
                ],
            }
        participation_elimination = explicit_participation_elimination
    equity_elimination = safe_decimal_or_zero(explicit_eliminations.get("equity_value"))
    if equity_elimination != 0:
        equity_elimination = abs(equity_elimination)
        field_path = "holdings_consolidation.eliminations.equity_value"
        verdict = _assumption_governance(
            request,
            field_name="equity_value",
            field_path=field_path,
            value=equity_elimination,
            monetary=True,
            parent_currency=parent_currency,
        )
        if not verdict.priced:
            return {
                "available": False,
                "mode": "consolidated_operating_fallback",
                "reason": "priced_assumption_governance_missing",
                "missing": [field_path],
                "unpriced_assumptions": [
                    _unpriced_assumption(
                        field_path=field_path,
                        value=equity_elimination,
                        verdict=verdict,
                    )
                ],
            }

    enterprise_value_available = all(row.get("enterprise_value_available") is True for row in rows)
    enterprise_low = -sotp_value_impact if enterprise_value_available else None
    enterprise_mid = -sotp_value_impact if enterprise_value_available else None
    enterprise_high = -sotp_value_impact if enterprise_value_available else None
    equity_low = -participation_elimination - equity_elimination - sotp_value_impact
    equity_mid = -participation_elimination - equity_elimination - sotp_value_impact
    equity_high = -participation_elimination - equity_elimination - sotp_value_impact
    priced_rows: list[dict[str, object]] = []
    contains_embedded_owner_dependency = False
    for row in rows:
        ownership = safe_decimal_or_zero(row.get("ownership_pct")) / Decimal("100")
        enterprise_low_contribution = (
            safe_decimal_or_zero(row.get("enterprise_value_low")) * ownership
            if enterprise_value_available
            else None
        )
        enterprise_mid_contribution = (
            safe_decimal_or_zero(row.get("enterprise_value_mid")) * ownership
            if enterprise_value_available
            else None
        )
        enterprise_high_contribution = (
            safe_decimal_or_zero(row.get("enterprise_value_high")) * ownership
            if enterprise_value_available
            else None
        )
        low_contribution = safe_decimal_or_zero(row.get("equity_value_low")) * ownership
        mid_contribution = safe_decimal_or_zero(row.get("equity_value_mid")) * ownership
        high_contribution = safe_decimal_or_zero(row.get("equity_value_high")) * ownership
        if safe_decimal_or_zero(row.get("embedded_owner_dependency_adjustment")) != 0:
            contains_embedded_owner_dependency = True
        if (
            enterprise_low is not None
            and enterprise_mid is not None
            and enterprise_high is not None
            and enterprise_low_contribution is not None
            and enterprise_mid_contribution is not None
            and enterprise_high_contribution is not None
        ):
            enterprise_low += enterprise_low_contribution
            enterprise_mid += enterprise_mid_contribution
            enterprise_high += enterprise_high_contribution
        equity_low += low_contribution
        equity_mid += mid_contribution
        equity_high += high_contribution
        priced_rows.append(
            {
                **row,
                "enterprise_value_low_contribution": enterprise_low_contribution,
                "enterprise_value_mid_contribution": enterprise_mid_contribution,
                # Backward-compatible alias for pre-range SOTP consumers.
                "enterprise_value_contribution": enterprise_mid_contribution,
                "enterprise_value_high_contribution": enterprise_high_contribution,
                "equity_value_low_contribution": low_contribution,
                "equity_value_mid_contribution": mid_contribution,
                "equity_value_high_contribution": high_contribution,
            }
        )

    return {
        "available": True,
        "version": "holding_sotp.v2",
        "mode": "true_sotp",
        "value_basis": "equity",
        "entity_rows": priced_rows,
        "participation_book_value_elimination": participation_elimination,
        "other_equity_value_elimination": equity_elimination,
        "operating_eliminations": operating_eliminations,
        "sotp_value_impact_elimination": sotp_value_impact,
        "enterprise_value_available": enterprise_value_available,
        "enterprise_value_low": (
            max(Decimal("0"), min(enterprise_low, enterprise_high))
            if enterprise_low is not None and enterprise_high is not None
            else None
        ),
        "enterprise_value_mid": (
            max(Decimal("0"), enterprise_mid) if enterprise_mid is not None else None
        ),
        "enterprise_value_high": (
            max(Decimal("0"), max(enterprise_low, enterprise_high))
            if enterprise_low is not None and enterprise_high is not None
            else None
        ),
        "equity_value_low": max(Decimal("0"), min(equity_low, equity_high)),
        "equity_value_mid": max(Decimal("0"), equity_mid),
        "equity_value_high": max(Decimal("0"), max(equity_low, equity_high)),
        "calculation_authority": "valuation_iq",
        "currency": parent_currency,
        "contains_embedded_owner_dependency": contains_embedded_owner_dependency,
    }


def apply_stateless_holdings_consolidation(
    request: CalculateRequest,
) -> tuple[CalculateRequest, dict[str, object] | None, list[TriageFlag]]:
    """Apply ownership and eliminations once; invalid structures remain standalone."""
    payload = request.holdings_consolidation
    if payload is None or not payload.subsidiaries:
        return request, standalone_holdings_fallback(request.business_context), []

    parent = _mapping(payload.parent)
    subsidiaries = list(payload.subsidiaries)
    parent_entity_id = _entity_source_id(parent)
    entity_ids = [
        entity_id
        for raw in (parent, *subsidiaries)
        if (entity_id := _entity_source_id(_mapping(raw))) is not None
    ]
    evidence_gate = evaluate_structure_evidence(
        request.business_context,
        holdings_entity_ids=entity_ids,
        subsidiary_count=len(subsidiaries),
        subsidiary_run_ids=list(payload.subsidiary_run_ids),
        real_estate_treatment=str(getattr(request, "real_estate_treatment", None) or "none"),
        intercompany_entries_present=bool(
            payload.eliminations or payload.intercompany_transactions
        ),
        holdings_ownership=_holdings_ownership(parent, subsidiaries),
        parent_entity_id=parent_entity_id,
        aggregation_basis=payload.aggregation_basis,
        consolidation_mode=payload.mode,
        allow_common_owner_sotp=True,
        assembly_provenance=_mapping(payload.assembly_provenance),
        valuation_currency=request.currency,
        entity_report_bindings=_entity_report_bindings(parent, subsidiaries),
        holdings_revision_id=(
            request.valuation_case.holdings_revision_id if request.valuation_case else None
        ),
        accepted_holdings_decision_ids=_accepted_holdings_decision_ids(request),
    )
    if not evidence_gate.consolidation_allowed:
        return _structure_evidence_standalone(request, payload, evidence_gate)

    consolidation_governance_issues = _consolidation_governance_issues(
        request,
        payload=payload,
        parent_currency=request.currency,
    )
    if consolidation_governance_issues:
        fields = [str(row["field"]) for row in consolidation_governance_issues]
        sotp = {
            "available": False,
            "mode": "standalone",
            "reason": "priced_assumption_governance_missing",
            "missing": fields,
            "unpriced_assumptions": consolidation_governance_issues,
        }
        return (
            request,
            {
                "applied": False,
                "mode": "standalone",
                "consolidation_mode": "standalone",
                "reason": "priced_assumption_governance_missing",
                "scenario_only": True,
                "unpriced_assumptions": consolidation_governance_issues,
                "subsidiary_run_ids": list(payload.subsidiary_run_ids),
                "calculation_authority": "valuation_iq",
                "sotp": sotp,
            },
            [
                TriageFlag(
                    field="holdings_consolidation",
                    issue="ungoverned_holdings_assumptions_excluded_from_priced_calculation",
                    severity="warning",
                    value={"fields": fields, "assumptions": consolidation_governance_issues},
                )
            ],
        )

    try:
        result = consolidate_holding_entities(
            parent=payload.parent,
            subsidiaries=payload.subsidiaries,
            eliminations=payload.eliminations,
            intercompany_transactions=payload.intercompany_transactions,
            mode=payload.mode,
            require_valid=True,
        )
    except (HoldingConsolidationInputError, TypeError, ValueError) as exc:
        validation = getattr(exc, "validation", None)
        return (
            request,
            {
                "applied": False,
                "mode": "standalone",
                "reason": "invalid_holding_structure",
                "validation": validation if isinstance(validation, Mapping) else None,
            },
            [
                TriageFlag(
                    field="holdings_consolidation",
                    issue="invalid_holding_structure_standalone_fallback",
                    severity="warning",
                    value=validation,
                )
            ],
        )

    lines = result.get("lines")
    if not isinstance(lines, Mapping):
        return request, {**result, "applied": False, "mode": "standalone"}, []

    updates: dict[str, object] = {}
    for line, field in _LINE_TO_YEAR_FIELD.items():
        if lines.get(line) is not None:
            updates[field] = safe_decimal_or_zero(lines.get(line))

    if "ebitda" in updates:
        updates["reported_ebitda"] = updates["ebitda"]
        updates["normalized_ebitda"] = None
        updates["ebitda_normalized"] = False
        updates["ebitda_normalization_metadata"] = {
            "reported_ebitda": updates["ebitda"],
            "normalization_scope": "consolidated_group",
            "adjustments": [],
        }

    net_debt = lines.get("net_debt")
    if net_debt is not None:
        net_debt_dec = safe_decimal_or_zero(net_debt)
        updates["total_debt"] = max(net_debt_dec, Decimal("0"))
        updates["cash"] = abs(min(net_debt_dec, Decimal("0")))

    common_owner_sotp = payload.aggregation_basis == "common_owner_sotp"
    updated_current = request.current_year.model_copy(update=updates)
    updated_request = (
        request
        if common_owner_sotp
        else request.model_copy(update={"current_year": updated_current})
    )
    sotp = _build_holding_sotp(
        payload,
        parent_currency=request.currency,
        request=request,
        consolidation_result=result,
    )
    group_bridge = resolve_stateless_bridge_adjustments(request)
    if sotp.get("available"):
        entity_rows = sotp.get("entity_rows")
        has_entity_bridge = isinstance(entity_rows, list) and any(
            safe_decimal_or_zero(row.get("tax_adjustment")) != Decimal("0")
            or safe_decimal_or_zero(row.get("other_balance_sheet_adjustment")) != Decimal("0")
            for row in entity_rows
            if isinstance(row, Mapping)
        )
        if has_entity_bridge and group_bridge.total != Decimal("0"):
            sotp = {
                **sotp,
                "available": False,
                "mode": "consolidated_operating_fallback",
                "reason": "ambiguous_group_and_entity_bridge_adjustments",
            }
        elif group_bridge.total != Decimal("0"):
            sotp = {
                **sotp,
                "equity_value_low": max(
                    Decimal("0"),
                    safe_decimal_or_zero(sotp.get("equity_value_low")) + group_bridge.total,
                ),
                "equity_value_mid": max(
                    Decimal("0"),
                    safe_decimal_or_zero(sotp.get("equity_value_mid")) + group_bridge.total,
                ),
                "equity_value_high": max(
                    Decimal("0"),
                    safe_decimal_or_zero(sotp.get("equity_value_high")) + group_bridge.total,
                ),
                "group_equity_bridge": group_bridge.to_payload(),
            }
    sotp_flags: list[TriageFlag] = []
    sotp_entity_rows = sotp.get("entity_rows")
    if not isinstance(sotp_entity_rows, list):
        sotp_entity_rows = []
    if not sotp.get("available"):
        unpriced_assumptions = sotp.get("unpriced_assumptions")
        sotp_flags.append(
            TriageFlag(
                field="holdings_consolidation",
                issue=(
                    "ungoverned_sotp_assumptions_excluded_from_priced_value"
                    if unpriced_assumptions
                    else "true_sotp_inputs_incomplete_consolidated_fallback"
                ),
                severity="warning",
                value=unpriced_assumptions or sotp.get("missing") or sotp.get("reason"),
            )
        )
    elif any(
        row.get("unpriced_entity_adjustments")
        for row in sotp_entity_rows
        if isinstance(row, Mapping)
    ):
        sotp_flags.append(
            TriageFlag(
                field="holdings_consolidation",
                issue="unverified_entity_bridge_adjustments_excluded_from_sotp",
                severity="warning",
            )
        )
    return (
        updated_request,
        {
            **result,
            "applied": True,
            "consolidation_mode": (
                "sotp_only_common_owner" if common_owner_sotp else f"consolidated_{payload.mode}"
            ),
            "aggregation_basis": payload.aggregation_basis,
            "subsidiary_run_ids": list(payload.subsidiary_run_ids),
            "calculation_authority": "valuation_iq",
            "structure_evidence_gate": evidence_gate.to_payload(),
            "assembly_provenance": payload.assembly_provenance,
            "sotp": sotp,
        },
        sotp_flags,
    )
