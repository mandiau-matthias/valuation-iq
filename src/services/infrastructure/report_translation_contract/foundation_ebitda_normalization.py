"""EBITDA-normalization foundation translation fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationFoundationEbitdaNormalizationFields:
    # =========================================================================
    # EBITDA NORMALIZATION (~40 strings)
    # =========================================================================

    ebitda_sde_title: str
    ebitda_normalization_title: str
    ebitda_sde_description: str
    ebitda_sde_formula: str
    ebitda_sde_vs_ebitda: str
    ebitda_sde_multiples_note: str
    ebitda_dcf_description: str
    ebitda_dcf_projections_note: str
    ebitda_normalization_description: str
    ebitda_adjustments_disclaimer: str
    # Review-required normalisation disclaimer surfaced above the bridge so the
    # advisor (and any third party reading the PDF) understands the addbacks
    # are proposals requiring evidence and judgement, not formal accounting opinions.
    ebitda_ai_disclaimer_title: str
    ebitda_ai_disclaimer_body: str
    # Empty-state copy: rendered when the bridge has no real adjustments (only
    # the synthetic base/result rows). Keeps the page calm — no warning callout,
    # no audit-disclaimer scaffolding for adjustments that don't exist.
    ebitda_no_adjustments_note: str
    # Detected-but-not-applied normalization candidates note. Rendered when
    # Hermes/ledger analysis surfaced normalization candidates (e.g.
    # related-party rent, owner-comp) that are flagged for advisor review and
    # therefore NOT summed into the applied bridge. Replaces the misleading
    # "no proposals registered" copy so the €0 applied line is explained
    # rather than reading as a clean ledger. Placeholders: {count}, {amount}.
    ebitda_normalization_candidates_note: str
    # Owner-led pending-normalisation prompt: rendered in place of the
    # adjustments table when no normalisations were entered for an
    # owner-managed micro-SME. Three Towers Capital regression: a 1-owner /
    # 5-FTE consultancy with €0 of explicit adjustments rendered as if the
    # reported EBITDA was already the sustainable owner-comp-adjusted figure.
    ebitda_owner_led_pending_title: str
    ebitda_owner_led_pending_body: str
    # Variant when the weighted multi-year basis embeds prior-year normalisations
    # but the base year still has €0 explicit adjustments (Restaurant Upswitch
    # audit, Jun 2026). Placeholder: none — see multi-year table for detail.
    ebitda_owner_led_pending_body_prior_year_norms: str
    ebitda_reported_label: str
    ebitda_owner_adjustments: str
    ebitda_total_adjustments: str
    ebitda_sde_year_label: str
    ebitda_normalized_year_label: str
    ebitda_adjustments_overview: str
    ebitda_source_legend: str
    ebitda_source_yuki: str
    ebitda_source_exact: str
    ebitda_source_suggestion: str
    ebitda_source_metadata: str
    ebitda_source_manual: str
    # Source-legend descriptions — explain what each colour bullet means
    # so a CFO reviewing the bridge knows whether the adjustment came from
    # an integration sync, an AI suggestion, or a preparer override.
    ebitda_source_yuki_desc: str
    ebitda_source_exact_desc: str
    ebitda_source_suggestion_desc: str
    ebitda_source_metadata_desc: str
    ebitda_source_manual_desc: str
    ebitda_multi_year_title: str
    ebitda_sustainable_description: str
    ebitda_valuation_basis: str
    ebitda_valuation_basis_dcf: str
    ebitda_valuation_basis_asset: str
    ebitda_valuation_basis_yield: str
    ebitda_year_column: str
    filing_year_col_base: str
    filing_year_col_base_minus: str
    ebitda_reported_column: str
    ebitda_normalized_column: str
    ebitda_weight_column: str
    ebitda_weighted_column: str
    ebitda_status_column: (
        str  # DEPRECATED: Status column removed from multi-year EBITDA table (Mar 2026)
    )
    ebitda_margin_suffix: str
    ebitda_approved: str
    ebitda_calculated_total: str
    ebitda_rounded_for_valuation: str
    ebitda_weighted_average_note: str
    ebitda_advisor_weighting_audit_note: str
    ebitda_standard_average_note: str
    ebitda_recent_years_note: str
    ebitda_amounts_rounded_note: str
    ebitda_adjustments_suffix: str
    ebitda_weighting_basis_note: str
    # Variant when prior-year normalisations flow into the weighted basis.
    # Placeholder: {amount}.
    ebitda_weighting_basis_note_prior_year_norms: str
    ebitda_real_estate_carve_out_note: str

