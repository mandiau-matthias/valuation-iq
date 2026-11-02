"""Disclaimer foundation translation fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationFoundationDisclaimerFields:
    # =========================================================================
    # DISCLAIMERS (~35 strings)
    # =========================================================================

    disc_custom_disclaimer_title: str
    disc_title: str
    disc_primary_title: str
    disc_primary_text: str
    disc_custom_disclaimer_matches_primary_body: str
    disc_regulatory_title: str
    disc_regulatory_text: str
    disc_data_dependency_title: str
    disc_data_dependency_text: str
    disc_third_party_title: str
    disc_third_party_text: str
    disc_validity_title: str
    disc_validity_text: str
    disc_validity_days: str
    # Explicit review date so M&A reviewers don't have to calculate the
    # reference-period endpoint. Aggregator computes `valuation_expiry_date`
    # and the template appends it after the validity copy.
    disc_validity_until_label: str
    disc_legal_summary_title: str
    disc_legal_item_1: str
    disc_legal_item_2: str
    disc_legal_item_3: str
    disc_legal_footer: str
    disc_methodology_title: str
    disc_methodology_default: str
    disc_methodology_asset_default: str
    disc_methodology_yield_default: str
    disc_benchmarks_label: str
    disc_benchmarks_default: str
    disc_revenue_band: str
    disc_sector_label: str
    disc_technical_standards: str
    disc_quality_notes_title: str
    # "+N more" footer when quality_warnings has more items than the
    # rendered cap (round-9 audit: previously cropped silently at 3).
    disc_quality_more_label: str
    disc_prepared_by: str
    disc_ref_label: str
    disc_references_title: str
    disc_references_intro: str
    disc_references_asset_intro: str
    # Academic / industry bibliography (HTML-safe lines; use |safe in templates)
    disc_biblio_damodaran: str
    disc_biblio_koller: str
    disc_biblio_pratt: str
    disc_biblio_hitchner: str
    disc_biblio_trugman: str
    disc_biblio_pepperdine: str
    disc_biblio_vfb: str
    disc_biblio_ibba: str
    disc_biblio_ivs: str
    disc_biblio_vlerick: str
    # Round-10 audit: cited in the EV/EBITDA dossier (DLOC/DLOM bands and
    # BE peer-set) but previously absent from the references page — added
    # so an M&A reviewer can trace every claim back to its source.
    disc_biblio_mercer: str
    disc_biblio_marktlink: str
    disc_biblio_asset_nav: str
    disc_biblio_yield_income: str
    # Startup-flow corpus (rendered when the active method is
    # ``startup_valuation``; the SME corpus above stays for every other
    # method so a single report never mixes the two literatures).
    disc_biblio_startup_intro: str
    disc_biblio_berkus: str
    disc_biblio_payne: str
    disc_biblio_sahlman: str
    disc_biblio_strebulaev: str
    disc_biblio_atomico: str
    disc_biblio_dealroom: str
    disc_biblio_insead_lbs: str
    disc_biblio_index_p9: str
    disc_preparer_override_title: str
    disc_preparer_override_template: str
    preparer_adjustment_premium: str
    preparer_adjustment_discount: str
    preparer_reason_strategic_buyer_premium: str
    preparer_reason_exceptional_management_premium: str
    preparer_reason_key_person_discount: str
    preparer_reason_real_estate_included: str
    preparer_reason_customer_concentration: str
    preparer_reason_distressed_sale: str
    preparer_reason_recurring_revenue_premium: str
    preparer_reason_other: str

