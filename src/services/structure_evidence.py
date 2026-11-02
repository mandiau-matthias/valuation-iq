"""Fail-closed Belgian structure-evidence gate for valuation scenarios.

Titan carries the long-lived decision context. ValuationIQ only reads the
versioned ``business_context.structure_evidence_v1`` block to decide whether a
simple holding consolidation may support a monetary scenario. The evidence
never changes valuation inputs by itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

STRUCTURE_EVIDENCE_KEY = "structure_evidence_v1"
STRUCTURE_EVIDENCE_CONTRACT = "be_structure_evidence_v1"

_STATUSES = {"missing", "draft", "advisor_reviewed", "expert_review_required"}
_ROLES = {"holding", "operating", "property", "ip", "management", "other"}
_PERIMETER_STATUSES = {"unknown", "draft", "advisor_reviewed"}
_REAL_ESTATE_TREATMENTS = {
    "none",
    "included",
    "carve_out",
    "owned_included",
    "owned_excluded",
    "leased",
    "unresolved",
}
_AUTHORS = {"registry", "owner", "advisor", "system"}


@dataclass(frozen=True)
class StructureEvidenceGate:
    """Normalized evidence plus deterministic consolidation/scenario gates."""

    present: bool
    normalized: dict[str, object] | None
    consolidation_allowed: bool
    scenario_eligible: bool
    expert_review_required: bool
    reasons: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "contract_version": STRUCTURE_EVIDENCE_CONTRACT,
            "present": self.present,
            "consolidation_allowed": self.consolidation_allowed,
            "scenario_eligible": self.scenario_eligible,
            "expert_review_required": self.expert_review_required,
            "reasons": list(self.reasons),
            "evidence": self.normalized,
        }


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _strict_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _percentage(value: object) -> float | None:
    if value is None:
        return None
    try:
        percentage = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not percentage.is_finite() or percentage < 0 or percentage > 100:
        return None
    return float(percentage)


def _text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item)) is not None]


def _valid_iso_timestamp(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return text


def _has_entity_cycle(entity_ids: set[str], links: Sequence[Mapping[str, object]]) -> bool:
    graph: dict[str, set[str]] = {entity_id: set() for entity_id in entity_ids}
    indegree = {entity_id: 0 for entity_id in entity_ids}
    for link in links:
        owner_id = _text(link.get("owner_id"))
        owned_id = _text(link.get("owned_entity_id"))
        if (
            owner_id is None
            or owned_id is None
            or owner_id not in entity_ids
            or owned_id not in entity_ids
        ):
            continue
        if owned_id not in graph[owner_id]:
            graph[owner_id].add(owned_id)
            indegree[owned_id] += 1

    pending = [entity_id for entity_id, degree in indegree.items() if degree == 0]
    visited = 0
    while pending:
        current = pending.pop()
        visited += 1
        for owned_id in graph[current]:
            indegree[owned_id] -= 1
            if indegree[owned_id] == 0:
                pending.append(owned_id)
    return visited != len(entity_ids)


def _connected_entities(
    entity_ids: set[str],
    links: Sequence[Mapping[str, object]],
) -> bool:
    if not entity_ids:
        return False
    graph: dict[str, set[str]] = {}
    for link in links:
        if link.get("confirmed") is not True:
            continue
        owner_id = _text(link.get("owner_id"))
        owned_id = _text(link.get("owned_entity_id"))
        if owner_id is None or owned_id is None:
            continue
        graph.setdefault(owner_id, set()).add(owned_id)
        graph.setdefault(owned_id, set()).add(owner_id)

    pending = [next(iter(entity_ids))]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        pending.extend(graph.get(current, ()))
    return entity_ids.issubset(visited)


def _connected_perimeter(
    perimeter_ids: set[str],
    entity_ids: set[str],
    links: Sequence[Mapping[str, object]],
) -> bool:
    if not perimeter_ids:
        return False
    if len(perimeter_ids) == 1:
        return True
    graph: dict[str, set[str]] = {entity_id: set() for entity_id in perimeter_ids}
    for link in links:
        if link.get("confirmed") is not True:
            continue
        owner_id = _text(link.get("owner_id"))
        owned_id = _text(link.get("owned_entity_id"))
        if owner_id in perimeter_ids and owned_id in perimeter_ids:
            graph[owner_id].add(owned_id)
            graph[owned_id].add(owner_id)

    pending = [next(iter(perimeter_ids))]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        pending.extend(graph[current])
    if visited == perimeter_ids:
        return True

    external_owners = {
        owner_id
        for link in links
        if link.get("confirmed") is True
        and (owner_id := _text(link.get("owner_id"))) is not None
        and owner_id not in entity_ids
    }
    return any(
        all(
            any(
                link.get("confirmed") is True
                and _text(link.get("owner_id")) == owner_id
                and _text(link.get("owned_entity_id")) == entity_id
                for link in links
            )
            for entity_id in perimeter_ids
        )
        for owner_id in external_owners
    )


def _ownership_matches(
    submitted: object,
    reviewed: object,
) -> bool:
    submitted_percentage = _percentage(submitted)
    reviewed_percentage = _percentage(reviewed)
    if submitted_percentage is None or reviewed_percentage is None:
        return False
    return Decimal(str(submitted_percentage)) == Decimal(str(reviewed_percentage))


def _uuid_strings_are_complete(values: Sequence[str], expected_count: int) -> bool:
    if expected_count <= 0:
        return len(values) == 0
    if len(values) != expected_count or len(set(values)) != expected_count:
        return False
    try:
        return all(str(UUID(value)) == value.lower() for value in values)
    except (ValueError, AttributeError):
        return False


def evaluate_structure_evidence(
    business_context: object,
    *,
    holdings_entity_ids: Sequence[str] = (),
    subsidiary_count: int = 0,
    subsidiary_run_ids: Sequence[str] = (),
    real_estate_treatment: str = "none",
    intercompany_entries_present: bool = False,
    holdings_ownership: Mapping[str, object] | None = None,
    parent_entity_id: str | None = None,
    aggregation_basis: str = "legal_group",
    consolidation_mode: str = "pro_rata",
    allow_common_owner_sotp: bool = False,
    assembly_provenance: Mapping[str, object] | None = None,
    valuation_currency: str | None = None,
    entity_report_bindings: Sequence[Mapping[str, object]] = (),
    holdings_revision_id: str | None = None,
    accepted_holdings_decision_ids: Sequence[str] = (),
) -> StructureEvidenceGate:
    """Validate evidence without allowing it to alter valuation arithmetic.

    Missing evidence and unsupported structures fail to standalone valuation.
    Draft simple groups may consolidate but cannot emit monetary scenarios.
    """
    context = _mapping(business_context)
    raw = context.get(STRUCTURE_EVIDENCE_KEY)
    if raw is None:
        return StructureEvidenceGate(
            present=False,
            normalized=None,
            consolidation_allowed=False,
            scenario_eligible=False,
            expert_review_required=False,
            reasons=("structure_evidence_missing",),
        )
    if not isinstance(raw, Mapping):
        return StructureEvidenceGate(
            present=True,
            normalized=None,
            consolidation_allowed=False,
            scenario_eligible=False,
            expert_review_required=True,
            reasons=("structure_evidence_invalid",),
        )

    reasons: list[str] = []
    blocking_reasons: list[str] = []

    contract_version = _text(raw.get("contract_version"))
    if contract_version != STRUCTURE_EVIDENCE_CONTRACT:
        blocking_reasons.append("structure_evidence_contract_unsupported")

    jurisdiction = (_text(raw.get("jurisdiction")) or "").upper()
    if jurisdiction != "BE":
        blocking_reasons.append("structure_evidence_non_be")

    status = _text(raw.get("status"))
    if status not in _STATUSES:
        blocking_reasons.append("structure_evidence_status_invalid")

    raw_entities = raw.get("entities")
    entity_rows = raw_entities if isinstance(raw_entities, list) else []
    entities: list[dict[str, object]] = []
    entity_ids: set[str] = set()
    role_counts = {role: 0 for role in _ROLES}
    if not 1 <= len(entity_rows) <= 5:
        blocking_reasons.append("structure_evidence_entity_count_unsupported")
    for raw_entity in entity_rows:
        entity = _mapping(raw_entity)
        entity_id = _text(entity.get("entity_id"))
        country_code = (_text(entity.get("country_code")) or "").upper()
        role = _text(entity.get("role"))
        if entity_id is None or entity_id in entity_ids:
            blocking_reasons.append("structure_evidence_entity_id_invalid")
            continue
        if country_code != "BE":
            blocking_reasons.append("structure_evidence_cross_border")
        if role not in _ROLES:
            blocking_reasons.append("structure_evidence_entity_role_invalid")
        else:
            role_counts[role] += 1
        entity_ids.add(entity_id)
        entities.append({"entity_id": entity_id, "country_code": country_code, "role": role})
    if role_counts["operating"] != 1:
        blocking_reasons.append("structure_evidence_operating_entity_count_unsupported")
    if role_counts["holding"] > 1:
        blocking_reasons.append("structure_evidence_holding_entity_count_unsupported")
    if any(role_counts[role] > 1 for role in ("property", "ip", "management")):
        blocking_reasons.append("structure_evidence_optional_entity_count_unsupported")
    if role_counts["other"]:
        blocking_reasons.append("structure_evidence_other_role_unsupported")

    raw_links = raw.get("ownership_links")
    link_rows = raw_links if isinstance(raw_links, list) else []
    links: list[dict[str, object]] = []
    for raw_link in link_rows:
        link = _mapping(raw_link)
        owner_id = _text(link.get("owner_id"))
        owned_entity_id = _text(link.get("owned_entity_id"))
        percentage = _percentage(link.get("percentage"))
        confirmed = _strict_bool(link.get("confirmed"))
        if owner_id is None or owned_entity_id not in entity_ids:
            blocking_reasons.append("structure_evidence_ownership_link_invalid")
            continue
        if link.get("percentage") is not None and percentage is None:
            blocking_reasons.append("structure_evidence_ownership_percentage_invalid")
        if percentage is None:
            blocking_reasons.append("structure_evidence_ownership_percentage_missing")
        if confirmed is not True:
            blocking_reasons.append("structure_evidence_ownership_link_unconfirmed")
        links.append(
            {
                "owner_id": owner_id,
                "owned_entity_id": owned_entity_id,
                "percentage": percentage,
                "confirmed": confirmed,
            }
        )
    if entity_ids and _has_entity_cycle(entity_ids, links):
        blocking_reasons.append("structure_evidence_ownership_cycle")
    linked_entities = {
        str(link["owned_entity_id"])
        for link in links
        if link.get("confirmed") is True and link.get("owned_entity_id") in entity_ids
    }
    if linked_entities != entity_ids:
        blocking_reasons.append("structure_evidence_ownership_links_incomplete")
    if not _connected_entities(entity_ids, links):
        blocking_reasons.append("structure_evidence_ownership_graph_disconnected")

    role_by_id = {str(entity["entity_id"]): entity.get("role") for entity in entities}
    holding_ids = {entity_id for entity_id, role in role_by_id.items() if role == "holding"}
    holding_id = next(iter(holding_ids), None)
    entity_owned_links = [
        link
        for link in links
        if link.get("confirmed") is True and link.get("owner_id") in entity_ids
    ]
    if holding_id is not None:
        if any(
            link.get("owner_id") != holding_id or link.get("owned_entity_id") == holding_id
            for link in entity_owned_links
        ) or any(
            not any(
                link.get("owner_id") == holding_id and link.get("owned_entity_id") == entity_id
                for link in links
            )
            for entity_id in entity_ids - {holding_id}
        ):
            blocking_reasons.append("structure_evidence_topology_unsupported")
    elif entity_owned_links:
        blocking_reasons.append("structure_evidence_topology_unsupported")

    signals_raw = _mapping(raw.get("signals"))
    real_estate_signal = _text(signals_raw.get("real_estate_treatment"))
    if real_estate_signal not in _REAL_ESTATE_TREATMENTS and real_estate_signal is not None:
        reasons.append("structure_evidence_real_estate_treatment_invalid")
    signals = {
        "ownership_confirmed": _strict_bool(signals_raw.get("ownership_confirmed")),
        "related_party_items": _strict_bool(signals_raw.get("related_party_items")),
        "real_estate_treatment": real_estate_signal,
        "intercompany_exposure": _strict_bool(signals_raw.get("intercompany_exposure")),
        "guarantee_exposure": _strict_bool(signals_raw.get("guarantee_exposure")),
        "transfer_restrictions": _strict_bool(signals_raw.get("transfer_restrictions")),
    }
    if any(value is None for key, value in signals.items() if key != "real_estate_treatment"):
        reasons.append("structure_evidence_signals_incomplete")

    consolidation_raw = _mapping(raw.get("consolidation"))
    consolidation = {
        "available": _strict_bool(consolidation_raw.get("available")),
        "eliminations_confirmed": _strict_bool(consolidation_raw.get("eliminations_confirmed")),
    }

    perimeter_raw = _mapping(raw.get("perimeter"))
    perimeter_status = _text(perimeter_raw.get("status"))
    perimeter_entity_ids = _text_list(perimeter_raw.get("entity_ids"))
    if perimeter_status not in _PERIMETER_STATUSES:
        reasons.append("structure_evidence_perimeter_status_invalid")
    perimeter_ids = set(perimeter_entity_ids)
    operating_ids = {entity_id for entity_id, role in role_by_id.items() if role == "operating"}
    if (
        not perimeter_entity_ids
        or len(perimeter_ids) != len(perimeter_entity_ids)
        or not perimeter_ids.issubset(entity_ids)
        or not operating_ids.issubset(perimeter_ids)
    ):
        blocking_reasons.append("structure_evidence_perimeter_invalid")
    elif not _connected_perimeter(perimeter_ids, entity_ids, links):
        blocking_reasons.append("structure_evidence_perimeter_disconnected")
    perimeter = {"status": perimeter_status, "entity_ids": perimeter_entity_ids}

    provenance_raw = _mapping(raw.get("provenance"))
    evidence_references = _text_list(provenance_raw.get("evidence_references"))
    provenance = {
        "revision": _text(provenance_raw.get("revision")),
        "author": _text(provenance_raw.get("author")),
        "observed_at": _valid_iso_timestamp(provenance_raw.get("observed_at")),
        "playbook_version": _text(provenance_raw.get("playbook_version")),
        "evidence_references": evidence_references,
    }
    if provenance["author"] not in _AUTHORS:
        reasons.append("structure_evidence_provenance_author_invalid")
    if status == "advisor_reviewed" and provenance["author"] != "advisor":
        blocking_reasons.append("structure_evidence_advisor_review_author_invalid")
    if (
        any(provenance[field] is None for field in ("revision", "observed_at", "playbook_version"))
        or not evidence_references
    ):
        reasons.append("structure_evidence_provenance_incomplete")

    expected_entity_ids = {item for item in holdings_entity_ids if item}
    if len(expected_entity_ids) != len(holdings_entity_ids) or expected_entity_ids != perimeter_ids:
        blocking_reasons.append("structure_evidence_holdings_entity_match_incomplete")
    if not _uuid_strings_are_complete(subsidiary_run_ids, subsidiary_count):
        blocking_reasons.append("structure_evidence_subsidiary_runs_incomplete")

    submitted_ownership = holdings_ownership or {}
    if aggregation_basis not in {"legal_group", "common_owner_sotp"}:
        blocking_reasons.append("structure_evidence_aggregation_basis_invalid")
    elif aggregation_basis == "legal_group":
        if holding_id is None or parent_entity_id != holding_id:
            blocking_reasons.append("structure_evidence_legal_group_parent_mismatch")
        for entity_id in expected_entity_ids - ({holding_id} if holding_id else set()):
            reviewed_links = [
                link
                for link in links
                if link.get("confirmed") is True
                and link.get("owner_id") == holding_id
                and link.get("owned_entity_id") == entity_id
            ]
            if len(reviewed_links) != 1 or not _ownership_matches(
                submitted_ownership.get(entity_id),
                reviewed_links[0].get("percentage") if reviewed_links else None,
            ):
                blocking_reasons.append("structure_evidence_ownership_percentage_mismatch")
                break
    else:
        if not allow_common_owner_sotp:
            blocking_reasons.append("structure_evidence_common_owner_sotp_path_unsupported")
        if holding_id is not None or role_by_id.get(parent_entity_id or "") != "operating":
            blocking_reasons.append("structure_evidence_common_owner_perimeter_invalid")
        external_owner_ids = {
            owner_id
            for link in links
            if link.get("confirmed") is True
            and (owner_id := _text(link.get("owner_id"))) is not None
            and owner_id not in entity_ids
        }
        matching_owner_ids = {
            owner_id
            for owner_id in external_owner_ids
            if all(
                any(
                    link.get("confirmed") is True
                    and link.get("owner_id") == owner_id
                    and link.get("owned_entity_id") == entity_id
                    and _ownership_matches(
                        submitted_ownership.get(entity_id),
                        link.get("percentage"),
                    )
                    for link in links
                )
                for entity_id in expected_entity_ids
            )
        }
        if len(matching_owner_ids) != 1:
            blocking_reasons.append("structure_evidence_common_owner_ownership_mismatch")

    if consolidation_mode != "pro_rata":
        blocking_reasons.append("structure_evidence_full_consolidation_control_unverified")

    normalized_treatment = (
        real_estate_treatment if real_estate_treatment in _REAL_ESTATE_TREATMENTS else "none"
    )
    if real_estate_signal is not None and real_estate_signal != normalized_treatment:
        reasons.append("structure_evidence_real_estate_treatment_mismatch")

    if status != "advisor_reviewed":
        blocking_reasons.append("structure_evidence_not_advisor_reviewed")
    if perimeter_status != "advisor_reviewed":
        blocking_reasons.append("structure_evidence_perimeter_not_advisor_reviewed")
    if signals["ownership_confirmed"] is not True:
        blocking_reasons.append("structure_evidence_ownership_unconfirmed")
    if consolidation["available"] is not True:
        blocking_reasons.append("structure_evidence_consolidation_unavailable")
    if (
        signals["intercompany_exposure"] is True
        and consolidation["eliminations_confirmed"] is not True
    ):
        reasons.append("structure_evidence_eliminations_unconfirmed")
    if intercompany_entries_present and signals["intercompany_exposure"] is not True:
        blocking_reasons.append("structure_evidence_intercompany_exposure_mismatch")
    if intercompany_entries_present and consolidation["eliminations_confirmed"] is not True:
        blocking_reasons.append("structure_evidence_intercompany_eliminations_unconfirmed")

    if status in {"missing", "expert_review_required"}:
        blocking_reasons.append(f"structure_evidence_{status}")

    assembly = assembly_provenance or {}
    assembly_contract = _text(assembly.get("contract_version"))
    assembly_revision = _text(assembly.get("structure_evidence_revision"))
    assembly_basis = _text(assembly.get("aggregation_basis"))
    assembly_perimeter_ids = _text_list(assembly.get("perimeter_entity_ids"))
    assembly_currency = (_text(assembly.get("currency")) or "").upper()
    assembly_valuation_date = _text(assembly.get("valuation_lens_date"))
    assembly_decision_ids = _text_list(assembly.get("decision_ids"))
    accepted_decision_ids = [
        decision_id
        for raw_decision_id in accepted_holdings_decision_ids
        if (decision_id := _text(raw_decision_id)) is not None
    ]
    raw_assembly_bindings = assembly.get("entity_report_bindings")
    assembly_binding_rows = raw_assembly_bindings if isinstance(raw_assembly_bindings, list) else []
    normalized_assembly_bindings = [
        {
            "entity_id": _text(_mapping(row).get("entity_id")),
            "valuation_report_id": _text(_mapping(row).get("valuation_report_id")),
            "valuation_evidence_revision_id": _text(
                _mapping(row).get("valuation_evidence_revision_id")
            ),
        }
        for row in assembly_binding_rows
    ]
    normalized_submitted_bindings = [
        {
            "entity_id": _text(_mapping(row).get("entity_id")),
            "valuation_report_id": _text(_mapping(row).get("valuation_report_id")),
            "valuation_evidence_revision_id": _text(
                _mapping(row).get("valuation_evidence_revision_id")
            ),
        }
        for row in entity_report_bindings
    ]
    try:
        parsed_assembly_date = (
            date.fromisoformat(assembly_valuation_date) if assembly_valuation_date else None
        )
    except ValueError:
        parsed_assembly_date = None
    assembly_entity_ids = [
        str(row["entity_id"])
        for row in normalized_assembly_bindings
        if row["entity_id"] is not None
    ]
    assembly_report_ids = [
        str(row["valuation_report_id"])
        for row in normalized_assembly_bindings
        if row["valuation_report_id"] is not None
    ]
    assembly_valuation_revisions = [
        str(row["valuation_evidence_revision_id"])
        for row in normalized_assembly_bindings
        if row["valuation_evidence_revision_id"] is not None
    ]
    submitted_by_entity = {
        str(row["entity_id"]): row
        for row in normalized_submitted_bindings
        if row["entity_id"] is not None
    }
    assembly_by_entity = {
        str(row["entity_id"]): row
        for row in normalized_assembly_bindings
        if row["entity_id"] is not None
    }
    if assembly_contract != "holdings_assembly.v2":
        blocking_reasons.append("structure_evidence_assembly_contract_unsupported")
    if _text(assembly.get("authority")) != "titan":
        blocking_reasons.append("structure_evidence_assembly_authority_invalid")
    if assembly_revision != provenance.get("revision"):
        blocking_reasons.append("structure_evidence_assembly_revision_mismatch")
    if _text(holdings_revision_id) != provenance.get("revision"):
        blocking_reasons.append("structure_evidence_holdings_revision_mismatch")
    if assembly_basis != aggregation_basis:
        blocking_reasons.append("structure_evidence_assembly_basis_mismatch")
    if set(assembly_perimeter_ids) != expected_entity_ids or len(assembly_perimeter_ids) != len(
        expected_entity_ids
    ):
        blocking_reasons.append("structure_evidence_assembly_perimeter_mismatch")
    complete_binding_count = subsidiary_count + 1
    bindings_complete = (
        len(normalized_assembly_bindings) == complete_binding_count
        and len(normalized_submitted_bindings) == complete_binding_count
        and len(assembly_entity_ids) == complete_binding_count
        and len(set(assembly_entity_ids)) == complete_binding_count
        and set(assembly_entity_ids) == expected_entity_ids
        and _uuid_strings_are_complete(assembly_report_ids, complete_binding_count)
        and len(assembly_valuation_revisions) == complete_binding_count
        and len(submitted_by_entity) == complete_binding_count
        and len(assembly_by_entity) == complete_binding_count
        and all(
            submitted_by_entity.get(entity_id) == assembly_by_entity.get(entity_id)
            for entity_id in expected_entity_ids
        )
        and [
            str(row["valuation_report_id"])
            for row in normalized_submitted_bindings[1:]
            if row["valuation_report_id"] is not None
        ]
        == list(subsidiary_run_ids)
    )
    if not bindings_complete:
        blocking_reasons.append("structure_evidence_assembly_reports_mismatch")
    if parsed_assembly_date is None:
        blocking_reasons.append("structure_evidence_assembly_valuation_date_invalid")
    if valuation_currency and assembly_currency != valuation_currency.upper():
        blocking_reasons.append("structure_evidence_assembly_currency_mismatch")
    if intercompany_entries_present and not assembly_decision_ids:
        blocking_reasons.append("structure_evidence_assembly_decisions_missing")
    if len(set(assembly_decision_ids)) != len(assembly_decision_ids) or not set(
        assembly_decision_ids
    ).issubset(set(accepted_decision_ids)):
        blocking_reasons.append("structure_evidence_assembly_decisions_mismatch")

    normalized: dict[str, object] = {
        "contract_version": contract_version,
        "jurisdiction": jurisdiction,
        "status": status,
        "entities": entities,
        "ownership_links": links,
        "signals": signals,
        "consolidation": consolidation,
        "perimeter": perimeter,
        "provenance": provenance,
        "assembly_provenance": dict(assembly),
    }
    all_reasons = tuple(dict.fromkeys((*blocking_reasons, *reasons)))
    consolidation_allowed = not blocking_reasons
    scenario_eligible = consolidation_allowed and not reasons
    expert_review_required = bool(blocking_reasons) or status == "expert_review_required"
    return StructureEvidenceGate(
        present=True,
        normalized=normalized,
        consolidation_allowed=consolidation_allowed,
        scenario_eligible=scenario_eligible,
        expert_review_required=expert_review_required,
        reasons=all_reasons,
    )


__all__ = [
    "STRUCTURE_EVIDENCE_CONTRACT",
    "STRUCTURE_EVIDENCE_KEY",
    "StructureEvidenceGate",
    "evaluate_structure_evidence",
]
