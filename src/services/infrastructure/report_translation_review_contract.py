"""Static BET-291 French report translation review contract."""

from __future__ import annotations

from dataclasses import dataclass

from src.services.infrastructure.report_translation_catalog_fr_sections.copy_spacing import (
    FRENCH_PROTECTED_GLOSSARY_TERMS,
)


@dataclass(frozen=True)
class FrenchReportSurface:
    """A BET-291 report surface that must have French copy coverage."""

    surface_id: str
    template_name: str
    acceptance_label: str
    required_fields: tuple[str, ...]


@dataclass(frozen=True)
class FrenchReportSurfaceStatus:
    """Current payload/review state for one French report surface."""

    surface: FrenchReportSurface
    missing_fields: tuple[str, ...]
    pending_native_review_fields: tuple[str, ...]

    @property
    def required_field_count(self) -> int:
        return len(self.surface.required_fields)

    @property
    def present_field_count(self) -> int:
        return self.required_field_count - len(self.missing_fields)

    @property
    def native_reviewed_field_count(self) -> int:
        return self.required_field_count - len(self.pending_native_review_fields)

    @property
    def is_payload_complete(self) -> bool:
        return not self.missing_fields

    @property
    def is_native_review_complete(self) -> bool:
        return self.is_payload_complete and not self.pending_native_review_fields


@dataclass(frozen=True)
class FrenchReportPersonaSnapshot:
    """A BET-291 FR full-report snapshot fixture requirement."""

    persona_id: str
    acceptance_label: str
    expected_fixture_name: str


@dataclass(frozen=True)
class FrenchReportPersonaSnapshotStatus:
    """Current fixture state for one required FR report persona."""

    persona: FrenchReportPersonaSnapshot
    recorded_fixture_name: str | None

    @property
    def is_snapshot_complete(self) -> bool:
        return self.recorded_fixture_name == self.persona.expected_fixture_name


@dataclass(frozen=True)
class FrenchReportCopyQualityIssue:
    """A machine-detectable French copy defect that blocks release."""

    field_name: str
    issue_type: str
    token: str
    excerpt: str


BET_291_FRENCH_REPORT_SURFACES: tuple[FrenchReportSurface, ...] = (
    FrenchReportSurface(
        surface_id="cover",
        template_name="cover.jinja",
        acceptance_label="Cover page and executive summary",
        required_fields=(
            "cover_estimate_label",
            "cover_ev_label",
            "cover_equity_label",
            "cover_ebitda_label",
            "cover_multiple_label",
            "cover_date_label",
            "cover_confidential",
            "exec_summary_title",
            "exec_narrative_basis",
            "exec_ev_equity_note_title",
        ),
    ),
    FrenchReportSurface(
        surface_id="methodology",
        template_name="methodology.jinja",
        acceptance_label="10-method explanation block",
        required_fields=(
            "disc_methodology_title",
            "methodology_narrative_multiples",
            "methodology_narrative_dcf_primary",
            "methodology_narrative_asset",
            "methodology_narrative_normalization",
            "methodology_notes_multiples",
            "methodology_notes_dcf",
            "calib_methodology_label",
        ),
    ),
    FrenchReportSurface(
        surface_id="multiples",
        template_name="multiples_section.jinja",
        acceptance_label="Upswitch Index sector multiples and benchmark IDs",
        required_fields=(
            "exec_median_multiple",
            "exec_comparable_transactions",
            "exec_benchmark_source_note",
            "seller_multiple_bridge_title",
            "seller_multiple_bridge_reference",
            "seller_multiple_bridge_base",
            "seller_multiple_bridge_applied",
            "market_provenance_title",
            "market_provenance_source_managed_dataset",
            "ebitda_multiple_methodology_intro",
        ),
    ),
    FrenchReportSurface(
        surface_id="sensitivity",
        template_name="sensitivity_grid.jinja",
        acceptance_label="Sensitivity grid",
        required_fields=(
            "sensitivity_title",
            "sensitivity_description",
            "sensitivity_ebitda_multiple_header",
            "sensitivity_low",
            "sensitivity_base",
            "sensitivity_high",
            "sensitivity_range",
            "sensitivity_provenance_note_template",
            "multiple_sensitivity_matrix_title",
            "multiple_sensitivity_caption",
        ),
    ),
    FrenchReportSurface(
        surface_id="defensibility",
        template_name="defensibility_section.jinja",
        acceptance_label="Warnings and risk register",
        required_fields=(
            "high_severity_callout_title",
            "warning_thin_comparables_proxy_message",
            "warning_thin_comparables_proxy_recommendation",
            "warning_owner_concentration_skip_message",
            "warning_owner_concentration_skip_recommendation",
            "warning_net_debt_unavailable_message",
            "warning_net_debt_unavailable_recommendation",
            "warning_owner_comp_estimated_message",
            "warning_owner_comp_estimated_recommendation",
            "disc_quality_notes_title",
        ),
    ),
    FrenchReportSurface(
        surface_id="attribution",
        template_name="attribution.jinja",
        acceptance_label="Sources, methodology version, and engine semver",
        required_fields=(
            "disc_references_title",
            "disc_references_intro",
            "disc_biblio_damodaran",
            "disc_biblio_koller",
            "disc_technical_standards",
            "disc_prepared_by",
            "disc_ref_label",
            "disc_legal_footer",
            "disc_primary_text",
            "disc_regulatory_text",
        ),
    ),
    FrenchReportSurface(
        surface_id="owner_risk",
        template_name="owner_risk_ledger.jinja",
        acceptance_label="Owner Profile and transferability score block",
        required_fields=(
            "cover_owner_profiling_summary",
            "owner_profiling_section_title",
            "owner_profiling_transferability_label",
            "owner_profiling_risk_label",
            "owner_profiling_key_risks_title",
            "owner_profiling_recommendations_title",
            "owner_profiling_disclaimer",
            "sellability_section_title",
            "sellability_score_label",
            "sellability_factor_owner_dependence",
        ),
    ),
)


BET_291_FRENCH_REPORT_PERSONA_SNAPSHOTS: tuple[FrenchReportPersonaSnapshot, ...] = (
    FrenchReportPersonaSnapshot(
        persona_id="owner",
        acceptance_label="Owner full FR report",
        expected_fixture_name="fr_owner_full_report",
    ),
    FrenchReportPersonaSnapshot(
        persona_id="advisor",
        acceptance_label="Advisor full FR report",
        expected_fixture_name="fr_advisor_full_report",
    ),
    FrenchReportPersonaSnapshot(
        persona_id="startup",
        acceptance_label="Startup full FR report",
        expected_fixture_name="fr_startup_full_report",
    ),
)

# The generated FR payload is code-covered. Native BE-accountant review must be
# recorded field-by-field before a surface can be treated as ship-ready.
FRENCH_NATIVE_REVIEWED_FIELDS: frozenset[str] = frozenset()

# Full-report snapshot fixtures recorded by the BET-291 persona render tests.
FRENCH_PERSONA_SNAPSHOT_FIXTURES: dict[str, str] = {
    "owner": "fr_owner_full_report",
    "advisor": "fr_advisor_full_report",
    "startup": "fr_startup_full_report",
}

FRENCH_GLOSSARY_TERMS = FRENCH_PROTECTED_GLOSSARY_TERMS
FRENCH_NATIVE_REVIEW_DECISIONS = ("approved", "needs_revision")
BET_291_REVIEW_GUIDANCE: tuple[str, ...] = (
    "Review the runtime_copy column as the copy that will render in FR reports.",
    "Set review_decision to approved or needs_revision for every row.",
    "Preserve template variables such as {amount}, {count}, and inline HTML tags.",
    "Check Belgian-French accounting terminology, M&A terminology, grammar, and tone.",
    "Flag legal/regulatory wording that should be checked by counsel before release.",
)
