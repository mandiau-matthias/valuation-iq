"""Adjusted-NAV foundation translation fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationFoundationAdjustedNavFields:
    # =========================================================================
    # ADJUSTED NAV (Gecorrigeerde NAV) DEDICATED PAGE (~7 strings)
    # =========================================================================

    nav_page_title: str
    nav_page_subtitle: str
    nav_page_badge: str
    nav_methodology_intro: str
    nav_intrinsic_summary_header: str
    nav_intrinsic_book_equity_label: str
    nav_intrinsic_revaluation_uplift_label: str
    nav_intrinsic_value_label: str
    nav_intrinsic_uplift_pct_label: str
    nav_intrinsic_ownership_label: str
    nav_assumptions_note: str
    # Per-line labels for the NAV bridge (replace key|replace('_',' ')|title junk)
    nav_label_real_estate: str
    nav_label_hidden_reserves: str
    nav_label_inventory: str
    nav_label_receivables: str
    nav_label_goodwill_writeoff: str
    nav_label_other_revaluations: str
    nav_label_real_estate_appraisal: str
    nav_label_equipment_revaluation: str
    nav_label_off_balance: str
    # Net liability / negative NAV branding
    nav_net_liability_summary_header: str
    nav_net_liability_callout: str
    # Audit trail (round-4 — moved from FE BelgianSmeAuditPanel to report)
    nav_audit_trail_title: str
    nav_audit_trail_subtitle: str
    nav_audit_trail_re_card_title: str
    nav_audit_trail_re_book: str
    nav_audit_trail_re_appraisal: str
    nav_audit_trail_re_meerwaarde: str
    nav_audit_trail_eq_card_title: str
    nav_audit_trail_eq_subtitle_user: str
    nav_audit_trail_eq_subtitle_straight_line: str
    nav_audit_trail_eq_age_label: str
    nav_audit_trail_eq_life_label: str
    nav_audit_trail_eq_original_cost: str
    nav_audit_trail_eq_tax_book: str
    nav_audit_trail_eq_economic_book: str
    nav_audit_trail_eq_meerwaarde: str
    nav_audit_trail_dtb_title: str
    nav_audit_trail_dtb_asset_class: str
    nav_audit_trail_dtb_meerwaarde: str
    nav_audit_trail_dtb_rate: str
    nav_audit_trail_dtb_deferred_tax: str
    nav_audit_trail_dtb_source: str
    nav_audit_trail_dtb_total: str
    nav_audit_trail_dtb_effective_label: str
    nav_audit_trail_sme_title: str
    nav_audit_trail_sme_eligible: str
    nav_audit_trail_sme_standard: str
    nav_rate_source_user_override: str
    nav_rate_source_global_user_rate: str
    nav_rate_source_engine_default_per_asset: str
    nav_rate_source_engine_default_global: str
    nav_asset_class_real_estate: str
    nav_asset_class_inventory: str
    nav_asset_class_receivables: str
    nav_asset_class_hidden_reserves: str
    nav_asset_class_other_revaluations: str
    # Deal-structure comparison (Aandelen vs. Handelsfonds)
    nav_deal_structure_title: str
    nav_deal_structure_subtitle: str
    nav_deal_headline_price: str
    nav_deal_seller_tax: str
    nav_deal_seller_net_proceeds: str
    nav_deal_buyer_tax_shield: str
    nav_deal_buyer_net_cost: str
    nav_deal_indifference_premium: str
    nav_deal_indifference_caption: str

