"""Stage-aware transparent calculation breakdown contract fields (BET-463).

Section in the main valuation report that renders the *transparent calculation
breakdown* — the honest, stage-graded view of how the headline range (and, from
the defensible tier on, the point estimate) was derived. Fed by the
``stage_aware_breakdown`` payload Titan attaches to ``valuation_data`` before
calling ``/api/v1/reports/render``.

Default values here are the Dutch (nl) copy — the primary report language. The
English and French catalogs override these keys (see
``report_translation_catalog_{en,fr}_sections``). Caregiver-tone per the A0
brand-voice baseline; no superlatives ("best", "only", "leading" are banned —
see banned-words.txt).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationStageAwareBreakdownFields:
    # Section chrome -------------------------------------------------------
    stage_breakdown_section_title: str = "Transparante berekening"
    stage_breakdown_section_subtitle: str = (
        "Hoe deze waarde tot stand komt — de gebruikte methodes, hun gewicht "
        "en bijdrage, en wat dit cijfer in dit stadium wel en niet zegt."
    )
    # Stage / tier line ----------------------------------------------------
    stage_breakdown_stage_label: str = "Fase"
    stage_breakdown_tier_label: str = "Niveau"
    # Methods table --------------------------------------------------------
    stage_breakdown_methods_heading: str = "Methode"
    stage_breakdown_weight_heading: str = "Gewicht"
    stage_breakdown_contribution_heading: str = "Bijdrage"
    # Supporting blocks ----------------------------------------------------
    stage_breakdown_rationale_label: str = "Waarom deze methodes"
    stage_breakdown_caveats_label: str = "Wat dit cijfer wel en niet zegt"
    stage_breakdown_provenance_label: str = "Herkomst referentiepunten"
    # Reconciliation note --------------------------------------------------
    stage_breakdown_reconciles_note: str = (
        "De gewogen methodes hierboven herleiden samen tot de getoonde "
        "waarde-indicatie."
    )
    stage_breakdown_indicative_blend_note: str = (
        "De methodes hieronder vormen een indicatieve mix; in dit stadium "
        "tonen we een bandbreedte, geen puntschatting."
    )
    # Empty / no-data ------------------------------------------------------
    stage_breakdown_no_data: str = "Niet beschikbaar"
