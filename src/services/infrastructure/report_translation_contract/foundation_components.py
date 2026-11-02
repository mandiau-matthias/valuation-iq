"""Reusable component foundation translation fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportTranslationFoundationComponentFields:
    # =========================================================================
    # COMPONENTS (~15 strings)
    # =========================================================================

    # Footer
    footer_indicative_estimate: str
    footer_confidential: str
    footer_page: str
    footer_of: str

    # Header
    header_confidential: str
    header_powered_by: str

    # Sensitivity Table
    sensitivity_title: str
    sensitivity_description: str
    sensitivity_ebitda_multiple_header: str
    sensitivity_low: str
    sensitivity_base: str
    sensitivity_high: str
    sensitivity_range: str
    sensitivity_illustrative_note: str
    sensitivity_corner_label: str

    # Adjustments Table
    adj_description: str
    adj_source: str
    adj_category: str
    adj_status: str
    adj_amount: str
    adj_result: str
    adj_base: str
    adj_owner: str
    adj_non_recurring: str
    adj_personal: str
    adj_related_party: str
    adj_depreciation: str
    adj_tax: str
    adj_discretionary: str
    adj_accounting: str
    adj_real_estate: str
    adj_other: str
    adj_approved: str
    adj_pending: str
    adj_rejected: str
    adj_manual: str

    # Waterfall Chart
    waterfall_title: str
    waterfall_reported: str
    waterfall_normalized: str
    waterfall_adjustment: str
    waterfall_no_data: str

    # Miscellaneous
    adj_by: str

    # Tax Latencies (Belastinglatenties)
    tax_latency_title: str
    tax_latency_description: str
    tax_latency_type: str
    tax_latency_desc_column: str
    tax_latency_temp_diff: str
    tax_latency_rate: str
    tax_latency_amount: str
    tax_latency_active: str
    tax_latency_passive: str
    tax_latency_net_impact: str
    tax_latency_account_code: str
    tax_latency_equity_bridge_qualifier: str

