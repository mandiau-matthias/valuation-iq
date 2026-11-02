"""Review status helpers for native-reviewed report translations."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable, Mapping

from src.services.infrastructure.report_translation_catalog_fr_sections import (
    FRENCH_REVIEWED_TRANSLATION_OVERRIDES,
)
from src.services.infrastructure.report_translation_catalog_fr_sections.copy_spacing import (
    INLINE_HTML_CLOSING_TAG_RE,
    INLINE_HTML_TAG_RE,
    TEMPLATE_VARIABLE_RE,
    repair_french_report_copy_spacing,
)
from src.services.infrastructure.report_translation_catalog_fr_sections.generated_payload import (
    FRENCH_TRANSLATION_PAYLOAD,
)
from src.services.infrastructure.report_translation_review_contract import (
    BET_291_FRENCH_REPORT_PERSONA_SNAPSHOTS,
    BET_291_FRENCH_REPORT_SURFACES,
    BET_291_REVIEW_GUIDANCE,
    FRENCH_GLOSSARY_TERMS,
    FRENCH_NATIVE_REVIEW_DECISIONS,
    FRENCH_NATIVE_REVIEWED_FIELDS,
    FRENCH_PERSONA_SNAPSHOT_FIXTURES,
    FrenchReportCopyQualityIssue,
    FrenchReportPersonaSnapshot,
    FrenchReportPersonaSnapshotStatus,
    FrenchReportSurface,
    FrenchReportSurfaceStatus,
)


def _excerpt(value: str, start: int, end: int, radius: int = 28) -> str:
    left = max(0, start - radius)
    right = min(len(value), end + radius)
    prefix = "..." if left > 0 else ""
    suffix = "..." if right < len(value) else ""
    return f"{prefix}{value[left:right]}{suffix}"


def _has_glued_letter(value: str, start: int, end: int) -> bool:
    previous_char = value[start - 1] if start > 0 else ""
    next_char = value[end] if end < len(value) else ""
    return previous_char.isalpha() or next_char.isalpha()


def _has_glued_html_boundary(value: str, start: int, end: int) -> bool:
    previous_char = value[start - 1] if start > 0 else ""
    next_char = value[end] if end < len(value) else ""
    if INLINE_HTML_CLOSING_TAG_RE.match(value, start):
        return next_char.isalpha()
    return previous_char.isalpha()


def _iter_glued_token_issues(
    field_name: str,
    value: str,
    issue_type: str,
    token_pattern: re.Pattern[str],
    *,
    boundary_checker=_has_glued_letter,
) -> tuple[FrenchReportCopyQualityIssue, ...]:
    return tuple(
        FrenchReportCopyQualityIssue(
            field_name=field_name,
            issue_type=issue_type,
            token=match.group(0),
            excerpt=_excerpt(value, match.start(), match.end()),
        )
        for match in token_pattern.finditer(value)
        if boundary_checker(value, match.start(), match.end())
    )


def build_french_report_copy_quality_issues(
    payload: Mapping[str, object] | None = None,
    *,
    repair_spacing: bool = False,
) -> tuple[FrenchReportCopyQualityIssue, ...]:
    """Return deterministic machine-detectable copy defects in the FR payload."""

    source = FRENCH_TRANSLATION_PAYLOAD if payload is None else payload
    if repair_spacing:
        source = repair_french_report_copy_spacing(source)

    glossary_patterns = tuple(
        re.compile(re.escape(term)) for term in sorted(FRENCH_GLOSSARY_TERMS, key=len, reverse=True)
    )
    issues: list[FrenchReportCopyQualityIssue] = []

    for field_name, raw_value in sorted(source.items()):
        if not isinstance(raw_value, str):
            continue

        for pattern in glossary_patterns:
            issues.extend(
                _iter_glued_token_issues(
                    field_name,
                    raw_value,
                    "glued_glossary_term",
                    pattern,
                )
            )

        issues.extend(
            _iter_glued_token_issues(
                field_name,
                raw_value,
                "glued_template_variable",
                TEMPLATE_VARIABLE_RE,
            )
        )
        issues.extend(
            _iter_glued_token_issues(
                field_name,
                raw_value,
                "glued_inline_html_tag",
                INLINE_HTML_TAG_RE,
                boundary_checker=_has_glued_html_boundary,
            )
        )

    return tuple(issues)


def build_french_report_surface_statuses(
    payload: Mapping[str, object] | None = None,
    native_reviewed_fields: frozenset[str] = FRENCH_NATIVE_REVIEWED_FIELDS,
) -> tuple[FrenchReportSurfaceStatus, ...]:
    """Return BET-291 payload/review status for the seven report surfaces."""

    payload_source = FRENCH_TRANSLATION_PAYLOAD if payload is None else payload
    payload_keys = set(payload_source.keys())
    reviewed = set(native_reviewed_fields)

    statuses: list[FrenchReportSurfaceStatus] = []
    for surface in BET_291_FRENCH_REPORT_SURFACES:
        required = set(surface.required_fields)
        statuses.append(
            FrenchReportSurfaceStatus(
                surface=surface,
                missing_fields=tuple(sorted(required - payload_keys)),
                pending_native_review_fields=tuple(sorted(required - reviewed)),
            )
        )
    return tuple(statuses)


def build_french_report_persona_snapshot_statuses(
    snapshot_fixtures: Mapping[str, str] | None = None,
) -> tuple[FrenchReportPersonaSnapshotStatus, ...]:
    """Return BET-291 snapshot-fixture status for owner/advisor/startup."""

    fixture_names = snapshot_fixtures or FRENCH_PERSONA_SNAPSHOT_FIXTURES
    return tuple(
        FrenchReportPersonaSnapshotStatus(
            persona=persona,
            recorded_fixture_name=fixture_names.get(persona.persona_id),
        )
        for persona in BET_291_FRENCH_REPORT_PERSONA_SNAPSHOTS
    )


def _copy_quality_issue_type_counts(
    issues: tuple[FrenchReportCopyQualityIssue, ...],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.issue_type] = counts.get(issue.issue_type, 0) + 1
    return counts


def _copy_quality_issue_dicts(
    issues: tuple[FrenchReportCopyQualityIssue, ...],
) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "field_name": issue.field_name,
            "issue_type": issue.issue_type,
            "token": issue.token,
            "excerpt": issue.excerpt,
        }
        for issue in issues
    )


def _required_native_review_field_names() -> tuple[str, ...]:
    return tuple(
        field_name
        for surface in BET_291_FRENCH_REPORT_SURFACES
        for field_name in surface.required_fields
    )


def _reviewed_override_status(
    native_reviewed_fields: frozenset[str],
    reviewed_translation_overrides: Mapping[str, object] | None = None,
) -> dict[str, object]:
    expected_fields = set(_required_native_review_field_names())
    reviewed_fields = set(native_reviewed_fields)
    overrides = (
        FRENCH_REVIEWED_TRANSLATION_OVERRIDES
        if reviewed_translation_overrides is None
        else reviewed_translation_overrides
    )
    override_keys = set(overrides.keys())
    missing_fields = tuple(sorted(reviewed_fields - override_keys))
    unknown_fields = tuple(sorted(override_keys - expected_fields))
    return {
        "complete": not missing_fields and not unknown_fields,
        "override_field_count": len(override_keys & expected_fields),
        "missing_reviewed_override_fields": missing_fields,
        "unknown_reviewed_override_fields": unknown_fields,
    }


def _string_cell(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    return value if isinstance(value, str) else ""


def _extract_tokens(pattern: re.Pattern[str], value: str) -> tuple[str, ...]:
    return tuple(match.group(0) for match in pattern.finditer(value))


def _python_assignment_literal(name: str, value: object) -> str:
    return f"{name} = {value!r}"


def _python_frozenset_assignment(name: str, values: tuple[str, ...]) -> str:
    if not values:
        return _python_assignment_literal(name, frozenset())

    lines = [f"{name} = frozenset({{"]
    lines.extend(f"    {value!r}," for value in values)
    lines.append("})")
    return "\n".join(lines)


def _python_mapping_assignment(name: str, values: Mapping[str, str]) -> str:
    if not values:
        return _python_assignment_literal(name, {})

    lines = [f"{name} = {{"]
    lines.extend(f"    {key!r}: {value!r}," for key, value in sorted(values.items()))
    lines.append("}")
    return "\n".join(lines)


def _stable_sha256(payload: object) -> str:
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _review_row_sha256(
    *,
    acceptance_label: str,
    field_name: str,
    runtime_copy: object,
    source_copy: object,
    surface_id: str,
    template_name: str,
) -> str:
    return _stable_sha256(
        {
            "acceptance_label": acceptance_label,
            "field_name": field_name,
            "runtime_copy": runtime_copy,
            "source_copy": source_copy,
            "surface_id": surface_id,
            "template_name": template_name,
            "ticket": "BET-291",
        }
    )


def build_french_report_native_review_rows(
    payload: Mapping[str, object] | None = None,
    native_reviewed_fields: frozenset[str] = FRENCH_NATIVE_REVIEWED_FIELDS,
) -> tuple[dict[str, object], ...]:
    """Return field-level rows for the native-FR BET-291 review packet."""

    source_payload = FRENCH_TRANSLATION_PAYLOAD if payload is None else payload
    runtime_payload = repair_french_report_copy_spacing(source_payload)
    reviewed = set(native_reviewed_fields)
    rows: list[dict[str, object]] = []

    for surface in BET_291_FRENCH_REPORT_SURFACES:
        for field_name in surface.required_fields:
            source_copy = source_payload.get(field_name)
            runtime_copy = runtime_payload.get(field_name)
            raw_issues = build_french_report_copy_quality_issues(payload={field_name: source_copy})
            runtime_issues = build_french_report_copy_quality_issues(
                payload={field_name: runtime_copy}
            )
            if field_name not in source_payload:
                review_status = "missing_payload"
            elif field_name in reviewed:
                review_status = "reviewed"
            else:
                review_status = "pending_native_review"

            rows.append(
                {
                    "ticket": "BET-291",
                    "surface_id": surface.surface_id,
                    "template_name": surface.template_name,
                    "acceptance_label": surface.acceptance_label,
                    "field_name": field_name,
                    "review_status": review_status,
                    "runtime_copy": runtime_copy,
                    "source_copy": source_copy,
                    "review_row_sha256": _review_row_sha256(
                        acceptance_label=surface.acceptance_label,
                        field_name=field_name,
                        runtime_copy=runtime_copy,
                        source_copy=source_copy,
                        surface_id=surface.surface_id,
                        template_name=surface.template_name,
                    ),
                    "copy_spacing_changed": runtime_copy != source_copy,
                    "raw_copy_quality_issue_count": len(raw_issues),
                    "runtime_copy_quality_issue_count": len(runtime_issues),
                    "raw_copy_quality_issues": _copy_quality_issue_dicts(raw_issues),
                    "runtime_copy_quality_issues": _copy_quality_issue_dicts(runtime_issues),
                    "review_decision": "",
                    "reviewed_copy": runtime_copy,
                    "reviewer_notes": "",
                }
            )
    return tuple(rows)


def validate_french_report_native_review_rows(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Validate a returned native-FR review CSV before release-gate recording."""

    expected_fields = set(_required_native_review_field_names())
    expected_rows_by_field = {
        _string_cell(row, "field_name"): row for row in build_french_report_native_review_rows()
    }
    seen: dict[str, Mapping[str, object]] = {}
    issues: list[dict[str, object]] = []
    decision_by_field: dict[str, str] = {}

    for row_number, row in enumerate(rows, start=2):
        field_name = _string_cell(row, "field_name").strip()
        decision = _string_cell(row, "review_decision").strip().lower()
        reviewed_copy = _string_cell(row, "reviewed_copy")
        reviewer_notes = _string_cell(row, "reviewer_notes").strip()

        if not field_name:
            issues.append(
                {
                    "row_number": row_number,
                    "field_name": field_name,
                    "issue_type": "missing_field_name",
                    "message": "Review row is missing field_name.",
                }
            )
            continue
        if field_name not in expected_fields:
            issues.append(
                {
                    "row_number": row_number,
                    "field_name": field_name,
                    "issue_type": "unknown_field",
                    "message": "Review row references a field outside BET-291 scope.",
                }
            )
            continue
        if field_name in seen:
            issues.append(
                {
                    "row_number": row_number,
                    "field_name": field_name,
                    "issue_type": "duplicate_field",
                    "message": "Review row duplicates a required field.",
                }
            )
            continue

        seen[field_name] = row
        decision_by_field[field_name] = decision
        expected_runtime_copy = _string_cell(expected_rows_by_field[field_name], "runtime_copy")
        returned_runtime_copy = _string_cell(row, "runtime_copy")
        if returned_runtime_copy != expected_runtime_copy:
            issues.append(
                {
                    "row_number": row_number,
                    "field_name": field_name,
                    "issue_type": "runtime_copy_mismatch",
                    "message": (
                        "runtime_copy must match the current ValuationIQ-generated review packet."
                    ),
                }
            )
        expected_review_row_hash = _string_cell(
            expected_rows_by_field[field_name],
            "review_row_sha256",
        )
        returned_review_row_hash = _string_cell(row, "review_row_sha256").strip().lower()
        if returned_review_row_hash != expected_review_row_hash:
            issues.append(
                {
                    "row_number": row_number,
                    "field_name": field_name,
                    "issue_type": "review_row_sha256_mismatch",
                    "message": ("review_row_sha256 must match the exported BET-291 review row."),
                }
            )
        if decision not in FRENCH_NATIVE_REVIEW_DECISIONS:
            issues.append(
                {
                    "row_number": row_number,
                    "field_name": field_name,
                    "issue_type": "invalid_review_decision",
                    "message": "review_decision must be approved or needs_revision.",
                }
            )
            continue

        if decision == "needs_revision":
            if not reviewer_notes:
                issues.append(
                    {
                        "row_number": row_number,
                        "field_name": field_name,
                        "issue_type": "missing_revision_note",
                        "message": "needs_revision rows must include reviewer_notes.",
                    }
                )
            continue

        if not reviewed_copy.strip():
            issues.append(
                {
                    "row_number": row_number,
                    "field_name": field_name,
                    "issue_type": "missing_reviewed_copy",
                    "message": "approved rows must include reviewed_copy.",
                }
            )
            continue

        original_variables = _extract_tokens(TEMPLATE_VARIABLE_RE, expected_runtime_copy)
        reviewed_variables = _extract_tokens(TEMPLATE_VARIABLE_RE, reviewed_copy)
        if original_variables != reviewed_variables:
            issues.append(
                {
                    "row_number": row_number,
                    "field_name": field_name,
                    "issue_type": "template_variable_mismatch",
                    "message": "reviewed_copy must preserve template variables in order.",
                    "expected_tokens": original_variables,
                    "actual_tokens": reviewed_variables,
                }
            )

        original_tags = _extract_tokens(INLINE_HTML_TAG_RE, expected_runtime_copy)
        reviewed_tags = _extract_tokens(INLINE_HTML_TAG_RE, reviewed_copy)
        if original_tags != reviewed_tags:
            issues.append(
                {
                    "row_number": row_number,
                    "field_name": field_name,
                    "issue_type": "inline_html_tag_mismatch",
                    "message": "reviewed_copy must preserve inline HTML tags in order.",
                    "expected_tokens": original_tags,
                    "actual_tokens": reviewed_tags,
                }
            )

        copy_issues = build_french_report_copy_quality_issues(payload={field_name: reviewed_copy})
        for issue in copy_issues:
            issues.append(
                {
                    "row_number": row_number,
                    "field_name": field_name,
                    "issue_type": f"reviewed_copy_{issue.issue_type}",
                    "message": "reviewed_copy still contains machine-detectable copy defects.",
                    "token": issue.token,
                    "excerpt": issue.excerpt,
                }
            )

    for field_name in sorted(expected_fields - set(seen)):
        issues.append(
            {
                "row_number": None,
                "field_name": field_name,
                "issue_type": "missing_review_row",
                "message": "Required BET-291 review field is missing from the returned packet.",
            }
        )

    invalid_fields = {issue["field_name"] for issue in issues if issue["field_name"]}
    approved_fields = tuple(
        sorted(
            field_name
            for field_name, decision in decision_by_field.items()
            if decision == "approved" and field_name not in invalid_fields
        )
    )
    needs_revision_fields = tuple(
        sorted(
            field_name
            for field_name, decision in decision_by_field.items()
            if decision == "needs_revision"
        )
    )

    return {
        "ticket": "BET-291",
        "expected_field_count": len(expected_fields),
        "received_field_count": len(seen),
        "approved_field_count": len(approved_fields),
        "needs_revision_field_count": len(needs_revision_fields),
        "issue_count": len(issues),
        "ready_for_release": len(issues) == 0 and len(approved_fields) == len(expected_fields),
        "approved_fields": approved_fields,
        "needs_revision_fields": needs_revision_fields,
        "issues": tuple(issues),
    }


def build_french_report_native_review_apply_packet(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Build a deterministic no-side-effects packet for applying reviewed FR copy."""

    materialized_rows = tuple(rows)
    validation = validate_french_report_native_review_rows(materialized_rows)
    ready_to_apply = bool(validation["ready_for_release"])
    approved_fields = tuple(validation["approved_fields"])
    rows_by_field = {
        _string_cell(row, "field_name").strip(): row
        for row in materialized_rows
        if _string_cell(row, "field_name").strip()
    }

    blockers: list[str] = []
    if validation["issue_count"]:
        blockers.append(f"Resolve {validation['issue_count']} review validation issue(s).")
    if validation["needs_revision_field_count"]:
        blockers.append(
            f"Resolve {validation['needs_revision_field_count']} field(s) marked needs_revision."
        )
    if validation["approved_field_count"] != validation["expected_field_count"]:
        blockers.append("Approve every required BET-291 field before applying reviewed FR copy.")

    reviewed_payload: dict[str, str] = {}
    if ready_to_apply:
        reviewed_payload = {
            field_name: _string_cell(rows_by_field[field_name], "reviewed_copy")
            for field_name in approved_fields
        }

    return {
        "ticket": "BET-291",
        "title": "French report PDF native-review apply packet",
        "ready_to_apply": ready_to_apply,
        "approved_field_count": validation["approved_field_count"],
        "expected_field_count": validation["expected_field_count"],
        "reviewed_payload_field_count": len(reviewed_payload),
        "blockers": tuple(blockers),
        "validation": validation,
        "reviewed_payload": reviewed_payload,
        "native_reviewed_fields_assignment": _python_frozenset_assignment(
            "FRENCH_NATIVE_REVIEWED_FIELDS",
            approved_fields if ready_to_apply else (),
        ),
        "reviewed_payload_assignment": _python_mapping_assignment(
            "FRENCH_REVIEWED_TRANSLATION_OVERRIDES",
            reviewed_payload,
        ),
        "reviewed_payload_target": (
            "src.services.infrastructure.report_translation_catalog_fr_sections."
            "FRENCH_REVIEWED_TRANSLATION_OVERRIDES"
        ),
        "application_guidance": (
            "Only apply this packet when ready_to_apply is true.",
            "Commit reviewed_payload into FRENCH_REVIEWED_TRANSLATION_OVERRIDES in the "
            "same change that records FRENCH_NATIVE_REVIEWED_FIELDS.",
            "After applying, french_report_review_summary() must report "
            "native_review_complete=true and ready_for_release=true.",
        ),
    }


def build_french_report_native_review_packet(
    payload: Mapping[str, object] | None = None,
    native_reviewed_fields: frozenset[str] = FRENCH_NATIVE_REVIEWED_FIELDS,
    persona_snapshot_fixtures: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Return an auditable handoff packet for the native-FR BET-291 review."""

    rows = build_french_report_native_review_rows(payload, native_reviewed_fields)
    summary = french_report_review_summary(
        payload=payload,
        native_reviewed_fields=native_reviewed_fields,
        persona_snapshot_fixtures=persona_snapshot_fixtures,
    )
    by_surface: dict[str, dict[str, object]] = {}
    for surface in BET_291_FRENCH_REPORT_SURFACES:
        surface_rows = tuple(row for row in rows if row["surface_id"] == surface.surface_id)
        by_surface[surface.surface_id] = {
            "surface_id": surface.surface_id,
            "template_name": surface.template_name,
            "acceptance_label": surface.acceptance_label,
            "field_count": len(surface_rows),
            "pending_native_review_count": sum(
                row["review_status"] == "pending_native_review" for row in surface_rows
            ),
            "missing_payload_count": sum(
                row["review_status"] == "missing_payload" for row in surface_rows
            ),
            "fields": surface_rows,
        }

    return {
        "ticket": "BET-291",
        "title": "French report PDF native-review packet",
        "review_guidance": BET_291_REVIEW_GUIDANCE,
        "summary": summary,
        "review_field_count": len(rows),
        "pending_native_review_field_count": sum(
            row["review_status"] == "pending_native_review" for row in rows
        ),
        "missing_payload_field_count": sum(
            row["review_status"] == "missing_payload" for row in rows
        ),
        "source_payload": "FRENCH_TRANSLATION_PAYLOAD",
        "runtime_payload_note": (
            "runtime_copy applies the deterministic spacing repair used by "
            "build_french_translation_payload()."
        ),
        "surfaces": by_surface,
    }


def build_french_report_release_gate_packet(
    payload: Mapping[str, object] | None = None,
    native_reviewed_fields: frozenset[str] = FRENCH_NATIVE_REVIEWED_FIELDS,
    persona_snapshot_fixtures: Mapping[str, str] | None = None,
    reviewed_translation_overrides: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Return the final BET-291 release/Done gate packet."""

    summary = french_report_review_summary(
        payload=payload,
        native_reviewed_fields=native_reviewed_fields,
        persona_snapshot_fixtures=persona_snapshot_fixtures,
        reviewed_translation_overrides=reviewed_translation_overrides,
    )
    blockers: list[str] = []

    if not summary["payload_complete"]:
        missing_count = sum(
            len(surface["missing_fields"]) for surface in summary["surfaces"].values()
        )
        blockers.append(f"French payload is missing {missing_count} required BET-291 field(s).")
    if not summary["native_review_complete"]:
        pending_count = sum(
            len(surface["pending_native_review_fields"]) for surface in summary["surfaces"].values()
        )
        blockers.append(
            f"Native-FR Belgian accountant review is missing for {pending_count} field(s)."
        )
    if not summary["persona_snapshot_complete"]:
        pending_personas = tuple(
            persona_id
            for persona_id, status in summary["persona_snapshots"].items()
            if not status["complete"]
        )
        blockers.append(
            "Required full-report FR persona snapshots are incomplete: "
            + ", ".join(pending_personas)
            + "."
        )
    if not summary["copy_quality_complete"]:
        blockers.append(
            f"French copy quality gate has {summary['copy_quality_issue_count']} issue(s)."
        )
    if not summary["reviewed_override_complete"]:
        if summary["missing_reviewed_override_fields"]:
            blockers.append(
                "Reviewed French copy overrides are missing for "
                f"{len(summary['missing_reviewed_override_fields'])} native-reviewed field(s)."
            )
        if summary["unknown_reviewed_override_fields"]:
            blockers.append(
                "Reviewed French copy overrides include "
                f"{len(summary['unknown_reviewed_override_fields'])} field(s) outside BET-291."
            )

    ready = bool(summary["ready_for_release"])
    return {
        "ticket": "BET-291",
        "title": "French report PDF release gate",
        "ready_for_release": ready,
        "exit_code": 0 if ready else 1,
        "done_gate": "move_to_done" if ready else "keep_in_progress",
        "blockers": tuple(blockers),
        "summary": summary,
    }


def french_report_review_summary(
    payload: Mapping[str, object] | None = None,
    native_reviewed_fields: frozenset[str] = FRENCH_NATIVE_REVIEWED_FIELDS,
    persona_snapshot_fixtures: Mapping[str, str] | None = None,
    reviewed_translation_overrides: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Return a compact summary suitable for release gates or Linear handoff."""

    statuses = build_french_report_surface_statuses(payload, native_reviewed_fields)
    persona_statuses = build_french_report_persona_snapshot_statuses(persona_snapshot_fixtures)
    reviewed_override_status = _reviewed_override_status(
        native_reviewed_fields,
        reviewed_translation_overrides,
    )
    raw_copy_quality_issues = build_french_report_copy_quality_issues(payload)
    copy_quality_issues = build_french_report_copy_quality_issues(payload, repair_spacing=True)
    payload_complete = all(status.is_payload_complete for status in statuses)
    native_review_complete = all(status.is_native_review_complete for status in statuses)
    persona_snapshot_complete = all(status.is_snapshot_complete for status in persona_statuses)
    copy_quality_complete = not copy_quality_issues
    copy_quality_issue_type_counts = _copy_quality_issue_type_counts(copy_quality_issues)
    raw_copy_quality_issue_type_counts = _copy_quality_issue_type_counts(raw_copy_quality_issues)
    return {
        "surface_count": len(statuses),
        "payload_complete": payload_complete,
        "native_review_complete": native_review_complete,
        "persona_snapshot_complete": persona_snapshot_complete,
        "reviewed_override_complete": reviewed_override_status["complete"],
        "reviewed_override_field_count": reviewed_override_status["override_field_count"],
        "missing_reviewed_override_fields": reviewed_override_status[
            "missing_reviewed_override_fields"
        ],
        "unknown_reviewed_override_fields": reviewed_override_status[
            "unknown_reviewed_override_fields"
        ],
        "copy_quality_complete": copy_quality_complete,
        "copy_quality_issue_count": len(copy_quality_issues),
        "copy_quality_issue_type_counts": copy_quality_issue_type_counts,
        "raw_copy_quality_issue_count": len(raw_copy_quality_issues),
        "raw_copy_quality_issue_type_counts": raw_copy_quality_issue_type_counts,
        "copy_spacing_repaired_issue_count": (
            len(raw_copy_quality_issues) - len(copy_quality_issues)
        ),
        "ready_for_release": (
            payload_complete
            and native_review_complete
            and persona_snapshot_complete
            and reviewed_override_status["complete"]
            and copy_quality_complete
        ),
        "copy_quality_issue_samples": tuple(_copy_quality_issue_dicts(copy_quality_issues[:25])),
        "surfaces": {
            status.surface.surface_id: {
                "template_name": status.surface.template_name,
                "required_field_count": status.required_field_count,
                "present_field_count": status.present_field_count,
                "native_reviewed_field_count": status.native_reviewed_field_count,
                "missing_fields": status.missing_fields,
                "pending_native_review_fields": status.pending_native_review_fields,
            }
            for status in statuses
        },
        "persona_snapshots": {
            status.persona.persona_id: {
                "acceptance_label": status.persona.acceptance_label,
                "expected_fixture_name": status.persona.expected_fixture_name,
                "recorded_fixture_name": status.recorded_fixture_name,
                "complete": status.is_snapshot_complete,
            }
            for status in persona_statuses
        },
    }
