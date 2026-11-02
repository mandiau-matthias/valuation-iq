"""SaaS cap-table foundation translation fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationFoundationSaasCapTableFields:
    # =========================================================================
    # SAAS CAP-TABLE & DILUTION PAGE (~14 strings)
    # =========================================================================

    saas_cap_table_title: str
    saas_cap_table_simulator_heading: str
    saas_cap_table_headline_sentence: str  # uses {investment} {pre_money} {dilution_pct}
    saas_cap_table_pre_money_label: str
    saas_cap_table_round_label: str
    saas_cap_table_post_money_label: str
    saas_cap_table_investor_dilution_label: str
    saas_cap_table_safe_dilution_label: str
    saas_cap_table_option_pool_label: str
    saas_cap_table_founder_dilution_label: str
    saas_cap_table_safe_overview_heading: str
    saas_cap_table_safe_principal_label: str
    saas_cap_table_safe_drag_label: str
    saas_cap_table_safe_assumption_note: str
    saas_cap_table_unavailable_note: str

